"""Extract ISMG sections from Business syllabus + also from Biology with tables."""
import sys
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
import pdfplumber
import re

# Business
pdf_path = r"C:\Qcaa_AI\Scrapper\qcaa_data\business\syllabus.pdf"
with pdfplumber.open(pdf_path) as pdf:
    full_text = "\n\n".join(p.extract_text() or "" for p in pdf.pages)

ismg_pattern = re.compile(
    r"(Instrument-specific marking guide.*?)(?=Instrument-specific marking guide|Assessment\s+objectives|Glossary|References|$)",
    re.DOTALL | re.IGNORECASE,
)
matches = list(ismg_pattern.finditer(full_text))
print(f"Business: Found {len(matches)} ISMG sections\n")

for i, m in enumerate(matches):
    text = m.group(1)[:2500]
    print(f"{'='*70}")
    print(f"Business ISMG #{i+1}")
    print(f"{'='*70}")
    print(text)
    print()

# Also try table extraction from Biology IA2 pages
print("\n\n" + "="*70)
print("BIOLOGY IA2 — TABLE EXTRACTION")
print("="*70)
pdf_path2 = r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf"
with pdfplumber.open(pdf_path2) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Instrument-specific marking guide" in text and "IA2" in text:
            tables = page.extract_tables()
            print(f"\nPage {page.page_number}: {len(tables)} tables found")
            for ti, table in enumerate(tables):
                print(f"  Table {ti}: {len(table)} rows")
                for row in table[:5]:
                    print(f"    {row}")
