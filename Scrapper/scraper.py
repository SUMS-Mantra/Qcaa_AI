"""
QCAA Syllabus Scraper Pipeline
===============================
Scrapes QCAA senior subject syllabuses, downloads PDFs, extracts structured
curriculum data (units + assessments), saves as JSON, and uploads to Supabase.

Usage:
    python scraper.py                  # full pipeline
    python scraper.py --skip-download  # reuse already-downloaded PDFs
    python scraper.py --skip-upload    # skip Supabase upload
"""

import os
import re
import json
import time
import logging
import argparse
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pdfplumber
from sentence_transformers import SentenceTransformer

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_URL = "https://www.qcaa.qld.edu.au"
SYLLABUS_INDEX = f"{BASE_URL}/senior/senior-subjects/syllabuses"
DATA_DIR = Path(__file__).parent / "qcaa_data"
JSON_DIR = Path(__file__).parent / "qcaa_json"
REQUEST_DELAY = 1.5  # seconds between HTTP requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# Supabase credentials — reads from env or falls back to Backend/.env
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensions, runs locally
EMBEDDING_DIM = 384
CHUNK_MIN_WORDS = 30      # merge sections smaller than this into neighbors
CHUNK_MAX_WORDS = 500     # split sections larger than this into sub-chunks

_embedding_model: SentenceTransformer | None = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("qcaa_scraper")


# ─── Supabase env bootstrap ─────────────────────────────────────────────────
def _load_env_from_backend():
    """Fall back to reading ../Backend/.env if env vars aren't already set."""
    global SUPABASE_URL, SUPABASE_KEY
    if SUPABASE_URL and SUPABASE_KEY:
        return
    env_path = Path(__file__).parent.parent / "Backend" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key == "SUPABASE_URL" and not SUPABASE_URL:
            SUPABASE_URL = val
        elif key == "SUPABASE_SERVICE_KEY" and not SUPABASE_KEY:
            SUPABASE_KEY = val
        # (OpenAI key no longer needed — using local embeddings)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Scrape subject links (two-level: learning areas → subjects)
# ═════════════════════════════════════════════════════════════════════════════
LEARNING_AREA_RE = re.compile(
    r"https://www\.qcaa\.qld\.edu\.au/senior/senior-subjects/syllabuses/"
    r"([a-z0-9-]+)$"
)
SUBJECT_RE = re.compile(
    r"https://www\.qcaa\.qld\.edu\.au/senior/senior-subjects/syllabuses/"
    r"[a-z0-9-]+/([a-z0-9-]+)$"
)


