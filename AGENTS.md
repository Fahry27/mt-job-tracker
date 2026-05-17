# Job Scraper Agent Documentation

This project is a specialized job scraping and matching agent designed for **Fahry Ramadhan**.

## Agent Objectives
1. **Discover**: Scrape high-quality job listings from curated and large-scale Indonesian job boards.
2. **Filter**: Apply strict keyword filtering (Positive/Negative) to ensure relevance.
3. **Match**: Score each job against the `candidate_profile.md` using a weighted point system.
4. **Rank**: Present the best opportunities first for efficient review.

## System Components
- **Config**: Centralized management of sources, keywords, and scoring weights.
- **Scraper**: Playwright-based engine for high-fidelity extraction.
- **Matcher**: Logic engine for calculating scores and generating recommendation insights.
- **Exporter**: CSV formatting for external review.

## Usage Instructions
Run the scraper from the root directory:

**1. Full Cycle (Discovery + Detail):**
```bash
python3 scraper/main.py --mode all --core-only --global-limit 10
```

**2. Discovery Only:**
```bash
python3 scraper/main.py --mode discovery --include-optional
```

**3. Detail Only (using cache):**
```bash
python3 scraper/main.py --mode detail --output output/my_ranked_jobs.csv
```

## Features
- **JSON-LD Parsing**: Automatically extracts structured `JobPosting` data for higher precision.
- **Two-Step Pipeline**: Separates URL discovery from detail extraction to allow for caching and modular execution.
- **Cache Support**: Discovered links are saved to `cache/discovered_jobs.json`.
