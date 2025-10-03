from pathlib import Path
path = Path('src/invoice_downloader/__main__.py')
text = path.read_text()
text = text.replace("document.querySelectorAll('a[href*\\"order\\"]')", "document.querySelectorAll(sel)")
text = text.replace("document.querySelectorAll('a[href*\\"order\\"]').length > prev", "document.querySelectorAll(sel).length > prev")
path.write_text(text, encoding='utf-8')
