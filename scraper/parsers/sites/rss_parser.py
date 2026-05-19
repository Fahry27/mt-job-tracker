"""RSS Feed Parser for Indeed and other RSS-based job sources."""
import urllib.request
import xml.etree.ElementTree as ET
import re
from html import unescape

USER_AGENT = "FahryJobMatcher/1.0 (+personal local scraper)"

def parse_rss_feed(url, source_name, limit=None):
    """
    Parse RSS feed URL and return job links in standard format.
    No Playwright needed — bypasses anti-bot completely.
    """
    links = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        
        # Standard RSS 2.0 format
        items = root.findall(".//item")
        
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            
            if not link_el or not link_el.text:
                continue
            
            job_url = link_el.text.strip()
            job_title = unescape(title_el.text.strip()) if title_el is not None and title_el.text else "Tidak tercantum"
            
            # Clean HTML from description
            description = ""
            if desc_el is not None and desc_el.text:
                description = re.sub(r'<[^>]+>', '', unescape(desc_el.text)).strip()[:300]
            
            # Extract company from title (Indeed format: "Job Title - Company - Location")
            company = "Tidak tercantum"
            parts = job_title.split(" - ")
            if len(parts) >= 2:
                company = parts[-2].strip() if len(parts) >= 3 else parts[-1].strip()
                job_title = parts[0].strip()
            
            links.append({
                "job_url": job_url,
                "job_title": job_title,
                "company": company,
                "source_name": source_name,
                "source_url": url,
                "description_preview": description,
                "pub_date": pub_el.text.strip() if pub_el is not None and pub_el.text else ""
            })
            
            if limit and len(links) >= limit:
                break
        
        print(f"      RSS: {len(links)} jobs parsed from {source_name}")
        
    except Exception as e:
        print(f"      ! RSS parse error for {source_name}: {e}")
    
    return links
