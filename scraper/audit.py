"""One-pass deep audit: GPA + Deadline rescoring. No scraping."""
import sys, os, csv, json, shutil
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper.parsers.gpa_helper import calculate_gpa_fields
from scraper.parsers.deadline_helper import calculate_deadline_fields
from config.scoring import JOB_FIELDS

CANDIDATE_GPA = 3.29
TODAY = date.today()
SEVERE_CODES = ["EXPERIENCE_TOO_HIGH","COMMISSION_ONLY","UNPAID_INTERNSHIP","UNCLEAR_COMPANY","NOT_RELEVANT","DEADLINE_EXPIRED","GPA_RISK_HIGH"]

# --- Load ---
def load_csv(path):
    jobs = []
    col_map = {"Rank":"rank","Score":"match_score","Match Category":"match_category",
        "Recommendation":"recommendation","Job Title":"job_title","Company":"company",
        "Location":"location","Source":"source","Link":"job_url",
        "Why Match":"why_match","Gaps / Concerns":"gaps_or_concerns",
        "Suggested CV Tailoring":"suggested_cv_tailoring","reason_codes":"reason_codes",
        "data_confidence":"data_confidence","scrape_status":"scrape_status","run_id":"run_id",
        "gpa_required":"gpa_required","gpa_gap":"gpa_gap","gpa_status":"gpa_status","gpa_note":"gpa_note"}
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            j = {col_map.get(k, k.lower().replace(" ","_")): v for k, v in row.items()}
            jobs.append(j)
    return jobs

