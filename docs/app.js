// ── analytics helper ──────────────────────────────────────────────────────
function track(event, category, action, label, detail) {
  const params = { category, action };
  if (label) params.label = label;
  if (detail) params.detail = detail;
  gtag('event', event, params);
}

// SVG icons
const ICON_GLOBE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
const ICON_SCHOLAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>`;
const ICON_PROGRAM = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`;
const ICON_CATALOG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
const ICON_PERSON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_BOOK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`;

// ── column tooltips ───────────────────────────────────────────────────────
const COL_TOOLTIPS = {
  citedby:    'Total citations received',
  citedby5y:  'Citations received in the past 5 years',
  hindex:     'Largest h where h papers each have ≥ h citations',
  hindex5y:   'h-index computed over the past 5 years',
  i10index:   'Number of papers with at least 10 citations',
  i10index5y: 'Papers with ≥ 10 citations in the past 5 years',
};

// ── column definitions ─────────────────────────────────────────────────────
const COLLEGE_COLS = [
  { key: 'name',             label: 'Institution',   numeric: false },
  { key: 'total',            label: 'Faculty',       numeric: true, tooltip: 'Number of faculty' },
  { key: 'total_citations',  label: 'Citations',     numeric: true, tooltip: 'Total citations received' },
  { key: 'courses_per_year', label: 'Courses',  numeric: true, tooltip: 'Number of unique courses offered in the last academic year' },
];

const FAC_COLS = [
  { key: 'name',       label: 'Name',      numeric: false },
  { key: 'title',      label: 'Title',     numeric: false },
  { key: 'citedby',    label: 'Cites',     numeric: true },
  { key: 'citedby5y',  label: 'Cites 5yr', numeric: true },
  { key: 'hindex',     label: 'h-index',   numeric: true },
  { key: 'hindex5y',   label: 'h5-index',   numeric: true },
  { key: 'i10index',   label: 'i10-index', numeric: true },
  { key: 'i10index5y', label: 'i10-5yr',   numeric: true },
];

// ── filter categories ──────────────────────────────────────────────────────
const CATEGORIES = [
  { key: 'tenured',      label: 'Tenured'      },
  { key: 'tenure_track', label: 'Tenure-track' },
  { key: 'teaching',     label: 'Teaching'     },
  { key: 'visiting',     label: 'Visiting'     },
  { key: 'adjunct',      label: 'Adjunct'      },
];

// CS subfields — mirrors CS_SUBFIELD_NAMES in scraper/faculty_site_analysis.py
const CS_SUBFIELDS = [
  'Artificial intelligence', 'Computer vision', 'Machine learning',
  'Natural language processing', 'Data science', 'Information retrieval',
  'Computer architecture', 'Computer networks', 'Distributed systems',
  'Computer security & privacy', 'Databases', 'Design automation',
  'Embedded & real-time systems', 'High-performance computing',
  'Mobile computing', 'Measurement & performance analysis',
  'Operating systems', 'Programming languages', 'Software engineering',
  'Algorithms & complexity', 'Quantum computing', 'Cryptography',
  'Logic & verification', 'Computational bio & bioinformatics',
  'Computer graphics', 'Computer science education',
  'Economics & computation', 'Human-computer interaction', 'Robotics',
  'Visualization', 'Computational social science', 'Games & interactive art',
];

// Slugifies a college name into the CSS class used by img/logo_sprite.css
// (e.g. "St. Mary's College of Maryland" -> "st-mary-s-college-of-maryland").
// Must match slug() in docs/generate_logo_sprite.py.
function collegeSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// ── state ──────────────────────────────────────────────────────────────────
let allColleges = [];
let collegeLinks = {};
let courseSchedules = {};
let collegeSort = { key: 'total', dir: -1 };
let activeCategories = new Set();
let activeSubfields = new Set();
let excludedSubfields = new Set();
let subfieldScope = 'faculty'; // 'faculty' | 'school'
let activeState = '';
let advancedExpanded = false;
let searchQuery = '';
let searchDraft = '';
let searchTimer = null;
let expandAllOn = false;

// USPS state/territory codes → full names. Used by the advanced state filter.
const US_STATES = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', DC: 'District of Columbia',
  FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois',
  IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana',
  ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota',
  MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada',
  NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York',
  NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon',
  PA: 'Pennsylvania', PR: 'Puerto Rico', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};

// ── theme ──────────────────────────────────────────────────────────────────
const html = document.documentElement;
const savedTheme = localStorage.getItem('theme') || 'light';
html.setAttribute('data-theme', savedTheme);

document.getElementById('theme-btn').addEventListener('click', () => {
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
});

// ── data ───────────────────────────────────────────────────────────────────
function loadSpriteImage() {
  return new Promise(resolve => {
    const img = new Image();
    img.onload = img.onerror = () => resolve();
    img.src = 'img/logo_sprite.webp';
  });
}

async function loadData() {
  const [dataRes] = await Promise.all([
    fetch('data.json'),
    loadSpriteImage(),
  ]);
  const merged = await dataRes.json();
  // Split the merged per-college map back into the three structures the
  // rendering code expects.
  allColleges = [];
  collegeLinks = {};
  courseSchedules = {};
  for (const [name, d] of Object.entries(merged)) {
    allColleges.push({
      name,
      faculty: d.faculty || [],
      total: d.total || 0,
      matched: d.matched || 0,
      total_citations: d.total_citations || 0,
    });
    collegeLinks[name] = {
      state: d.state ?? null,
      program_url: d.program_url ?? null,
      faculty_url: d.faculty_url ?? null,
      catalog_url: d.catalog_url ?? null,
      schedule_url: d.schedule_url ?? null,
    };
    if (d.terms) {
      courseSchedules[name] = { terms: d.terms, courses: d.courses };
    }
  }

  // Precompute a normalized lookup of each faculty's interests so the
  // subfield filter can match in O(1) per chip.
  for (const c of allColleges) {
    const collegeLc = c.name.toLowerCase();
    for (const f of c.faculty) {
      f._interestsSet = new Set(
        (f.interests || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
      );
      f._search = [f.name, f.title, f.interests, c.name]
        .filter(Boolean).join(' ').toLowerCase();
    }
    c._search = collegeLc;
    c.courses_per_year = coursesInLatestYear(courseSchedules[c.name]);
  }

  buildCollegeHeaders();
  buildFilterBar();
  buildAdvancedBar();
  renderAll();

  document.getElementById('loading-spinner').hidden = true;
  document.getElementById('table-wrap').hidden = false;

  updateHeaderH();
}

// Keep --header-h on :root in sync with the main column-header height, and
// --summary-h scoped to each .college-row in sync with that row's own summary
// height. Per-row scoping matters because on narrow viewports the college
// name may wrap to two lines, so summaries don't all share one height — we
// want each row's fac-head-row to stick directly under its own summary.
//
// Math.floor(getBoundingClientRect().height) under-measures by a sub-pixel
// when the rendered height is fractional, ensuring each subsequent sticky
// element's top sits at or slightly above the previous element's actual
// bottom. The (sub-pixel) overlap is hidden by the higher-z-index element
// above; without it, offsetHeight's rounding could leave a tiny gap through
// which scrolling table content shows.
function measureH(el) {
  return Math.floor(el.getBoundingClientRect().height) + 'px';
}

function updateHeaderH() {
  const row = document.querySelector('.col-head-row');
  if (row) {
    document.documentElement.style.setProperty('--header-h', measureH(row));
  }
  document.querySelectorAll('.college-row').forEach(updateRowVars);
}

// Sticky offsets for each row's fac-head-row / course thead depend on the
// actual rendered heights of the summary above them and the panel-toggle
// (when present). Both are scoped per .college-row.
function updateRowVars(r) {
  const s = r.querySelector('.college-summary');
  if (s) r.style.setProperty('--summary-h', measureH(s));
  const t = r.querySelector('.panel-toggle');
  r.style.setProperty('--toggle-h', t ? measureH(t) : '0px');
}
window.addEventListener('resize', updateHeaderH);
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(updateHeaderH);
}

// ── filter bar ─────────────────────────────────────────────────────────────
function categoryCounts() {
  const counts = Object.fromEntries(CATEGORIES.map(c => [c.key, 0]));
  for (const college of allColleges) {
    for (const f of college.faculty) {
      if (counts[f.category] != null) counts[f.category] += 1;
    }
  }
  return counts;
}

function buildFilterBar() {
  const bar = document.getElementById('filter-bar');
  const counts = categoryCounts();
  const expandLabel = expandAllOn ? 'Collapse all' : 'Expand all';
  const expandIcon = expandAllOn
    ? `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,7 6,3 10,7"/></svg>`
    : `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,5 6,9 10,5"/></svg>`;
  const advIcon = advancedExpanded
    ? `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,7 6,3 10,7"/></svg>`
    : `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,5 6,9 10,5"/></svg>`;
  const advTotal = activeSubfields.size + excludedSubfields.size + (activeState ? 1 : 0);
  const advCount = advTotal > 0 ? ` (${advTotal})` : '';
  const advActive = (advancedExpanded || advTotal > 0) ? 'active' : '';

  // Preserve focus + caret position on the search input across rebuilds
  // (chip clicks call buildFilterBar(), which would otherwise blow it away).
  const prevSearch = document.getElementById('search-input');
  const searchHadFocus = prevSearch && document.activeElement === prevSearch;
  const searchCaret = searchHadFocus
    ? [prevSearch.selectionStart, prevSearch.selectionEnd]
    : null;

  bar.innerHTML =
    `<span class="filter-label">Show</span>` +
    CATEGORIES.map(c => {
      const on = activeCategories.has(c.key);
      return `<button class="filter-chip ${on ? 'active' : ''}" data-cat="${c.key}">
        ${c.label}<span class="filter-chip-count">${counts[c.key]}</span>
      </button>`;
    }).join('') +
    `<span class="filter-spacer"></span>` +
    `<input type="text" class="search-input" id="search-input" placeholder="Search…"
      aria-label="Search faculty" value="${esc(searchDraft)}" />` +
    `<button class="expand-toggle ${advActive}" id="advanced-toggle">${advIcon}Advanced filter${advCount}</button>` +
    `<button class="expand-toggle" id="expand-toggle">${expandIcon}${expandLabel}</button>`;

  if (searchHadFocus) {
    const el = document.getElementById('search-input');
    el.focus();
    try { el.setSelectionRange(searchCaret[0], searchCaret[1]); } catch (_) {}
  }

  bar.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const k = btn.dataset.cat;
      const wasActive = activeCategories.has(k);
      if (wasActive) activeCategories.delete(k);
      else activeCategories.add(k);
      track('filter', 'category', wasActive ? 'clear' : 'include', k);
      buildFilterBar();
      renderAll();
    });
  });

  document.getElementById('expand-toggle').addEventListener('click', toggleExpandAll);
  document.getElementById('advanced-toggle').addEventListener('click', () => {
    advancedExpanded = !advancedExpanded;
    track('toggle_advanced', 'advanced', advancedExpanded ? 'expand' : 'collapse');
    document.getElementById('advanced-bar').classList.toggle('collapsed', !advancedExpanded);
    buildFilterBar();
  });
  const searchEl = document.getElementById('search-input');
  const commitSearch = () => {
    clearTimeout(searchTimer);
    searchTimer = null;
    if (searchQuery !== searchDraft) {
      searchQuery = searchDraft;
      if (searchQuery) track('filter', 'search', 'search', searchQuery);
      renderAll();
    }
  };
  searchEl.addEventListener('input', e => {
    searchDraft = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(commitSearch, 1000);
  });
  searchEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitSearch();
    }
  });
}

