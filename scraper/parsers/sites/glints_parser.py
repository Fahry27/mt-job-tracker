from scraper.parsers.sites.base_parser import BaseParser

class GlintsParser(BaseParser):
    def discover_links(self, soup, base_url):
        results = []
        # Glints renders job cards with links to /opportunities/jobs/[id]
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/opportunities/jobs/" in href and "/explore" not in href:
                full_url = href if href.startswith("http") else f"https://glints.com{href}"
                full_url = full_url.split("?")[0]
                if full_url not in seen:
                    seen.add(full_url)
                    title = a.get_text(strip=True) or "Tidak tercantum"
                    results.append({
                        "job_title": title,
                        "job_url": full_url,
                        "source_url": base_url
                    })
        return results
