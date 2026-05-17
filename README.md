# Job Scraper & Matcher Agent

Professional job scraping and matching system for Management Trainee (MT) and ODP programs in Indonesia.

## Features
- **Polite Crawling**: Respects `robots.txt` and uses custom delays.
- **Two-Step Pipeline**: Separates URL discovery from detail extraction.
- **JSON-LD Parsing**: High-precision data extraction from structured JobPosting schemas.
- **Confidence Scoring**: 0-100 data quality score for each job.
- **Reason Codes**: Explainable matching and penalty logic.
- **Smart Filtering**: Generates `apply_today.csv` for high-potential opportunities.
- **Structured Output**: Organizes runs into `output/YYYY-MM-DD/HHMMSS/` with summary and logs.

## Output Structure
Every time you run the scraper, it creates a unique timestamped folder:
```
output/
├── latest_jobs_ranked.csv       # Link to the most recent full results
├── latest_apply_today.csv      # Link to the most recent top picks
├── latest_run_summary.json      # Summary of the most recent run
└── 2026-05-06/                  # Date folder
    └── 065602/                  # Time folder (Run ID: 20260506_065602)
        ├── jobs_ranked.csv      # Full ranked results for this run
        ├── apply_today.csv      # Top picks for this run
        ├── run_summary.json     # Statistics and metadata
        └── scrape_log.txt       # Detailed execution log
```
```bash
pip install playwright playwright-stealth beautifulsoup4 lxml
playwright install chromium
```

## CLI Usage Examples

### 1. Full Cycle (Core Sources)
Scrape and rank jobs from core sources with a limit of 50 jobs total.
```bash
python3 scraper/main.py --mode all --core-only --limit 50 --output output/jobs_ranked.csv
```

### 2. Broad Discovery (Include Optional)
Discover jobs from larger boards (Indeed, JobStreet, etc.) with a higher limit.
```bash
python3 scraper/main.py --mode all --include-optional --limit 100 --output output/jobs_ranked.csv
```

### 3. Force Re-scrape
Ignore the 24-hour cache and re-scrape all URLs.
```bash
python3 scraper/main.py --core-only --force --output output/jobs_ranked.csv
```

### 4. Discovery Only
Only collect URLs without scraping details.
```bash
python3 scraper/main.py --mode discovery --core-only
```

### 5. Detail Only (Resume from Cache)
Process details for URLs already found in the discovery phase.
```bash
python3 scraper/main.py --mode detail --output output/resumed_jobs.csv
```

## Configuration
- `candidate_profile.md`: Update this file to change matching criteria.
- `config/sources.py`: Add or remove job sources.
- `config/keywords.py`: Update positive/negative keywords.
- `config/scoring.py`: Adjust scoring weights and penalties.
