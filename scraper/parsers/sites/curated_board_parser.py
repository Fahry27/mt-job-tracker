import re
from scraper.parsers.sites.base_parser import BaseParser

class CuratedBoardParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        articles = soup.find_all(["article", "div"], class_=re.compile(r"post|item|entry", re.I))
        if not articles: articles = soup.find_all(["h2", "h3"])
        for art in articles:
            link_el = art.find("a", href=True) if art.name not in ["h2", "h3"] else art.find("a", href=True)
            if not link_el: continue
            href = link_el.get("href")
            if not href.startswith("http"): continue
            results.append({"job_title": link_el.get_text(strip=True) or "Tidak tercantum", "job_url": href, "source_url": base_url})
        return results
