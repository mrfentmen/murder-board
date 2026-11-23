#!/usr/bin/env python3
"""Unit tests for bank_detective.py and build_training_mix.py."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bank_detective import audit_corpus, bank_rows
from build_training_mix import compile_bundle


class TestDetectiveBanker(unittest.TestCase):
    def test_bank_and_bundle_all_specialties(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            out_dir = root / "bundle"

            # 1. Cold case
            bank_rows(
                "cold_case",
                [
                    {
                        "family": "survival-window-narrowing",
                        "user": "File MB-2016-09: doc02 ME sets death 22:30-00:30. doc10 logs outgoing SMS from victim phone at 23:46. doc05 logs victim keypad code 3305 at 23:54.",
                        "assistant": (
                            "CASE BLUF: Practical survival floor narrows to 23:54-00:30 while preserving the 22:30-00:30 ME window on record.\n"
                            "1. TIMELINE: doc10 ('outgoing SMS from victim phone at 23:46') and doc05 ('code 3305 at 23:54') establish activity post-23:45.\n"
                            "2. INNOCENT ALTERNATIVE: Another person possessing the handset or code 3305 triggered the 23:54 unlock; corroborate handset lock-state."
                        ),
                    }
                ],
                data_dir=data_dir,
                sleep_s=0.0,
            )

            # 2. Room biometrics (requires innocent alternative & rejects polygraph overclaims)
            bad = bank_rows(
                "room_biometrics",
                [
                    {
                        "family": "othello-innocent-panic",
                        "user": "Subject HR=132 BPM, EDA=8.4 uS on both control and target questions.",
                        "assistant": "CASE BLUF: Sweat proves lying on the murder question.",
                    }
                ],
                data_dir=data_dir,
                sleep_s=0.0,
            )
            self.assertEqual(bad["last_batch"]["accepted"], 0)

            good_room = bank_rows(
                "room_biometrics",
                [
                    {
                        "family": "othello-innocent-panic",
                        "user": "Room Session R-14: Baseline HR 124 BPM, EDA 7.8 uS during control questions; HR 128 BPM, EDA 8.1 uS during 23:00 alibi question; flat on 5-item CIT shim array.",
                        "assistant": (
                            "CASE BLUF: Generalized sympathetic arousal without stimulus-locked CIT recognition—classic Othello-error profile.\n"
                            "1. BIOMETRIC DELTA: Minimal delta (+4 BPM, +0.3 uS EDA) between control and alibi prompts; zero RMSSD crash on the withheld CIT item.\n"
                            "2. INNOCENT ALTERNATIVE: Acute fear of wrongful accusation or generalised interrogation anxiety.\n"
                            "3. NEXT LEAD: Shift to non-confrontational PEACE open recall and verify peripheral parking timestamp via ALPR."
                        ),
                    }
                ],
                data_dir=data_dir,
                sleep_s=0.0,
            )
            self.assertEqual(good_room["last_batch"]["accepted"], 1)

            # 3. Code fence validation
            bank_rows(
                "code",
                [
                    {
                        "family": "rppg-hrv-rmssd-calc",
                        "user": "Write a Python function computing vagal HRV RMSSD in milliseconds from inter-beat intervals (IBI ms).",
                        "assistant": (
                            "CASE BLUF: Compute root mean square of successive RR differences to detect stimulus-locked vagal withdrawal.\n"
                            "```python\n"
                            "import math\n\n"
                            "def compute_rmssd_ms(ibi_ms: list[float]) -> float:\n"
                            "    if len(ibi_ms) < 2:\n"
                            "        raise ValueError('Need >= 2 IBIs')\n"
                            "    diffs = [(ibi_ms[i + 1] - ibi_ms[i]) ** 2 for i in range(len(ibi_ms) - 1)]\n"
                            "    return round(math.sqrt(sum(diffs) / len(diffs)), 2)\n"
                            "```"
                        ),
                    }
                ],
                data_dir=data_dir,
                sleep_s=0.0,
            )

            # 4. Validation row
            bank_rows(
                "val",
                [
                    {
                        "family": "val-cold-case",
                        "user": "Audit Case MB-99: doc01 observes 'Two brass casings near desk'; doc13 ledger logs 'Item 4: One brass casing'.",
                        "assistant": (
                            "CASE BLUF: Material CSI custody count discrepancy between scene report and property ledger.\n"
                            "1. GAP: doc01 ('Two brass casings near desk') vs. doc13 ('Item 4: One brass casing').\n"
                            "2. INNOCENT ALTERNATIVE: Clerical transcription omission on intake sheet or second casing booked under a separate voucher.\n"
                            "3. NEXT LEAD: Audit physical property envelope seals and scene photo log."
                        ),
                    }
                ],
                data_dir=data_dir,
                sleep_s=0.0,
            )

            aud = audit_corpus(data_dir=data_dir)
            self.assertEqual(aud["total_unique_prompts"], 4)

            manifest = compile_bundle(data_dir=data_dir, out_dir=out_dir)
            self.assertEqual(manifest["train_rows"], 3)
            self.assertEqual(manifest["val_rows"], 1)


if __name__ == "__main__":
    unittest.main()
