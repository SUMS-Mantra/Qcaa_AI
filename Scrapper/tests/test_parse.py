"""Quick test: download + parse + save JSON for 2 subjects."""
import sys
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
from scraper import (
    download_all_syllabuses, extract_pdf_text,
    parse_units, parse_assessments, save_json
)

# Just test with Business and Biology
test_subjects = [
    {"name": "Business", "slug": "business",
     "url": "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/humanities-social-sciences/business"},
    {"name": "Biology", "slug": "biology",
     "url": "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/sciences/biology"},
]

# Download
downloaded = download_all_syllabuses(test_subjects)
print(f"\nDownloaded: {len(downloaded)}")

# Parse each
for subj in downloaded:
    print(f"\n{'='*60}")
    print(f"PARSING: {subj['name']}")
    print(f"{'='*60}")
    text = extract_pdf_text(subj["pdf_path"])
    print(f"Text length: {len(text)} chars")
    print(f"First 300 chars:\n{text[:300]}\n")

    units = parse_units(text, subj["name"])
    assessments = parse_assessments(text, subj["name"])

    print(f"\nUnits found: {len(units)}")
    for u in units:
        print(f"  {u['unit']}: {u['title'][:60]}")

    print(f"\nAssessments found: {len(assessments)}")
    for a in assessments:
        print(f"  {a['assessment']}: {a['technique'][:60] if a['technique'] else '(no technique)'}")
        if a['criteria']:
            for c in a['criteria']:
                print(f"    - {c['name']}: {c['marks']} marks")

    combined = save_json(subj["slug"], units, assessments)
    print(f"  JSON saved!")
