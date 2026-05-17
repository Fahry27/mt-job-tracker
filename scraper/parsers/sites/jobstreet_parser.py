from scraper.parsers.sites.base_parser import BaseParser

class JobStreetParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/id/job/" in href:
                full_url = href if href.startswith("http") else f"https://id.jobstreet.com{href}"
                results.append({"job_title": a.get_text(strip=True), "job_url": full_url.split("?")[0], "source_url": base_url})
        return results
