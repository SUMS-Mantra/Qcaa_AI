"""Test ISMG extraction + full pipeline for Biology and Business."""
import sys, json
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
from scraper import (
    extract_pdf_text, parse_units, parse_assessments,
    parse_ismg_from_pdf, save_json
)

subjects = [
    {"name": "Biology", "slug": "biology", "pdf_path": r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf"},
    {"name": "Business", "slug": "business", "pdf_path": r"C:\Qcaa_AI\Scrapper\qcaa_data\business\syllabus.pdf"},
]

for subj in subjects:
    print(f"\n{'='*70}")
    print(f"  {subj['name']}")
    print(f"{'='*70}")

    text = extract_pdf_text(subj["pdf_path"])
    units = parse_units(text, subj["name"])
    assessments = parse_assessments(text, subj["name"])
    ismgs = parse_ismg_from_pdf(subj["pdf_path"])

    for assess in assessments:
        key = assess["assessment"]
        assess["ismg"] = ismgs.get(key, [])

    # Print summary
    for a in assessments:
        print(f"\n  {a['assessment']}: {a['technique'][:50]}")
        if a["ismg"]:
            for crit in a["ismg"]:
                bands_summary = ", ".join(f"{b['marks']}({len(b['descriptors'])}d)" for b in crit["bands"])
                print(f"    ISMG: {crit['criterion']:25s} -> {bands_summary}")
        else:
            print(f"    ISMG: (none)")

    combined = save_json(subj["slug"], units, assessments)

# Show a sample ISMG in full JSON
print("\n\n" + "="*70)
print("SAMPLE: Biology IA2 full ISMG JSON")
print("="*70)
with open(r"C:\Qcaa_AI\Scrapper\qcaa_json\biology\ia2.json", encoding="utf-8") as f:
    data = json.load(f)
    if "ismg" in data:
        print(json.dumps(data["ismg"][:2], indent=2, ensure_ascii=False))
