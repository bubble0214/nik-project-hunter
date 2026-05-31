"""Debug Tianjin intent detail page"""
import asyncio, httpx
from bs4 import BeautifulSoup

async def main():
    url = "http://tjgp.cz.tj.gov.cn/viewer.do?id=1007592770&ver=2"
    client = httpx.AsyncClient(timeout=30, follow_redirects=True)
    resp = await client.get(url)
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    body = soup.get_text()
    print("Body text preview:", body[:1000])
    print("\n--- H1 tags ---")
    for h in soup.find_all("h1"):
        print(f"H1: {h.get_text(strip=True)[:80]}")
    print("\n--- H2 tags ---")
    for h in soup.find_all("h2"):
        print(f"H2: {h.get_text(strip=True)[:80]}")
    print("\n--- Title tag ---")
    t = soup.find("title")
    if t:
        print(f"Title: {t.get_text(strip=True)[:80]}")
    await client.aclose()

asyncio.run(main())