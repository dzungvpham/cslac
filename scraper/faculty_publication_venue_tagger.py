"""Tag publication venues with CSRankings conference labels.

Reads faculty_publications.csv, matches each venue against the CSRankings
conference list, and writes the result back with three new columns:
  - venue_acronym: conference acronym (e.g. "CHI", "ICSE") or empty
  - venue_area: area name (e.g. "HCI", "SE") or empty
  - venue_in_csranking: 1 if matched, empty otherwise

Source: https://csrankings.org/ (81 conferences across 27 areas)

Usage:
    python faculty_publication_venue_tagger.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── CSRankings venue patterns ───────────────────────────────────────────────
# (acronym, area, include_patterns, exclude_patterns)
# Patterns are matched case-insensitively against the venue string.
# Source: https://csrankings.org/ — 81 conferences across 27 areas.
CSRANKINGS = [
    # AI
    ("AAAI", "AI", [r"AAAI Conference on Artificial Intelligence", r"\bNational Conference on Artificial Intelligence"], [r"Symposium", r"Ethics", r"Interactive Digital"]),
    ("IJCAI", "AI", [r"International Joint Conference.*Artificial Intelligence"], []),
    # Vision
    ("CVPR", "Vision", [r"\(CVPR\b", r"IEEE.*Conference on Computer Vision and Pattern Recognition(?!\s*Workshop)"], [r"Workshop"]),
    ("ECCV", "Vision", [r"\bECCV\b", r"European Conference on Computer Vision"], [r"Workshop"]),
    ("ICCV", "Vision", [r"\bICCV\b", r"International Conference on Computer Vision(?! and Pattern)"], [r"Workshop"]),
    # ML/Mining
    ("ICLR", "ML", [r"\bICLR\b", r"International Conference on Learning Representations"], []),
    ("ICML", "ML", [r"\bICML\b", r"International Conference on Machine Learning(?!\s+and)"], []),
    ("NeurIPS", "ML", [r"\bNeurIPS\b", r"\bNIPS\b", r"Neural Information Processing Systems"], []),
    ("KDD", "ML", [r"\bSIGKDD\b"], []),
    # NLP
    ("ACL", "NLP", [r"Annual Meeting of the Association for Computational Linguistics"], [r"NAACL", r"EACL", r"Nations of the Americas"]),
    ("EMNLP", "NLP", [r"Conference on Empirical Methods in Natural Language Processing"], [r"Findings"]),
    ("NAACL", "NLP", [r"\bNAACL\b", r"North American Chapter.*Computational Linguistics", r"Nations of the Americas Chapter.*Computational Linguistics"], [r"Findings"]),
    # Web & IR
    ("SIGIR", "Web+IR", [r"ACM SIGIR.*(?:conference|symposium)"], []),
    ("WWW", "Web+IR", [r"\bThe Web Conference\b", r"International World Wide Web Conference"], []),
    # Architecture
    ("ASPLOS", "Arch", [r"Architectural Support for Programming Languages"], []),
    ("ISCA", "Arch", [r"\(ISCA\)", r"ACM.*International Symposium on Computer Architecture(?! and High)"], [r"SBAC"]),
    ("MICRO", "Arch", [r"\(MICRO\)", r"Symposium on Microarchitecture"], []),
    ("HPCA", "Arch", [r"\bHPCA\b", r"High.Performance Computer Architecture"], []),
    # Networks
    ("SIGCOMM", "Networks", [r"ACM SIGCOMM.*Conference", r"ACM SIGCOMM \d{4}"], [r"[Ii]nternet [Mm]easurement", r"[Ww]orkshop"]),
    ("NSDI", "Networks", [r"\bNSDI\b", r"Networked Systems Design and Implementation"], []),
    # Security
    ("CCS", "Security", [r"SIGSAC Conference on Computer and Communications Security"], []),
    ("Oakland", "Security", [r"IEEE Symposium on Security and Privacy", r"\bIEEE S&P\b", r"\bIEEE S&amp;P\b", r"\(SP\)"], [r"Workshop"]),
    ("USENIX Security", "Security", [r"USENIX Security"], []),
    ("NDSS", "Security", [r"Network and Distributed System Security Symposium"], []),
    # Databases
    ("SIGMOD", "DB", [r"SIGMOD.*Conference on Management of Data"], []),
    ("VLDB", "DB", [r"\bVLDB\b"], []),
    ("ICDE", "DB", [r"International Conference on Data Engineering"], []),
    ("PODS", "DB", [r"Symposium on Principles of Database Systems", r"\(PODS\)"], []),
    # Design Automation
    ("DAC", "DA", [r"Design Automation Conference", r"\bDAC\b"], []),
    ("ICCAD", "DA", [r"\bICCAD\b", r"International Conference on Computer.Aided Design"], []),
    # Embedded/RT
    ("EMSOFT", "Bed", [r"\bEMSOFT\b", r"International Conference on Embedded Software"], []),
    ("RTAS", "Bed", [r"\bRTAS\b", r"Real.Time.*Embedded Technology"], []),
    ("RTSS", "Bed", [r"\bRTSS\b", r"Real.Time Systems Symposium"], []),
    # HPC
    ("HPDC", "HPC", [r"\bHPDC\b", r"High Performance Distributed Computing"], []),
    ("ICS", "HPC", [r"International Conference on Supercomputing"], []),
    ("SC", "HPC", [r"International Conference for High Performance Computing"], [r"Workshop"]),
    # Mobile Computing
    ("MobiCom", "Mobile", [r"Mobile Computing and Networking"], []),
    ("MobiSys", "Mobile", [r"Mobile Systems, Applications"], []),
    ("SenSys", "Mobile", [r"Embedded Networked Sensor Systems"], []),
    # Measurement & Performance
    ("IMC", "Metrics", [r"Internet Measurement Conference"], []),
    ("SIGMETRICS", "Metrics", [r"SIGMETRICS.*(?:Conference|conference).*Measurement"], []),
    # Operating Systems
    ("OSDI", "OS", [r"Operating Systems Design and Implementation", r"\(OSDI\)"], []),
    ("SOSP", "OS", [r"Symposium on Operating Systems Principles"], []),
    ("EuroSys", "OS", [r"\bEuroSys\b"], []),
    ("FAST", "OS", [r"\(FAST\)", r"USENIX.*File and Storage"], []),
    ("USENIX ATC", "OS", [r"USENIX Annual Technical"], []),
    # Programming Languages
    ("PLDI", "PL", [r"Programming Language Design and Implementation"], []),
    ("POPL", "PL", [r"Principles of [Pp]rogramming [Ll]anguages"], []),
    ("ICFP", "PL", [r"International.*[Cc]onference on Functional [Pp]rogramming"], []),
    ("OOPSLA", "PL", [r"Object.[Oo]riented [Pp]rogramming"], []),
    # Software Engineering
    ("FSE", "SE", [r"Foundations of Software Engineering"], []),
    ("ICSE", "SE", [r"International Conference on Software Engineering"], [r"Knowledge Engineering"]),
    ("ASE", "SE", [r"Automated Software Engineering", r"\(ASE\)"], []),
    ("ISSTA", "SE", [r"International.*[Ss]ymposium on Software Testing and Analysis"], []),
    # Theory
    ("FOCS", "Theory", [r"Symposium on Foundations of Computer Science", r"\(FOCS\)"], []),
    ("SODA", "Theory", [r"Symposium on Discrete Algorithms"], []),
    ("STOC", "Theory", [r"[Ss]ymposium on Theory of [Cc]omputing"], []),
    # Cryptography
    ("CRYPTO", "Crypt", [r"International Cryptology Conference", r"\(CRYPTO\)"], []),
    ("EuroCrypt", "Crypt", [r"\bEUROCRYPT\b", r"Theory and Applications of Cryptographic Techniques"], []),
    # Logic & Verification
    ("CAV", "Logic", [r"Computer Aided Verification", r"\(CAV\)"], []),
    ("LICS", "Logic", [r"Symposium on Logic in Computer Science", r"\(LICS\)"], []),
    # Bioinformatics
    ("ISMB", "Bio", [r"Intelligent Systems for Molecular Biology"], []),
    ("RECOMB", "Bio", [r"\bRECOMB\b", r"Research in Computational Molecular Biology"], []),
    # Graphics
    ("SIGGRAPH", "Graphics", [r"ACM SIGGRAPH \d{4}\b(?!.*(?:Poster|Art|Educator|Forum|Motion))"], []),
    ("SIGGRAPH Asia", "Graphics", [r"SIGGRAPH Asia"], []),
    ("EUROGRAPHICS", "Graphics", [r"\bEurographics\b"], []),
    # CS Education
    ("SIGCSE", "CSEd", [r"SIGCSE.*[Ss]ymposium", r"ACM Technical Symposium on Comput\w+ Science Education", r"Technical Symposium on Comput\w+ Science Education"], []),
    # Economics & Computation
    ("EC", "ECom", [r"ACM.*Conference on Economics and Computation"], []),
    ("WINE", "ECom", [r"\bWINE\b", r"Internet and Network Economics"], []),
    # AI Ethics
    ("FAccT", "AIEthics", [r"\bFAccT\b", r"Fairness,? Accountability,? and Transparency"], []),
    # HCI
    ("CHI", "HCI", [r"CHI.*Human Factors in Computing Systems", r"SIGCHI.*Human Factors"], []),
    ("UbiComp", "HCI", [r"\bUbiComp\b", r"ACM.*Ubiquitous Computing(?! Electronics)"], [r"UEMCON"]),
    ("Pervasive", "HCI", [r"\bPervasive Computing\b"], []),
    ("IMWUT", "HCI", [r"\bIMWUT\b", r"Interactive, Mobile, Wearable and Ubiquitous"], []),
    ("UIST", "HCI", [r"User Interface Software and Technology"], []),
    # Robotics
    ("ICRA", "Robotics", [r"\bICRA\b", r"International Conference on Robotics and Automation"], []),
    ("IROS", "Robotics", [r"\bIROS\b", r"Intelligent Robots and Systems"], []),
    ("RSS", "Robotics", [r"Robotics:?\s*Science and Systems"], []),
    # Visualization
    ("VIS", "Visualization", [r"IEEE Visualization", r"\bIEEE VIS\b", r"\(VIS\)"], []),
    ("VR", "Visualization", [r"IEEE.*(?:Virtual Reality|VR\b).*(?:Conference|Symposium|Proceedings)", r"\(VR\)"], [r"Workshop", r"VRW", r"AIVR"]),
]


def match_venue(venue: str) -> tuple[str, str] | None:
    """Return (acronym, area) if venue matches a CSRankings conference."""
    if not isinstance(venue, str) or venue.startswith("http"):
        return None
    for acronym, area, includes, excludes in CSRANKINGS:
        if any(re.search(ep, venue, re.IGNORECASE) for ep in excludes):
            continue
        if any(re.search(p, venue, re.IGNORECASE) for p in includes):
            return acronym, area
    return None


# ── ICORE 2026 conference rankings ─────────────────────────────────────────
# Scraped from https://portal.core.edu.au/conf-ranks/ (ICORE2026 source).
# Maps venue strings to (core_acronym, core_rank).
#
# Matching strategy (in priority order):
#   1. CSRankings acronym → CORE acronym lookup
#   2. Acronym extracted from parentheses in venue name → CORE lookup
#   3. Title-keyword matching for remaining venues (conservative stop list)

ICORE_URL = "https://portal.core.edu.au/conf-ranks/?search=&by=all&source=ICORE2026&sort=arank&page={page}"
ICORE_PAGES = 20

# CSRankings acronyms that differ from CORE acronyms
_CSRANKING_TO_CORE = {
    "Oakland": "S&P",
    "USENIX Security": "UsenixSec",
    "USENIX ATC": "USENIX",
    "EUROGRAPHICS": "EG",
    "EuroCrypt": "EUROCRYPT",
    "VIS": "IEEE VIS",
}

_TITLE_STOP = frozenset({
    "a", "an", "the", "of", "on", "and", "in", "for", "its", "to", "with",
    "proceedings", "annual", "biennial", "international", "national",
    "acm", "ieee", "siam", "usenix", "aaai", "rsj",
})

_VENUE_PREFIX_RE = re.compile(
    r"^proceedings\s+of\s+(?:the\s+)?"
    r"(?:(?:\w+)\s+)?"                          # "first", "15th", "2016", etc.
    r"(?:\(\d{4}\)\s+)?"                         # "(2016)"
    r"(?:(?:ACM|IEEE|SIAM|USENIX|AAAI)\s+)?",   # org prefix
    re.IGNORECASE,
)
# Strict variant — only strips year/ordinal/org-acronym, never an arbitrary
# word. Used alongside the greedy variant in match_core so a venue like
# "Proceedings of the Genetic and Evolutionary Computation Conference"
# keeps "genetic" in its token set (the greedy `\w+` would eat it).
_VENUE_PREFIX_STRICT_RE = re.compile(
    r"^proceedings\s+of\s+(?:the\s+)?"
    r"(?:(?:"
        r"\d{4}"                                # 2016
        r"|\d{1,3}(?:st|nd|rd|th)"              # 15th, 2nd
        r"|first|second|third|fourth|fifth"
        r"|sixth|seventh|eighth|ninth|tenth"
        r"|eleventh|twelfth|thirteenth"
        r"|fourteenth|fifteenth|sixteenth"
        r"|seventeenth|eighteenth|nineteenth"
        r"|twentieth|thirtieth|fortieth"
        r"|fiftieth|sixtieth|seventieth"
        r"|eightieth|ninetieth|hundredth"
    r")\s+)?"
    r"(?:\(\d{4}\)\s+)?"
    r"(?:(?:ACM|IEEE|SIAM|USENIX|AAAI)\s+)?",
    re.IGNORECASE,
)
_PAREN_JUNK_RE = re.compile(
    r"\s*\((?:"
    r"(?:IEEE\s*)?Cat\.?\s*No\.|"               # (IEEE Cat. No.XX) / (Cat. No.XX)
    r"IEEE\s*Cat\b"
    r")[^)]*\)",
    re.IGNORECASE,
)
_ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _stem(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ses") or w.endswith("zes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokenize(s: str, prefix_re: re.Pattern = _VENUE_PREFIX_RE) -> set[str]:
    s = s.replace("&amp;", "&")
    s = _PAREN_JUNK_RE.sub("", s)
    s = prefix_re.sub("", s)
    s = _ORDINAL_RE.sub("", s)
    s = _YEAR_RE.sub("", s)
    return {
        _stem(w.lower())
        for w in re.split(r"\W+", s)
        if w and len(w) > 1 and w.lower() not in _TITLE_STOP
    }

_RANK_ORDER = {"A*": 0, "A": 1, "B": 2, "C": 3, "": 99}
_PAREN_ACRONYM_RE = re.compile(r"\(([A-Z][A-Za-z&/+\-]{1,15})(?:[\s\-]*\d{0,4})?\)")


_ICORE_CACHE = Path(__file__).resolve().parent / "icore2026.csv"


_ICORE_DETAIL_URL = "https://portal.core.edu.au/conf-ranks/{id}/"


def _build_core_db(rows: list[dict]) -> dict[str, tuple[str, str, str]]:
    """Build {key: (title, rank, url)} dict, disambiguating duplicate acronyms.

    The highest-ranked entry keeps the plain acronym; lower-ranked duplicates
    get "ACR (Title)" as their key so both remain matchable.
    """
    best: dict[str, tuple[str, str, int]] = {}
    for r in rows:
        acr, title, rank = str(r["acronym"]), str(r["title"]), str(r["rank"])
        pri = _RANK_ORDER.get(rank, 99)
        if acr not in best or pri < best[acr][2]:
            best[acr] = (title, rank, pri)

    result: dict[str, tuple[str, str, str]] = {}
    for r in rows:
        acr = str(r["acronym"])
        title = str(r["title"])
        rank = str(r["rank"])
        url = str(r.get("url", ""))
        pri = _RANK_ORDER.get(rank, 99)
        if pri == best[acr][2] and title == best[acr][0]:
            result[acr] = (title, rank, url)
        else:
            result[f"{acr} ({title})"] = (title, rank, url)
    return result


def _load_or_scrape_icore() -> dict[str, tuple[str, str, str]]:
    """Load ICORE 2026 rankings from cache, scraping if not present.

    Re-scrapes if the cache is missing a `url` column (older cache format
    predating the per-conference detail URL).
    """
    if _ICORE_CACHE.exists():
        cache = pd.read_csv(_ICORE_CACHE).fillna("")
        if "url" in cache.columns:
            return _build_core_db(cache.to_dict("records"))
    return _scrape_and_save_icore()


# Each row's <tr> carries `onclick="navigate('/conf-ranks/<id>/')"` — the only
# place the conference's detail URL surfaces in the listing markup.
_ICORE_ROW_RE = re.compile(
    r"<tr[^>]*onclick=\"navigate\('/conf-ranks/(\d+)/'\)\"[^>]*>(.*?)</tr>",
    re.DOTALL,
)


def _scrape_and_save_icore() -> dict[str, tuple[str, str, str]]:
    """Scrape ICORE 2026 rankings and save to CSV cache."""
    import html as html_mod
    import time

    import requests as req_lib

    session = req_lib.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    rows = []
    for page in range(1, ICORE_PAGES + 1):
        url = ICORE_URL.format(page=page)
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.text
        for m in _ICORE_ROW_RE.finditer(content):
            conf_id, row_html = m.group(1), m.group(2)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
            cells = [html_mod.unescape(re.sub(r"<[^>]+>", "", c).strip()) for c in cells]
            if len(cells) < 4 or cells[2] != "ICORE2026":
                continue
            title = re.sub(
                r"\s*\((?:was|formerly|previously|prev\.|now|renamed|also known)[^)]*\)\s*$",
                "", cells[0], flags=re.IGNORECASE,
            ).strip()
            acronym, rank = cells[1], cells[3]
            r = rank.replace("Australasian ", "")
            if r not in _RANK_ORDER:
                r = ""
            rows.append({
                "acronym": acronym,
                "title": title,
                "rank": r,
                "url": _ICORE_DETAIL_URL.format(id=conf_id),
            })
        if page < ICORE_PAGES:
            time.sleep(0.3)

    cache_df = pd.DataFrame(rows)
    cache_df.to_csv(_ICORE_CACHE, index=False)
    print(f"  Saved to {_ICORE_CACHE}")

    return _build_core_db(rows)


def match_core(
    df: pd.DataFrame, core_db: dict[str, tuple[str, str, str]],
) -> dict[str, tuple[str, str, str]]:
    """Match venue strings to ICORE rankings. Returns {venue: (acronym, rank, url)}."""
    venues = df["venue"].dropna().unique()
    venue_to_core: dict[str, tuple[str, str, str]] = {}

    # Step 1: CSRankings acronym → CORE lookup
    for _, row in df[["venue", "venue_acronym"]].drop_duplicates().iterrows():
        v, acr = row["venue"], row["venue_acronym"]
        if not isinstance(v, str) or not isinstance(acr, str) or not acr:
            continue
        core_acr = _CSRANKING_TO_CORE.get(acr, acr)
        if core_acr in core_db:
            _, rank, url = core_db[core_acr]
            venue_to_core[v] = (core_acr, rank, url)

    # Step 2: Parenthetical acronym in venue name
    for v in venues:
        if not isinstance(v, str) or v.startswith("http") or v in venue_to_core:
            continue
        m = _PAREN_ACRONYM_RE.search(v)
        if m:
            acr = m.group(1).rstrip()
            if acr in core_db:
                _, rank, url = core_db[acr]
                venue_to_core[v] = (acr, rank, url)

    # Step 3: Word-set matching — score by recall (CORE words found in venue),
    # tiebreak by Jaccard.  Skip journals / book series that don't look like
    # conference proceedings (OpenAlex often mislabels proceedings as journals).
    _CONF_WORDS_RE = re.compile(
        r"proceedings|conference|symposium|workshop", re.IGNORECASE,
    )
    journal_venues = set(
        v for v in df.loc[
            df["venue_type"].isin(["journal", "book series"]), "venue"
        ].dropna().unique()
        if not _CONF_WORDS_RE.search(v)
    )
    core_tokens = {acr: _tokenize(title) for acr, (title, _, _) in core_db.items()}
    for v in venues:
        if not isinstance(v, str) or v.startswith("http") or v in venue_to_core:
            continue
        if v in journal_venues:
            continue
        # Tokenize with both the greedy and strict prefix strippers and
        # score each against CORE — the greedy one eats one leading word
        # (helpful for modifiers like "Companion"/"Joint" but harmful when
        # that word is real title content like "Genetic"), so trying both
        # avoids regressing either case.
        token_variants = [_tokenize(v), _tokenize(v, _VENUE_PREFIX_STRICT_RE)]
        best_acr, best_rank, best_url = None, None, None
        best_recall, best_jaccard = 0.0, 0.0
        for v_tokens in token_variants:
            if len(v_tokens) < 2:
                continue
            for acr, c_tokens in core_tokens.items():
                if len(c_tokens) < 2:
                    continue
                inter = len(c_tokens & v_tokens)
                recall = inter / len(c_tokens)
                jaccard = inter / len(c_tokens | v_tokens)
                if recall >= 0.8 and jaccard >= 0.65 and (recall, jaccard) > (best_recall, best_jaccard):
                    _, best_rank, best_url = core_db[acr]
                    best_acr = acr
                    best_recall, best_jaccard = recall, jaccard
        if best_acr:
            venue_to_core[v] = (best_acr, best_rank, best_url)

    return venue_to_core


# ── Scimago journal rankings ────────────────────────────────────────────────
# Loaded from scraper/scimagojr.csv (downloaded from scimagojr.com).
# Matched by normalized journal title.

# Scimago CSVs to merge. Each is filtered to a single subject area on the
# Scimago side (the site forces a per-area download); we load them all so
# cross-disciplinary venues (math journals like Discrete Math, Linear
# Algebra) get matched in addition to CS-area journals. When a journal
# appears in multiple areas with different quartiles, the better quartile
# wins — same convention Scimago uses for its "SJR Best Quartile" column.
_SJR_PATHS = [
    Path(__file__).resolve().parent / "scimagojr.csv",       # Computer Science
    Path(__file__).resolve().parent / "scimagojr_math.csv",  # Mathematics
]

_Q_RANK = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "-": 4, "": 5}


# Scimago often appends the venue's acronym after a comma — e.g.
# "Proceedings - AAAI ... Conference, AIIDE" or "Lecture Notes ..., LNICST".
# We strip the trailing acronym before normalizing so it doesn't show up
# as an extra token that blocks the subset match against the OpenAlex
# venue (which never carries the acronym).
_TRAILING_ACRONYM_RE = re.compile(r",\s*[A-Z][A-Z0-9]{1,7}\s*$")


def _norm_journal(s: str) -> str:
    s = _TRAILING_ACRONYM_RE.sub("", s.strip()).lower()
    s = s.replace("&amp;", "and").replace("&", "and")
    s = re.sub(r"\bthe\b", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Hand-curated SJR quartiles for journals our faculty publish in that don't
# appear in scimagojr.csv (it's filtered to Computer Science only, so cross-
# disciplinary venues — Nature, PRL, JAMA, the math journals, etc. — are
# missing). Quartiles reflect Scimago's public rankings as of 2024.
# Keys are already in `_norm_journal` form.
_CURATED_SJR: dict[str, str] = {
    # Multidisciplinary
    "nature": "Q1",
    "science": "Q1",
    "nature communications": "Q1",
    "plos one": "Q1",
    # Math venue not in scimagojr_math.csv under this name — the CSV lists
    # it as bare "Involve" (1 token, below the subset-match threshold), so
    # the OpenAlex string "Involve, a Journal of Mathematics" needs an
    # explicit entry to pick up the Q3 ranking.
    "involve a journal of mathematics": "Q3",
    # CS journals not in the CS-filtered SJR
    "ieee transactions on networking": "Q1",  # subset-matches "IEEE/ACM Transactions on Networking"
    "acm sigplan notices": "Q3",
    "quantum": "Q1",
    "journal of vision": "Q1",
    "evolutionary computation": "Q1",
    "performance evaluation": "Q1",
    "queueing systems": "Q1",
    # Statistics
    "american statistician": "Q1",
    "annual review of statistics and its application": "Q1",
    # Medical / biology
    "jama internal medicine": "Q1",
    "genome biology": "Q1",
    "jacc heart failure": "Q1",
    "journal of chemical education": "Q2",
    # Physics
    "physical review letters": "Q1",
    "international journal of theoretical physics": "Q2",
    # Education
    "educational technology research and development": "Q1",
    # Other
    "internet research": "Q1",
    # Curated to override an otherwise-confusing subset match: the venue
    # "Journal of Intelligent & Robotic Systems" would subset-match to
    # Scimago's shorter "Journal of Intelligent Systems" (different journal);
    # the real one is "Journal of Intelligent and Robotic Systems: Theory
    # and Applications" (Q2) but the subtitle blocks the subset rule.
    "journal of intelligent and robotic systems": "Q2",
    # Likewise, this education journal isn't in CS-filtered SJR; without
    # a curated entry the subset rule fires on a misordered look-alike.
    "journal of science education and technology": "Q2",
}

_JOURNAL_TOKEN_STOP = frozenset({"of", "and", "in", "for", "on", "a", "an", "with"})


def _journal_tokens(norm: str) -> frozenset[str]:
    """Tokens for fuzzy subset matching: drop stopwords, keep length >= 2."""
    return frozenset(
        w for w in norm.split() if len(w) > 1 and w not in _JOURNAL_TOKEN_STOP
    )


def _journal_tokens_ordered(norm: str) -> list[str]:
    """Same tokens as _journal_tokens but ordered + deduplicated. Used to
    check that one title's tokens appear in the other in the same order
    (so reorderings like "Software Engineering" vs "Engineering Software"
    don't match)."""
    seen: set[str] = set()
    result: list[str] = []
    for w in norm.split():
        if len(w) > 1 and w not in _JOURNAL_TOKEN_STOP and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def _is_subseq(needle: list[str], haystack: list[str]) -> bool:
    """True if every token in `needle` appears in `haystack` in the same order."""
    j = 0
    for h in haystack:
        if j < len(needle) and h == needle[j]:
            j += 1
    return j == len(needle)


_SJR_DETAIL_URL = "https://www.scimagojr.com/journalsearch.php?q={sid}&tip=sid&clean=0"


def match_sjr(df: pd.DataFrame) -> dict[str, tuple[str, str, str]]:
    """Match journal venues to Scimago. Returns {venue: (quartile, issn, url)}."""
    sjr_by_norm: dict[str, tuple[str, str, str]] = {}
    for sjr_path in _SJR_PATHS:
        sjr = pd.read_csv(sjr_path, sep=";")
        for _, row in sjr.iterrows():
            n = _norm_journal(str(row["Title"]))
            sid = str(row["Sourceid"]).strip()
            url = _SJR_DETAIL_URL.format(sid=sid) if sid else ""
            new_entry = (str(row["SJR Best Quartile"]), str(row["Issn"]), url)
            existing = sjr_by_norm.get(n)
            if existing is None or _Q_RANK.get(new_entry[0], 99) < _Q_RANK.get(existing[0], 99):
                sjr_by_norm[n] = new_entry
    # Layer curated entries on top — only add if Scimago doesn't already have
    # the journal, so the CSV remains the source of truth where it has data.
    for n, q in _CURATED_SJR.items():
        sjr_by_norm.setdefault(n, (q, "", ""))

    # Pre-compute token sets + ordered token lists for subset-match fallback.
    # Only Scimago entries with >= 3 meaningful tokens participate — short
    # titles are too easy to accidentally match (e.g. "Nature" against
    # "Nature Genetics").
    sjr_token_index: list[tuple[frozenset[str], list[str], tuple[str, str, str]]] = []
    for n, data in sjr_by_norm.items():
        toks = _journal_tokens(n)
        if len(toks) >= 3:
            sjr_token_index.append((toks, _journal_tokens_ordered(n), data))

    venue_to_sjr: dict[str, tuple[str, str, str]] = {}
    journals = df.loc[df["venue_type"] == "journal", "venue"].dropna().unique()
    for v in journals:
        n = _norm_journal(v)
        if n in sjr_by_norm:
            venue_to_sjr[v] = sjr_by_norm[n]
            continue
        # Fallback: a Scimago entry's tokens are a strict subset of the
        # venue's tokens, IN THE SAME ORDER, with at most one extra venue
        # token. Catches naming drift like venue "IEEE/ACM Transactions on
        # Networking" vs Scimago "IEEE Transactions on Networking". The
        # order check kills reordering false positives like venue "Advances
        # in Software Engineering" vs Scimago "Advances in Engineering
        # Software" — same tokens, different journals. Prefer the most-
        # specific match (largest scimago token set) when multiple fit.
        v_tokens = _journal_tokens(n)
        if len(v_tokens) < 3:
            continue
        v_tokens_ordered = _journal_tokens_ordered(n)
        best: tuple[int, tuple[str, str, str]] | None = None
        for s_tokens, s_tokens_ordered, sjr_data in sjr_token_index:
            if not s_tokens <= v_tokens:
                continue
            extras = len(v_tokens - s_tokens)
            if extras > 1:
                continue
            # When the token sets are identical and the title is long
            # enough that random token coincidence is implausible (>= 5
            # tokens), skip the order check — Scimago and OpenAlex sometimes
            # disagree on word order for conference proceedings (e.g.
            # OpenAlex "Proceedings of the AAAI Conference on Artificial
            # Intelligence and Interactive Digital Entertainment" vs
            # Scimago "Proceedings - AAAI Artificial Intelligence and
            # Interactive Digital Entertainment Conference"). Short titles
            # still need order preservation to block reorderings like
            # "Advances in Software Engineering" vs "Advances in
            # Engineering Software".
            order_ok = (
                (extras == 0 and len(s_tokens) >= 5)
                or _is_subseq(s_tokens_ordered, v_tokens_ordered)
            )
            if not order_ok:
                continue
            if best is None or len(s_tokens) > best[0]:
                best = (len(s_tokens), sjr_data)
        if best is not None:
            venue_to_sjr[v] = best[1]

    return venue_to_sjr


def main():
    input_path = DATA_DIR / "faculty_publications.csv"
    df = pd.read_csv(input_path)

    # CSRankings tagging
    matches = df["venue"].apply(match_venue)
    df["venue_acronym"] = matches.apply(lambda m: m[0] if m else "")
    df["venue_area"] = matches.apply(lambda m: m[1] if m else "")
    df["venue_in_csranking"] = matches.apply(lambda m: 1 if m else "")

    # ICORE conference ranking
    print("Loading ICORE 2026 rankings...")
    core_db = _load_or_scrape_icore()
    print(f"  {len(core_db)} ranked conferences")
    core_matches = match_core(df, core_db)
    df["venue_core_ranking"] = df["venue"].map(
        lambda v: core_matches[v][1] if v in core_matches else ""
    )
    df["venue_core_url"] = df["venue"].map(
        lambda v: core_matches[v][2] if v in core_matches else ""
    )
    # Fill venue_acronym from CORE for venues not matched by CSRankings
    for v, (acr, _, _) in core_matches.items():
        mask = (df["venue"] == v) & (df["venue_acronym"] == "")
        df.loc[mask, "venue_acronym"] = acr

    # "Findings of" ACL/EMNLP/NAACL — tag with parent conference rank
    _FINDINGS_RE = re.compile(
        r"Findings of the Association for Computational Linguistics"
        r"[:\s]*(ACL|EMNLP|NAACL)",
        re.IGNORECASE,
    )
    for _, row in df.iterrows():
        v = row["venue"]
        if not isinstance(v, str) or row["venue_acronym"]:
            continue
        m = _FINDINGS_RE.search(v)
        if m:
            parent = m.group(1).upper()
            acr = f"{parent} (Findings)"
            core_acr = parent if parent != "EMNLP" else "EMNLP"
            parent_entry = core_db.get(core_acr, ("", "", ""))
            rank = parent_entry[1] if core_acr in core_db else ""
            url = parent_entry[2] if core_acr in core_db else ""
            df.loc[df["venue"] == v, "venue_acronym"] = acr
            df.loc[df["venue"] == v, "venue_core_ranking"] = rank
            df.loc[df["venue"] == v, "venue_core_url"] = url

    # Scimago journal ranking
    print("Matching Scimago journal rankings...")
    sjr_matches = match_sjr(df)
    df["venue_sjr_quartile"] = df["venue"].map(
        lambda v: sjr_matches[v][0] if v in sjr_matches else ""
    )
    df["venue_issn"] = df["venue"].map(
        lambda v: sjr_matches[v][1] if v in sjr_matches else ""
    )
    df["venue_sjr_url"] = df["venue"].map(
        lambda v: sjr_matches[v][2] if v in sjr_matches else ""
    )
    print(f"  {len(sjr_matches)} journals matched")

    df.to_csv(input_path, index=False)

    # Summary
    n_csr = (df["venue_in_csranking"] == 1).sum()
    n_core = (df["venue_core_ranking"] != "").sum()
    n_sjr = (df["venue_sjr_quartile"] != "").sum()
    print(f"\nCSRankings: {n_csr}/{len(df)} rows")
    print(f"ICORE:      {n_core}/{len(df)} rows")
    for rank in ["A*", "A", "B", "C"]:
        print(f"  {rank}: {(df['venue_core_ranking'] == rank).sum()}")
    print(f"Scimago:    {n_sjr}/{len(df)} rows")
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        print(f"  {q}: {(df['venue_sjr_quartile'] == q).sum()}")


if __name__ == "__main__":
    main()
