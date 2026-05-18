// MT Job Tracker – Dashboard Script
// Reads from output/latest/ and renders interactive job cards

// ===================== STATE =====================
const APPLIED_KEY = 'mt_tracker_applied_v2';
const HIDDEN_KEY = 'mt_tracker_hidden_v1';
const KANBAN_KEY = 'mt_tracker_kanban_v1';

let allJobs = [];
let summaryData = {};
let currentTab = 'apply-today';
let currentCoverJob = null; 
let insightsData = null; 

let serverState = { kanban: {}, hidden: {}, notes: {}, historical_jobs: {} };

const state = {
    getKanban() { return serverState.kanban || {}; },
    getHidden() { return serverState.hidden || {}; },
    getNotes() { return serverState.notes || {}; },
    
    setKanban(obj) {
        serverState.kanban = obj;
        this.sync();
    },
    setHidden(obj) {
        serverState.hidden = obj;
        this.sync();
    },
    setNote(id, text) {
        if (!serverState.notes) serverState.notes = {};
        if (!text) delete serverState.notes[id];
        else serverState.notes[id] = text;
        this.sync();
    },
    
    sync() {
        fetch('/api/state', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(serverState)
        }).catch(err => console.error("Failed to sync state", err));
    },
    
    migrateFromLocal() {
        let changed = false;
        try {
            // Migrate old true/false applied to kanban
            const oldApplied = JSON.parse(localStorage.getItem(APPLIED_KEY));
            if (oldApplied && Object.keys(oldApplied).length > 0) {
                for (const id in oldApplied) {
                    if (!serverState.kanban[id]) serverState.kanban[id] = 'applied';
                }
                localStorage.removeItem(APPLIED_KEY);
                changed = true;
            }
            
            // Migrate kanban
            const localK = JSON.parse(localStorage.getItem(KANBAN_KEY));
            if (localK && Object.keys(localK).length > 0) {
                serverState.kanban = { ...serverState.kanban, ...localK };
                localStorage.removeItem(KANBAN_KEY);
                changed = true;
            }
            
            // Migrate hidden
            const localH = JSON.parse(localStorage.getItem(HIDDEN_KEY));
            if (localH && Object.keys(localH).length > 0) {
                serverState.hidden = { ...serverState.hidden, ...localH };
                localStorage.removeItem(HIDDEN_KEY);
                changed = true;
            }
        } catch(e) {}
        
        if (changed) this.sync();
    },

    // Timeline tracking
    getTimeline() { return serverState.timeline || {}; },
    setTimeline(obj) { serverState.timeline = obj; this.sync(); },
    addTimelineEvent(id, status) {
        const t = this.getTimeline();
        if (!t[id]) t[id] = [];
        t[id].push({ status, date: new Date().toISOString() });
        serverState.timeline = t;
    },
    // Reminders
    getReminders() { return serverState.reminders || {}; },
    setReminder(id, datetime) {
        const r = this.getReminders();
        r[id] = datetime;
        serverState.reminders = r;
        this.sync();
    },

    getStatus(id) { return this.getKanban()[id] || null; },
    setStatus(id, status) {
        const k = this.getKanban();
        if (status) {
            k[id] = status;
            this.addTimelineEvent(id, status);
            if (!serverState.historical_jobs) serverState.historical_jobs = {};
            if (!serverState.historical_jobs[id]) {
                const job = allJobs.find(j => j._id === id || j._id_alt === id);
                if (job) {
                    serverState.historical_jobs[id] = {
                        Company: job.Company,
                        'Job Title': job['Job Title'],
                        Location: job.Location,
                        URL: job.URL || '#',
                        Score: job.Score || job._score || 0,
                        'Why Match': job['Why Match'] || '',
                        _score: job.Score || job._score || 0,
                        _id: id
                    };
                }
            }
        } else { 
            delete k[id]; 
            if (serverState.historical_jobs) delete serverState.historical_jobs[id];
        }
        this.setKanban(k);
    },
    toggle(id) {
        const current = this.getStatus(id);
        if (current) this.setStatus(id, null); else this.setStatus(id, 'applied');
        return !!this.getStatus(id);
    },
    isApplied(id) { return !!this.getStatus(id); },
    appliedCount() { return Object.keys(this.getKanban()).length; },
    
    hide(id) {
        const h = this.getHidden();
        h[id] = new Date().toISOString();
        this.setHidden(h);
    },
    isHidden(id) { return !!this.getHidden()[id]; }
};

// ===================== INIT =====================
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupSearch();
    setupTheme();
    setupExport();
    fetchStateAndData();
});

// ===================== DARK MODE =====================
function setupTheme() {
    let saved = localStorage.getItem('mt_theme');
    if (!saved) {
        saved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        localStorage.setItem('mt_theme', saved);
    }
    
    if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    updateThemeIcon(saved);

    document.getElementById('theme-toggle').addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        if (next === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
        else document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('mt_theme', next);
        updateThemeIcon(next);
        // Redraw charts to match new theme colours
        if (typeof drawCharts === 'function') drawCharts();
    });
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle .material-icons-round');
    if (icon) icon.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
}

// ===================== EXPORT KANBAN =====================
function setupExport() {
    document.getElementById('export-kanban').addEventListener('click', () => {
        if (currentTab !== 'tracker') switchTab('tracker');
        setTimeout(() => window.print(), 300);
    });
}

// ===================== TABS =====================
function setupTabs() {
    document.querySelectorAll('.nav-item[data-tab]').forEach(item => {
        item.addEventListener('click', e => {
            e.preventDefault();
            switchTab(item.dataset.tab);
        });
    });
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.nav-item[data-tab]').forEach(i => i.classList.remove('active'));
    const activeNav = document.querySelector(`.nav-item[data-tab="${tab}"]`);
    if (activeNav) activeNav.classList.add('active');
    renderTab();
}

// ===================== SEARCH =====================
function setupSearch() {
    document.getElementById('search-input').addEventListener('input', renderTab);
    document.getElementById('score-filter').addEventListener('change', renderTab);
    if(document.getElementById('location-filter')) document.getElementById('location-filter').addEventListener('change', renderTab);
    if(document.getElementById('industry-filter')) document.getElementById('industry-filter').addEventListener('change', renderTab);
}

