from scraper.parsers.sites.base_parser import BaseParser

class KalibrrParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        # Kalibrr job cards link to /job/[id]-[slug]
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/job/" in href or "/jobs/" in href:
                full_url = href if href.startswith("http") else f"https://www.kalibrr.id{href}"
                full_url = full_url.split("?")[0]
                if full_url not in seen and "kalibrr" in full_url:
                    seen.add(full_url)
                    title = a.get_text(strip=True) or "Tidak tercantum"
                    results.append({
                        "job_title": title,
                        "job_url": full_url,
                        "source_url": base_url
                    })
        return results
