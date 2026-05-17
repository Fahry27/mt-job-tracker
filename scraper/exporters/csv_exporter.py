import csv
import os

def export_to_csv(ranked_jobs, filepath, field_names):
    """
    Export ranked jobs to a CSV file.
    Maps internal dictionary keys to the requested column headers.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    mapping = {
        "rank": "Rank",
        "match_score": "Score",
        "match_category": "Match Category",
        "recommendation": "Recommendation",
        "job_title": "Job Title",
        "company": "Company",
        "location": "Location",
        "source": "Source",
        "job_url": "Link",
        "why_match": "Why Match",
        "gaps_or_concerns": "Gaps / Concerns",
        "suggested_cv_tailoring": "Suggested CV Tailoring",
        "reason_codes": "reason_codes",
        "data_confidence": "data_confidence",
        "scrape_status": "scrape_status",
        "run_id": "run_id",
        "gpa_required": "gpa_required",
        "gpa_gap": "gpa_gap",
        "gpa_status": "gpa_status",
        "gpa_note": "gpa_note",
    }

    try:
        with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=field_names, extrasaction="ignore")
            writer.writeheader()
            for rank, job in enumerate(ranked_jobs, 1):
                row = {mapping[k] if k in mapping else k: job.get(k, "Tidak tercantum") for k in mapping.keys()}
                row["Rank"] = rank
                # Ensure all field_names are present
                for k in field_names:
                    if k not in row:
                        internal_key = [ik for ik, dk in mapping.items() if dk == k]
                        if internal_key:
                            row[k] = job.get(internal_key[0], "Tidak tercantum")
                        else:
                            row[k] = job.get(k.lower().replace(" ", "_"), "Tidak tercantum")
                writer.writerow(row)
        return True
    except Exception as e:
        print(f"Error exporting CSV {filepath}: {e}")
        return False

def export_apply_today(ranked_jobs, filepath, field_names):
    """
    Export 'Apply Today' filtered results with GPA-aware filtering.
    
    GPA filtering rules:
    - Meets GPA: allowed
    - No GPA Listed: allowed
    - Qualitative GPA Requirement: allowed
    - Slight GPA Gap: allowed if score >= 75
    - Moderate GPA Gap: allowed only if score >= 75 and no major non-GPA risk
    - High GPA Gap: EXCLUDED from apply_today
    """
    severe_penalties = ["EXPERIENCE_TOO_HIGH", "COMMISSION_ONLY", "UNPAID_INTERNSHIP", "UNCLEAR_COMPANY", "NOT_RELEVANT"]
    
    filtered_jobs = []
    for job in ranked_jobs:
        score = job.get("match_score", 0)
        confidence = job.get("data_confidence", 0)
        rec = job.get("recommendation", "")
        codes = job.get("reason_codes", "")
        gpa_status = job.get("gpa_status", "No GPA Listed")
        
        has_severe = any(p in codes for p in severe_penalties)
        
        # Base criteria: score >= 75, confidence >= 60, good recommendation, no severe penalties
        if score < 75 or confidence < 60 or rec not in ["Apply", "Apply / Maybe"] or has_severe:
            continue
        
        # GPA-specific filtering
        if gpa_status == "High GPA Gap":
            # Excluded from apply_today entirely
            continue
        elif gpa_status == "Moderate GPA Gap":
            # Allowed only if score >= 75 (already checked) and no major risk
            # More strict: also need no MAJOR_RISK
            if "MAJOR_RISK" in codes:
                continue
        # Slight GPA Gap, Meets GPA, No GPA Listed, Qualitative: all allowed if base criteria pass
        
        filtered_jobs.append(job)
            
    return export_to_csv(filtered_jobs, filepath, field_names)

def generate_recommendation_summary(ranked_jobs, run_dir, summary):
    """
    Generate recommendation_summary.md report with GPA Risk Review section.
    """
    report_path = os.path.join(run_dir, "recommendation_summary.md")
    
    apply_today = [j for j in ranked_jobs if j.get("match_score", 0) >= 75 and j.get("data_confidence", 0) >= 60 and j.get("recommendation") in ["Apply", "Apply / Maybe"]]
    
    # GPA status counts
    gpa_counts = {
        "Meets GPA": 0,
        "Slight GPA Gap": 0,
        "Moderate GPA Gap": 0,
        "High GPA Gap": 0,
        "No GPA Listed": 0,
        "Qualitative GPA Requirement": 0,
    }
    gpa_slight_jobs = []
    gpa_moderate_high_jobs = []
    
    for job in ranked_jobs:
        status = job.get("gpa_status", "No GPA Listed")
        if status in gpa_counts:
            gpa_counts[status] += 1
        else:
            gpa_counts["No GPA Listed"] += 1
        
        if status == "Slight GPA Gap":
            gpa_slight_jobs.append(job)
        elif status in ["Moderate GPA Gap", "High GPA Gap"]:
            gpa_moderate_high_jobs.append(job)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Unified Job Recommendation Summary\n\n")
        
        f.write("## Run Info\n")
        f.write(f"- Run ID: {summary.get('run_id')}\n")
        f.write(f"- Included previous folders: {', '.join(summary.get('included_previous_today_folders', []))}\n")
        f.write(f"- Previous rows loaded: {summary.get('previous_rows_loaded')}\n")
        f.write(f"- New rows loaded: {summary.get('new_rows_loaded')}\n")
        f.write(f"- Duplicates removed: {summary.get('duplicates_removed')}\n")
        f.write(f"- Total exported: {summary.get('total_exported')}\n")
        f.write(f"- Total apply today: {len(apply_today)}\n\n")
        
        f.write("## Top 10 Apply Today\n")
        f.write("| Rank | Score | Category | Job Title | Company | Location | Source | Link | Why Apply |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for i, job in enumerate(apply_today[:10], 1):
            f.write(f"| {i} | {job.get('match_score')} | {job.get('match_category')} | {job.get('job_title')} | {job.get('company')} | {job.get('location')} | {job.get('source')} | [Link]({job.get('job_url')}) | {job.get('why_match')} |\n")
        
        f.write("\n## Strong Matches\n")
        for job in [j for j in ranked_jobs if j.get("match_score", 0) >= 85]:
            f.write(f"- **{job.get('job_title')}** @ {job.get('company')} ({job.get('match_score')} pts)\n")
            
        f.write("\n## Good Matches\n")
        for job in [j for j in ranked_jobs if 75 <= j.get("match_score", 0) < 85]:
            f.write(f"- **{job.get('job_title')}** @ {job.get('company')} ({job.get('match_score')} pts)\n")

        # --- GPA Risk Review Section ---
        f.write("\n## GPA Risk Review\n\n")
        f.write("### GPA Status Distribution\n")
        f.write("| GPA Status | Count |\n")
        f.write("| :--- | :--- |\n")
        for status, count in gpa_counts.items():
            f.write(f"| {status} | {count} |\n")
        f.write("\n")
        
        if gpa_slight_jobs:
            f.write("### Slight GPA Gap Jobs\n")
            f.write("Jobs where GPA requirement is only slightly above 3.29 (e.g., 3.30). These are still worth applying to.\n\n")
            for job in gpa_slight_jobs:
                f.write(f"- **{job.get('job_title')}** @ {job.get('company')} — GPA req: {job.get('gpa_required')} (Score: {job.get('match_score')} pts)\n")
            f.write("\n")
        
        if gpa_moderate_high_jobs:
            f.write("### Moderate / High GPA Gap Jobs\n")
            f.write("Jobs still included but with lower priority due to GPA gap.\n\n")
            for job in gpa_moderate_high_jobs:
                f.write(f"- **{job.get('job_title')}** @ {job.get('company')} — GPA req: {job.get('gpa_required')}, Status: {job.get('gpa_status')} (Score: {job.get('match_score')} pts)\n")
            f.write("\n")

        f.write("\n## Jobs to Review Manually\n")
        manual = [j for j in ranked_jobs if j.get("data_confidence", 0) < 60 or j.get("salary") == "Tidak tercantum" or "GPA_RISK" in j.get("reason_codes", "") or "MAJOR_RISK" in j.get("reason_codes", "") or "VAGUE_JD" in j.get("reason_codes", "")]
        for job in manual[:10]:
            f.write(f"- **{job.get('job_title')}** @ {job.get('company')} (Confidence: {job.get('data_confidence')}%)\n")

        f.write("\n## Jobs to Skip\n")
        skipped = [j for j in ranked_jobs if j.get("recommendation") == "Skip" or any(p in j.get("reason_codes", "") for p in ["EXPERIENCE_TOO_HIGH", "COMMISSION_ONLY", "UNPAID_INTERNSHIP"])]
        for job in skipped[:10]:
            f.write(f"- **{job.get('job_title')}** @ {job.get('company')} (Reason: {job.get('reason_codes')})\n")

        f.write("\n## CV Keywords to Emphasize Today\n")
        keywords = set()
        for job in ranked_jobs[:5]:
            for kw in job.get("keywords_found", "").split(", "):
                if kw: keywords.add(kw)
        f.write(", ".join(list(keywords)[:15]))
        f.write("\n")
    
    return True

def get_super_aggressive_fields(job, rank):
    score = job.get("match_score", 0)
    
    if score >= 75:
        priority = "Priority 1 - Apply Now"
        recommendation = "Apply"
        apply_notes = "Apply first. Strong enough match."
    elif score >= 60:
        priority = "Priority 2 - Apply Today"
        recommendation = "Apply"
        apply_notes = "Apply today. Good volume target."
    elif score >= 45:
        priority = "Priority 3 - Apply If Fast"
        recommendation = "Maybe Apply"
        apply_notes = "Apply if the form is quick."
    elif score >= 30:
        priority = "Priority 4 - Review Quickly"
        recommendation = "Review"
        apply_notes = "Review quickly before applying."
    else:
        priority = "Priority 5 - Last Option"
        recommendation = "Skip Last"
        apply_notes = "Last option only."

    def clean_text(text):
        if not text or text == "Tidak tercantum":
            return ""
        if isinstance(text, list):
            text = "; ".join([str(x) for x in text])
        return str(text).replace("\r", " ").replace("\n", " ").strip()

    return {
        "rank": rank,
        "score": score,
        "super_aggressive_priority": priority,
        "super_aggressive_recommendation": recommendation,
        "match_category": job.get("match_category", ""),
        "tracker_status": job.get("tracker_status", ""),
        "job_title": clean_text(job.get("job_title", "")),
        "company_name": clean_text(job.get("company", "")),
        "location": clean_text(job.get("location", "")),
        "job_link": clean_text(job.get("job_url", job.get("Link", ""))),
        "source": clean_text(job.get("source", "")),
        "source_url": clean_text(job.get("source_url", "")),
        "date_posted": clean_text(job.get("date_posted", "")),
        "date_collected": clean_text(job.get("date_collected", job.get("last_scraped", ""))),
        "salary_min": clean_text(job.get("salary_min", job.get("salary", ""))),
        "salary_max": clean_text(job.get("salary_max", "")),
        "industry": clean_text(job.get("industry", "")),
        "work_arrangement": clean_text(job.get("work_arrangement", "")),
        "parsing_confidence": job.get("data_confidence", ""),
        "match_reasons": clean_text(job.get("why_match", "")),
        "gaps": clean_text(job.get("gaps_or_concerns", "")),
        "missing_skills": clean_text(job.get("missing_skills", "")),
        "red_flags": clean_text(job.get("reason_codes", "")),
        "cv_tailoring_notes": clean_text(job.get("suggested_cv_tailoring", "")),
        "job_description": clean_text(job.get("job_description_summary", job.get("description", ""))),
        "requirements": clean_text(job.get("requirements", "")),
        "responsibilities": clean_text(job.get("responsibilities", "")),
        "raw_text": clean_text(job.get("raw_text", "")),
        "data_origin": clean_text(job.get("data_origin", "scraper")),
        "duplicate_group_key": clean_text(job.get("duplicate_group_key", "")),
        "gpa_required": clean_text(str(job.get("gpa_required", ""))),
        "gpa_gap": clean_text(str(job.get("gpa_gap", ""))),
        "gpa_status": clean_text(job.get("gpa_status", "")),
        "gpa_note": clean_text(job.get("gpa_note", "")),
        "apply_notes": apply_notes
    }

def export_super_aggressive(ranked_jobs, filepath):
    columns = [
        "rank", "score", "super_aggressive_priority", "super_aggressive_recommendation",
        "match_category", "tracker_status", "job_title", "company_name", "location",
        "job_link", "source", "source_url", "date_posted", "date_collected",
        "salary_min", "salary_max", "industry", "work_arrangement", "parsing_confidence",
        "match_reasons", "gaps", "missing_skills", "red_flags", "cv_tailoring_notes",
        "job_description", "requirements", "responsibilities", "raw_text", "data_origin",
        "duplicate_group_key", "gpa_required", "gpa_gap", "gpa_status", "gpa_note",
        "apply_notes"
    ]
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    try:
        with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for rank, job in enumerate(ranked_jobs, 1):
                row = get_super_aggressive_fields(job, rank)
                writer.writerow(row)
        return True
    except Exception as e:
        print(f"Error exporting super aggressive CSV {filepath}: {e}")
        return False
