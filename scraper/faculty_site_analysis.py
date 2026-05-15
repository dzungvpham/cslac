import json
import os
import subprocess
import time
import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm

SOURCE_PATH = "../data/faculty_list.csv"
GOOGLE_SCHOLAR_PATH = "../data/faculty_list_with_verified_profile.csv"
OUTPUT_PATH = "../data/faculty_list_with_field.csv"
CLEANED_WEBSITE_PATH = "../data/faculty_websites_cleaned"

OLLAMA_PORT = 11434
OLLAMA_MODEL = "qwen3:30b-a3b-instruct-2507-q4_K_M"


def _wsl_host_ip():
    """Return the Windows host IP from inside WSL2, or None if not derivable."""
    try:
        out = subprocess.check_output(
            ["ip", "route", "show", "default"], text=True, timeout=2
        )
        for tok in out.split():
            if tok.count(".") == 3 and tok.replace(".", "").isdigit():
                return tok
    except Exception:
        return None
    return None


def _resolve_ollama_url():
    """Pick a reachable Ollama base URL.

    Order: $OLLAMA_HOST (if set) -> localhost -> WSL Windows-host gateway.
    Returns the full /api/generate URL.
    """
    candidates = []
    env_host = os.environ.get("OLLAMA_HOST", "").strip()
    if env_host:
        if "://" not in env_host:
            env_host = f"http://{env_host}"
        candidates.append(env_host.rstrip("/"))
    candidates.append(f"http://localhost:{OLLAMA_PORT}")
    win_ip = _wsl_host_ip()
    if win_ip:
        candidates.append(f"http://{win_ip}:{OLLAMA_PORT}")

    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        try:
            resp = requests.get(f"{base}/api/tags", timeout=2)
            if resp.ok:
                print(f"Using Ollama at {base}")
                return f"{base}/api/generate"
        except requests.RequestException:
            continue

    raise RuntimeError(
        "Could not reach Ollama on any of: "
        + ", ".join(seen)
        + ". Set OLLAMA_HOST or start `ollama serve`."
    )


OLLAMA_URL = _resolve_ollama_url()

REQUEST_TIMEOUT = 180
MAX_RETRIES = 2
MIN_TEXT_CHARS = 100
MAX_TEXT_CHARS = 12000
MAX_SUBFIELDS = 5

# GPU throttling: short delay after every Ollama call, longer cool-down break
# every Nth call. Tuned to keep an unstable GPU from overheating during a
# multi-hour batch. Override via env vars if needed.
THROTTLE_PER_REQUEST_SEC = float(os.environ.get("FSA_THROTTLE_SEC", "1.0"))
THROTTLE_BREAK_INTERVAL = int(os.environ.get("FSA_BREAK_INTERVAL", "100"))
THROTTLE_BREAK_SEC = float(os.environ.get("FSA_BREAK_SEC", "60.0"))

ALLOWED_FIELDS = ["Computer Science", "Mathematics or Statistics", "Unknown", "Invalid"]
TRUSTED_SCHOLAR_STATUSES = {"matched", "manual_approved"}

