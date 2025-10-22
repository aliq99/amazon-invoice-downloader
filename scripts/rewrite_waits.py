from pathlib import Path


TARGET_PATH = Path("apps/worker/src/invoice_downloader/__main__.py")
OLD_CARD_BLOCK = """async def _wait_for_additional_cards(page, previous_count: int, timeout: int = 10000) -> bool:\n    try:\n        await page.wait_for_function(\n            \"(payload) => {\n                try {\n                    return document.querySelectorAll(payload.selector).length > payload.previous;\n                } catch (e) {\n                    return false;\n                }\n            }\",\n            arg={\"selector\": ORDER_CARD_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_orders_list(page, base_url: str, previous_count: int) -> bool:\n"""
NEW_CARD_BLOCK = """async def _wait_for_additional_cards(page, previous_count: int, timeout: int = 10000) -> bool:\n    script = \"\"\"(payload) => {\\n    try {\\n        return document.querySelectorAll(payload.selector).length > payload.previous;\\n    } catch (e) {\\n        return false;\\n    }\\n}\"\"\"\n    try:\n        await page.wait_for_function(\n            script,\n            arg={\"selector\": ORDER_CARD_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_orders_list(page, base_url: str, previous_count: int) -> bool:\n"""

OLD_TRANSACTION_BLOCK = """async def _wait_for_additional_transactions(page, previous_count: int, timeout: int = 15000) -> bool:\n    try:\n        await page.wait_for_function(\n            \"(payload) => {\n                try {\n                    return document.querySelectorAll(payload.selector).length > payload.previous;\n                } catch (e) {\n                    return false;\n                }\n            }\",\n            arg={\"selector\": TRANSACTION_LINK_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_transactions_list(page, base_url: str, previous_count: int) -> bool:\n"""
NEW_TRANSACTION_BLOCK = """async def _wait_for_additional_transactions(page, previous_count: int, timeout: int = 15000) -> bool:\n    script = \"\"\"(payload) => {\\n    try {\\n        return document.querySelectorAll(payload.selector).length > payload.previous;\\n    } catch (e) {\\n        return false;\\n    }\\n}\"\"\"\n    try:\n        await page.wait_for_function(\n            script,\n            arg={\"selector\": TRANSACTION_LINK_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_transactions_list(page, base_url: str, previous_count: int) -> bool:\n"""

def main() -> None:
    text = TARGET_PATH.read_text(encoding="utf-8")
    if OLD_CARD_BLOCK not in text or OLD_TRANSACTION_BLOCK not in text:
        raise SystemExit("expected blocks not found")

    updated = text.replace(OLD_CARD_BLOCK, NEW_CARD_BLOCK).replace(
        OLD_TRANSACTION_BLOCK, NEW_TRANSACTION_BLOCK
    )
    TARGET_PATH.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
