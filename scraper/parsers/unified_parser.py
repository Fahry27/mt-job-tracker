import time
import random
import re
import json
import os
import asyncio
import urllib.robotparser
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup

try:
    from config.keywords import POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, INDONESIAN_POSITIVE_KEYWORDS
    from scraper.parsers.json_ld_parser import extract_json_ld
    from scraper.parsers.sites.parser_factory import ParserFactory
    from scraper.parsers.llm_fallback import parse_with_llm
    from scraper.parsers.sites.rss_parser import parse_rss_feed
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from config.keywords import POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, INDONESIAN_POSITIVE_KEYWORDS
    from scraper.parsers.json_ld_parser import extract_json_ld
    from scraper.parsers.sites.parser_factory import ParserFactory
    from scraper.parsers.llm_fallback import parse_with_llm
    from scraper.parsers.sites.rss_parser import parse_rss_feed

URL_CACHE_FILE = "cache/scraped_urls.json"
SOURCE_HEALTH_FILE = "cache/source_health.json"
USER_AGENT = "FahryJobMatcher/1.0 (+personal local scraper)"

class UnifiedScraper:
    def __init__(self, headless=True, timeout=20000, proxies=None):
        self.headless = headless
        self.timeout = timeout # 20 seconds as requested
        self.playwright = None
        self.browser = None
        self.context = None
        self.robot_parsers = {}
        self.url_cache = self._load_url_cache()
        self.proxies = proxies or []
        self.current_proxy = None
        self.source_health = self._load_source_health()

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        
        proxy_settings = None
        env_proxy = os.getenv("PROXY_URL")
        if env_proxy:
            proxy_settings = {"server": env_proxy}
            self.current_proxy = env_proxy
        elif self.proxies:
            self.current_proxy = random.choice(self.proxies)
            proxy_settings = {"server": self.current_proxy}

        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 800},
            proxy=proxy_settings
        )

    async def stop(self):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        self._save_url_cache()
        self._finalize_source_health()

    def _load_url_cache(self):
        if os.path.exists(URL_CACHE_FILE):
            try:
                with open(URL_CACHE_FILE, "r") as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_url_cache(self):
        os.makedirs(os.path.dirname(URL_CACHE_FILE), exist_ok=True)
        with open(URL_CACHE_FILE, "w") as f:
            json.dump(self.url_cache, f, indent=2)

    def _load_source_health(self):
        if os.path.exists(SOURCE_HEALTH_FILE):
            try:
                with open(SOURCE_HEALTH_FILE, "r") as f:
                    return json.load(f)
            except: return {}
        return {}

    def _track_source(self, domain, success):
        if domain not in self.source_health:
            self.source_health[domain] = {"errors": 0, "total": 0, "blocked": False}
        self.source_health[domain]["total"] += 1
        if not success:
            self.source_health[domain]["errors"] += 1

    def _is_source_blocked(self, url):
        domain = "/".join(url.split("/")[:3])
        health = self.source_health.get(domain, {})
        if health.get("blocked"):
            print(f"      ⚠️ Skipping {domain} (auto-blacklisted: >{health.get('errors',0)}/{health.get('total',0)} errors)")
            return True
        return False

    def _finalize_source_health(self):
        for domain, data in self.source_health.items():
            total = data.get("total", 0)
            errors = data.get("errors", 0)
            if total >= 3 and errors / total > 0.8:
                data["blocked"] = True
                print(f"    ⛔ Auto-blacklisted: {domain} ({errors}/{total} errors)")
            elif total >= 3 and errors / total < 0.3:
                data["blocked"] = False  # Rehabilitate if improved
        os.makedirs(os.path.dirname(SOURCE_HEALTH_FILE), exist_ok=True)
        with open(SOURCE_HEALTH_FILE, "w") as f:
            json.dump(self.source_health, f, indent=2)

    def is_url_scraped_recently(self, url):
        if url in self.url_cache:
            last_scraped = datetime.fromisoformat(self.url_cache[url])
            if datetime.now() - last_scraped < timedelta(hours=24):
                return True
        return False

    def mark_url_scraped(self, url):
        self.url_cache[url] = datetime.now().isoformat()

    async def can_fetch(self, url):
        domain = "/".join(url.split("/")[:3])
        if domain not in self.robot_parsers:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{domain}/robots.txt")
            try:
                await asyncio.to_thread(rp.read)
                self.robot_parsers[domain] = rp
            except:
                return True # Default to True if robots.txt can't be read
        
        rp = self.robot_parsers[domain]
        # Respect Crawl-delay
        delay = rp.crawl_delay(USER_AGENT) or 3
        await asyncio.sleep(delay)
        
        return rp.can_fetch(USER_AGENT, url)

    async def get_content(self, url, retry_limit=2):
        # Check source blacklist first
        if self._is_source_blocked(url):
            return None

        if not await self.can_fetch(url):
            print(f"      ! Blocked by robots.txt: {url}")
            return None

        page = await self.context.new_page()
        await stealth_async(page)
        
        api_data_list = []
        async def handle_response(response):
            if response.request.resource_type in ["fetch", "xhr"]:
                try:
                    if response.status == 200 and "application/json" in response.headers.get("content-type", ""):
                        json_resp = await response.json()
                        if isinstance(json_resp, dict) or isinstance(json_resp, list):
                            api_data_list.append(json_resp)
                except:
                    pass

        page.on("response", handle_response)
        
        content = None
        domain_key = "/".join(url.split("/")[:3])
        for attempt in range(retry_limit + 1):
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                if not response: continue
                
                status = response.status
                if status in [429, 503]:
                    print(f"      ! HTTP {status} - Backing off... (Proxy: {self.current_proxy or 'Direct'})")
                    self._track_source(domain_key, False)
                    await asyncio.sleep(10 * (attempt + 1))
                    continue
                
                if status >= 400:
                    print(f"      ! HTTP {status} for {url}")
                    self._track_source(domain_key, False)
                    break

                self._track_source(domain_key, True)

                await asyncio.sleep(random.uniform(2, 4))
                content = await page.content()
                break
            except Exception as e:
                print(f"      X Attempt {attempt+1} failed for {url}: {e}")
                await asyncio.sleep(5 * (attempt + 1))
        
        await page.close()
        if content:
            return {"html": content, "api_data": api_data_list}
        return None

    async def discover_links(self, source_config, limit=None, max_pages=1):
        source_name = source_config["source_name"]
        url = source_config["url"]
        source_type = source_config["source_type"]

        print(f"    -> Discovering links from {source_name}...")

        # RSS Feed sources — no Playwright needed
        if source_type == "rss_feed":
            rss_links = parse_rss_feed(url, source_name, limit=limit)
            return rss_links

        all_links = []
        seen = set()
        pages_to_try = max_pages if source_type == "curated_job_board" else 1

        for page_num in range(1, pages_to_try + 1):
            page_url = url if page_num == 1 else f"{url.rstrip('/')}/page/{page_num}/"
            content_dict = await self.get_content(page_url)
            if not content_dict or not content_dict.get("html"):
                break
            
            html = content_dict["html"]

            soup = BeautifulSoup(html, "lxml")
            links = []
            
            parser = ParserFactory.get_parser(source_type, url)
            if parser:
                links = parser.discover_links(soup, page_url)
            else:
                print(f"      ! No parser found for {source_type} ({url})")

            new_on_page = 0
            for l in links:
                if l["job_url"] not in seen:
                    seen.add(l["job_url"])
                    l["source_name"] = source_name
                    all_links.append(l)
                    new_on_page += 1

            print(f"      Page {page_num}: +{new_on_page} links (total {len(all_links)})")
            if new_on_page == 0 or (limit and len(all_links) >= limit):
                break

        return all_links[:limit] if limit else all_links


    async def scrape_details(self, job_links, force=False):
        jobs = []
        semaphore = asyncio.Semaphore(5)

        async def _process(i, link):
            url = link["job_url"]
            if not force and self.is_url_scraped_recently(url):
                print(f"      [{i+1}/{len(job_links)}] Skipping (recently scraped): {link.get('job_title')}")
                return None

            print(f"      [{i+1}/{len(job_links)}] Parsing detail: {link.get('job_title', 'Job')}")
            async with semaphore:
                detail = await self.scrape_detail(url, link)
                if detail:
                    self.mark_url_scraped(url)
                    return detail
            return None

        tasks = [_process(i, link) for i, link in enumerate(job_links)]
        results = await asyncio.gather(*tasks)
        jobs = [r for r in results if r]
        return jobs

    async def scrape_detail(self, url, link_data):
        content_dict = await self.get_content(url)
        if not content_dict or not content_dict.get("html"): return None
        
        html = content_dict["html"]
        api_data_list = content_dict.get("api_data", [])
        
        json_data = extract_json_ld(html)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        text_lower = text.lower()
        
        scrape_status = "Success"
        
        # If JSON-LD failed, try to scan the intercepted API data for keywords
        if not json_data and api_data_list:
            api_string = json.dumps(api_data_list).lower()
            if "jobtitle" in api_string or "description" in api_string or "requirements" in api_string:
                scrape_status = "Success (API Interception Fallback)"
                # This is a basic demonstration of API fallback. 
                # A more sophisticated parser would extract exact fields here.

        # Calculation of data confidence
        confidence = 0
        scrape_status = "Success"

        if json_data:
            job_title = json_data.get("job_title")
            company = json_data.get("company")
            location = json_data.get("location")
            date_posted = json_data.get("date_posted")
            deadline = json_data.get("deadline")
            salary = json_data.get("salary")
            description = json_data.get("description")
            requirements = json_data.get("requirements")
            responsibilities = json_data.get("responsibilities")
            scrape_status = "Success (JSON-LD)"
        else:
            job_title = soup.find("h1").get_text(strip=True) if soup.find("h1") else link_data.get("job_title", "Tidak tercantum")
            
            # === SMART COMPANY EXTRACTION ===
            # Step 1: Try to extract from the job title itself (most reliable for curated boards)
            # Patterns: "MT Lowongan @ PT Astra", "Management Trainee – Kawan Lama Group", "MT dari Toyota"
            company = "Tidak tercantum"
            title_text = job_title or link_data.get("job_title", "")
            
            title_company_patterns = [
                r'@\s*(PT\s+\w[\w\s]+?)(?:\s*[-–(]|$)',        # "... @ PT Astra..."
                r'[-–]\s*(PT\s+\w[\w\s]+?)(?:\s*[-–(]|$)',     # "... – PT Toyota..."
                r'\bdi\s+(PT\s+\w[\w\s]+?)(?:\s*[-–(]|$)',      # "... di PT Kalbe..."
                r'\bdari\s+(PT\s+\w[\w\s]+?)(?:\s*[-–(]|$)',    # "... dari PT Unilever..."
                r'[-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Group)(?:\s*[-–(]|$)',  # "– Kawan Lama Group"
                r'[-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s*[-–(]|$)',  # "– Dharma Polimetal"
            ]
            for pattern in title_company_patterns:
                m = re.search(pattern, title_text, re.IGNORECASE)
                if m:
                    company = m.group(1).strip().rstrip('.,')
                    break
            
            # Step 2: Search ONLY within the main content area, not sidebar/footer
            if company == "Tidak tercantum":
                content_area = (
                    soup.find("article") or
                    soup.find("main") or
                    soup.find(class_=re.compile(r'entry-content|post-content|article-content|job-content|content-area', re.I)) or
                    soup.find("div", id=re.compile(r'content|main|article', re.I))
                )
                if content_area:
                    content_text = content_area.get_text(separator=" ", strip=True)
                    # Look for company patterns in content area only (first 2000 chars = above fold)
                    content_snippet = content_text[:2000]
                    for p in [r"PT\s+[A-Z][a-zA-Z\s&]+?(?=\s+(?:adalah|merupakan|membuka|mencari|membutuhkan|Tbk|Indonesia)|[,.]|$)",
                               r"Bank\s+[A-Z][a-zA-Z\s]+?(?=\s+(?:adalah|merupakan|membuka)|[,.]|$)"]:
                        m = re.search(p, content_snippet)
                        if m:
                            candidate = m.group(0).strip().rstrip('.,')
                            # Reject known false positives (sponsors, generic names)
                            false_positives = {"PT Pamapersada", "PT Biro", "PT Karunia", "PT Berca"}
                            if candidate not in false_positives:
                                company = candidate
                                break
            
            location = "Tidak tercantum"
            for city in ["jakarta", "surabaya", "bandung", "tangerang", "bekasi", "bogor", "depok",
                         "semarang", "medan", "makassar", "bali", "denpasar", "yogyakarta", "malang"]:
                if city in text_lower: location = city.capitalize(); break
            date_posted = deadline = salary = responsibilities = "Tidak tercantum"
            description = text[:500] + "..."
            requirements = "Tidak tercantum"
            req_section = soup.find(string=re.compile(r"Kualifikasi|Requirements|Persyaratan|Requirement", re.I))
            if req_section and req_section.find_parent():
                requirements = req_section.find_parent().get_text(strip=True)[:1000]
            scrape_status = "Success (HTML Fallback)"

        # --- LLM FALLBACK ---
        # Jika JSON-LD gagal dan API Interception tidak menemukan apa-apa, gunakan AI
        if not json_data and scrape_status != "Success (API Interception Fallback)":
            llm_data = await parse_with_llm(text)
            if llm_data:
                job_title = llm_data.get("job_title") or job_title
                company = llm_data.get("company") or company
                location = llm_data.get("location") or location
                salary = llm_data.get("salary") or salary
                if llm_data.get("requirements"): requirements = llm_data.get("requirements")
                scrape_status = "Success (LLM AI Fallback)"

        # Confidence Scoring
        if job_title and job_title != "Tidak tercantum": confidence += 20
        if company and company != "Tidak tercantum": confidence += 15
        if location and location != "Tidak tercantum": confidence += 15
        if requirements and requirements != "Tidak tercantum": confidence += 15
        if (description and description != "Tidak tercantum") or (responsibilities and responsibilities != "Tidak tercantum"): confidence += 15
        if (date_posted and date_posted != "Tidak tercantum") or (deadline and deadline != "Tidak tercantum"): confidence += 10
        if url: confidence += 10 # Apply URL always found if we are here

        # Final field assembly
        combined_pos = POSITIVE_KEYWORDS + INDONESIAN_POSITIVE_KEYWORDS
        found_pos = [kw for kw in combined_pos if kw in text_lower]
        found_neg = [kw for kw in NEGATIVE_KEYWORDS if kw in text_lower]

        return {
            "source": link_data.get("source_name", "Unknown"),
            "source_url": link_data.get("source_url", url),
            "job_title": job_title or "Tidak tercantum",
            "company": company or "Tidak tercantum",
            "location": location or "Tidak tercantum",
            "date_posted": date_posted or "Tidak tercantum",
            "deadline": deadline or "Tidak tercantum",
            "salary": salary or "Tidak tercantum",
            "work_arrangement": "Tidak tercantum",
            "industry": "Tidak tercantum",
            "job_url": url,
            "apply_url": url,
            "job_description_summary": (description or text[:500])[:500] + "...",
            "requirements": requirements or "Tidak tercantum",
            "responsibilities": responsibilities or "Tidak tercantum",
            "keywords_found": ", ".join(found_pos),
            "negative_keywords_found": ", ".join(found_neg),
            "last_scraped": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_confidence": confidence,
            "scrape_status": scrape_status
        }

    # Parser methods moved to scraper/parsers/sites/
