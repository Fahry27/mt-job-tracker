import argparse
import sys
import os
import json
import shutil
import csv
import glob
import asyncio
import time
from datetime import datetime, date

# Adjust path to import from parent and config directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.sources import CORE_SOURCES, OPTIONAL_DISCOVERY_SOURCES
from config.scoring import JOB_FIELDS
from scraper.parsers.unified_parser import UnifiedScraper
from scraper.parsers.matcher import rank_jobs, deduplicate_jobs
from scraper.parsers.deadline_helper import calculate_deadline_fields
from scraper.exporters.csv_exporter import export_to_csv, export_apply_today, generate_recommendation_summary, export_super_aggressive
from scraper.notifier import notify_high_matches
from scraper.parsers.ai_matcher import analyze_job_with_ai
from scraper.parsers.market_insight import generate_market_insights
from scraper.parsers.web_enricher import enrich_jobs

CACHE_FILE = "cache/discovered_jobs.json"

POWERFUL_AUDIT_FIELDS = JOB_FIELDS + [
    "deadline_parsed", "deadline_status", "days_until_deadline",
    "urgency_level", "deadline_note", "not_apply_today_reason"
]

def parse_args():
    parser = argparse.ArgumentParser(description="Job Scraper & Matcher v4.0 (Unified)")
    parser.add_argument("--mode", choices=["discovery", "detail", "all"], default="all", help="Scraping mode")
    parser.add_argument("--core-only", action="store_true", help="Scrape only CORE_SOURCES")
    parser.add_argument("--include-optional", action="store_true", help="Include OPTIONAL_DISCOVERY_SOURCES")
    parser.add_argument("--force", action="store_true", help="Ignore 24h cache and re-scrape all URLs")
    parser.add_argument("--unified", action="store_true", help="Merge today's results with a new all-in run")
    parser.add_argument("--super-aggressive", action="store_true", help="Export a super aggressive unified CSV without scraping")
    parser.add_argument("--merge-all", action="store_true", help="Merge ALL previous results from output history")
    parser.add_argument("--gpa-rescore", action="store_true", help="GPA-focused rescore using existing data from output/latest")
    parser.add_argument("--powerful", action="store_true", help="POWERFUL_FULL_RUN: scrape + merge history + GPA/deadline audit + full reports")
    parser.add_argument("--use-ai", action="store_true", help="Use Gemini API for semantic matching on top jobs")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of jobs per source")
    parser.add_argument("--global-limit", type=int, default=None, help="Limit total number of jobs in output")
    parser.add_argument("--max-pages-per-source", type=int, default=1, help="Maximum pagination depth per source (default 1)")
    parser.add_argument("--output-dir", type=str, default="output", help="Base output directory")
    parser.add_argument("--flat-output", action="store_true", help="Store files directly in output dir")
    return parser.parse_args()

def create_run_output_dir(base_dir, unified=False, gpa_rescore=False, powerful=False):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")
    run_id = now.strftime("%Y%m%d_%H%M%S")

    if powerful or gpa_rescore or unified:
        pass # Ignore mode prefixes to keep folder names short
    
    run_dir = os.path.join(base_dir, f"{date_str}_{time_str}")
    
    os.makedirs(run_dir, exist_ok=True)
    return run_dir, run_id

