"""Track 1 Simulator: Cartel, TBML & Shell-Company Money-Laundering Hunter (SPEC 7).

Implements 6 AML laundering typologies + 20% `CLEAR_NO_SAR` clean false-positive packets:
  1. SMURFING_FUNNEL (4-7 structured <$10,000 multi-branch cash drops swept within 24h
     through a newly formed zero-payroll LLC, >96% pass-through velocity)
  2. TBML_INVOICE_AND_WEIGHT_MISMATCH (uses COMMODITY_BENCHMARKS from pools.py: either
     12x-35x $/kg over-invoicing OR Bill-of-Lading container weight exceeding physical
     27,500 kg container ceiling)
  3. LAYERED_SHELL_ROUND_TRIP (3-hop loop across OFFSHORE_JURISDICTIONS formed within
     24-48 hours, sharing registered agent suite/IP block, cycling funds back as bogus
     'IP licensing / shareholder loan')
  4. CASH_FRONT_UTILITY_MISMATCH (uses CASH_FRONT_ARCHETYPES: car wash, nail spa, coin
     laundry, parking lot, vending route depositing 85-94% cash 6x-15x above municipal
     water/gas/wholesale physical ceiling)
  5. CRYPTO_PEEL_AND_OTC_SETTLEMENT (P2P/Zelle/ACH mule fan-in from 6 unrelated retail
     accounts -> zero-tax shell -> high-risk stablecoin OTC desk)
  6. ALL_CASH_REAL_ESTATE_NOMINEE (newly formed anonymous series LLC purchasing distressed
     commercial property via split foreign third-party wires with immediate flip/refinance
     loan-back)
  7. CLEAN_FALSE_POSITIVE (20% of dataset: uses LEGIT_BUSINESS_PROFILES making $120k-$450k
     legitimate equipment/scanner/harvest/festival wires corroborated by UCC-1 liens,
     W-2 ADP payroll, IRS EFTPS taxes, and Square POS surges -> disposition: CLEAR_NO_SAR)

Generates BOTH:
  - Static FIU dossier audits (75%)
  - Multi-step FIU tool-calling trajectories (25%, calling `query_corporate_registry`,
    `check_commodity_benchmark`, `pull_utility_capacity` before filing final `<audit>` + JSON)

Enforces explicit arithmetic in `<audit>...</audit>`, verbatim `evidence_quotes` verified
via `quote_ok()` against the dossier/tool records, mandatory `innocent_alternative`, and
zero Prosecutor veto violations.
"""

from __future__ import annotations

import json
import random
from typing import Any

from training.common import (
    CASH_FRONT_ARCHETYPES,
    COMMODITY_BENCHMARKS,
    LEGIT_BUSINESS_PROFILES,
    OFFSHORE_JURISDICTIONS,
    SHELL_PREFIXES,
    SHELL_SUFFIXES,
    check_prosecutor_vetoes,
    make_rng,
    pick_distinct,
    quote_ok,
    random_address,
    sample_unique_names,
)

AML_TYPOLOGIES = (
    "SMURFING_FUNNEL",
    "TBML_INVOICE_AND_WEIGHT_MISMATCH",
    "LAYERED_SHELL_ROUND_TRIP",
    "CASH_FRONT_UTILITY_MISMATCH",
    "CRYPTO_PEEL_AND_OTC_SETTLEMENT",
    "ALL_CASH_REAL_ESTATE_NOMINEE",
    "CLEAN_FALSE_POSITIVE",
)

TOOLS_AML: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_corporate_registry",
            "description": "Retrieve incorporation timestamps, beneficial owners/nominees, W-2 headcount, registered agent suites, and MX/IP network metadata for entities in an FIU alert.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of corporate entity names to query.",
                    }
                },
                "required": ["entity_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_commodity_benchmark",
            "description": "Query customs spot unit prices ($/kg), ISO 40-ft container payload ceilings (27,500 kg max), and commercial equipment/lien registries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Invoice numbers, transaction IDs, or commodity descriptions to benchmark.",
                    }
                },
                "required": ["reference_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pull_utility_capacity",
            "description": "Pull municipal water/gas/kWh utility meters, wholesale supplier COGS, ADP/IRS EFTPS payroll filings, Square POS card ratios, and county deed/escrow records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entities to audit for physical throughput and operating corroboration.",
                    }
                },
                "required": ["entity_names"],
            },
        },
    },
]

SYSTEM_PROMPT_AML_STATIC = """You are a Financial Intelligence Unit (FIU) Money-Laundering & Shell-Network Investigator AI.
Work strictly from the documents in the case packet. Rules that never bend:
1. Compute explicit arithmetic in <audit>...</audit>: cash-to-card split %, pass-through velocity %, implied $/kg vs. market benchmark, declared kg vs. 27,500 kg physical container ceiling, or reported cash vs. utility-derived physical capacity ceiling.
2. Separate tainted laundering vehicles from legitimate businesses triggered by naive >$100k static rules when corroborated by UCC-1 liens, W-2 ADP payroll, IRS EFTPS taxes, or Square POS festival surges. If every entity is corroborated, set disposition to `CLEAR_NO_SAR`.
3. Ground every finding in exact verbatim substrings (`evidence_quotes`) from `KYC_REGISTRY`, `TX_LEDGER`, or `CORROBORATION_ANNEX`.
4. Judge the paper record, never declare personal criminal guilt, and include a commercial `innocent_alternative` note explaining what benign business scenario was considered and why the record supports or refutes it.

Respond with a step-by-step <audit>...</audit> trace followed by a single valid JSON FIU determination."""

SYSTEM_PROMPT_AML_TOOLS = """You are an Active Financial Intelligence Unit (FIU) Investigator AI with desk retrieval tools:
- `query_corporate_registry(entity_names)`
- `check_commodity_benchmark(reference_ids)`
- `pull_utility_capacity(entity_names)`

At Alert Intake you see only the flagged transaction ledger. Before issuing your final determination:
1. Call the investigative tools using `<think>...</think>` + `<tool_call>{"name": ..., "arguments": ...}</tool_call>` to pull corporate ownership/formation metadata, commodity/equipment benchmarks, and utility/payroll/deed corroboration.
2. Once records are retrieved, emit a quantitative `<audit>...</audit>` trace showing explicit math, verbatim `evidence_quotes` from `ALERT_LEDGER` and tool outputs, a neutral `innocent_alternative`, and the final JSON FIU determination."""