// ── advanced (subfield) filter bar ────────────────────────────────────────
function subfieldCounts() {
  const counts = Object.fromEntries(CS_SUBFIELDS.map(s => [s, 0]));
  const perSchool = subfieldScope === 'school';
  for (const c of allColleges) {
    const seen = perSchool ? new Set() : null;
    for (const f of c.faculty) {
      for (const s of CS_SUBFIELDS) {
        if (!f._interestsSet.has(s.toLowerCase())) continue;
        if (perSchool) {
          if (!seen.has(s)) { counts[s] += 1; seen.add(s); }
        } else {
          counts[s] += 1;
        }
      }
    }
  }
  return counts;
}

function buildAdvancedBar() {
  const bar = document.getElementById('advanced-bar');
  const counts = subfieldCounts();
  const hasAny = activeSubfields.size > 0 || excludedSubfields.size > 0;
  const clearBtn = hasAny
    ? `<button class="filter-chip" id="subfield-clear">Clear</button>`
    : '';
  const scopeHint = subfieldScope === 'faculty'
    ? `Apply to <span class="hint-scope">each faculty</span> — only show people whose interests match.`
    : `Apply to <span class="hint-scope">whole schools</span> — only show schools that have such faculty.`;
  const interactHint = `Click to <span class="hint-include">include</span>, again to <span class="hint-exclude">exclude</span>, once more to clear.`;
  const sortedSubfields = [...CS_SUBFIELDS].sort((a, b) => a.localeCompare(b));

  // Build state-dropdown options from states actually present in the dataset,
  // sorted alphabetically by full name.
  const presentStates = new Set();
  for (const c of allColleges) {
    const code = collegeLinks[c.name]?.state;
    if (code && US_STATES[code]) presentStates.add(code);
  }
  const sortedStates = [...presentStates].sort((a, b) => US_STATES[a].localeCompare(US_STATES[b]));
  const stateOptions = `<option value="">All states</option>` +
    sortedStates.map(code => {
      const sel = code === activeState ? ' selected' : '';
      return `<option value="${esc(code)}"${sel}>${esc(US_STATES[code])}</option>`;
    }).join('');

  bar.innerHTML =
    `<div class="adv-row adv-row-scope">
       <span class="filter-label">Scope</span>
       <div class="scope-toggle" role="tablist" aria-label="Filter scope">
         <button data-scope="faculty" class="${subfieldScope === 'faculty' ? 'active' : ''}" role="tab" aria-selected="${subfieldScope === 'faculty'}">Faculty</button>
         <button data-scope="school"  class="${subfieldScope === 'school'  ? 'active' : ''}" role="tab" aria-selected="${subfieldScope === 'school'}">School</button>
       </div>
       <span class="adv-hint-inline">${scopeHint}</span>
     </div>` +
    `<div class="adv-row adv-row-state">
       <span class="filter-label">State</span>
       <select class="state-select ${activeState ? 'active' : ''}" id="state-select" aria-label="Filter by state">
         ${stateOptions}
       </select>
     </div>` +
    `<div class="adv-row adv-row-subfields">
       <span class="filter-label">Subfields</span>` +
       sortedSubfields.map(s => {
         const cls = activeSubfields.has(s) ? 'active'
           : excludedSubfields.has(s) ? 'exclude'
           : '';
         return `<button class="filter-chip ${cls}" data-subfield="${esc(s)}">
           ${esc(s)}<span class="filter-chip-count">${counts[s]}</span>
         </button>`;
       }).join('') +
       clearBtn +
    `</div>` +
    `<div class="adv-row"><span class="adv-hint-inline">${interactHint}</span></div>`;

  bar.querySelectorAll('.filter-chip[data-subfield]').forEach(btn => {
    btn.addEventListener('click', () => {
      const k = btn.dataset.subfield;
      let action;
      // tri-state cycle: off → include → exclude → off
      if (activeSubfields.has(k)) {
        activeSubfields.delete(k);
        excludedSubfields.add(k);
        action = 'exclude';
      } else if (excludedSubfields.has(k)) {
        excludedSubfields.delete(k);
        action = 'clear';
      } else {
        activeSubfields.add(k);
        action = 'include';
      }
      track('filter', 'subfield', action, k);
      buildAdvancedBar();
      buildFilterBar();
      renderAll();
    });
  });

  const clearEl = document.getElementById('subfield-clear');
  if (clearEl) clearEl.addEventListener('click', () => {
    activeSubfields.clear();
    excludedSubfields.clear();
    buildAdvancedBar();
    buildFilterBar();
    renderAll();
  });

  bar.querySelectorAll('.scope-toggle button').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.scope;
      if (next === subfieldScope) return;
      subfieldScope = next;
      track('filter', 'scope', 'switch', next);
      buildAdvancedBar();
      buildFilterBar();
      renderAll();
    });
  });

  const stateEl = document.getElementById('state-select');
  if (stateEl) stateEl.addEventListener('change', () => {
    activeState = stateEl.value;
    track('filter', 'state', activeState ? 'include' : 'clear', activeState || 'all');
    buildAdvancedBar();
    buildFilterBar();
    renderAll();
  });
}