CS_SUBFIELDS = [
    ("Artificial intelligence",
     "General AI methods not subsumed by ML/CV/NLP. Includes: symbolic AI, "
     "search, planning, automated reasoning, knowledge representation, "
     "multi-agent systems, autonomous agents, expert systems, AI ethics/safety "
     "as a research area, foundation-model agents."),
    ("Computer vision",
     "Image and video understanding. Includes: object recognition/detection, "
     "segmentation, 3D vision, visual SLAM, scene understanding, generative "
     "image models, medical image analysis, pose estimation, action recognition."),
    ("Machine learning",
     "Statistical and neural learning as the methodological contribution. "
     "Includes: supervised/unsupervised/self-supervised learning, deep learning, "
     "reinforcement learning, learning theory, probabilistic ML, ML systems and "
     "MLOps. Use this only when ML is the research itself; if ML is just a tool "
     "applied within CV/NLP/Robotics/etc., prefer those instead."),
    ("Natural language processing",
     "Computational linguistics and language technology. Includes: text "
     "understanding, machine translation, speech recognition/synthesis, "
     "dialogue systems, sentiment analysis, parsing, large language models, "
     "computational psycholinguistics and sentence-processing modeling."),
    ("Data science",
     "Applied data analysis and engineering for insight. Includes: data mining, "
     "knowledge discovery, predictive analytics, large-scale data pipelines and "
     "wrangling, exploratory data analysis as research. Distinct from pure "
     "statistics (which goes to Mathematics or Statistics)."),
    ("Information retrieval",
     "Search and recommendation. Includes: search engines, ranking, recommender "
     "systems, collaborative filtering, query understanding, indexing, "
     "content tagging, social bookmarking systems."),
    ("Computer architecture",
     "Hardware microarchitecture and design. Includes: processors, cache and "
     "memory hierarchy, accelerators (GPU/TPU/NPU), ISA design, hardware/"
     "software interface, SoCs, chiplets. Software-only systems work belongs "
     "elsewhere."),
    ("Computer networks",
     "Networking research. Includes: protocols, internet measurement, wireless "
     "and mobile networks, SDN/NFV, datacenter networks, edge networks, "
     "network performance and management."),
    ("Distributed systems",
     "Distributed and cloud computing systems. Includes: consensus, large-scale "
     "services, distributed storage, fault tolerance, microservices, "
     "peer-to-peer, edge/serverless platforms, blockchain consensus protocols."),
    ("Computer security & privacy",
     "ADVERSARIAL or CONFIDENTIALITY-focused research on digital systems and "
     "data. Includes: computer/network/system security, malware/exploits, "
     "vulnerability research, applied cryptography in systems, side-channel "
     "attacks, usable security, differential privacy, privacy-preserving "
     "computation. Does NOT include: accessibility (that's HCI), web privacy "
     "policies in page footers, or any non-adversarial mention of the word "
     "'privacy'. Require an explicit security/threat-model framing."),
    ("Databases",
     "Data management systems. Includes: query processing/optimization, "
     "transactions, indexing, SQL/NoSQL/graph/time-series databases, data "
     "warehouses, stream processing, schema design."),
    ("Design automation",
     "Electronic design automation (EDA) as a tool/system contribution. "
     "Includes: hardware synthesis algorithms (as EDA tooling), place-and-"
     "route, formal hardware verification, HDL design tools. A theorist who "
     "studies algorithms FOR logic synthesis primarily contributes to "
     "Algorithms & complexity, not Design automation."),
    ("Embedded & real-time systems",
     "Resource-constrained or time-critical computing. Includes: IoT, "
     "embedded software, RTOS, cyber-physical systems, sensor networks, "
     "automotive/aerospace/medical device software."),
    ("High-performance computing",
     "Parallel and scientific computing. Includes: parallel algorithms, "
     "GPU/HPC systems, scientific simulation, MPI/CUDA programming, "
     "supercomputing, performance tuning of numerical workloads."),
    ("Mobile computing",
     "Mobile and ubiquitous computing. Includes: mobile OS/apps, ubiquitous "
     "and pervasive computing, mobile/wearable sensing, smartphone-based "
     "research, mobile health (mHealth)."),
    ("Measurement & performance analysis",
     "Empirical systems measurement and modeling. Includes: benchmarking, "
     "workload characterization, performance modeling, system profiling, "
     "capacity planning."),
    ("Operating systems",
     "OS internals. Includes: kernels, virtualization, hypervisors, file "
     "systems, schedulers, memory managers, OS-level abstractions."),
    ("Programming languages",
     "Language theory and implementation. Includes: language design, "
     "compilers, type systems, semantics, program analysis, runtime systems, "
     "domain-specific languages, language-based security."),
    ("Software engineering",
     "Software development research. Includes: software testing, debugging, "
     "maintenance, refactoring, dev tools, requirements engineering, empirical "
     "SE, mining software repositories, assurance cases, software quality."),
    ("Algorithms & complexity",
     "Theoretical CS. Includes: algorithm design, complexity theory, "
     "approximation/randomized algorithms, combinatorial optimization, "
     "computational geometry, lower bounds, fine-grained complexity. "
     "A theorist whose application happens to be logic synthesis or "
     "networks belongs here if the contribution is algorithmic."),
    ("Quantum computing",
     "Quantum CS. Includes: quantum algorithms, quantum information, "
     "quantum complexity, quantum software stacks, quantum error correction."),
    ("Cryptography",
     "Cryptographic theory and protocols. Includes: encryption schemes, "
     "zero-knowledge proofs, multi-party computation, post-quantum crypto, "
     "hash functions, signature schemes, foundations of cryptography. "
     "Systems-level deployment of crypto (e.g. building secure systems) "
     "leans toward Computer security & privacy."),
    ("Logic & verification",
     "Formal methods. Includes: theorem proving, model checking, SAT/SMT "
     "solving, abstract interpretation, software/hardware verification, "
     "interactive proof assistants, type-theoretic foundations of proofs."),
    ("Computational bio & bioinformatics",
     "Algorithmic and computational research in biology and biomedicine. "
     "Includes: genomics, proteomics, sequence analysis, computational "
     "evolution, structural biology computation, biomedical informatics, "
     "agroinformatics, single-cell analysis methods."),
    ("Computer graphics",
     "Visual computing. Includes: rendering, geometric modeling, animation, "
     "physical simulation for graphics, geometric processing, GPU shading, "
     "computational photography on the synthesis side, generative graphics."),
    ("Computer science education",
     "CS pedagogy as a research area. Includes: curriculum design, broadening "
     "participation in computing, novice programmer studies, programming "
     "environments designed for learning (e.g. Scratch/Blockly research), "
     "K-12 CS, assessment in CS."),
    ("Economics & computation",
     "Algorithmic game theory and computational economics. Includes: "
     "mechanism design, market design, auction theory, social choice, fair "
     "division, computational economics."),
    ("Human-computer interaction",
     "HCI, UX, and ACCESSIBILITY research. Includes: interaction design, "
     "user studies, usability, accessibility for people with disabilities, "
     "assistive technology, inclusive design, CSCW (computer-supported "
     "cooperative work), social-computing interface aspects, novel input/"
     "output devices, AR/VR interaction. ACCESSIBILITY work belongs HERE, "
     "not in Computer security & privacy."),
    ("Robotics",
     "Robot systems and methods. Includes: robot perception, motion "
     "planning, manipulation, control, autonomous vehicles (research side), "
     "human-robot interaction, robot learning, swarm robotics. When a person "
     "explicitly identifies as a robotics researcher, this IS their subfield."),
    ("Visualization",
     "Data and scientific visualization. Includes: information visualization, "
     "visual analytics, dashboard design, immersive/AR visualization, "
     "visualization of high-dimensional or scientific data."),
    ("Computational social science",
     "Computational methods applied to social, political, or cultural data. "
     "Includes: computational analysis of social media, networks of human "
     "behavior, computational political science, digital sociology."),
    ("Games & interactive art",
     "Game research and interactive media. Includes: game design as research, "
     "game AI, procedural content generation, generative art, interactive "
     "installations, computational creativity."),
]
CS_SUBFIELD_NAMES = [name for name, _ in CS_SUBFIELDS]
CS_SUBFIELD_LOOKUP = {name.lower(): name for name in CS_SUBFIELD_NAMES}

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {"type": "string"},
        "field_reasoning": {"type": "string"},
        "field": {"type": "string", "enum": ALLOWED_FIELDS},
        "subfield_reasoning": {"type": "string"},
        "subfields": {
            "type": "array",
            "items": {"type": "string", "enum": CS_SUBFIELD_NAMES},
            "maxItems": MAX_SUBFIELDS,
        },
        "rationale": {"type": "string"},
    },
    "required": [
        "evidence",
        "field_reasoning",
        "field",
        "subfield_reasoning",
        "subfields",
        "rationale",
    ],
}

