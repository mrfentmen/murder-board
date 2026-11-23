# Saved Datasets, Benchmarks, Papers & Live Public Archives

**Policy:** Links and API endpoints saved for training curriculum design, benchmarking, and post-fine-tune cold-case evaluation. No external model weights or third-party HuggingFace/arXiv archives were downloaded onto this machine.

---

## 1. Real-World Cold-Case Target Workspace (Post-Sim, Post-Fine-Tune Gate)
- **CrimeOwl AI — Public & Private Cold-Case Workspace**
  - Main platform: `https://crimeowl.ai/`
  - Public case library (homicides, missing persons, FBI Wanted syncs, financial fugitives incl. *Ellen Greenberg*, *Jennifer Kesse*, *Carnell Sledge*, *Amy Bradley*, *Shelton Sanders*, *Bhadreshkumar Patel*, *Ruja Ignatova / OneCoin*): `https://crimeowl.ai/cases`
  - Law enforcement workflow overview: `https://crimeowl.ai/law-enforcement`

---

## 2. Core Detective & Deductive Reasoning Datasets / Papers
- **DetectiveQA** (Long-context ~100K-token classical detective novels, 1,200 questions with paragraph-level clue indices, distractor analysis, and step-by-step reasoning chains; Apache-2.0)
  - Hugging Face Dataset: `https://huggingface.co/datasets/Phospheneser/DetectiveQA`
- **MuSR: Testing the Limits of Chain-of-Thought with Multistep Soft Reasoning** (Sprague et al., ICLR 2024 Spotlight — neurosymbolic reasoning-tree murder mysteries, ~1,000-word narratives)
  - Paper PDF: `https://arxiv.org/pdf/2310.16049`
  - Abstract / Landing: `https://arxiv.org/abs/2310.16049`
- **TurnaboutLLM: A Deductive Reasoning Benchmark from Detective Games** (Yuan et al., EMNLP 2025 — *Ace Attorney* & *Danganronpa* interactive testimony-vs-evidence contradiction spotting)
  - Paper PDF: `https://aclanthology.org/2025.emnlp-main.101.pdf`
  - ACL Anthology Page: `https://aclanthology.org/2025.emnlp-main.101/`
- **WhodunitBench: Evaluating Large Multimodal Agents via Murder Mystery Games** (Xie et al., NeurIPS 2024 Datasets & Benchmarks Spotlight — 50 curated scripts + 3,000+ evaluation questions)
  - NeurIPS Poster / Abstract: `https://neurips.cc/virtual/2024/poster/97492`
  - Open-Source GitHub Repo: `https://github.com/jun0wanan/WhodunitBench-Murder_Mystery_Games`

---

## 3. Complementary Forensic & Investigative Skill Corpora (Cloud Training Mix)
### A. Temporal & Timeline Ordering
- **TORQUE** (Temporal Ordering Questions): `https://allenai.org/data/torque` / `https://arxiv.org/abs/2005.00246`
- **TimeQA** (Time-sensitive factual reasoning across evolving timelines): `https://arxiv.org/abs/2108.06314`
- **TempReason** (Temporal grounding, interval arithmetic, and event ordering): `https://arxiv.org/abs/2306.03872`

### B. Multi-Hop Retrieval & Strict Fact Verification (NLI)
- **MuSiQue** (Multi-hop questions via single-hop composition — forces real multi-hop retrieval): `https://arxiv.org/abs/2108.00573`
- **HotpotQA**: `https://hotpotqa.github.io/`
- **2WikiMultihopQA**: `https://arxiv.org/abs/2011.01060`
- **FEVER** (Fact Extraction and VERification — `SUPPORTED` / `REFUTED` / `NOT ENOUGH INFO`): `https://fever.ai/`
- **ContractNLI** (Document-level evidence span citation + contradiction/entailment): `https://stanfordnlp.github.io/contract-nli/`
- **SciFact**: `https://github.com/allenai/scifact`

### C. Entity Resolution, Coreference & Knowledge Graph Extraction (GraphRAG)
- **DocRED** (Document-Level Relation Extraction across multi-paragraph entities & aliases): `https://arxiv.org/abs/1906.06127`
- **OntoNotes 5.0** (Coreference & named-entity linking): `https://catalog.ldc.upenn.edu/LDC2013T19`