function visibleRows() {
  return document.querySelectorAll('#colleges-list .college-row');
}

function toggleExpandAll() {
  expandAllOn = !expandAllOn;
  track('toggle_expand_all', 'expand_all', expandAllOn ? 'expand' : 'collapse');
  visibleRows().forEach(row => {
    if (expandAllOn && !row.classList.contains('open')) {
      row.classList.add('open');
      const panel = row.querySelector('.faculty-panel-inner');
      if (panel && !panel._built) {
        panel._build();
        panel._built = true;
        updateRowVars(row);
      }
    } else if (!expandAllOn) {
      row.classList.remove('open');
    }
  });
  buildFilterBar();
}

// ── filtered aggregation ───────────────────────────────────────────────────
function filteredFaculty(college) {
  const facultyScope = subfieldScope === 'faculty';
  const subActive = facultyScope && activeSubfields.size > 0;
  const subExclude = facultyScope && excludedSubfields.size > 0;
  const catActive = activeCategories.size > 0;
  const q = searchQuery.trim().toLowerCase();
  // If the college name itself matches, every faculty row passes the search.
  const collegeHit = q && college._search.includes(q);
  return college.faculty.filter(f => {
    if (catActive && !activeCategories.has(f.category)) return false;
    if (subActive) {
      let hit = false;
      for (const s of activeSubfields) {
        if (f._interestsSet.has(s.toLowerCase())) { hit = true; break; }
      }
      if (!hit) return false;
    }
    if (subExclude) {
      for (const s of excludedSubfields) {
        if (f._interestsSet.has(s.toLowerCase())) return false;
      }
    }
    if (q && !collegeHit && !f._search.includes(q)) return false;
    return true;
  });
}

