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
const ICON_SCROLL = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`;

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
  { key: 'courses_per_year', label: 'Courses',  numeric: true, tooltip: 'Number of unique courses offered in the last academic year' },
  { key: 'filtered_pubs',   label: 'Papers',   numeric: true, tooltip: 'Number of papers affiliated with the institution and matching the current filters' },
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

const PUB_COLS = [
  { key: 'year',    label: 'Year',    numeric: true  },
  { key: 'title',   label: 'Title',   numeric: false },
  { key: 'venue',   label: 'Venue',   numeric: false },
  { key: 'authors', label: 'Authors', numeric: false },
  { key: 'cites',   label: 'Cites',   numeric: true  },
];

// ── filter categories ──────────────────────────────────────────────────────
const CATEGORIES = [
  { key: 'tenured',      label: 'Tenured'      },
  { key: 'tenure_track', label: 'Tenure-track' },
  { key: 'visiting',     label: 'Visiting'     },
  { key: 'teaching',     label: 'Teaching'     },
  { key: 'adjunct',      label: 'Adjunct'      },
];

// Global panel-view selector. The per-panel toggle still lets users
// override one school at a time; changing the global one re-applies to
// every open panel.
const VIEWS = [
  { key: 'faculty',      label: 'Faculty' },
  { key: 'courses',      label: 'Courses' },
  { key: 'publications', label: 'Papers'  },
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
let collegesByName = {};
let collegeLinks = {};
let courseSchedules = {};
let collegePublications = {};
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
let currentView = 'faculty';
let pubIncludes = {
  conference: new Set(['A*', 'A']),
  journal: new Set(['Q1']),
  other: new Set(),
};
let pubExcludes = {
  conference: new Set(),
  journal: new Set(),
  other: new Set(),
};
let pubYearFrom = null;
let pubYearTo = null;
let pubYearsAvailable = [];

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
  collegePublications = {};
  for (const [name, d] of Object.entries(merged)) {
    allColleges.push({
      name,
      faculty: d.faculty || [],
      total: d.total || 0,
      matched: d.matched || 0,
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
    if (d.publications) {
      collegePublications[name] = d.publications;
    }
  }

  const yearSet = new Set();
  for (const pubs of Object.values(collegePublications)) {
    for (const p of pubs) { if (p.year != null) yearSet.add(p.year); }
  }
  pubYearsAvailable = [...yearSet].filter(y => y >= 1990).sort((a, b) => a - b);
  if (pubYearsAvailable.length) {
    const maxYear = pubYearsAvailable[pubYearsAvailable.length - 1];
    pubYearFrom = maxYear - 10;
    pubYearTo = maxYear;
  }

  // Precompute a normalized lookup of each faculty's interests so the
  // subfield filter can match in O(1) per chip.
  collegesByName = {};
  for (const c of allColleges) {
    const stateCode = collegeLinks[c.name]?.state;
    const stateName = stateCode && US_STATES[stateCode];
    const collegeBits = [c.name, stateCode, stateName].filter(Boolean).join(' ');
    for (const f of c.faculty) {
      f._interestsSet = new Set(
        (f.interests || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
      );
      // `_nameSearch` is name only — drives the "expand to pubs + courses"
      // path. `_search` adds title/interests/college, used for the weaker
      // "show this faculty as a row" path.
      f._nameSearch = (f.name || '').toLowerCase();
      f._search = [f.name, f.title, f.interests, c.name]
        .filter(Boolean).join(' ').toLowerCase();
    }
    c._search = collegeBits.toLowerCase();
    c.courses_per_year = coursesInLatestYear(courseSchedules[c.name]);
    collegesByName[c.name] = c;
  }
  // Search strings for publications (title, venue, every author + affiliation,
  // plus the canonical matched-faculty names so a query like "Katie Keith"
  // finds papers whose OpenAlex author list spells it "Katherine A. Keith").
  // Each faculty also gets a `_matchedPubs` list pointing at the papers they
  // were matched on, so search can cross-check whether the triggering pub
  // would actually pass the current pub filters before claiming a match.
  for (const [name, pubs] of Object.entries(collegePublications)) {
    const college = collegesByName[name];
    const byFacultyName = new Map();
    if (college) {
      for (const f of college.faculty) {
        f._matchedPubs = [];
        if (f.name) byFacultyName.set(f.name.toLowerCase(), f);
      }
    }
    for (const p of pubs) {
      p._college = name;
      const parts = [p.title, p.venue, p.venue_acronym];
      if (Array.isArray(p.authors)) {
        for (const a of p.authors) {
          if (a.name) parts.push(a.name);
          if (a.affiliation) parts.push(a.affiliation);
        }
      }
      if (Array.isArray(p.matched_faculty)) {
        for (const mf of p.matched_faculty) if (mf) parts.push(mf);
      }
      p._search = parts.filter(Boolean).join(' ').toLowerCase();
      if (Array.isArray(p.matched_faculty)) {
        for (const facName of p.matched_faculty) {
          const f = byFacultyName.get((facName || '').toLowerCase());
          if (f) f._matchedPubs.push(p);
        }
      }
    }
  }
  // Search strings for courses (code, name, every instructor across all terms),
  // plus a per-faculty list of courses they teach so expansion can use it.
  for (const [collegeName, sched] of Object.entries(courseSchedules)) {
    if (!sched?.courses) continue;
    const college = collegesByName[collegeName];
    const byFacultyName = new Map();
    if (college) {
      for (const f of college.faculty) {
        f._matchedCourses = [];
        if (f.name) byFacultyName.set(f.name, f);
      }
    }
    for (const c of sched.courses) {
      // Course `_search` is intentionally code + name only. Instructor-name
      // queries reach courses via step 1 → step 5 (faculty match expands to
      // their courses); including instructors here would also pull in every
      // co-instructor of every course they ever taught as faculty rows in
      // step 6, which surfaces unrelated faculty.
      c._search = [c.code, c.name].filter(Boolean).join(' ').toLowerCase();
      if (Array.isArray(c.instructors)) {
        const seenInstr = new Set();
        for (const instr of c.instructors) {
          if (!Array.isArray(instr)) continue;
          for (const p of instr) {
            if (!p.n || seenInstr.has(p.n)) continue;
            seenInstr.add(p.n);
            const f = byFacultyName.get(p.n);
            if (f) f._matchedCourses.push(c);
          }
        }
      }
    }
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
  const pubFilterCount = pubIncludes.conference.size + pubIncludes.journal.size + pubIncludes.other.size
    + pubExcludes.conference.size + pubExcludes.journal.size + pubExcludes.other.size
    + (pubYearFrom != null ? 1 : 0) + (pubYearTo != null ? 1 : 0);
  const advTotal = activeSubfields.size + excludedSubfields.size + (activeState ? 1 : 0) + pubFilterCount;
  const advCount = advTotal > 0 ? ` (${advTotal})` : '';
  const advActive = (advancedExpanded || advTotal > 0) ? 'active' : '';

  // Preserve focus + caret position on the search input across rebuilds
  // (chip clicks call buildFilterBar(), which would otherwise blow it away).
  const prevSearch = document.getElementById('search-input');
  const searchHadFocus = prevSearch && document.activeElement === prevSearch;
  const searchCaret = searchHadFocus
    ? [prevSearch.selectionStart, prevSearch.selectionEnd]
    : null;

  const viewLabel = VIEWS.find(v => v.key === currentView)?.label || 'Faculty';
  const viewItems = VIEWS.map(v =>
    `<div class="cs-dropdown-item${v.key === currentView ? ' selected' : ''}" data-value="${v.key}">${v.label}</div>`
  ).join('');

  bar.innerHTML =
    `<span class="filter-label">Show</span>` +
    `<div class="cs-dropdown" id="view-dd">
       <button class="cs-dropdown-btn ${currentView !== 'faculty' ? 'active' : ''}" type="button">${viewLabel}</button>
       <div class="cs-dropdown-list">${viewItems}</div>
     </div>` +
    CATEGORIES.map(c => {
      const on = activeCategories.has(c.key);
      return `<button class="filter-chip ${on ? 'active' : ''}" data-cat="${c.key}">
        ${c.label}<span class="filter-chip-count">${counts[c.key]}</span>
      </button>`;
    }).join('') +
    `<input type="text" class="search-input" id="search-input" placeholder="Search…"
      aria-label="Search faculty, publications, and courses" value="${esc(searchDraft)}" />` +
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

  const viewDd = document.getElementById('view-dd');
  if (viewDd) {
    const viewBtn = viewDd.querySelector('.cs-dropdown-btn');
    const viewList = viewDd.querySelector('.cs-dropdown-list');
    viewBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const wasOpen = viewDd.classList.contains('open');
      document.querySelectorAll('.cs-dropdown.open').forEach(d => d.classList.remove('open'));
      if (!wasOpen) {
        viewDd.classList.add('open');
        const sel = viewList.querySelector('.selected');
        if (sel) sel.scrollIntoView({ block: 'nearest' });
      }
    });
    viewList.querySelectorAll('.cs-dropdown-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        viewDd.classList.remove('open');
        const next = item.dataset.value;
        if (next === currentView) return;
        currentView = next;
        track('view', 'global', 'switch', currentView);
        applyGlobalView();
        buildFilterBar();
      });
    });
  }
}

// Force every built panel onto the current global view. Unbuilt panels
// pick it up via the panel._view initialization in buildPanel.
function applyGlobalView() {
  document.querySelectorAll('.faculty-panel-inner').forEach(panel => {
    panel._view = currentView;
    if (panel._render) panel._render();
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
  const stateItems = `<div class="cs-dropdown-item${!activeState ? ' selected' : ''}" data-value="">All states</div>` +
    sortedStates.map(code => {
      const sel = code === activeState ? ' selected' : '';
      return `<div class="cs-dropdown-item${sel}" data-value="${esc(code)}">${esc(US_STATES[code])}</div>`;
    }).join('');
  const stateLabel = activeState ? esc(US_STATES[activeState]) : 'All states';

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
       <div class="cs-dropdown" id="state-dd">
         <button class="cs-dropdown-btn ${activeState ? 'active' : ''}" type="button">${stateLabel}</button>
         <div class="cs-dropdown-list">${stateItems}</div>
       </div>
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
    `<div class="adv-row adv-row-pubs">
       <span class="filter-label">Pubs</span>` +
       PUB_FILTER_GROUPS.map(g => {
         const chips = g.values.map(v => {
           const isObj = typeof v === 'object';
           const val = isObj ? v.key : v;
           const label = isObj ? v.label : v;
           const cls = pubIncludes[g.key].has(val) ? 'active'
             : pubExcludes[g.key].has(val) ? 'exclude'
             : '';
           return `<button class="pub-filter-chip ${cls}" data-group="${g.key}" data-value="${esc(val)}">${esc(label)}</button>`;
         }).join('');
         return `<div class="pub-filter-group"><span class="pub-filter-label">${g.label}</span>${chips}</div>`;
       }).join('') +
       `<div class="pub-filter-group">
          <span class="pub-filter-label">Year</span>
          <div class="cs-dropdown" id="pub-year-from-dd">
            <button class="cs-dropdown-btn ${pubYearFrom != null ? 'active' : ''}" type="button">${pubYearFrom != null ? pubYearFrom : 'From'}</button>
            <div class="cs-dropdown-list">
              <div class="cs-dropdown-item${pubYearFrom == null ? ' selected' : ''}" data-value="">From</div>
              ${pubYearsAvailable.map(y => `<div class="cs-dropdown-item${y === pubYearFrom ? ' selected' : ''}" data-value="${y}">${y}</div>`).join('')}
            </div>
          </div>
          <span class="pub-year-dash">–</span>
          <div class="cs-dropdown" id="pub-year-to-dd">
            <button class="cs-dropdown-btn ${pubYearTo != null ? 'active' : ''}" type="button">${pubYearTo != null ? pubYearTo : 'To'}</button>
            <div class="cs-dropdown-list">
              <div class="cs-dropdown-item${pubYearTo == null ? ' selected' : ''}" data-value="">To</div>
              ${pubYearsAvailable.map(y => `<div class="cs-dropdown-item${y === pubYearTo ? ' selected' : ''}" data-value="${y}">${y}</div>`).join('')}
            </div>
          </div>
        </div>` +
    `</div>` +
    `<div class="adv-row"><span class="adv-hint-inline">${interactHint}</span></div>`
  ;

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

  bar.querySelectorAll('.pub-filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.dataset.group;
      const value = btn.dataset.value;
      const inc = pubIncludes[group];
      const exc = pubExcludes[group];
      let action;
      // tri-state cycle: off → include → exclude → off
      if (inc.has(value)) {
        inc.delete(value);
        exc.add(value);
        action = 'exclude';
      } else if (exc.has(value)) {
        exc.delete(value);
        action = 'clear';
      } else {
        inc.add(value);
        action = 'include';
      }
      track('filter', 'publication', action, `${group}:${value}`);
      buildAdvancedBar();
      buildFilterBar();
      renderAll();
    });
  });

  bar.querySelectorAll('.cs-dropdown').forEach(dd => {
    const btn = dd.querySelector('.cs-dropdown-btn');
    const list = dd.querySelector('.cs-dropdown-list');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const wasOpen = dd.classList.contains('open');
      document.querySelectorAll('.cs-dropdown.open').forEach(d => d.classList.remove('open'));
      if (!wasOpen) {
        dd.classList.add('open');
        const sel = list.querySelector('.selected');
        if (sel) sel.scrollIntoView({ block: 'nearest' });
      }
    });
    list.querySelectorAll('.cs-dropdown-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        dd.classList.remove('open');
        const raw = item.dataset.value;
        if (dd.id === 'state-dd') {
          activeState = raw || '';
          track('filter', 'state', activeState ? 'include' : 'clear', activeState || 'all');
        } else {
          const val = raw ? parseInt(raw, 10) : null;
          const isFrom = dd.id === 'pub-year-from-dd';
          if (isFrom) {
            pubYearFrom = val;
            if (pubYearFrom != null && pubYearTo != null && pubYearFrom > pubYearTo) pubYearTo = pubYearFrom;
            track('filter', 'publication_year', pubYearFrom != null ? 'set_from' : 'clear_from', String(pubYearFrom ?? ''));
          } else {
            pubYearTo = val;
            if (pubYearFrom != null && pubYearTo != null && pubYearTo < pubYearFrom) pubYearFrom = pubYearTo;
            track('filter', 'publication_year', pubYearTo != null ? 'set_to' : 'clear_to', String(pubYearTo ?? ''));
          }
        }
        buildAdvancedBar();
        buildFilterBar();
        renderAll();
      });
    });
  });
  document.addEventListener('click', () => {
    document.querySelectorAll('.cs-dropdown.open').forEach(d => d.classList.remove('open'));
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
// Tokenize the query once per search. AND-of-tokens means `Daniel Barowy`
// matches `Daniel W. Barowy` (each token has to appear as a substring of the
// item's `_search` blob, but they need not be adjacent or in order).
let _cachedSearchQ = null;
let _cachedSearchTokens = [];
function getSearchTokens() {
  const q = searchQuery.trim().toLowerCase();
  if (_cachedSearchQ !== q) {
    _cachedSearchQ = q;
    _cachedSearchTokens = q ? q.split(/\s+/).filter(Boolean) : [];
  }
  return _cachedSearchTokens;
}

// The search model is categorical: a query is "matched" via one or more of
// {faculty, pub title/venue, pub LAC author, pub other author, course, college}
// and each category has different propagation rules. Rather than one boolean
// predicate over every item, we precompute four sets — faculty/pubs/courses/
// colleges that should be visible — and the renderers do membership checks.
//
//   • Faculty name match → that faculty's row, their papers (filtered) and
//     their courses.
//   • Faculty title/interests-only match → just the faculty row (their pubs
//     and courses stay hidden — a generic field query like "algorithms"
//     shouldn't drag in every paper of every algorithms researcher).
//   • Pub title/venue match → that paper plus its matched-faculty as rows
//     (no extra papers, no courses).
//   • Pub author match where that author IS an LAC faculty → treated as a
//     direct faculty match for the matching LAC author.
//   • Pub author match where the author is NOT an LAC faculty (e.g. an
//     external collaborator) → just the paper.
//   • Course match → that course plus its instructors as faculty rows
//     (the instructors are *not* expanded — their other pubs and courses
//     stay hidden unless they match the query through some other path).
//   • College/state match → everything for that college passes (papers still
//     subject to the active pub filters).
let _searchResult = null;

function pubVisibleBase(p) {
  if (pubYearFrom != null && (p.year == null || p.year < pubYearFrom)) return false;
  if (pubYearTo != null && (p.year == null || p.year > pubYearTo)) return false;
  const t = p.pub_type;
  let group, value;
  if (t === 'conference' || t === 'journal') {
    group = t;
    value = p.venue_ranking;
  } else {
    group = 'other';
    value = t;
  }
  if (pubExcludes[group].has(value)) return false;
  const anyInc = pubIncludes.conference.size || pubIncludes.journal.size || pubIncludes.other.size;
  if (anyInc && !pubIncludes[group].has(value)) return false;
  return true;
}

function computeSearchResult() {
  const tokens = getSearchTokens();
  if (!tokens.length) return null;
  const matchesAll = s => !!s && tokens.every(t => s.includes(t));
  const result = {
    colleges: new Set(),
    faculty: new Set(),
    pubs: new Set(),
    courses: new Set(),
  };
  for (const college of allColleges) {
    const pubs = collegePublications[college.name] || [];
    const courses = courseSchedules[college.name]?.courses || [];
    // College-name (or state) match passes the whole college through; pubs
    // are still gated by the user's quality/year filters.
    if (matchesAll(college._search)) {
      result.colleges.add(college);
      for (const f of college.faculty) result.faculty.add(f);
      for (const p of pubs) if (pubVisibleBase(p)) result.pubs.add(p);
      for (const c of courses) result.courses.add(c);
      continue;
    }
    const facByName = new Map();
    for (const f of college.faculty) if (f.name) facByName.set(f.name, f);
    let collegeHasMatch = false;
    const expanded = new Set();
    // 1. Faculty match:
    //    - Name match → faculty row + expand to their pubs + courses.
    //    - Title/interests-only match → faculty row only (don't expand,
    //      otherwise a generic query like "algorithms" would pull in every
    //      paper and course of anyone whose field includes algorithms).
    for (const f of college.faculty) {
      if (matchesAll(f._nameSearch)) {
        result.faculty.add(f);
        expanded.add(f);
        collegeHasMatch = true;
      } else if (matchesAll(f._search)) {
        result.faculty.add(f);
        collegeHasMatch = true;
      }
    }
    // 2/3/4. Pub-level matches.
    for (const p of pubs) {
      if (!pubVisibleBase(p)) continue;
      const tvText = ((p.title || '') + ' ' + (p.venue || '') + ' ' + (p.venue_acronym || '')).toLowerCase();
      const titleVenueMatch = matchesAll(tvText);
      let lacAuthor = null;
      if (Array.isArray(p.matched_faculty)) {
        for (const fn of p.matched_faculty) {
          if (matchesAll((fn || '').toLowerCase())) { lacAuthor = fn; break; }
        }
      }
      let otherAuthorMatch = false;
      if (!lacAuthor && Array.isArray(p.authors)) {
        for (const a of p.authors) {
          const aText = ((a.name || '') + ' ' + (a.affiliation || '')).toLowerCase();
          if (matchesAll(aText)) { otherAuthorMatch = true; break; }
        }
      }
      if (titleVenueMatch) {
        result.pubs.add(p);
        for (const fn of p.matched_faculty || []) {
          const f = facByName.get(fn);
          if (f) result.faculty.add(f); // row only — not expanded
        }
        collegeHasMatch = true;
      }
      if (lacAuthor) {
        const f = facByName.get(lacAuthor);
        if (f) {
          result.faculty.add(f);
          expanded.add(f);
          collegeHasMatch = true;
        }
      } else if (otherAuthorMatch) {
        // External co-author match: show the paper, but don't surface any
        // LAC faculty just because they happen to be on the same paper.
        result.pubs.add(p);
        collegeHasMatch = true;
      }
    }
    // 5. Expand pubs + courses for faculty matched directly or via LAC author.
    for (const f of expanded) {
      for (const p of f._matchedPubs || []) {
        if (pubVisibleBase(p)) result.pubs.add(p);
      }
      for (const c of f._matchedCourses || []) {
        result.courses.add(c);
      }
    }
    // 6. Course match (on the course's code + name only — `_search` no
    //    longer includes instructor names) → course row plus the faculty
    //    teaching it as faculty rows. They're added to `result.faculty`
    //    but not to `expanded`, so they don't drag in their other pubs
    //    or courses.
    for (const c of courses) {
      if (!matchesAll(c._search)) continue;
      result.courses.add(c);
      collegeHasMatch = true;
      if (Array.isArray(c.instructors)) {
        const seen = new Set();
        for (const instr of c.instructors) {
          if (!Array.isArray(instr)) continue;
          for (const p of instr) {
            if (!p.n || seen.has(p.n)) continue;
            seen.add(p.n);
            const f = facByName.get(p.n);
            if (f) result.faculty.add(f);
          }
        }
      }
    }
    if (collegeHasMatch) result.colleges.add(college);
  }
  return result;
}

function searchHitFaculty(f) { return !_searchResult || _searchResult.faculty.has(f); }
function searchHitPub(p)     { return !_searchResult || _searchResult.pubs.has(p); }
function searchHitCourse(c)  { return !_searchResult || _searchResult.courses.has(c); }

function filteredFaculty(college) {
  const facultyScope = subfieldScope === 'faculty';
  const subActive = facultyScope && activeSubfields.size > 0;
  const subExclude = facultyScope && excludedSubfields.size > 0;
  const catActive = activeCategories.size > 0;
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
    if (!searchHitFaculty(f)) return false;
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

function filteredPubCount(collegeName) {
  const pubs = collegePublications[collegeName];
  if (!pubs) return null;
  let count = 0;
  for (const p of pubs) { if (pubVisible(p)) count++; }
  return count;
}

// Search-aware course count. Used both for the row's Courses column when
// search is active and to decide whether to keep a college in the results.
function filteredCourseCount(collegeName) {
  const sched = courseSchedules[collegeName];
  if (!sched?.courses) return null;
  let count = 0;
  for (const c of sched.courses) {
    if (searchHitCourse(c)) count++;
  }
  return count;
}

function aggregateCollege(college) {
  const fac = filteredFaculty(college);
  return {
    ...college,
    faculty: fac,
    total: fac.length,
    filtered_pubs: filteredPubCount(college.name),
    filtered_courses: filteredCourseCount(college.name),
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

function updatePapersStat() {
  let total = 0;
  for (const pubs of Object.values(collegePublications)) {
    for (const p of pubs) { if (pubVisible(p)) total++; }
  }
  animateStat(document.getElementById('stat-papers'), total);

  const parts = [];
  for (const g of PUB_FILTER_GROUPS) {
    for (const v of g.values) {
      const isObj = typeof v === 'object';
      const val = isObj ? v.key : v;
      const label = isObj ? v.label : v;
      if (pubIncludes[g.key].has(val)) parts.push(label);
      else if (pubExcludes[g.key].has(val)) parts.push('−' + label);
    }
  }
  if (pubYearFrom != null || pubYearTo != null) {
    const from = pubYearFrom ?? pubYearsAvailable[0];
    const to = pubYearTo ?? pubYearsAvailable[pubYearsAvailable.length - 1];
    if (from === to) {
      parts.push(String(from));
    } else {
      const fc = Math.floor(from / 100);
      const tc = Math.floor(to / 100);
      parts.push(fc === tc
        ? `${from}-${String(to).slice(-2)}`
        : `${from}-${to}`);
    }
  }
  const suffix = parts.length ? ` (${parts.join(', ')})` : '';
  document.getElementById('stat-papers-label').textContent = `Papers${suffix}`;
}

function renderAll() {
  // Refresh the categorical search match sets before any filtered lookups.
  _searchResult = computeSearchResult();
  const searching = !!searchQuery.trim();
  const aggregated = allColleges
    .filter(c => !activeState || collegeLinks[c.name]?.state === activeState)
    .filter(passesSchoolFilter)
    .map(aggregateCollege)
    // With an active search, keep a college if any of {faculty, pubs, courses}
    // has a match — that way searching a venue or instructor surfaces the
    // college even when no faculty name matches.
    .filter(c => c.total > 0
      || (searching && ((c.filtered_pubs ?? 0) > 0 || (c.filtered_courses ?? 0) > 0)));
  const totalFaculty = aggregated.reduce((s, c) => s + c.total, 0);
  animateStat(document.getElementById('stat-colleges'), aggregated.length);
  animateStat(document.getElementById('stat-faculty'), totalFaculty);
  updatePapersStat();
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

  row.querySelectorAll('.th-label').forEach(label => {
    label.addEventListener('click', () => {
      const key = label.closest('.th').dataset.col;
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
  const searching = !!searchQuery.trim();
  const fn = {
    name:              c => c.name,
    total:             c => c.total,
    courses_per_year:  c => (searching ? c.filtered_courses : c.courses_per_year) ?? -1,
    filtered_pubs:     c => c.filtered_pubs ?? -1,
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
      pubSort: panel?._pubSort,
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

  // When the user is searching, the Courses column shows the count of
  // search-matching courses (across all years) instead of the static
  // last-academic-year count.
  const searching = !!searchQuery.trim();
  const coursesValue = searching ? college.filtered_courses : college.courses_per_year;
  const cpyText  = fmt(coursesValue);
  const fpText   = fmt(college.filtered_pubs);
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
        <div class="td-num ${coursesValue != null && (!searching || coursesValue > 0) ? '' : 'dim'}">${cpyText}</div>
        <div class="td-num ${college.filtered_pubs != null && college.filtered_pubs > 0 ? '' : 'dim'}">${fpText}</div>
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
    if (priorOpenState.pubSort !== undefined) panel._pubSort = priorOpenState.pubSort;
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
  const publications = collegePublications[college.name];
  const hasCourses = !!schedule;
  const hasPublications = !!publications;
  const facultyUrl = (collegeLinks[college.name] || {}).faculty_url;
  if (panel._view === undefined) panel._view = currentView;
  // Persisted across view-toggles via the outer panel element; the inner
  // .panel-body gets re-created on each render so we can't store it there.
  if (panel._showColumbia === undefined) panel._showColumbia = false;
  // termOffset is undefined initially; renderCourseTable defaults to the
  // latest TERMS_PER_PAGE window when no offset has been set yet.

  function render() {
    // Read panel._view fresh each render so applyGlobalView's reassignment
    // is picked up. Fall back when the chosen view has no data for this
    // school, so the toggle highlight tracks the actually-rendered table.
    let view = panel._view || currentView;
    if (view === 'courses' && !hasCourses) view = 'faculty';
    if (view === 'publications' && !hasPublications) view = 'faculty';

    const coursesBtn = hasCourses
      ? `<button data-view="courses" class="${view === 'courses' ? 'active' : ''}" title="Courses" aria-label="Courses">${ICON_BOOK}</button>`
      : `<button data-view="courses" class="disabled" disabled title="Course schedule not accessible" aria-label="Course schedule not accessible">${ICON_BOOK}</button>`;
    const pubsBtn = hasPublications
      ? `<button data-view="publications" class="${view === 'publications' ? 'active' : ''}" title="Papers" aria-label="Papers">${ICON_SCROLL}</button>`
      : `<button data-view="publications" class="disabled" disabled title="No publication data" aria-label="No publication data">${ICON_SCROLL}</button>`;
    const collegeNameEsc = esc(college.name).replace(/'/g, "\\'");
    const sourceLink = facultyUrl
      ? `<a class="faculty-source-link" href="${esc(facultyUrl)}" target="_blank" rel="noopener" onclick="track('click_link','link','faculty_source','${collegeNameEsc}')">source</a>`
      : '';
    const toggleHtml = `
      <div class="panel-toggle" role="tablist">
        <div class="panel-toggle-views">
          <button data-view="faculty" class="${view === 'faculty' ? 'active' : ''}" title="Faculty" aria-label="Faculty">${ICON_PERSON}</button>
          ${coursesBtn}
          ${pubsBtn}
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
    } else if (view === 'publications' && hasPublications) {
      renderPublicationsTable(body, publications);
    } else {
      renderFacultyTable(body, college.faculty);
    }

    // Scope to view-toggle buttons only — `.panel-toggle button` would also
    // match the term-pagination buttons rendered into the slot, whose
    // `dataset.view` is undefined and would flip the panel back to faculty.
    panel.querySelectorAll('.panel-toggle button[data-view]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        panel._view = btn.dataset.view;
        track('switch_panel_view', 'panel', 'switch', panel._view, college.name);
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
        <span class="fth-label">${col.label} <span class="sort-icon">${arrow}</span></span>
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
    const body = faculty.length
      ? `<div class="fac-rows-wrap">${rowsHtml()}</div>`
      : `<div class="course-empty">No faculty match the current search.</div>`;
    panel.innerHTML = `
      <div class="fac-head-row">
        <div class="fac-grid" id="fac-head-${panel.id}">${headersHtml()}</div>
      </div>
      ${body}
    `;

    panel.querySelectorAll('.fth-label').forEach(label => {
      label.addEventListener('click', e => {
        e.stopPropagation();
        const key = label.closest('.fth').dataset.facCol;
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

// ── publications panel ────────────────────────────────────────────────────
const PUB_FILTER_GROUPS = [
  { key: 'conference', label: 'Conferences', values: ['A*', 'A', 'B', 'C'] },
  { key: 'journal',    label: 'Journals',    values: ['Q1', 'Q2', 'Q3', 'Q4'] },
  { key: 'other',      label: 'Other',       values: [
    { key: 'workshop', label: 'Workshop' },
    { key: 'preprint', label: 'Preprint' },
    { key: 'book',     label: 'Book' },
    { key: 'other',    label: 'Other' },
  ]},
];

function pubVisible(p) {
  if (!pubVisibleBase(p)) return false;
  return searchHitPub(p);
}

function renderPublicationsTable(panel, publications) {
  const outer = panel.closest('.faculty-panel-inner') || panel;
  if (!outer._pubSort) outer._pubSort = { key: 'year', dir: -1 };
  let pubSort = outer._pubSort;

  function headersHtml() {
    return PUB_COLS.map(col => {
      const active = col.key === pubSort.key;
      const arrow = active ? (pubSort.dir === 1 ? '↑' : '↓') : '↕';
      return `<div class="pth ${active ? 'sorted' : ''}" data-pub-col="${col.key}">
        <span class="pth-label">${col.label} <span class="sort-icon">${arrow}</span></span>
      </div>`;
    }).join('');
  }

  function sortedPubs() {
    const filtered = publications.filter(pubVisible);
    const fn = {
      year:    p => p.year ?? -1,
      title:   p => (p.title || '').toLowerCase(),
      venue:   p => (p.venue_acronym || p.venue || '').toLowerCase(),
      authors: p => (p.authors || []).map(a => a.name).join(', ').toLowerCase(),
      cites:   p => p.cites ?? -1,
    }[pubSort.key] || (p => p.year ?? -1);

    return filtered.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === 'string') return pubSort.dir * av.localeCompare(bv);
      return pubSort.dir * (av - bv);
    });
  }

  function rowsHtml(sorted) {
    return sorted.map(p => {
      const yearStr = p.year != null ? String(p.year) : '—';

      const titleHtml = safeHtml(dedupeMathFallback(p.title || ''));
      const titleInner = p.url
        ? `<a class="pub-title-link" href="${esc(p.url)}" target="_blank" rel="noopener">${titleHtml}</a>`
        : `<span class="pub-title-text">${titleHtml}</span>`;

      let venueHtml = '';
      if (p.venue_acronym) {
        const venueTip = esc(plainText(p.venue || ''));
        venueHtml = p.venue_url
          ? `<a href="${esc(p.venue_url)}" target="_blank" rel="noopener" title="${venueTip}">${esc(p.venue_acronym)}</a>`
          : `<span title="${venueTip}">${esc(p.venue_acronym)}</span>`;
      } else if (p.venue) {
        venueHtml = p.venue_url
          ? `<a class="pub-venue-full" href="${esc(p.venue_url)}" target="_blank" rel="noopener">${safeHtml(p.venue)}</a>`
          : `<span class="pub-venue-full">${safeHtml(p.venue)}</span>`;
      } else {
        venueHtml = '—';
      }
      if (p.venue_ranking) {
        venueHtml += `<sup class="venue-rank" title="${esc(p.venue_ranking_source || '')}">${esc(p.venue_ranking)}</sup>`;
      }

      let authorsHtml = '—';
      if (p.authors && p.authors.length) {
        const authorSpans = p.authors.map(a => {
          const tip = a.affiliation ? ` title="${esc(a.affiliation)}"` : '';
          if (a.url) {
            return `<a class="pub-author" href="${esc(a.url)}" target="_blank" rel="noopener"${tip}>${esc(a.name)}</a>`;
          }
          return `<span class="pub-author"${tip}>${esc(a.name)}</span>`;
        });
        if (authorSpans.length > 8) {
          authorsHtml =
            `<span class="authors-short">${authorSpans.slice(0, 8).join(', ')}, … <button class="authors-toggle" aria-label="Show all authors">+</button></span>` +
            `<span class="authors-full" hidden>${authorSpans.join(', ')} <button class="authors-toggle" aria-label="Collapse authors">−</button></span>`;
        } else {
          authorsHtml = authorSpans.join(', ');
        }
      }

      const citesStr = p.cites != null
        ? `<span class="num-full">${p.cites.toLocaleString()}</span><span class="num-short">${abbrev(p.cites)}</span>`
        : '—';

      return `
        <div class="pub-row">
          <div class="pub-grid">
            <div class="ptd ptd-year">${yearStr}</div>
            <div class="ptd ptd-title">${titleInner}</div>
            <div class="ptd ptd-venue">${venueHtml}</div>
            <div class="ptd ptd-authors">${authorsHtml}</div>
            <div class="ptd-num">${citesStr}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function render() {
    const sorted = sortedPubs();
    const body = sorted.length
      ? `<div class="pub-rows-wrap">${rowsHtml(sorted)}</div>`
      : `<div class="course-empty">No publications match the current filters.</div>`;
    panel.innerHTML = `
      <div class="pub-head-row">
        <div class="pub-grid" id="pub-head-${panel.id}">${headersHtml()}</div>
      </div>
      ${body}
    `;
    renderMathIn(panel.querySelector('.pub-rows-wrap'));

    panel.querySelectorAll('.pth-label').forEach(label => {
      label.addEventListener('click', e => {
        e.stopPropagation();
        const key = label.closest('.pth').dataset.pubCol;
        if (pubSort.key === key) {
          pubSort.dir *= -1;
        } else {
          pubSort = { key, dir: key === 'title' || key === 'venue' ? 1 : -1 };
        }
        outer._pubSort = pubSort;
        track('sort', 'publications', pubSort.dir === 1 ? 'asc' : 'desc', key);
        render();
      });
    });

    panel.querySelectorAll('.authors-toggle').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const cell = btn.closest('.ptd-authors');
        const short = cell.querySelector('.authors-short');
        const full = cell.querySelector('.authors-full');
        const showing = !full.hidden;
        short.hidden = !showing;
        full.hidden = showing;
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

  let visibleCourses = isBarnard && !showColumbia
    ? schedule.courses.filter(c => !COLUMBIA_CODE_RE.test(c.code))
    : schedule.courses;
  visibleCourses = visibleCourses.filter(searchHitCourse);
  if (!visibleCourses.length) {
    panel.innerHTML = `<div class="course-empty">No courses match the current search.</div>`;
    return;
  }

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

const SAFE_INLINE_TAG = /^<\/?(?:i|b|u|em|strong|sub|sup|scp|small)\s*\/?>$/i;

function safeHtml(s) {
  if (s == null || s === '') return '';
  return String(s).replace(
    /<[^>]*>|&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);|[<>&"]/g,
    m => {
      if (m.length === 1) {
        return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[m];
      }
      if (m[0] === '<') return SAFE_INLINE_TAG.test(m) ? m : esc(m);
      return m;
    }
  );
}

const _plainTpl = document.createElement('template');
function plainText(s) {
  if (s == null || s === '') return '';
  _plainTpl.innerHTML = String(s);
  return _plainTpl.content.textContent || '';
}

// OpenAlex titles often follow `$$<latex>$$` with a redundant text-rendered fallback
// (e.g. `$$\mathcal {ALCS}5_m$$ ALCS 5 m`). When we render the math with KaTeX, drop
// the fallback by checking whether the chars right after the math block, with whitespace
// and grouping braces removed, match the LaTeX with commands/sub/sup markers stripped.
function dedupeMathFallback(s) {
  if (s == null || s === '') return '';
  const norm = x => x.replace(/[\s{}]/g, '');
  const cleanLatex = inner => norm(
    inner.replace(/\\[a-zA-Z]+\s*/g, '').replace(/[\\_^]/g, '')
  );
  let out = '';
  let i = 0;
  while (i < s.length) {
    const start = s.indexOf('$$', i);
    if (start < 0) { out += s.slice(i); break; }
    const end = s.indexOf('$$', start + 2);
    if (end < 0) { out += s.slice(i); break; }
    out += s.slice(i, end + 2);
    i = end + 2;
    const target = cleanLatex(s.slice(start + 2, end));
    if (!target) continue;
    let j = i;
    while (j < s.length && /\s/.test(s[j])) j++;
    if (j === i) continue;
    let acc = '';
    for (let k = j; k < s.length && k - j < 200; k++) {
      if (s[k] === '$') break;
      acc += s[k];
      const accNorm = norm(acc);
      if (accNorm === target) { i = k + 1; break; }
      if (accNorm.length > target.length) break;
    }
  }
  return out;
}

function renderMathIn(el) {
  if (typeof renderMathInElement !== 'function' || !el) return;
  try {
    renderMathInElement(el, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$',  right: '$',  display: false },
      ],
      throwOnError: false,
      errorColor: 'inherit',
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'],
    });
  } catch (_) { /* swallow render errors */ }
}

// Re-render any panels that were populated before KaTeX finished loading.
window.addEventListener('load', () => {
  document.querySelectorAll('.pub-rows-wrap').forEach(renderMathIn);
});

loadData();

// ── custom tooltip (replaces slow native title) ───────────────────────────
(function initTooltip() {
  const tip = document.getElementById('tip');
  let cur = null;
  let savedTitle = '';

  function show(el, text, e) {
    cur = el;
    savedTitle = text;
    el.removeAttribute('title');
    tip.textContent = text;
    tip.classList.add('visible');
    position(e);
  }

  function hide() {
    if (!cur) return;
    cur.setAttribute('title', savedTitle);
    cur = null;
    tip.classList.remove('visible');
  }

  function position(e) {
    const pad = 8;
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    const r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth) x = e.clientX - r.width - pad;
    if (y + r.height > window.innerHeight) y = e.clientY - r.height - pad;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }

  function closest(el) {
    while (el && el !== document.body) {
      if (el.getAttribute && el.getAttribute('title')) return el;
      el = el.parentElement;
    }
    return null;
  }

  document.addEventListener('mouseover', function (e) {
    const el = closest(e.target);
    if (el) show(el, el.getAttribute('title'), e);
  });

  document.addEventListener('mouseout', function (e) {
    if (cur && !cur.contains(e.relatedTarget)) hide();
  });

  document.addEventListener('mousemove', function (e) {
    if (cur) position(e);
  });
})();
