"""Map OpenAlex subfields/topics → our internal CS subfields.

OpenAlex tags each work with multiple `topics` (granular, ~4000 globally) and
their parent `subfields` (broader, ~270 globally). Our taxonomy of 32 CS
subfields lives in `scraper/faculty_site_analysis.CS_SUBFIELDS`.

This module provides `map_paper_to_cs_subfields(topics, subfields)` which
returns the union of our CS subfields a paper belongs to, used to gate paper
visibility when the user clicks a subfield chip in the dashboard.

Design notes:
- ONLY topics are used. OpenAlex `subfields` are too noisy to map directly:
  a software-testing paper ends up in "Computer Networks and Communications";
  a paper about Cuban drums sits under "Computer Vision and Pattern
  Recognition"; broad subfields like "Artificial Intelligence" cover NLP/ML/
  CV/PL all at once. The 4000-topic taxonomy is much more reliable.
- The mapping is intentionally conservative: when a topic could plausibly
  belong to multiple of our subfields, we list them all; when a topic is
  borderline (pure math, music, physics, pure EE), we leave it unmapped.
  Papers with no mapped topic end up with an empty list — that's fine and
  expected (~3% of papers).
- The `openalex_subfields` argument to `map_paper_to_cs_subfields` is kept
  in the signature for forward compatibility but currently ignored.
"""

from __future__ import annotations