def archive_old_root_files(base_dir):
    """Move any CSV/JSON/TXT/MD/XLSX files sitting directly in output/ root to archive_old_outputs/."""
    archive_dir = os.path.join(base_dir, "archive_old_outputs")
    extensions = ("*.csv", "*.json", "*.txt", "*.md", "*.xlsx")
    moved = 0
    
    for ext in extensions:
        for filepath in glob.glob(os.path.join(base_dir, ext)):
            # Only files directly in root, not in subdirectories
            if os.path.isfile(filepath):
                os.makedirs(archive_dir, exist_ok=True)
                dest = os.path.join(archive_dir, os.path.basename(filepath))
                # Handle name collision
                if os.path.exists(dest):
                    base, fext = os.path.splitext(os.path.basename(filepath))
                    dest = os.path.join(archive_dir, f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{fext}")
                shutil.move(filepath, dest)
                moved += 1
    
    return moved

def merge_outputs(base_dir, only_today=True):
    today = datetime.now().strftime("%Y-%m-%d")
    previous_jobs = []
    included_folders = []

    if not os.path.exists(base_dir):
        return [], []

    # Walk through the output directory
    for root, dirs, files in os.walk(base_dir):
        # We are looking for folders containing today's date if only_today is True
        if only_today and today not in root:
            continue

        if "latest" in root or "archive_old" in root:
            continue
            
        for file in ["jobs_ranked.csv", "apply_today.csv"]:
                path = os.path.join(root, file)
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8-sig") as f:
                            reader = csv.DictReader(f)
                            # Map CSV headers back to internal keys
                            mapping = {v: k for k, v in {
                                "rank": "Rank", "match_score": "Score", "match_category": "Match Category",
                                "recommendation": "Recommendation", "job_title": "Job Title",
                                "company": "Company", "location": "Location", "source": "Source",
                                "job_url": "Link", "why_match": "Why Match", "gaps_or_concerns": "Gaps / Concerns",
                                "suggested_cv_tailoring": "Suggested CV Tailoring", "reason_codes": "reason_codes",
                                "data_confidence": "data_confidence", "scrape_status": "scrape_status", "run_id": "run_id",
                                "gpa_required": "gpa_required", "gpa_gap": "gpa_gap",
                                "gpa_status": "gpa_status", "gpa_note": "gpa_note"
                            }.items()}
                            
                            for row in reader:
                                internal_job = {mapping.get(k, k.lower().replace(" ", "_")): v for k, v in row.items()}
                                previous_jobs.append(internal_job)
                            
                            if root not in included_folders:
                                included_folders.append(os.path.relpath(root, base_dir))
                    except Exception as e:
                        print(f"      ! Error reading {path}: {e}")
    
    return previous_jobs, included_folders

def load_latest_jobs(base_dir):
    """Load jobs from output/latest/jobs_ranked.csv for GPA rescoring."""
    latest_csv = os.path.join(base_dir, "latest", "jobs_ranked.csv")
    if not os.path.exists(latest_csv):
        print(f"    ! No latest jobs found at {latest_csv}")
        return []
    
    jobs = []
    try:
        with open(latest_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            mapping = {v: k for k, v in {
                "rank": "Rank", "match_score": "Score", "match_category": "Match Category",
                "recommendation": "Recommendation", "job_title": "Job Title",
                "company": "Company", "location": "Location", "source": "Source",
                "job_url": "Link", "why_match": "Why Match", "gaps_or_concerns": "Gaps / Concerns",
                "suggested_cv_tailoring": "Suggested CV Tailoring", "reason_codes": "reason_codes",
                "data_confidence": "data_confidence", "scrape_status": "scrape_status", "run_id": "run_id",
                "gpa_required": "gpa_required", "gpa_gap": "gpa_gap",
                "gpa_status": "gpa_status", "gpa_note": "gpa_note"
            }.items()}
            
            for row in reader:
                internal_job = {mapping.get(k, k.lower().replace(" ", "_")): v for k, v in row.items()}
                jobs.append(internal_job)
    except Exception as e:
        print(f"    ! Error reading latest CSV: {e}")
    
    return jobs

async def main_async():
    args = parse_args()
    sources = CORE_SOURCES + OPTIONAL_DISCOVERY_SOURCES if args.include_optional else CORE_SOURCES
    start_time = datetime.now()
    
    # Archive old root files first
    archived = archive_old_root_files(args.output_dir)
    if archived > 0:
        print(f"Archived {archived} old root files to output/archive_old_outputs/")
    
    # 1. Prepare Directory
    run_dir, run_id = create_run_output_dir(
        args.output_dir, unified=args.unified,
        gpa_rescore=args.gpa_rescore, powerful=getattr(args, 'powerful', False)
    )
    log_path = os.path.join(run_dir, "logs.txt")
    log_content = []

    def log(msg):
        print(msg)
        log_content.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

    log("="*60)
    if getattr(args, 'powerful', False):
        log(f"  MT JOB SCRAPER & MATCHER v4.0 - Mode: POWERFUL_FULL_RUN")
    else:
        log(f"  MT JOB SCRAPER & MATCHER v4.0 - Mode: {'GPA_RESCORE' if args.gpa_rescore else args.mode.upper()}")
    log(f"  Unified Mode: {args.unified}")
    log(f"  Run ID: {run_id}")
    log(f"  Output Folder: {run_dir}")
    log("="*60 + "\n")

    # --- GPA Rescore Mode ---
    if args.gpa_rescore:
        log("GPA RESCORE MODE: Loading existing data from output/latest...")
        existing_jobs = load_latest_jobs(args.output_dir)
        if not existing_jobs:
            log("No jobs found to rescore. Exiting.")
            return
        
        log(f"Loaded {len(existing_jobs)} jobs for GPA rescoring.")
        
        # Standardize numeric scores
        for job in existing_jobs:
            for k in ["match_score", "data_confidence"]:
                if k in job and isinstance(job[k], str):
                    try: job[k] = float(job[k])
                    except: job[k] = 0
        
        # Re-score with GPA-aware logic
        log("Re-scoring all jobs with GPA-aware logic...")
        ranked_jobs = rank_jobs(existing_jobs)
        
        if getattr(args, 'use_ai', False):
            log("Running AI Semantic Matching on top jobs (Score >= 60)...")
            # Only process up to 20 potential jobs to save API quota
            candidates_for_ai = [j for j in ranked_jobs if j.get("match_score", 0) >= 60][:20]
            for i, job in enumerate(candidates_for_ai):
                print(f"    [AI] Analyzing {i+1}/{len(candidates_for_ai)}: {job.get('company')} - {job.get('job_title')}")
                analyze_job_with_ai(job)
                # Small delay to respect free API rate limits (15 RPM)
                time.sleep(2)
            
            # Re-sort after AI adjusts the scores
            ranked_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            
        # Sort
        def sort_key(j):
            score = j.get("match_score", 0)
            confidence = j.get("data_confidence", 0)
            date = j.get("date_posted", "Tidak tercantum")
            company = j.get("company", "Tidak tercantum")
            return (-score, -confidence, date == "Tidak tercantum", date, company)
        ranked_jobs.sort(key=sort_key)
        
        # GPA counts
        gpa_counts = _count_gpa_statuses(ranked_jobs)
        
        # Export
        jobs_ranked_path = os.path.join(run_dir, "jobs_ranked.csv")
        apply_today_path = os.path.join(run_dir, "apply_today.csv")
        summary_path = os.path.join(run_dir, "run_summary.json")
        
        log(f"Exporting GPA-rescored results to {run_dir}...")
        export_to_csv(ranked_jobs, jobs_ranked_path, JOB_FIELDS)
        export_apply_today(ranked_jobs, apply_today_path, JOB_FIELDS)
        
        total_apply_today = len([j for j in ranked_jobs if j.get("match_score", 0) >= 75 and j.get("data_confidence", 0) >= 60 and j.get("recommendation") in ["Apply", "Apply / Maybe"] and j.get("gpa_status") != "High GPA Gap"])
        
        summary = {
            "run_id": run_id,
            "run_type": "gpa_rescore",
            "started_at": start_time.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "included_previous_today_folders": [],
            "previous_rows_loaded": len(existing_jobs),
            "new_rows_loaded": 0,
            "total_rows_before_dedup": len(existing_jobs),
            "duplicates_removed": 0,
            "total_links_discovered": 0,
            "total_detail_pages_attempted": 0,
            "total_successful_detail_pages": 0,
            "total_exported": len(ranked_jobs),
            "total_apply_today": total_apply_today,
            "strong_match_count": len([j for j in ranked_jobs if j.get("match_score", 0) >= 85]),
            "good_match_count": len([j for j in ranked_jobs if 75 <= j.get("match_score", 0) < 85]),
            "possible_match_count": len([j for j in ranked_jobs if 60 <= j.get("match_score", 0) < 75]),
            "weak_match_count": len([j for j in ranked_jobs if 45 <= j.get("match_score", 0) < 60]),
            "not_recommended_count": len([j for j in ranked_jobs if j.get("match_score", 0) < 45]),
            "output_folder": run_dir,
            "latest_folder": os.path.join(args.output_dir, "latest"),
            "gpa_meets_count": gpa_counts["Meets GPA"],
            "gpa_slight_gap_count": gpa_counts["Slight GPA Gap"],
            "gpa_moderate_gap_count": gpa_counts["Moderate GPA Gap"],
            "gpa_high_gap_count": gpa_counts["High GPA Gap"],
            "gpa_not_listed_count": gpa_counts["No GPA Listed"],
            "gpa_qualitative_count": gpa_counts["Qualitative GPA Requirement"],
        }
        
        with open(summary_path, "w") as f: json.dump(summary, f, indent=2)
        with open(log_path, "w") as f: f.write("\n".join(log_content))
        generate_recommendation_summary(ranked_jobs, run_dir, summary)
        
        # Update latest
        _update_latest(args.output_dir, run_dir)
        
        # Final print
        _print_gpa_final(run_dir, len(ranked_jobs), total_apply_today, gpa_counts)
        return

    previous_jobs = []
    included_folders = []
    if args.unified or args.merge_all or args.super_aggressive:
        log("Scanning for previous results to merge...")
        previous_jobs, included_folders = merge_outputs(args.output_dir, only_today=not (args.merge_all or args.super_aggressive))
        log(f"Loaded {len(previous_jobs)} rows from {len(included_folders)} previous folders.")



    # 2. Run Scraping
    scraper = UnifiedScraper(headless=False)
    new_jobs = []
    
    if args.mode in ["discovery", "all"]:
        await scraper.start()
        try:
            discovered_links = []
            for source in sources:
                log(f">>> Discovering: {source['source_name']}")
                links = await scraper.discover_links(
                    source,
                    limit=args.limit,
                    max_pages=args.max_pages_per_source or 1
                )
                discovered_links.extend(links)
                if args.global_limit and len(discovered_links) >= args.global_limit: break
            
            log(f"\n[DETAIL MODE] Scrapping details for {len(discovered_links)} new links...")
            new_jobs = await scraper.scrape_details(discovered_links, force=args.force)
        finally:
            await scraper.stop()

    # 3. Merge & Deduplicate
    all_jobs = previous_jobs + new_jobs
    initial_count = len(all_jobs)
    
    # Use sophisticated deduplication as requested
    def get_dedup_key(j):
        url = j.get("job_url") or j.get("Link")
        if url and "Tidak tercantum" not in str(url): return str(url).lower().strip()
        apply_url = j.get("apply_url")
        if apply_url and "Tidak tercantum" not in str(apply_url): return str(apply_url).lower().strip()
        return f"{str(j.get('company')).lower()}|{str(j.get('job_title')).lower()}|{str(j.get('location')).lower()}".strip()

    seen_dict = {}
    for job in all_jobs:
        key = get_dedup_key(job)
        if key not in seen_dict:
            seen_dict[key] = job
        elif args.super_aggressive:
            # Merge logic for super aggressive
            existing = seen_dict[key]
            
            # 1. Keep longest description
            desc1 = str(existing.get("job_description_summary", existing.get("description", "")))
            desc2 = str(job.get("job_description_summary", job.get("description", "")))
            if len(desc2) > len(desc1):
                existing["job_description_summary"] = job.get("job_description_summary", "")
                existing["description"] = job.get("description", "")
                
            # 2. Keep highest score
            score1 = float(existing.get("match_score", existing.get("Score", 0)) or 0)
            score2 = float(job.get("match_score", job.get("Score", 0)) or 0)
            if score2 > score1:
                existing["match_score"] = score2
                existing["Score"] = score2
                
            # 3. Set data_origin
            existing["data_origin"] = "merged_duplicate"
            existing["duplicate_group_key"] = key
            
            seen_dict[key] = existing

    unique_jobs = list(seen_dict.values())
    
    duplicates_removed = initial_count - len(unique_jobs)
    log(f"Merged Total: {initial_count}")
    log(f"Duplicates Removed: {duplicates_removed}")
    log(f"Unique Jobs to Rank: {len(unique_jobs)}")

    # 4. Re-score & Rank
    log("Re-scoring all combined jobs...")
    for job in unique_jobs:
        # Standardize numeric scores from previous CSVs
        for k in ["match_score", "data_confidence"]:
            if k in job and isinstance(job[k], str):
                try: job[k] = float(job[k])
                except: job[k] = 0
    
    ranked_jobs = rank_jobs(unique_jobs)
    
    if getattr(args, 'use_ai', False):
        log("Running AI Semantic Matching on top jobs (Score >= 60)...")
        # Only process up to 20 potential jobs to save API quota
        candidates_for_ai = [j for j in ranked_jobs if j.get("match_score", 0) >= 60][:20]
        for i, job in enumerate(candidates_for_ai):
            print(f"    [AI] Analyzing {i+1}/{len(candidates_for_ai)}: {job.get('company')} - {job.get('job_title')}")
            analyze_job_with_ai(job)
            time.sleep(2)
            
        # Re-sort after AI score adjustments
        ranked_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    # Sort with ties-breaking as requested: Score (desc) > Confidence (desc) > Date (desc) > Company (asc)
    def sort_key(j):
        score = j.get("match_score", 0)
        confidence = j.get("data_confidence", 0)
        date = j.get("date_posted", "Tidak tercantum")
        company = j.get("company", "Tidak tercantum")
        return (-score, -confidence, date == "Tidak tercantum", date, company)
    
    ranked_jobs.sort(key=sort_key)

    # 5. Export
    if args.super_aggressive:
        date_str = datetime.now().strftime("%Y-%m-%d")
        sa_filename = f"fahry_super_aggressive_unified_apply_export_{date_str}.csv"
        jobs_ranked_path = os.path.join(run_dir, sa_filename)
        
        log(f"Exporting Super Aggressive Unified CSV to {jobs_ranked_path}...")
        export_super_aggressive(ranked_jobs, jobs_ranked_path)
        
        # Super Aggressive Summary Console Print
        p1 = len([j for j in ranked_jobs if j.get("match_score", 0) >= 75])
        p2 = len([j for j in ranked_jobs if 60 <= j.get("match_score", 0) < 75])
        p3 = len([j for j in ranked_jobs if 45 <= j.get("match_score", 0) < 60])
        p4 = len([j for j in ranked_jobs if 30 <= j.get("match_score", 0) < 45])
        p5 = len([j for j in ranked_jobs if j.get("match_score", 0) < 30])
        
        print("\n" + "="*50)
        print(" SUPER AGGRESSIVE EXPORT SUMMARY ")
        print("="*50)
        print(f"Total Combined before Dedup: {initial_count}")
        print(f"Duplicates Removed: {duplicates_removed}")
        print(f"Final Unique Jobs: {len(unique_jobs)}\n")
        print(f"Priority 1 (Apply Now)     : {p1}")
        print(f"Priority 2 (Apply Today)   : {p2}")
        print(f"Priority 3 (Apply If Fast) : {p3}")
        print(f"Priority 4 (Review Quickly): {p4}")
        print(f"Priority 5 (Last Option)   : {p5}")
        print("="*50 + "\n")
        
        # Copy to latest
        _update_latest(args.output_dir, run_dir)
        return
        
    jobs_ranked_path = os.path.join(run_dir, "jobs_ranked.csv")
    apply_today_path = os.path.join(run_dir, "apply_today.csv")
    summary_path = os.path.join(run_dir, "run_summary.json")
    report_path = os.path.join(run_dir, "recommendation_summary.md")

    is_powerful = getattr(args, 'powerful', False)

    # --- Deadline audit for powerful run ---
    gpa_changed = dl_changed = 0
    SEVERE_CODES = ["EXPERIENCE_TOO_HIGH","COMMISSION_ONLY","UNPAID_INTERNSHIP","UNCLEAR_COMPANY","NOT_RELEVANT","DEADLINE_EXPIRED","GPA_RISK_HIGH"]
    if is_powerful:
        log("Running deadline audit on all jobs...")
        today = date.today()
        for job in ranked_jobs:
            dl = calculate_deadline_fields(job, today)
            old_score = job.get("match_score", 0)
            if dl["deadline_penalty"] != 0:
                new_score = max(0, min(100, old_score + dl["deadline_penalty"]))
                job["match_score"] = new_score
                dl_changed += 1
                # Update category/rec
                s = new_score
                if s >= 85: job["match_category"], job["recommendation"] = "Strong Match", "Apply"
                elif s >= 75: job["match_category"], job["recommendation"] = "Good Match", "Apply / Maybe"
                elif s >= 60: job["match_category"], job["recommendation"] = "Possible Match", "Maybe"
                elif s >= 45: job["match_category"], job["recommendation"] = "Weak Match", "Low Priority"
                else: job["match_category"], job["recommendation"] = "Not Recommended", "Skip"
            # Merge new reason codes
            existing_codes = [c.strip() for c in str(job.get("reason_codes","")).split(",") if c.strip() and not c.strip().startswith("DEADLINE_")]
            job["reason_codes"] = ", ".join(existing_codes + dl["deadline_reason_codes"])
            job.update({
                "deadline_parsed": dl["deadline_parsed"],
                "deadline_status": dl["deadline_status"],
                "days_until_deadline": dl["days_until_deadline"],
                "urgency_level": dl["urgency_level"],
                "deadline_note": dl["deadline_note"],
            })
            if job.get("gpa_penalty", 0) != 0:
                gpa_changed += 1

        # Re-sort with deadline priority
        dl_order = {"Open": 0, "Unknown": 1, "Expired": 2}
        urg_order = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3, "Expired": 4}
        ranked_jobs.sort(key=lambda j: (
            -j.get("match_score", 0), -j.get("data_confidence", 0),
            dl_order.get(j.get("deadline_status","Unknown"), 1),
            urg_order.get(j.get("urgency_level","Unknown"), 3),
            j.get("company",""), j.get("job_title","")
        ))

        # not_apply_today_reason
        def _not_apply_reason(job):
            s = job.get("match_score", 0)
            conf = float(job.get("data_confidence", 0) or 0)
            rec = job.get("recommendation", "")
            codes = job.get("reason_codes", "")
            gs = job.get("gpa_status", "")
            ds = job.get("deadline_status", "Unknown")
            url = job.get("job_url", "") or job.get("apply_url", "")
            if ds == "Expired": return "Expired deadline"
            if s < 75: return "Score below 75"
            if conf < 60: return "Data confidence below 60"
            if rec not in ("Apply", "Apply / Maybe"): return "Recommendation not Apply"
            for sv in SEVERE_CODES:
                if sv in codes:
                    if sv == "GPA_RISK_HIGH": return "High GPA gap"
                    if sv == "DEADLINE_EXPIRED": return "Expired deadline"
                    return sv.replace("_"," ").title()
            if not url or url == "Tidak tercantum": return "Missing apply URL"
            if gs == "High GPA Gap": return "High GPA gap"
            if gs == "Moderate GPA Gap" and s < 90: return "Moderate GPA gap and score below 90"
            if gs == "Slight GPA Gap" and s < 80: return "Slight GPA gap and score below 80"
            return None

        for job in ranked_jobs:
            job["not_apply_today_reason"] = _not_apply_reason(job)

    log(f"Exporting results to {run_dir}...")
    out_fields = POWERFUL_AUDIT_FIELDS if is_powerful else JOB_FIELDS
    export_to_csv(ranked_jobs, jobs_ranked_path, out_fields)

    if is_powerful:
        at_jobs = [j for j in ranked_jobs if j.get("not_apply_today_reason") is None]
        export_to_csv(at_jobs, apply_today_path, out_fields)
    else:
        export_apply_today(ranked_jobs, apply_today_path, JOB_FIELDS)

    
    # Statistics for summary
    total_links_discovered = len(discovered_links) if 'discovered_links' in locals() else len(new_jobs)
    total_detail_pages_attempted = total_links_discovered
    total_successful_detail_pages = len(new_jobs)
    total_apply_today = len(at_jobs) if is_powerful else len([j for j in ranked_jobs if j.get("match_score", 0) >= 75 and j.get("data_confidence", 0) >= 60 and j.get("recommendation") in ["Apply", "Apply / Maybe"] and j.get("gpa_status") != "High GPA Gap"])

    gpa_counts = _count_gpa_statuses(ranked_jobs)

    dl_dist = {}
    urg_dist = {}
    if is_powerful:
        for j in ranked_jobs:
            ds = j.get("deadline_status", "Unknown")
            dl_dist[ds] = dl_dist.get(ds, 0) + 1
            ul = j.get("urgency_level", "Unknown")
            urg_dist[ul] = urg_dist.get(ul, 0) + 1

    expired_removed = sum(1 for j in ranked_jobs if is_powerful and j.get("deadline_status") == "Expired" and j.get("not_apply_today_reason") == "Expired deadline")

    run_type = "POWERFUL_FULL_RUN" if is_powerful else ("super_aggressive" if args.super_aggressive else ("unified_all_in_with_previous_today_data" if args.unified else ("merge_all" if args.merge_all else "normal")))

    summary = {
        "run_id": run_id,
        "run_type": run_type,
        "started_at": start_time.isoformat(),
        "finished_at": datetime.now().isoformat(),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
        "included_previous_today_folders": included_folders,
        "previous_rows_loaded": len(previous_jobs),
        "new_rows_loaded": len(new_jobs),
        "total_rows_before_dedup": initial_count,
        "duplicates_removed": duplicates_removed,
        "total_links_discovered": total_links_discovered,
        "total_detail_pages_attempted": total_detail_pages_attempted,
        "total_successful_detail_pages": total_successful_detail_pages,
        "total_detail_pages_failed": total_detail_pages_attempted - total_successful_detail_pages,
        "historical_rows_loaded": len(previous_jobs),
        "total_exported": len(ranked_jobs),
        "total_apply_today": total_apply_today,
        "strong_match_count": len([j for j in ranked_jobs if j.get("match_score", 0) >= 85]),
        "good_match_count": len([j for j in ranked_jobs if 75 <= j.get("match_score", 0) < 85]),
        "possible_match_count": len([j for j in ranked_jobs if 60 <= j.get("match_score", 0) < 75]),
        "weak_match_count": len([j for j in ranked_jobs if 45 <= j.get("match_score", 0) < 60]),
        "not_recommended_count": len([j for j in ranked_jobs if j.get("match_score", 0) < 45]),
        "output_folder": run_dir,
        "latest_folder": os.path.join(args.output_dir, "latest"),
        "gpa_priority_match_count": gpa_counts.get("Priority GPA Match", 0),
        "gpa_meets_count": gpa_counts.get("Meets GPA", 0),
        "gpa_slight_gap_count": gpa_counts.get("Slight GPA Gap", 0),
        "gpa_moderate_gap_count": gpa_counts.get("Moderate GPA Gap", 0),
        "gpa_high_gap_count": gpa_counts.get("High GPA Gap", 0),
        "gpa_not_listed_count": gpa_counts.get("No GPA Listed", 0),
        "gpa_qualitative_count": gpa_counts.get("Qualitative GPA Requirement", 0),
        "deadline_open_count": dl_dist.get("Open", 0),
        "deadline_expired_count": dl_dist.get("Expired", 0),
        "deadline_unknown_count": dl_dist.get("Unknown", 0),
        "deadline_urgent_high_count": urg_dist.get("High", 0),
        "deadline_urgent_medium_count": urg_dist.get("Medium", 0),
        "expired_removed_from_apply_today_count": expired_removed,
        "scores_changed_by_gpa_count": gpa_changed,
        "scores_changed_by_deadline_count": dl_changed,
    }

    with open(summary_path, "w") as f: json.dump(summary, f, indent=2)
    with open(log_path, "w") as f: f.write("\n".join(log_content))

    if is_powerful:
        _write_powerful_audit_report(ranked_jobs, run_dir, summary, total_links_discovered, total_detail_pages_attempted, total_successful_detail_pages, gpa_counts, dl_dist, urg_dist, expired_removed)
        _write_powerful_rec_summary(ranked_jobs, at_jobs, run_dir, summary, gpa_counts, dl_dist, urg_dist)
    else:
        generate_recommendation_summary(ranked_jobs, run_dir, summary)

    # Enrich low-confidence jobs with AI metadata
    if getattr(args, 'use_ai', False):
        ranked_jobs = enrich_jobs(ranked_jobs)

    # Generate AI Market Insights if requested
    if getattr(args, 'use_ai', False):
        generate_market_insights(ranked_jobs, run_dir)

    # 6. Update Latest
    _update_latest(args.output_dir, run_dir)

    # Final Print
    if is_powerful:
        gpa_ok = gpa_counts.get("Priority GPA Match",0) + gpa_counts.get("Meets GPA",0) + gpa_counts.get("No GPA Listed",0)
        gpa_above = gpa_counts.get("Slight GPA Gap",0) + gpa_counts.get("Moderate GPA Gap",0) + gpa_counts.get("High GPA Gap",0)
        print("\nPOWERFUL FULL RUN COMPLETE\n")
        print(f"Run folder:\n{os.path.abspath(run_dir)}\n")
        print(f"Latest folder:\noutput/latest\n")
        print(f"Total links discovered:\n{total_links_discovered}\n")
        print(f"Successful detail pages:\n{total_successful_detail_pages}\n")
        print(f"Historical rows loaded:\n{len(previous_jobs)}\n")
        print(f"Duplicates removed:\n{duplicates_removed}\n")
        print(f"Total exported:\n{len(ranked_jobs)}\n")
        print(f"Apply today:\n{total_apply_today}\n")
        print(f"GPA <= 3.29:\n{gpa_ok}\n")
        print(f"GPA > 3.29:\n{gpa_above}\n")
        print(f"Expired jobs:\n{dl_dist.get('Expired',0)}\n")
        print("Open:")
        print("output/latest/audit_report.md")
        print("output/latest/recommendation_summary.md")
        print("output/latest/jobs_ranked.csv")
        print("output/latest/apply_today.csv")
    else:
        _print_gpa_final(run_dir, len(ranked_jobs), total_apply_today, gpa_counts,
                         total_links_discovered, total_detail_pages_attempted,
                         total_successful_detail_pages, duplicates_removed)

    # Kirim Notifikasi Telegram
    log("Checking for Telegram notifications...")
    notify_high_matches(ranked_jobs, run_id)



def _count_gpa_statuses(ranked_jobs):
    """Count GPA status distribution across ranked jobs."""
    counts = {
        "Priority GPA Match": 0,
        "Meets GPA": 0,
        "Slight GPA Gap": 0,
        "Moderate GPA Gap": 0,
        "High GPA Gap": 0,
        "No GPA Listed": 0,
        "Qualitative GPA Requirement": 0,
    }
    for job in ranked_jobs:
        status = job.get("gpa_status", "No GPA Listed")
        if status in counts:
            counts[status] += 1
        else:
            counts["No GPA Listed"] += 1
    return counts


def _write_powerful_audit_report(ranked_jobs, run_dir, summary, links, attempted, succeeded, gpa_counts, dl_dist, urg_dist, expired_removed):
    path = os.path.join(run_dir, "audit_report.md")
    reasons = {}
    for j in ranked_jobs:
        r = j.get("not_apply_today_reason")
        if r:
            reasons[r] = reasons.get(r, 0) + 1
    gpa_ok = gpa_counts.get("Priority GPA Match",0) + gpa_counts.get("Meets GPA",0) + gpa_counts.get("No GPA Listed",0)
    gpa_above = gpa_counts.get("Slight GPA Gap",0) + gpa_counts.get("Moderate GPA Gap",0) + gpa_counts.get("High GPA Gap",0)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Audit Report — Powerful Full Run\n\n")
        f.write(f"- Total links discovered: {links}\n")
        f.write(f"- Detail pages attempted: {attempted}\n")
        f.write(f"- Detail pages succeeded: {succeeded}\n")
        f.write(f"- Detail pages failed: {attempted - succeeded}\n")
        f.write(f"- Historical rows loaded: {summary.get('previous_rows_loaded', 0)}\n")
        f.write(f"- New rows scraped: {summary.get('new_rows_loaded', 0)}\n")
        f.write(f"- Total before dedup: {summary.get('total_rows_before_dedup', 0)}\n")
        f.write(f"- Duplicates removed: {summary.get('duplicates_removed', 0)}\n")
        f.write(f"- Total exported: {summary.get('total_exported', 0)}\n")
        f.write(f"- Total apply today: {summary.get('total_apply_today', 0)}\n")
        f.write(f"- Scores changed by GPA: {summary.get('scores_changed_by_gpa_count', 0)}\n")
        f.write(f"- Scores changed by deadline: {summary.get('scores_changed_by_deadline_count', 0)}\n")
        f.write(f"- Expired jobs found: {dl_dist.get('Expired', 0)}\n")
        f.write(f"- Expired removed from apply_today: {expired_removed}\n")
        f.write(f"- Jobs with GPA <= 3.29: {gpa_ok}\n")
        f.write(f"- Jobs with GPA > 3.29: {gpa_above}\n\n")
        f.write("## Top Reasons Not in Apply Today\n")
        for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
            f.write(f"- {r}: {c}\n")
        f.write("\n## Source Compliance\n")
        f.write("- robots.txt: respected (blocked sources skipped)\n")
        f.write("- Anti-bot: no bypass attempted\n")
        f.write("- Auto-apply: not performed\n")


def _write_powerful_rec_summary(ranked_jobs, at_jobs, run_dir, summary, gpa_counts, dl_dist, urg_dist):
    path = os.path.join(run_dir, "recommendation_summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Powerful Full Job Scraper Summary\n\n")
        f.write("## Run Info\n")
        f.write(f"- Run ID: {summary.get('run_id')}\n")
        f.write(f"- Started: {summary.get('started_at')}\n")
        f.write(f"- Finished: {summary.get('finished_at')}\n")
        f.write(f"- Total links discovered: {summary.get('total_links_discovered')}\n")
        f.write(f"- Detail pages success: {summary.get('total_successful_detail_pages')}\n")
        f.write(f"- Historical rows loaded: {summary.get('previous_rows_loaded')}\n")
        f.write(f"- Duplicates removed: {summary.get('duplicates_removed')}\n")
        f.write(f"- Total exported: {summary.get('total_exported')}\n")
        f.write(f"- Total apply today: {len(at_jobs)}\n\n")
        f.write("## Top Apply Today\n")
        f.write("| # | Score | Title | Company | GPA | Deadline | Link |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, j in enumerate(at_jobs[:15], 1):
            f.write(f"| {i} | {j.get('match_score')} | {j.get('job_title','')} | {j.get('company','')} | {j.get('gpa_status','')} | {j.get('deadline_status','')} | [Link]({j.get('job_url','')}) |\n")
        f.write("\n## Strong Matches\n")
        for j in [x for x in ranked_jobs if x.get("match_score",0) >= 85]:
            f.write(f"- **{j.get('job_title')}** @ {j.get('company')} ({j.get('match_score')} pts)\n")
        f.write("\n## Good Matches\n")
        for j in [x for x in ranked_jobs if 75 <= x.get("match_score",0) < 85]:
            f.write(f"- **{j.get('job_title')}** @ {j.get('company')} ({j.get('match_score')} pts)\n")
        f.write("\n## GPA Priority Review\n")
        for k in ["Priority GPA Match","Meets GPA","Slight GPA Gap","Moderate GPA Gap","High GPA Gap","No GPA Listed","Qualitative GPA Requirement"]:
            f.write(f"- {k}: {gpa_counts.get(k,0)}\n")
        f.write("\n## Best GPA-Fit Jobs\n")
        for j in ranked_jobs:
            if j.get("gpa_status") in ("Priority GPA Match","Meets GPA"):
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — req {j.get('gpa_required')} (Score: {j.get('match_score')})\n")
        f.write("\n## GPA Gap Jobs\n")
        for j in ranked_jobs:
            if "GPA Gap" in j.get("gpa_status",""):
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — {j.get('gpa_status')}, req {j.get('gpa_required')} (Score: {j.get('match_score')})\n")
        f.write("\n## Deadline Review\n")
        for k in ["Open","Expired","Unknown"]:
            f.write(f"- {k}: {dl_dist.get(k,0)}\n")
        f.write(f"- Urgent High: {urg_dist.get('High',0)}\n")
        f.write(f"- Urgent Medium: {urg_dist.get('Medium',0)}\n")
        f.write("\n## Expired Jobs Removed from Apply Today\n")
        for j in ranked_jobs:
            if j.get("deadline_status") == "Expired":
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — {j.get('deadline_note')}\n")
        f.write("\n## Review Manually\n")
        for j in ranked_jobs:
            gs = j.get("gpa_status","")
            ds = j.get("deadline_status","")
            conf = float(j.get("data_confidence",0) or 0)
            if ds == "Unknown" or gs in ("No GPA Listed","Qualitative GPA Requirement") or conf < 60:
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} (GPA: {gs}, DL: {ds}, Conf: {conf}%)\n")


def _update_latest(output_dir, run_dir):
    """Copy run output files to output/latest/."""
    latest_dir = os.path.join(output_dir, "latest")
    os.makedirs(latest_dir, exist_ok=True)
    for fname in ["jobs_ranked.csv", "apply_today.csv", "run_summary.json", "logs.txt",
                  "recommendation_summary.md", "audit_report.md", "market_insights.json"]:
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(latest_dir, fname))
    for fname in os.listdir(run_dir):
        if "super_aggressive" in fname:
            shutil.copy2(os.path.join(run_dir, fname), os.path.join(latest_dir, fname))