// In school scope, a college is kept iff (a) it has ≥1 in-category faculty
// matching any included subfield (when includes are set) AND (b) it has no
// in-category faculty matching any excluded subfield. Categories still apply
// so toggling Adjunct off doesn't let an adjunct keep a school visible.
function passesSchoolFilter(college) {
  if (subfieldScope !== 'school') return true;
  if (activeSubfields.size === 0 && excludedSubfields.size === 0) return true;
  const incLower = [...activeSubfields].map(s => s.toLowerCase());
  const excLower = [...excludedSubfields].map(s => s.toLowerCase());
  let hasInclude = activeSubfields.size === 0;
  const catActive = activeCategories.size > 0;
  for (const f of college.faculty) {
    if (catActive && !activeCategories.has(f.category)) continue;
    for (const s of excLower) {
      if (f._interestsSet.has(s)) return false;
    }
    if (!hasInclude) {
      for (const s of incLower) {
        if (f._interestsSet.has(s)) { hasInclude = true; break; }
      }
    }
  }
  return hasInclude;
}

function coursesInLatestYear(schedule) {
  if (!schedule || !schedule.terms?.length || !schedule.courses?.length) return null;
  let latestYear = '';
  for (const t of schedule.terms) if (t.year > latestYear) latestYear = t.year;
  const idxs = schedule.terms
    .map((t, i) => t.year === latestYear ? i : -1)
    .filter(i => i >= 0);
  let count = 0;
  for (const c of schedule.courses) {
    if (idxs.some(i => c.offered[i])) count++;
  }
  return count;
}

function aggregateCollege(college) {
  const fac = filteredFaculty(college);
  const cites = fac.map(f => f.citedby).filter(v => v != null);
  return {
    ...college,
    faculty: fac,
    total: fac.length,
    total_citations: cites.reduce((s, v) => s + v, 0),
  };
}

function animateStat(el, target) {
  const prev = el.dataset.value == null ? 0 : parseInt(el.dataset.value, 10);
  if (prev === target && el.classList.contains('count-spinner')) return;
  el.dataset.value = String(target);
  const targetStr = String(target);
  const slots = targetStr.length;
  const prevStr = String(prev).padStart(slots, '0').slice(-slots);

  el.classList.add('count-spinner');
  el.innerHTML = '';

  const strips = [];
  for (let i = 0; i < slots; i++) {
    const from = parseInt(prevStr[i], 10);
    const to = parseInt(targetStr[i], 10);
    const extraSpins = i + 1; // rightward digits spin more
    const forwardDelta = (to - from + 10) % 10;
    const total = extraSpins * 10 + forwardDelta;

    const slot = document.createElement('span');
    slot.className = 'digit';
    const strip = document.createElement('span');
    strip.className = 'digit-strip';
    for (let d = 0; d <= total; d++) {
      const ds = document.createElement('span');
      ds.textContent = (from + d) % 10;
      strip.appendChild(ds);
    }
    const slotDuration = 280 + i * 70;
    strip.style.transition = `transform ${slotDuration}ms cubic-bezier(0.22, 1, 0.36, 1)`;
    strip.style.transform = 'translateY(0)';
    slot.appendChild(strip);
    el.appendChild(slot);
    strips.push({ strip, total });
  }

  void el.offsetHeight; // force reflow so initial transform is registered
  requestAnimationFrame(() => {
    for (const { strip, total } of strips) {
      strip.style.transform = `translateY(-${total}em)`;
    }
  });
}

function renderAll() {
  const aggregated = allColleges
    .filter(c => !activeState || collegeLinks[c.name]?.state === activeState)
    .filter(passesSchoolFilter)
    .map(aggregateCollege)
    .filter(c => c.total > 0);
  const totalFaculty = aggregated.reduce((s, c) => s + c.total, 0);
  animateStat(document.getElementById('stat-colleges'), aggregated.length);
  animateStat(document.getElementById('stat-faculty'), totalFaculty);
  renderColleges(aggregated);
  // College rows were rebuilt — re-stamp each row's --summary-h.
  if (typeof updateHeaderH === 'function') updateHeaderH();
}

