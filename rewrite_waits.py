from pathlib import Path
import textwrap

path = Path("src/invoice_downloader/__main__.py")
text = path.read_text()

old_cards = """async def _wait_for_additional_cards(page, previous_count: int, timeout: int = 10000) -> bool:\n    try:\n        await page.wait_for_function(\n            \"(payload) => {\n                try {\n                    return document.querySelectorAll(payload.selector).length > payload.previous;\n                } catch (e) {\n                    return false;\n                }\n            }\",\n            arg={\"selector\": ORDER_CARD_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_orders_list(page, base_url: str, previous_count: int) -> bool:\n"""
new_cards = """async def _wait_for_additional_cards(page, previous_count: int, timeout: int = 10000) -> bool:\n    script = \"\"\"(payload) => {\\n    try {\\n        return document.querySelectorAll(payload.selector).length > payload.previous;\\n    } catch (e) {\\n        return false;\\n    }\\n}\"\"\"\n    try:\n        await page.wait_for_function(\n            script,\n            arg={\"selector\": ORDER_CARD_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_orders_list(page, base_url: str, previous_count: int) -> bool:\n"""

old_tx = """async def _wait_for_additional_transactions(page, previous_count: int, timeout: int = 15000) -> bool:\n    try:\n        await page.wait_for_function(\n            \"(payload) => {\n                try {\n                    return document.querySelectorAll(payload.selector).length > payload.previous;\n                } catch (e) {\n                    return false;\n                }\n            }\",\n            arg={\"selector\": TRANSACTION_LINK_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_transactions_list(page, base_url: str, previous_count: int) -> bool:\n"""
new_tx = """async def _wait_for_additional_transactions(page, previous_count: int, timeout: int = 15000) -> bool:\n    script = \"\"\"(payload) => {\\n    try {\\n        return document.querySelectorAll(payload.selector).length > payload.previous;\\n    } catch (e) {\\n        return false;\\n    }\\n}\"\"\"\n    try:\n        await page.wait_for_function(\n            script,\n            arg={\"selector\": TRANSACTION_LINK_SELECTOR, \"previous\": previous_count},\n            timeout=timeout,\n        )\n        return True\n    except PlaywrightTimeoutError:\n        return False\n\n\nasync def _advance_transactions_list(page, base_url: str, previous_count: int) -> bool:\n"""

if old_cards not in text or old_tx not in text:
    raise SystemExit('expected blocks not found')

text = text.replace(old_cards, new_cards).replace(old_tx, new_tx)
path.write_text(text, encoding='utf-8')