### D. Legal, Exoneration & Forensic Science Reference Archives
- **Harvard Caselaw Access Project (CAP) / Free Law Project CourtListener**: `https://case.law/` · `https://www.courtlistener.com/`
- **FBI Vault (FOIA Declassified Investigative Files & FD-302s)**: `https://vault.fbi.gov/`
- **National Registry of Exonerations** (Real wrongful-conviction tunnel-vision & false-alibi cases): `https://www.law.umich.edu/special/exoneration/`
- **National Institute of Justice (NIJ) Cold Case & Forensic Guides**: `https://nij.ojp.gov/topics/law-enforcement/investigations/cold-case-investigations`
- **NamUs (National Missing and Unidentified Persons System)**: `https://namus.nij.ojp.gov/`
- **ICIJ Offshore Leaks Database** (Panama / Pandora / Paradise corporate shell graphs): `https://offshoreleaks.icij.org/`

---

## 4. Track 2 ("Future Room AI") — Biometric, Stress, rPPG & Deception Benchmarks
Used to ground sensor distributions (`HR`, `HRV RMSSD`, `EDA` sweat conductance, periorbital temperature, pupil dilation, vocal jitter, response latency) in peer-reviewed human physiology:
- **WESAD (Wearable Stress and Affect Detection — UCI ML Repository):** Chest & wrist `ECG`, `BVP/PPG`, `EDA (µS)`, `EMG`, respiration, and temperature under baseline, stress, and cognitive load — `https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection`
- **Bag-of-Lies (Multimodal Deception Dataset):** Synchronized video, audio, gaze/pupil, and physiological recordings on truthful vs. deceptive recall — `https://arxiv.org/abs/1904.03656`
- **Real-Life Trial Deception Dataset (Pérez-Rosas et al., Univ. of Michigan):** Real public courtroom video/audio/transcripts comparing verified truthful vs. deceptive testimony — `https://lit.eecs.umich.edu/downloads.html`
- **Miami University Deception Detection Database (MU3D):** Standardized truthful/deceptive interview videos & transcripts — `https://sc.lib.miamioh.edu/handle/2374.MIA/6067`
- **UBFC-rPPG (Contactless Camera Photoplethysmography Benchmark):** Remote facial video heart-rate and `HRV` extraction — `https://sites.google.com/view/ybenezeth/ubfcrppg`
- **Concealed Information Test (CIT) & Cognitive-Load Interviewing Foundations:** Verschuere, Ben-Shakhar & Meijer (*Memory Detection: Theory and Application of the Concealed Information Test*); Vrij et al. (*Cognitive-Load Deception Detection & Reverse-Order Recall*).

---

## 5. Live Open Public APIs Wired Into `training/real_archives/harvest_and_despoil.py`
- **Old Bailey Proceedings API (1674–1913 Homicide Trials):**
  - Search: `https://www.dhi.ac.uk/api/data/oldbailey_record`
  - Full XML/HTML Witness & Surgeon Transcript: `https://www.dhi.ac.uk/api/data/oldbailey_record_single?idkey=<ID>`
- **U.S. Department of Justice Public Case & Indictment API (Homicide, Cold Case, RICO, Money Laundering):**
  - `https://www.justice.gov/api/v1/press_releases.json`
- **FDNY / NYC 911 EMS Incident Dispatch Data (2005 Historical – 2026 Modern):**
  - `https://data.cityofnewyork.us/resource/76xm-jjuj.json`
- **NYPD 911 Calls for Service:**
  - `https://data.cityofnewyork.us/resource/n2zq-pubd.json`
- **San Francisco Police Department (SFPD) 911 Calls for Service (incl. Original vs. Final Reclassifications):**
  - `https://data.sfgov.org/resource/gnap-fj3t.json`
- **San Francisco Fire / EMS 911 Dispatches:**
  - `https://data.sfgov.org/resource/nuek-vuh3.json`
- **Seattle Real-Time / Historical Fire 911 Calls:**
  - `https://data.seattle.gov/resource/kzjm-xkqj.json`
- **U.S. Treasury OFAC Specially Designated Nationals (Cartel & Shell Networks):**
  - `https://www.treasury.gov/ofac/downloads/sdn.csv`
