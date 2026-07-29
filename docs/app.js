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
const ICON_OPENALEX = `<span class="oa-link-icon" aria-hidden="true"></span>`;
const ICON_CATALOG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
const ICON_PERSON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
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

// ── venue ranking tooltips ────────────────────────────────────────────────
// ICORE percentile bands derived from the published ICORE2026 distribution
// of 825 ranked venues (A* 7.52%, A 13.09%, B 30.18%, C 46.18%) — bounds
// are cumulative.
const SCIMAGO_SOURCE = 'SCImago 2025 Journal Ranking';
const ICORE_SOURCE = 'ICORE 2026 Conference Ranking';
const VENUE_RANK_TOOLTIPS = {
  'Q1': `Top 25% in ${SCIMAGO_SOURCE}`,
  'Q2': `25–50th percentile in ${SCIMAGO_SOURCE}`,
  'Q3': `50–75th percentile in ${SCIMAGO_SOURCE}`,
  'Q4': `Bottom 25% in ${SCIMAGO_SOURCE}`,
  'A*': `Top 7.5% in ${ICORE_SOURCE}`,
  'A':  `7.5–20.6th percentile in ${ICORE_SOURCE}`,
  'B':  `20.6–50.8th percentile in ${ICORE_SOURCE}`,
  'C':  `50.8–97th percentile in ${ICORE_SOURCE}`,
};
function venueRankTooltip(rank, source) {
  return VENUE_RANK_TOOLTIPS[rank] || source || '';
}