def get_subject_links() -> list[dict]:
    """
    Two-pass scrape:
      1. Get learning area URLs from the index page.
      2. For each learning area, get individual subject URLs.
    Returns [{name, slug, url}, …].
    """
    log.info("Fetching syllabus index page ...")
    resp = requests.get(SYLLABUS_INDEX, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Collect learning area pages
    area_urls = []
    seen_areas = set()
    for a_tag in soup.select("a[href]"):
        href = a_tag["href"]
        if not isinstance(href, str):
            continue
        full = urljoin(BASE_URL, href)
        m = LEARNING_AREA_RE.match(full)
        if m and m.group(1) not in seen_areas:
            seen_areas.add(m.group(1))
            area_urls.append(full)

    log.info("Found %d learning areas", len(area_urls))

    # For each area, scrape individual subject links
    subjects = []
    seen_slugs = set()
    for area_url in area_urls:
        log.info("  Scanning area: %s", area_url.split("/")[-1])
        try:
            r = requests.get(area_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("    Failed: %s", e)
            continue

        area_soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in area_soup.select("a[href]"):
            href = a_tag["href"]
            if not isinstance(href, str):
                continue
            full = urljoin(BASE_URL, href)
            sm = SUBJECT_RE.match(full)
            if sm and sm.group(1) not in seen_slugs:
                slug = sm.group(1)
                seen_slugs.add(slug)
                name = a_tag.get_text(strip=True) or slug.replace("-", " ").title()
                subjects.append({"name": name, "slug": slug, "url": full})

        time.sleep(REQUEST_DELAY)

    log.info("Discovered %d individual subjects", len(subjects))
    for s in subjects:
        log.info("  - %s", s["name"])
    return subjects


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Download syllabus PDFs
# ═════════════════════════════════════════════════════════════════════════════
def get_syllabus_pdf_url(subject_url: str) -> str | None:
    """Visit a subject page and return the URL of the main syllabus PDF.

    QCAA syllabus PDFs follow the naming pattern: *_syll.pdf
    The first such PDF on the page is always the latest version.
    """
    resp = requests.get(subject_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    pdf_links = []
    for a_tag in soup.select("a[href$='.pdf']"):
        href = a_tag["href"]
        if not isinstance(href, str):
            continue
        full = urljoin(BASE_URL, href)
        text = a_tag.get_text(strip=True).lower()
        pdf_links.append((full, text))

    # Priority 1: URL contains "_syll" (official syllabus naming)
    for url, _ in pdf_links:
        if "_syll" in url.lower():
            return url

    # Priority 2: link text contains "syllabus"
    for url, text in pdf_links:
        if "syllabus" in text:
            return url

    # Priority 3: first PDF on the page
    if pdf_links:
        return pdf_links[0][0]

    return None


def download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF if it doesn't already exist. Returns True on success."""
    if dest.exists():
        log.info("    ✓ Already downloaded: %s", dest.name)
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("    ↓ Downloading %s", url.split("/")[-1])
    resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    log.info("    ✓ Saved → %s", dest)
    return True


def download_all_syllabuses(subjects: list[dict]) -> list[dict]:
    """Download the main syllabus PDF for each subject. Returns updated list."""
    downloaded = []
    for subj in subjects:
        log.info("Processing: %s", subj["name"])
        pdf_url = get_syllabus_pdf_url(subj["url"])
        if not pdf_url:
            log.warning("  ✗ No PDF found for %s", subj["name"])
            continue
        dest = DATA_DIR / subj["slug"] / "syllabus.pdf"
        if download_pdf(pdf_url, dest):
            subj["pdf_path"] = str(dest)
            downloaded.append(subj)
        time.sleep(REQUEST_DELAY)
    log.info("Downloaded %d / %d syllabus PDFs", len(downloaded), len(subjects))
    return downloaded


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Extract text from PDF
# ═════════════════════════════════════════════════════════════════════════════
def extract_pdf_text(pdf_path: str) -> str:
    """Extract and clean full text from a PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    raw = "\n\n".join(pages)
    # Clean up
    raw = re.sub(r"(?m)^\s*Page\s+\d+\s*(of\s+\d+)?\s*$", "", raw)  # page numbers
    raw = re.sub(r"(?m)^.*General senior syllabus.*$", "", raw)       # footer
    raw = re.sub(r"(?m)^.*Queensland Curriculum.*$", "", raw)          # header
    raw = re.sub(r"\n{3,}", "\n\n", raw)                              # excess blanks
    return raw.strip()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Parse syllabus structure
# ═════════════════════════════════════════════════════════════════════════════

# ── 4a. Units ────────────────────────────────────────────────────────────────
def parse_units(text: str, subject_name: str) -> list[dict]:
    """Extract Unit 1–4 information from syllabus text."""
    units = []
    # Pattern: "Unit 1: Title" or "Unit 1 — Title" or "Unit 1\nTitle"
    unit_pattern = re.compile(
        r"(?:^|\n)\s*Unit\s+(\d)\s*[:\-–—]?\s*(.+?)(?=\n)",
        re.IGNORECASE,
    )
    matches = list(unit_pattern.finditer(text))

    for i, m in enumerate(matches):
        unit_num = int(m.group(1))
        title = re.sub(r"[\s.]+$", "", m.group(2)).strip()
        # Grab description text until next Unit heading or next major section
        start = m.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            # Stop at assessments section or end
            assess_start = re.search(
                r"\n\s*(?:Internal assessment|Assessment\s+\d|IA\d|External assessment)",
                text[start:],
                re.IGNORECASE,
            )
            end = start + assess_start.start() if assess_start else start + 3000
        description = text[start:end].strip()
        # Trim to first ~1500 chars to keep it reasonable
        if len(description) > 1500:
            description = description[:1500] + "…"

        units.append({
            "unit": f"Unit {unit_num}",
            "title": title,
            "subject": subject_name,
            "description": description,
        })

    # If regex found nothing, try a simpler approach for numbered units
    if not units:
        for n in range(1, 5):
            simple = re.search(
                rf"Unit\s+{n}\b[:\-–—]?\s*(.+?)(?:\n|$)", text, re.IGNORECASE
            )
            if simple:
                units.append({
                    "unit": f"Unit {n}",
                    "title": simple.group(1).strip(),
                    "subject": subject_name,
                    "description": "",
                })

    # Deduplicate: keep the entry with the longest description per unit number
    best: dict[str, dict] = {}
    for u in units:
        key = u["unit"]
        if key not in best or len(u.get("description", "")) > len(best[key].get("description", "")):
            best[key] = u
    units = sorted(best.values(), key=lambda u: u["unit"])

    log.info("  Parsed %d units", len(units))
    return units


# ── 4b. Assessments ─────────────────────────────────────────────────────────
ASSESSMENT_KEYS = {
    "ia1": "IA1",
    "ia2": "IA2",
    "ia3": "IA3",
    "internal assessment 1": "IA1",
    "internal assessment 2": "IA2",
    "internal assessment 3": "IA3",
    "external assessment": "External",
    "external examination": "External",
}

# Mark allocation regex — e.g. "Describing 4" or "Describing  Marks\n...3–4"
CRITERION_LINE = re.compile(
    r"^\s*([\w/\s]+?)\s+(\d+(?:[–-]\d+)?)\s*$", re.MULTILINE
)


def _extract_conditions(block: str) -> dict:
    """Pull out assessment conditions like technique, duration, length, unit."""
    cond: dict = {}
    for label, key in [
        ("Technique", "technique"),
        ("Duration", "duration"),
        ("Mode / length|Mode/length|Length", "length"),
        ("Unit/?s?", "unit"),
        ("Topic/?s?", "topic"),
        ("Individual / group|Individual/group", "group"),
    ]:
        m = re.search(
            rf"(?:^|\n)\s*(?:{label})\s+(.+?)(?=\n\s*\w+\s|$)",
            block,
            re.IGNORECASE,
        )
        if m:
            cond[key] = m.group(1).strip()
    return cond


def _extract_criteria(block: str) -> list[dict]:
    """Extract marking criteria + marks from an assessment section."""
    criteria = []
    seen = set()

    # Pattern 1: table-like "Criterion  Marks allocated"
    # Followed by rows like "Describing  4"
    table_section = re.search(
        r"(?:Marking\s+(?:summary|guide)|Criterion\s+Marks)",
        block,
        re.IGNORECASE,
    )
    search_text = block[table_section.start():] if table_section else block

    # Pattern 2: "CriterionName  Marks\n..." headers in marking guide
    header_pat = re.compile(
        r"^(Describing|Explaining|Analysing|Evaluating|Communicating|"
        r"Reasoning|Interpreting|Investigating|Creating|Applying|"
        r"Synthesising|Researching|Experimenting|Modelling|"
        r"Problem-solving|Planning)\s+Marks",
        re.MULTILINE | re.IGNORECASE,
    )
    for hm in header_pat.finditer(search_text):
        crit_name = hm.group(1).strip().title()
        if crit_name.lower() not in seen:
            # Find the highest mark range after this header
            after = search_text[hm.end(): hm.end() + 500]
            mark_m = re.search(r"(\d+)[–-](\d+)", after)
            marks = int(mark_m.group(2)) if mark_m else 0
            criteria.append({"name": crit_name, "marks": marks})
            seen.add(crit_name.lower())

    # Pattern 3: simple table rows "Describing  4"
    if not criteria:
        for cm in CRITERION_LINE.finditer(search_text):
            name = cm.group(1).strip().title()
            marks_str = cm.group(2)
            if name.lower() in (
                "overall", "total", "marks", "page", "the", "mark",
                "allocated", "provisional",
            ):
                continue
            if name.lower() not in seen:
                # Take highest number in range
                nums = re.findall(r"\d+", marks_str)
                marks = max(int(n) for n in nums) if nums else 0
                criteria.append({"name": name, "marks": marks})
                seen.add(name.lower())

    # Filter out obvious noise (multi-word sentences, non-criterion names)
    NOISE_WORDS = {
        "units", "schools", "conditions", "paper", "the", "each", "mark",
        "marks", "allocated", "total", "overall", "page", "provisional",
        "to", "in", "and", "of", "is", "are", "for",
    }
    criteria = [
        c for c in criteria
        if len(c["name"].split()) <= 3
        and c["name"].split()[0].lower() not in NOISE_WORDS
    ]

    return criteria


def parse_assessments(text: str, subject_name: str) -> list[dict]:
    """Extract IA1/IA2/IA3/External assessment details from syllabus text."""
    assessments = []

    # Find assessment section boundaries
    assess_pattern = re.compile(
        r"(?:^|\n)\s*(?:Internal\s+assessment\s+(\d)|"
        r"(External\s+(?:assessment|examination)))\s*[:\-–—]?\s*(.*?)(?=\n)",
        re.IGNORECASE,
    )
    matches = list(assess_pattern.finditer(text))

    for i, m in enumerate(matches):
        if m.group(1):
            key = f"IA{m.group(1)}"
        else:
            key = "External"
        title = m.group(3).strip() if m.group(3) else ""

        # Extract the block of text for this assessment
        start = m.start()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = min(start + 5000, len(text))
        block = text[start:end]

        conditions = _extract_conditions(block)
        criteria = _extract_criteria(block)

        # Try to get technique from title or conditions
        technique = conditions.pop("technique", title or "")
        technique = re.sub(r"[\s.]+$", "", technique).strip()

        assessment = {
            "assessment": key,
            "subject": subject_name,
            "technique": technique,
            "unit": conditions.pop("unit", ""),
            "conditions": conditions,
            "criteria": criteria,
        }
        assessments.append(assessment)

    # Fallback: look for "IA2" style headings
    if not assessments:
        for ia_pat in [r"IA(\d)", r"EA\b"]:
            for m in re.finditer(ia_pat, text, re.IGNORECASE):
                key = f"IA{m.group(1)}" if "(" in ia_pat else "External"
                block = text[m.start(): m.start() + 3000]
                assessments.append({
                    "assessment": key,
                    "subject": subject_name,
                    "technique": "",
                    "unit": "",
                    "conditions": _extract_conditions(block),
                    "criteria": _extract_criteria(block),
                })

    # Deduplicate: keep entry with the most criteria per assessment key
    best: dict[str, dict] = {}
    for a in assessments:
        key = a["assessment"]
        if key not in best or len(a.get("criteria", [])) > len(best[key].get("criteria", [])):
            best[key] = a
    assessments = sorted(best.values(), key=lambda a: a["assessment"])

    log.info("  Parsed %d assessments", len(assessments))
    return assessments


# ── 4c. ISMGs (Instrument-Specific Marking Guides) ──────────────────────────
BULLET = "\uf0b7"  # the bullet character used in QCAA PDF tables


def _parse_ismg_table(table: list[list]) -> dict | None:
    """Parse a single pdfplumber table into a structured ISMG criterion.

    Returns {"criterion": str, "bands": [{"marks": str, "descriptors": [str]}]}
    or None if the table doesn't look like an ISMG.
    """
    if not table or len(table) < 3:
        return None

    # Row 0: criterion name — first non-empty cell that isn't "Marks" or empty
    criterion = None
    for cell in table[0]:
        if cell and cell.strip() and cell.strip().lower() != "marks":
            criterion = cell.strip()
            break
    if not criterion:
        return None

    bands = []
    for row in table[1:]:
        # Find descriptors (usually column 0) and marks (usually column 3+)
        desc_text = None
        marks_text = None
        for ci, cell in enumerate(row):
            if cell is None:
                continue
            cell = cell.strip()
            if not cell:
                continue
            # Check if this cell is a mark range like "4-5", "2–3", "1", "0"
            if re.match(r"^\d+(?:\s*[–\-]\s*\d+)?$", cell) and len(cell) < 10:
                marks_text = cell.replace("–", "-").replace("\u2013", "-")
            elif cell.lower().startswith("the student response has the following"):
                continue  # skip header row
            elif cell.lower().startswith("the student response does not match"):
                # This is the "0 marks" row
                desc_text = "The student response does not match any of the descriptors above."
                marks_text = "0"
            else:
                desc_text = cell

        if desc_text and marks_text:
            # Split bullet-separated descriptors into a list
            descriptors = []
            for chunk in desc_text.split(BULLET):
                chunk = chunk.strip().rstrip(".")
                if chunk and not chunk.lower().startswith("the student response"):
                    descriptors.append(chunk)
            if not descriptors:
                descriptors = [desc_text.strip()]
            bands.append({"marks": marks_text, "descriptors": descriptors})

    if not bands:
        return None

    return {"criterion": criterion, "bands": bands}


def parse_ismg_from_pdf(pdf_path: str) -> dict[str, list[dict]]:
    """Extract all ISMGs from a syllabus PDF using table extraction.

    Returns a dict keyed by assessment key (IA1, IA2, IA3, External), where
    each value is a list of criterion dicts with mark bands and descriptors.

    Example:
        {"IA1": [
            {"criterion": "Describing", "bands": [
                {"marks": "3-4", "descriptors": ["recognition of significant..."]},
                {"marks": "2",   "descriptors": ["recognition of relevant..."]},
                ...
            ]},
            ...
        ]}
    """
    ismgs: dict[str, list[dict]] = {}
    current_key: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Check if this page starts a new ISMG section
            header_match = re.search(
                r"Instrument-specific marking guide\s*\((\w+)\)",
                text,
                re.IGNORECASE,
            )
            if header_match:
                raw_key = header_match.group(1).upper()
                # Normalise: "IA1", "IA2", "IA3", "EA" → "External"
                key: str = "External" if raw_key.startswith("E") else raw_key
                current_key = key
                if key not in ismgs:
                    ismgs[key] = []

            # If we're not inside any ISMG section, skip table extraction
            if current_key is None:
                continue

            # Check if we've left the ISMG section (hit next major heading)
            if re.search(
                r"(?:^|\n)\s*(?:Internal assessment \d|External assessment|"
                r"Assessment objectives|Glossary\b|References\b)",
                text,
                re.IGNORECASE,
            ) and not header_match:
                # Only reset if we don't also have a new ISMG header on this page
                current_key = None
                continue

            # Extract tables from this page
            tables = page.extract_tables()
            for tbl in tables:
                parsed = _parse_ismg_table(tbl)
                if parsed:
                    ismgs[current_key].append(parsed)

    total = sum(len(v) for v in ismgs.values())
    log.info("  Parsed ISMGs: %s (%d criteria total)",
             {k: len(v) for k, v in ismgs.items()}, total)
    return ismgs


# ── 4d. Mark Allocation tables ──────────────────────────────────────────────
def parse_mark_allocations_from_pdf(pdf_path: str) -> dict[str, dict]:
    """Extract mark allocation tables from a syllabus PDF.

    Returns a dict keyed by assessment key (IA1, IA2, IA3, External), where
    each value is:
        {
            "criteria": [
                {"criterion": "Describing", "objectives": "1", "marks": 4},
                ...
            ],
            "total_marks": 25
        }
    """
    allocations: dict[str, dict] = {}
    current_ia: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Track which IA section we're in by looking for assessment headings
            for m in re.finditer(
                r"Internal\s+assessment\s+(\d)|External\s+(?:assessment|examination)",
                text,
                re.IGNORECASE,
            ):
                if m.group(1):
                    current_ia = f"IA{m.group(1)}"
                else:
                    current_ia = "External"

            # Only process pages that have "Mark allocation" text
            if not re.search(r"Mark\s+allocation", text, re.IGNORECASE):
                continue
            if current_ia is None:
                continue

            tables = page.extract_tables()
            for tbl in tables:
                if not tbl or len(tbl) < 2:
                    continue

                # Check if header row contains "Criterion"
                header_cells = [
                    (c or "").strip().lower() for c in tbl[0]
                ]
                if "criterion" not in " ".join(header_cells):
                    continue

                criteria = []
                total_marks = 0
                for row in tbl[1:]:
                    cells = [(c or "").strip() for c in row]
                    # Find the first non-empty cell as criterion name
                    name = ""
                    for c in cells:
                        if c and c.lower() not in ("", "none"):
                            name = c
                            break
                    if not name:
                        continue

                    if name.lower().startswith("total"):
                        # Extract total marks
                        for c in reversed(cells):
                            if c and re.match(r"^\d+$", c):
                                total_marks = int(c)
                                break
                        continue

                    # Skip empty or header-like rows
                    if not name or name.lower() in ("criterion",):
                        continue

                    # Find objectives and marks from remaining cells
                    objectives = ""
                    marks = 0
                    numeric_cells = []
                    for c in cells:
                        if not c or c == name:
                            continue
                        # Could be objectives like "1, 2, 6" or marks like "5"
                        numeric_cells.append(c)

                    if len(numeric_cells) >= 2:
                        objectives = numeric_cells[0]
                        try:
                            marks = int(numeric_cells[-1])
                        except ValueError:
                            pass
                    elif len(numeric_cells) == 1:
                        try:
                            marks = int(numeric_cells[0])
                        except ValueError:
                            objectives = numeric_cells[0]

                    criteria.append({
                        "criterion": name,
                        "objectives": objectives,
                        "marks": marks,
                    })

                if criteria:
                    allocations[current_ia] = {
                        "criteria": criteria,
                        "total_marks": total_marks or sum(
                            c["marks"] for c in criteria
                        ),
                    }

    log.info("  Parsed mark allocations: %s",
             {k: v["total_marks"] for k, v in allocations.items()})
    return allocations


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Save JSON files
# ═════════════════════════════════════════════════════════════════════════════
def save_json(subject_slug: str, units: list[dict], assessments: list[dict]):
    """Save individual JSON files per unit and assessment."""
    out_dir = JSON_DIR / subject_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    files_written = 0

    for unit in units:
        num = re.search(r"\d+", unit["unit"])
        filename = f"unit{num.group()}.json" if num else f"unit_{unit['unit']}.json"
        path = out_dir / filename
        path.write_text(json.dumps(unit, indent=2, ensure_ascii=False), encoding="utf-8")
        files_written += 1

    for assess in assessments:
        key = assess["assessment"].lower().replace(" ", "_")
        filename = f"{key}.json" if key != "external" else "external.json"
        path = out_dir / filename
        path.write_text(
            json.dumps(assess, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        files_written += 1

    # Also save a combined file
    combined = {
        "subject": units[0]["subject"] if units else subject_slug,
        "units": units,
        "assessments": assessments,
    }
    (out_dir / "combined.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    files_written += 1

    log.info("  Saved %d JSON files → %s/", files_written, out_dir)
    return combined


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Upload to Supabase
# ═════════════════════════════════════════════════════════════════════════════
def upload_to_supabase(all_data: list[dict]):
    """Upload parsed curriculum data to the qcaa_curriculum table via REST API."""
    _load_env_from_backend()
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.warning("Supabase credentials not found — skipping upload")
        return

    log.info("Connecting to Supabase REST API …")
    rest_url = f"{SUPABASE_URL}/rest/v1/qcaa_curriculum"
    headers_sb = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    rows = []
    for subj_data in all_data:
        subject = subj_data["subject"]
        for unit in subj_data.get("units", []):
            rows.append({
                "subject": subject,
                "section_type": "unit",
                "section_key": unit["unit"],
                "content": unit,
            })
        for assess in subj_data.get("assessments", []):
            rows.append({
                "subject": subject,
                "section_type": "assessment",
                "section_key": assess["assessment"],
                "content": assess,
            })

    if not rows:
        log.warning("No data to upload")
        return

    # Upsert in batches of 50
    batch_size = 50
    uploaded = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        resp = requests.post(rest_url, headers=headers_sb, json=batch, timeout=30)
        if resp.status_code in (200, 201):
            uploaded += len(batch)
            log.info("  Uploaded %d / %d rows", uploaded, len(rows))
        else:
            log.error("  Upload failed (%d): %s", resp.status_code, resp.text[:300])

    log.info("✓ Supabase upload complete: %d rows", uploaded)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 — Text Chunking
# ═════════════════════════════════════════════════════════════════════════════

# Heading patterns that should start a new chunk.
# Uses finditer (not split) so we keep headings attached to their bodies.
_HEADING_RE = re.compile(
    r"(?:^|\n)\s*("
    r"Unit\s+\d[^:\n]*(?::\s*[^\n]*)?"            # Unit 1: Cells …
    r"|Topic\s+\d[^:\n]*(?::\s*[^\n]*)?"           # Topic 1: …
    r"|Internal\s+assessment\s+\d[^:\n]*"           # Internal assessment 1 …
    r"|External\s+(?:assessment|examination)[^:\n]*" # External assessment …
    r"|Instrument-specific\s+marking\s+guide[^\n]*"  # ISMG heading
    r"|Assessment\s+objectives[^\n]*"                # AO section
    r"|Conditions[^\n]*"                             # Conditions block
    r"|Mark\s+allocation[^\n]*"                      # Mark allocation table
    r"|Glossary[^\n]*"                               # Glossary
    r"|References[^\n]*"                             # References
    r")",
    re.IGNORECASE,
)

# Pages that commonly appear as boilerplate in QCAA PDFs
_BOILERPLATE_RE = re.compile(
    r"(?:Queensland\s+Curriculum\s+&\s+Assessment\s+Authority|"
    r"©\s*State\s+of\s+Queensland|"
    r"Page\s+\d+\s+of\s+\d+|"
    r"v\d+\.\d+\s+\w+\s+\d{4})",
    re.IGNORECASE,
)


def chunk_text(full_text: str, subject: str,
               pdf_name: str = "") -> list[dict]:
    """Split syllabus text into semantically meaningful chunks.

    Each chunk is ~30-500 words and tagged with metadata.
    Returns [{"subject", "section", "type", "text", "metadata"}, …]
    """
    # ── Step 1: find heading positions ──
    matches = list(_HEADING_RE.finditer(full_text))

    # Build (heading_text, body_text) pairs using positions
    sections: list[tuple[str, str]] = []

    # Content before first heading → "Introduction"
    first_pos = matches[0].start() if matches else len(full_text)
    intro = full_text[:first_pos].strip()
    if intro:
        sections.append(("Introduction", intro))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[body_start:body_end].strip()
        sections.append((heading, body))

    # ── Step 2: drop boilerplate-heavy & empty sections ──
    filtered: list[tuple[str, str]] = []
    for heading, body in sections:
        # Strip repeated PDF header/footer lines
        lines = body.split("\n")
        lines = [ln for ln in lines if not _BOILERPLATE_RE.search(ln)]
        body = "\n".join(lines).strip()

        word_count = len(body.split())
        if word_count < 5:
            continue

        # Skip end-matter sections that have minimal value for AI grading
        h_lower = heading.lower()
        if h_lower.startswith("references") and word_count < 60:
            continue
        if h_lower.startswith("glossary") and word_count < 60:
            continue

        filtered.append((heading, body))

    # ── Step 3: merge tiny sections into their neighbor ──
    merged: list[tuple[str, str]] = []
    for heading, body in filtered:
        if merged and len(body.split()) < CHUNK_MIN_WORDS:
            # Append to previous section's body
            prev_heading, prev_body = merged[-1]
            merged[-1] = (prev_heading, prev_body + "\n\n" + heading + "\n" + body)
        else:
            merged.append((heading, body))

    # ── Step 4: sub-split long sections, build final chunks ──
    chunks: list[dict] = []
    for heading, body in merged:
        section_type = _classify_section(heading)
        section_label = _section_label(heading)

        if len(body.split()) <= CHUNK_MAX_WORDS:
            chunks.append(_make_chunk(
                subject, section_label, section_type, body, pdf_name,
            ))
        else:
            # Split on double-newlines (paragraphs)
            paragraphs = re.split(r"\n{2,}", body)
            current_chunk = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                candidate = (current_chunk + "\n\n" + para).strip()
                if len(candidate.split()) > CHUNK_MAX_WORDS and current_chunk:
                    chunks.append(_make_chunk(
                        subject, section_label, section_type,
                        current_chunk, pdf_name,
                    ))
                    current_chunk = para
                else:
                    current_chunk = candidate
            if current_chunk and len(current_chunk.split()) >= CHUNK_MIN_WORDS:
                chunks.append(_make_chunk(
                    subject, section_label, section_type,
                    current_chunk, pdf_name,
                ))
            elif current_chunk and chunks:
                # Too small — tack onto the previous chunk
                prev = chunks[-1]
                prev["text"] += "\n\n" + current_chunk
                prev["metadata"]["word_count"] = len(prev["text"].split())

    log.info("  Chunked into %d text sections", len(chunks))
    return chunks


def _classify_section(heading: str) -> str:
    """Return a type label based on the heading text."""
    h = heading.lower()
    if "internal assessment" in h or "external" in h:
        return "assessment"
    if "instrument-specific" in h or "marking guide" in h:
        return "ismg"
    if "mark allocation" in h:
        return "mark_allocation"
    if "unit" in h:
        return "unit"
    if "topic" in h:
        return "topic"
    if "assessment objectives" in h:
        return "objectives"
    if "conditions" in h:
        return "conditions"
    if "glossary" in h:
        return "glossary"
    if "references" in h:
        return "references"
    return "general"


def _section_label(heading: str) -> str:
    """Produce a short section label like 'IA2' or 'Unit 3'."""
    h = heading.strip()
    m = re.match(r"Internal\s+assessment\s+(\d)", h, re.IGNORECASE)
    if m:
        return f"IA{m.group(1)}"
    if re.match(r"External", h, re.IGNORECASE):
        return "External"
    m = re.match(r"Unit\s+(\d)", h, re.IGNORECASE)
    if m:
        return f"Unit {m.group(1)}"
    m = re.match(r"Topic\s+(\d)", h, re.IGNORECASE)
    if m:
        return f"Topic {m.group(1)}"
    return h[:40]


def _make_chunk(subject: str, section: str, section_type: str,
                text: str, pdf_name: str) -> dict:
    return {
        "subject": subject,
        "section": section,
        "type": section_type,
        "text": text,
        "metadata": {
            "source": "QCAA syllabus",
            "pdf": pdf_name,
            "word_count": len(text.split()),
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# STEP 8 — Generate Vector Embeddings (local, no API key needed)
# ═════════════════════════════════════════════════════════════════════════════
def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (downloaded once, cached locally)."""
    global _embedding_model
    if _embedding_model is None:
        log.info("Loading embedding model '%s' …", EMBEDDING_MODEL_NAME)
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def generate_embeddings(chunks: list[dict],
                        batch_size: int = 256) -> list[list[float]]:
    """Generate embeddings for a list of text chunks locally.

    Uses sentence-transformers (all-MiniLM-L6-v2, 384 dims).
    Returns a list of embedding vectors (same order as input chunks).
    """
    model = _get_model()
    texts = [c["text"] for c in chunks]
    log.info("  Encoding %d chunks with %s …", len(texts), EMBEDDING_MODEL_NAME)
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    return [v.tolist() for v in vectors]


def generate_embedding(text: str) -> list[float]:
    """Generate a single embedding vector for one piece of text."""
    model = _get_model()
    return model.encode(text).tolist()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 9 — Store Vectors in Supabase
# ═════════════════════════════════════════════════════════════════════════════
def store_vectors_supabase(chunks: list[dict],
                          embeddings: list[list[float]]):
    """Insert text chunks with their embeddings into the qcaa_vectors table."""
    _load_env_from_backend()
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.warning("Supabase credentials not found — skipping vector upload")
        return

    rest_url = f"{SUPABASE_URL}/rest/v1/qcaa_vectors"
    headers_sb = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append({
            "subject": chunk["subject"],
            "section": chunk["section"],
            "content": chunk["text"],
            "embedding": emb,
            "metadata": chunk["metadata"],
        })

    # Insert in batches of 20 (vectors are large)
    batch_size = 20
    uploaded = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        resp = requests.post(rest_url, headers=headers_sb, json=batch, timeout=60)
        if resp.status_code in (200, 201):
            uploaded += len(batch)
            log.info("  Stored %d / %d vectors", uploaded, len(rows))
        else:
            log.error("  Vector upload failed (%d): %s",
                      resp.status_code, resp.text[:300])

    log.info("✓ Vector upload complete: %d rows", uploaded)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 10 — Main pipeline
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="QCAA Syllabus Scraper")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip PDF downloading (reuse existing files)")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip Supabase upload")
    parser.add_argument("--skip-vectors", action="store_true",
                        help="Skip embedding generation and vector upload")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("QCAA Syllabus Scraper — starting")
    log.info("=" * 60)

    # 1. Scrape subject list
    subjects = get_subject_links()
    if not subjects:
        log.error("No subjects found — check the QCAA website URL")
        return

    # 2. Download PDFs
    if not args.skip_download:
        subjects = download_all_syllabuses(subjects)
    else:
        # Attach existing PDF paths
        for subj in subjects:
            pdf = DATA_DIR / subj["slug"] / "syllabus.pdf"
            if pdf.exists():
                subj["pdf_path"] = str(pdf)
        subjects = [s for s in subjects if "pdf_path" in s]
        log.info("Found %d existing PDFs", len(subjects))

    # 3–5. Extract, parse, save
    all_data = []
    all_chunks: list[dict] = []
    for subj in subjects:
        log.info("Parsing: %s", subj["name"])
        text = extract_pdf_text(subj["pdf_path"])
        if len(text) < 100:
            log.warning("  ✗ Very little text extracted — skipping")
            continue

        units = parse_units(text, subj["name"])
        assessments = parse_assessments(text, subj["name"])

        # Extract ISMGs and mark allocations from PDF tables
        ismgs = parse_ismg_from_pdf(subj["pdf_path"])
        mark_allocs = parse_mark_allocations_from_pdf(subj["pdf_path"])
        for assess in assessments:
            key = assess["assessment"]
            assess["ismg"] = ismgs.get(key, [])
            assess["mark_allocation"] = mark_allocs.get(key, {})

        if not units and not assessments:
            log.warning("  ✗ No structured data found — skipping")
            continue

        combined = save_json(subj["slug"], units, assessments)
        all_data.append(combined)

        # Chunk the full text for vector embedding
        if not args.skip_vectors:
            pdf_name = Path(subj["pdf_path"]).parent.name + "_syllabus"
            subj_chunks = chunk_text(text, subj["name"], pdf_name)
            all_chunks.extend(subj_chunks)

    log.info("=" * 60)
    log.info("Parsed %d subjects total", len(all_data))

    # 6. Upload structured data
    if not args.skip_upload and all_data:
        upload_to_supabase(all_data)
    elif args.skip_upload:
        log.info("Supabase upload skipped (--skip-upload)")

    # 7. Generate embeddings and store vectors
    if not args.skip_vectors and all_chunks:
        log.info("=" * 60)
        log.info("Generating embeddings for %d chunks …", len(all_chunks))
        try:
            embeddings = generate_embeddings(all_chunks)
            store_vectors_supabase(all_chunks, embeddings)
        except RuntimeError as e:
            log.error("Embedding failed: %s", e)
        except Exception as e:
            log.error("Embedding/upload error: %s", e)
    elif args.skip_vectors:
        log.info("Vector embedding skipped (--skip-vectors)")

    log.info("=" * 60)
    log.info("Done!")


if __name__ == "__main__":
    main()