// ── college headers ────────────────────────────────────────────────────────
function buildCollegeHeaders() {
  const row = document.getElementById('col-headers');
  row.innerHTML = COLLEGE_COLS.map((col, i) => {
    const active = col.key === collegeSort.key;
    const arrow = active ? (collegeSort.dir === 1 ? '↑' : '↓') : '↕';
    const tip = col.tooltip ? ` title="${esc(col.tooltip)}"` : '';
    return `<div class="th ${active ? 'sorted' : ''}" data-col="${col.key}"${tip}>
      <span class="th-label">${col.label} <span class="sort-icon">${arrow}</span></span>
    </div>`;
  }).join('');

  row.querySelectorAll('.th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.col;
      if (collegeSort.key === key) {
        collegeSort.dir *= -1;
      } else {
        collegeSort = { key, dir: key === 'name' ? 1 : -1 };
      }
      track('sort', 'college', collegeSort.dir === 1 ? 'asc' : 'desc', key);
      buildCollegeHeaders();
      renderAll();
    });
  });
}

// ── college sort ───────────────────────────────────────────────────────────
function sortedColleges(colleges) {
  const fn = {
    name:              c => c.name,
    total:             c => c.total,
    total_citations:   c => c.total_citations ?? -1,
    courses_per_year:  c => c.courses_per_year ?? -1,
  }[collegeSort.key] || (c => c.name);

  return [...colleges].sort((a, b) => {
    const av = fn(a), bv = fn(b);
    if (typeof av === 'string') return collegeSort.dir * av.localeCompare(bv);
    return collegeSort.dir * (av - bv);
  });
}

// ── render colleges ────────────────────────────────────────────────────────
function renderColleges(colleges) {
  const list = document.getElementById('colleges-list');
  // Snapshot open/panel state from the rows being torn down so a filter,
  // sort, or search re-render doesn't collapse rows the user had expanded.
  const preserved = new Map();
  list.querySelectorAll('.college-row').forEach(row => {
    if (!row.classList.contains('open')) return;
    const name = row.querySelector('.cn-full')?.textContent;
    if (!name) return;
    const panel = row.querySelector('.faculty-panel-inner');
    preserved.set(name, {
      view: panel?._view,
      showColumbia: panel?._showColumbia,
      termOffset: panel?._termOffset,
    });
  });
  list.innerHTML = '';
  sortedColleges(colleges).forEach((college, idx) => {
    list.appendChild(buildCollegeRow(college, idx, preserved.get(college.name)));
  });
}

function fmt(n) { return n != null ? n.toLocaleString() : '—'; }

// Mobile-only short form for college names: abbreviates "University" → "Univ."
// to save horizontal space on narrow viewports.
function shortCollegeName(name) {
  return name.replace(/\bUniversity\b/g, 'Univ.');
}

// Compact form for narrow mobile columns: 1,640 → "1.6k", 11,245 → "11.2k".
// Numbers under 1000 keep their plain form.
function abbrev(n) {
  if (n < 1000) return n.toLocaleString();
  const r = Math.round(n / 100) / 10;
  return (Number.isInteger(r) ? r.toFixed(0) : r.toFixed(1)) + 'k';
}