// ── column definitions ─────────────────────────────────────────────────────
const COLLEGE_COLS = [
  { key: 'rank',             label: 'Institution',   numeric: false, tooltip: 'Default sorting order: Faculty size -> # of electives -> # of papers -> # of graduates.' },
  { key: 'total',            label: 'Faculty',       numeric: true, tooltip: 'Number of faculty' },
  { key: 'grads',            label: '4YR-GRAD',      numeric: true, tooltip: 'The total number of graduated CS majors from 2021 to 2024 (according to IPEDS)' },
  { key: 'grad_fac',         label: 'GRAD:FAC',      numeric: true, tooltip: 'Ratio of the total number of graduated CS majors from 2021 to 2024 (according to IPEDS) to the current number of tenured/tenure-track faculty' },
  { key: 'electives',        label: 'Electives',  numeric: true, tooltip: 'Number of advanced CS electives offered in the last two academic years. Excludes (pre-)cores, independent study/thesis/seminar, and non-CS cross-listings.' },
  { key: 'papers',          label: 'Papers',   numeric: true, tooltip: 'Number of papers affiliated with the institution and matching the current filters' },
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
  { key: 'year',    label: '<span class="lbl-full">Year</span><span class="lbl-short">Yr</span>', numeric: true  },
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

// Display-only short labels for select subfields. Keys must match CS_SUBFIELDS
// verbatim. Filter chips, the faculty-card interests line, and any other UI
// surface the short form, but internal state (activeSubfields, _interestsSet)
// keeps the long form, and the search index includes both so queries by
// either name still hit.
const CS_SUBFIELD_SHORT_LABELS = {
  'Algorithms & complexity': 'Algo',
  'Artificial intelligence': 'AI',
  'Computational bio & bioinformatics': 'Comp. bio',
  'Computational social science': 'Comp. social science',
  'Computer architecture': 'Architecture',
  'Computer graphics': 'Graphics',
  'Computer networks': 'Networks',
  'Computer science education': 'CS Ed',
  'Computer security & privacy': 'Security',
  'Computer vision': 'CV',
  'Databases': 'DB',
  'Distributed systems': 'Distributed',
  'Games & interactive art': 'Games & art',
  'Embedded & real-time systems': 'Embedded & real-time',
  'High-performance computing': 'HPC',
  'Human-computer interaction': 'HCI',
  'Information retrieval': 'IR',
  'Machine learning': 'ML',
  'Measurement & performance analysis': 'Measurement',
  'Mobile computing': 'Mobicomp',
  'Natural language processing': 'NLP',
  'Operating systems': 'OS',
  'Programming languages': 'PL',
  'Quantum computing': 'Quantum',
  'Software engineering': 'SWE',
  'Visualization': 'Viz',
};

function shortSubfieldLabel(name) {
  return CS_SUBFIELD_SHORT_LABELS[name] || name;
}

// Groups for the subfield filter chips. Mirrors the four top-level CSRankings
// areas. Every entry in CS_SUBFIELDS must appear in exactly one group.
const CS_SUBFIELD_GROUPS = [
  { label: 'AI', subfields: [
    'Artificial intelligence', 'Computer vision', 'Data science',
    'Information retrieval', 'Machine learning', 'Natural language processing',
  ]},
  { label: 'Theory', subfields: [
    'Algorithms & complexity', 'Cryptography', 'Logic & verification',
  ]},
  { label: 'Systems', subfields: [
    'Computer architecture', 'Computer networks', 'Computer security & privacy',
    'Databases', 'Design automation', 'Distributed systems',
    'Embedded & real-time systems', 'High-performance computing',
    'Measurement & performance analysis', 'Mobile computing',
    'Operating systems', 'Programming languages', 'Software engineering',
  ]},
  { label: 'Interdisciplinary', subfields: [
    'Computational bio & bioinformatics', 'Computational social science',
    'Computer graphics', 'Computer science education',
    'Economics & computation', 'Games & interactive art',
    'Human-computer interaction', 'Quantum computing', 'Robotics',
    'Visualization',
  ]},
];

// Renders a comma-separated interests string with each known subfield swapped
// for its short label. Unknown items (e.g. raw Scholar interests for untrusted
// rows) pass through untouched.
function shortenInterestsForDisplay(text) {
  if (!text) return text;
  return text.split(',').map(s => {
    const t = s.trim();
    return CS_SUBFIELD_SHORT_LABELS[t] || t;
  }).join(', ');
}

// Slugifies a college name into the CSS class used by img/logo_sprite.css
// (e.g. "St. Mary's College of Maryland" -> "st-mary-s-college-of-maryland").
// Must match slug() in docs/generate_logo_sprite.py.
function collegeSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// ── state ──────────────────────────────────────────────────────────────────
// Hidden debug mode, enabled only via a `debug` URL param (e.g. ?debug=1).
// Surfaces internal diagnostics — currently an info icon on every course row
// explaining whether it counts toward the Electives total. Off for any
// falsy/absent value so a stray ?debug=0 stays hidden.
const DEBUG = (() => {
  const v = new URLSearchParams(location.search).get('debug');
  return v !== null && v !== '' && v !== '0' && v !== 'false';
})();

let allColleges = [];
let collegesByName = {};
let collegeLinks = {};
let courseSchedules = {};
let collegePublications = {};
// null = the default multi-column ordering (see defaultCollegeCompare). A
// non-null { key, dir, clicks } means the user clicked a header to sort by a
// single column; `clicks` drives the 3-click cycle back to the default.
let collegeSort = null;
let activeCategories = new Set(['tenured', 'tenure_track']);
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
// Minimum citation count a paper must have to pass the pub filters. 0 disables
// the gate; the default of 1 drops never-cited papers.
let pubMinCites = 1;
let pubMinCitesTimer = null;

// ── URL state ─────────────────────────────────────────────────────────────
// Filter, sort, view, and expand-all state is round-tripped through the URL
// query string so users can share a link that pre-applies their current view.
// Defaults are omitted from the serialized URL, so a clean page load produces
// no query string.
const URL_DEFAULTS = {
  cat: new Set(['tenured', 'tenure_track']),
  view: 'faculty',
  scope: 'faculty',
  pubInc: {
    conference: new Set(['A*', 'A']),
    journal: new Set(['Q1']),
    other: new Set(),
  },
  minCites: 1,
};
const PUB_GROUP_SHORT = { conference: 'c', journal: 'j', other: 'o' };
const PUB_GROUP_LONG = { c: 'conference', j: 'journal', o: 'other' };
const VALID_VIEW = new Set(['faculty', 'courses', 'publications']);
const VALID_SCOPE = new Set(['faculty', 'school']);
const VALID_SORT_KEYS = new Set(['rank', 'total', 'grads', 'grad_fac', 'electives', 'papers']);

function setsEqual(a, b) {
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

// pubYearFrom/To default to a 10-year window of the latest available year.
// Computed dynamically since pubYearsAvailable is populated from the dataset.
function defaultPubYearRange() {
  if (!pubYearsAvailable.length) return [null, null];
  const max = pubYearsAvailable[pubYearsAvailable.length - 1];
  return [max - 10, max];
}

function encodePubGroups(groups) {
  const parts = [];
  for (const g of ['conference', 'journal', 'other']) {
    for (const v of groups[g]) parts.push(`${PUB_GROUP_SHORT[g]}:${v}`);
  }
  return parts.join(',');
}

function decodePubGroups(str) {
  const out = { conference: new Set(), journal: new Set(), other: new Set() };
  if (!str) return out;
  for (const item of str.split(',')) {
    const colon = item.indexOf(':');
    if (colon < 0) continue;
    const group = PUB_GROUP_LONG[item.slice(0, colon)];
    if (group) out[group].add(item.slice(colon + 1));
  }
  return out;
}

// includeDefaults=true spells every non-empty filter out, producing the
// self-documenting form used by the Share button. includeDefaults=false is
// the terse address-bar form: anything matching its default is omitted so a
// vanilla visit shows no query string. Fields with empty defaults (sub,
// xsub, xvenue, state, q, expand) are written only when the user has set
// them — there's no "default value" to spell out for those.
function buildUrlParams({ includeDefaults = false } = {}) {
  const p = new URLSearchParams();
  if (includeDefaults || !setsEqual(activeCategories, URL_DEFAULTS.cat)) {
    p.set('cat', [...activeCategories].join(','));
  }
  if (activeSubfields.size) p.set('sub', [...activeSubfields].join(','));
  if (excludedSubfields.size) p.set('xsub', [...excludedSubfields].join(','));
  if (includeDefaults || subfieldScope !== URL_DEFAULTS.scope) p.set('scope', subfieldScope);
  if (activeState) p.set('state', activeState);
  if (searchQuery) p.set('q', searchQuery);
  if (includeDefaults || currentView !== URL_DEFAULTS.view) p.set('view', currentView);

  let venueDiff = false;
  for (const g of ['conference', 'journal', 'other']) {
    if (!setsEqual(pubIncludes[g], URL_DEFAULTS.pubInc[g])) { venueDiff = true; break; }
  }
  if (includeDefaults || venueDiff) p.set('venue', encodePubGroups(pubIncludes));
  const xvenueCount = pubExcludes.conference.size + pubExcludes.journal.size + pubExcludes.other.size;
  if (xvenueCount) p.set('xvenue', encodePubGroups(pubExcludes));

  const [defFrom, defTo] = defaultPubYearRange();
  if (includeDefaults || pubYearFrom !== defFrom) {
    p.set('yfrom', pubYearFrom == null ? '' : String(pubYearFrom));
  }
  if (includeDefaults || pubYearTo !== defTo) {
    p.set('yto', pubYearTo == null ? '' : String(pubYearTo));
  }
  if (includeDefaults || pubMinCites !== URL_DEFAULTS.minCites) {
    p.set('mincite', String(pubMinCites));
  }

  if (includeDefaults) {
    p.set('sort', collegeSort
      ? (collegeSort.dir === -1 ? collegeSort.key + '_desc' : collegeSort.key)
      : 'default');
  } else if (collegeSort) {
    p.set('sort', collegeSort.dir === -1 ? collegeSort.key + '_desc' : collegeSort.key);
  }
  if (expandAllOn) p.set('expand', '1');
  return p;
}

// URLSearchParams escapes commas to %2C; commas are URL-safe sub-delims and
// we use them as in-value list separators, so unescape for readability.
function paramsToQuery(p) {
  return p.toString().replace(/%2C/g, ',');
}

function currentUrl() {
  const qs = paramsToQuery(buildUrlParams());
  return location.origin + location.pathname + (qs ? '?' + qs : '');
}

function shareUrl() {
  const qs = paramsToQuery(buildUrlParams({ includeDefaults: true }));
  return location.origin + location.pathname + (qs ? '?' + qs : '');
}

let _urlSyncQueued = false;
function syncUrl() {
  if (_urlSyncQueued) return;
  _urlSyncQueued = true;
  requestAnimationFrame(() => {
    _urlSyncQueued = false;
    const target = currentUrl();
    if (target !== location.href) history.replaceState(null, '', target);
  });
}

function applyUrlState() {
  const p = new URLSearchParams(location.search);

  if (p.has('cat')) {
    activeCategories = new Set(p.get('cat').split(',').filter(Boolean));
  }
  if (p.has('sub')) {
    activeSubfields = new Set(p.get('sub').split(',').filter(Boolean));
  }
  if (p.has('xsub')) {
    excludedSubfields = new Set(p.get('xsub').split(',').filter(Boolean));
  }
  if (p.has('scope')) {
    const v = p.get('scope');
    if (VALID_SCOPE.has(v)) subfieldScope = v;
  }
  if (p.has('state')) activeState = p.get('state') || '';
  if (p.has('q')) {
    searchQuery = p.get('q');
    searchDraft = searchQuery;
  }
  if (p.has('view')) {
    const v = p.get('view');
    if (VALID_VIEW.has(v)) currentView = v;
  }
  if (p.has('venue')) pubIncludes = decodePubGroups(p.get('venue'));
  if (p.has('xvenue')) pubExcludes = decodePubGroups(p.get('xvenue'));
  if (p.has('yfrom')) {
    const raw = p.get('yfrom');
    if (raw === '') pubYearFrom = null;
    else {
      const y = parseInt(raw, 10);
      if (Number.isFinite(y)) pubYearFrom = y;
    }
  }
  if (p.has('yto')) {
    const raw = p.get('yto');
    if (raw === '') pubYearTo = null;
    else {
      const y = parseInt(raw, 10);
      if (Number.isFinite(y)) pubYearTo = y;
    }
  }
  if (p.has('mincite')) {
    const n = parseInt(p.get('mincite'), 10);
    pubMinCites = Number.isFinite(n) && n > 0 ? n : 0;
  }
  if (p.has('sort')) {
    const s = p.get('sort');
    if (s === 'default') {
      collegeSort = null;
    } else {
      const dir = s.endsWith('_desc') ? -1 : 1;
      const key = s.replace(/_desc$/, '');
      if (key === 'rank') {
        // Institution: ascending is the resting default (collegeSort=null), so
        // only the descending state is materialized.
        collegeSort = dir === -1 ? { key: 'rank', dir: -1, clicks: 1 } : null;
      } else if (VALID_SORT_KEYS.has(key)) {
        // Reconstruct the click count from the direction so the 3-click cycle
        // stays consistent across a shared-URL reload: a numeric column's first
        // click goes descending, the second flips to ascending, the third
        // clears back to default.
        collegeSort = { key, dir, clicks: dir === -1 ? 1 : 2 };
      }
    }
  }
  if (p.get('expand') === '1') expandAllOn = true;

  // Auto-open the advanced bar when the URL pre-applies any advanced filter,
  // so the visitor can see what's been set.
  const [defFrom, defTo] = defaultPubYearRange();
  let pubFiltersCustom = false;
  for (const g of ['conference', 'journal', 'other']) {
    if (!setsEqual(pubIncludes[g], URL_DEFAULTS.pubInc[g]) || pubExcludes[g].size) {
      pubFiltersCustom = true;
      break;
    }
  }
  const advActive = activeSubfields.size || excludedSubfields.size ||
    subfieldScope !== URL_DEFAULTS.scope || activeState ||
    pubYearFrom !== defFrom || pubYearTo !== defTo || pubFiltersCustom ||
    pubMinCites !== URL_DEFAULTS.minCites;
  if (advActive) {
    advancedExpanded = true;
    const bar = document.getElementById('advanced-bar');
    if (bar) bar.classList.remove('collapsed');
  }
}

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

// ── share link ─────────────────────────────────────────────────────────────
function flashShareCopied(label) {
  const btn = document.getElementById('share-btn');
  if (!btn) return;
  const fb = btn.querySelector('.action-feedback');
  if (fb && label) fb.textContent = label;
  btn.classList.add('copied');
  clearTimeout(btn._copiedTimer);
  btn._copiedTimer = setTimeout(() => btn.classList.remove('copied'), 1500);
}

document.getElementById('share-btn').addEventListener('click', async () => {
  // If the user is mid-typing in the search box, commit the draft so the
  // shared URL captures the current query rather than the previous one.
  if (searchDraft !== searchQuery) {
    searchQuery = searchDraft;
    if (searchTimer) { clearTimeout(searchTimer); searchTimer = null; }
    renderAll();
  }
  const url = shareUrl();
  let ok = false;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try { await navigator.clipboard.writeText(url); ok = true; } catch (_) {}
  }
  if (!ok) {
    const ta = document.createElement('textarea');
    ta.value = url;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); ok = true; } catch (_) {}
    document.body.removeChild(ta);
  }
  flashShareCopied(ok ? 'Copied!' : 'Copy failed');
  track('share', 'share', ok ? 'copy' : 'copy_fail');
});

// ── export to JSON ───────────────────────────────────────────────────────────
function flashExportSaved(label) {
  const btn = document.getElementById('export-btn');
  if (!btn) return;
  const fb = btn.querySelector('.action-feedback');
  if (fb && label) fb.textContent = label;
  btn.classList.add('copied');
  clearTimeout(btn._copiedTimer);
  btn._copiedTimer = setTimeout(() => btn.classList.remove('copied'), 1500);
}

