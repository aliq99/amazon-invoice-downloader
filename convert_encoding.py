from pathlib import Path

path = Path("src/invoice_downloader/__main__.py")
text = path.read_text(encoding='utf-16').encode('utf-8').decode('utf-8')
path.write_text(text, encoding='utf-8')
