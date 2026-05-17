# Candidate Profile - Python Representation (Enriched v2.0)
# Sync this with candidate_profile.md
# Last updated: 2026-05-13

CANDIDATE_PROFILE = {
    # === IDENTITY ===
    "name": "Fahry Ramadhan",
    "nickname": "Fahry",
    "date_of_birth": "2003-10-27",
    "age": 22,
    "gender": "Male",
    "religion": "Islam",
    "ethnicity": "Jawa",
    "marital_status": "Single",
    "nationality": "Indonesian",
    "phone": "0811172710",
    "email": "fahryramadhan4@gmail.com",
    "linkedin": "linkedin.com/in/fahry-ramadhan-33250321b",
    "instagram": "@fahryramadhannn",
    "location": "Tangerang Selatan, Banten",
    "address": "JL. Kerosin I Blok K.2/D.14 No. 11, Pondok Ranji, Ciputat Timur, Tangerang Selatan, Banten 15412",

    # === PHYSICAL & ADMINISTRATIVE ===
    "height_cm": 177,
    "weight_kg": 82,
    "blood_type": "A",
    "sim": ["SIM A", "SIM C"],
    "sim_valid_until": "2029-04-08",
    "bpjs_active": True,
    "bpjs_number": "0001634230179",
    "health_status": "All normal (MCU 2024)",
    "covid_vaccination": "Booster 2",
    "disability": False,
    "color_blind": False,

    # === EDUCATION ===
    "status": "Fresh graduate",
    "degree": "S1 / D4 Bisnis Internasional",
    "university": "Universitas Padjadjaran",
    "study_period": "Aug 2021 – Aug 2025",
    "gpa": 3.29,
    "gpa_scale": 4.00,
    "focus_areas": [
        "Strategi Bisnis", "Perdagangan Internasional",
        "Pemasaran", "Manajemen Operasional"
    ],
    "thesis": "Strategi Pengamanan dan Peningkatan Daya Saing Industri Keramik Lokal",
    "toefl_score": 540,
    "high_school": "SMAN 4 Tangerang Selatan (2019-2021), IPS",
    "languages": {
        "Indonesian": "Native",
        "English": "Intermediate (TOEFL 540)",
        "Mandarin": "Basic"
    },

    # === EMPLOYMENT PREFERENCES ===
    "target_salary_idr_min": 5500000,
    "target_salary_idr_max": 7000000,
    "expected_benefits": [
        "BPJS Kesehatan", "BPJS Ketenagakerjaan",
        "Tunjangan transportasi", "Tunjangan makan"
    ],
    "willing_to_relocate": True,
    "willing_remote_area": True,
    "work_arrangement": ["onsite", "hybrid", "remote"],
    "available_immediately": True,
    "open_to_alternative_positions": True,
    "last_salary_idr": 5399000,  # PT Plymilindo Perdana internship

    # === TARGET ROLES ===
    "preferred_roles": [
        "Management Trainee", "Management Trainee Operations",
        "Management Trainee Sales", "Management Trainee Generalist",
        "MT", "ODP", "Officer Development Program",
        "Graduate Development Program", "GDP",
        "Management Development Program", "MDP",
        "Graduate Trainee", "Fresh Graduate Program",
        "Business Operations Associate", "Operations Associate",
        "Supply Chain Associate", "Warehouse Operations",
        "Inventory Control", "Logistics Coordinator",
        "Commercial Operations", "Business Development Associate",
        "Business Development Executive", "Export Import Staff",
        "Procurement Staff", "Purchasing Staff",
        "Retail Operations Trainee", "FMCG Management Trainee",
        "Manufacturing Management Trainee",
        "Logistics Management Trainee", "Operations Trainee",
        "Supply Chain Trainee", "Procurement Trainee",
        "Commercial Trainee", "New Retail Management Trainee",
        "Sales Trainee", "Marketing Trainee"
    ],

    # === ROLE KEYWORD PATTERNS (for fuzzy matching) ===
    "role_keywords_positive": [
        "management trainee", "mt ", "odp", "gdp", "mdp",
        "graduate program", "trainee", "fresh graduate",
        "development program", "associate", "coordinator",
        "operations", "supply chain", "warehouse", "logistics",
        "procurement", "purchasing", "inventory", "export",
        "import", "commercial", "business development",
        "retail", "sales trainee", "marketing trainee"
    ],
    "role_keywords_negative": [
        "senior", "manager", "lead", "head", "director",
        "5+ years", "3+ years", "experienced",
        "medical", "doctor", "nurse", "engineer",
        "software", "developer", "programmer", "data scientist",
        "designer", "architect", "lawyer", "accountant",
        "S2 required", "master required"
    ],

    # === INDUSTRIES ===
    "industries": [
        "FMCG", "Manufacturing", "Logistics", "Retail",
        "Multifinance", "Consumer Goods", "Consumer Electronics",
        "Export-Import", "Supply Chain", "Operations",
        "Warehouse", "Procurement", "Purchasing",
        "Commercial", "Business Development",
        "Automotive", "Mining", "Heavy Equipment",
        "Banking", "Financial Services", "Distribution",
        "Telecommunications"
    ],

    # === PROFESSIONAL EXPERIENCE ===
    "experience": [
        {
            "title": "Owner & Head of Research & Development",
            "company": "Brochacho Holdings",
            "period": "Apr 2025 – Present",
            "location": "Tangerang Selatan",
            "type": "entrepreneurship",
            "highlights": [
                "Founded consumer goods company from ground up",
                "Developed 5+ SKUs through market research & competitor analysis",
                "Built business operating systems from scratch",
                "Managed full supply chain: sourcing to distribution",
                "Led lean team of 2-3 people"
            ]
        },
        {
            "title": "Independent Trader — Smartphones & Electronics",
            "company": "Self-Employed",
            "period": "2021 – Present",
            "type": "entrepreneurship",
            "highlights": [
                "3-5 transactions/month, 20-30% profit margin",
                "Market trend analysis & demand forecasting",
                "Built loyal buyer network on Tokopedia & Shopee",
                "Managed asset rotation & capital liquidity independently"
            ]
        },
        {
            "title": "Intern — Warehouse & Supply Chain",
            "company": "PT. Plymilindo Perdana",
            "period": "Oct 2025 – Apr 2026",
            "location": "Tangerang, Banten",
            "industry": "Industrial Manufacturing",
            "type": "internship",
            "salary": 5399000,
            "highlights": [
                "Industrial-scale warehouse ops with 10+ person team",
                "Stock verification & real-time inventory monitoring",
                "Identified layout inefficiencies, proposed workflow improvements",
                "Completed ISO 9001:2015 QMS training"
            ]
        },
        {
            "title": "Intern — Marketing & Promotion",
            "company": "Kementerian Perindustrian — Balai Besar Keramik",
            "period": "Feb 2024 – Aug 2024",
            "location": "Bandung, Jawa Barat",
            "industry": "Government / Public Sector",
            "type": "internship",
            "highlights": [
                "6-month national ceramic product promotion program",
                "Marketing materials development & partner coordination",
                "Market data collection & analysis for strategic decisions",
                "External stakeholder communication"
            ]
        },
        {
            "title": "Crowd Control Manager",
            "company": "Ciremai Music Festival 2023",
            "period": "Aug – Sep 2023",
            "location": "Ciremai, Jawa Barat",
            "type": "event_management",
            "highlights": [
                "Led field team for 5,000+ visitors",
                "Achieved zero incidents",
                "Real-time coordination with security, organizers, vendors",
                "Handled crowd surge exceeding initial estimates"
            ]
        },
        {
            "title": "Creative Assistant",
            "company": "Garuda International Cup II",
            "period": "Jun – Jul 2022",
            "location": "Sentul, Jawa Barat",
            "type": "event_management",
            "highlights": [
                "Cross-divisional creative & logistics coordination",
                "International sports event"
            ]
        }
    ],

    # === ORGANIZATIONAL EXPERIENCE ===
    "organizations": [
        {
            "role": "Facilitator",
            "org": "P Plus FEB Unpad 2023 & Discovery Bisnis Internasional 2023",
            "period": "Jan – Feb 2023"
        },
        {
            "role": "Deputy Technical Director",
            "org": "EFEST 2022 — Economics Symposium",
            "period": "Jan – Mar 2022"
        },
        {
            "role": "Technical & Logistics",
            "org": "Padjadjaran Educational Festival 2021 & FEB Awards 2021",
            "period": "Jan – Mar 2021"
        }
    ],

    # === SKILLS ===
    "skills": [
        "Business Strategy & Development",
        "Operations & Supply Chain Management",
        "Market Research & Data Analysis",
        "Negotiation & Stakeholder Management",
        "Cross-functional Team Coordination",
        "Project Execution Under Pressure",
        "Entrepreneurial Mindset & Ownership",
        "Process Improvement",
        "Quality Management (ISO 9001:2015)",
        "International Trade & Export Documentation",
        "Customer Relationship Management",
        "Inventory Monitoring & Stock Accuracy",
        "Logistics Coordination & Shipment Monitoring",
        "Procurement & Purchasing Support",
        "Vendor Coordination",
        "Marketplace Management (Tokopedia, Shopee)",
        "Pricing Strategy & Competitive Analysis",
        "Event Operations & Crowd Management",
        "Leadership Under Pressure",
        "Operational Reporting",
        "Commercial Operations",
        "Business Development Support",
        "Product R&D & Go-to-Market Strategy",
        "Financial Recording & Business Systems",
        "Microsoft Office (Word, Excel, PowerPoint)",
        "Business Proposal Development"
    ],

    # === SKILL KEYWORDS (for matching against job descriptions) ===
    "skill_keywords": [
        "operations", "supply chain", "warehouse", "inventory",
        "logistics", "procurement", "purchasing", "vendor",
        "market research", "data analysis", "negotiation",
        "stakeholder", "coordination", "project management",
        "iso 9001", "quality management", "export", "import",
        "customs", "documentation", "hs code", "business development",
        "crm", "customer relationship", "marketplace",
        "microsoft office", "excel", "leadership", "team",
        "cross-functional", "process improvement", "pricing",
        "strategy", "commercial", "reporting", "product development",
        "go-to-market", "entrepreneur", "fmcg", "consumer goods",
        "retail", "sales", "marketing", "distribution"
    ],

    # === CERTIFICATIONS ===
    "certifications": [
        {
            "name": "BNSP Competency Certificate — Export Document Preparation",
            "reg_number": "EXIM.1593.00071",
            "issuer": "LSP Ekspor Impor Internasional, Bandung",
            "valid_from": "2024-06",
            "valid_until": "2027-06",
            "competency_units": [
                "HS Code Classification",
                "Customs Clearance",
                "Export Documentation",
                "SKA Completion",
                "Packing List",
                "Invoice",
                "Post-Clearance Procedures"
            ]
        },
        {
            "name": "ISO 9001:2015 Quality Management System Training",
            "cert_number": "003/PP/TRN/ISO/1025/01",
            "issuer": "PT. Plymilindo Perdana",
            "date": "2025-10-20"
        }
    ],

    # === PERSONALITY PROFILE ===
    "mbti": "ENTJ",
    "personality_traits": [
        "Decisive", "Strategic", "Leadership-oriented",
        "Goal-driven", "Assertive", "Fast learner",
        "Cross-functional agility", "Entrepreneurial mindset",
        "Target-oriented", "Proactive & self-driven",
        "Resilient under pressure", "Adaptable"
    ],
    "hobbies": ["Memasak", "Berbisnis", "Bersepeda", "Bulu tangkis"],
    "interested_fields": ["Management System", "Marketing", "Logistic & Spare Part"],

    # === CV VARIANTS (for tailored application) ===
    "cv_variants": {
        "general_mt_id": "CV_Fahry_Ramadhan.pdf",
        "general_mt_id_docx": "CV_Fahry_Ramadhan_MT.docx",
        "ats_en": "Fahry_Ramadhan_CV_ATS_EN.pdf",
        "formal_riwayat_hidup": "CV_ID_Fahry_Ramadhan.pdf",
        "with_photo_id": "CV_FAHRY_ADA_FOTO.pdf",
        "with_photo_en": "Cv_Terakhir_fahry.pdf",
        "fastrata_mt_sales": "CV_Fahry_FastrataBuana_MT_Sales_ID.pdf",
        "xiaomi_new_retail": "CV_Fahry_Xiaomi_NewRetailMT.pdf",
        "secure_parking_bde": "CV_Fahry_SecureParking_BDE.docx"
    },

    # === SCORING WEIGHTS ===
    "scoring_weights": {
        "role_fit": 20,
        "experience_match": 20,
        "skill_match": 20,
        "industry_domain_match": 10,
        "leadership_execution_fit": 10,
        "education_certification_fit": 10,
        "location_work_arrangement_fit": 5,
        "compensation_fit": 5
    },

    # === RECOMMENDATION THRESHOLDS ===
    "recommendation_rules": {
        "strong_match": {"min": 85, "max": 100, "action": "Apply"},
        "good_match": {"min": 75, "max": 84, "action": "Apply / Maybe"},
        "possible_match": {"min": 60, "max": 74, "action": "Maybe"},
        "weak_match": {"min": 45, "max": 59, "action": "Low Priority"},
        "not_recommended": {"min": 0, "max": 44, "action": "Skip"}
    }
}