function buildCollegeRow(college, idx, priorOpenState) {
  const div = document.createElement('div');
  div.className = 'college-row';

  const citFull  = college.total_citations > 0 ? fmt(college.total_citations) : '—';
  const citShort = college.total_citations > 0 ? abbrev(college.total_citations) : '—';
  const cpyText  = fmt(college.courses_per_year);
  const links   = collegeLinks[college.name] || {};

  const cnEsc = esc(college.name).replace(/'/g, "\\'");
  const programLink = links.program_url
    ? `<a class="college-link" href="${esc(links.program_url)}" target="_blank" rel="noopener" title="Department website" onclick="track('click_link','link','college_program','${cnEsc}')">${ICON_PROGRAM}</a>`
    : '';
  const scheduleLink = (links.schedule_url && courseSchedules[college.name])
    ? `<a class="college-link" href="${esc(links.schedule_url)}" target="_blank" rel="noopener" title="Course schedule" onclick="track('click_link','link','college_schedule','${cnEsc}')">${ICON_CATALOG}</a>`
    : `<span class="college-link disabled" title="Course schedule not accessible" aria-label="Course schedule not accessible">${ICON_CATALOG}</span>`;
  const logoImg = `<span class="college-logo cl-${collegeSlug(college.name)}" aria-hidden="true"></span>`;

  div.innerHTML = `
    <div class="college-summary">
      <div class="col-grid">
        <div class="td td-name">
          <span class="name-marker">
            <span class="college-num">${idx + 1}</span>
            <span class="chevron">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4,2 8,6 4,10"/>
              </svg>
            </span>
          </span>
          <span class="name-body">
            <span class="name-title">
              ${logoImg}
              <span class="college-name"><span class="cn-full">${esc(college.name)}</span><span class="cn-short">${esc(shortCollegeName(college.name))}</span></span>
              ${links.state ? `<span class="college-state">${esc(links.state)}</span>` : ''}
            </span>
            <span class="college-links">${programLink}${scheduleLink}</span>
          </span>
        </div>
        <div class="td-num">${college.total}</div>
        <div class="td-num ${college.total_citations > 0 ? '' : 'dim'}"><span class="num-full">${citFull}</span><span class="num-short">${citShort}</span></div>
        <div class="td-num ${college.courses_per_year != null ? '' : 'dim'}">${cpyText}</div>
      </div>
    </div>
    <div class="faculty-panel">
      <div class="faculty-panel-inner" id="fac-panel-${idx}"></div>
    </div>
  `;

  div.querySelectorAll('.college-link').forEach(a => {
    a.addEventListener('click', e => e.stopPropagation());
  });

  const panel = div.querySelector(`#fac-panel-${idx}`);
  panel._build = () => buildPanel(panel, college);

  if (priorOpenState) {
    if (priorOpenState.view !== undefined) panel._view = priorOpenState.view;
    if (priorOpenState.showColumbia !== undefined) panel._showColumbia = priorOpenState.showColumbia;
    if (priorOpenState.termOffset !== undefined) panel._termOffset = priorOpenState.termOffset;
  }

  if (expandAllOn || priorOpenState) {
    div.classList.add('open');
    panel._build();
    panel._built = true;
    // updateRowVars runs after this row is in the DOM — see renderColleges.
  }

  div.querySelector('.college-summary').addEventListener('click', () => {
    const wasOpen = div.classList.contains('open');
    div.classList.toggle('open', !wasOpen);
    track('toggle_college', 'college', wasOpen ? 'collapse' : 'expand', college.name);
    if (!wasOpen && !panel._built) {
      panel._build();
      panel._built = true;
      updateRowVars(div); // toggle now in DOM; measure for sticky offset
    }
    buildFilterBar();
  });

  return div;
}

// ── panel container (toggle + faculty/courses view) ────────────────────────
// Course-schedule term columns are paginated to a fixed window with ◀/▶
// buttons in the panel-toggle row. On small viewports the window is
// TERMS_PER_PAGE terms wide and shifts a page-at-a-time; on larger
// viewports the window is YEARS_PER_PAGE academic years wide (variable
// term count, depending on how many terms each year has) and shifts a
// year-page-at-a-time. Declared up here so the MediaQueryList listener
// below buildPanel can reference them without hitting the const TDZ.
const SMALL_VIEWPORT_MQ = window.matchMedia('(max-width: 720px)');
const TERMS_PER_PAGE = 4;
const YEARS_PER_PAGE = 4;

function buildPanel(panel, college) {
  const schedule = courseSchedules[college.name];
  const hasCourses = !!schedule;
  const facultyUrl = (collegeLinks[college.name] || {}).faculty_url;
  let view = panel._view || 'faculty';
  // Persisted across view-toggles via the outer panel element; the inner
  // .panel-body gets re-created on each render so we can't store it there.
  if (panel._showColumbia === undefined) panel._showColumbia = false;
  // termOffset is undefined initially; renderCourseTable defaults to the
  // latest TERMS_PER_PAGE window when no offset has been set yet.

  function render() {
    const coursesBtn = hasCourses
      ? `<button data-view="courses" class="${view === 'courses' ? 'active' : ''}" title="Courses" aria-label="Courses">${ICON_BOOK}</button>`
      : `<button data-view="courses" class="disabled" disabled title="Course schedule not accessible" aria-label="Course schedule not accessible">${ICON_BOOK}</button>`;
    const collegeNameEsc = esc(college.name).replace(/'/g, "\\'");
    const sourceLink = facultyUrl
      ? `<a class="faculty-source-link" href="${esc(facultyUrl)}" target="_blank" rel="noopener" onclick="track('click_link','link','faculty_source','${collegeNameEsc}')">source</a>`
      : '';
    const toggleHtml = `
      <div class="panel-toggle" role="tablist">
        <div class="panel-toggle-views">
          <button data-view="faculty" class="${view === 'faculty' ? 'active' : ''}" title="Faculty" aria-label="Faculty">${ICON_PERSON}</button>
          ${coursesBtn}
          ${view === 'faculty' ? sourceLink : ''}
        </div>
        <div class="term-paginator-slot"></div>
      </div>
    `;

    panel.innerHTML = toggleHtml + `<div class="panel-body"></div>`;
    const body = panel.querySelector('.panel-body');

    if (view === 'courses' && hasCourses) {
      renderCourseTable(body, schedule, college.name, {
        showColumbia: panel._showColumbia,
        onToggleColumbia: () => {
          panel._showColumbia = !panel._showColumbia;
          render();
        },
        termOffset: panel._termOffset,
        onShiftTerms: (next) => {
          panel._termOffset = next;
          render();
        },
      });
    } else {
      renderFacultyTable(body, college.faculty);
    }

    // Scope to view-toggle buttons only — `.panel-toggle button` would also
    // match the term-pagination buttons rendered into the slot, whose
    // `dataset.view` is undefined and would flip the panel back to faculty.
    panel.querySelectorAll('.panel-toggle button[data-view]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        view = btn.dataset.view;
        panel._view = view;
        track('switch_panel_view', 'panel', 'switch', view, college.name);
        render();
        // If the user had scrolled past the panel-toggle (it's sticky-
        // pinned at the top of the open row), reset scroll so they land
        // on the start of the new table. Otherwise switching from a long
        // courses table to a shorter faculty table leaves them staring at
        // unrelated rows shoved up from below.
        const newToggle = panel.querySelector('.panel-toggle');
        const stickyTop = parseFloat(getComputedStyle(newToggle).top) || 0;
        const panelTop = panel.getBoundingClientRect().top;
        if (panelTop < stickyTop) {
          window.scrollBy({ top: panelTop - stickyTop, behavior: 'smooth' });
        }
      });
    });
  }

  panel._render = render;
  render();
}

// Re-render any open course panels when the viewport crosses the small-
// viewport breakpoint, so the term-column window switches between the
// term-based (small) and year-based (large) pagination modes. The stored
// offset means different things in the two modes, so reset it.
SMALL_VIEWPORT_MQ.addEventListener('change', () => {
  document.querySelectorAll('.college-row.open').forEach(row => {
    const panel = row.querySelector('.faculty-panel-inner');
    if (panel && panel._view === 'courses' && panel._render) {
      panel._termOffset = undefined;
      panel._render();
    }
  });
});