SYSTEM_PROMPT = (
    "You are an academic-profile classifier. Given evidence about a faculty "
    "member (website text and/or Google Scholar interests), you decide which "
    "umbrella field their research and teaching belongs to and, if they are in "
    "Computer Science, which subfields. You output JSON matching the provided "
    "schema. You output JSON only - no prose, no markdown."
)

TAXONOMY_BLOCK = "\n".join(f"- {name}: {desc}" for name, desc in CS_SUBFIELDS)

DISAMBIGUATION_RULES = f"""\
Classification rules:
1. The department name is NOT the answer. Many liberal-arts colleges have joint
   "Mathematics & Computer Science" or "Math, Statistics & CS" departments. Classify
   based on the person's actual research and primary teaching focus, not the
   department label.
2. Pure mathematicians (topology, number theory, abstract algebra, real/complex
   analysis, differential geometry, combinatorics without algorithmic focus,
   mathematical logic without verification angle) -> "Mathematics or Statistics",
   even if they teach intro CS courses.
3. Statisticians of any flavor (mathematical statistics, applied statistics,
   biostatistics, statistical theory, probability theory) -> "Mathematics or
   Statistics".
4. "Computational X" belongs to Computer Science only when the methodological
   contribution is computational (algorithms, systems, ML methods). If the
   contribution is to the X domain itself using standard computational tools, it
   belongs to that domain (so a statistician who runs simulations -> "Mathematics or
   Statistics", not Computer Science).
   IMPORTANT: This "domain vs method" rule applies to NON-CS domains (biology,
   sociology, fluid mechanics, physiology). It does NOT apply to subfields that are
   themselves listed in the CS taxonomy. Robotics, Computer graphics, HCI, NLP,
   Computer vision, Computational bio & bioinformatics, Visualization, Computational
   social science, Games & interactive art, Computer science education, etc. are CS
   subfields. If a person's stated primary research is one of these, that IS the
   subfield - do not demote it to "just an application".
5. Computer scientists who also teach math/stats courses still go to Computer Science
   if their research is in CS.
6. Use Unknown when the evidence exists but has no usable signal about research or
   teaching areas.
7. Use Invalid when the text is clearly not a faculty profile (e.g. 404 page, error
   stub, navigation-only content, captcha block, or a profile of a different person).
8. Subfields are populated ONLY when field == "Computer Science". For all other
   fields, subfields must be an empty array.
9. Subfield evidence bar is HIGH. Only include a subfield if there is direct,
   substantive evidence in the text or Scholar interests - multiple mentions, an
   explicit research/teaching area, listed publications, or a project description.
   Do NOT assign a subfield from:
     - a single tangential keyword ("uses ML in passing")
     - generic college/department boilerplate
     - tools or domains that merely sit adjacent to the work (e.g. "logic synthesis"
       does not automatically imply Computer architecture; "human subjects"
       does not imply Human-computer interaction; "data" does not imply Data
       science).
   When in doubt, leave the subfield out.
10. Return only as many subfields as GENUINELY apply (0 through {MAX_SUBFIELDS} - fewer is
    better than padding). Zero subfields is acceptable for Computer Science when
    no specific subfield has strong evidence. Do not repeat a subfield. Order by
    importance to the person's research.
11. CONSISTENCY: the final "subfields" array must contain exactly the entries
    rated "strong" in your "subfield_reasoning" - no additions, no omissions, no
    substitutions. If a subfield is not rated "strong", it must NOT appear in
    "subfields". Reread your subfield_reasoning before emitting subfields.
12. IMPORTANT - enum hygiene: every entry in "subfields" must be one of the
    exact taxonomy strings listed above (with the exact spelling and
    capitalization). When subfield_reasoning mentions a concept that is NOT in
    the taxonomy (e.g. "Accessibility", "Deep learning", "Sentence processing",
    "AI safety", "Machine translation", "Recommender systems"), map it to its
    PARENT taxonomy entry - for example, Accessibility -> Human-computer
    interaction, Deep learning -> Machine learning, Sentence processing ->
    Natural language processing, Recommender systems -> Information retrieval.
    If two reasoning concepts both map to the SAME taxonomy entry, list that
    entry only ONCE. NEVER substitute a different taxonomy entry just to fill
    a slot - fewer subfields is correct, padding is wrong.
13. NO COMPUTER SECURITY & PRIVACY FALLBACK: never include "Computer security & privacy" unless
    the research is explicitly about adversarial threats, attackers, malware,
    cryptographic systems, or confidentiality of data. Accessibility, "privacy
    policy" page footers, child-facing tools, ethics research, or anything
    about "protecting users" in a general sense do NOT qualify. If you are
    tempted to add "Computer security & privacy" because you have a second strong
    concept that doesn't fit the taxonomy, instead list ONE subfield and stop.

Output structure (the schema enforces this):
- "evidence": briefly quote or paraphrase the 1-3 strongest signals from the
  available evidence that indicate research focus.
- "field_reasoning": 1-2 sentences applying the rules above to pick a field.
- "field": one of the allowed values.
- "subfield_reasoning": for Computer Science, list each candidate subfield and
  rate the evidence (strong / weak / none); reject the weak/none ones. Empty
  string for non-CS fields.
- "subfields": final list (0-{MAX_SUBFIELDS} entries), only those rated "strong".
- "rationale": one short summary sentence.
"""

