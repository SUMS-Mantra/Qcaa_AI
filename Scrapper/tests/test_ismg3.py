"""Check which pages have ISMG tables across both PDFs."""
import pdfplumber

for name, path in [
    ("Biology", r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf"),
    ("Business", r"C:\Qcaa_AI\Scrapper\qcaa_data\business\syllabus.pdf"),
]:
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Instrument-specific marking guide" in text or "nstrument-specific" in text:
                tables = page.extract_tables()
                print(f"  Page {page.page_number}: {len(tables)} tables  |  {text[:80].strip()}")
                if tables:
                    for ti, t in enumerate(tables):
                        # Show criterion name from first row
                        crit = t[0][1] if len(t[0]) > 1 and t[0][1] else t[0][0]
                        print(f"    Table {ti}: {len(t)} rows, criterion={crit}")
