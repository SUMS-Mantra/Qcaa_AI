"""Seed the assessments table from qcaa_curriculum assessment rows."""

import requests

URL = "https://viaavlsapupfausltdro.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpYWF2bHNhcHVwZmF1c2x0ZHJvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzMwMTk0NCwiZXhwIjoyMDg4ODc3OTQ0fQ.IDak1HpNBBqXXmJRdcGBsO-2jz-btct3AJgMCTmPzqw"

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

# 1. Get all subjects (id + name)
resp = requests.get(f"{URL}/rest/v1/subjects?select=id,name&order=name", headers=headers, timeout=30)
resp.raise_for_status()
subject_map = {s["name"]: s["id"] for s in resp.json()}
print(f"Loaded {len(subject_map)} subjects")

# 2. Get all assessment rows from qcaa_curriculum (subject + section_key)
resp2 = requests.get(
    f"{URL}/rest/v1/qcaa_curriculum?section_type=eq.assessment&select=subject,section_key",
    headers=headers,
    timeout=30,
)
resp2.raise_for_status()
curriculum_assessments = resp2.json()

# 3. Build unique (subject_id, assessment_name) pairs
pairs = set()
for row in curriculum_assessments:
    subject_name = row["subject"]
    assessment_name = row["section_key"]  # e.g. "IA1", "IA2", "EA"
    subject_id = subject_map.get(subject_name)
    if subject_id:
        pairs.add((subject_id, assessment_name))

print(f"Found {len(pairs)} subject-assessment pairs")

# 4. Insert into assessments table
payload = [{"subject_id": sid, "name": name} for sid, name in sorted(pairs)]
headers["Prefer"] = "resolution=merge-duplicates,return=representation"
resp3 = requests.post(f"{URL}/rest/v1/assessments", headers=headers, json=payload, timeout=30)

if resp3.status_code in (200, 201):
    inserted = resp3.json()
    print(f"Inserted/upserted {len(inserted)} assessments:")
    for a in inserted:
        # Find subject name for display
        subj_name = next((n for n, sid in subject_map.items() if sid == a["subject_id"]), "?")
        print(f"  id={a['id']:>4}  {subj_name} — {a['name']}")
else:
    print(f"Error {resp3.status_code}: {resp3.text}")