EXAMPLES_BLOCK = """\
Examples (each shows the full reasoning + answer the schema expects):

Example 1 - CS in a joint Math/CS department; reject a weakly-supported third subfield:
Input:
  Name: Jane Doe
  Title: Associate Professor
  College: Example College
  Scholar interests: Computer security; Privacy; Usable security
  Website excerpt: "My research is on usable privacy and security. I study how
    non-expert users make security decisions and design tools that make secure
    behavior easier. I sometimes use machine learning models to cluster user
    behavior patterns."
Output:
{"evidence": "Scholar tags 'Computer security; Privacy; Usable security'; site states research is usable privacy/security with HCI lens.", "field_reasoning": "Research is squarely in CS (security with HCI methodology); not pure math/stats.", "field": "Computer Science", "subfield_reasoning": "Computer security & privacy: strong (multiple mentions, primary topic). Human-computer interaction: strong (usable security, user-facing tools). Machine learning: weak (mentioned once as an auxiliary tool, not a research area). Reject ML.", "subfields": ["Computer security & privacy", "Human-computer interaction"], "rationale": "Usable security/privacy with HCI methods; ML is incidental tooling, not a research subfield."}

Example 2 - Pure mathematician in a joint Math/Stat/CS department:
Input:
  Name: John Smith
  Title: Professor
  College: Example College
  Scholar interests: Algebraic topology; Knot theory
  Website excerpt: "I work in algebraic topology, focusing on knot invariants. I
    teach Calculus and Intro to Computer Science."
Output:
{"evidence": "Scholar interests are 'Algebraic topology; Knot theory'; site explicitly states research is algebraic topology / knot invariants.", "field_reasoning": "Topology/knot theory is pure mathematics. Teaching intro CS courses does not redirect classification per rule 1.", "field": "Mathematics or Statistics", "subfield_reasoning": "", "subfields": [], "rationale": "Pure topology research; intro CS teaching is irrelevant."}

Example 3 - Theorist whose adjacent application could mislead the model:
Input:
  Name: Sam Lee
  Title: Assistant Professor
  College: Example College
  Scholar interests: (not available)
  Website excerpt: "My research interests are computational complexity, algorithm
    design and analysis, and logic synthesis. I studied high-performance
    algorithms for optimal logic synthesis."
Output:
{"evidence": "Site lists three research interests: computational complexity, algorithm design, logic synthesis. PhD work was algorithms for logic synthesis.", "field_reasoning": "Algorithm-/complexity-flavored CS research; clearly Computer Science, not pure math.", "subfield_reasoning": "Algorithms & complexity: strong (two of three stated interests, plus thesis). Design automation: weak - 'logic synthesis' is the application domain, not a contribution to EDA tooling itself; primary contribution is algorithmic. Computer architecture: none - no hardware microarchitecture work mentioned. Reject DA and architecture.", "field": "Computer Science", "subfields": ["Algorithms & complexity"], "rationale": "Theory-side researcher whose application is logic synthesis; subfield is algorithms, not hardware."}

Example 4 - Invalid (not a real faculty profile):
Input:
  Name: Bob Jones
  Title: Professor
  College: Example College
  Scholar interests: (not available)
  Website excerpt: "Page not found. The page you are looking for has been moved
    or no longer exists. Return to home page."
Output:
{"evidence": "Page consists of a 404 message only.", "field_reasoning": "No profile content; cannot classify.", "field": "Invalid", "subfield_reasoning": "", "subfields": [], "rationale": "Page is a 404 stub."}

Example 5 - CS with a clearly dominant single subfield, reject domain-adjacent tags:
Input:
  Name: Maria Lopez
  Title: Assistant Professor
  College: Example College
  Scholar interests: Robotics; Motion planning
  Website excerpt: "My lab studies motion planning and manipulation for
    autonomous robots. We collect data from physical robot trials."
Output:
{"evidence": "Scholar interests are robotics + motion planning; site describes robotic motion planning lab.", "field_reasoning": "Clearly Computer Science.", "subfield_reasoning": "Robotics: strong (entire research program). Data science: none - collecting trial data is not data-science research. Machine learning: none - not mentioned as a research focus. Single subfield only.", "field": "Computer Science", "subfields": ["Robotics"], "rationale": "Robotics-only; data collection is incidental."}

Example 6a - Accessibility researcher; map "Accessibility" to HCI, do NOT add
Computer security & privacy as a substitute:
Input:
  Name: Pat Kim
  Title: Associate Professor
  College: Example College
  Scholar interests: accessibility; human-computer interaction
  Website excerpt: "My research is in accessibility, making digital interfaces
    more usable for people with disabilities. Recent work focuses on accessible
    programming environments for children with visual impairments."
Output:
{"evidence": "Scholar tags 'accessibility; human-computer interaction'; site centers on accessibility of digital interfaces and accessible programming environments for visually impaired children.", "field_reasoning": "Accessibility/HCI research; clearly Computer Science.", "subfield_reasoning": "Human-computer interaction: strong (explicitly named in Scholar and website). Accessibility: strong but is NOT a separate taxonomy entry - it rolls up into HCI. Both strong concepts therefore map to the SAME taxonomy entry; list HCI once. No other subfield has evidence. Do NOT add Computer security & privacy as a substitute - the research is not adversarial.", "field": "Computer Science", "subfields": ["Human-computer interaction"], "rationale": "Accessibility/HCI research; the array has one entry because Accessibility rolls into HCI."}

Example 6 - Computational psycholinguist; reject HCI based on 'human subjects':
Input:
  Name: Lee Park
  Title: Assistant Professor
  College: Example College
  Scholar interests: Computational linguistics; Sentence processing; Neural language models
  Website excerpt: "I work at the intersection of sentence processing and
    computational linguistics. My research involves human subjects experiments
    and computational modeling with neural language models."
Output:
{"evidence": "Scholar tags computational linguistics, sentence processing, neural LMs; site centers NLP + psycholinguistics.", "field_reasoning": "Computational linguistics with neural LMs is core CS / NLP.", "subfield_reasoning": "Natural language processing: strong (primary topic, neural LMs). Artificial intelligence: weak - neural LMs sit under NLP for this person; would only add AI if there were broader AI research. Human-computer interaction: none - 'human subjects experiments' here means psycholinguistic experiments, not interface/UX research. Reject AI and HCI.", "field": "Computer Science", "subfields": ["Natural language processing"], "rationale": "Computational psycholinguistics; NLP only - 'human subjects' is psycholinguistics, not HCI."}

Example 7 - Scholar-only fallback (no website text available):
Input:
  Name: Alex Rivera
  Title: Assistant Professor
  College: Example College
  Scholar interests: distributed systems; consensus protocols; blockchain
  (No website text - classify from Scholar interests alone.)
Output:
{"evidence": "Scholar interests explicitly: distributed systems, consensus protocols, blockchain.", "field_reasoning": "Distributed-systems research; clearly Computer Science.", "subfield_reasoning": "Distributed systems: strong (named directly, plus consensus and blockchain which are textbook distributed-systems topics).", "field": "Computer Science", "subfields": ["Distributed systems"], "rationale": "Three Scholar tags all map to Distributed systems."}
"""