USER_PROMPTS_STATIC = (
    "Audit this FIU compliance case packet. Show explicit arithmetic in <audit>, cite verbatim quotes, clear corroborated businesses, and output your JSON SAR determination.",
    "Transaction Monitoring escalated the entity cluster below. Run velocity, unit-price/weight, utility-capacity, and corporate-link math in <audit>, then emit the structured JSON FIU report.",
    "Review the attached KYC snapshot, 30-day ledger, and trade/utility annex. Separate true laundering typologies from false positives with exact math and verbatim quotes.",
)

USER_PROMPTS_TOOL_OPEN = (
    "NEW FIU ALERT INTAKE: You have only the flagged 30-day ledger below. Query corporate registry, commodity/equipment benchmarks, and utility/operating capacity before filing your <audit> and JSON SAR decision.",
    "ACTIVE DESK AUDIT: Use `query_corporate_registry`, `check_commodity_benchmark`, and `pull_utility_capacity` to investigate the escalated transactions below, then emit `<audit>` + JSON.",
)


def _pick_typology(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.20:
        return "CLEAN_FALSE_POSITIVE"
    bucket = (roll - 0.20) / 0.80
    positive = AML_TYPOLOGIES[:-1]  # 6 laundering typologies evenly weighted (~13.33% each)
    idx = min(len(positive) - 1, int(bucket * len(positive)))
    return positive[idx]


def _build_case_components(rng: random.Random, typology: str, packet_id: str) -> dict[str, Any]:
    people = sample_unique_names(rng, 12)
    legit_picks = pick_distinct(rng, LEGIT_BUSINESS_PROFILES, 3)
    l1_name, l1_sec, l1_just = legit_picks[0]
    l2_name, l2_sec, l2_just = legit_picks[1]
    l3_name, l3_sec, l3_just = legit_picks[2]

    l1_wire = rng.randrange(125000, 445000, 5000)
    l2_wire = rng.randrange(120000, 380000, 5000)
    l2_payroll = rng.randrange(48000, 112000, 2000)
    l2_tax = int(round(l2_payroll * 0.28))

    sh_roots = pick_distinct(rng, SHELL_PREFIXES, 4)
    sh_sufs = [rng.choice(SHELL_SUFFIXES) for _ in range(4)]
    shell_a = f"{sh_roots[0]} {sh_sufs[0]}"
    shell_b = f"{sh_roots[1]} {sh_sufs[1]}"
    shell_c = f"{sh_roots[2]} {sh_sufs[2]}"

    j_picks = pick_distinct(rng, OFFSHORE_JURISDICTIONS, 3)
    shared_suite = f"Suite {rng.randint(210, 940)}, {random_address(rng)}, {j_picks[0][0]}"
    shared_ip = f"198.51.100.{rng.randint(12, 244)}/29"

    kyc_lines = [
        f"- {l1_name} ({l1_sec}) | Formed: 2015-04-18 | UBO: {people[0]} | W-2 Staff: {rng.randint(16, 42)} | Addr: {random_address(rng)}",
        f"- {l2_name} ({l2_sec}) | Formed: 2018-09-06 | UBO: {people[1]} | W-2 Staff: {rng.randint(11, 29)} | Addr: {random_address(rng)}",
    ]
    ledger_lines = [
        f"  [TX-101] {l1_name} -> Verified OEM / Commercial Escrow: WIRE OUT ${l1_wire:,} (Static alert: single wire >= $120,000).",
        f"  [TX-102] {l2_name} -> Supplier / Season Settlement WIRE OUT ${l2_wire:,}; ADP W-2 Payroll ACH OUT ${l2_payroll:,}; IRS EFTPS Tax ACH OUT ${l2_tax:,}.",
    ]
    commodity_lines = [
        f"  * Benchmark Check ({l1_name}, TX-101): Verified {l1_just} matching ${l1_wire:,} settlement within normal OEM price band.",
    ]
    utility_lines = [
        f"  * Operating & Tax Check ({l1_name}): Active W-2 ADP payroll, IRS EFTPS remittances, and Square POS card receipts align with commercial volume.",
        f"  * Operating & Tax Check ({l2_name}, TX-102): Verified {l2_just}; ADP payroll ${l2_payroll:,} and IRS EFTPS ${l2_tax:,} match historic 6-year baseline.",
    ]

    cleared_entities = [l1_name, l2_name]
    tainted_entities: list[str] = []
    laundered_usd = 0
    quant_metrics: dict[str, Any] = {}
    subpoenas: list[str] = []
    quotes_static: list[dict[str, str]] = []
    quotes_tool: list[dict[str, str]] = []
    ref_ids = ["TX-101", "TX-102"]

    # ------------------------------------------------------------------
    # Typology 1: SMURFING_FUNNEL (4-7 drops <$10k, <30d zero-payroll LLC, >96% 24h velocity)
    # ------------------------------------------------------------------
    if typology == "SMURFING_FUNNEL":
        n_drops = rng.randint(4, 7)
        drops = [rng.randrange(8750, 9950, 50) for _ in range(n_drops)]
        total_in = sum(drops)
        pct_vel = round(rng.uniform(96.4, 99.1), 1)
        wire_out = int(round(total_in * (pct_vel / 100.0)))
        realized_vel = round(wire_out / total_in * 100.0, 2)
        age_days = rng.randint(9, 26)

        tainted_entities = [shell_a, shell_b]
        laundered_usd = total_in
        kyc_q = f"{shell_a} (declared wholesale consulting) | Formed: {age_days} days ago | Nominee Manager: {people[2]} | W-2 Staff: 0"
        kyc_lines.extend([
            f"- {kyc_q} | Agent: {shared_suite}",
            f"- {shell_b} ({j_picks[1][1]}, {j_picks[1][0]}) | Director: {people[3]} | Foreign beneficiary desk",
        ])
        for i, amt in enumerate(drops, start=1):
            runner = people[3 + (i % 4)]
            ledger_lines.append(
                f"  [TX-20{i}] Branch #{i} Counter Cash Drop ({runner}) -> {shell_a}: CASH IN ${amt:,} (below $10,000 CTR threshold)."
            )
        led_q = f"[TX-299] {shell_a} -> {shell_b} ({j_picks[1][0]}): SAME-DAY WIRE OUT ${wire_out:,} within 19 hours of cash drops"
        ledger_lines.append(f"  {led_q}; $0 rent, $0 payroll, $0 IRS EFTPS tax.")
        commodity_lines.append(
            f"  * Invoice & Customs Check (TX-299): Zero customs entries, bills of lading, or UCC-1 commercial filings found for {shell_a}."
        )
        util_q = f"{n_drops} cash deposits across {n_drops} branches in 18 hours totaling ${total_in:,} swept out at {realized_vel}% 24h velocity"
        utility_lines.append(
            f"  * Branch Velocity & Utility Note ({shell_a}): {util_q}; 0 kWh commercial meter account."
        )
        ref_ids.append("TX-299")
        disposition = "FILE_SAR_ESCALATE"
        quant_metrics = {
            "structured_drop_count": n_drops,
            "total_cash_in_usd": total_in,
            "same_day_wire_out_usd": wire_out,
            "passthrough_velocity_pct": realized_vel,
            "entity_age_days": age_days,
        }
        inno = (
            f"Multi-store retail franchises occasionally make several sub-$10,000 branch deposits in one day, "
            f"but a genuine retailer exhibits POS card settlements, W-2 payroll, rent, and supplier COGS rather than "
            f"a {age_days}-day-old zero-payroll LLC sweeping {realized_vel}% offshore within 19 hours."
        )
        subpoenas = [
            f"FinCEN 314(b) notice and BOI beneficial-ownership subpoena on {shell_a} and {shell_b}",
            f"Pull teller surveillance video and currency-counter bill-strap logs for TX-201..TX-20{n_drops}",
        ]
        math_block = (
            f"- Smurfing & Funnel Math ({shell_a}): {n_drops} structured cash drops ({' + '.join('$'+format(x,',') for x in drops)} = ${total_in:,}), "
            f"every deposit held below the $10,000 CTR threshold (`max=${max(drops):,}`).\n"
            f"- 24-Hour Pass-Through Velocity: `${wire_out:,} / ${total_in:,} = {realized_vel}%` (>96% threshold) wired out within 19 hours by a "
            f"{age_days}-day-old LLC with 0 W-2 employees and $0 operating debits."
        )
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": util_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_UTILITY_CAPACITY", "quote": util_q},
        ]

    # ------------------------------------------------------------------
    # Typology 2: TBML_INVOICE_AND_WEIGHT_MISMATCH (12x-35x $/kg OR >27,500 kg container ceiling)
    # ------------------------------------------------------------------
    elif typology == "TBML_INVOICE_AND_WEIGHT_MISMATCH":
        comm_name, bench_price, unit, comm_max_kg = rng.choice(COMMODITY_BENCHMARKS)
        inv_id = f"INV-{rng.randint(4100, 9899)}"
        bol_id = f"BOL-{rng.randint(70000, 99999)}"
        over_weight_mode = rng.random() < 0.50

        tainted_entities = [shell_a, shell_b]
        kyc_q = f"{shell_a} (import-export desk) | Formed: 5 mos ago | UBO: {people[2]} | W-2 Staff: 1 | Agent: {shared_suite}"
        kyc_lines.extend([
            f"- {kyc_q}",
            f"- {shell_b} ({j_picks[2][1]}, {j_picks[2][0]}) | Director: {people[3]} | Shares {shared_ip} corporate mail server with {shell_a}",
        ])

        if not over_weight_mode:
            qty_kg = rng.randrange(5000, min(18000, comm_max_kg), 500)
            mult = rng.randint(12, 35)
            implied_unit = round(bench_price * mult, 2)
            invoice_usd = int(round(qty_kg * implied_unit))
            fair_usd = int(round(qty_kg * bench_price))
            laundered_usd = invoice_usd - fair_usd
            actual_ratio = round((invoice_usd / qty_kg) / bench_price, 2)

            led_q = f"[TX-301] {shell_a} -> {shell_b}: TRADE WIRE OUT ${invoice_usd:,} settling {inv_id} ({qty_kg:,} {unit} {comm_name}, single 40ft container)"
            ledger_lines.append(f"  {led_q}.")
            comm_q = f"Market spot benchmark for {comm_name} is ${bench_price:.2f}/{unit} (40ft container max {comm_max_kg:,} kg; ISO physical ceiling 27,500 kg)"
            commodity_lines.append(
                f"  * Customs & Spot Price Audit ({inv_id}): {comm_q}. Implied invoice unit price = ${implied_unit:.2f}/{unit} ({actual_ratio}x spot)."
            )
            utility_lines.append(
                f"  * Warehouse & Logistics Check ({shell_a}): No cold/bulk warehouse lease or domestic trucking bills on file."
            )
            quant_metrics = {
                "tbml_mode": "unit_price_over_invoicing",
                "quantity_kg": qty_kg,
                "benchmark_usd_per_kg": bench_price,
                "implied_usd_per_kg": implied_unit,
                "price_multiplier_x": actual_ratio,
                "excess_value_transfer_usd": laundered_usd,
            }
            math_block = (
                f"- TBML Over-Invoicing Math ({inv_id}, TX-301): `${invoice_usd:,} / {qty_kg:,} kg = ${implied_unit:.2f}/kg` vs. "
                f"spot benchmark `${bench_price:.2f}/kg` -> `{actual_ratio}x` market price (within 12x-35x TBML anomaly band).\n"
                f"- Illicit Value Transfer: Fair shipment value `${qty_kg:,} kg * ${bench_price:.2f}/kg = ${fair_usd:,}`; "
                f"excess cross-border transfer `${invoice_usd:,} - ${fair_usd:,} = ${laundered_usd:,}`."
            )
            inno = (
                f"Custom medical-grade or patented specialty formulations can command premiums over bulk spot prices, "
                f"but {inv_id} declares standard `{comm_name}` between two entities sharing `{shared_ip}` with zero warehouse footprint."
            )
        else:
            # Physical container weight impossibility (> 27,500 kg physical 40ft ceiling) + phantom tonnage value transfer
            declared_kg = rng.randrange(39000, 58000, 1000)
            unit_billed = round(bench_price * rng.uniform(3.5, 6.5), 2)
            invoice_usd = int(round(declared_kg * unit_billed))
            max_legal_usd = int(round(comm_max_kg * bench_price))
            laundered_usd = invoice_usd - max_legal_usd
            overweight_ratio = round(declared_kg / 27500.0, 2)

            led_q = f"[TX-301] {shell_a} -> {shell_b}: TRADE WIRE OUT ${invoice_usd:,} settling {inv_id} / {bol_id} ({declared_kg:,} {unit} {comm_name} in ONE 40ft container)"
            ledger_lines.append(f"  {led_q}.")
            comm_q = f"Physical 40ft ISO container payload ceiling is 27,500 kg (commodity stowage cap {comm_max_kg:,} kg; spot ${bench_price:.2f}/{unit})"
            commodity_lines.append(
                f"  * Customs & Container Physics Audit ({inv_id} / {bol_id}): {comm_q}. Declared single-container load of {declared_kg:,} kg exceeds physical ceiling by {declared_kg - 27500:,} kg ({overweight_ratio}x max)."
            )
            utility_lines.append(
                f"  * Port Drayage & Warehouse Check ({shell_a}): Zero port drayage weigh-tickets or warehouse leases on file."
            )
            quant_metrics = {
                "tbml_mode": "container_weight_ceiling_impossibility",
                "declared_single_container_kg": declared_kg,
                "iso_container_ceiling_kg": 27500,
                "excess_phantom_kg": declared_kg - 27500,
                "benchmark_usd_per_kg": bench_price,
                "excess_value_transfer_usd": laundered_usd,
            }
            math_block = (
                f"- TBML Container Physics & Pricing Math ({inv_id} / {bol_id}): Declared `{declared_kg:,} kg` inside ONE 40ft container exceeds "
                f"the `27,500 kg` physical ISO container payload ceiling by `{declared_kg - 27500:,} kg` (`{overweight_ratio}x` ceiling; commodity stowage cap `{comm_max_kg:,} kg`).\n"
                f"- Phantom-Tonnage Value Transfer: Even a full legal container at `${bench_price:.2f}/kg` is worth `${comm_max_kg:,} * ${bench_price:.2f} = ${max_legal_usd:,}`; "
                f"wire of `${invoice_usd:,}` (`${unit_billed:.2f}/kg`) transfers `${invoice_usd:,} - ${max_legal_usd:,} = ${laundered_usd:,}` in excess value."
            )
            inno = (
                f"Clerical typo merging two container bills onto one invoice line (e.g., 2 x 20ft/40ft boxes) is possible, "
                f"but simultaneous unit-price markup (`${unit_billed:.2f}/kg` vs `${bench_price:.2f}/kg`), zero port drayage tickets, and shared `{shared_ip}` refute benign clerical error."
            )

        ref_ids.append(inv_id)
        disposition = "FILE_SAR_ESCALATE"
        subpoenas = [
            f"CBP Form 7501 entry packet, carrier master Bill of Lading ({bol_id}), and port crane scale logs for {inv_id}",
            f"SWIFT MT103/202 correspondent wire records and BOI registry pull on {shell_a} and {shell_b}",
        ]
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": comm_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_COMMODITY_BENCHMARK", "quote": comm_q},
        ]

    # ------------------------------------------------------------------
    # Typology 3: LAYERED_SHELL_ROUND_TRIP (3-hop offshore loop formed in 24-48h)
    # ------------------------------------------------------------------
    elif typology == "LAYERED_SHELL_ROUND_TRIP":
        formation_span_hrs = rng.randint(25, 46)
        hop1 = rng.randrange(260000, 680000, 10000)
        hop2 = int(round(hop1 * 0.975))
        hop3 = int(round(hop1 * 0.955))
        retention_pct = round(hop3 / hop1 * 100.0, 2)

        tainted_entities = [shell_a, shell_b, shell_c]
        laundered_usd = hop1
        kyc_q = (
            f"{shell_a} ({j_picks[0][1]}), {shell_b} ({j_picks[1][1]}), and {shell_c} ({j_picks[2][1]}) "
            f"incorporated within {formation_span_hrs} hours; share agent {shared_suite} and IP block {shared_ip}"
        )
        kyc_lines.extend([
            f"- {shell_a} ({j_picks[0][1]}) | Controller: {people[2]} | W-2 Staff: 0 | Agent: {shared_suite}",
            f"- {shell_b} ({j_picks[1][1]}) | Nominee: {people[3]} | W-2 Staff: 0 | MX/IP: {shared_ip}",
            f"- {shell_c} ({j_picks[2][1]}) | UBO: {people[2]} | W-2 Staff: 0 | Linkage: {kyc_q}",
        ])
        led_q = f"[TX-403] {shell_b} -> {shell_c}: WIRE IN ${hop3:,} ('long-term shareholder loan') +34h completing circular round-trip"
        ledger_lines.extend([
            f"  [TX-401] Unverified Bulk FX Desk -> {shell_a}: WIRE IN ${hop1:,} ('advisory retainer').",
            f"  [TX-402] {shell_a} -> {shell_b} ({j_picks[1][0]}): WIRE OUT ${hop2:,} ('enterprise IP licensing fee') +16h.",
            f"  {led_q}.",
        ])
        comm_q = f"Zero USPTO/WIPO registered software patents, trademarks, or licensing contracts exist for {shell_a} or {shell_b}"
        commodity_lines.append(f"  * IP & Commercial Registry Check (TX-402): {comm_q}.")
        utility_lines.append(
            f"  * Tax & Payroll Check ({shell_a}, {shell_b}, {shell_c}): Zero W-2 employees, zero IRS EFTPS filings, zero commercial office utility meters."
        )
        ref_ids.append("TX-402")
        disposition = "FILE_SAR_ESCALATE"
        quant_metrics = {
            "formation_burst_hours": formation_span_hrs,
            "hop1_in_usd": hop1,
            "hop2_offshore_usd": hop2,
            "hop3_return_loan_usd": hop3,
            "round_trip_retention_pct": retention_pct,
        }
        math_block = (
            f"- 3-Hop Shell Round-Trip Math: `${hop1:,}` enters `{shell_a}` (TX-401) -> `${hop2:,}` (`{round(hop2/hop1*100,1)}%`) hops to `{shell_b}` "
            f"as 'IP licensing' (+16h, TX-402) -> `${hop3:,}` (`{retention_pct}%` net retained, fee drag `${hop1 - hop3:,}`) returns to `{shell_c}` "
            f"as a 'shareholder loan' (+34h, TX-403).\n"
            f"- Coordinated Shell Formation: All 3 zero-employee entities formed within `{formation_span_hrs} hours` (24-48h burst window) sharing `{shared_suite}`, IP `{shared_ip}`, and UBO `{people[2]}`."
        )
        inno = (
            f"Multinational startups sometimes form Delaware/offshore holding structures for IP tax planning and intercompany loans, "
            f"but legitimate restructurings involve pre-existing IP filings, operating payroll, and legal opinion letters rather than a "
            f"{formation_span_hrs}-hour shell burst cycling {retention_pct}% of unverified funds in 34 hours."
        )
        subpoenas = [
            f"Corporate Transparency BOI & registered-agent KYC intake files at {shared_suite} for {shell_a} and {shell_c}",
            f"USD correspondent clearing messages (MT103/MT202 COV) for offshore hop {shell_b} (TX-402, TX-403)",
        ]
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": comm_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_COMMODITY_BENCHMARK", "quote": comm_q},
        ]

    # ------------------------------------------------------------------
    # Typology 4: CASH_FRONT_UTILITY_MISMATCH (85-94% cash, 6x-15x above physical ceiling)
    # ------------------------------------------------------------------
    elif typology == "CASH_FRONT_UTILITY_MISMATCH":
        front_name, front_kind, max_cap, util_proof = rng.choice(CASH_FRONT_ARCHETYPES)
        cap_mult = round(rng.uniform(6.4, 14.4), 2)
        reported_cash = int(round((max_cap * cap_mult) / 100.0) * 100)
        target_cash_share = rng.uniform(0.86, 0.935)
        card_in = int(round(reported_cash * (1.0 - target_cash_share) / target_cash_share / 50.0) * 50)
        real_cash_pct = round(reported_cash / (reported_cash + card_in) * 100.0, 1)
        real_mult = round(reported_cash / max_cap, 2)
        sweep_out = int(round(reported_cash * 0.89))

        tainted_entities = [front_name, shell_a]
        laundered_usd = reported_cash - max_cap
        kyc_q = f"{front_name} ({front_kind}) | UBO: {people[2]} | Upstream Payee: {shell_a} (0 W-2 staff at {shared_suite})"
        kyc_lines.extend([
            f"- {kyc_q}",
            f"- {shell_a} ('management & linen leasing') | Manager: {people[3]} | W-2 Staff: 0 | Addr: {shared_suite}",
        ])
        led_q = f"[TX-501] {front_name}: Night-Drop CASH IN ${reported_cash:,} vs. Card POS IN ${card_in:,} ({real_cash_pct}% cash); [TX-502] WIRE OUT ${sweep_out:,} to {shell_a}"
        ledger_lines.append(f"  {led_q}.")
        commodity_lines.append(
            f"  * Sector Payment Mix Benchmark ({front_kind}): Regional peer average is 76% card / 24% cash; zero equipment liens filed by {shell_a}."
        )
        util_q = f"Physical Capacity Audit ({front_name}): {util_proof}"
        utility_lines.append(f"  * {util_q}.")
        ref_ids.append("TX-501")
        disposition = "FILE_SAR_ESCALATE"
        quant_metrics = {
            "reported_cash_usd": reported_cash,
            "card_pos_usd": card_in,
            "cash_share_pct": real_cash_pct,
            "utility_physical_ceiling_usd": max_cap,
            "ceiling_multiplier_x": real_mult,
            "excess_comingled_cash_usd": laundered_usd,
        }
        math_block = (
            f"- Cash-to-Card Mix Math ({front_name}): `${reported_cash:,} / (${reported_cash:,} + ${card_in:,}) = {real_cash_pct}%` cash "
            f"(85-94% cash-front band vs. ~24% sector cash norm).\n"
            f"- Utility Physical Ceiling Math: Reported cash `${reported_cash:,} / ${max_cap:,} ceiling = {real_mult}x` physical capacity "
            f"(6x-15x anomaly band; {util_proof}), proving at least `${reported_cash:,} - ${max_cap:,} = ${laundered_usd:,}/mo` in illicit cash co-mingling swept to `{shell_a}`."
        )
        inno = (
            f"A broken credit-card terminal or neighborhood block party could temporarily lift cash share for a few days, "
            f"but it cannot physically generate `{real_mult}x` more car washes/loads/stalls/sales than municipal water, gas, stall count, or wholesale COGS allow."
        )
        subpoenas = [
            f" Certified municipal utility meter logs, wholesale distributor invoices, and POS Z-tapes for {front_name}",
            f"Beneficial ownership & bank signatory subpoena for upstream recipient {shell_a} (TX-502)",
        ]
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": util_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_UTILITY_CAPACITY", "quote": util_q},
        ]

    # ------------------------------------------------------------------
    # Typology 5: CRYPTO_PEEL_AND_OTC_SETTLEMENT (6 retail mules -> zero-tax shell -> OTC desk)
    # ------------------------------------------------------------------
    elif typology == "CRYPTO_PEEL_AND_OTC_SETTLEMENT":
        mule_amts = [rng.randrange(14500, 29500, 500) for _ in range(6)]
        total_fan_in = sum(mule_amts)
        otc_wire = int(round(total_fan_in * 0.978))
        sweep_pct = round(otc_wire / total_fan_in * 100.0, 2)
        otc_name = f"{sh_roots[3]} Digital OTC Settlement Ltd."

        tainted_entities = [shell_a, otc_name]
        laundered_usd = total_fan_in
        kyc_q = f"{shell_a} ('digital marketing LLC') | Formed: 22 days ago | UBO: {people[2]} | W-2 Staff: 0 | IRS EFTPS Filings: $0"
        kyc_lines.extend([
            f"- {kyc_q} | Agent: {shared_suite}",
            f"- {otc_name} ({j_picks[2][0]} high-risk USDT/stablecoin OTC desk) | Unhosted TRON peel-chain settlement cluster",
        ])
        for m_i, m_amt in enumerate(mule_amts, start=1):
            ledger_lines.append(
                f"  [TX-60{m_i}] Unrelated Retail Mule #{m_i} ({people[3 + m_i]}) -> {shell_a}: ZELLE/SAME-DAY ACH IN ${m_amt:,}."
            )
        led_q = f"[TX-609] {shell_a} -> {otc_name}: FEDWIRE OUT ${otc_wire:,} ('USDT OTC liquidity block') within 9 hours of 6-account mule fan-in"
        ledger_lines.append(f"  {led_q}.")
        comm_q = f"Blockchain & OTC Risk Note ({otc_name}): Counterparty settles into high-risk peel-chain wallets splitting 2-5% hops across unhosted addresses"
        commodity_lines.append(f"  * {comm_q}.")
        utility_lines.append(
            f"  * Tax & Merchant Audit ({shell_a}): $0 card processing, $0 IRS EFTPS payroll/tax, 6 retail P2P/ACH senders share zero geographic or employer overlap."
        )
        ref_ids.append("TX-609")
        disposition = "FILE_SAR_ESCALATE"
        quant_metrics = {
            "retail_mule_count": 6,
            "total_p2p_ach_fan_in_usd": total_fan_in,
            "otc_stablecoin_wire_usd": otc_wire,
            "sweep_velocity_pct": sweep_pct,
        }
        math_block = (
            f"- 6-Mule Fan-In Math ({shell_a}): 6 unrelated retail Zelle/ACH inflows (`{' + '.join('$'+format(x,',') for x in mule_amts)} = ${total_fan_in:,}`).\n"
            f"- Rapid OTC Conversion Sweep: `${otc_wire:,} / ${total_fan_in:,} = {sweep_pct}%` wired within 9 hours to high-risk stablecoin desk `{otc_name}` "
            f"with `$0` IRS EFTPS taxes and `0` W-2 staff."
        )
        inno = (
            f"Licensed e-commerce aggregators or crowdfunding platforms receive many retail ACH inflows before treasury sweeps, "
            f"but operate with merchant card processors, customer refund flows, and tax filings rather than a 22-day-old zero-tax LLC wiring {sweep_pct}% to a peel-chain OTC desk."
        )
        subpoenas = [
            f"FinCEN 314(b) requests to originating retail banks for Mule #1..#6 (TX-601..TX-606) login IP/device fingerprints",
            f"VASP KYC, wallet deposit addresses, and TRON/EVM transaction hashes from {otc_name} for TX-609",
        ]
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": comm_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_COMMODITY_BENCHMARK", "quote": comm_q},
        ]

    # ------------------------------------------------------------------
    # Typology 6: ALL_CASH_REAL_ESTATE_NOMINEE (anonymous series LLC + split foreign 3rd-party wires + immediate loan-back)
    # ------------------------------------------------------------------
    elif typology == "ALL_CASH_REAL_ESTATE_NOMINEE":
        series_name = f"{sh_roots[0]} Series-7 Property LLC"
        w1 = rng.randrange(195000, 310000, 5000)
        w2 = rng.randrange(185000, 295000, 5000)
        w3 = rng.randrange(175000, 275000, 5000)
        purchase_usd = w1 + w2 + w3
        refi_loan_usd = int(round(purchase_usd * 0.86))
        refi_pct = round(refi_loan_usd / purchase_usd * 100.0, 1)
        prop_addr = random_address(rng)

        tainted_entities = [series_name, shell_b, shell_c]
        laundered_usd = purchase_usd
        kyc_q = f"{series_name} (Wyoming anonymous series LLC) | Formed: 11 days before closing | Nominee Organizer: {people[2]} | W-2 Staff: 0"
        kyc_lines.extend([
            f"- {kyc_q} | Agent: {shared_suite}",
            f"- {shell_b} ({j_picks[1][0]} third-party remitter #1) & {shell_c} ({j_picks[2][0]} third-party remitter #2) | Unrelated foreign trade shells",
        ])
        led_q = (
            f"[TX-701..703] Split Third-Party Foreign Wires (${w1:,} + ${w2:,} + ${w3:,} = ${purchase_usd:,}) -> Title Escrow for {series_name} "
            f"all-cash purchase of {prop_addr}; [TX-704] +14 days private-lender cash-out refinance / flip loan-back WIRE OUT ${refi_loan_usd:,}"
        )
        ledger_lines.append(f"  {led_q}.")
        commodity_lines.append(
            f"  * Commercial Appraisal & Lien Check ({prop_addr}): No bank mortgage at acquisition; zero construction permits pulled prior to +14d cash-out extraction."
        )
        util_q = f"County Deed & Tenant Audit ({prop_addr}): Distressed vacant warehouse (0 active tenants, minimal standby electric meter); {refi_pct}% equity extracted in 14 days"
        utility_lines.append(f"  * {util_q}.")
        ref_ids.append("TX-701..703")
        disposition = "FILE_SAR_ESCALATE"
        quant_metrics = {
            "split_foreign_wires_usd": [w1, w2, w3],
            "all_cash_purchase_usd": purchase_usd,
            "cashout_loan_back_usd": refi_loan_usd,
            "extracted_equity_pct": refi_pct,
            "holding_period_days": 14,
        }
        math_block = (
            f"- Split Foreign Third-Party Acquisition Math ({series_name}): `${w1:,} + ${w2:,} + ${w3:,} = ${purchase_usd:,}` wired directly into title escrow "
            f"by unrelated offshore third parties (`{shell_b}`, `{shell_c}`) for an 11-day-old anonymous series LLC.\n"
            f"- Rapid Integration / Loan-Back Extraction: Within `14 days` of closing on vacant warehouse `{prop_addr}`, `{series_name}` extracted "
            f"`${refi_loan_usd:,} / ${purchase_usd:,} = {refi_pct}%` clean Layer-3 proceeds via cash-out refinance / loan-back with zero renovations."
        )
        inno = (
            f"Real-estate syndications frequently pool investor wires into a newly formed special-purpose LLC and refinance after value-add rehab, "
            f"but legitimate syndications wire from KYC'd LP subscription accounts rather than unrelated foreign trade shells followed by a 14-day zero-rehab cash-out."
        )
        subpoenas = [
            f"FinCEN Residential/Commercial Real Estate Rule closing file, ALTA settlement statement, and BOI disclosure on {series_name}",
            f"SWIFT originator records on foreign third-party wires from {shell_b} and {shell_c} plus lender underwriting file on TX-704",
        ]
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": util_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_UTILITY_CAPACITY", "quote": util_q},
        ]

    # ------------------------------------------------------------------
    # Typology 7: CLEAN_FALSE_POSITIVE (20% of dataset -> CLEAR_NO_SAR)
    # ------------------------------------------------------------------
    else:
        l3_wire = rng.randrange(135000, 435000, 5000)
        l3_pos_card = rng.randrange(190000, 510000, 5000)
        l3_payroll = rng.randrange(54000, 138000, 2000)
        l3_tax = int(round(l3_payroll * 0.27))
        payroll_ratio = round(l3_payroll / l3_pos_card * 100.0, 1)

        cleared_entities = [l1_name, l2_name, l3_name]
        tainted_entities = []
        laundered_usd = 0

        kyc_q = f"{l3_name} ({l3_sec}) | Formed: 2014-06-11 | UBO: {people[2]} | W-2 Staff: {rng.randint(18, 44)}"
        kyc_lines.append(f"- {kyc_q} | Addr: {random_address(rng)}")
        led_q = (
            f"[TX-103] {l3_name} -> Verified Vendor / Equipment Escrow WIRE OUT ${l3_wire:,}; "
            f"Square POS Card Settlement IN ${l3_pos_card:,}; ADP W-2 Payroll ACH OUT ${l3_payroll:,}; IRS EFTPS Tax ACH OUT ${l3_tax:,}"
        )
        ledger_lines.append(f"  {led_q}.")
        comm_q = f"Benchmark Check ({l3_name}, TX-103): Verified {l3_just} corroborating ${l3_wire:,} wire with UCC-1 / commercial contract on file"
        commodity_lines.append(f"  * {comm_q}.")
        util_q = f"Operating & Utility Check ({l3_name}): Industrial/commercial utility meter, Square POS surge (${l3_pos_card:,}), ADP payroll (${l3_payroll:,}), and IRS EFTPS (${l3_tax:,}) fully match"
        utility_lines.append(f"  * {util_q}.")
        ref_ids.append("TX-103")
        disposition = "CLEAR_NO_SAR"
        quant_metrics = {
            "evaluated_large_wires_usd": [l1_wire, l2_wire, l3_wire],
            "total_corroborated_wire_volume_usd": l1_wire + l2_wire + l3_wire,
            "l3_payroll_to_pos_pct": payroll_ratio,
            "illicit_volume_usd": 0,
        }
        math_block = (
            f"- High-Dollar Alert Verification: Three static `>=$120k` alerts totaling `${l1_wire:,} + ${l2_wire:,} + ${l3_wire:,} = ${l1_wire + l2_wire + l3_wire:,}`.\n"
            f"- Operating Ratio Math (`{l3_name}`): Square POS card inflows `${l3_pos_card:,}`, ADP W-2 payroll `${l3_payroll:,}` (`{payroll_ratio}%` of card revenue), "
            f"and IRS EFTPS tax remittance `${l3_tax:,}` (`{round(l3_tax/l3_payroll*100,1)}%` withholding) align with `{l3_just}`. "
            f"`{l1_name}` (`${l1_wire:,}`) and `{l2_name}` (`${l2_wire:,}`) are identically backed by UCC-1/OEM invoices and W-2 payroll -> `$0` illicit volume (`CLEAR_NO_SAR`)."
        )
        inno = (
            f"All flagged `$120k-$450k` disbursements represent ordinary capital equipment, scanner, harvest, or festival settlements "
            f"corroborated by UCC-1 liens, W-2 ADP payroll, IRS EFTPS tax payments, and Square POS card surges; filing a defensive SAR is unwarranted."
        )
        subpoenas = []
        quotes_static = [
            {"doc_id": "KYC_REGISTRY", "quote": kyc_q},
            {"doc_id": "TX_LEDGER", "quote": led_q},
            {"doc_id": "CORROBORATION_ANNEX", "quote": comm_q},
        ]
        quotes_tool = [
            {"doc_id": "ALERT_LEDGER", "quote": led_q},
            {"doc_id": "TOOL_CORPORATE_REGISTRY", "quote": kyc_q},
            {"doc_id": "TOOL_COMMODITY_BENCHMARK", "quote": comm_q},
        ]

    rng.shuffle(kyc_lines)
    rng.shuffle(ledger_lines)
    annex_combined = commodity_lines + utility_lines
    rng.shuffle(annex_combined)

    all_entity_names = sorted(set(cleared_entities + tainted_entities))

    return {
        "packet_id": packet_id,
        "disposition": disposition,
        "typology": typology,
        "tainted_entities": sorted(tainted_entities),
        "cleared_entities": sorted(cleared_entities),
        "all_entity_names": all_entity_names,
        "ref_ids": ref_ids,
        "laundered_usd": laundered_usd,
        "quant_metrics": quant_metrics,
        "innocent_alternative": inno,
        "subpoenas": subpoenas,
        "math_block": math_block,
        "l1_name": l1_name,
        "l1_wire": l1_wire,
        "l2_name": l2_name,
        "l2_wire": l2_wire,
        "kyc_text": "\n".join(kyc_lines),
        "ledger_text": "\n".join(ledger_lines),
        "annex_text": "\n".join(annex_combined),
        "commodity_text": "\n".join(commodity_lines),
        "utility_text": "\n".join(utility_lines),
        "quotes_static": quotes_static,
        "quotes_tool": quotes_tool,
    }


