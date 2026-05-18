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

let serverState = { kanban: {}, hidden: {}, notes: {} };

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
        } else { delete k[id]; }
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
                    _score: parseFloat(j.Score || j['match_score'] || 0),
                    _isApplyToday: !j['not_apply_today_reason'] || j['not_apply_today_reason'].trim() === '',
                    _id: slugify((j.Company || '') + (j['Job Title'] || '') + (j.Location || ''))
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
    if(el('run-date-sidebar')) el('run-date-sidebar').textContent = dateStr;

    const applyTodayJobs = allJobs.filter(isApplyToday);
    if(el('all-count')) el('all-count').textContent = allJobs.length;
    if(el('apply-today-count')) el('apply-today-count').textContent = applyTodayJobs.length;

    populateFilters();
    renderTab();
    updateAppliedBadge();
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
    
    Object.keys(kanbanData).forEach(id => {
        const status = kanbanData[id];
        const job = allJobs.find(j => j._id === id);
        if (job) {
            const card = buildCard(job, 0, true);
            const col = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-cards`);
            if (col) col.appendChild(card);
        }
    });
    
    document.querySelectorAll('.kanban-column').forEach(col => {
        const count = col.querySelectorAll('.job-card').length;
        if(col.querySelector('.k-count')) col.querySelector('.k-count').textContent = count;
        
        // Add collapse toggle if not already present
        const header = col.querySelector('.kanban-header');
        if (header && !header.querySelector('.k-toggle')) {
            const btn = document.createElement('button');
            btn.className = 'k-toggle';
            btn.innerHTML = '<span class="material-icons-round" style="font-size:18px;">expand_less</span>';
            btn.style.cssText = 'background:none; border:none; cursor:pointer; color:var(--store-text-muted); padding:4px; border-radius:50%; display:flex;';
            btn.addEventListener('click', () => {
                const cards = col.querySelector('.kanban-cards');
                const icon = btn.querySelector('.material-icons-round');
                if (cards.style.display === 'none') {
                    cards.style.display = '';
                    icon.textContent = 'expand_less';
                } else {
                    cards.style.display = 'none';
                    icon.textContent = 'expand_more';
                }
            });
            header.appendChild(btn);
        }
    });
}

window.dropKanban = function(event, status) {
    event.preventDefault();
    const id = event.dataTransfer.getData('text/plain');
    if (id) {
        state.setStatus(id, status);
        // If moved to interview, prompt for reminder
        if (status === 'interview') {
            const job = allJobs.find(j => j._id === id);
            const dt = prompt(`Kapan jadwal interview ${job ? job.Company : ''}?\n(Format: 2026-05-20 09:00)`);
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

// ===================== BUILD CARD =====================
function buildCard(job, displayRank, isKanban) {
    const score = job._score;
    const id = job._id;
    const isApplied = state.isApplied(id);

    const card = document.createElement('div');
    card.className = `job-card${isApplied && !isKanban ? ' applied' : ''}`;
    card.dataset.id = id;

    if (isKanban) {
        card.draggable = true;
        card.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', id);
            setTimeout(() => card.style.opacity = '0.5', 0);
        });
        card.addEventListener('dragend', () => card.style.opacity = '1');
    }

    const companyName = job.Company || 'Unknown';
    const initials = getInitials(companyName);
    const { bg, fg } = avatarColor(companyName);

    const scoreClass = score >= 85 ? 'strong' : score >= 75 ? 'good' : score >= 60 ? 'possible' : score >= 45 ? 'weak' : 'skip';

    const indMatch = (job['Why Match'] || '').match(/Industry match:\s([^;]+)/);
    const industryTag = indMatch ? `<span class="chip chip-industry">${indMatch[1].trim()}</span>` : '';

    const applyTodayTag = isApplyToday(job) && !isKanban ? `<span class="chip chip-fire">🔥 Apply today</span>` : '';
    const appliedTag = isApplied && !isKanban ? `<span class="chip chip-applied">✓ Applied</span>` : '';
    
    const hasAI = job['Why Match'] && job['Why Match'].includes('[AI]');
    const aiTag = hasAI ? `<span class="chip chip-ai">🤖 AI</span>` : '';

    const salary = job['salary_ai_extracted'];
    const salaryHtml = salary ? `<span class="meta-divider">·</span><span class="meta-location" style="color:var(--store-green); font-weight:500;">${salary}</span>` : '';
    const location = job.Location && job.Location !== 'Tidak tercantum' ? `📍 ${job.Location}` : '';

    card.innerHTML = `
        ${!isKanban ? `<button class="hide-btn material-icons-round" title="Sembunyikan" data-id="${id}">close</button>` : `<button class="hide-btn material-icons-round" title="Hapus dari Kanban" style="color:#d93025;" data-id="${id}">delete</button>`}
        <div class="company-avatar" style="background:${bg};color:${fg}; position: relative; overflow: hidden;">
            <div class="initials" style="display:flex; align-items:center; justify-content:center; width:100%; height:100%;">${initials}</div>
            <img class="real-logo" src="" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; background:white; display:none; padding:8px;" alt="Logo">
        </div>
        <div class="card-title">
            <a href="${job.URL || '#'}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${job['Job Title'] || '—'}</a>
        </div>
        <div class="card-meta">
            <span class="meta-company">${job.Company || '—'}</span>
            ${location ? `<span class="meta-divider">·</span><span class="meta-location">${location}</span>` : ''}
            ${salaryHtml}
        </div>
        <div class="card-tags">
            ${aiTag}${industryTag}${applyTodayTag}${appliedTag}
        </div>
        ${isKanban ? buildTimelineHtml(id) : ''}
        <div class="card-footer">
            <div class="score-price ${scoreClass}">
                <span class="label">Score</span>
                ${Math.round(score)}
            </div>
            ${isKanban 
                ? `<div style="display:flex; gap:6px; flex-wrap:wrap;">
                     <button class="apply-btn chip-ai" style="padding:5px 10px; font-size:12px; width:auto;" onclick="openCoverLetterModal('${id}')">📝 Lamaran</button>
                     <button class="apply-btn" style="padding:5px 10px; font-size:12px; width:auto; border-color:var(--store-orange); color:var(--store-orange);" onclick="openInterviewPrepModal('${id}')">🎤 Interview</button>
                     <button class="apply-btn" style="padding:5px 10px; font-size:12px; width:auto; border-color:var(--store-green); color:var(--store-green);" onclick="openResumePrepModal('${id}')">📄 Bedah CV</button>
                   </div>`
                : `<button class="apply-btn${isApplied ? ' applied' : ''}" data-id="${id}">${isApplied ? '✓ Sudah Apply' : 'Tandai Apply'}</button>`
            }
        </div>
    `;

    if (!isKanban) {
        card.querySelector('.apply-btn').addEventListener('click', e => {
            e.stopPropagation();
            const wasApplied = state.isApplied(id);
            if (!wasApplied && job.URL) window.open(job.URL, '_blank', 'noopener,noreferrer');

            const nowApplied = state.toggle(id);
            const btn = card.querySelector('.apply-btn');
            btn.classList.toggle('applied', nowApplied);
            btn.textContent = nowApplied ? '✓ Sudah Apply' : 'Tandai Apply';
            card.classList.toggle('applied', nowApplied);
            updateAppliedBadge();
        });
        
        card.querySelector('.hide-btn').addEventListener('click', e => {
            e.stopPropagation();
            state.hide(id);
            card.style.transition = 'opacity 0.3s, transform 0.3s';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9)';
            setTimeout(() => card.remove(), 300);
        });
    } else {
        card.querySelector('.hide-btn').addEventListener('click', e => {
            e.stopPropagation();
            state.setStatus(id, null);
            card.remove();
            renderKanban();
            updateAppliedBadge();
        });
    }

    loadCompanyLogo(companyName, card.querySelector('.real-logo'), card.querySelector('.initials'));
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

    const container = el('overview-container');
    container.innerHTML = `
        <div class="stat-card applied-stat">
            <div class="stat-label">Sudah Apply</div>
            <div class="stat-value">${applied}</div>
            <div class="stat-desc">lowongan yang Anda lamar</div>
        </div>
        <div class="stat-card default">
            <div class="stat-label">Total Discrape</div>
            <div class="stat-value">${allJobs.length}</div>
            <div class="stat-desc">lowongan unik ditemukan</div>
        </div>
        <div class="stat-card good">
            <div class="stat-label">Apply Today</div>
            <div class="stat-value">${applyToday}</div>
            <div class="stat-desc">rekomendasi lamar hari ini</div>
        </div>
        <div class="stat-card strong">
            <div class="stat-label">Strong Match</div>
            <div class="stat-value">${strong}</div>
            <div class="stat-desc">skor ≥ 85 pts</div>
        </div>
        <div class="stat-card good">
            <div class="stat-label">Good Match</div>
            <div class="stat-value">${good}</div>
            <div class="stat-desc">skor 75–84 pts</div>
        </div>
        <div class="stat-card possible">
            <div class="stat-label">Possible Match</div>
            <div class="stat-value">${possible}</div>
            <div class="stat-desc">skor 60–74 pts</div>
        </div>
        <div class="overview-section-title">Info Scraping</div>
        <div class="stat-card default">
            <div class="stat-label">Run Terakhir</div>
            <div class="stat-value" style="font-size:1.1rem;line-height:1.3">${dateStr}</div>
            <div class="stat-desc">${summaryData.run_id || '—'}</div>
        </div>
        <div class="stat-card default">
            <div class="stat-label">Links Discovered</div>
            <div class="stat-value">${summaryData.total_links_discovered || 0}</div>
            <div class="stat-desc">total dari semua sumber</div>
        </div>
        <div class="stat-card default">
            <div class="stat-label">Duplikat Dihapus</div>
            <div class="stat-value">${summaryData.duplicates_removed || 0}</div>
            <div class="stat-desc">setelah deduplication</div>
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
        bar.textContent = state.appliedCount() > 0
            ? `Anda memiliki ${state.appliedCount()} lamaran di papan Kanban.`
            : 'Belum ada lamaran tersimpan. Mulai eksplorasi sekarang.';
    }
}

function updateAppliedBadge() {
    if(el('applied-count')) el('applied-count').textContent = state.appliedCount();
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