# Granular OpenAlex topic -> our CS subfields. Topics not listed here
# contribute no tags (the paper falls back to its subfield mapping above,
# which may also produce nothing — that's fine, the paper is "untagged").
OPENALEX_TOPIC_TO_CS: dict[str, list[str]] = {
    # ── CS Education ──────────────────────────────────────────────────
    "Teaching and Learning Programming": ["Computer science education"],
    "Innovative Teaching and Learning Methods": ["Computer science education"],
    "Innovative Teaching Methods": ["Computer science education"],
    "Information Systems Education and Curriculum Development": ["Computer science education"],
    "Experimental Learning in Engineering": ["Computer science education"],
    "Online Learning and Analytics": ["Computer science education"],
    "Online and Blended Learning": ["Computer science education"],
    "Open Education and E-Learning": ["Computer science education"],
    "Intelligent Tutoring Systems and Adaptive Learning": ["Computer science education"],
    "Educational Technology and Assessment": ["Computer science education"],
    "Gender and Technology in Education": ["Computer science education"],
    "Wikis in Education and Collaboration": ["Computer science education"],
    "E-Learning and Knowledge Management": ["Computer science education"],
    "Biomedical and Engineering Education": ["Computer science education"],
    "Statistics Education and Methodologies": ["Computer science education"],
    "Student Assessment and Feedback": ["Computer science education"],
    "Problem and Project Based Learning": ["Computer science education"],
    "Educational Assessment and Pedagogy": ["Computer science education"],
    "Educational Robotics and Engineering": ["Computer science education", "Robotics"],
    "Educational Games and Gamification": ["Computer science education", "Games & interactive art"],
    "Mobile Learning in Education": ["Computer science education", "Mobile computing"],
    "Career Development and Diversity": ["Computer science education"],
    "Service-Learning and Community Engagement": ["Computer science education"],
    "Higher Education and Teaching Methods": ["Computer science education"],
    "Academic integrity and plagiarism": ["Computer science education"],
    "Digital Storytelling and Education": ["Computer science education"],

    # ── Software Engineering ──────────────────────────────────────────
    "Software Engineering Research": ["Software engineering"],
    "Software Engineering Techniques and Practices": ["Software engineering"],
    "Software Testing and Debugging Techniques": ["Software engineering"],
    "Software Reliability and Analysis Research": ["Software engineering"],
    "Software Engineering and Design Patterns": ["Software engineering"],
    "Advanced Software Engineering Methodologies": ["Software engineering"],
    "Model-Driven Software Engineering Techniques": ["Software engineering"],
    "Open Source Software Innovations": ["Software engineering"],
    "Service-Oriented Architecture and Web Services": ["Software engineering"],
    "Business Process Modeling and Analysis": ["Software engineering"],
    "Spreadsheets and End-User Computing": ["Software engineering"],
    "Mobile and Web Applications": ["Software engineering", "Mobile computing"],
    "Web Applications and Data Management": ["Software engineering", "Databases"],
    "Software System Performance and Reliability": ["Software engineering", "Measurement & performance analysis"],

    # ── Programming Languages ─────────────────────────────────────────
    "Logic, programming, and type systems": ["Programming languages"],

    # ── Natural Language Processing ───────────────────────────────────
    "Natural Language Processing Techniques": ["Natural language processing"],
    "Topic Modeling": ["Natural language processing"],
    "Text Readability and Simplification": ["Natural language processing"],
    "Sentiment Analysis and Opinion Mining": ["Natural language processing"],
    "Speech and dialogue systems": ["Natural language processing"],
    "Speech Recognition and Synthesis": ["Natural language processing"],
    "Speech and Audio Processing": ["Natural language processing"],
    "Advanced Text Analysis Techniques": ["Natural language processing"],
    "Computational and Text Analysis Methods": ["Natural language processing"],
    "Authorship Attribution and Profiling": ["Natural language processing"],
    "Text and Document Classification Technologies": ["Natural language processing"],
    "Hate Speech and Cyberbullying Detection": ["Natural language processing", "Computational social science"],
    "Biomedical Text Mining and Ontologies": ["Natural language processing", "Computational bio & bioinformatics"],

    # ── Computer Vision ───────────────────────────────────────────────
    "Advanced Vision and Imaging": ["Computer vision"],
    "Advanced Image and Video Retrieval Techniques": ["Computer vision", "Information retrieval"],
    "Image Retrieval and Classification Techniques": ["Computer vision"],
    "Video Analysis and Summarization": ["Computer vision"],
    "Digital Image Processing Techniques": ["Computer vision"],
    "Handwritten Text Recognition Techniques": ["Computer vision"],
    "Face and Expression Recognition": ["Computer vision"],
    "Face recognition and analysis": ["Computer vision"],
    "Image Processing and 3D Reconstruction": ["Computer vision"],
    "Medical Image Segmentation Techniques": ["Computer vision"],
    "Human Pose and Action Recognition": ["Computer vision"],
    "3D Shape Modeling and Analysis": ["Computer vision", "Computer graphics"],
    "Image and Object Detection Techniques": ["Computer vision"],
    "Video Surveillance and Tracking Methods": ["Computer vision"],
    "Visual Attention and Saliency Detection": ["Computer vision"],
    "Image and Video Quality Assessment": ["Computer vision"],
    "Image Enhancement Techniques": ["Computer vision"],
    "Image and Signal Denoising Methods": ["Computer vision"],
    "Image Processing Techniques and Applications": ["Computer vision"],
    "Advanced Image Processing Techniques": ["Computer vision"],
    "Remote-Sensing Image Classification": ["Computer vision"],
    "Generative Adversarial Networks and Image Synthesis": ["Computer vision", "Machine learning"],
    "Gait Recognition and Analysis": ["Computer vision"],
    "Gaze Tracking and Assistive Technology": ["Computer vision", "Human-computer interaction"],
    "Hand Gesture Recognition Systems": ["Computer vision", "Human-computer interaction"],

    # ── Machine Learning ──────────────────────────────────────────────
    "Machine Learning and Algorithms": ["Machine learning"],
    "Machine Learning and Data Classification": ["Machine learning"],
    "Adversarial Robustness in Machine Learning": ["Machine learning"],
    "Neural Networks and Applications": ["Machine learning"],
    "Advanced Neural Network Applications": ["Machine learning"],
    "Advanced Graph Neural Networks": ["Machine learning"],
    "Advanced Memory and Neural Computing": ["Machine learning"],
    "Neural Networks and Reservoir Computing": ["Machine learning"],
    "Advanced Bandit Algorithms Research": ["Machine learning"],
    "Imbalanced Data Classification Techniques": ["Machine learning"],
    "Domain Adaptation and Few-Shot Learning": ["Machine learning"],
    "Multimodal Machine Learning Applications": ["Machine learning"],
    "Bayesian Modeling and Causal Inference": ["Machine learning"],
    "Bayesian Methods and Mixture Models": ["Machine learning"],
    "Gaussian Processes and Bayesian Inference": ["Machine learning"],
    "Advanced Clustering Algorithms Research": ["Machine learning"],
    "Stochastic Gradient Optimization Techniques": ["Machine learning"],
    "Anomaly Detection Techniques and Applications": ["Machine learning"],
    "Time Series Analysis and Forecasting": ["Machine learning"],
    "Machine Learning in Bioinformatics": ["Machine learning", "Computational bio & bioinformatics"],
    "Machine Learning in Healthcare": ["Machine learning"],
    "Machine Learning in Materials Science": ["Machine learning"],
    "AI in cancer detection": ["Machine learning"],
    "COVID-19 diagnosis using AI": ["Machine learning"],
    "Reinforcement Learning in Robotics": ["Machine learning", "Robotics"],
    "Cognitive Computing and Networks": ["Machine learning"],
    "Emotion and Mood Recognition": ["Machine learning"],

    # ── Artificial Intelligence (general / symbolic) ──────────────────
    "Logic, Reasoning, and Knowledge": ["Artificial intelligence"],
    "Computability, Logic, AI Algorithms": ["Artificial intelligence", "Logic & verification"],
    "AI-based Problem Solving and Planning": ["Artificial intelligence"],
    "Multi-Agent Systems and Negotiation": ["Artificial intelligence"],
    "Constraint Satisfaction and Optimization": ["Artificial intelligence"],
    "Ethics and Social Impacts of AI": ["Artificial intelligence"],
    "Explainable Artificial Intelligence (XAI)": ["Artificial intelligence"],
    "Evolutionary Algorithms and Applications": ["Artificial intelligence"],
    "Metaheuristic Optimization Algorithms Research": ["Artificial intelligence"],
    "AI in Service Interactions": ["Artificial intelligence"],
    "Artificial Intelligence in Healthcare": ["Artificial intelligence"],
    "Artificial Intelligence in Healthcare and Education": ["Artificial intelligence"],
    "Law, AI, and Intellectual Property": ["Artificial intelligence"],
    "Rough Sets and Fuzzy Logic": ["Artificial intelligence"],
    "Fuzzy Logic and Control Systems": ["Artificial intelligence"],

    # ── Data Science ──────────────────────────────────────────────────
    "Data Mining Algorithms and Applications": ["Data science"],
    "Data Stream Mining Techniques": ["Data science"],
    "Big Data and Business Intelligence": ["Data science"],
    "Web Data Mining and Analysis": ["Data science"],
    "Data Analysis with R": ["Data science"],
    "Sports Analytics and Performance": ["Data science"],

    # ── Information Retrieval ─────────────────────────────────────────
    "Information Retrieval and Search Behavior": ["Information retrieval"],
    "Recommender Systems and Techniques": ["Information retrieval"],
    "Semantic Web and Ontologies": ["Information retrieval"],
    "Expert finding and Q&A systems": ["Information retrieval"],

    # ── Distributed Systems ───────────────────────────────────────────
    "Distributed systems and fault tolerance": ["Distributed systems"],
    "Distributed and Parallel Computing Systems": ["Distributed systems", "High-performance computing"],
    "Cloud Computing and Resource Management": ["Distributed systems"],
    "Cloud Data Security Solutions": ["Distributed systems", "Computer security & privacy"],
    "Cloud Computing and Remote Desktop Technologies": ["Distributed systems"],
    "Peer-to-Peer Network Technologies": ["Distributed systems", "Computer networks"],
    "Blockchain Technology Applications and Security": ["Distributed systems", "Computer security & privacy"],

    # ── High-Performance Computing ────────────────────────────────────
    "Parallel Computing and Optimization Techniques": ["High-performance computing"],
    "Scientific Computing and Data Management": ["High-performance computing"],

    # ── Computer Networks ─────────────────────────────────────────────
    "Internet Traffic Analysis and Secure E-voting": ["Computer networks", "Computer security & privacy"],
    "Software-Defined Networks and 5G": ["Computer networks"],
    "Network Traffic and Congestion Control": ["Computer networks"],
    "Caching and Content Delivery": ["Computer networks", "Distributed systems"],
    "Wireless Networks and Protocols": ["Computer networks"],
    "Advanced Wireless Network Optimization": ["Computer networks"],
    "Wireless Communication Networks Research": ["Computer networks"],
    "Advanced MIMO Systems Optimization": ["Computer networks"],
    "Advanced Optical Network Technologies": ["Computer networks"],
    "Interconnection Networks and Systems": ["Computer networks"],
    "Cooperative Communication and Network Coding": ["Computer networks"],
    "Mobile Ad Hoc Networks": ["Computer networks", "Mobile computing"],
    "Opportunistic and Delay-Tolerant Networks": ["Computer networks"],
    "Vehicular Ad Hoc Networks (VANETs)": ["Computer networks"],
    "IPv6, Mobility, Handover, Networks, Security": ["Computer networks", "Computer security & privacy"],
    "IoT Networks and Protocols": ["Computer networks", "Embedded & real-time systems"],
    "Mobile Agent-Based Network Management": ["Computer networks", "Mobile computing"],
    "Network Packet Processing and Optimization": ["Computer networks"],
    "Energy Harvesting in Wireless Networks": ["Computer networks"],
    "Energy Efficient Wireless Sensor Networks": ["Computer networks", "Embedded & real-time systems"],
    "Bluetooth and Wireless Communication Technologies": ["Computer networks"],
    "Multimedia Communication and Technology": ["Computer networks"],
    "Underwater Vehicles and Communication Systems": ["Computer networks"],
    "Cognitive Radio Networks and Spectrum Sensing": ["Computer networks"],
    "Security in Wireless Sensor Networks": ["Computer networks", "Computer security & privacy"],

    # ── Embedded & Real-time Systems ──────────────────────────────────
    "Embedded Systems Design Techniques": ["Embedded & real-time systems"],
    "Real-Time Systems Scheduling": ["Embedded & real-time systems", "Operating systems"],
    "IoT and Edge/Fog Computing": ["Embedded & real-time systems"],
    "IoT-based Smart Home Systems": ["Embedded & real-time systems"],
    "Smart Parking Systems Research": ["Embedded & real-time systems"],
    "Smart Grid Energy Management": ["Embedded & real-time systems"],
    "Internet of Things and AI": ["Embedded & real-time systems"],
    "Advanced Data and IoT Technologies": ["Embedded & real-time systems"],

    # ── Mobile Computing ──────────────────────────────────────────────
    "Mobile Crowdsensing and Crowdsourcing": ["Mobile computing"],
    "Human Mobility and Location-Based Analysis": ["Mobile computing", "Data science"],
    "Context-Aware Activity Recognition Systems": ["Mobile computing"],
    "Indoor and Outdoor Localization Technologies": ["Mobile computing"],

    # ── Computer Security & Privacy ───────────────────────────────────
    "Privacy-Preserving Technologies in Data": ["Computer security & privacy"],
    "Network Security and Intrusion Detection": ["Computer security & privacy"],
    "Advanced Malware Detection Techniques": ["Computer security & privacy"],
    "Privacy, Security, and Data Protection": ["Computer security & privacy"],
    "Security and Verification in Computing": ["Computer security & privacy"],
    "User Authentication and Security Systems": ["Computer security & privacy"],
    "Spam and Phishing Detection": ["Computer security & privacy"],
    "Web Application Security Vulnerabilities": ["Computer security & privacy"],
    "Information and Cyber Security": ["Computer security & privacy"],
    "Advanced Authentication Protocols Security": ["Computer security & privacy"],
    "Digital and Cyber Forensics": ["Computer security & privacy"],
    "Biometric Identification and Security": ["Computer security & privacy"],
    "Access Control and Trust": ["Computer security & privacy"],
    "Cybercrime and Law Enforcement Studies": ["Computer security & privacy"],
    "Digital Rights Management and Security": ["Computer security & privacy"],
    "Advanced Steganography and Watermarking Techniques": ["Computer security & privacy", "Cryptography"],
    "Digital Media Forensic Detection": ["Computer security & privacy"],
    "Physical Unclonable Functions (PUFs) and Hardware Security": ["Computer security & privacy", "Computer architecture"],

    # ── Databases ─────────────────────────────────────────────────────
    "Advanced Database Systems and Queries": ["Databases"],
    "Advanced Data Storage Technologies": ["Databases"],
    "Data Management and Algorithms": ["Databases", "Algorithms & complexity"],
    "Data Quality and Management": ["Databases"],

    # ── Cryptography ──────────────────────────────────────────────────
    "Cryptography and Data Security": ["Cryptography"],
    "Coding theory and cryptography": ["Cryptography"],
    "Cryptographic Implementations and Security": ["Cryptography"],
    "Quantum Information and Cryptography": ["Cryptography", "Quantum computing"],
    "Chaos-based Image/Signal Encryption": ["Cryptography"],
    "Cryptography and Residue Arithmetic": ["Cryptography"],
    "Error Correcting Code Techniques": ["Cryptography"],

    # ── Quantum Computing ─────────────────────────────────────────────
    "Quantum Computing Algorithms and Architecture": ["Quantum computing"],

    # ── Algorithms & Complexity ───────────────────────────────────────
    "Algorithms and Data Compression": ["Algorithms & complexity"],
    "Complexity and Algorithms in Graphs": ["Algorithms & complexity"],
    "Advanced Graph Theory Research": ["Algorithms & complexity"],
    "Graph Theory and Algorithms": ["Algorithms & complexity"],
    "Graph theory and applications": ["Algorithms & complexity"],
    "Limits and Structures in Graph Theory": ["Algorithms & complexity"],
    "Graph Labeling and Dimension Problems": ["Algorithms & complexity"],
    "graph theory and CDMA systems": ["Algorithms & complexity"],
    "Optimization and Search Problems": ["Algorithms & complexity"],
    "Scheduling and Optimization Algorithms": ["Algorithms & complexity"],
    "Computational Geometry and Mesh Generation": ["Algorithms & complexity"],
    "Cellular Automata and Applications": ["Algorithms & complexity"],
    "Topological and Geometric Data Analysis": ["Algorithms & complexity"],
    "semigroups and automata theory": ["Algorithms & complexity"],
    "Matrix Theory and Algorithms": ["Algorithms & complexity"],
    "Optimization and Packing Problems": ["Algorithms & complexity"],
    "Advanced Multi-Objective Optimization Algorithms": ["Algorithms & complexity"],
    "Advanced Queuing Theory Analysis": ["Algorithms & complexity"],
    "Genome Rearrangement Algorithms": ["Algorithms & complexity", "Computational bio & bioinformatics"],
    "Vehicle Routing Optimization Methods": ["Algorithms & complexity"],

    # ── Logic & Verification ──────────────────────────────────────────
    "Formal Methods in Verification": ["Logic & verification"],
    "Petri Nets in System Modeling": ["Logic & verification"],

    # ── Computational Bio & Bioinformatics ────────────────────────────
    "Genetics, Bioinformatics, and Biomedical Research": ["Computational bio & bioinformatics"],
    "Gene Regulatory Network Analysis": ["Computational bio & bioinformatics"],
    "Bioinformatics and Genomic Networks": ["Computational bio & bioinformatics"],
    "DNA and Biological Computing": ["Computational bio & bioinformatics"],
    "Protein Structure and Dynamics": ["Computational bio & bioinformatics"],
    "Computational Drug Discovery Methods": ["Computational bio & bioinformatics"],
    "Genomics and Phylogenetic Studies": ["Computational bio & bioinformatics"],
    "Evolution and Genetic Dynamics": ["Computational bio & bioinformatics"],
    "CRISPR and Genetic Engineering": ["Computational bio & bioinformatics"],

    # ── Computer Graphics ─────────────────────────────────────────────
    "Computer Graphics and Visualization Techniques": ["Computer graphics", "Visualization"],
    "Human Motion and Animation": ["Computer graphics"],
    "3D Modeling in Geospatial Applications": ["Computer graphics"],
    "3D Surveying and Cultural Heritage": ["Computer graphics"],

    # ── Visualization ─────────────────────────────────────────────────
    "Data Visualization and Analytics": ["Visualization"],

    # ── Robotics ──────────────────────────────────────────────────────
    "Robotic Path Planning Algorithms": ["Robotics"],
    "Robotics and Sensor-Based Localization": ["Robotics"],
    "Robotic Locomotion and Control": ["Robotics"],
    "Robot Manipulation and Learning": ["Robotics"],
    "Modular Robots and Swarm Intelligence": ["Robotics"],
    "Robotics and Automated Systems": ["Robotics"],
    "Robotic Mechanisms and Dynamics": ["Robotics"],
    "Social Robot Interaction and HRI": ["Robotics", "Human-computer interaction"],
    "Teleoperation and Haptic Systems": ["Robotics", "Human-computer interaction"],
    "Distributed Control Multi-Agent Systems": ["Robotics"],
    "Micro and Nano Robotics": ["Robotics"],
    "UAV Applications and Optimization": ["Robotics"],

    # ── Human-Computer Interaction ────────────────────────────────────
    "Innovative Human-Technology Interaction": ["Human-computer interaction"],
    "Tactile and Sensory Interactions": ["Human-computer interaction"],
    "Interactive and Immersive Displays": ["Human-computer interaction"],
    "Virtual Reality Applications and Impacts": ["Human-computer interaction"],
    "Augmented Reality Applications": ["Human-computer interaction"],
    "Usability and User Interface Design": ["Human-computer interaction"],
    "Digital Accessibility for Disabilities": ["Human-computer interaction"],
    "Personal Information Management and User Behavior": ["Human-computer interaction"],
    "Persona Design and Applications": ["Human-computer interaction"],
    "Human-Automation Interaction and Safety": ["Human-computer interaction"],
    "Technology Use by Older Adults": ["Human-computer interaction"],
    "Health Literacy and Information Accessibility": ["Human-computer interaction"],
    "Digital Mental Health Interventions": ["Human-computer interaction"],
    "EEG and Brain-Computer Interfaces": ["Human-computer interaction"],
    "Assistive Technology in Communication and Mobility": ["Human-computer interaction"],
    "Hearing Impairment and Communication": ["Human-computer interaction"],

    # ── Games & Interactive Art ───────────────────────────────────────
    "Digital Games and Media": ["Games & interactive art"],
    "Artificial Intelligence in Games": ["Games & interactive art", "Artificial intelligence"],
    "Art, Technology, and Culture": ["Games & interactive art"],

    # ── Computer Architecture & Design Automation ─────────────────────
    "VLSI and FPGA Design Techniques": ["Computer architecture", "Design automation"],
    "Low-power high-performance VLSI design": ["Computer architecture", "Design automation"],
    "VLSI and Analog Circuit Testing": ["Computer architecture", "Design automation"],
    "Advancements in Semiconductor Devices and Circuit Design": ["Computer architecture"],
    "Radiation Effects in Electronics": ["Computer architecture"],

    # ── Computational Social Science ──────────────────────────────────
    "Misinformation and Its Impacts": ["Computational social science"],
    "Social Media and Politics": ["Computational social science"],
    "Opinion Dynamics and Social Influence": ["Computational social science"],
    "Complex Network Analysis Techniques": ["Computational social science", "Data science"],
    "ICT in Developing Communities": ["Computational social science"],
    "Sexuality, Behavior, and Technology": ["Computational social science"],

    # ── Economics & Computation ───────────────────────────────────────
    "Auction Theory and Applications": ["Economics & computation"],
    "Game Theory and Voting Systems": ["Economics & computation"],
    "Game Theory and Applications": ["Economics & computation"],
    "Evolutionary Game Theory and Cooperation": ["Economics & computation"],

    # ── Measurement & Performance Analysis ────────────────────────────
    # (handled via "Software System Performance and Reliability" above)
}


def map_paper_to_cs_subfields(
    topics: list[str] | None,
    openalex_subfields: list[str] | None = None,
) -> list[str]:
    """Return the union of our CS subfields that a paper belongs to.

    Order is deterministic: walks topics in order and appends each new tag.
    `openalex_subfields` is accepted but ignored — see module docstring.
    """
    result: list[str] = []
    seen: set[str] = set()
    for t in topics or ():
        for sf in OPENALEX_TOPIC_TO_CS.get(t, ()):
            if sf not in seen:
                result.append(sf)
                seen.add(sf)
    return result
