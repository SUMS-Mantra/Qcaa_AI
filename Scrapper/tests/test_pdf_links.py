import requests
from bs4 import BeautifulSoup

r = requests.get('https://www.qcaa.qld.edu.au/senior/senior-subjects/syllabuses/humanities-social-sciences/business', headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
for a in soup.select('a[href$=".pdf"]'):
    text = a.get_text(strip=True)
    href = a.get('href','')
    print(text + ' | ' + href)
