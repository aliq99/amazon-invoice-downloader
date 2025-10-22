from pathlib import Path


TARGET_PATH = Path("apps/worker/src/invoice_downloader/__main__.py")
ORDER_SELECTOR_CALL = "document.querySelectorAll('a[href*\"order\"]')"
REPLACEMENT_CALL = "document.querySelectorAll(sel)"
ORDER_COUNT_EXPR = "document.querySelectorAll('a[href*\"order\"]').length > prev"
REPLACEMENT_COUNT_EXPR = "document.querySelectorAll(sel).length > prev"


def main() -> None:
    text = TARGET_PATH.read_text(encoding="utf-8")
    text = text.replace(ORDER_SELECTOR_CALL, REPLACEMENT_CALL)
    text = text.replace(ORDER_COUNT_EXPR, REPLACEMENT_COUNT_EXPR)
    TARGET_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
