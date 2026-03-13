"""Examine mark allocation tables in Biology and Business PDFs."""
import pdfplumber
import re

for name, path in [
    ("Biology", r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf"),
    ("Business", r"C:\Qcaa_AI\Scrapper\qcaa_data\business\syllabus.pdf"),
]:
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if re.search(r"Mark\s+allocation|Marks?\s+allocated", text, re.IGNORECASE):
                # Show surrounding context
                for m in re.finditer(r"Mark\s+allocation|Marks?\s+allocated", text, re.IGNORECASE):
                    start = max(0, m.start() - 50)
                    end = min(len(text), m.end() + 500)
                    snippet = text[start:end]
                    print(f"\n  Page {page.page_number} (char {m.start()}):")
                    print(f"  {snippet}")
                
                # Also show tables on this page
                tables = page.extract_tables()
                if tables:
                    for ti, t in enumerate(tables):
                        print(f"\n  Page {page.page_number} Table {ti}: {len(t)} rows")
                        for row in t:
                            print(f"    {row}")
