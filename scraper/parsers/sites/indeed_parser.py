from scraper.parsers.sites.base_parser import BaseParser

class IndeedParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        for a in soup.select('a[class*="jcs-JobTitle"]'):
            href = a.get("href")
            full_url = href if href.startswith("http") else f"https://id.indeed.com{href}"
            results.append({"job_title": a.get_text(strip=True), "job_url": full_url.split("&")[0], "source_url": base_url})
        return results
