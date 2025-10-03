import argparse
import asyncio
import logging
import re
from contextlib import suppress
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parents[2]
DOWNLOAD_DIR = BASE_DIR / "downloads"
REPORTS_DIR = BASE_DIR / "reports"
USER_DATA_DIR = BASE_DIR / ".pw-user-data"
DEFAULT_CSV_PATH = REPORTS_DIR / "orders.csv"
ORDER_IDS_FILE = REPORTS_DIR / "order_ids.txt"

MAX_RETRIES = 3
RETRY_DELAY_S = 5
DETAIL_PAGE_TIMEOUT_MS = 180_000
INVOICE_DOWNLOAD_TIMEOUT_MS = 120_000
PAGINATION_MAX_WAIT_MS = 45_000
ORDER_ID_RE = re.compile(r"(\d{3}-\d{7}-\d{7})")
ORDER_CARD_LOCATOR = "[data-testid='order-card'], [id^='ordersContainer'] section, .order, .a-box-group"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def ensure_directories() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def card_last4_regex(last4: str) -> re.Pattern[str]:
    escaped = re.escape(last4)
    pattern = rf"(?:[\\*\\u2022-])+\\s*{escaped}|{escaped}"
    print(f"DEBUG: Regex pattern for {last4}: {pattern}")
    return re.compile(pattern)


async def goto_with_login(
    page, target_url: str, *, wait_until: str = "domcontentloaded", timeout: int = 60000
) -> None:
    for _ in range(2):
        await page.goto(target_url, wait_until=wait_until, timeout=timeout)
        lowered = page.url.lower()
        if "signin" not in lowered and "ap/signin" not in lowered:
            return
        log.info("LOGIN REQUIRED: complete authentication in the browser window.")
        try:
            await page.wait_for_url(lambda current: "signin" not in current.lower(), timeout=300000)
        except PlaywrightTimeoutError:
            log.error("Timeout waiting for Amazon login to finish.")
            raise
        log.info("Login successful.")
    log.warning("Still seeing sign-in page after retries; continuing.")


async def collect_order_ids(
    page, base_url: str, last4: Optional[str], year: Optional[int] = None
) -> List[str]:
    if year:
        start_url = f"{base_url}/gp/your-account/order-history?orderFilter=year-{year}"
    else:
        start_url = f"{base_url}/gp/your-account/order-history"

    await goto_with_login(page, start_url, timeout=PAGINATION_MAX_WAIT_MS)
    await page.wait_for_load_state("domcontentloaded", timeout=PAGINATION_MAX_WAIT_MS)

    gathered: List[str] = []
    seen = set()
    visited_urls = set()
    page_num = 1

    while True:
        current_url = page.url
        if current_url in visited_urls:
            log.info("Order history page %s already visited, stopping pagination.", page_num)
            break
        visited_urls.add(current_url)

        await page.wait_for_load_state("domcontentloaded", timeout=PAGINATION_MAX_WAIT_MS)
        cards = page.locator(ORDER_CARD_LOCATOR)
        count = await cards.count()
        log.info("Order history page %s: located %s cards", page_num, count)

        for idx in range(count):
            card = cards.nth(idx)
            try:
                text = await card.inner_text()
            except Exception:
                continue

            match = ORDER_ID_RE.search(text)
            if not match:
                try:
                    header_text = await card.locator("a:has-text('Order')").first.inner_text(timeout=500)
                    match = ORDER_ID_RE.search(header_text)
                except Exception:
                    match = None
            if not match:
                continue

            order_id = match.group(1)
            if order_id not in seen:
                seen.add(order_id)
                gathered.append(order_id)

        next_locator = page.locator(".a-pagination .a-last a, a:has-text('Next')")
        if await next_locator.count() == 0:
            break
        next_button = next_locator.first
        disabled = False
        with suppress(Exception):
            disabled = await next_button.is_disabled()
        if disabled:
            break

        next_href = await next_button.get_attribute("href")
        log.info("Advancing to the next order history page.")
        if next_href:
            next_url = urljoin(f"{base_url}/", next_href)
            if next_url in visited_urls:
                log.info("Next page URL already visited; stopping pagination loop.")
                break
            await goto_with_login(page, next_url, timeout=PAGINATION_MAX_WAIT_MS)
        else:
            previous_url = page.url
            await next_button.click()
            try:
                await page.wait_for_url(lambda current: current != previous_url, timeout=PAGINATION_MAX_WAIT_MS)
            except PlaywrightTimeoutError:
                log.warning("Pagination click did not change the page within the timeout; stopping.")
                break
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=PAGINATION_MAX_WAIT_MS)
        except PlaywrightTimeoutError:
            log.warning("Pagination load_state timeout; stopping.")
            break
        page_num += 1

    log.info("Collected %s order IDs from order history.", len(gathered))
    return gathered


