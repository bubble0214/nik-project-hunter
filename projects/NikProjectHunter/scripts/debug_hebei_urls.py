"""Debug Hebei URL date extraction"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import re

async def main():
    client = httpx.AsyncClient(timeout=30)
    r = await client.get("https://www.ccgp-hebei.gov.cn/province/")
    soup = BeautifulSoup(r.text, "html.parser")
    
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/cggg/" in href and not href.endswith("/cggg/") and not href.endswith("/cggg"):
            title = a.get_text(strip=True)
            if len(title) >= 10:
                full = f"https://www.ccgp-hebei.gov.cn{href}" if href.startswith("/") else href
                urls.add(full)
    
    print(f"Total unique URLs: {len(urls)}")
    for u in list(urls)[:10]:
        print(f"  {u}")
        # Test date extraction
        m = re.search(r"/20(\d{2})(\d{2})/t20(\d{2})(\d{2})(\d{2})_", u)
        if m:
            print(f"    -> Date: 20{m.group(1)}-{m.group(2)}-{m.group(4)}")
        m2 = re.search(r"/(20\d{2})(\d{2})/", u)
        if m2:
            print(f"    -> Dir: {m2.group(1)}-{m2.group(2)}")
    
    await client.aclose()

asyncio.run(main())