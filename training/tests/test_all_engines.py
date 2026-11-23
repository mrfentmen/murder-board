#!/usr/bin/env python3
"""Comprehensive end-to-end unit test suite across all SPEC 7 training engines.

Verifies:
  1. All 6 SPEC 7 procedural simulators:
     - `murder_board_sim` (all 11 chairs, actionable + holdout modes, playable case export)
     - `noisy_vault_retrieval` (80-120 doc vault, 4-6 tool hops, almanac + entity graph, archival hold)
     - `forensic_micro_skills` (all 8 micro-skill drills)
     - `dispatch_911_sim` (single-turn + multi-turn escalation, <= 18 words, coerced caller safety)
     - `aml_hunter_sim` (all 7 typologies including 20% CLEAR_NO_SAR, static + multi-step tool trajectories)
     - `interrogation_room_sim` (Mode A homicide, Mode B 911 bodycam, Mode C AML customs, Othello Law)
  2. Real-archive shards (`training/datasets/real_v1/`) via `verify_corpus_directory` and domain breakdown
  3. `chunked_10gb_adapters` (all 9 external format converters + 10 GB `BatchBudgetGuard` & checkpoint resume)
  4. `rlvr_rewards` (`compute_investigator_reward` >= 0.95 on live generated gold rows across all 6 simulators
     and `-1.0` Othello-Error cliff on innocent anxious / trauma subject violation)
  5. `normalize_to_strict_qlora_chatml` and `verify_strict_qlora_folder` from `training/export_qlora_folders.py`
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from training.common import STANDING_BRIEF_CLOSER, check_prosecutor_vetoes, quote_ok, recompute_score
from training.export_qlora_folders import normalize_to_strict_qlora_chatml, verify_strict_qlora_folder
from training.external_adapters.chunked_10gb_adapters import (
    ADAPTER_REGISTRY,
    BatchBudgetGuard,
    run_self_test as run_adapters_self_test,
)
from training.rlvr_rewards import (
    compute_investigator_reward,
    openrlhf_reward_func,
    run_self_test as run_rlvr_self_test,
    trl_grpo_reward_fn,
    verl_compute_score,
)
from training.track1_now.aml_hunter_sim import AML_TYPOLOGIES, generate_aml_hunter_example
from training.track1_now.dispatch_911_sim import SUB_ARCHETYPE_CATALOG, generate_dispatch_911_example
from training.track1_now.forensic_micro_skills import (
    MICRO_SKILL_TYPES,
    generate_micro_skill_example,
    validate_micro_skill_example,
)
from training.track1_now.murder_board_sim import (
    MB_STEPS,
    export_playable_cases,
    generate_murder_board_case_bundle,
    generate_murder_board_example,
)
from training.track1_now.noisy_vault_retrieval import generate_vault_retrieval_example
from training.track2_future.interrogation_room_sim import (
    generate_interrogation_room_example,
    validate_interrogation_room_example,
)
from training.verify_factory_corpus import verify_corpus_directory


class TestAllSpec7Engines(unittest.TestCase):
    def test_01_murder_board_sim_11_chairs_and_modes(self) -> None:
        seen_chairs: set[str] = set()
        seen_modes: set[str] = set()
        # Case 0..4 (indices 0..54) cover both ACTIONABLE_RECORD_CHAIN and INSUFFICIENT_EVIDENCE_HOLD (case_index % 5 == 4)
        for case_idx in (0, 4):
            bundle = generate_murder_board_case_bundle("train", case_idx)
            seen_modes.add(bundle["case_mode"])
            self.assertEqual(len(bundle["documents"]), 16)
            for step_offset in range(len(MB_STEPS)):
                idx = case_idx * len(MB_STEPS) + step_offset
                row = generate_murder_board_example("train", idx)
                seen_chairs.add(row["subtask"])
                self.assertEqual(row["domain"], "cold_case_murder_board")
                self.assertEqual(row["ground_truth"]["quote_check_drops"], 0)

                res = compute_investigator_reward(
                    row["messages"][:-1],
                    row["messages"][-1]["content"],
                    row["ground_truth"],
                )
                self.assertGreaterEqual(
                    res["reward"],
                    0.95,
                    f"Murder board chair {row['subtask']} (mode={bundle['case_mode']}) reward < 0.95: {res}",
                )
                self.assertEqual(res["violations"], [])

        self.assertEqual(len(seen_chairs), 11)
        self.assertIn("ACTIONABLE_RECORD_CHAIN", seen_modes)
        self.assertIn("INSUFFICIENT_EVIDENCE_HOLD", seen_modes)

        with tempfile.TemporaryDirectory(prefix="mb_playable_test_") as tmp:
            dirs = export_playable_cases(Path(tmp), count=2)
            self.assertEqual(len(dirs), 2)
            for d in dirs:
                self.assertTrue((d / "registry.json").exists())
                self.assertTrue((d / "golden_outputs.json").exists())
                self.assertTrue((d / "doc01.txt").exists())
                self.assertTrue((d / "doc16.txt").exists())

    def test_02_noisy_vault_retrieval_sim(self) -> None:
        postures: set[str] = set()
        # Index 0..4 covers actionable + archival hold (index % 5 == 4)
        for idx in range(5):
            row = generate_vault_retrieval_example("train", idx)
            gt = row["ground_truth"]
            postures.add(gt["case_posture"])
            self.assertTrue(80 <= gt["vault_size"] <= 120)
            self.assertTrue(4 <= gt["pre_submit_hops"] <= 6)
            self.assertEqual(gt["quote_check_drops"], 0)

            res = compute_investigator_reward(
                row["messages"][:-1],
                row["messages"][-1]["content"],
                gt,
            )
            self.assertGreaterEqual(
                res["reward"],
                0.95,
                f"Vault retrieval idx={idx} ({gt['case_posture']}) reward < 0.95: {res}",
            )
            self.assertEqual(res["violations"], [])

        self.assertIn("ACTIONABLE_EVIDENCE_CHAIN", postures)
        self.assertIn("ARCHIVAL_HOLD_MISSING_RECORDS", postures)

    def test_03_forensic_micro_skills_all_8_drills(self) -> None:
        seen_drills: set[str] = set()
        for idx in range(len(MICRO_SKILL_TYPES) * 2):
            row = generate_micro_skill_example("train", idx)
            self.assertEqual(validate_micro_skill_example(row), [])
            seen_drills.add(row["subtask"])

            res = compute_investigator_reward(
                row["messages"][:-1],
                row["messages"][-1]["content"],
                row["ground_truth"],
            )
            self.assertGreaterEqual(
                res["reward"],
                0.95,
                f"Forensic micro-skill {row['subtask']} (idx={idx}) reward < 0.95: {res}",
            )
            self.assertEqual(res["violations"], [])

        self.assertEqual(seen_drills, set(MICRO_SKILL_TYPES))

    def test_04_dispatch_911_sim(self) -> None:
        modes_seen: set[str] = set()
        for idx in range(24):
            row = generate_dispatch_911_example("train", idx)
            gt = row["ground_truth"]
            modes_seen.add(gt["interaction_mode"])
            self.assertLessEqual(gt["next_line_word_count"], 18)
            for wc in gt["all_turn_word_counts"]:
                self.assertLessEqual(wc, 18)
            self.assertEqual(gt["quote_check_drops"], 0)

            res = compute_investigator_reward(
                row["messages"][:-1],
                row["messages"][-1]["content"],
                gt,
            )
            self.assertGreaterEqual(
                res["reward"],
                0.95,
                f"911 triage idx={idx} ({gt['sub_archetype']}) reward < 0.95: {res}",
            )
            self.assertEqual(res["violations"], [])

        self.assertIn("single_turn", modes_seen)
        self.assertIn("multi_turn_escalation", modes_seen)
        self.assertGreaterEqual(len(SUB_ARCHETYPE_CATALOG), 21)

    def test_05_aml_hunter_sim(self) -> None:
        dispositions: set[str] = set()
        modes: set[str] = set()
        for idx in range(25):
            row = generate_aml_hunter_example("train", idx)
            gt = row["ground_truth"]
            dispositions.add(gt["disposition"])
            modes.add(gt["interaction_mode"])
            self.assertIn(gt["detected_typology"], AML_TYPOLOGIES)
            self.assertEqual(gt["quote_check_drops"], 0)

            res = compute_investigator_reward(
                row["messages"][:-1],
                row["messages"][-1]["content"],
                gt,
            )
            self.assertGreaterEqual(
                res["reward"],
                0.95,
                f"AML hunter idx={idx} ({gt['detected_typology']}) reward < 0.95: {res}",
            )
            self.assertEqual(res["violations"], [])

        self.assertIn("FILE_SAR_ESCALATE", dispositions)
        self.assertIn("CLEAR_NO_SAR", dispositions)
        self.assertIn("static_dossier", modes)
        self.assertIn("multi_step_tool_trajectory", modes)

    def test_06_interrogation_room_sim_and_othello_cliff(self) -> None:
        room_modes: set[str] = set()
        othello_row = None
        for idx in range(20):
            row = generate_interrogation_room_example("train", idx)
            validate_interrogation_room_example(row)
            gt = row["ground_truth"]
            room_modes.add(gt["room_mode"])
            if gt.get("othello_trap") and othello_row is None:
                othello_row = row

            res = compute_investigator_reward(
                row["messages"][:-1],
                row["messages"][-1]["content"],
                gt,
            )
            self.assertGreaterEqual(
                res["reward"],
                0.95,
                f"Track 2 Room idx={idx} ({row['subtask']}) reward < 0.95: {res}",
            )
            self.assertEqual(res["violations"], [])

        self.assertEqual(room_modes, {"homicide_interview", "triage_911_bodycam", "aml_customs_secondary"})
        self.assertIsNotNone(othello_row)

        # Verify hard -1.0 Othello-Error Cliff on live Othello trap example when completion accuses of lying/deception
        assert othello_row is not None
        corrupted_payload = json.loads(othello_row["messages"][-1]["content"])
        corrupted_payload["next_room_protocol_move"] = (
            "Confront subject immediately; elevated heart rate and sweat indicate deception and subject is lying."
        )
        cliff_res = compute_investigator_reward(
            othello_row["messages"][:-1],
            json.dumps(corrupted_payload),
            othello_row["ground_truth"],
        )
        self.assertEqual(cliff_res["reward"], -1.0)
        self.assertIn("othello_error_cliff_triggered", cliff_res["violations"])

        # Verify hard -1.0 Othello-Error Cliff when innocent_physiological_alternative is omitted
        corrupted_missing_inno = json.loads(othello_row["messages"][-1]["content"])
        corrupted_missing_inno["innocent_physiological_alternative"] = ""
        cliff_res_2 = compute_investigator_reward(
            othello_row["messages"][:-1],
            json.dumps(corrupted_missing_inno),
            othello_row["ground_truth"],
        )
        self.assertEqual(cliff_res_2["reward"], -1.0)
        self.assertIn("othello_error_cliff_triggered", cliff_res_2["violations"])

    def test_07_real_v1_archive_shards(self) -> None:
        real_dir = Path(__file__).resolve().parents[1] / "datasets" / "real_v1"
        self.assertTrue(real_dir.exists(), f"Missing real_v1 directory at {real_dir}")
        report = verify_corpus_directory(real_dir)
        self.assertEqual(report["status"], "PASSED")
        self.assertTrue(report["under_10gb_cap"])
        self.assertGreaterEqual(report["total_rows"], 600)
        self.assertIn("cold_case_murder_board", report["by_domain"])
        self.assertIn("dispatch_911_triage", report["by_domain"])
        self.assertIn("aml_laundering_hunter", report["by_domain"])

    def test_08_chunked_10gb_adapters_and_rlvr_rewards_suites(self) -> None:
        self.assertGreaterEqual(len(ADAPTER_REGISTRY), 9)
        guard = BatchBudgetGuard()
        self.assertEqual(guard.max_bytes, int(9.5 * (1024 ** 3)))

        adapter_summary = run_adapters_self_test()
        self.assertEqual(adapter_summary["status"], "PASS")
        self.assertEqual(adapter_summary["converters_verified"], 9)
        self.assertTrue(adapter_summary["checkpoint_resume_verified"])

        rlvr_summary = run_rlvr_self_test()
        self.assertEqual(rlvr_summary["status"], "PASS")
        self.assertGreaterEqual(rlvr_summary["total_assertions_passed"], 25)

    def test_09_strict_qlora_chatml_export_and_folder_verifier(self) -> None:
        samples = [
            generate_murder_board_example("train", 0),
            generate_vault_retrieval_example("train", 0),
            generate_micro_skill_example("train", 0),
            generate_dispatch_911_example("train", 0),
            generate_aml_hunter_example("train", 0),
            generate_interrogation_room_example("train", 0),
        ]
        with tempfile.TemporaryDirectory(prefix="qlora_strict_test_") as tmp:
            folder = Path(tmp) / "01_test_qlora"
            folder.mkdir(parents=True, exist_ok=True)
            for split in ("train", "val", "test"):
                fp = folder / f"{split}.jsonl"
                with fp.open("w", encoding="utf-8") as f:
                    for raw in samples:
                        strict_row = normalize_to_strict_qlora_chatml(raw)
                        self.assertEqual(list(strict_row.keys()), ["messages"])
                        f.write(json.dumps(strict_row, ensure_ascii=False) + "\n")

            stats = verify_strict_qlora_folder(folder)
            self.assertEqual(stats["train"]["rows"], len(samples))
            self.assertEqual(stats["val"]["rows"], len(samples))
            self.assertEqual(stats["test"]["rows"], len(samples))
            self.assertLess(stats["total_mb"], 10.0)

            # Verify extra top-level column is caught immediately by verify_strict_qlora_folder
            bad_folder = Path(tmp) / "02_bad_qlora"
            bad_folder.mkdir(parents=True, exist_ok=True)
            (bad_folder / "train.jsonl").write_text(
                json.dumps({
                    "messages": [
                        {"role": "user", "content": "Prompt"},
                        {"role": "assistant", "content": "Response"},
                    ],
                    "extra_column": 123,
                }) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError):
                verify_strict_qlora_folder(bad_folder)


if __name__ == "__main__":
    unittest.main()
