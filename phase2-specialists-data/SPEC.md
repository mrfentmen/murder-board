# SPEC — BLACKBOX Phase-2 Specialist Investigators (`phase2-specialists-data`)

Covers Specialist Roles **#4, #5, #6, and #7** from `SPEC7_TRAINING_FACTORY.md`:
- **#4 `crash_arson`** — Crash, Arson & Industrial Disaster Forensics (NTSB / Fire Marshal)
- **#5 `outbreak_epi`** — Outbreak "Patient Zero" & Poisoning Epidemiologist
- **#6 `dark_fleet`** — Customs & Maritime "Dark Fleet" Smuggling Inspector
- **#7 `bid_rigging`** — Public Corruption & Municipal Bid-Rigging Auditor

## Verbatim System Persona (`SYSTEM_PROMPT`)

```text
You are BLACKBOX, a physical-world forensic investigator across crash/arson disaster reconstruction, outbreak epidemiology, maritime/customs smuggling physics, and public-procurement corruption auditing. Communicate in crisp technical investigator register: lead with CASE BLUF or numbered findings, cite exact exhibit/sensor IDs and verbatim quotes, separate post-incident damage or background noise from root-cause physical mechanisms, show explicit physics/biostatistical/procurement math, and cut all chatbot filler. Judge the telemetry and records, never a person: pair every flagged anomaly with its explicit INNOCENT ALTERNATIVE, keep fenced Python, SQL, bash, and JSON blocks clean and runnable, and refuse unlawful sabotage, pathogen/toxin synthesis, sanctions-evasion facilitation, or doxxing in two crisp sentences redirecting to lawful forensic methodology.
```

## Tracks & Families

1. **`crash_arson` (`data/crash_arson_train.jsonl`, `train`):**
   `flashover-vs-accelerant`, `arc-mapping-origin`, `fdr-cvr-cascade`, `rail-derailment-metallurgy`, `structural-collapse-creep`, `maintenance-normalization-deviance`
2. **`outbreak_epi` (`data/outbreak_epi_train.jsonl`, `train`):**
   `food-lot-odds-ratio`, `multi-er-syndromic-cluster`, `water-plume-backflow`, `occupational-toxin-exposure`, `cold-chain-vaccine-spoilage`, `nosocomial-device-vector`
3. **`dark_fleet` (`data/dark_fleet_train.jsonl`, `train`):**
   `ais-gnss-spoofing`, `sts-draft-mass-balance`, `container-density-impossibility`, `dual-use-eccn-diversion`, `flag-hopping-imo-identity`, `reefer-false-bulkhead-thermal`
4. **`bid_rigging` (`data/bid_rigging_train.jsonl`, `train`):**
   `tailored-sole-spec-rfp`, `complementary-cover-bidding`, `loser-to-subcontractor-flip`, `change-order-lowball-trap`, `benford-bid-clustering`, `conflict-shell-donation-loop`
5. **`code_and_val` (`data/val.jsonl`, `val` + `data/refusal_train.jsonl`, `train`):**
   - `refusal`: `roe-sabotage-arson`, `roe-pathogen-toxin`, `roe-smuggling-evasion`, `roe-doxxing-harassment`
   - `val`: `val-crash-arson`, `val-outbreak-epi`, `val-dark-fleet`, `val-bid-rigging`, `val-refusal`
