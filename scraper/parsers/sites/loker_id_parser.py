from scraper.parsers.sites.base_parser import BaseParser

class LokerIdParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        for a in soup.select('a[href*="/job/"]'):
            title = a.get_text(strip=True)
            if title and len(title) > 5:
                results.append({"job_title": title, "job_url": a.get("href"), "source_url": base_url})
        return results