_submit_prompt_count = 0


def submit_prompt(prompt):
    """Send a prompt to Ollama with throttling.

    After every call we sleep THROTTLE_PER_REQUEST_SEC, and after every
    THROTTLE_BREAK_INTERVAL calls we take a longer THROTTLE_BREAK_SEC cool-down.
    This lets the GPU dissipate heat between long batch runs.
    """
    global _submit_prompt_count
    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": JSON_SCHEMA,
        "keep_alive": "30m",
        "options": {
            "seed": 47,
            "temperature": 0,
            "top_p": 1.0,
            "repeat_penalty": 1.0,
            "num_ctx": 16384,
            "num_predict": 1024,
        },
    }
    last_err = None
    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            response = resp.json()["response"]
            break
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    _submit_prompt_count += 1
    if THROTTLE_BREAK_INTERVAL > 0 and _submit_prompt_count % THROTTLE_BREAK_INTERVAL == 0:
        print(
            f"\n[throttle] {_submit_prompt_count} Ollama calls so far; "
            f"sleeping {THROTTLE_BREAK_SEC:.0f}s to let the GPU cool."
        )
        time.sleep(THROTTLE_BREAK_SEC)
    elif THROTTLE_PER_REQUEST_SEC > 0:
        time.sleep(THROTTLE_PER_REQUEST_SEC)

    if response is None:
        print(f"\nOllama call failed after {MAX_RETRIES + 1} attempts: {last_err}")
    return response