def enrich_from_sa(jobs, sa_path):
    """Merge description data from super aggressive CSV if available."""
    if not os.path.exists(sa_path):
        return
    sa_map = {}
    with open(sa_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            link = row.get("job_link","").strip()
            if link:
                sa_map[link.lower()] = row
    for j in jobs:
        url = j.get("job_url","").lower().strip()
        if url in sa_map:
            sa = sa_map[url]
            for field in ["job_description","requirements","responsibilities","raw_text"]:
                val = sa.get(field,"").strip()
                if val and val != "Tidak tercantum":
                    j[field] = val

# --- Audit & Score ---
def audit_job(job, old_score):
    gpa = calculate_gpa_fields(job, CANDIDATE_GPA)
    dl = calculate_deadline_fields(job, TODAY)
    
    # Rebuild reason codes: keep non-GPA/non-deadline codes
    old_codes = [c.strip() for c in job.get("reason_codes","").split(",") if c.strip()]
    gpa_dl_prefixes = ("GPA_","DEADLINE_")
    kept_codes = [c for c in old_codes if not any(c.startswith(p) for p in gpa_dl_prefixes)]
    new_codes = kept_codes + gpa["gpa_reason_codes"] + dl["deadline_reason_codes"]

    # Recalc score: start from old base, remove old GPA effect, apply new
    score = old_score + gpa["gpa_penalty"] + dl["deadline_penalty"]
    score = max(0, min(100, score))

    # Category & recommendation
    if score >= 85: cat, rec = "Strong Match", "Apply"
    elif score >= 75: cat, rec = "Good Match", "Apply / Maybe"
    elif score >= 60: cat, rec = "Possible Match", "Maybe"
    elif score >= 45: cat, rec = "Weak Match", "Low Priority"
    else: cat, rec = "Not Recommended", "Skip"
    
    conf = float(job.get("data_confidence", 0) or 0)
    if conf < 50:
        rec = "Review Manually"

    # Gaps
    gaps = []
    old_gaps = job.get("gaps_or_concerns","")
    if old_gaps and old_gaps != "None detected":
        gaps.append(old_gaps)
    if gpa["gpa_penalty"] < 0:
        gaps.append(f"GPA: {gpa['gpa_note']}")
    if dl["deadline_penalty"] < 0:
        gaps.append(f"Deadline: {dl['deadline_note']}")

    job.update({
        "match_score": score, "match_category": cat, "recommendation": rec,
        "reason_codes": ", ".join(new_codes),
        "gaps_or_concerns": "; ".join(gaps) if gaps else "None detected",
        "gpa_required": gpa["gpa_required"], "gpa_gap": gpa["gpa_gap"],
        "gpa_status": gpa["gpa_status"], "gpa_note": gpa["gpa_note"],
        "deadline_parsed": dl["deadline_parsed"], "deadline_status": dl["deadline_status"],
        "days_until_deadline": dl["days_until_deadline"], "urgency_level": dl["urgency_level"],
        "deadline_note": dl["deadline_note"],
    })
    return gpa["gpa_penalty"] != 0, dl["deadline_penalty"] != 0

# --- Apply Today ---
def calc_not_apply_reason(job):
    score = job.get("match_score", 0)
    conf = float(job.get("data_confidence", 0) or 0)
    rec = job.get("recommendation", "")
    codes = job.get("reason_codes", "")
    gs = job.get("gpa_status", "")
    ds = job.get("deadline_status", "")
    url = job.get("job_url", "") or job.get("apply_url", "")

    if ds == "Expired": return "Expired deadline"
    if score < 75: return "Score below 75"
    if conf < 60: return "Data confidence below 60"
    if rec not in ("Apply", "Apply / Maybe"): return "Recommendation not Apply"
    for sev in SEVERE_CODES:
        if sev in codes:
            if sev == "DEADLINE_EXPIRED": return "Expired deadline"
            if sev == "GPA_RISK_HIGH": return "High GPA gap"
            return sev.replace("_"," ").title()
    if not url or url == "Tidak tercantum": return "Missing apply URL"
    if gs == "High GPA Gap": return "High GPA gap"
    if gs == "Moderate GPA Gap" and score < 90: return "Moderate GPA gap and score below 90"
    if gs == "Slight GPA Gap" and score < 80: return "Slight GPA gap and score below 80"
    if gs == "Qualitative GPA Requirement" and score < 75: return "Qualitative GPA and score below 75"
    return None  # Passes!

# --- Export ---
AUDIT_FIELDS = JOB_FIELDS + ["deadline_parsed","deadline_status","days_until_deadline","urgency_level","deadline_note","not_apply_today_reason"]

def export_csv(jobs, path, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mapping = {"rank":"Rank","match_score":"Score","match_category":"Match Category",
        "recommendation":"Recommendation","job_title":"Job Title","company":"Company",
        "location":"Location","source":"Source","job_url":"Link",
        "why_match":"Why Match","gaps_or_concerns":"Gaps / Concerns",
        "suggested_cv_tailoring":"Suggested CV Tailoring"}
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for rank, job in enumerate(jobs, 1):
            row = {mapping.get(k,k): job.get(k, "Tidak tercantum") for k in mapping}
            row["Rank"] = rank
            for col in fields:
                if col not in row:
                    ik = [a for a,b in mapping.items() if b == col]
                    row[col] = job.get(ik[0], "Tidak tercantum") if ik else job.get(col.lower().replace(" ","_"), "Tidak tercantum")
            w.writerow(row)

def write_audit_report(path, stats, jobs):
    reasons = {}
    for j in jobs:
        r = j.get("not_apply_today_reason")
        if r:
            reasons[r] = reasons.get(r, 0) + 1
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Audit Report — One-Pass GPA + Deadline\n\n")
        f.write(f"- Total jobs audited: {stats['total']}\n")
        f.write(f"- Scores changed by GPA: {stats['gpa_changed']}\n")
        f.write(f"- Scores changed by deadline: {stats['dl_changed']}\n")
        f.write(f"- Expired jobs found: {stats['expired']}\n")
        f.write(f"- Expired removed from apply_today: {stats['expired_removed']}\n")
        f.write(f"- Jobs with GPA <= 3.29: {stats['gpa_ok']}\n")
        f.write(f"- Jobs with GPA > 3.29: {stats['gpa_above']}\n\n")
        f.write("## Top Reasons Not in Apply Today\n")
        for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
            f.write(f"- {r}: {c}\n")
        f.write("\n## Data Gaps\n")
        f.write(f"- Jobs with no description text for GPA scan: {stats['no_desc']}\n")
        f.write(f"- Jobs with unknown deadline: {stats['dl_unknown']}\n")

def write_rec_summary(path, jobs, stats, summary):
    at = [j for j in jobs if j.get("not_apply_today_reason") is None]
    with open(path, "w", encoding="utf-8") as f:
        f.write("# GPA + Deadline Reviewed Job Recommendations\n\n")
        f.write("## Top Apply Today\n")
        f.write("| # | Score | Title | Company | GPA Status | Deadline | Link |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, j in enumerate(at[:15], 1):
            f.write(f"| {i} | {j.get('match_score')} | {j.get('job_title','')} | {j.get('company','')} | {j.get('gpa_status','')} | {j.get('deadline_status','')} | [Link]({j.get('job_url','')}) |\n")

        f.write("\n## GPA Priority Review\n")
        for k in ["Priority GPA Match","Meets GPA","Slight GPA Gap","Moderate GPA Gap","High GPA Gap","No GPA Listed","Qualitative GPA Requirement"]:
            f.write(f"- {k}: {stats['gpa_dist'].get(k, 0)}\n")

        f.write("\n## Best GPA-Fit Jobs\n")
        for j in jobs:
            if j.get("gpa_status") in ("Priority GPA Match","Meets GPA"):
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — GPA req: {j.get('gpa_required')} (Score: {j.get('match_score')})\n")

        f.write("\n## GPA Gap Jobs\n")
        f.write("These jobs are still included but with lower priority due to GPA gap.\n\n")
        for j in jobs:
            if "GPA Gap" in j.get("gpa_status",""):
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — {j.get('gpa_status')}, req {j.get('gpa_required')} (Score: {j.get('match_score')})\n")

        f.write("\n## Deadline Review\n")
        for k in ["Open","Expired","Unknown"]:
            f.write(f"- {k}: {stats['dl_dist'].get(k,0)}\n")
        f.write(f"- Urgent High: {stats['urg_dist'].get('High',0)}\n")
        f.write(f"- Urgent Medium: {stats['urg_dist'].get('Medium',0)}\n")

        f.write("\n## Expired Jobs Removed from Apply Today\n")
        for j in jobs:
            if j.get("deadline_status") == "Expired":
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} — {j.get('deadline_note')}\n")

        f.write("\n## Review Manually\n")
        for j in jobs:
            gs = j.get("gpa_status","")
            ds = j.get("deadline_status","")
            conf = float(j.get("data_confidence",0) or 0)
            url = j.get("job_url","")
            if ds == "Unknown" or gs in ("No GPA Listed","Qualitative GPA Requirement") or conf < 60 or not url:
                f.write(f"- **{j.get('job_title')}** @ {j.get('company')} (GPA: {gs}, Deadline: {ds}, Conf: {conf}%)\n")

# --- Main ---
def main():
    base = "output"
    src = os.path.join(base, "latest", "jobs_ranked.csv")
    sa_path = os.path.join(base, "latest", "fahry_super_aggressive_unified_apply_export_2026-05-07.csv")
    
    if not os.path.exists(src):
        print(f"ERROR: {src} not found"); return

    start = datetime.now()
    now = datetime.now()
    run_dir = os.path.join(base, f"{now.strftime('%Y-%m-%d')}_GPA_DL_AUDIT_{now.strftime('%H-%M-%S')}")
    os.makedirs(run_dir, exist_ok=True)
    run_id = now.strftime("%Y%m%d_%H%M%S")

    print("="*60)
    print(f"  ONE-PASS GPA + DEADLINE AUDIT")
    print(f"  Run ID: {run_id}")
    print(f"  Output: {run_dir}")
    print("="*60 + "\n")

    # Load
    jobs = load_csv(src)
    print(f"Loaded {len(jobs)} jobs from {src}")
    enrich_from_sa(jobs, sa_path)
    enriched = sum(1 for j in jobs if j.get("job_description","").strip())
    print(f"Enriched {enriched} jobs with description data from super aggressive CSV")

    # Audit
    gpa_changed = dl_changed = 0
    for job in jobs:
        old_score = float(job.get("match_score", 0) or 0)
        job["data_confidence"] = float(job.get("data_confidence", 0) or 0)
        gc, dc = audit_job(job, old_score)
        if gc: gpa_changed += 1
        if dc: dl_changed += 1

    # Apply today
    for job in jobs:
        job["not_apply_today_reason"] = calc_not_apply_reason(job)

    # Sort
    dl_order = {"Open": 0, "Unknown": 1, "Expired": 2}
    urg_order = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3, "Expired": 4}
    jobs.sort(key=lambda j: (
        -j.get("match_score", 0),
        -j.get("data_confidence", 0),
        dl_order.get(j.get("deadline_status","Unknown"), 1),
        urg_order.get(j.get("urgency_level","Unknown"), 3),
        j.get("company",""), j.get("job_title","")
    ))

    # Stats
    gpa_dist = {}
    for j in jobs:
        gs = j.get("gpa_status","No GPA Listed")
        gpa_dist[gs] = gpa_dist.get(gs, 0) + 1
    dl_dist = {}
    for j in jobs:
        ds = j.get("deadline_status","Unknown")
        dl_dist[ds] = dl_dist.get(ds, 0) + 1
    urg_dist = {}
    for j in jobs:
        ul = j.get("urgency_level","Unknown")
        urg_dist[ul] = urg_dist.get(ul, 0) + 1

    expired = dl_dist.get("Expired", 0)
    expired_removed = sum(1 for j in jobs if j.get("deadline_status") == "Expired" and j.get("not_apply_today_reason") == "Expired deadline")
    gpa_ok = sum(1 for j in jobs if j.get("gpa_status") in ("Priority GPA Match","Meets GPA","No GPA Listed"))
    gpa_above = sum(1 for j in jobs if "GPA Gap" in j.get("gpa_status",""))
    no_desc = sum(1 for j in jobs if not j.get("job_description","").strip() and not j.get("requirements","").strip())
    apply_today_jobs = [j for j in jobs if j.get("not_apply_today_reason") is None]

    stats = {"total": len(jobs), "gpa_changed": gpa_changed, "dl_changed": dl_changed,
             "expired": expired, "expired_removed": expired_removed, "gpa_ok": gpa_ok,
             "gpa_above": gpa_above, "no_desc": no_desc, "dl_unknown": dl_dist.get("Unknown",0),
             "gpa_dist": gpa_dist, "dl_dist": dl_dist, "urg_dist": urg_dist}

    # Export
    export_csv(jobs, os.path.join(run_dir, "jobs_ranked.csv"), AUDIT_FIELDS)
    export_csv(apply_today_jobs, os.path.join(run_dir, "apply_today.csv"), AUDIT_FIELDS)

    summary = {
        "run_id": run_id, "run_type": "ONE_PASS_GPA_DEADLINE_AUDIT",
        "started_at": start.isoformat(), "finished_at": datetime.now().isoformat(),
        "duration_seconds": (datetime.now()-start).total_seconds(),
        "total_jobs_audited": len(jobs), "total_apply_today": len(apply_today_jobs),
        "gpa_priority_match_count": gpa_dist.get("Priority GPA Match",0),
        "gpa_meets_count": gpa_dist.get("Meets GPA",0),
        "gpa_slight_gap_count": gpa_dist.get("Slight GPA Gap",0),
        "gpa_moderate_gap_count": gpa_dist.get("Moderate GPA Gap",0),
        "gpa_high_gap_count": gpa_dist.get("High GPA Gap",0),
        "gpa_not_listed_count": gpa_dist.get("No GPA Listed",0),
        "gpa_qualitative_count": gpa_dist.get("Qualitative GPA Requirement",0),
        "deadline_open_count": dl_dist.get("Open",0),
        "deadline_expired_count": expired,
        "deadline_unknown_count": dl_dist.get("Unknown",0),
        "deadline_urgent_high_count": urg_dist.get("High",0),
        "deadline_urgent_medium_count": urg_dist.get("Medium",0),
        "expired_removed_from_apply_today_count": expired_removed,
        "scores_changed_by_gpa_count": gpa_changed,
        "scores_changed_by_deadline_count": dl_changed,
        "output_folder": run_dir, "latest_folder": os.path.join(base,"latest"),
        "included_previous_today_folders": [], "previous_rows_loaded": len(jobs),
        "new_rows_loaded": 0, "duplicates_removed": 0, "total_exported": len(jobs),
    }
    with open(os.path.join(run_dir, "run_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(run_dir, "logs.txt"), "w") as f:
        f.write(f"One-pass audit completed at {datetime.now().isoformat()}\n")
        f.write(f"Jobs: {len(jobs)}, GPA changed: {gpa_changed}, DL changed: {dl_changed}\n")

    write_audit_report(os.path.join(run_dir, "audit_report.md"), stats, jobs)
    write_rec_summary(os.path.join(run_dir, "recommendation_summary.md"), jobs, stats, summary)

    # Update latest
    latest = os.path.join(base, "latest")
    os.makedirs(latest, exist_ok=True)
    for fname in ["jobs_ranked.csv","apply_today.csv","run_summary.json","logs.txt","recommendation_summary.md","audit_report.md"]:
        src_f = os.path.join(run_dir, fname)
        if os.path.exists(src_f):
            shutil.copy2(src_f, os.path.join(latest, fname))

    # Final print
    print(f"\nONE-PASS GPA + DEADLINE AUDIT COMPLETE\n")
    print(f"Run folder:\n{os.path.abspath(run_dir)}\n")
    print(f"Latest folder:\noutput/latest\n")
    print(f"Total jobs audited:\n{len(jobs)}\n")
    print(f"Apply today:\n{len(apply_today_jobs)}\n")
    print(f"GPA <= 3.29:\n{gpa_ok}\n")
    print(f"GPA > 3.29:\n{gpa_above}\n")
    print(f"Expired jobs:\n{expired}\n")
    print(f"Expired removed from apply today:\n{expired_removed}\n")
    print(f"Scores changed by GPA:\n{gpa_changed}\n")
    print(f"Scores changed by deadline:\n{dl_changed}\n")
    print(f"\nOpen:")
    print("output/latest/audit_report.md")
    print("output/latest/recommendation_summary.md")
    print("output/latest/jobs_ranked.csv")
    print("output/latest/apply_today.csv")

if __name__ == "__main__":
    main()