// Serialize the current filtered + ordered dashboard. Mirrors what's on screen:
// the same college ordering (sortedColleges) and ranks as renderColleges, each
// college's filtered faculty, and its publications/courses passing the active
// pub/subfield/search filters. Internal `_`-prefixed working fields (search
// strings, match-link back-references, Sets) are dropped via the replacer.
function buildExportData() {
  const ordered = sortedColleges(currentAggregatedColleges());
  const ranks = computeCollegeRanks(ordered);
  const colleges = ordered.map((c, idx) => {
    const links = collegeLinks[c.name] || {};
    const pubs = (collegePublications[c.name] || []).filter(pubVisible);
    const sched = courseSchedules[c.name];
    const courses = sched?.courses ? sched.courses.filter(courseVisible) : [];
    // `course.offered`/`instructors` are positional arrays parallel to this
    // `terms` axis (sorted year asc, then F→W→S→Su), so the export is only
    // decodable when the term axis travels alongside the courses.
    const terms = sched?.terms ?? null;
    return {
      rank: ranks[idx],
      name: c.name,
      state: links.state ?? null,
      faculty_count: c.total,
      electives: c.electives ?? null,
      filtered_courses: c.filtered_courses ?? null,
      papers: c.papers ?? null,
      majors_4yr: c.grads ?? null,
      grad_per_faculty: c.grad_fac ?? null,
      program_url: links.program_url ?? null,
      faculty_url: links.faculty_url ?? null,
      schedule_url: links.schedule_url ?? null,
      publications_url: links.publications_url ?? null,
      faculty: c.faculty,
      publications: pubs,
      terms,
      courses,
    };
  });
  return {
    generated_at: new Date().toISOString(),
    source: location.origin + location.pathname,
    share_url: shareUrl(),
    filters: {
      search: searchQuery || null,
      state: activeState || null,
      job_titles: [...activeCategories],
      subfield_scope: subfieldScope,
      subfields_included: [...activeSubfields],
      subfields_excluded: [...excludedSubfields],
      venue_includes: {
        conference: [...pubIncludes.conference],
        journal: [...pubIncludes.journal],
        other: [...pubIncludes.other],
      },
      pub_year_from: pubYearFrom,
      pub_year_to: pubYearTo,
      pub_min_cites: pubMinCites,
    },
    college_count: colleges.length,
    faculty_count: colleges.reduce((s, c) => s + c.faculty_count, 0),
    colleges,
  };
}