def build_website_prompt(name, title, college, scholar_interests, text):
    text = text[:MAX_TEXT_CHARS]
    scholar_block = (
        f"Google Scholar interests (auxiliary signal): {scholar_interests}\n"
        if scholar_interests
        else "Google Scholar interests: (not available)\n"
    )
    return f"""\
Classify the faculty member below using their website text as the primary signal.

Allowed fields: {", ".join(ALLOWED_FIELDS)}

Computer Science subfields (only used when field == "Computer Science"):
{TAXONOMY_BLOCK}

{DISAMBIGUATION_RULES}

{EXAMPLES_BLOCK}

Now classify this faculty member:
- Name: {name}
- Title: {title}
- College: {college}
{scholar_block}
Website text (may contain noise, truncated):
<START OF TEXT>
{text}
<END OF TEXT>

Output JSON matching the schema. Subfields empty unless field is Computer Science.
At most {MAX_SUBFIELDS} subfields. The "rationale" field is one short sentence.
"""


def build_scholar_prompt(name, title, college, scholar_interests):
    return f"""\
Classify the faculty member below. NO website text is available - the only
signal you have is their Google Scholar interests (which are a verified
authoritative source). Classify based on those Scholar tags only. Only return
"Unknown" if the interests are empty or completely off-topic (e.g. clearly
non-academic). Do NOT return "Invalid" - this is verified Scholar data, not a
broken webpage.

Allowed fields: {", ".join(ALLOWED_FIELDS)}

Computer Science subfields (only used when field == "Computer Science"):
{TAXONOMY_BLOCK}

{DISAMBIGUATION_RULES}

{EXAMPLES_BLOCK}

Now classify this faculty member from Scholar interests only:
- Name: {name}
- Title: {title}
- College: {college}
- Google Scholar interests (authoritative): {scholar_interests}

Output JSON matching the schema. Subfields empty unless field is Computer Science.
At most {MAX_SUBFIELDS} subfields. The "rationale" field is one short sentence.
"""


