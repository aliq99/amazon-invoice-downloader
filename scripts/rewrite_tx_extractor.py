from pathlib import Path
import textwrap

path = Path("apps/worker/src/invoice_downloader/__main__.py")
text = path.read_text()

old_block = textwrap.dedent('''
async def _extract_transactions_order_ids(page, card_suffix: str) -> List[str]:
    pattern = re.compile(r"(\\d{3}-\\d{7}-\\d{7})")
    normalized_suffix = ''.join(ch for ch in card_suffix if ch.isdigit()) if card_suffix else ''
    anchors_script = """
    (suffix) => {
        const results = [];
        const normalized = suffix || '';
        const anchors = Array.from(document.querySelectorAll('a[href*\"order\"]'));
        for (const anchor of anchors) {
            const href = anchor.getAttribute('href') || anchor.href || '';
            const context = anchor.closest('div');
            const contextText = (context ? context.innerText : anchor.textContent || '').toLowerCase();
            if (normalized && !contextText.includes(normalized)) {
                continue;
            }
            results.push({ href, text: anchor.textContent || '' });
        }
        return results;
    }
    """
    try:
        rows = await page.evaluate(anchors_script, normalized_suffix)
    except Exception:  # noqa: BLE001
        rows = []
    log.info(f'Payments anchor sample: {rows[:5]}')
    order_ids: List[str] = []
    for row in rows:
        href = row.get("href") or ""
        text = row.get("text") or ""
        match = pattern.search(href) or pattern.search(text)
        if match:
            oid = match.group(1)
            if oid not in order_ids:
                order_ids.append(oid)
    return order_ids
''')

if old_block not in text:
    raise SystemExit('existing transactions extractor not found')

new_block = textwrap.dedent('''
async def _extract_transactions_order_ids(page, card_suffix: str) -> List[str]:
    pattern = re.compile(r"(\\d{3}-\\d{7}-\\d{7})")
    normalized_suffix = ''.join(ch for ch in card_suffix if ch.isdigit()) if card_suffix else ''
    anchors_script = """
    (suffix) => {
        const normalized = suffix || '';
        const anchors = Array.from(document.querySelectorAll('a[href*\"order\"]'));
        const results = [];
        for (const anchor of anchors) {
            const href = anchor.getAttribute('href') || anchor.href || '';
            const container = anchor.closest('.transaction-row, .transaction, .a-row') || anchor.closest('div');
            const contextText = (container ? container.innerText : anchor.textContent || '').toLowerCase();
            if (normalized && !contextText.includes(normalized)) {
                continue;
            }
            const amountMatch = contextText.match(/[-+]?\$?\d+[\.,]\d{2}/);
            results.push({
                href,
                text: anchor.textContent || '',
                context: contextText,
                amount: amountMatch ? amountMatch[0] : ''
            });
        }
        return results;
    }
    """
    try:
        rows = await page.evaluate(anchors_script, normalized_suffix)
    except Exception:  # noqa: BLE001
        rows = []
    if rows:
        log.info(f"Payments anchor sample (first 5): {rows[:5]}")
    else:
        log.info("Payments anchor sample: [] (no anchors found)")
    order_ids: List[str] = []
    for row in rows:
        href = row.get("href") or ""
        text = row.get("text") or ""
        match = pattern.search(href) or pattern.search(text)
        if not match:
            match = pattern.search(row.get('context', ''))
        if match:
            oid = match.group(1)
            if oid not in order_ids:
                order_ids.append(oid)
    return order_ids
''')

text = text.replace(old_block, new_block)

path.write_text(text, encoding='utf-8')