// ===================== FETCH DATA =====================
async function fetchStateAndData() {
    try {
        const stateRes = await fetch('/api/state');
        if (stateRes.ok) {
            const data = await stateRes.json();
            serverState.kanban = data.kanban || {};
            serverState.hidden = data.hidden || {};
            serverState.apply_dates = data.apply_dates || {};
            serverState.notes = data.notes || {};
            serverState.historical_jobs = data.historical_jobs || {};
            state.migrateFromLocal();
        }
    } catch (e) {
        console.warn("Could not fetch state from server, falling back to local memory", e);
        state.migrateFromLocal();
    }
    await fetchData();
}

async function fetchData() {
    try {
        const [summaryRes, csvRes, insightsRes] = await Promise.all([
            fetch('../output/latest/run_summary.json'),
            fetch('../output/latest/jobs_ranked.csv'),
            fetch('../output/latest/market_insights.json').catch(() => null)
        ]);

        if (!summaryRes.ok || !csvRes.ok) throw new Error('fetch failed');

        summaryData = await summaryRes.json();
        const csvText = await csvRes.text();
        
        if (insightsRes && insightsRes.ok) {
            try { insightsData = await insightsRes.json(); } catch(e) {}
        }

        Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            complete(results) {
                allJobs = results.data.map(j => ({
                    ...j,
                    URL: j.Link || j.URL || j.job_url || '#',
                    _score: parseFloat(j.Score || j['match_score'] || 0),
                    _isApplyToday: !j['not_apply_today_reason'] || j['not_apply_today_reason'].trim() === '',
                    _id: slugify((j.Company || '') + (j['Job Title'] || '') + (j.Location || '')),
                    _id_alt: slugify((j['Job Title'] || '') + (j.Company || '') + (j.Location || ''))
                }));
                initUI();
            },
            error(err) { showError(); }
        });
    } catch (e) {
        console.error(e);
        showError();
    }
}

// ===================== INIT UI =====================
function initUI() {
    hide('loading-state');
    const d = new Date(summaryData.finished_at || Date.now());
    const dateStr = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' });
    if(el('run-date-sidebar')) el('run-date-sidebar').textContent = 'Pembaruan: ' + dateStr;

    const applyTodayJobs = allJobs.filter(isApplyToday);
    if(el('all-count')) el('all-count').textContent = allJobs.length;
    if(el('apply-today-count')) el('apply-today-count').textContent = applyTodayJobs.length;

    populateFilters();
    initCustomDropdowns();
    renderTab();
    updateAppliedBadge();

    // Auto-hide header on scroll down, show on scroll up
    let lastScrollY = window.scrollY;
    const header = document.querySelector('.global-header');
    if (header) {
        window.addEventListener('scroll', () => {
            const currentScrollY = window.scrollY;
            if (Math.abs(currentScrollY - lastScrollY) < 10) return;
            
            if (currentScrollY > lastScrollY && currentScrollY > 80) {
                header.classList.add('header-hidden');
            } else {
                header.classList.remove('header-hidden');
            }
            lastScrollY = currentScrollY;
        }, { passive: true });
    }
}

function populateFilters() {
    const locations = new Set();
    const industries = new Set();
    
    allJobs.forEach(j => {
        if (j.Location && j.Location !== 'Tidak tercantum') {
            j.Location.split(',').map(l => l.trim()).forEach(l => {
                if (l) locations.add(l);
            });
        }
        
        const indMatch = (j['Why Match'] || '').match(/Industry match:\s([^;]+)/);
        if (indMatch && indMatch[1]) {
            industries.add(indMatch[1].trim());
        }
    });
    
    const locSelect = document.getElementById('location-filter');
    if (locSelect && locSelect.options.length <= 1) {
        Array.from(locations).sort().forEach(loc => {
            const opt = document.createElement('option');
            opt.value = loc; opt.textContent = loc;
            locSelect.appendChild(opt);
        });
    }
    
    const indSelect = document.getElementById('industry-filter');
    if (indSelect && indSelect.options.length <= 1) {
        Array.from(industries).sort().forEach(ind => {
            const opt = document.createElement('option');
            opt.value = ind; opt.textContent = ind;
            indSelect.appendChild(opt);
        });
    }
}

// ===================== RENDER TAB =====================
function renderTab() {
    hide('jobs-container');
    hide('overview-container');
    hide('empty-state');
    hide('kanban-board');
    hide('insights-container');

    const query = (el('search-input').value || '').toLowerCase().trim();
    const minScore = parseInt(el('score-filter').value || '0');
    const locationQuery = (el('location-filter') ? el('location-filter').value.toLowerCase() : '');
    const industryQuery = (el('industry-filter') ? el('industry-filter').value.toLowerCase() : '');

    const titles = {
        'apply-today': ['Rekomendasi Hari Ini', 'Lowongan terbaik yang sesuai dengan profil Anda'],
        'browse': ['Semua Lowongan', 'Jelajahi seluruh hasil scraping terbaru'],
        'tracker': ['Pelacakan Lamaran', 'Kanban board untuk memantau progres Anda'],
        'overview': ['Statistik Performa', 'Ringkasan pencarian kerja Anda'],
        'insights': ['Market Insights (AI)', 'Tren pasar kerja Management Trainee saat ini']
    };
    const [title, sub] = titles[currentTab] || ['', ''];
    if(el('page-title')) el('page-title').textContent = title;
    if (el('hero-title')) el('hero-title').textContent = title;
    if (el('summary-text')) el('summary-text').textContent = sub;

    if (currentTab === 'overview') {
        renderOverview();
        return;
    }
    
    if (currentTab === 'insights') {
        renderInsights();
        return;
    }

    let jobs = allJobs.filter(j => !state.isHidden(j._id));

    if (currentTab === 'tracker') {
        renderKanban();
        updateSummaryBar([], 'tracker');
        return;
    }

    if (currentTab === 'apply-today') {
        jobs = jobs.filter(isApplyToday);
    }

    if (query) {
        jobs = jobs.filter(j =>
            (j['Job Title'] || '').toLowerCase().includes(query) ||
            (j.Company || '').toLowerCase().includes(query) ||
            (j.Location || '').toLowerCase().includes(query)
        );
    }

    if (minScore > 0) {
        jobs = jobs.filter(j => j._score >= minScore);
    }
    
    if (locationQuery) {
        jobs = jobs.filter(j => (j.Location || '').toLowerCase().includes(locationQuery));
    }
    
    if (industryQuery) {
        jobs = jobs.filter(j => {
            const indMatch = (j['Why Match'] || '').match(/Industry match:\s([^;]+)/);
            return indMatch && indMatch[1].toLowerCase().includes(industryQuery);
        });
    }

    jobs = [...jobs].sort((a, b) => b._score - a._score || parseInt(a.Rank) - parseInt(b.Rank));
    updateSummaryBar(jobs, currentTab);

    if (jobs.length === 0) {
        show('empty-state');
        return;
    }

    const container = el('jobs-container');
    container.innerHTML = '';
    jobs.forEach((job, i) => container.appendChild(buildCard(job, i + 1, false)));
    show('jobs-container');
}

