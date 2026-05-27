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
}

# Words too generic to be useful for title-based matching
_TITLE_STOP = frozenset({
    "international", "conference", "on", "the", "of", "and", "in", "for",
    "a", "an", "proceedings", "annual", "ieee", "acm", "symposium", "workshop",
    "computing", "computer", "science", "sciences", "systems", "system",
    "engineering", "advances", "applications", "theory", "practice",
    "methods", "techniques", "world", "joint", "european", "north",
    "american", "asia", "pacific", "national", "association",
    "artificial", "intelligence", "information", "knowledge", "data",
    "software", "security", "privacy", "network", "networks", "learning",
    "machine", "language", "languages", "design", "analysis", "management",
    "distributed", "parallel", "mobile", "web", "multimedia", "digital",
    "signal", "processing", "pattern", "recognition", "logic", "formal",
    "programming", "database", "databases", "research", "technology",
    "technologies", "modeling", "modelling", "simulation", "automated",
    "automation", "intelligent", "smart", "high", "performance", "real",
    "time", "user", "human", "interaction", "visualization", "visual",
    "cognitive", "neural", "embedded", "testing", "verification",
    "validation", "mining", "retrieval", "natural", "image",
})

_RANK_ORDER = {"A*": 0, "A": 1, "B": 2, "C": 3}
_PAREN_ACRONYM_RE = re.compile(r"\(([A-Z][A-Za-z&/+\-]{1,15})(?:[\s\-]*\d{0,4})?\)")


_ICORE_CACHE = Path(__file__).resolve().parent / "icore2026.csv"


def _load_or_scrape_icore() -> dict[str, tuple[str, str]]:
    """Load ICORE 2026 rankings from cache, scraping if not present."""
    if _ICORE_CACHE.exists():
        cache = pd.read_csv(_ICORE_CACHE)
        result = {}
        for _, row in cache.iterrows():
            acr, title, rank = row["acronym"], row["title"], row["rank"]
            if acr not in result or _RANK_ORDER.get(rank, 99) < _RANK_ORDER.get(result[acr][1], 99):
                result[acr] = (title, rank)
        return result
    return _scrape_and_save_icore()


def _scrape_and_save_icore() -> dict[str, tuple[str, str]]:
    """Scrape ICORE 2026 rankings and save to CSV cache."""
    import html as html_mod
    import time
    import urllib.request

    rows = []
    for page in range(1, ICORE_PAGES + 1):
        url = ICORE_URL.format(page=page)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
        cells = re.findall(r"<td[^>]*>(.*?)</td>", content, re.DOTALL)
        cells = [html_mod.unescape(re.sub(r"<[^>]+>", "", c).strip()) for c in cells]
        i = 0
        while i < len(cells) - 3:
            if cells[i + 2] == "ICORE2026":
                title = re.sub(
                    r"\s*\((?:was|formerly|previously|prev\.|now|renamed|also known)[^)]*\)\s*$",
                    "", cells[i], flags=re.IGNORECASE,
                ).strip()
                acronym, rank = cells[i + 1], cells[i + 3]
                r = rank.replace("Australasian ", "")
                if r in _RANK_ORDER:
                    rows.append({"acronym": acronym, "title": title, "rank": r})
                i += 9
            else:
                i += 1
        if page < ICORE_PAGES:
            time.sleep(0.3)

    cache_df = pd.DataFrame(rows)
    cache_df.to_csv(_ICORE_CACHE, index=False)
    print(f"  Saved to {_ICORE_CACHE}")

    result = {}
    for _, row in cache_df.iterrows():
        acr, title, rank = row["acronym"], row["title"], row["rank"]
        if acr not in result or _RANK_ORDER[rank] < _RANK_ORDER.get(result[acr][1], 99):
            result[acr] = (title, rank)
    return result


def match_core(
    df: pd.DataFrame, core_db: dict[str, tuple[str, str]],
) -> dict[str, tuple[str, str]]:
    """Match venue strings to ICORE rankings. Returns {venue: (acronym, rank)}."""
    venues = df["venue"].dropna().unique()
    venue_to_core: dict[str, tuple[str, str]] = {}

    # Step 1: CSRankings acronym → CORE lookup
    for _, row in df[["venue", "venue_acronym"]].drop_duplicates().iterrows():
        v, acr = row["venue"], row["venue_acronym"]
        if not isinstance(v, str) or not isinstance(acr, str) or not acr:
            continue
        core_acr = _CSRANKING_TO_CORE.get(acr, acr)
        if core_acr in core_db:
            venue_to_core[v] = (core_acr, core_db[core_acr][1])

    # Step 2: Parenthetical acronym in venue name
    for v in venues:
        if not isinstance(v, str) or v.startswith("http") or v in venue_to_core:
            continue
        m = _PAREN_ACRONYM_RE.search(v)
        if m:
            acr = m.group(1).rstrip()
            if acr in core_db:
                venue_to_core[v] = (acr, core_db[acr][1])

    # Step 3: Title-keyword matching (all distinctive words must appear in order)
    for acr, (title, rank) in core_db.items():
        words = [w for w in re.split(r"\W+", title) if w.lower() not in _TITLE_STOP and len(w) > 2]
        if len(words) < 2:
            continue
        pattern = r"\b" + r"\b.*?\b".join(re.escape(w) for w in words) + r"\b"
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue
        for v in venues:
            if not isinstance(v, str) or v.startswith("http") or v in venue_to_core:
                continue
            if compiled.search(v):
                venue_to_core[v] = (acr, rank)

    return venue_to_core


# ── Scimago journal rankings ────────────────────────────────────────────────
# Loaded from scraper/scimagojr.csv (downloaded from scimagojr.com).
# Matched by normalized journal title.

_SJR_PATH = Path(__file__).resolve().parent / "scimagojr.csv"


def _norm_journal(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("&amp;", "and").replace("&", "and")
    s = re.sub(r"\bthe\b", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_sjr(df: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """Match journal venues to Scimago. Returns {venue: (quartile, issn)}."""
    sjr = pd.read_csv(_SJR_PATH, sep=";")
    sjr_by_norm: dict[str, tuple[str, str]] = {}
    for _, row in sjr.iterrows():
        n = _norm_journal(str(row["Title"]))
        sjr_by_norm[n] = (str(row["SJR Best Quartile"]), str(row["Issn"]))

    venue_to_sjr: dict[str, tuple[str, str]] = {}
    journals = df.loc[df["venue_type"] == "journal", "venue"].dropna().unique()
    for v in journals:
        n = _norm_journal(v)
        if n in sjr_by_norm:
            venue_to_sjr[v] = sjr_by_norm[n]

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
    # Fill venue_acronym from CORE for venues not matched by CSRankings
    for v, (acr, _) in core_matches.items():
        mask = (df["venue"] == v) & (df["venue_acronym"] == "")
        df.loc[mask, "venue_acronym"] = acr

    # Scimago journal ranking
    print("Matching Scimago journal rankings...")
    sjr_matches = match_sjr(df)
    df["venue_sjr_quartile"] = df["venue"].map(
        lambda v: sjr_matches[v][0] if v in sjr_matches else ""
    )
    df["venue_issn"] = df["venue"].map(
        lambda v: sjr_matches[v][1] if v in sjr_matches else ""
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
