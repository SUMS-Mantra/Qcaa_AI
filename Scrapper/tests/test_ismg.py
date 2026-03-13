"""Extract and display the ISMG sections from the Biology syllabus PDF."""
import sys
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
import pdfplumber
import re

pdf_path = r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf"

with pdfplumber.open(pdf_path) as pdf:
    full_text = "\n\n".join(p.extract_text() or "" for p in pdf.pages)

# Find all ISMG sections
ismg_pattern = re.compile(
    r"(Instrument-specific marking guide.*?)(?=Instrument-specific marking guide|Assessment\s+objectives|Glossary|References|$)",
    re.DOTALL | re.IGNORECASE,
)
matches = list(ismg_pattern.finditer(full_text))
print(f"Found {len(matches)} ISMG sections\n")

for i, m in enumerate(matches):
    text = m.group(1)[:2000]
    print(f"{'='*70}")
    print(f"ISMG #{i+1} (starts at char {m.start()})")
    print(f"{'='*70}")
    print(text)
    print()
