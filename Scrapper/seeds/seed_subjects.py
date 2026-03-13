"""Seed the subjects table from distinct subjects in qcaa_curriculum."""

import requests

URL = "https://viaavlsapupfausltdro.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpYWF2bHNhcHVwZmF1c2x0ZHJvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzMwMTk0NCwiZXhwIjoyMDg4ODc3OTQ0fQ.IDak1HpNBBqXXmJRdcGBsO-2jz-btct3AJgMCTmPzqw"

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

# 1. Get distinct subjects from qcaa_curriculum
resp = requests.get(f"{URL}/rest/v1/qcaa_curriculum?select=subject", headers=headers, timeout=30)
resp.raise_for_status()
rows = resp.json()
subjects = sorted(set(r["subject"] for r in rows))
print(f"Found {len(subjects)} distinct subjects in qcaa_curriculum")

# 2. Upsert into subjects table
headers["Prefer"] = "resolution=merge-duplicates,return=representation"
payload = [{"name": s} for s in subjects]
resp2 = requests.post(f"{URL}/rest/v1/subjects", headers=headers, json=payload, timeout=30)

if resp2.status_code in (200, 201):
    inserted = resp2.json()
    print(f"Inserted/upserted {len(inserted)} subjects:")
    for s in inserted:
        print(f"  id={s['id']:>3}  {s['name']}")
else:
    print(f"Error {resp2.status_code}: {resp2.text}")
