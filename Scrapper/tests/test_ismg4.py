"""Check ALL pages with tables around ISMG sections."""
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
            tables = page.extract_tables()
            if tables:
                text = (page.extract_text() or "")[:100].strip().replace("\n", " | ")
                print(f"  Page {page.page_number}: {len(tables)} tables  |  {text}")
                for ti, t in enumerate(tables):
                    crit = None
                    for cell in (t[0] if t else []):
                        if cell and cell.strip() and cell.strip() != "Marks":
                            crit = cell.strip()[:40]
                            break
                    print(f"    T{ti}: {len(t)} rows, first_cell='{crit}'")