def parse_response(raw):
    if raw is None:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None

    field = obj.get("field", "")
    if field not in ALLOWED_FIELDS:
        return {"field": "Unknown", "subfields": []}

    subfields_raw = obj.get("subfields") or []
    if field != "Computer Science":
        return {"field": field, "subfields": []}

    seen = set()
    canonical = []
    for s in subfields_raw:
        if not isinstance(s, str):
            continue
        norm = CS_SUBFIELD_LOOKUP.get(s.strip().lower())
        if norm and norm not in seen:
            seen.add(norm)
            canonical.append(norm)
        if len(canonical) >= MAX_SUBFIELDS:
            break
    return {"field": field, "subfields": canonical}


def _trusted_scholar_interests(row):
    """Return non-empty Scholar interests string only when the row's Scholar
    match status is in TRUSTED_SCHOLAR_STATUSES. Empty string otherwise."""
    status = row.get("scholar_match_status")
    if not (isinstance(status, str) and status in TRUSTED_SCHOLAR_STATUSES):
        return ""
    interests = row.get("scholar_interests")
    if isinstance(interests, str) and interests.strip():
        return interests.strip()
    return ""


def classify_row(row, verbose=False):
    """Two-pass classification.

    Pass 1: classify from the cleaned website text (using Scholar interests
            as auxiliary context when trusted).
    Pass 2: if Pass 1 returns Unknown/Invalid AND we have trusted Scholar
            interests, retry with Scholar interests as the sole signal.

    If both passes fail to yield a CS / Math classification, the result is
    returned as-is (the calling code will leave the row's prior value in place
    or mark it for manual review).
    """
    name = row["name"]
    title = row.get("title") if pd.notna(row.get("title")) else ""
    college = row["college"]

    scholar_interests = _trusted_scholar_interests(row)

    path = Path(CLEANED_WEBSITE_PATH) / college / f"{name}.txt"
    text = None
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if len(text.strip()) < MIN_TEXT_CHARS:
            text = None

    # Pass 1: website + scholar (when both available).
    website_result = None
    if text is not None:
        prompt = build_website_prompt(name, title, college, scholar_interests, text)
        raw = submit_prompt(prompt)
        website_result = parse_response(raw)
        if verbose:
            print(f"  Pass 1 (website): {website_result}")
        if website_result is not None and website_result["field"] in (
            "Computer Science",
            "Mathematics or Statistics",
        ):
            return {**website_result, "source": "website"}

    # Pass 2: scholar-only fallback when website failed AND we have trusted
    # scholar interests.
    if scholar_interests:
        prompt = build_scholar_prompt(name, title, college, scholar_interests)
        raw = submit_prompt(prompt)
        scholar_result = parse_response(raw)
        if verbose:
            print(f"  Pass 2 (scholar): {scholar_result}")
        if scholar_result is not None and scholar_result["field"] in (
            "Computer Science",
            "Mathematics or Statistics",
        ):
            return {**scholar_result, "source": "scholar"}

    # Neither pass produced a CS/Math classification. Return the best Unknown/
    # Invalid signal we have so the row still gets a sensible value for the
    # manual-review step.
    if website_result is not None:
        return {**website_result, "source": "website"}
    if text is None and not scholar_interests:
        return {"field": "Invalid", "subfields": [], "source": "no_data"}
    return {"field": "Unknown", "subfields": [], "source": "no_signal"}