# === HELPER FUNCTIONS ===

def get_all_role_keywords():
    """Return combined list of role titles and positive keywords for matching."""
    return (
        [r.lower() for r in CANDIDATE_PROFILE["preferred_roles"]] +
        CANDIDATE_PROFILE["role_keywords_positive"]
    )


def get_negative_keywords():
    """Return negative keywords that should disqualify a job listing."""
    return CANDIDATE_PROFILE["role_keywords_negative"]


def get_skill_keywords():
    """Return skill keywords for matching against job descriptions."""
    return CANDIDATE_PROFILE["skill_keywords"]


def get_industry_keywords():
    """Return industry keywords for domain matching."""
    return [i.lower() for i in CANDIDATE_PROFILE["industries"]]


def recommend_cv_variant(job_title: str, job_language: str = "id") -> str:
    """Suggest the best CV variant based on job title and language."""
    title_lower = job_title.lower()
    variants = CANDIDATE_PROFILE["cv_variants"]

    # Specific role matches
    if "sales" in title_lower and "fastrata" in title_lower:
        return variants["fastrata_mt_sales"]
    if "retail" in title_lower or "xiaomi" in title_lower:
        return variants["xiaomi_new_retail"]
    if "business development" in title_lower:
        return variants["secure_parking_bde"]

    # Language-based defaults
    if job_language == "en":
        return variants["ats_en"]

    # Check if formal CV needed (government, SOE, BUMN)
    if any(kw in title_lower for kw in ["pama", "astra", "bumn", "pertamina", "pln"]):
        return variants["formal_riwayat_hidup"]

    # Default
    return variants["general_mt_id"]


def calculate_compensation_fit(salary_offered: int) -> float:
    """Calculate compensation fit score (0-1)."""
    min_sal = CANDIDATE_PROFILE["target_salary_idr_min"]
    max_sal = CANDIDATE_PROFILE["target_salary_idr_max"]

    if salary_offered >= max_sal:
        return 1.0
    elif salary_offered >= min_sal:
        return 0.7 + 0.3 * ((salary_offered - min_sal) / (max_sal - min_sal))
    elif salary_offered >= min_sal * 0.8:
        return 0.4
    else:
        return 0.1
