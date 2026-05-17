# Job Scraper Rules

## General Principles
- **No Hallucination**: Do not invent missing job data. Use "Tidak tercantum" for unavailable fields.
- **Polite Crawling**: Always check `robots.txt`, respect `Crawl-delay`, and use a custom User-Agent.
- **No Auto-Apply**: This agent only discover and matches jobs. It must never auto-apply.
- **Privacy & Terms**: Do not scrape pages requiring login, captcha, or paywalls.

## Scraping Workflow
1. **Discovery Mode**: Collect URLs from listing/category pages.
2. **Detail Mode**: Visit each URL, prioritizing JSON-LD JobPosting parsing, then falling back to HTML.
3. **Caching**: Maintain `cache/scraped_urls.json` to avoid re-scraping the same URL within 24 hours unless `--force` is used.

## Scoring & Matching
- Always read `candidate_profile.md` for candidate details and target criteria.
- Use a 100-point system: Role fit (20), Experience (20), Skill (20), Industry (10), Leadership (10), Education (10), Location (5), Compensation (5).
- Apply strict penalties for experience >= 3 years, senior roles, or irrelevant domains.

## Data Quality
- Calculate `data_confidence` (0-100) based on field availability.
- Use `reason_codes` to explain scores and penalties.
- Categorize results: Strong Match (85+), Good Match (75+), etc.

## Export
- **jobs_ranked.csv**: All unique discovered jobs sorted by score.
- **apply_today.csv**: High-quality matches (Score >= 75, Confidence >= 60) without severe penalties.