// ── faculty panel ──────────────────────────────────────────────────────────
function renderFacultyTable(panel, faculty) {
  let facSort = { key: 'name', dir: 1 };

  function headersHtml() {
    return FAC_COLS.map(col => {
      const active = col.key === facSort.key;
      const arrow = active ? (facSort.dir === 1 ? '↑' : '↓') : '↕';
      const tip = COL_TOOLTIPS[col.key] ? ` title="${esc(COL_TOOLTIPS[col.key])}"` : '';
      return `<div class="fth ${active ? 'sorted' : ''}" data-fac-col="${col.key}"${tip}>
        <span class="fth-label">${col.label}</span> <span class="sort-icon">${arrow}</span>
      </div>`;
    }).join('');
  }

  function sortedFaculty() {
    const fn = {
      name:        f => f.name,
      title:       f => f.title,
      citedby:     f => f.citedby ?? -1,
      citedby5y:   f => f.citedby5y ?? -1,
      hindex:      f => f.hindex ?? -1,
      hindex5y:    f => f.hindex5y ?? -1,
      i10index:    f => f.i10index ?? -1,
      i10index5y:  f => f.i10index5y ?? -1,
    }[facSort.key] || (f => f.name);

    return [...faculty].sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === 'string') return facSort.dir * av.localeCompare(bv);
      return facSort.dir * (av - bv);
    });
  }

  function rowsHtml() {
    return sortedFaculty().map(f => {
      const nameEsc = esc(f.name).replace(/'/g, "\\'");
      const webLink = f.url
        ? `<a class="fac-link" href="${esc(f.url)}" target="_blank" rel="noopener" title="Personal website" onclick="track('click_link','link','faculty_website','${nameEsc}')">${ICON_GLOBE}</a>`
        : '';
      const schLink = f.scholar_url
        ? `<a class="fac-link" href="${esc(f.scholar_url)}" target="_blank" rel="noopener" title="Google Scholar" onclick="track('click_link','link','faculty_scholar','${nameEsc}')">${ICON_SCHOLAR}</a>`
        : '';

      function num(v) {
        if (v == null) return `<div class="ftd-num na">—</div>`;
        return `<div class="ftd-num">`
          + `<span class="num-full">${v.toLocaleString()}</span>`
          + `<span class="num-short">${abbrev(v)}</span>`
          + `</div>`;
      }

      return `
        <div class="fac-row">
          <div class="fac-grid">
            <div class="ftd ftd-name-cell">
              <div class="fac-name-row">
                <span class="fac-name-text">${esc(f.name)}</span>
                <span class="fac-links">${webLink}${schLink}</span>
              </div>
              <div class="fac-title-inline">${esc(f.title)}</div>
              ${f.interests ? `<div class="fac-interests">${esc(f.interests)}</div>` : ''}
            </div>
            <div class="ftd-title">${esc(f.title)}</div>
            ${num(f.citedby)}
            ${num(f.citedby5y)}
            ${num(f.hindex)}
            ${num(f.hindex5y)}
            ${num(f.i10index)}
            ${num(f.i10index5y)}
          </div>
        </div>
      `;
    }).join('');
  }

  function render() {
    panel.innerHTML = `
      <div class="fac-head-row">
        <div class="fac-grid" id="fac-head-${panel.id}">${headersHtml()}</div>
      </div>
      <div class="fac-rows-wrap">${rowsHtml()}</div>
    `;

    panel.querySelectorAll('.fth').forEach(th => {
      th.addEventListener('click', e => {
        e.stopPropagation();
        const key = th.dataset.facCol;
        if (facSort.key === key) {
          facSort.dir *= -1;
        } else {
          facSort = { key, dir: key === 'name' || key === 'title' ? 1 : -1 };
        }
        track('sort', 'faculty', facSort.dir === 1 ? 'asc' : 'desc', key);
        render();
      });
    });
  }

  render();
}

// ── course schedule view ───────────────────────────────────────────────────
// Barnard's catalogue lists Columbia cross-listings (COMS W*/E*) alongside
// its own BC-prefixed courses. They count toward the major, but most of
// them are taught at Columbia — so we hide them by default and expose a
// toggle on the Course column header.
const COLUMBIA_CODE_RE = /^COMS\s+(W|E)/i;