def needs_processing(value):
    if pd.isna(value):
        return True
    s = str(value).strip()
    return s == "" or s == "rescrape"


OUTPUT_COLUMNS = ["name", "title", "college", "field", "subfields"]


def atomic_write_csv(df, path):
    """Write CSV to a tmp file then atomically rename.

    `os.replace` is atomic on POSIX and best-effort atomic on Windows. Even if
    the process is killed mid-write, the previous on-disk file is preserved
    intact - the partial write only ever lives in the .tmp sibling.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    df[OUTPUT_COLUMNS].to_csv(tmp, index=False)
    os.replace(tmp, p)


def load_working_df():
    """Load source CSV, merging in any prior progress from OUTPUT_PATH."""
    source = pd.read_csv(SOURCE_PATH)
    google_scholar = pd.read_csv(GOOGLE_SCHOLAR_PATH)
    source = pd.merge(source, google_scholar, how="inner", on=["name", "title", "college"])
    if "field" not in source.columns:
        source["field"] = ""
    if "subfields" not in source.columns:
        source["subfields"] = ""

    out_path = Path(OUTPUT_PATH)
    if not out_path.is_file():
        return source

    try:
        existing = pd.read_csv(OUTPUT_PATH)
    except Exception as e:
        print(f"WARNING: existing {OUTPUT_PATH} unreadable ({e}); starting fresh.")
        return source

    if "field" not in existing.columns:
        return source

    prior = {}
    for _, r in existing.iterrows():
        key = (r["name"], r["college"])
        field = r.get("field", "")
        subfields = r.get("subfields", "")
        prior[key] = (
            "" if pd.isna(field) else str(field),
            "" if pd.isna(subfields) else str(subfields),
        )

    for i, row in source.iterrows():
        key = (row["name"], row["college"])
        if key in prior:
            f, sf = prior[key]
            source.at[i, "field"] = f
            source.at[i, "subfields"] = sf

    print(f"Resuming: {sum(1 for v in prior.values() if v[0] not in ('', 'rescrape'))} prior classifications loaded.")
    return source


if __name__ == "__main__":
    faculty = load_working_df()

    todo_mask = faculty["field"].apply(needs_processing) & faculty["url"].notna()
    todo_idx = faculty.index[todo_mask].tolist()
    print(f"{len(todo_idx)} rows to classify (of {len(faculty)} total).")

    # Initial flush so OUTPUT_PATH exists from the start.
    atomic_write_csv(faculty, OUTPUT_PATH)

    source_counts = {"website": 0, "scholar": 0, "no_data": 0, "no_signal": 0}

    for i in tqdm(todo_idx, desc="Classifying faculty"):
        row = faculty.loc[i]
        try:
            result = classify_row(row)
        except Exception as e:
            print(f"\nError on {row['name']} | {row['college']}: {e}")
            continue

        if result is None:
            print(f"\nSkipping {row['name']} | {row['college']}: model returned no usable output")
            continue

        faculty.at[i, "field"] = result["field"]
        faculty.at[i, "subfields"] = "|".join(result["subfields"])
        source_counts[result.get("source", "no_signal")] = source_counts.get(result.get("source", "no_signal"), 0) + 1
        try:
            atomic_write_csv(faculty, OUTPUT_PATH)
        except Exception as e:
            print(f"\nWARNING: failed to write checkpoint at row {i}: {e}")

    print("Done.")
    print(f"Classification sources: {source_counts}")
