"""Test mark allocation extraction for Biology and Business."""
import sys, json
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
from scraper import (
    extract_pdf_text, parse_units, parse_assessments,
    parse_ismg_from_pdf, parse_mark_allocations_from_pdf, save_json
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
    mark_allocs = parse_mark_allocations_from_pdf(subj["pdf_path"])

    for assess in assessments:
        key = assess["assessment"]
        assess["ismg"] = ismgs.get(key, [])
        assess["mark_allocation"] = mark_allocs.get(key, {})

    for a in assessments:
        print(f"\n  {a['assessment']}: {a['technique'][:50]}")
        ma = a.get("mark_allocation", {})
        if ma:
            print(f"    Total marks: {ma['total_marks']}")
            for c in ma["criteria"]:
                print(f"      {c['criterion']:30s}  obj={c['objectives']:10s}  marks={c['marks']}")
        else:
            print(f"    Mark allocation: (none)")

    combined = save_json(subj["slug"], units, assessments)

# Show sample JSON
print(f"\n\n{'='*70}")
print("SAMPLE: Business IA1 mark_allocation JSON")
print(f"{'='*70}")
with open(r"C:\Qcaa_AI\Scrapper\qcaa_json\business\ia1.json", encoding="utf-8") as f:
    data = json.load(f)
    print(json.dumps(data.get("mark_allocation", {}), indent=2))
