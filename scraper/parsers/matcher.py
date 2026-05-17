import re
import os

try:
    from candidate_profile import CANDIDATE_PROFILE, recommend_cv_variant
    from config.scoring import SCORING_WEIGHTS, PENALTIES
    from scraper.parsers.gpa_helper import calculate_gpa_fields
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from candidate_profile import CANDIDATE_PROFILE, recommend_cv_variant
    from config.scoring import SCORING_WEIGHTS, PENALTIES
    from scraper.parsers.gpa_helper import calculate_gpa_fields

def normalize_text(text):
    if not text: return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def deduplicate_jobs(jobs):
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = normalize_text(job.get("job_title", "")) + \
              normalize_text(job.get("company", "")) + \
              job.get("job_url", "")
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return unique_jobs

def calculate_score(job):
    score = 0
    why_match = []
    gaps = []
    reason_codes = []
    
    title_lower = job.get("job_title", "").lower()
    company_lower = job.get("company", "").lower()
    desc_lower = job.get("job_description_summary", "").lower()
    req_lower = job.get("requirements", "").lower()
    full_text = (title_lower + " " + desc_lower + " " + req_lower)

    # 1. Role Fit (20)
    role_score = 0
    for role in CANDIDATE_PROFILE["preferred_roles"]:
        if role.lower() in title_lower:
            role_score = SCORING_WEIGHTS["role_fit"]
            why_match.append(f"Role match: {role}")
            if any(kw in title_lower for kw in ["mt", "odp", "trainee"]):
                reason_codes.append("MT_ODP_MATCH")
            break
    score += role_score

    # 2. Experience Match (20)
    exp_score = SCORING_WEIGHTS["experience_match"]
    if any(kw in full_text for kw in ["fresh graduate", "lulusan baru", "graduate program", "0-1 year", "0-2 years"]):
        why_match.append("Experience match: Entry level (0-2 years)")
        reason_codes.append("FRESH_GRAD_ACCEPTED")
    score += exp_score

    # 3. Skill Match (20)
    skill_matches = 0
    matched_skills = []
    for skill in CANDIDATE_PROFILE["skills"]:
        if skill.lower() in full_text:
            skill_matches += 1
            matched_skills.append(skill)
            if "supply chain" in skill.lower() or "operations" in skill.lower():
                if "OPS_SUPPLY_CHAIN_MATCH" not in reason_codes: reason_codes.append("OPS_SUPPLY_CHAIN_MATCH")
            if "logistics" in skill.lower(): reason_codes.append("LOGISTICS_MATCH")
            if "warehouse" in skill.lower(): reason_codes.append("WAREHOUSE_MATCH")
            if "procurement" in skill.lower(): reason_codes.append("PROCUREMENT_MATCH")
            if "commercial" in skill.lower(): reason_codes.append("COMMERCIAL_MATCH")

    skill_score = min(SCORING_WEIGHTS["skill_match"], skill_matches * 2)
    if matched_skills:
        why_match.append(f"Skills matched: {', '.join(matched_skills[:3])}")
    score += skill_score

    # 4. Industry Match (10)
    industry_score = 0
    for ind in CANDIDATE_PROFILE["industries"]:
        if ind.lower() in full_text or ind.lower() in company_lower:
            industry_score = SCORING_WEIGHTS["industry_match"]
            why_match.append(f"Industry match: {ind}")
            if ind.lower() == "fmcg": reason_codes.append("FMCG_MATCH")
            break
    score += industry_score

    # 5. Leadership Fit (10)
    if any(kw in full_text for kw in ["leadership", "trainee", "development program", "future leader", "execution"]):
        score += SCORING_WEIGHTS["leadership_fit"]
        why_match.append("Leadership/Execution fit")

    # 6. Education Fit (10)
    if any(kw in full_text for kw in ["s1", "d4", "bisnis", "internasional", "unpad"]):
        score += SCORING_WEIGHTS["education_fit"]
        why_match.append("Education match: D4 Bisnis Internasional Unpad")
    else:
        reason_codes.append("MAJOR_RISK")

    # 7. Location Fit (5)
    if CANDIDATE_PROFILE["willing_to_relocate"]:
        score += SCORING_WEIGHTS["location_fit"]
        why_match.append("Willing to relocate (nationwide)")
        reason_codes.append("NATIONWIDE_PLACEMENT")

    # 8. Compensation Fit (5)
    score += SCORING_WEIGHTS["compensation_fit"]
    if job.get("salary") == "Tidak tercantum":
        reason_codes.append("SALARY_MISSING")

    # --- Penalties ---
    if re.search(r"3\s*(?:year|tahun)", full_text):
        score += PENALTIES["exp_3_plus"]
        gaps.append("Requires 3+ years experience")
        reason_codes.append("EXPERIENCE_TOO_HIGH")
    if re.search(r"5\s*(?:year|tahun)", full_text):
        score += PENALTIES["exp_5_plus"]
        gaps.append("Requires 5+ years experience")
        if "EXPERIENCE_TOO_HIGH" not in reason_codes: reason_codes.append("EXPERIENCE_TOO_HIGH")
    
    if job.get("company") == "Tidak tercantum":
        reason_codes.append("UNCLEAR_COMPANY")
    
    if len(desc_lower) < 100:
        reason_codes.append("VAGUE_JD")

    if any(kw in full_text for kw in ["commission only", "unpaid", "tidak dibayar"]):
        score += PENALTIES["commission_only"]
        gaps.append("Commission-only or unpaid")
        if "unpaid" in full_text: reason_codes.append("UNPAID_INTERNSHIP")
        else: reason_codes.append("COMMISSION_ONLY")

    # --- GPA-Aware Scoring ---
    gpa_result = calculate_gpa_fields(job)
    score += gpa_result["gpa_penalty"]
    reason_codes.extend(gpa_result["gpa_reason_codes"])
    if gpa_result["gpa_penalty"] < 0:
        gaps.append(f"GPA risk: {gpa_result['gpa_note']}")

    score = max(0, min(100, score))
    
    # Match Category & Recommendation
    category = "Not Recommended"
    recommendation = "Skip"
    if score >= 85:
        category = "Strong Match"; recommendation = "Apply"
    elif score >= 75:
        category = "Good Match"; recommendation = "Apply / Maybe"
    elif score >= 60:
        category = "Possible Match"; recommendation = "Maybe"
    elif score >= 45:
        category = "Weak Match"; recommendation = "Low Priority"

    # Confidence Override
    if job.get("data_confidence", 100) < 50:
        recommendation = "Review Manually"

    cv_to_use = recommend_cv_variant(title_lower)
    tailoring = f"Gunakan CV: {cv_to_use}. Highlight {', '.join(matched_skills[:3]) if matched_skills else 'operational leadership'} & D4 Bisnis Internasional Unpad."

    return {
        "match_score": score,
        "match_category": category,
        "recommendation": recommendation,
        "why_match": "; ".join(why_match),
        "gaps_or_concerns": "; ".join(gaps) if gaps else "None detected",
        "suggested_cv_tailoring": tailoring,
        "reason_codes": ", ".join(reason_codes),
        "gpa_required": gpa_result["gpa_required"],
        "gpa_gap": gpa_result["gpa_gap"],
        "gpa_status": gpa_result["gpa_status"],
        "gpa_note": gpa_result["gpa_note"],
    }

def rank_jobs(jobs):
    scored_jobs = []
    for job in jobs:
        scoring_data = calculate_score(job)
        job.update(scoring_data)
        scored_jobs.append(job)
    return sorted(scored_jobs, key=lambda x: x["match_score"], reverse=True)
