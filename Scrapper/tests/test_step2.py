"""Quick test: check syllabus PDF URLs for a few subjects."""
import sys
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
from scraper import get_syllabus_pdf_url

test_urls = [
    ("Business", "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/humanities-social-sciences/business"),
    ("English", "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/english/english"),
    ("Biology", "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/sciences/biology"),
    ("Physics", "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/sciences/physics"),
    ("Dance", "https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/the-arts/dance"),
]

for name, url in test_urls:
    pdf = get_syllabus_pdf_url(url)
    print(f"{name:20s} -> {pdf}")
