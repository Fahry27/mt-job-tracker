from scraper.parsers.sites.base_parser import BaseParser

class ProspleParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        cards = soup.select('section[role="button"], a[href*="/jobs-internships/"]')
        for card in cards:
            a = card if card.name == "a" else card.find("a", href=True)
            if not a: continue
            href = a.get("href")
            full_url = href if href.startswith("http") else f"https://id.prosple.com{href}"
            results.append({"job_title": a.get_text(strip=True) or "Tidak tercantum", "job_url": full_url, "source_url": base_url})
        return results
