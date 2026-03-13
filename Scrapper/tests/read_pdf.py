import pdfplumber

pdf = pdfplumber.open(r'c:\Qcaa_AI\Scrapper\IA2.pdf')
print(f'Total pages: {len(pdf.pages)}')
for i, p in enumerate(pdf.pages):
    text = p.extract_text() or ''
    print(f'\n=== Page {i+1} ===')
    print(text[:1200])
pdf.close()