def _validate_aml_output(
    fiu_report: dict[str, Any],
    assistant_text: str,
    docs_by_id: dict[str, dict[str, str]],
) -> None:
    assert "<audit>" in assistant_text and "</audit>" in assistant_text
    quotes = fiu_report["evidence_quotes"]
    assert len(quotes) >= 3, "Expected >=3 verbatim evidence_quotes in AML determination"
    for q in quotes:
        assert quote_ok(q["quote"], q["doc_id"], docs_by_id), (
            f"AML quote failed quote_ok on {q['doc_id']}: {q['quote']!r}"
        )
    assert fiu_report.get("innocent_alternative") and len(fiu_report["innocent_alternative"]) >= 25
    veto_hits = check_prosecutor_vetoes(assistant_text, [])
    assert not veto_hits, f"Prosecutor veto violation in AML output: {veto_hits}"


def generate_aml_hunter_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Generate one deterministic static (75%) or multi-step tool-calling (25%) FIU AML example."""
    rng = make_rng(split, "aml_laundering_hunter", index, salt)

    packet_id = f"FIU-{rng.randint(2024, 2026)}-{rng.randint(100000, 999999)}"
    typology = _pick_typology(rng)
    is_tool_mode = rng.random() < 0.25

    case = _build_case_components(rng, typology, packet_id)

    quotes_used = case["quotes_tool"] if is_tool_mode else case["quotes_static"]
    fiu_report = {
        "packet_id": packet_id,
        "disposition": case["disposition"],
        "detected_typology": typology,
        "tainted_entities": case["tainted_entities"],
        "cleared_false_positive_entities": case["cleared_entities"],
        "estimated_illicit_volume_usd": case["laundered_usd"],
        "quantitative_metrics": case["quant_metrics"],
        "evidence_quotes": quotes_used,
        "innocent_alternative": case["innocent_alternative"],
        "recommended_subpoenas_and_actions": case["subpoenas"],
    }

    audit_trace = (
        f"<audit>\n"
        f"1. Legitimate Commercial Baseline Check: `{case['l1_name']}` (`${case['l1_wire']:,}`) and `{case['l2_name']}` (`${case['l2_wire']:,}`) "
        f"are corroborated by W-2 ADP payroll, IRS EFTPS tax remittances, UCC-1/OEM contracts, and POS card flows -> CLEARED as false positives.\n"
        f"2. Typology & Quantitative Proof (`{typology}`):\n"
        f"{case['math_block']}\n"
        f"3. Commercial Alternative Evaluated (`innocent_alternative`): {case['innocent_alternative']}\n"
        f"4. Disposition: `{case['disposition']}` (estimated illicit volume = `${case['laundered_usd']:,}`).\n"
        f"</audit>"
    )
    final_assistant_text = f"{audit_trace}\n```json\n{json.dumps(fiu_report, indent=2)}\n```"

    if not is_tool_mode:
        docs_static = {
            "KYC_REGISTRY": {"id": "KYC_REGISTRY", "text": case["kyc_text"]},
            "TX_LEDGER": {"id": "TX_LEDGER", "text": case["ledger_text"]},
            "CORROBORATION_ANNEX": {"id": "CORROBORATION_ANNEX", "text": case["annex_text"]},
        }
        _validate_aml_output(fiu_report, final_assistant_text, docs_static)

        dossier = (
            f"=== FIU CASE PACKET: {packet_id} ===\n\n"
            f"=== KYC_REGISTRY ===\n{case['kyc_text']}\n\n"
            f"=== TX_LEDGER ===\n{case['ledger_text']}\n\n"
            f"=== CORROBORATION_ANNEX ===\n{case['annex_text']}"
        )
        user_prompt = f"{rng.choice(USER_PROMPTS_STATIC)}\n\n{dossier}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_AML_STATIC},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": final_assistant_text},
        ]
        tools_called: list[str] = []
    else:
        docs_tool = {
            "ALERT_LEDGER": {"id": "ALERT_LEDGER", "text": case["ledger_text"]},
            "TOOL_CORPORATE_REGISTRY": {"id": "TOOL_CORPORATE_REGISTRY", "text": case["kyc_text"]},
            "TOOL_COMMODITY_BENCHMARK": {"id": "TOOL_COMMODITY_BENCHMARK", "text": case["commodity_text"]},
            "TOOL_UTILITY_CAPACITY": {"id": "TOOL_UTILITY_CAPACITY", "text": case["utility_text"]},
        }
        _validate_aml_output(fiu_report, final_assistant_text, docs_tool)

        user_open = (
            f"{rng.choice(USER_PROMPTS_TOOL_OPEN)}\n\n"
            f"=== FIU ALERT: {packet_id} ===\n"
            f"Entities Mentioned: {', '.join(case['all_entity_names'])}\n\n"
            f"=== ALERT_LEDGER ===\n{case['ledger_text']}"
        )

        # Step 1: query_corporate_registry
        call_1 = {"name": "query_corporate_registry", "arguments": {"entity_names": case["all_entity_names"]}}
        asst_1 = (
            f"<think>We only have the raw 30-day `ALERT_LEDGER` for {packet_id}. First, pull corporate incorporation dates, "
            f"W-2 headcount, registered agent suites, and IP/UBO links across all {len(case['all_entity_names'])} entities.</think>\n"
            f"<tool_call>\n{json.dumps(call_1)}\n</tool_call>"
        )
        obs_1 = f"=== TOOL_CORPORATE_REGISTRY ===\n{case['kyc_text']}"

        # Step 2: check_commodity_benchmark
        call_2 = {"name": "check_commodity_benchmark", "arguments": {"reference_ids": case["ref_ids"]}}
        asst_2 = (
            f"<think>Corporate registry returned entity ages, W-2 headcounts, and shared agent/IP metadata. "
            f"Next, check customs unit-price/weight benchmarks and commercial UCC-1/OEM filings on {', '.join(case['ref_ids'])}.</think>\n"
            f"<tool_call>\n{json.dumps(call_2)}\n</tool_call>"
        )
        obs_2 = f"=== TOOL_COMMODITY_BENCHMARK ===\n{case['commodity_text']}"

        # Step 3: pull_utility_capacity
        call_3 = {"name": "pull_utility_capacity", "arguments": {"entity_names": case["all_entity_names"]}}
        asst_3 = (
            f"<think>Now pull municipal water/gas/electric capacity meters, ADP/IRS EFTPS payroll tax confirmations, "
            f"Square POS card ratios, and county deed records to verify physical throughput and clear legitimate firms.</think>\n"
            f"<tool_call>\n{json.dumps(call_3)}\n</tool_call>"
        )
        obs_3 = f"=== TOOL_UTILITY_CAPACITY ===\n{case['utility_text']}"

        for t_msg in (asst_1, asst_2, asst_3):
            assert not check_prosecutor_vetoes(t_msg, [])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_AML_TOOLS},
            {"role": "user", "content": user_open},
            {"role": "assistant", "content": asst_1},
            {"role": "tool", "name": "query_corporate_registry", "content": obs_1},
            {"role": "assistant", "content": asst_2},
            {"role": "tool", "name": "check_commodity_benchmark", "content": obs_2},
            {"role": "assistant", "content": asst_3},
            {"role": "tool", "name": "pull_utility_capacity", "content": obs_3},
            {"role": "assistant", "content": final_assistant_text},
        ]
        tools_called = [
            "query_corporate_registry",
            "check_commodity_benchmark",
            "pull_utility_capacity",
        ]

    return {
        "id": f"aml_hunter_{split}_{index:07d}",
        "track": "track1_now",
        "domain": "aml_laundering_hunter",
        "subtask": typology,
        "split": split,
        "tools": TOOLS_AML if is_tool_mode else [],
        "messages": messages,
        "ground_truth": {
            "packet_id": packet_id,
            "disposition": case["disposition"],
            "detected_typology": typology,
            "interaction_mode": "multi_step_tool_trajectory" if is_tool_mode else "static_dossier",
            "tools_called": tools_called,
            "tainted_entities": case["tainted_entities"],
            "cleared_entities": case["cleared_entities"],
            "estimated_illicit_volume_usd": case["laundered_usd"],
            "quantitative_metrics": case["quant_metrics"],
            "evidence_quotes": quotes_used,
            "quote_check_drops": 0,
        },
    }