def _print_gpa_final(run_dir, total_exported, total_apply_today, gpa_counts,
                      total_links_discovered=0, total_detail_pages_attempted=0,
                      total_successful_detail_pages=0, duplicates_removed=0):
    """Print final summary with GPA stats."""
    print("\nGPA-AWARE SCORING + FOLDERING UPDATE COMPLETE\n")
    print(f"Run folder:\n{os.path.abspath(run_dir)}\n")
    print(f"Latest folder:\noutput/latest\n")
    if total_links_discovered:
        print(f"Total links discovered:\n{total_links_discovered}\n")
        print(f"Total detail pages attempted:\n{total_detail_pages_attempted}\n")
        print(f"Total successful detail pages:\n{total_successful_detail_pages}\n")
        print(f"Duplicates removed:\n{duplicates_removed}\n")
    print(f"Total exported:\n{total_exported}\n")
    print(f"Total apply today:\n{total_apply_today}\n")
    print(f"GPA meets:\n{gpa_counts['Meets GPA']}\n")
    print(f"Slight GPA gap:\n{gpa_counts['Slight GPA Gap']}\n")
    print(f"Moderate GPA gap:\n{gpa_counts['Moderate GPA Gap']}\n")
    print(f"High GPA gap:\n{gpa_counts['High GPA Gap']}\n")
    print(f"No GPA listed:\n{gpa_counts['No GPA Listed']}\n")
    print(f"Qualitative GPA:\n{gpa_counts['Qualitative GPA Requirement']}\n")
    print("Open:")
    print("output/latest/recommendation_summary.md")
    print("output/latest/jobs_ranked.csv")
    print("output/latest/apply_today.csv")

if __name__ == "__main__":
    asyncio.run(main_async())
