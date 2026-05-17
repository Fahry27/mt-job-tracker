from scraper.parsers.sites.base_parser import BaseParser

class JoobleParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        for a in soup.select('a[href*="/desc/"]'):
            results.append({"job_title": a.get_text(strip=True), "job_url": a.get("href"), "source_url": base_url})
        return results