function renderCourseTable(panel, schedule, collegeName, opts) {
  const { showColumbia, onToggleColumbia, termOffset, onShiftTerms } = opts;
  const isBarnard = collegeName === 'Barnard College';
  const cnEsc = esc(collegeName).replace(/'/g, "\\'");

  if (!schedule.courses.length) {
    panel.innerHTML = `<div class="course-empty">No course-schedule data.</div>`;
    return;
  }

  const visibleCourses = isBarnard && !showColumbia
    ? schedule.courses.filter(c => !COLUMBIA_CODE_RE.test(c.code))
    : schedule.courses;

  // Decide the visible term-column range. The window is either
  // TERMS_PER_PAGE terms (small viewport) or YEARS_PER_PAGE academic
  // years (everything else). `termOffset` is reused as the active offset:
  // a term index on small, a year index on large. Whoever flips the
  // viewport breakpoint must reset it (see SMALL_VIEWPORT_MQ listener).
  const totalTerms = schedule.terms.length;
  const small = SMALL_VIEWPORT_MQ.matches;
  // Unique academic years in chronological order (terms are already sorted).
  const uniqueYears = [];
  for (const t of schedule.terms) {
    if (uniqueYears[uniqueYears.length - 1] !== t.year) uniqueYears.push(t.year);
  }
  const pageStep = small ? TERMS_PER_PAGE : YEARS_PER_PAGE;
  const maxOffset = small
    ? Math.max(0, totalTerms - TERMS_PER_PAGE)
    : Math.max(0, uniqueYears.length - YEARS_PER_PAGE);
  const paginated = small
    ? totalTerms > TERMS_PER_PAGE
    : uniqueYears.length > YEARS_PER_PAGE;

  let startIdx = 0;
  let endIdx = totalTerms;
  let offsetValue = 0;
  if (paginated) {
    offsetValue = Math.max(0, Math.min(termOffset ?? maxOffset, maxOffset));
    if (small) {
      startIdx = offsetValue;
      endIdx = offsetValue + TERMS_PER_PAGE;
    } else {
      const visibleYears = new Set(uniqueYears.slice(offsetValue, offsetValue + YEARS_PER_PAGE));
      startIdx = schedule.terms.findIndex(t => visibleYears.has(t.year));
      // last index whose year is in the window, +1
      let lastIdx = startIdx;
      for (let k = schedule.terms.length - 1; k >= 0; k--) {
        if (visibleYears.has(schedule.terms[k].year)) { lastIdx = k; break; }
      }
      endIdx = lastIdx + 1;
    }
  }

  const visibleTerms = schedule.terms.slice(startIdx, endIdx);
  const atStart = offsetValue === 0;
  const atEnd = offsetValue >= maxOffset;

  const headerCells = visibleTerms
    .map(t => `<th>${esc(t.label)}</th>`)
    .join('');

  const rows = visibleCourses.map(c => {
    const cells = c.offered.slice(startIdx, endIdx).map((v, j) => {
      const i = j + startIdx;
      if (v === 0 || v === false) {
        return `<td><span class="course-dash">—</span></td>`;
      }
      // Prefer matched-instructor display when present.
      const instr = c.instructors && c.instructors[i];
      if (Array.isArray(instr) && instr.length) {
        const items = instr.map(p => {
          const label = esc(p.l ?? '');
          const tip = esc(p.n ?? p.l ?? '');
          if (p.u) {
            const instrEsc = tip.replace(/'/g, "\\'");
            return `<a class="course-instr" href="${esc(p.u)}" target="_blank" rel="noopener" title="${tip}" onclick="track('click_link','link','course_instructor','${cnEsc}','${instrEsc}')">${label}</a>`;
          }
          return `<span class="course-instr course-instr-nolink" title="${tip}">${label}</span>`;
        });
        // 3+ instructors: wrap to two lines (first line gets ⌈n/2⌉ items).
        const SEP = '<span class="course-instr-sep">,</span>';
        const lines = items.length >= 3
          ? [items.slice(0, Math.ceil(items.length / 2)), items.slice(Math.ceil(items.length / 2))]
          : [items];
        const html = lines
          .map(line => `<span class="course-instr-row">${line.join(SEP)}</span>`)
          .join('');
        return `<td><div class="course-instr-list">${html}</div></td>`;
      }
      if (typeof v === 'string' && v) {
        return `<td><a class="course-check" href="${esc(v)}" target="_blank" rel="noopener" title="${esc(v)}">✓</a></td>`;
      }
      return `<td><span class="course-check">✓</span></td>`;
    }).join('');
    const titleInner = `
      <span class="course-code">${esc(c.code)}</span>
      <span class="course-name" title="${esc(c.name)}">${esc(c.name)}</span>
    `;
    const codeEsc = esc(c.code).replace(/'/g, "\\'");
    const titleCell = c.url
      ? `<a class="course-title-link" href="${esc(c.url)}" target="_blank" rel="noopener" onclick="track('click_link','link','course','${cnEsc}','${codeEsc}')">${titleInner}</a>`
      : `<div class="course-title-cell">${titleInner}</div>`;
    return `
      <tr>
        <td class="course-sticky">${titleCell}</td>
        ${cells}
      </tr>
    `;
  }).join('');

  const columbiaToggle = isBarnard ? `
    <button class="course-xlist-toggle ${showColumbia ? 'active' : ''}"
            title="${showColumbia ? 'Hide cross-listed Columbia courses' : 'Show cross-listed Columbia courses'}">
      ${showColumbia ? 'Hide Columbia' : 'Show Columbia'}
    </button>
  ` : '';

  panel.innerHTML = `
    <div class="course-wrap">
      <table class="course-table">
        <thead>
          <tr>
            <th class="course-sticky"><div class="course-title-cell"><span>Course</span>${columbiaToggle}</div></th>
            ${headerCells}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  if (isBarnard && onToggleColumbia) {
    const btn = panel.querySelector('.course-xlist-toggle');
    if (btn) {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        onToggleColumbia();
      });
    }
  }

  // The paginator lives in the panel-toggle row (above the table), so we
  // reach up to the enclosing panel root to fill the slot rendered there.
  const slot = panel.closest('.faculty-panel-inner')?.querySelector('.term-paginator-slot');
  if (slot) {
    if (paginated && onShiftTerms) {
      const lastVisible = visibleTerms[visibleTerms.length - 1];
      const firstVisible = visibleTerms[0];
      slot.innerHTML = `
        <div class="term-paginator">
          <button class="term-page-btn" data-shift="-1" ${atStart ? 'disabled' : ''}
                  aria-label="Earlier terms" title="Earlier terms">◀</button>
          <span class="term-paginator-range">${esc(firstVisible.label)} – ${esc(lastVisible.label)}</span>
          <button class="term-page-btn" data-shift="1" ${atEnd ? 'disabled' : ''}
                  aria-label="Later terms" title="Later terms">▶</button>
        </div>
      `;
      slot.querySelectorAll('.term-page-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          const dir = parseInt(btn.dataset.shift, 10) || 0;
          onShiftTerms(offsetValue + dir * pageStep);
        });
      });
    } else {
      slot.innerHTML = '';
    }
  }
}

// ── utils ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

loadData();