document.getElementById('export-btn').addEventListener('click', () => {
  // Commit a mid-typing search draft so the export captures the current query.
  if (searchDraft !== searchQuery) {
    searchQuery = searchDraft;
    if (searchTimer) { clearTimeout(searchTimer); searchTimer = null; }
    renderAll();
  }
  let ok = false;
  try {
    const json = JSON.stringify(
      buildExportData(),
      (k, v) => (k.startsWith('_') ? undefined : v),
      2,
    );
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'cslac.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    ok = true;
  } catch (_) {}
  flashExportSaved(ok ? 'Saved!' : 'Export failed');
  track('export', 'export', ok ? 'json' : 'json_fail');
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
      grads: d.majors ?? null,
    });
    collegeLinks[name] = {
      state: d.state ?? null,
      program_url: d.program_url ?? null,
      faculty_url: d.faculty_url ?? null,
      schedule_url: d.schedule_url ?? null,
      publications_url: d.publications_url ?? null,
    };
    if (d.terms) {
      courseSchedules[name] = {
        college: name, terms: d.terms, courses: d.courses,
        minCoreLevel: minCoreLevel(d.courses),
      };
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
    const collegeBits = [c.name, displayCollegeName(c.name), stateCode, stateName].filter(Boolean).join(' ');
    for (const f of c.faculty) {
      f._interestsSet = new Set(
        (f.interests || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
      );
      // `_nameSearch` is name only — drives the "expand to pubs + courses"
      // path. `_search` adds title/interests/college, used for the weaker
      // "show this faculty as a row" path. We append the short labels too
      // so a query like "ML" or "HCI" still hits the right faculty.
      f._nameSearch = (f.name || '').toLowerCase();
      const interestShorts = (f.interests || '')
        .split(',')
        .map(s => CS_SUBFIELD_SHORT_LABELS[s.trim()])
        .filter(Boolean);
      f._search = [f.name, f.title, f.interests, ...interestShorts, c.name, displayCollegeName(c.name)]
        .filter(Boolean).join(' ').toLowerCase();
    }
    c._search = collegeBits.toLowerCase();
    c.electives = recentCourseCount(courseSchedules[c.name], isElective);
    // GRAD:FAC: CS majors graduated over the last 4 years divided by the number
    // of tenured + tenure-track faculty. Deliberately fixed — independent of the
    // job-title / subfield / search filters — so it never shifts as the user
    // filters (aggregateCollege carries it through unchanged). Rounded to the
    // nearest integer so display, sort, and tie-ranks agree, and rendered as an
    // "N:1" ratio in buildCollegeRow; null (→ "—") when there's no degree data,
    // zero grads, or no tenure-line faculty.
    const ttCount = c.faculty.filter(
      f => f.category === 'tenured' || f.category === 'tenure_track').length;
    c.grad_fac = (c.grads > 0 && ttCount > 0)
      ? Math.round(c.grads / ttCount)
      : null;
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
      p._subfieldsSet = new Set(p.subfields || []);
      // Cross-college dedup key for the top-bar Papers count. Mirrors the
      // Python scraper's `_norm_title`: lowercase, non-alphanumerics → space,
      // trimmed. The same paper with matched faculty at multiple LACs ends
      // up as one row per college, so we collapse those for the global stat.
      p._dedupKey = (p.title || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
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

  applyUrlState();
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

  const categoryChipsHtml = CATEGORIES.map(c => {
    const on = activeCategories.has(c.key);
    return `<button class="filter-chip ${on ? 'active' : ''}" data-cat="${c.key}">
      ${c.label}<span class="filter-chip-count">${counts[c.key]}</span>
    </button>`;
  }).join('');

  bar.innerHTML =
    `<span class="filter-label">Show</span>` +
    `<div class="cs-dropdown" id="view-dd">
       <button class="cs-dropdown-btn" type="button">${viewLabel}</button>
       <div class="cs-dropdown-list">${viewItems}</div>
     </div>` +
    `<span class="category-chips">${categoryChipsHtml}</span>` +
    `<span class="search-wrap${searchDraft ? '' : ' empty'}">
       <input type="text" class="search-input" id="search-input" placeholder="Search…"
         aria-label="Search faculty, publications, and courses" value="${esc(searchDraft)}" />
       <button type="button" class="search-clear" id="search-clear" aria-label="Clear search" title="Clear search">
         <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
           <line x1="3.5" y1="3.5" x2="8.5" y2="8.5" />
           <line x1="8.5" y1="3.5" x2="3.5" y2="8.5" />
         </svg>
       </button>
     </span>` +
    `<button class="expand-toggle" id="advanced-toggle">${advIcon}Advanced filter</button>` +
    `<button class="expand-toggle" id="expand-toggle">${expandIcon}${expandLabel}</button>`;

  if (searchHadFocus) {
    const el = document.getElementById('search-input');
    el.focus();
    try { el.setSelectionRange(searchCaret[0], searchCaret[1]); } catch (_) {}
  }

  bar.querySelectorAll('.filter-chip[data-cat]').forEach(btn => {
    btn.addEventListener('click', () => {
      const k = btn.dataset.cat;
      const wasActive = activeCategories.has(k);
      if (wasActive) activeCategories.delete(k);
      else activeCategories.add(k);
      track('filter', 'category', wasActive ? 'clear' : 'include', k);
      buildFilterBar();
      buildAdvancedBar();
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
  const searchWrap = searchEl.closest('.search-wrap');
  const syncSearchEmpty = () => {
    if (searchWrap) searchWrap.classList.toggle('empty', !searchDraft);
  };
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
    syncSearchEmpty();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(commitSearch, 1000);
  });
  searchEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitSearch();
    } else if (e.key === 'Escape' && searchDraft) {
      e.preventDefault();
      searchDraft = '';
      searchEl.value = '';
      syncSearchEmpty();
      commitSearch();
    }
  });
  const searchClearBtn = document.getElementById('search-clear');
  if (searchClearBtn) {
    searchClearBtn.addEventListener('mousedown', e => e.preventDefault());
    searchClearBtn.addEventListener('click', () => {
      if (!searchDraft && !searchQuery) {
        searchEl.focus();
        return;
      }
      searchDraft = '';
      searchEl.value = '';
      syncSearchEmpty();
      track('filter', 'search', 'clear', '');
      commitSearch();
      searchEl.focus();
    });
  }

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
        syncUrl();
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
function buildAdvancedBar() {
  const bar = document.getElementById('advanced-bar');
  const scopeHint = subfieldScope === 'faculty'
    ? `Apply to <span class="hint-scope">each faculty</span> — only show people whose interests match.`
    : `Apply to <span class="hint-scope">whole schools</span> — only show schools that have such faculty.`;
  const interactHint = `Click to <span class="hint-include">include</span>, again to <span class="hint-exclude">exclude</span>, once more to clear.`;

  // Per-group chip HTML, with each group's chips sorted by their display label.
  const subfieldChip = s => {
    const cls = activeSubfields.has(s) ? 'active'
      : excludedSubfields.has(s) ? 'exclude'
      : '';
    const shortLabel = shortSubfieldLabel(s);
    const titleAttr = shortLabel !== s ? ` title="${esc(s)}"` : '';
    return `<button class="filter-chip ${cls}" data-subfield="${esc(s)}"${titleAttr}>
      ${esc(shortLabel)}
    </button>`;
  };
  const subfieldGroupsHtml = CS_SUBFIELD_GROUPS.map(g => {
    const sorted = [...g.subfields].sort((a, b) =>
      shortSubfieldLabel(a).localeCompare(shortSubfieldLabel(b))
    );
    return `<div class="pub-filter-group subfield-group"><span class="pub-filter-label">${esc(g.label)}</span>${sorted.map(subfieldChip).join('')}</div>`;
  }).join('');

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

  const catCounts = categoryCounts();
  const jobTitleChipsHtml = CATEGORIES.map(c => {
    const on = activeCategories.has(c.key);
    return `<button class="filter-chip ${on ? 'active' : ''}" data-cat="${c.key}">
      ${esc(c.label)}<span class="filter-chip-count">${catCounts[c.key]}</span>
    </button>`;
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
       <div class="cs-dropdown" id="state-dd">
         <button class="cs-dropdown-btn" type="button">${stateLabel}</button>
         <div class="cs-dropdown-list">${stateItems}</div>
       </div>
     </div>` +
    `<div class="adv-row adv-row-jobtitle">
       <span class="filter-label">Job Title</span>
       ${jobTitleChipsHtml}
     </div>` +
    `<div class="adv-row adv-row-subfields">
       <span class="filter-label" title="Filter for faculty, courses, and papers based on their fields. Derived from csrankings.org with a few additions.">Subfields</span>` +
       subfieldGroupsHtml +
    `</div>` +
    `<div class="adv-row adv-row-pubs">
       <span class="filter-label">Papers</span>
       <div class="pub-filter-groups">` +
       PUB_FILTER_GROUPS.map(g => {
         const chips = g.values.map(v => {
           const isObj = typeof v === 'object';
           const val = isObj ? v.key : v;
           const label = isObj ? v.label : v;
           const cls = pubIncludes[g.key].has(val) ? 'active'
             : pubExcludes[g.key].has(val) ? 'exclude'
             : '';
           const tip = (isObj && v.tooltip) || VENUE_RANK_TOOLTIPS[val];
           const titleAttr = tip ? ` title="${esc(tip)}"` : '';
           return `<button class="pub-filter-chip ${cls}" data-group="${g.key}" data-value="${esc(val)}"${titleAttr}>${esc(label)}</button>`;
         }).join('');
         return `<div class="pub-filter-group"><span class="pub-filter-label">${g.label}</span>${chips}</div>`;
       }).join('') +
       `<div class="pub-filter-group">
          <span class="pub-filter-label">Year</span>
          <div class="cs-dropdown" id="pub-year-from-dd">
            <button class="cs-dropdown-btn" type="button">${pubYearFrom != null ? pubYearFrom : 'From'}</button>
            <div class="cs-dropdown-list">
              <div class="cs-dropdown-item${pubYearFrom == null ? ' selected' : ''}" data-value="">From</div>
              ${pubYearsAvailable.map(y => `<div class="cs-dropdown-item${y === pubYearFrom ? ' selected' : ''}" data-value="${y}">${y}</div>`).join('')}
            </div>
          </div>
          <span class="pub-year-dash">–</span>
          <div class="cs-dropdown" id="pub-year-to-dd">
            <button class="cs-dropdown-btn" type="button">${pubYearTo != null ? pubYearTo : 'To'}</button>
            <div class="cs-dropdown-list">
              <div class="cs-dropdown-item${pubYearTo == null ? ' selected' : ''}" data-value="">To</div>
              ${pubYearsAvailable.map(y => `<div class="cs-dropdown-item${y === pubYearTo ? ' selected' : ''}" data-value="${y}">${y}</div>`).join('')}
            </div>
          </div>
        </div>` +
       `<div class="pub-filter-group">
          <span class="pub-filter-label" title="Only show papers with at least this many citations. 0 shows all papers.">Min. cite</span>
          <input type="number" class="pub-num-input" id="pub-min-cites" min="0" step="1"
                 inputmode="numeric" aria-label="Minimum citations per paper"
                 value="${pubMinCites}" />
        </div>` +
    `</div></div>` +
    `<div class="adv-row"><span class="adv-hint-inline">${interactHint}</span></div>`
  ;

  bar.querySelectorAll('.filter-chip[data-cat]').forEach(btn => {
    btn.addEventListener('click', () => {
      const k = btn.dataset.cat;
      const wasActive = activeCategories.has(k);
      if (wasActive) activeCategories.delete(k);
      else activeCategories.add(k);
      track('filter', 'category', wasActive ? 'clear' : 'include', k);
      buildAdvancedBar();
      buildFilterBar();
      renderAll();
    });
  });

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

  // Min-cites box. Debounced like the search input, and deliberately does NOT
  // call buildAdvancedBar() on commit — rebuilding the bar mid-typing would
  // blow away focus and the caret.
  const minCitesEl = document.getElementById('pub-min-cites');
  const commitMinCites = (normalize = false) => {
    clearTimeout(pubMinCitesTimer);
    pubMinCitesTimer = null;
    const n = parseInt(minCitesEl.value, 10);
    const next = Number.isFinite(n) && n > 0 ? n : 0;
    // Snap a blank/garbage/negative entry back to the value we actually applied.
    if (normalize && minCitesEl.value !== String(next)) minCitesEl.value = String(next);
    if (next === pubMinCites) return;
    pubMinCites = next;
    track('filter', 'publication_min_cites', next ? 'set' : 'clear', String(next));
    buildFilterBar();
    renderAll();
  };
  minCitesEl.addEventListener('input', () => {
    clearTimeout(pubMinCitesTimer);
    pubMinCitesTimer = setTimeout(commitMinCites, 500);
  });
  minCitesEl.addEventListener('change', () => commitMinCites());
  minCitesEl.addEventListener('blur', () => commitMinCites(true));
  minCitesEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitMinCites(true);
    }
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
  syncUrl();
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
  if (!p.venue) return false;
  if (pubYearFrom != null && (p.year == null || p.year < pubYearFrom)) return false;
  if (pubYearTo != null && (p.year == null || p.year > pubYearTo)) return false;
  if (pubMinCites > 0 && (p.cites ?? 0) < pubMinCites) return false;
  const t = p.pub_type;
  let group, value;
  if ((t === 'conference' || t === 'journal') && p.venue_ranking) {
    group = t;
    value = p.venue_ranking;
  } else if (t === 'workshop' || t === 'preprint') {
    group = 'other';
    value = t;
  } else {
    // Unranked conferences/journals, books, and everything else fold into
    // the single "Unranked" chip in the Other group.
    group = 'other';
    value = 'unranked';
  }
  if (pubExcludes[group].has(value)) return false;
  const anyInc = pubIncludes.conference.size || pubIncludes.journal.size || pubIncludes.other.size;
  if (anyInc && !pubIncludes[group].has(value)) return false;
  // Subfield gate (independent of the Faculty/School scope toggle):
  // - any excluded subfield matching this pub hides it
  // - if any subfield is included, the pub must hit at least one
  // - untagged pubs are hidden the moment any include is active
  const sfs = p._subfieldsSet;
  if (excludedSubfields.size && sfs) {
    for (const s of excludedSubfields) {
      if (sfs.has(s)) return false;
    }
  }
  if (activeSubfields.size) {
    if (!sfs || sfs.size === 0) return false;
    let hit = false;
    for (const s of activeSubfields) {
      if (sfs.has(s)) { hit = true; break; }
    }
    if (!hit) return false;
  }
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

// How many academic years the Courses column counts over (the college's most
// recent N years present in the schedule).
const RECENT_YEARS = 2;

// School-specific rule: courses offered only in these terms don't count toward
// the college's elective total. Williams' January "Winter Study" term is mostly
// informal one-off courses (Magic: the Gathering, Fiber Arts) rather than
// regular CS electives, so it would otherwise inflate the count relative to
// schools with no Winter term. The courses still appear in the schedule grid;
// they just don't contribute to the count.
const UNCOUNTED_TERMS = { 'Williams College': new Set(['W']) };

// The numeric level of a course code (the first run of digits): "COMSC-151" →
// 151, "CS 314" → 314, "COMSC-133DV" → 133. Null when the code has no digits.
function codeLevel(code) {
  const m = String(code || '').match(/\d+/);
  return m ? parseInt(m[0], 10) : null;
}

// The lowest level among a college's `Core` courses (intro/data-structures/
// algorithms — the shared foundation). Courses numbered below this are
// pre-major / non-major service courses (e.g. "Computing & the Digital World")
// that sit beneath the major's entry point and shouldn't count as electives,
// even when classified into a subfield. Null when the college has no Core data.
function minCoreLevel(courses) {
  let min = null;
  for (const c of courses || []) {
    if (c.category !== 'Core') continue;
    const lvl = codeLevel(c.code);
    if (lvl != null && (min == null || lvl < min)) min = lvl;
  }
  return min;
}

// Count unique courses actually offered (a non-zero `offered` cell) in the
// college's most recent RECENT_YEARS academic years, optionally restricted to
// courses matching `predicate` (e.g. the active search + subfield filter).
function recentCourseCount(schedule, predicate) {
  if (!schedule || !schedule.terms?.length || !schedule.courses?.length) return null;
  const recent = new Set(
    [...new Set(schedule.terms.map(t => t.year))].sort().slice(-RECENT_YEARS)
  );
  const uncounted = UNCOUNTED_TERMS[schedule.college];
  const idxs = schedule.terms
    .map((t, i) => (recent.has(t.year) && !(uncounted && uncounted.has(t.term))) ? i : -1)
    .filter(i => i >= 0);
  const minCore = schedule.minCoreLevel;
  let count = 0;
  for (const c of schedule.courses) {
    if (predicate && !predicate(c)) continue;
    // Below the major's lowest Core course → not an elective (see minCoreLevel).
    if (minCore != null) {
      const lvl = codeLevel(c.code);
      if (lvl != null && lvl < minCore) continue;
    }
    if (idxs.some(i => c.offered[i])) count++;
  }
  return count;
}

// Debug helper: explain whether a single course contributes to a college's
// Electives total, mirroring the per-course decision inside recentCourseCount
// (isElective category gate + below-lowest-Core gate + offered-in-recent-window
// gate, minus the Williams Winter exclusion). Returns the boolean plus the list
// of reasons it's excluded (empty when counted).
function electiveCountStatus(course, schedule) {
  const recent = new Set(
    [...new Set(schedule.terms.map(t => t.year))].sort().slice(-RECENT_YEARS)
  );
  const uncounted = UNCOUNTED_TERMS[schedule.college];
  const idxs = schedule.terms
    .map((t, i) => (recent.has(t.year) && !(uncounted && uncounted.has(t.term))) ? i : -1)
    .filter(i => i >= 0);
  const reasons = [];
  if (!isElective(course)) {
    reasons.push(`category "${course.category || '—'}" is non-elective`);
  }
  const minCore = schedule.minCoreLevel;
  const lvl = codeLevel(course.code);
  if (minCore != null && lvl != null && lvl < minCore) {
    reasons.push(`code level ${lvl} is below the lowest Core course (${minCore})`);
  }
  if (!idxs.some(i => course.offered[i])) {
    reasons.push(`not offered in the last ${RECENT_YEARS} academic years`);
  }
  return { counted: reasons.length === 0, reasons };
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
// Subfield gate for a course, mirroring the publication gate (and independent
// of the Faculty/School scope toggle). A course's `category` is one of the 32
// CS subfields or a meta bucket (Core/Misc/Other/Unknown); the meta buckets
// aren't filter chips, so any active subfield include hides them, which is what
// we want — filtering "Machine learning" should surface only ML courses.
function courseSubfieldVisible(c) {
  const cat = c.category;
  if (excludedSubfields.size && cat && excludedSubfields.has(cat)) return false;
  if (activeSubfields.size && (!cat || !activeSubfields.has(cat))) return false;
  return true;
}

function courseVisible(c) {
  return searchHitCourse(c) && courseSubfieldVisible(c);
}

// An "elective" is a real CS lecture course beyond the shared foundation. We
// exclude three category meta-buckets (set by course_classifier.py): `Core`
// (intro programming, data structures, discrete math, the standard algorithms
// course, computer organization — the sequence every CS program shares; note
// advanced/applied algorithms and theory of computation stay electives), `Misc`
// (independent study / thesis / seminar / lab — not a real lecture course), and
// `Unknown` (non-CS courses
// like Calculus swept in by cross-listing). Everything else — the 32 CS
// subfields plus `Other` — counts. Drives the Electives column's resting count
// (a subfield filter already restricts to electives; a text search may surface
// a matched foundational course, mirroring how the other columns behave).
const NON_ELECTIVE_CATEGORIES = new Set(['Core', 'Misc', 'Unknown']);
function isElective(c) {
  return !NON_ELECTIVE_CATEGORIES.has(c.category);
}

function aggregateCollege(college) {
  const fac = filteredFaculty(college);
  return {
    ...college,
    faculty: fac,
    total: fac.length,
    papers: filteredPubCount(college.name),
    // Unique courses offered in the last RECENT_YEARS years matching the active
    // search + subfield filter — drives the Courses column value, its sort, and
    // (when searching) whether a course-only match keeps the college's row.
    filtered_courses: recentCourseCount(courseSchedules[college.name], courseVisible),
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
  const seen = new Set();
  let total = 0;
  for (const pubs of Object.values(collegePublications)) {
    for (const p of pubs) {
      if (!pubVisible(p)) continue;
      if (p._dedupKey) {
        if (seen.has(p._dedupKey)) continue;
        seen.add(p._dedupKey);
      }
      total++;
    }
  }
  animateStat(document.getElementById('stat-papers'), total);

  const parts = [];
  const anyIncluded = pubIncludes.conference.size || pubIncludes.journal.size || pubIncludes.other.size;
  for (const g of PUB_FILTER_GROUPS) {
    for (const v of g.values) {
      const isObj = typeof v === 'object';
      const val = isObj ? v.key : v;
      const label = isObj ? v.label : v;
      if (pubIncludes[g.key].has(val)) parts.push(label);
      else if (!anyIncluded && pubExcludes[g.key].has(val)) parts.push('−' + label);
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
  if (pubMinCites > 0) {
    parts.push(`≥${pubMinCites} cite${pubMinCites === 1 ? '' : 's'}`);
  }
  const suffix = parts.length ? ` (${parts.join(', ')})` : '';
  // Suffix lives in its own span so the mobile breakpoint can hide just the
  // active-filter values while keeping the "Papers" label.
  document.getElementById('stat-papers-label').innerHTML =
    `Papers<span class="stat-filter-suffix">${esc(suffix)}</span>`;
}

// The colleges currently surviving the active filters (state, school-scope,
// job-title, subfield, search), each with its filtered faculty + counts. Used
// by renderAll and by the JSON export so both reflect the same filtered view.
function currentAggregatedColleges() {
  const searching = !!searchQuery.trim();
  // An active subfield include gates pubs and courses by subfield too (see
  // pubVisibleBase / courseSubfieldVisible), so — like a search — it can match a
  // college through its papers or courses even when no faculty's interests do.
  const subfieldIncluding = activeSubfields.size > 0;
  return allColleges
    .filter(c => !activeState || collegeLinks[c.name]?.state === activeState)
    .filter(passesSchoolFilter)
    .map(aggregateCollege)
    // Keep a college if any of {faculty, pubs, courses} has a match — so a
    // search or subfield filter that hits a venue, course, or paper surfaces the
    // college even when no faculty row matches. (In School scope,
    // passesSchoolFilter has already restricted to schools with matching
    // faculty, so this can't re-add one there.)
    .filter(c => c.total > 0
      || ((searching || subfieldIncluding) && ((c.papers ?? 0) > 0 || (c.filtered_courses ?? 0) > 0)));
}

function renderAll() {
  // Refresh the categorical search match sets before any filtered lookups.
  _searchResult = computeSearchResult();
  const aggregated = currentAggregatedColleges();
  const totalFaculty = aggregated.reduce((s, c) => s + c.total, 0);
  animateStat(document.getElementById('stat-colleges'), aggregated.length);
  animateStat(document.getElementById('stat-faculty'), totalFaculty);
  updatePapersStat();
  renderColleges(aggregated);
  // College rows were rebuilt — re-stamp each row's --summary-h.
  if (typeof updateHeaderH === 'function') updateHeaderH();
  syncUrl();
}

// ── college headers ────────────────────────────────────────────────────────
function buildCollegeHeaders() {
  const row = document.getElementById('col-headers');
  row.innerHTML = COLLEGE_COLS.map((col, i) => {
    let active, arrow;
    if (col.key === 'rank') {
      // Institution is the resting default sort: always highlighted, ascending
      // (↑) unless explicitly reversed to descending (↓). It only drops to the
      // neutral ↕ state while another column owns the active sort.
      active = !collegeSort || collegeSort.key === 'rank';
      const desc = collegeSort && collegeSort.key === 'rank' && collegeSort.dir === -1;
      arrow = active ? (desc ? '↓' : '↑') : '↕';
    } else {
      active = collegeSort && col.key === collegeSort.key;
      arrow = active ? (collegeSort.dir === 1 ? '↑' : '↓') : '↕';
    }
    const tip = col.tooltip ? ` title="${esc(col.tooltip)}"` : '';
    return `<div class="th ${active ? 'sorted' : ''}" data-col="${col.key}"${tip}>
      <span class="th-label">${col.label}<span class="sort-icon">${arrow}</span></span>
    </div>`;
  }).join('');

  row.querySelectorAll('.th-label').forEach(label => {
    label.addEventListener('click', () => {
      const key = label.closest('.th').dataset.col;
      if (key === 'rank') {
        // Institution is a 2-state toggle, not part of the 3-click cycle:
        // ascending (the resting default, stored as collegeSort=null) ⇄
        // descending. Any non-default state goes back to ascending; ascending
        // reverses to descending. It never enters the neutral/unsorted state.
        collegeSort = collegeSort ? null : { key: 'rank', dir: -1, clicks: 1 };
      } else if (collegeSort && collegeSort.key === key) {
        // 3-click cycle on the same column: 1st click sorts (set above),
        // 2nd flips direction, 3rd clears back to the default ordering.
        collegeSort.clicks += 1;
        if (collegeSort.clicks >= 3) collegeSort = null;
        else collegeSort.dir *= -1;
      } else {
        collegeSort = { key, dir: -1, clicks: 1 };
      }
      track('sort', 'college',
        collegeSort ? (collegeSort.dir === 1 ? 'asc' : 'desc') : 'default', key);
      buildCollegeHeaders();
      renderAll();
    });
  });
}

// ── college sort ───────────────────────────────────────────────────────────
function collegeSortValueFn() {
  // Sort by the filtered course count whenever courses are being filtered —
  // by search or by an active subfield filter — matching the Courses column's
  // displayed value (see courseFiltering in buildCollegeRow).
  const courseFiltering = !!searchQuery.trim()
    || activeSubfields.size > 0 || excludedSubfields.size > 0;
  return {
    total:             c => c.total,
    // null when there's no degree data (or 0 grads); the comparator floats
    // those "—" rows to the bottom in both directions (see sortedColleges).
    grads:             c => c.grads || null,
    grad_fac:          c => c.grad_fac,
    electives:         c => (courseFiltering ? c.filtered_courses : c.electives) ?? -1,
    papers:            c => c.papers ?? 0,
  }[collegeSort.key] || (c => c.name);
}

// Default ordering when no single column is actively sorted: Faculty desc,
// then total Electives desc (always the unfiltered count — independent of any
// active course filter), then Papers desc, then 4YR-GRAD desc, with name as
// the final tie-breaker. Missing numeric values sink via the -1 fallback.
const DEFAULT_SORT_VALUE_FNS = [
  c => c.total ?? -1,
  c => c.electives ?? -1,
  c => c.papers ?? 0,
  c => c.grads ?? -1,
];
function defaultCollegeCompare(a, b) {
  for (const fn of DEFAULT_SORT_VALUE_FNS) {
    const av = fn(a), bv = fn(b);
    if (av !== bv) return bv - av; // all descending
  }
  return a.name.localeCompare(b.name);
}

// Value function used for the rank ("#") column. In default mode rows are
// ranked by Faculty (the primary default-sort column); otherwise by the
// actively-sorted column.
function collegeRankValueFn() {
  return collegeSort ? collegeSortValueFn() : (c => c.total ?? -1);
}

function sortedColleges(colleges) {
  if (!collegeSort) return [...colleges].sort(defaultCollegeCompare);
  // The Institution column sorts by row number — i.e. each row's position in
  // the default ordering. Ascending reproduces the default order; descending
  // reverses it.
  if (collegeSort.key === 'rank') {
    return [...colleges].sort((a, b) => collegeSort.dir * defaultCollegeCompare(a, b));
  }
  const fn = collegeSortValueFn();
  return [...colleges].sort((a, b) => {
    const av = fn(a), bv = fn(b);
    if (typeof av === 'string') return collegeSort.dir * av.localeCompare(bv);
    // Rows with no value (null) always sink to the bottom regardless of sort
    // direction — e.g. the "—" rows in the MAJORS / MAJ:FAC columns.
    if (av == null || bv == null) {
      if (av == null && bv == null) return 0;
      return av == null ? 1 : -1;
    }
    return collegeSort.dir * (av - bv);
  });
}

// Competition ranking ("1224"): rows with the same sort-column value share
// a rank; the next distinct value jumps ahead by the size of the tie group.
// e.g. faculty counts 18, 13, 13, 13, 10 → ranks 1, 2, 2, 2, 5. This only
// applies when a single column is actively sorted — in the default
// multi-column ordering each row gets a plain sequential 1, 2, 3, … number.
function computeCollegeRanks(sorted) {
  if (!collegeSort) return sorted.map((_, i) => i + 1);
  // Rank-sort keeps each row's intrinsic default-order number attached, so the
  // "#" column reads 1…N ascending and N…1 descending (not a re-derived rank).
  if (collegeSort.key === 'rank') {
    const n = sorted.length;
    return sorted.map((_, i) => collegeSort.dir === 1 ? i + 1 : n - i);
  }
  const fn = collegeRankValueFn();
  const ranks = new Array(sorted.length);
  let lastVal, lastRank = 0;
  for (let i = 0; i < sorted.length; i++) {
    const v = fn(sorted[i]);
    if (i === 0 || v !== lastVal) {
      lastRank = i + 1;
      lastVal = v;
    }
    ranks[i] = lastRank;
  }
  return ranks;
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
      termOffset: panel?._termOffset,
      pubSort: panel?._pubSort,
    });
  });
  list.innerHTML = '';
  const sorted = sortedColleges(colleges);
  const ranks = computeCollegeRanks(sorted);
  sorted.forEach((college, idx) => {
    list.appendChild(buildCollegeRow(college, idx, preserved.get(college.name), ranks[idx]));
  });
}

function fmt(n) { return n ? n.toLocaleString() : '—'; }

// Friendlier names for colleges whose official name is unwieldy or eclipses
// a more common short name — applied for ALL viewports (used wherever a
// college's full name is displayed; shortCollegeName below then operates on
// this name for the mobile-only form).
const COLLEGE_DISPLAY_NAMES = {
  'The University of the South':           'Sewanee',
  'University of North Carolina Asheville': 'UNC Asheville',
  'University of Virginia--Wise':           'UVA Wise',
  'University of Minnesota Morris':         'UMN Morris',
};
function displayCollegeName(name) {
  return COLLEGE_DISPLAY_NAMES[name] || name;
}

// Mobile-only short form for college names: drops a leading "University of"
// / "The University of the" (e.g. "University of Richmond" → "Richmond"),
// drops a trailing "University" or "College" (e.g. "Bucknell University" →
// "Bucknell", "Carleton College" → "Carleton"), and for "X College (XX)"
// names with a trailing state acronym drops just "College" while keeping
// the acronym (e.g. "Wheaton College (MA)" → "Wheaton (MA)") to save
// horizontal space on narrow viewports.
//
// Special case: "Trinity College" (Hartford, CT) and "Trinity University"
// (San Antonio, TX) would both shorten to the ambiguous "Trinity" — append
// each one's state to disambiguate. "Massachusetts College of Liberal Arts"
// has no shortenable suffix, so it maps to its acronym "MCLA".
function shortCollegeName(name) {
  if (name === 'Trinity College') return 'Trinity (CT)';
  if (name === 'Trinity University') return 'Trinity (TX)';
  // No "University"/trailing-"College" rule below shortens this long name,
  // so use its well-known acronym on narrow viewports.
  if (name === 'Massachusetts College of Liberal Arts') return 'MCLA';
  return name
    .replace(/^(The )?University of (the )?/, '')
    .replace(/\s+University$/, '')
    .replace(/\bUniversity\b/g, 'Univ.')
    .replace(/\s+College(\s+\([A-Z]{2}\))$/, '$1')
    .replace(/\s+College$/, '');
}

// Compact form for narrow mobile columns: 1,640 → "1.6k", 11,245 → "11.2k".
// Numbers under 1000 keep their plain form.
function abbrev(n) {
  if (n < 1000) return n.toLocaleString();
  const r = Math.round(n / 100) / 10;
  return (Number.isInteger(r) ? r.toFixed(0) : r.toFixed(1)) + 'k';
}

// Word-level abbreviations applied to the mobile (small-viewport) form
// of venue names so long titles don't blow up the narrow column. Sorted
// alphabetically — the regex below uses \b boundaries, so prefix pairs
// like Transaction/Transactions don't need a particular order.
const VENUE_ABBREVIATIONS = [
  ['Algorithm',    'Algo.'],
  ['Algorithms',    'Algo.'],
  ["and", "&"],
  ['Application',    'Appl.'],
  ['Applications',   'Appl.'],
  ['Artificial',     'Artf.'],
  ['Association',    'Assoc.'],
  ['Communication',  'Comm.'],
  ['Communications', 'Comm.'],
  ['Computation',  'Comp.'],
  ['Computational',  'Comp.'],
  ['Computer',       'Comput.'],
  ['Computing',      'Comput.'],
  ['Conference',     'Conf.'],
  ['Distributed',      'Dist.'],
  ['Education',      'Edu.'],
  ['Educational',    'Edu.'],
  ['Engineering',    'Eng.'],
  ['Information',    'Info.'],
  ['Intelligence',   'Intell.'],
  ['Interaction',  "Interact'n"],
  ['International',  "Int'l"],
  ['Journal',        'Jrnl.'],
  ['Language', 'Lang.'],
  ['Languages', 'Lang.'],
  ['Magazine',       'Mag.'],
  ['Mathematical',   'Math.'],
  ['Mathematics',    'Math.'],
  ['Operation',    "Operat'n."],
  ['Proceedings',    'Proc.'],
  ['Programming',    'Prog.'],
  ['Research',       'Rsrch.'],
  ['Society',        'Soc.'],
  ['Symposia',       'Symp.'],
  ['Symposium',      'Symp.'],
  ['Technologies',   'Tech.'],
  ['Technology',     'Tech.'],
  ['Transaction',    'Trans.'],
  ['Transactions',   'Trans.'],
  ['Ubiquitous',   'Ubiq.'],
  ['Visualization',   'Vis.'],
  ['Visualizations',   'Vis.'],
  ['Workshop',       'Wksp.'],
  ['Workshops',      'Wksps.'],
];
const VENUE_ABBREV_RE = new RegExp(
  '\\b(' + VENUE_ABBREVIATIONS.map(([w]) => w).join('|') + ')\\b',
  'gi',
);
const VENUE_ABBREV_MAP = (() => {
  const m = new Map();
  for (const [from, to] of VENUE_ABBREVIATIONS) m.set(from.toLowerCase(), to);
  return m;
})();
// Replace long venue words with shorter forms (Proceedings → Proc., etc.).
// Case-insensitive match; if the original was lowercase, the replacement
// is lowercased too so "international workshop" → "int'l wksp.".
function abbreviateVenue(text) {
  if (!text) return text;
  return text.replace(VENUE_ABBREV_RE, (m) => {
    const to = VENUE_ABBREV_MAP.get(m.toLowerCase());
    return m[0] === m[0].toUpperCase() ? to : to[0].toLowerCase() + to.slice(1);
  });
}

// Returns a truncated copy of `text` cut at the last word boundary ≤
// maxChars, or null if the text already fits (no truncation needed) or
// can't be cut cleanly (no usable space, or the cut would land inside
// a `$…$` math block). Used for the mobile-only short forms of title
// and venue so the +/- toggle can sit inline after the literal "…".
function safeTruncateForLines(text, maxChars) {
  if (!text || text.length <= maxChars) return null;
  let inMath = false;
  let lastSpace = -1;
  for (let i = 0; i < maxChars; i++) {
    const ch = text[i];
    if (ch === '$') inMath = !inMath;
    else if (ch === ' ' && !inMath) lastSpace = i;
  }
  if (lastSpace < maxChars * 0.4) return null;
  return text.slice(0, lastSpace);
}

function buildCollegeRow(college, idx, priorOpenState, rank) {
  const div = document.createElement('div');
  div.className = 'college-row';

  // The Electives column counts unique *elective* courses (see isElective —
  // excludes the shared Core/Misc/Unknown buckets) offered in the last
  // RECENT_YEARS academic years; when the user is searching or has an active
  // subfield filter (both gate courses via courseVisible), it shows the count
  // restricted to the matching courses.
  const searching = !!searchQuery.trim();
  const courseFiltering = searching || activeSubfields.size > 0 || excludedSubfields.size > 0;
  const coursesValue = courseFiltering ? college.filtered_courses : college.electives;
  const cpyText  = fmt(coursesValue);
  const fpText   = fmt(college.papers);
  const links   = collegeLinks[college.name] || {};

  const cnEsc = esc(college.name).replace(/'/g, "\\'");
  // The college name itself links to the department website (when we have one);
  // falls back to a plain span otherwise. Same markup/style either way.
  const displayName = displayCollegeName(college.name);
  const nameInner = `<span class="cn-full">${esc(displayName)}</span><span class="cn-short">${esc(shortCollegeName(displayName))}</span>`;
  const nameEl = links.program_url
    ? `<a class="college-name" href="${esc(links.program_url)}" target="_blank" rel="noopener" title="Department website" onclick="track('click_link','link','college_program','${cnEsc}')">${nameInner}</a>`
    : `<span class="college-name">${nameInner}</span>`;
  const logoImg = `<span class="college-logo cl-${collegeSlug(college.name)}" aria-hidden="true"></span>`;

  div.innerHTML = `
    <div class="college-summary">
      <div class="col-grid">
        <div class="td td-name">
          <span class="name-marker">
            <span class="college-num">${rank}</span>
            <span class="chevron">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4,2 8,6 4,10"/>
              </svg>
            </span>
          </span>
          <span class="name-body">
            <span class="name-title">
              ${logoImg}
              ${nameEl}
              ${links.state ? `<span class="college-state">${esc(links.state)}</span>` : ''}
            </span>
          </span>
        </div>
        <div class="td-num">${college.total}</div>
        <div class="td-num ${college.grads ? '' : 'dim'}">${fmt(college.grads)}</div>
        <div class="td-num ${college.grad_fac != null ? '' : 'dim'}">${college.grad_fac != null ? college.grad_fac + ':1' : '—'}</div>
        <div class="td-num ${coursesValue != null && (!courseFiltering || coursesValue > 0) ? '' : 'dim'}">${cpyText}</div>
        <div class="td-num ${college.papers != null && college.papers > 0 ? '' : 'dim'}">${fpText}</div>
      </div>
    </div>
    <div class="faculty-panel">
      <div class="faculty-panel-inner" id="fac-panel-${idx}"></div>
    </div>
  `;

  div.querySelectorAll('a.college-name').forEach(a => {
    a.addEventListener('click', e => e.stopPropagation());
  });

  const panel = div.querySelector(`#fac-panel-${idx}`);
  panel._build = () => buildPanel(panel, college);

  if (priorOpenState) {
    if (priorOpenState.view !== undefined) panel._view = priorOpenState.view;
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
  const scheduleUrl = (collegeLinks[college.name] || {}).schedule_url;
  const pubsUrl = (collegeLinks[college.name] || {}).publications_url;
  if (panel._view === undefined) panel._view = currentView;
  // termOffset is undefined initially; renderCourseTable defaults to the
  // latest TERMS_PER_PAGE window when no offset has been set yet.

  function render() {
    // Read panel._view fresh each render so applyGlobalView's reassignment
    // is picked up. Fall back when the chosen view has no data for this
    // school, so the toggle highlight tracks the actually-rendered table.
    let view = panel._view || currentView;
    if (view === 'courses' && !hasCourses) view = 'faculty';
    if (view === 'publications' && !hasPublications) view = 'faculty';
    // When the (filtered) faculty list is empty but another tab has matching
    // content — e.g. a college kept visible only by a subfield filter's course
    // or paper matches — open that tab instead of an empty "No faculty" list.
    if (view === 'faculty' && college.faculty.length === 0) {
      if (hasCourses && schedule.courses.some(courseVisible)) view = 'courses';
      else if (hasPublications && publications.some(pubVisible)) view = 'publications';
    }

    const coursesBtn = hasCourses
      ? `<button data-view="courses" class="${view === 'courses' ? 'active' : ''}" title="Courses" aria-label="Courses">${ICON_CATALOG}</button>`
      : `<button data-view="courses" class="disabled" disabled title="Course schedule not accessible" aria-label="Course schedule not accessible">${ICON_CATALOG}</button>`;
    const pubsBtn = hasPublications
      ? `<button data-view="publications" class="${view === 'publications' ? 'active' : ''}" title="Papers" aria-label="Papers">${ICON_SCROLL}</button>`
      : `<button data-view="publications" class="disabled" disabled title="No publication data" aria-label="No publication data">${ICON_SCROLL}</button>`;
    const collegeNameEsc = esc(college.name).replace(/'/g, "\\'");
    const sourceLink = facultyUrl
      ? `<a class="faculty-source-link" href="${esc(facultyUrl)}" target="_blank" rel="noopener" onclick="track('click_link','link','faculty_source','${collegeNameEsc}')">source</a>`
      : '';
    // Course-schedule source — the link that used to live in the calendar icon.
    const scheduleSourceLink = (scheduleUrl && hasCourses)
      ? `<a class="faculty-source-link" href="${esc(scheduleUrl)}" target="_blank" rel="noopener" onclick="track('click_link','link','college_schedule','${collegeNameEsc}')">source</a>`
      : '';
    // Publications source — OpenAlex "works" listing of the college's CS papers.
    const pubsSourceLink = (pubsUrl && hasPublications)
      ? `<a class="faculty-source-link" href="${esc(pubsUrl)}" target="_blank" rel="noopener" onclick="track('click_link','link','college_publications','${collegeNameEsc}')">source</a>`
      : '';
    const toggleHtml = `
      <div class="panel-toggle" role="tablist">
        <div class="panel-toggle-views">
          <button data-view="faculty" class="${view === 'faculty' ? 'active' : ''}" title="Faculty" aria-label="Faculty">${ICON_PERSON}</button>
          ${coursesBtn}
          ${pubsBtn}
          ${view === 'faculty' ? sourceLink : ''}
          ${view === 'courses' ? scheduleSourceLink : ''}
          ${view === 'publications' ? pubsSourceLink : ''}
        </div>
        <div class="term-paginator-slot"></div>
      </div>
    `;

    panel.innerHTML = toggleHtml + `<div class="panel-body"></div>`;
    const body = panel.querySelector('.panel-body');

    if (view === 'courses' && hasCourses) {
      renderCourseTable(body, schedule, college.name, {
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
        <span class="fth-label">${col.label}<span class="sort-icon">${arrow}</span></span>
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
      const oaLink = f.openalex_url
        ? `<a class="fac-link" href="${esc(f.openalex_url)}" target="_blank" rel="noopener" title="OpenAlex" onclick="track('click_link','link','faculty_openalex','${nameEsc}')">${ICON_OPENALEX}</a>`
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
                <span class="fac-links">${webLink}${schLink}${oaLink}</span>
              </div>
              <div class="fac-title-inline">${esc(f.title)}</div>
              ${f.interests ? `<div class="fac-interests">${esc(shortenInterestsForDisplay(f.interests))}</div>` : ''}
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
    { key: 'unranked', label: 'Unranked', tooltip: 'Unranked conferences/journals' },
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
        <span class="pth-label">${col.label}<span class="sort-icon">${arrow}</span></span>
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
      const yearStr = p.year != null
        ? `<span class="num-full">${p.year}</span><span class="num-short">&rsquo;${String(p.year).slice(-2)}</span>`
        : '—';

      // Title: mirror the Authors pattern — render a truncated short
      // span (text + literal "…" + "+" inline) and a full span, then
      // CSS picks which is visible per viewport. Putting the "+" inline
      // after the ellipsis (rather than absolute bottom-right) is what
      // makes the toggle land "next to the ellipsis."
      const fullTitle = p.title || '';
      const titleCut = safeTruncateForLines(fullTitle, 60);
      const renderTitleLink = (text) => {
        const html = safeHtml(dedupeMathFallback(text));
        return p.url
          ? `<a class="pub-title-link" href="${esc(p.url)}" target="_blank" rel="noopener">${html}</a>`
          : `<span class="pub-title-text">${html}</span>`;
      };
      let titleInner;
      if (titleCut) {
        titleInner =
          `<span class="title-short">${renderTitleLink(titleCut)}<span class="trunc-tail">… <button class="title-toggle" type="button" aria-label="Show full title">+</button></span></span>` +
          `<span class="title-full">${renderTitleLink(fullTitle)} <button class="title-toggle" type="button" aria-label="Collapse title">−</button></span>`;
      } else {
        titleInner = renderTitleLink(fullTitle);
      }

      // Venue: on small viewports we abbreviate long words ("Proceedings"
      // → "Proc.", etc.) so the venue fits the narrow column. When the
      // abbreviation changes the text we render two siblings — .venue-short
      // for mobile, .venue-desktop for wider viewports — and CSS picks
      // which is visible. No truncation/toggle: the abbreviation does the
      // shortening, and the column lets long names wrap.
      const venueText = p.venue_acronym || p.venue || '';
      const abbrevText = abbreviateVenue(venueText);
      const hasAbbrev = abbrevText !== venueText;
      const renderVenueText = (text) => {
        if (p.venue_acronym) {
          const venueTip = esc(plainText(p.venue || ''));
          return p.venue_url
            ? `<a href="${esc(p.venue_url)}" target="_blank" rel="noopener" title="${venueTip}">${esc(text)}</a>`
            : `<span title="${venueTip}">${esc(text)}</span>`;
        }
        if (p.venue) {
          return p.venue_url
            ? `<a class="pub-venue-full" href="${esc(p.venue_url)}" target="_blank" rel="noopener">${safeHtml(text)}</a>`
            : `<span class="pub-venue-full">${safeHtml(text)}</span>`;
        }
        return '—';
      };
      let rankHtml = '';
      if (p.venue_ranking) {
        const rankTip = esc(venueRankTooltip(p.venue_ranking, p.venue_ranking_source));
        const rankLabel = esc(p.venue_ranking);
        rankHtml = p.venue_ranking_url
          ? `<sup class="venue-rank"><a href="${esc(p.venue_ranking_url)}" target="_blank" rel="noopener" title="${rankTip}">${rankLabel}</a></sup>`
          : `<sup class="venue-rank" title="${rankTip}">${rankLabel}</sup>`;
      }
      const venueHtml = hasAbbrev
        ? `<span class="venue-short">${renderVenueText(abbrevText)}${rankHtml}</span>` +
          `<span class="venue-desktop">${renderVenueText(venueText)}${rankHtml}</span>`
        : renderVenueText(venueText) + rankHtml;

      let authorsHtml = '—';
      if (p.authors && p.authors.length) {
        const authorSpans = p.authors.map(a => {
          const tip = a.affiliation ? ` title="${esc(a.affiliation)}"` : '';
          if (a.url) {
            return `<a class="pub-author" href="${esc(a.url)}" target="_blank" rel="noopener"${tip}>${esc(a.name)}</a>`;
          }
          return `<span class="pub-author"${tip}>${esc(a.name)}</span>`;
        });
        const total = authorSpans.length;
        const allHtml = authorSpans.join(', ');
        // Truncate at different thresholds per viewport: 5 on mobile,
        // 8 on desktop. CSS shows whichever short form matches the
        // current viewport; clicking + expands to the full list.
        if (total <= 5) {
          authorsHtml = allHtml;
        } else {
          const expandBtn = `<button class="authors-toggle" type="button" aria-label="Show all authors">+</button>`;
          const collapseBtn = `<button class="authors-toggle" type="button" aria-label="Collapse authors">−</button>`;
          const mobileShort = `${authorSpans.slice(0, 5).join(', ')}, … ${expandBtn}`;
          const desktopShort = total > 8
            ? `${authorSpans.slice(0, 8).join(', ')}, … ${expandBtn}`
            : allHtml;
          authorsHtml =
            `<span class="authors-mobile-short">${mobileShort}</span>` +
            `<span class="authors-desktop-short">${desktopShort}</span>` +
            `<span class="authors-full" hidden>${allHtml} ${collapseBtn}</span>`;
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
        const full = cell.querySelector('.authors-full');
        const shorts = cell.querySelectorAll('.authors-mobile-short, .authors-desktop-short');
        const expanded = !full.hidden;
        full.hidden = expanded;
        shorts.forEach(s => { s.hidden = !expanded; });
      });
    });

    // Title +/- toggle. The cell carries .title-short and .title-full
    // siblings; CSS picks the visible one per viewport. The +/- button
    // lives inline at the end of either span, so it sits right next to
    // the "…" instead of in the cell's corner.
    panel.querySelectorAll('.title-toggle').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const cell = btn.closest('.ptd-title');
        cell.classList.toggle('expanded');
      });
    });
  }

  render();
}

// ── course schedule view ───────────────────────────────────────────────────
function renderCourseTable(panel, schedule, collegeName, opts) {
  const { termOffset, onShiftTerms } = opts;
  const cnEsc = esc(collegeName).replace(/'/g, "\\'");

  if (!schedule.courses.length) {
    panel.innerHTML = `<div class="course-empty">No course-schedule data.</div>`;
    return;
  }

  const visibleCourses = schedule.courses.filter(courseVisible);
  if (!visibleCourses.length) {
    panel.innerHTML = `<div class="course-empty">No courses match the current filters.</div>`;
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
    let debugBadge = '';
    if (DEBUG) {
      const { counted, reasons } = electiveCountStatus(c, schedule);
      const tip = counted
        ? 'Counted toward Electives'
        : 'NOT counted toward Electives — ' + reasons.join('; ');
      debugBadge = `<span class="course-debug ${counted ? 'is-counted' : 'is-excluded'}" title="${esc(tip)}">i</span>`;
    }
    const titleInner = `
      ${debugBadge}
      <span class="course-code">${esc(c.code)}</span>
      <span class="course-name">${esc(c.name)}</span>
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

  panel.innerHTML = `
    <div class="course-wrap">
      <table class="course-table">
        <thead>
          <tr>
            <th class="course-sticky"><div class="course-title-cell"><span>Course</span></div></th>
            ${headerCells}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  // Attach the full-name tooltip only where the name is actually clipped — i.e.
  // the single-line ellipsis on wide viewports. Names that wrap (small
  // viewports) report no overflow and stay tooltip-free.
  panel.querySelectorAll('.course-name').forEach(el => {
    if (el.scrollWidth > el.clientWidth) el.title = el.textContent;
  });

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
  const noHover = matchMedia('(hover: none)');
  let cur = null;
  let savedTitle = '';

  function show(el, text, clientX, clientY) {
    cur = el;
    savedTitle = text;
    el.removeAttribute('title');
    tip.textContent = text;
    tip.classList.add('visible');
    positionAt(clientX, clientY);
  }

  function hide() {
    if (!cur) return;
    cur.setAttribute('title', savedTitle);
    cur = null;
    tip.classList.remove('visible');
  }

  function positionAt(clientX, clientY) {
    const pad = 8;
    let x = clientX + pad;
    let y = clientY + pad;
    const r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth) x = clientX - r.width - pad;
    if (y + r.height > window.innerHeight) y = clientY - r.height - pad;
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
    if (noHover.matches) return;
    const el = closest(e.target);
    if (el) show(el, el.getAttribute('title'), e.clientX, e.clientY);
  });

  document.addEventListener('mouseout', function (e) {
    if (noHover.matches) return;
    if (cur && !cur.contains(e.relatedTarget)) hide();
  });

  document.addEventListener('mousemove', function (e) {
    if (noHover.matches) return;
    if (cur) positionAt(e.clientX, e.clientY);
  });
})();