async def _download_invoice(page, invoice_locator, destination: Path) -> bool:
    with suppress(Exception):
        await invoice_locator.scroll_into_view_if_needed(timeout=5_000)
    try:
        async with page.expect_download(timeout=INVOICE_DOWNLOAD_TIMEOUT_MS) as download_info:
            await invoice_locator.click()
        download = await download_info.value
    except PlaywrightTimeoutError:
        log.warning(
            "Invoice download did not start before timeout (%ss).",
            INVOICE_DOWNLOAD_TIMEOUT_MS // 1000,
        )
        return False
    except Exception as exc:
        log.error("Invoice click failed: %s", exc)
        return False
    try:
        await download.save_as(destination)
        return True
    except Exception as exc:
        log.error("Failed to save %s: %s", destination.name, exc)
        return False



async def download_invoice_for_order(
    page, base_url: str, order_id: str, last4: Optional[str]
) -> None:
    details_url = f"{base_url}/gp/your-account/order-details?orderID={order_id}"

    async def save_invoice_variant(invoice_url: str, suffix_parts: List[str], label: str) -> bool:
        suffix = f"_{'_'.join(suffix_parts)}" if suffix_parts else ""
        pdf_path = DOWNLOAD_DIR / f"{order_id}{suffix}.pdf"
        if pdf_path.exists():
            log.info("Skipping %s (already downloaded).", pdf_path.name)
            return False

        try:
            await goto_with_login(page, invoice_url, timeout=DETAIL_PAGE_TIMEOUT_MS)
            await page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception as exc:
            log.error("Order %s %s: failed to load invoice page: %s", order_id, label, exc)
            return False

        pdf_saved = False
        try:
            with suppress(Exception):
                await page.emulate_media(media="screen")
            await page.pdf(path=str(pdf_path))
            log.info("Saved %s", pdf_path.name)
            pdf_saved = True
        except Exception as pdf_exc:
            log.warning("Order %s %s: PDF generation failed: %s", order_id, label, pdf_exc)

            try:
                download_locator = page.locator(
                    "a[download], "
                    "button:has-text('Download'), "
                    "a:has-text('Download'), "
                    "[aria-label*='Download'], "
                    ".download-button, "
                    "button:has-text('Print')"
                ).first

                if await download_locator.count() > 0:
                    async with page.expect_download(timeout=INVOICE_DOWNLOAD_TIMEOUT_MS) as download_info:
                        await download_locator.click()
                    download = await download_info.value
                    await download.save_as(pdf_path)
                    log.info("Saved %s via download", pdf_path.name)
                    pdf_saved = True
                else:
                    log.warning("Order %s %s: no download controls available.", order_id, label)
            except PlaywrightTimeoutError:
                log.warning("Order %s %s: fallback download timeout.", order_id, label)
            except Exception as fallback_exc:
                log.error("Order %s %s: fallback download failed: %s", order_id, label, fallback_exc)

        return pdf_saved

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await goto_with_login(page, details_url, timeout=DETAIL_PAGE_TIMEOUT_MS)
            await page.wait_for_load_state("domcontentloaded", timeout=DETAIL_PAGE_TIMEOUT_MS)

            body_locator = page.locator("body")
            with suppress(Exception):
                await body_locator.wait_for(state="visible", timeout=DETAIL_PAGE_TIMEOUT_MS)

            if last4:
                matcher = card_last4_regex(last4)
                body_text = await body_locator.inner_text(timeout=DETAIL_PAGE_TIMEOUT_MS)
                log.info("Order %s: searching for pattern matching '%s'", order_id, last4)
                payment_section = (
                    body_text[body_text.find("Payment"): body_text.find("Payment") + 200]
                    if "Payment" in body_text
                    else "N/A"
                )
                log.info(
                    "Order %s: Payment section snippet: %s",
                    order_id,
                    payment_section.replace('\n', ' ')[:150],
                )
                if not matcher.search(body_text):
                    log.info("Order %s: last four %s not present, skipping.", order_id, last4)
                    return

            candidate_selectors = [
                "a[href*='invoice']",
                "a[href*='order-invoice']",
                "a[href*='summary/print']",
                "a[href*='order-summary']",
                "a[href*='print-receipt']",
                "a[href*='order-receipt']",
                "a:has-text('Invoice')",
                "a:has-text('View Invoice')",
                "a:has-text('Print invoice')",
                "a:has-text('View order summary')",
                "button:has-text('Invoice')",
                "button:has-text('Receipt')",
                "button:has-text('View')",
                "[data-a-modal*='invoice']",
                "[data-action*='invoice']",
                "a[onclick*='invoice']",
                "button[onclick*='invoice']",
            ]
            invoice_links = page.locator(", ".join(candidate_selectors))

            if await invoice_links.count() == 0:
                invoice_links = page.get_by_role(
                    "link", name=re.compile(r"invoice|receipt|summary|print", re.I)
                )

            if await invoice_links.count() == 0:
                invoice_links = page.locator(".order-actions, .order-info, #orderDetails").get_by_role(
                    "link", name=re.compile(r"invoice|receipt|summary|print", re.I)
                )

            link_count = await invoice_links.count()
            if link_count == 0:
                potential = []
                all_links = page.locator("a")
                total_links = await all_links.count()
                sample_size = min(total_links, 20)
                for i in range(sample_size):
                    link = all_links.nth(i)
                    try:
                        text = (await link.inner_text()).strip()
                    except Exception:
                        text = ""
                    href = await link.get_attribute("href")
                    if text and any(token in text.lower() for token in ("invoice", "receipt", "print", "view")):
                        snippet = f"{text[:30]} -> {href[:50] if href else 'no href'}"
                        potential.append(snippet)
                if potential:
                    log.info("Order %s: Found potential invoice links: %s", order_id, "; ".join(potential))
                log.warning("Order %s: no invoice links found.", order_id)
                return

            log.info("Order %s: found %s invoice link(s).", order_id, link_count)

            for idx in range(link_count):
                invoice_link = invoice_links.nth(idx)

                with suppress(Exception):
                    await invoice_link.scroll_into_view_if_needed(timeout=5_000)

                try:
                    await invoice_link.wait_for(state="visible", timeout=10_000)
                except PlaywrightTimeoutError:
                    log.warning("Order %s: invoice link %s not visible, skipping.", order_id, idx + 1)
                    continue

                invoice_href = (await invoice_link.get_attribute("href") or "")

                is_modal_trigger = (
                    not invoice_href
                    or invoice_href.strip() in {"", "#"}
                    or invoice_href.lower().startswith("javascript")
                )

                if is_modal_trigger:
                    try:
                        await invoice_link.click()
                        await page.wait_for_timeout(2000)

                        modal_selectors = [
                            "[role='dialog'] a[href*='/invoice/'], [role='dialog'] a[href*='invoice.pdf']",
                            ".a-popover a[href*='/invoice/'], .a-popover a[href*='invoice.pdf']",
                            ".a-modal a[href*='/invoice/'], .a-modal a[href*='invoice.pdf']",
                            "[role='dialog'] a:has-text('Invoice'):not(:has-text('Summary'))",
                            ".a-popover a:has-text('Invoice'):not(:has-text('Summary'))",
                            "[role='dialog'] a[href*='invoice']:not([href*='summary/print'])",
                            ".a-popover a[href*='invoice']:not([href*='summary/print'])",
                        ]

                        modal_locator = None
                        for selector in modal_selectors:
                            candidate = page.locator(selector)
                            if await candidate.count() > 0:
                                modal_locator = candidate
                                break

                        if not modal_locator or await modal_locator.count() == 0:
                            log.warning("Order %s: could not find invoice links in modal, skipping.", order_id)
                            await page.keyboard.press("Escape")
                            continue

                        modal_urls: List[str] = []
                        modal_count = await modal_locator.count()
                        log.info("Order %s: found %s invoice(s) in modal.", order_id, modal_count)

                        for modal_idx in range(modal_count):
                            modal_link = modal_locator.nth(modal_idx)
                            modal_href = await modal_link.get_attribute("href") or ""
                            if (
                                modal_href
                                and not modal_href.lower().startswith("javascript")
                                and "summary/print" not in modal_href
                            ):
                                modal_urls.append(urljoin(f"{base_url}/", modal_href))

                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)

                        if not modal_urls:
                            log.warning(
                                "Order %s: modal links did not contain invoice URLs, skipping.",
                                order_id,
                            )
                            continue

                        for modal_idx, modal_url in enumerate(modal_urls, start=1):
                            suffix_parts: List[str] = []
                            if link_count > 1:
                                suffix_parts.append(str(idx + 1))
                            if len(modal_urls) > 1:
                                suffix_parts.append(str(modal_idx))

                            label = f"modal invoice {modal_idx}/{len(modal_urls)}"
                            await save_invoice_variant(modal_url, suffix_parts, label)

                            if modal_idx < len(modal_urls):
                                await goto_with_login(page, details_url, timeout=DETAIL_PAGE_TIMEOUT_MS)
                                await page.wait_for_load_state("domcontentloaded", timeout=DETAIL_PAGE_TIMEOUT_MS)
                                await asyncio.sleep(1)

                        await goto_with_login(page, details_url, timeout=DETAIL_PAGE_TIMEOUT_MS)
                        await page.wait_for_load_state("domcontentloaded", timeout=DETAIL_PAGE_TIMEOUT_MS)
                        continue
                    except Exception as exc:
                        log.error(
                            "Order %s invoice %s: failed to handle modal trigger: %s",
                            order_id,
                            idx + 1,
                            exc,
                        )
                        with suppress(Exception):
                            await page.keyboard.press("Escape")
                        continue

                suffix_parts: List[str] = []
                if link_count > 1:
                    suffix_parts.append(str(idx + 1))

                label = f"invoice {idx + 1}/{link_count}"
                await save_invoice_variant(urljoin(f"{base_url}/", invoice_href), suffix_parts, label)

                if idx < link_count - 1:
                    await goto_with_login(page, details_url, timeout=DETAIL_PAGE_TIMEOUT_MS)
                    await page.wait_for_load_state("domcontentloaded", timeout=DETAIL_PAGE_TIMEOUT_MS)
                    await asyncio.sleep(2)

            return

        except PlaywrightTimeoutError:
            log.warning("Order %s: timeout while loading (attempt %s/%s).", order_id, attempt, MAX_RETRIES)
        except Exception as exc:
            log.error("Order %s: unexpected error (attempt %s/%s): %s", order_id, attempt, MAX_RETRIES, exc)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY_S)

    log.error("Order %s: exhausted retries, moving on.", order_id)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Amazon invoices by crawling order history.")
    parser.add_argument("--domain", default="www.amazon.ca", help="Amazon domain, e.g. www.amazon.com")
    parser.add_argument("--last4", default="", help="Last four digits of the payment card to filter on.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="Optional CSV report to seed order IDs.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode.")
    parser.add_argument("--force-crawl", action="store_true", help="Skip CSV and crawl order history instead.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[],
        help="One or more years to crawl (e.g. 2023 2024). Omit to use Amazon's default history.",
    )
    return parser.parse_args()


def load_ids_from_csv(csv_path: Path, last4: str) -> List[str]:
    if not csv_path.exists():
        log.warning("CSV report not found at %s.", csv_path)
        return []

    log.info("Filtering CSV report at %s for last four '%s'.", csv_path, last4)
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    cols = {c.lower().replace(" ", "-"): c for c in df.columns}
    oid_col = cols.get("order-id", cols.get("orderid"))
    if not oid_col:
        log.error("No order-id column found in CSV.")
        return []

    order_ids = df[oid_col].dropna().drop_duplicates().tolist()
    if last4:
        matcher = card_last4_regex(last4)
        pay_cols = [c for c in df.columns if "payment" in c.lower()]
        filtered = []
        for _, row in df.iterrows():
            blob = " ".join(str(row[c]) for c in pay_cols)
            if matcher.search(blob):
                filtered.append(row[oid_col])
        order_ids = list(dict.fromkeys(filtered))

    log.info("CSV provided %s distinct order IDs.", len(order_ids))
    return order_ids


async def run(args: argparse.Namespace) -> None:
    ensure_directories()
    base_url = f"https://{args.domain}"
    last4 = args.last4.strip() or None

    order_ids: List[str] = []
    if not args.force_crawl:
        order_ids.extend(load_ids_from_csv(args.csv, args.last4.strip()))
    elif ORDER_IDS_FILE.exists():
        ORDER_IDS_FILE.unlink(missing_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=args.headless,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()

        try:
            await goto_with_login(page, base_url)

            if args.force_crawl or not order_ids:
                log.info("Crawling Amazon order history for order IDs.")
                years = args.years or [None]
                for year in years:
                    label = str(year) if year else "default history"
                    log.info("Crawling %s", label)
                    crawled = await collect_order_ids(page, base_url, last4, year=year)
                    order_ids.extend(crawled)

            if not order_ids:
                log.info("No order IDs gathered; nothing to download.")
                return

            unique_ids = list(dict.fromkeys(order_ids))
            log.info("Attempting downloads for %s orders.", len(unique_ids))
            for oid in unique_ids:
                await download_invoice_for_order(page, base_url, oid, last4)
        finally:
            log.info("Closing browser context.")
            with suppress(Exception):
                await context.close()


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