// ===================== KANBAN LOGIC =====================
function renderKanban() {
    show('kanban-board');
    
    document.querySelectorAll('.kanban-cards').forEach(c => {
        c.innerHTML = '';
        if(c.previousElementSibling) c.previousElementSibling.querySelector('.k-count').textContent = '0';
    });
    
    const kanbanData = state.getKanban();
    
    // Retrieve active filter values
    const query = (el('search-input')?.value || '').toLowerCase().trim();
    const minScore = parseInt(el('score-filter')?.value || '0');
    const locationQuery = (el('location-filter') ? el('location-filter').value.toLowerCase().trim() : '');
    const industryQuery = (el('industry-filter') ? el('industry-filter').value.toLowerCase().trim() : '');
    
    Object.keys(kanbanData).forEach(id => {
        const status = kanbanData[id];
        const job = allJobs.find(j => j._id === id || j._id_alt === id) || (serverState.historical_jobs && serverState.historical_jobs[id]);
        if (job) {
            // 1. Search Query Filter
            if (query) {
                const titleMatch = (job['Job Title'] || '').toLowerCase().includes(query);
                const companyMatch = (job.Company || '').toLowerCase().includes(query);
                const locMatch = (job.Location || '').toLowerCase().includes(query);
                if (!titleMatch && !companyMatch && !locMatch) return;
            }
            // 2. Score Filter
            if (minScore > 0) {
                const score = parseFloat(job.Score || job._score || 0);
                if (score < minScore) return;
            }
            // 3. Location Filter
            if (locationQuery) {
                if (!(job.Location || '').toLowerCase().includes(locationQuery)) return;
            }
            // 4. Industry Filter
            if (industryQuery) {
                if (!(job['Why Match'] || '').toLowerCase().includes(industryQuery)) return;
            }

            const card = buildCard(job, 0, true);
            const col = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-cards`);
            if (col) col.appendChild(card);
        }
    });
    
    let totalVisibleKanban = 0;
    document.querySelectorAll('.kanban-column').forEach(col => {
        const cardsContainer = col.querySelector('.kanban-cards');
        const count = cardsContainer.querySelectorAll('.k-card').length;
        if(col.querySelector('.k-count')) col.querySelector('.k-count').textContent = count;
        totalVisibleKanban += count;
        
        // Add collapse toggle if not already present
        const header = col.querySelector('.kanban-header');
        if (header && !header.querySelector('.k-toggle')) {
            const btn = document.createElement('button');
            btn.className = 'k-toggle';
            btn.innerHTML = '<span class="material-icons-round" style="font-size:18px;">expand_less</span>';
            btn.style.cssText = 'background:none; border:none; cursor:pointer; color:var(--store-text-muted); padding:4px; border-radius:50%; display:flex;';
            btn.addEventListener('click', () => {
                const isCollapsed = col.classList.toggle('collapsed');
                const icon = btn.querySelector('.material-icons-round');
                icon.textContent = isCollapsed ? 'expand_more' : 'expand_less';
            });
            header.appendChild(btn);
        }

        // Feature: elegant minimalist empty placeholder card
        if (count === 0) {
            const status = col.dataset.status;
            let icon = 'inbox';
            let label = 'Belum ada data';
            if (status === 'applied') { icon = 'inbox'; label = 'Belum ada lamaran'; }
            else if (status === 'assessment') { icon = 'fact_check'; label = 'Belum ada ujian'; }
            else if (status === 'interview') { icon = 'event'; label = 'Belum ada interview'; }
            else if (status === 'result') { icon = 'emoji_events'; label = 'Belum ada hasil'; }

            const placeholder = document.createElement('div');
            placeholder.className = 'k-empty-placeholder';
            placeholder.innerHTML = `
                <span class="material-icons-round">${icon}</span>
                <p>${label}</p>
            `;
            cardsContainer.appendChild(placeholder);
        }
    });

    if (el('applied-count')) el('applied-count').textContent = totalVisibleKanban;
}

window.dropKanban = function(event, status) {
    event.preventDefault();
    const id = event.dataTransfer.getData('text/plain');
    if (id) {
        state.setStatus(id, status);
        // If moved to interview, prompt for reminder
        if (status === 'interview') {
            const job = allJobs.find(j => j._id === id || j._id_alt === id) || (serverState.historical_jobs && serverState.historical_jobs[id]);
            const companyName = job ? job.Company : 'Pekerjaan Terlacak';
            const dt = prompt(`Kapan jadwal interview ${companyName}?\n(Format: 2026-05-20 09:00)`);
            if (dt) state.setReminder(id, dt);
        }
        renderKanban();
        updateAppliedBadge();
    }
};

// ===================== COVER LETTER AI =====================
window.openCoverLetterModal = function(jobId) {
    const job = allJobs.find(j => j._id === jobId);
    if (!job) return;
    
    currentCoverJob = job;
    show('cover-modal');
    show('cover-loading');
    hide('cover-text');
    hide('cover-footer');
    
    fetch('/api/generate-cover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: job.Company, title: job['Job Title'] })
    })
    .then(r => r.json())
    .then(data => {
        hide('cover-loading');
        if (data.error) {
            el('cover-text').value = "Error: " + data.error;
        } else {
            el('cover-text').value = data.cover_letter;
            show('cover-footer');
        }
        show('cover-text');
    })
    .catch(err => {
        hide('cover-loading');
        show('cover-text');
        el('cover-text').value = "Error menghubungkan ke AI Backend. Pastikan Anda menjalankan run_dashboard.py versi terbaru.";
    });
};

window.closeModal = function() {
    hide('cover-modal');
};

// ===================== INTERVIEW PREP AI =====================
window.openInterviewPrepModal = function(jobId) {
    const job = allJobs.find(j => j._id === jobId);
    if (!job) return;
    
    show('cover-modal');
    show('cover-loading');
    hide('cover-text');
    hide('cover-footer');
    
    // Update modal title
    const modalTitle = document.querySelector('.modal-header h2');
    if (modalTitle) modalTitle.textContent = '🎤 Persiapan Interview (AI)';
    
    fetch('/api/generate-interview-prep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: job.Company, title: job['Job Title'] })
    })
    .then(r => r.json())
    .then(data => {
        hide('cover-loading');
        if (data.error) {
            el('cover-text').value = 'Error: ' + data.error;
        } else {
            el('cover-text').value = data.prep;
            show('cover-footer');
        }
        show('cover-text');
    })
    .catch(() => {
        hide('cover-loading');
        show('cover-text');
        el('cover-text').value = 'Error menghubungkan ke AI Backend.';
    });
};

// ===================== RESUME PREP AI =====================
window.openResumePrepModal = function(jobId) {
    const job = allJobs.find(j => j._id === jobId);
    if (!job) return;
    
    show('cover-modal');
    show('cover-loading');
    hide('cover-text');
    hide('cover-footer');
    
    // Update modal title
    const modalTitle = document.querySelector('.modal-header h2');
    if (modalTitle) modalTitle.textContent = '📄 Bedah CV (ATS)';
    
    fetch('/api/generate-resume-tips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: job.Company, title: job['Job Title'] })
    })
    .then(r => r.json())
    .then(data => {
        hide('cover-loading');
        if (data.error) {
            el('cover-text').value = 'Error: ' + data.error;
        } else {
            el('cover-text').value = data.tips;
            show('cover-footer');
        }
        show('cover-text');
    })
    .catch(() => {
        hide('cover-loading');
        show('cover-text');
        el('cover-text').value = 'Error menghubungkan ke AI Backend.';
    });
};

const copyBtn = document.getElementById('copy-cover');
if(copyBtn) {
    copyBtn.addEventListener('click', () => {
        const text = el('cover-text').value;
        navigator.clipboard.writeText(text).then(() => {
            const btn = el('copy-cover');
            btn.textContent = 'Tersalin!';
            setTimeout(() => btn.textContent = 'Salin Teks', 2000);
        });
    });
}

function buildCard(job, displayRank, isKanban) {
    const score = job._score;
    const id = job._id;
    const isApplied = state.isApplied(id);

    const card = document.createElement('div');
    card.className = isKanban ? 'k-card' : 'product-card';
    if (isApplied && !isKanban) card.classList.add('applied');
    card.dataset.id = id;

    if (isKanban) {
        card.draggable = true;
        card.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', id);
            setTimeout(() => card.classList.add('dragging'), 0);
        });
        card.addEventListener('dragend', () => card.classList.remove('dragging'));
    }

    const companyName = job.Company || 'Unknown';
    
    // Feature 6: Comparison checkbox (only on list view)
    const isCompared = compareList.has(id);
    const compareHtml = !isKanban ? `<button class="btn-secondary compare-btn ${isCompared ? 'active' : ''}" data-id="${id}" title="Pilih untuk bandingkan" onclick="event.stopPropagation(); toggleCompare('${id}', this)"><span class="material-icons-round">compare_arrows</span></button>` : '';

    // Feature 3: Score Breakdown Tooltip
    let scoreClass = 'score-low';
    if (score >= 85) scoreClass = 'score-high';
    else if (score >= 75) scoreClass = 'score-medium';
    else if (score >= 60) scoreClass = 'score-medium';
    
    // Parse why match for tooltip
    const whyMatch = job['Why Match'] || '';
    const breakdownRows = whyMatch.split(';').map(row => row.trim()).filter(Boolean);
    const tooltipHtml = breakdownRows.length > 0 
        ? `<div class="score-tooltip">${breakdownRows.map(r => `<div>${r}</div>`).join('')}</div>`
        : '';

    const scoreHtml = !isKanban ? `
        <div class="score-badge ${scoreClass}">
            ${Math.round(score)}
            ${tooltipHtml}
        </div>
    ` : '';

    const industryMatch = whyMatch.match(/Industry match:\s([^;]+)/);
    const industryTag = industryMatch ? `<span class="tag">${industryMatch[1].trim()}</span>` : '';
    const aiTag = whyMatch.includes('[AI]') ? `<span class="tag">🤖 AI Evaluated</span>` : '';
    const appliedTag = isApplied && !isKanban ? `<span class="tag" style="background:var(--store-green-bg); color:var(--store-green);">✓ Applied</span>` : '';

    const salary = job['salary_ai_extracted'];
    const compEnc = encodeURIComponent(companyName);
    const titleEnc = encodeURIComponent(job['Job Title'] || 'Management Trainee');
    
    const salaryHtml = salary && salary !== '-' && salary !== 'Tidak tercantum'
        ? `<span><span class="material-icons-round">payments</span> <strong style="color:var(--store-green);">${salary}</strong></span>` 
        : `<span><span class="material-icons-round">payments</span> <a href="https://www.google.com/search?q=gaji+${titleEnc}+di+${compEnc}" target="_blank" style="color:var(--store-blue);text-decoration:none;" onclick="event.stopPropagation()">Cari Info Gaji ↗</a></span>`;
        
    const location = job.Location && job.Location !== 'Tidak tercantum' && job.Location !== '-' 
        ? `<span><span class="material-icons-round">location_on</span> ${job.Location}</span>` 
        : `<span><span class="material-icons-round">location_on</span> <a href="https://www.google.com/search?q=lokasi+kantor+${compEnc}" target="_blank" style="color:var(--store-blue);text-decoration:none;" onclick="event.stopPropagation()">Cari Lokasi ↗</a></span>`;

    // Feature 8: Quick Research
    const researchHtml = `
        <div class="quick-research">
            <a href="https://www.linkedin.com/search/results/companies/?keywords=${compEnc}" target="_blank" class="quick-btn" onclick="event.stopPropagation()">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg> LinkedIn
            </a>
            <a href="https://www.glassdoor.com/Search/results.htm?keyword=${compEnc}" target="_blank" class="quick-btn" onclick="event.stopPropagation()">
                <span class="material-icons-round" style="font-size:14px;">work</span> Glassdoor
            </a>
        </div>
    `;

    // Feature 4: Interview Countdown
    let countdownHtml = '';
    if (isKanban && state.getKanban()[id] === 'interview') {
        // Mock countdown logic based on apply_date (in real scenario, we'd have interview_date)
        const applyDate = serverState.apply_dates?.[id];
        if (applyDate) {
            const daysSinceApply = Math.floor((Date.now() - new Date(applyDate).getTime()) / (1000 * 60 * 60 * 24));
            // Simulate interview date is 14 days after apply
            const daysLeft = 14 - daysSinceApply;
            if (daysLeft > 0 && daysLeft <= 3) {
                countdownHtml = `<div class="countdown-badge countdown-danger">⏳ ${daysLeft} hari lagi</div>`;
            } else if (daysLeft > 3) {
                countdownHtml = `<div class="countdown-badge countdown-warning">⏳ ${daysLeft} hari lagi</div>`;
            }
        }
    }

    if (!isKanban) {
        card.innerHTML = `
            ${scoreHtml}
            <div class="p-company">${companyName}</div>
            <div class="p-title"><a href="${job.URL || '#'}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${job['Job Title'] || '—'}</a></div>
            <div class="p-meta">
                ${location}
                ${salaryHtml}
            </div>
            <div class="p-tags">${aiTag}${industryTag}${appliedTag}</div>
            <div class="p-reason">${whyMatch.replace(/;/g, ' • ')}</div>
            ${researchHtml}
            <div class="p-actions" style="margin-top:20px;">
                ${compareHtml}
                <button class="btn-primary apply-btn${isApplied ? ' applied' : ''}" data-id="${id}">${isApplied ? '✓ Sudah Apply' : 'Tandai Apply'}</button>
                <button class="btn-secondary hide-btn" data-id="${id}" title="Sembunyikan"><span class="material-icons-round">visibility_off</span></button>
            </div>
        `;

        card.querySelector('.apply-btn').addEventListener('click', e => {
            e.stopPropagation();
            const wasApplied = state.isApplied(id);
            if (!wasApplied && job.URL) window.open(job.URL, '_blank', 'noopener,noreferrer');
            const nowApplied = state.toggle(id);
            const btn = card.querySelector('.apply-btn');
            btn.classList.toggle('applied', nowApplied);
            btn.textContent = nowApplied ? '✓ Sudah Apply' : 'Tandai Apply';
            updateAppliedBadge();
        });
        
        card.querySelector('.hide-btn').addEventListener('click', e => {
            e.stopPropagation();
            state.hide(id);
            card.style.opacity = '0';
            setTimeout(() => card.remove(), 300);
        });

    } else {
        // Kanban Card Layout
        card.innerHTML = `
            <button class="remove-btn material-icons-round" data-id="${id}">close</button>
            <div class="k-company">${companyName}</div>
            <div class="k-title"><a href="${job.URL || '#'}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;" onclick="event.stopPropagation()">${job['Job Title'] || '—'}</a></div>
            ${countdownHtml}
            ${researchHtml}
            <div class="k-actions">
                <button class="k-action-btn" style="color:var(--store-blue);" onclick="openCoverLetterModal('${id}')">📝 Cover</button>
                <button class="k-action-btn" style="color:var(--store-orange);" onclick="openInterviewPrepModal('${id}')">🎤 Prep</button>
                <button class="k-action-btn" style="color:var(--store-green);" onclick="openResumePrepModal('${id}')">📄 CV</button>
            </div>
        `;

        card.querySelector('.remove-btn').addEventListener('click', e => {
            e.stopPropagation();
            state.setStatus(id, null);
            card.remove();
            renderKanban();
            updateAppliedBadge();
        });
    }

    return card;
}

// ===================== OVERVIEW =====================
function renderOverview() {
    const applied = state.appliedCount();
    const applyToday = allJobs.filter(isApplyToday).length;
    const strong = allJobs.filter(j => j._score >= 85).length;
    const good = allJobs.filter(j => j._score >= 75 && j._score < 85).length;
    const possible = allJobs.filter(j => j._score >= 60 && j._score < 75).length;

    const d = new Date(summaryData.finished_at || Date.now());
    const dateStr = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });

    // Feature 7: Apply Heatmap logic
    const dates = serverState.apply_dates || {};
    const heatData = {};
    Object.values(dates).forEach(dateStr => {
        if (!heatData[dateStr]) heatData[dateStr] = 0;
        heatData[dateStr]++;
    });

    let heatmapCells = '';
    const today = new Date();
    // Generate last 84 days (12 weeks)
    for (let i = 83; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(today.getDate() - i);
        const ymd = d.toISOString().split('T')[0];
        const count = heatData[ymd] || 0;
        let level = 0;
        if (count >= 4) level = 4;
        else if (count === 3) level = 3;
        else if (count === 2) level = 2;
        else if (count >= 1) level = 1;
        
        heatmapCells += `<div class="heatmap-cell" data-level="${level}" title="${d.toLocaleDateString('id-ID')}: ${count} lamaran"></div>`;
    }

    const container = el('overview-container');
    container.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon blue"><span class="material-icons-round">check_circle</span></div>
            <div class="stat-info">
                <h4>Sudah Apply</h4>
                <p>${applied}</p>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon green"><span class="material-icons-round">storage</span></div>
            <div class="stat-info">
                <h4>Total Discrape</h4>
                <p>${allJobs.length}</p>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background:var(--store-orange-bg);color:var(--store-orange);"><span class="material-icons-round">star</span></div>
            <div class="stat-info">
                <h4>Strong Match</h4>
                <p>${strong}</p>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background:var(--store-red-bg);color:var(--store-red);"><span class="material-icons-round">history</span></div>
            <div class="stat-info">
                <h4>Run Terakhir</h4>
                <p style="font-size:16px;">${dateStr}</p>
            </div>
        </div>
        
        <!-- Apply Heatmap -->
        <div class="heatmap-card">
            <h3 class="heatmap-title">Aktivitas Melamar</h3>
            <div class="heatmap-grid" style="display:grid; grid-template-rows: repeat(7, 1fr); grid-auto-flow: column; gap: 4px; overflow-x: auto;">
                ${heatmapCells}
            </div>
        </div>
    `;

    if(el('summary-bar')) el('summary-bar').textContent = `📊 Anda sudah apply ${applied} lowongan dari ${allJobs.length} yang tersedia.`;
    show('overview-container');
}

let chartInstances = {};

function renderInsights() {
    const container = el('insights-container');
    
    // Always render charts area
    let html = `
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px; margin-bottom:24px;">
            <div style="background:var(--store-surface); border-radius:16px; padding:24px; border:1px solid var(--store-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="margin-top:0; font-size:1.1rem; text-align:center;">Status Lamaran (Kanban)</h3>
                <div style="position:relative; height:250px; width:100%; display:flex; justify-content:center;">
                    <canvas id="kanbanChart"></canvas>
                </div>
            </div>
            <div style="background:var(--store-surface); border-radius:16px; padding:24px; border:1px solid var(--store-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="margin-top:0; font-size:1.1rem; text-align:center;">Top 5 Industri Dilamar</h3>
                <div style="position:relative; height:250px; width:100%;">
                    <canvas id="industryChart"></canvas>
                </div>
            </div>
        </div>
    `;

    if (!insightsData) {
        html += `
            <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 20px; text-align:center; background:var(--store-surface); border-radius:16px; border:1px dashed var(--store-border);">
                <span class="material-icons-round" style="font-size:48px; color:var(--store-text-muted); margin-bottom:16px;">analytics</span>
                <h3 style="margin-bottom:8px;">AI Market Insights Belum Tersedia</h3>
                <p style="color:var(--store-text-muted); max-width:400px; font-size:14px;">Jalankan scraper dengan argumen --powerful --use-ai untuk menghasilkan AI Market Insights.</p>
            </div>
        `;
    } else {
        let skillsHtml = insightsData.top_skills.map(s => `
            <div style="display:flex; justify-content:space-between; padding:12px 24px; border-bottom:1px solid var(--store-border); align-items:center;">
                <span style="font-weight:600; font-size:15px;">${s.skill}</span>
                <span class="chip ${s.demand === 'Tinggi' ? 'chip-fire' : 'chip-industry'}">${s.demand}</span>
            </div>
        `).join('');
        
        html += `
            <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:24px; margin-top:8px;">
                <div style="display:flex; flex-direction:column; gap:24px;">
                    <div style="background:var(--store-surface); border-radius:16px; padding:32px; border:1px solid var(--store-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <h3 style="margin-top:0; margin-bottom:16px; font-size:1.2rem; display:flex; align-items:center; gap:10px;"><span class="material-icons-round" style="color:var(--store-blue);">trending_up</span> Tren Perekrutan Terkini</h3>
                        <p style="color:var(--store-text-main); line-height:1.7; font-size:15px; margin:0;">${insightsData.hiring_trend_summary}</p>
                    </div>
                    
                    <div style="background:var(--store-surface); border-radius:16px; padding:32px; border:1px solid var(--store-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <h3 style="margin-top:0; margin-bottom:16px; font-size:1.2rem; display:flex; align-items:center; gap:10px;"><span class="material-icons-round" style="color:var(--store-green);">payments</span> Ekspektasi Gaji & Kompensasi</h3>
                        <p style="color:var(--store-green); font-weight:600; font-size:1.1rem; margin:0;">${insightsData.salary_insights}</p>
                    </div>
                </div>
                
                <div style="background:var(--store-surface); border-radius:16px; border:1px solid var(--store-border); overflow:hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); align-self:start;">
                    <div style="padding:20px 24px; background:var(--store-surface); border-bottom:1px solid var(--store-border);">
                        <h3 style="margin:0; font-size:1.1rem; display:flex; align-items:center; gap:8px;"><span class="material-icons-round" style="color:var(--store-blue); font-size:20px;">model_training</span> Top Skills Diminati</h3>
                    </div>
                    <div style="display:flex; flex-direction:column;">
                        ${skillsHtml}
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    show('insights-container');
    
    // Draw charts after DOM is updated
    setTimeout(drawCharts, 100);
}

function drawCharts() {
    if (typeof Chart === 'undefined') return;
    
    // Destroy existing charts to prevent overlaps
    Object.values(chartInstances).forEach(chart => chart.destroy());
    chartInstances = {};

    // 1. Kanban Doughnut Chart
    const kanban = state.getKanban();
    const statusCounts = { applied: 0, assessment: 0, interview: 0, result: 0 };
    Object.values(kanban).forEach(status => {
        if (statusCounts[status] !== undefined) statusCounts[status]++;
    });

    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDarkMode ? '#e2e8f0' : '#1e293b';

    Chart.defaults.color = textColor;
    Chart.defaults.font.family = "'Google Sans', sans-serif";

    const kanbanCtx = document.getElementById('kanbanChart');
    if (kanbanCtx) {
        chartInstances.kanban = new Chart(kanbanCtx, {
            type: 'doughnut',
            data: {
                labels: ['Applied', 'Assessment', 'Interview', 'Result'],
                datasets: [{
                    data: [statusCounts.applied, statusCounts.assessment, statusCounts.interview, statusCounts.result],
                    backgroundColor: ['#e2e8f0', '#fef08a', '#93c5fd', '#86efac'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right' } },
                cutout: '70%'
            }
        });
    }

    // 2. Top Industry Bar Chart
    const appliedIds = Object.keys(kanban);
    const appliedJobs = allJobs.filter(j => {
        const jId = slugify(j.Company + j['Job Title'] + j.Location);
        return appliedIds.includes(jId);
    });

    const industryCounts = {};
    appliedJobs.forEach(j => {
        const ind = j.Industry || 'Other';
        industryCounts[ind] = (industryCounts[ind] || 0) + 1;
    });

    const sortedInd = Object.entries(industryCounts).sort((a,b) => b[1]-a[1]).slice(0, 5);
    
    const industryCtx = document.getElementById('industryChart');
    if (industryCtx) {
        chartInstances.industry = new Chart(industryCtx, {
            type: 'bar',
            data: {
                labels: sortedInd.map(x => x[0].substring(0, 15) + (x[0].length>15?'...':'')),
                datasets: [{
                    label: 'Jumlah Lamaran',
                    data: sortedInd.map(x => x[1]),
                    backgroundColor: '#3b82f6',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } }
                }
            }
        });
    }
}
// ===================== TIMELINE =====================
function buildTimelineHtml(id) {
    const timeline = state.getTimeline()[id];
    if (!timeline || timeline.length === 0) return '';
    
    const statusEmoji = { applied: '📨', assessment: '📝', interview: '🎤', result: '🏆' };
    const items = timeline.slice(-3).map(e => {
        const d = new Date(e.date);
        const ds = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
        return `<span style="font-size:11px; color:var(--store-text-muted);">${statusEmoji[e.status] || '•'} ${ds}</span>`;
    }).join(' → ');
    
    const reminder = state.getReminders()[id];
    const reminderHtml = reminder ? `<span style="font-size:11px; color:var(--store-orange); font-weight:500;">⏰ ${reminder}</span>` : '';
    
    return `<div style="display:flex; flex-wrap:wrap; gap:4px; align-items:center; margin-bottom:8px; padding:6px 8px; background:var(--store-surface-hover); border-radius:8px;">${items} ${reminderHtml}</div>`;
}

// ===================== HELPERS =====================
function isApplyToday(j) {
    if (typeof j._isApplyToday !== 'undefined') return j._isApplyToday;
    const score = parseFloat(j.Score || j._score || 0);
    const rec = j.Recommendation || '';
    const conf = parseFloat(j.data_confidence || 0);
    const gpaStatus = j.gpa_status || '';
    const deadlineStatus = j.deadline_status || '';
    return (
        score >= 75 &&
        conf >= 60 &&
        (rec === 'Apply' || rec === 'Apply / Maybe') &&
        gpaStatus !== 'High GPA Gap' &&
        deadlineStatus !== 'Expired'
    );
}

function updateSummaryBar(jobs, tab) {
    const bar = el('summary-text');
    if (!bar) return;
    
    if (tab === 'apply-today') {
        bar.textContent = jobs.length > 0
            ? `Menampilkan ${jobs.length} rekomendasi terbaik hari ini dengan skor ≥ 75`
            : 'Tidak ada lowongan prioritas hari ini.';
    } else if (tab === 'browse') {
        bar.textContent = `Menampilkan ${jobs.length} lowongan dari total ${allJobs.length} posisi yang tersedia`;
    } else if (tab === 'tracker') {
        let totalVisibleKanban = 0;
        document.querySelectorAll('.kanban-column .kanban-cards').forEach(cardsContainer => {
            totalVisibleKanban += cardsContainer.querySelectorAll('.k-card').length;
        });
        bar.textContent = totalVisibleKanban > 0
            ? `Anda memiliki ${totalVisibleKanban} lamaran di papan Kanban.`
            : 'Belum ada lamaran tersimpan dengan kriteria ini. Mulai eksplorasi sekarang.';
    }
}

function updateAppliedBadge() {
    if (!el('applied-count')) return;
    if (currentTab === 'tracker') {
        let totalVisibleKanban = 0;
        document.querySelectorAll('.kanban-column .kanban-cards').forEach(cardsContainer => {
            totalVisibleKanban += cardsContainer.querySelectorAll('.k-card').length;
        });
        el('applied-count').textContent = totalVisibleKanban;
    } else {
        el('applied-count').textContent = state.appliedCount();
    }
}

function showError() {
    hide('loading-state');
    show('error-state');
    if(el('summary-bar')) el('summary-bar').textContent = '⚠️ Gagal memuat data. Pastikan output/latest/jobs_ranked.csv ada.';
}

function el(id) { return document.getElementById(id); }
function show(id) { el(id)?.classList.remove('hidden'); }
function hide(id) { el(id)?.classList.add('hidden'); }

function slugify(str) {
    return (str || '').toLowerCase().replace(/[^a-z0-9]/g, '').substring(0, 80);
}

function getInitials(name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
}

function avatarColor(name) {
    const palettes = [
        { bg: '#e0e7ff', fg: '#3730a3' }, { bg: '#fce7f3', fg: '#9d174d' },
        { bg: '#d1fae5', fg: '#065f46' }, { bg: '#fef3c7', fg: '#92400e' },
        { bg: '#dbeafe', fg: '#1e40af' }, { bg: '#ede9fe', fg: '#5b21b6' },
        { bg: '#fee2e2', fg: '#991b1b' }, { bg: '#e0f2fe', fg: '#0c4a6e' },
        { bg: '#f0fdf4', fg: '#14532d' }, { bg: '#fdf4ff', fg: '#701a75' },
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return palettes[Math.abs(hash) % palettes.length];
}

const logoCache = {};
async function loadCompanyLogo(companyName, imgEl, initialsEl) {
    let query = companyName.toLowerCase();
    query = query.replace(/\b(pt|tbk|cv|ltd|inc|group|corp|corporation|indonesia|persero)\b\.?/g, '').trim();
    if (!query) return;

    if (logoCache[query] === 'failed') return;
    if (logoCache[query]) {
        imgEl.src = logoCache[query];
        imgEl.onload = () => { imgEl.style.display = 'block'; initialsEl.style.display = 'none'; };
        return;
    }

    try {
        const res = await fetch(`https://autocomplete.clearbit.com/v1/companies/suggest?query=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('Net err');
        const data = await res.json();
        
        if (data && data.length > 0 && data[0].logo) {
            logoCache[query] = data[0].logo;
            imgEl.src = data[0].logo;
            imgEl.onload = () => { imgEl.style.display = 'block'; initialsEl.style.display = 'none'; };
        } else {
            logoCache[query] = 'failed';
        }
    } catch (error) {
        logoCache[query] = 'failed';
    }
}

window.editNote = function(id) {
    const current = state.getNotes()[id] || '';
    const text = prompt('Catatan Pribadi untuk lowongan ini:', current);
    if (text !== null) {
        state.setNote(id, text);
        renderTab(currentTab);
    }
};

// ===================== COMPARISON MODE =====================
let compareList = new Set();

window.toggleCompare = function(id, btnEl) {
    if (compareList.has(id)) {
        compareList.delete(id);
        if(btnEl) btnEl.classList.remove('active');
    } else {
        if (compareList.size >= 3) {
            alert('Maksimal 3 lowongan untuk dibandingkan.');
            return;
        }
        compareList.add(id);
        if(btnEl) btnEl.classList.add('active');
    }
    
    const bar = el('comparison-bar');
    if (compareList.size >= 2) {
        bar.classList.remove('hidden');
        el('compare-count').textContent = `${compareList.size} terpilih`;
    } else {
        bar.classList.add('hidden');
    }
};

el('compare-clear').addEventListener('click', () => {
    compareList.clear();
    document.querySelectorAll('.compare-btn').forEach(btn => btn.classList.remove('active'));
    el('comparison-bar').classList.add('hidden');
});

el('compare-btn').addEventListener('click', () => {
    const jobs = Array.from(compareList).map(id => allJobs.find(j => j._id === id));
    
    let thead = '<tr><th>Aspek</th>' + jobs.map(j => `<th>${j.Company}</th>`).join('') + '</tr>';
    
    const rows = [
        ['Posisi', j => j['Job Title']],
        ['Skor', j => `<strong style="color:var(--store-blue);">${Math.round(j._score)}</strong>`],
        ['Lokasi', j => j.Location],
        ['Gaji (AI)', j => j.salary_ai_extracted || '-'],
        ['Industri', j => {
            const m = (j['Why Match']||'').match(/Industry match:\s([^;]+)/);
            return m ? m[1] : '-';
        }]
    ];
    
    let tbody = rows.map(row => {
        return `<tr><td style="font-weight:600;">${row[0]}</td>` + 
               jobs.map(j => `<td>${row[1](j)}</td>`).join('') + 
               '</tr>';
    }).join('');
    
    el('compare-table-container').innerHTML = `
        <table style="width:100%; border-collapse: collapse; text-align:left;">
            <thead style="border-bottom:2px solid var(--store-border);">${thead}</thead>
            <tbody>${tbody}</tbody>
        </table>
        <style>
            #compare-table-container th, #compare-table-container td { padding: 12px; border-bottom: 1px solid var(--store-border); }
        </style>
    `;
    
    show('compare-modal');
});

window.closeCompareModal = function() {
    hide('compare-modal');
};

function initCustomDropdowns() {
    // Remove any existing custom select wrappers to prevent duplicate renders
    document.querySelectorAll('.custom-select-wrapper').forEach(w => w.remove());

    const selects = document.querySelectorAll('.store-select');
    selects.forEach(select => {
        // Hide the original native select
        select.style.display = 'none';

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select-wrapper';
        
        // Trigger button
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        
        const textSpan = document.createElement('span');
        const selectedOpt = select.options[select.selectedIndex];
        textSpan.textContent = selectedOpt ? selectedOpt.textContent : select.placeholder || '';
        
        const arrow = document.createElement('span');
        arrow.className = 'material-icons-round';
        arrow.style.fontSize = '18px';
        arrow.style.transition = 'transform 0.2s';
        arrow.textContent = 'expand_more';
        
        trigger.appendChild(textSpan);
        trigger.appendChild(arrow);
        wrapper.appendChild(trigger);
        
        // Options container
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'custom-select-options';
        
        Array.from(select.options).forEach(opt => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'custom-option';
            if (opt.selected) optionDiv.classList.add('selected');
            optionDiv.textContent = opt.textContent;
            
            optionDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                // Remove selected class from all options
                optionsContainer.querySelectorAll('.custom-option').forEach(o => o.classList.remove('selected'));
                optionDiv.classList.add('selected');
                
                // Update selected text and trigger change event on native select
                textSpan.textContent = opt.textContent;
                select.value = opt.value;
                select.dispatchEvent(new Event('change'));
                
                // Close dropdown
                wrapper.classList.remove('open');
                arrow.style.transform = 'rotate(0deg)';
            });
            
            optionsContainer.appendChild(optionDiv);
        });
        
        wrapper.appendChild(optionsContainer);
        
        // Toggle on trigger click
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close other custom dropdowns
            document.querySelectorAll('.custom-select-wrapper').forEach(w => {
                if (w !== wrapper) {
                    w.classList.remove('open');
                    const otherArrow = w.querySelector('.material-icons-round');
                    if (otherArrow) otherArrow.style.transform = 'rotate(0deg)';
                }
            });
            
            const isOpen = wrapper.classList.contains('open');
            wrapper.classList.toggle('open');
            arrow.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
        });
        
        // Insert wrapper right after native select
        select.parentNode.insertBefore(wrapper, select.nextSibling);
    });
}

// Close dropdown on click outside
document.addEventListener('click', () => {
    document.querySelectorAll('.custom-select-wrapper').forEach(w => {
        w.classList.remove('open');
        const arrow = w.querySelector('.material-icons-round');
        if (arrow) arrow.style.transform = 'rotate(0deg)';
    });
});
