#!/usr/bin/env python3
"""Unit tests for training/common (validators, split RNG isolation, almanac, physiology)."""

from __future__ import annotations

import unittest

from training.common import (
    STANDING_BRIEF_CLOSER,
    almanac_for_night,
    check_prosecutor_vetoes,
    deterministic_seed,
    euclidean_drive_minutes,
    load_mb_agent_prompts,
    make_rng,
    quote_ok,
    recompute_score,
    road_miles_between,
    sample_biometric_baseline,
    sample_biometric_turn,
    sample_unique_names,
)


class TestCommonFoundation(unittest.TestCase):
    def test_split_seed_disjointness(self) -> None:
        splits = ("train", "val", "test", "eval_sim")
        seen: set[int] = set()
        for sp in splits:
            for idx in range(500):
                s = deterministic_seed(sp, "domain_a", idx)
                self.assertNotIn(s, seen, f"Seed collision on {sp}:{idx}")
                seen.add(s)

    def test_load_murder_board_prompts(self) -> None:
        prompts = load_mb_agent_prompts()
        self.assertEqual(len(prompts), 11)
        self.assertIn("01_first_officer.md", prompts)
        self.assertIn("08_cross_examiner.md", prompts)
        self.assertIn("11_lead_detective.md", prompts)

    def test_quote_ok_exact_port(self) -> None:
        docs = {
            "doc01": {"id": "doc01", "text": "Two   shell casings were observed\non the office floor near the desk."},
        }
        self.assertTrue(quote_ok("Two shell casings were observed on the office floor", "doc01", docs))
        self.assertFalse(quote_ok("two casings", "doc01", docs))  # paraphrased
        self.assertFalse(quote_ok("floor", "doc01", docs))        # < 8 chars
        self.assertFalse(quote_ok("Two shell casings were observed", "doc99", docs))

    def test_recompute_score_rubric(self) -> None:
        self.assertEqual(
            recompute_score({"cites_high_contradiction": True, "in_window": True, "closes_gap": False, "still_reachable": True}),
            80,
        )
        self.assertEqual(
            recompute_score({"cites_high_contradiction": True, "in_window": True, "closes_gap": True, "still_reachable": True}),
            100,
        )
        self.assertEqual(recompute_score({}), 0)

    def test_prosecutor_vetoes(self) -> None:
        clean_brief = f"Record doc05 conflicts with doc03 at 00:09.\n\n{STANDING_BRIEF_CLOSER}"
        self.assertEqual(check_prosecutor_vetoes(clean_brief, [{"phrase": "killed", "reason": "no"}]), [])

        bad_brief = "Marcus Webb is guilty and is lying about the car."
        hits = check_prosecutor_vetoes(bad_brief, [{"phrase": "killed", "reason": "no"}])
        self.assertIn("is guilty", hits)
        self.assertIn("is lying", hits)

    def test_road_distance_and_almanac(self) -> None:
        mi = road_miles_between((0.0, 0.0), (10.0, 0.0))
        self.assertAlmostEqual(mi, 12.8, places=1)
        mins = euclidean_drive_minutes((0.0, 0.0), (10.0, 0.0), mph=38.0)
        self.assertGreaterEqual(mins, 20)

        rng = make_rng("train", "alm_test", 1)
        alm = almanac_for_night(rng, "2018-10-14")
        self.assertTrue(0 <= alm["moon_illumination_pct"] <= 100)
        self.assertGreaterEqual(alm["unlit_visibility_feet"], 30)

    def test_biometric_biological_bounds_1000_draws(self) -> None:
        rng = make_rng("train", "bio_bounds", 42)
        archetypes = ("OTHELLO_INNOCENT_ANXIOUS", "TRAUMA_WITNESS", "CALM_CONCEALER")
        stimuli = (
            "neutral_control",
            "general_accusation_calm_liar",
            "cit_guilty_knowledge_hit",
            "cognitive_load_reverse_order",
            "othello_panic_both_control_and_target",
            "embarrassed_unrelated_secret",
            "trauma_sensory_flashback",
        )
        for _ in range(1000):
            arch = rng.choice(archetypes)
            base = sample_biometric_baseline(rng, arch)
            stim = rng.choice(stimuli)
            turn = sample_biometric_turn(rng, base, stim)
            b = turn["biometrics"]
            a = turn["acoustics"]
            self.assertTrue(48.0 <= b["hr_bpm"] <= 175.0)
            self.assertTrue(8.0 <= b["hrv_rmssd_ms"] <= 95.0)
            self.assertTrue(0.4 <= b["eda_sweat_uS"] <= 22.0)
            self.assertTrue(7.0 <= b["respiration_rpm"] <= 36.0)
            self.assertGreaterEqual(a["response_latency_ms"], 180)

    def test_unique_name_pool_capacity(self) -> None:
        rng = make_rng("val", "names", 7)
        names = sample_unique_names(rng, 250)
        self.assertEqual(len(names), 250)
        self.assertEqual(len(set(names)), 250)


if __name__ == "__main__":
    unittest.main()
