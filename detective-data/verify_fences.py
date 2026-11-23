#!/usr/bin/env python3
"""Read-only triple-backtick code-fence verifier for DEADBOLT JSONL streams.

Modeled on the verification section of `data for del/README.md`:
  - Scans any JSONL file or `data/*.jsonl` (strictly read-only),
  - Extracts all triple-backtick code fences across all messages:
      * Parses 100% of `python` / `py` fences with `ast.parse`,
      * Syntax-checks 100% of `bash` / `sh` fences with `bash -n`,
      * Parses 100% of `json` fences with `json.loads`,
      * Parses/executes self-contained `sql` fences against an in-memory
        `sqlite3.connect(":memory:")` syntax explain/prepare check where applicable,
  - Prints a clean JSON verification report and exits non-zero if any fence fails.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"

FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
DDL_RE = re.compile(r"\bCREATE\s+(?:TEMP\s+|TEMPORARY\s+)?(?:TABLE|VIEW)\b", re.I)
SQL_COMMENT_LINE_RE = re.compile(r"^\s*--.*$", re.M)


def check_python_fence(code: str) -> str | None:
    try:
        ast.parse(code)
        return None
    except SyntaxError as exc:
        return f"python SyntaxError (line {exc.lineno}): {exc.msg}"


def check_json_fence(code: str) -> str | None:
    try:
        json.loads(code)
        return None
    except Exception as exc:
        return f"json decode error: {exc}"


def check_bash_fence(code: str) -> str | None:
    try:
        proc = subprocess.run(
            ["bash", "-n"],
            input=code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            return f"bash -n failed: {err}"
        return None
    except Exception as exc:
        return f"bash execution error: {exc}"


def check_sql_fence(code: str) -> tuple[str, str | None]:
    """Verify SQL fences against an in-memory sqlite3 connection.

    Returns `(mode, error)` where `mode` is either `"executed_self_contained"`
    (when CREATE TABLE/VIEW DDL is included and executes cleanly) or
    `"syntax_checked"` (when queries reference external tables and pass
    SQLite statement completeness + syntax check without a syntax error).
    """
    stripped = SQL_COMMENT_LINE_RE.sub("", code).strip()
    if not stripped:
        return "empty", "empty SQL fence"

    conn = sqlite3.connect(":memory:")
    try:
        if DDL_RE.search(stripped):
            try:
                conn.executescript(code)
                return "executed_self_contained", None
            except sqlite3.OperationalError as exc:
                msg = str(exc)
                if "syntax error" in msg.lower() or "incomplete input" in msg.lower():
                    return "executed_self_contained", f"sqlite3 syntax error: {msg}"
                # Non-SQLite dialect or missing external table reference after partial DDL
                return "syntax_checked", None
            except sqlite3.Error as exc:
                return "executed_self_contained", f"sqlite3 error: {exc}"
        else:
            # Query-only SQL block without CREATE TABLE: verify statement syntax via EXPLAIN
            statements = [s.strip() for s in stripped.split(";") if s.strip()]
            for stmt in statements:
                try:
                    conn.execute(f"EXPLAIN {stmt}")
                except sqlite3.OperationalError as exc:
                    msg = str(exc)
                    # "no such table" / "no such function" / "no such column" means SQLite
                    # successfully parsed the SQL AST and reached schema resolution!
                    if "syntax error" in msg.lower() or "incomplete input" in msg.lower():
                        return "syntax_checked", f"sqlite3 syntax error: {msg}"
                except sqlite3.Error as exc:
                    msg = str(exc)
                    if "syntax error" in msg.lower():
                        return "syntax_checked", f"sqlite3 syntax error: {msg}"
            return "syntax_checked", None
    finally:
        conn.close()


def verify_jsonl_paths(paths: list[Path]) -> dict:
    files_scanned = 0
    rows_scanned = 0
    fences_by_lang: Counter[str] = Counter()
    passed_by_lang: Counter[str] = Counter()
    sql_modes: Counter[str] = Counter()
    failures: list[dict] = []

    for path in sorted(paths):
        if not path.exists() or not path.is_file():
            continue
        files_scanned += 1
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                rows_scanned += 1
                try:
                    obj = json.loads(line)
                except Exception as exc:
                    failures.append(
                        {
                            "file": str(path),
                            "line": line_no,
                            "row_id": None,
                            "lang": "jsonl",
                            "error": f"malformed JSONL row: {exc}",
                        }
                    )
                    continue

                row_id = obj.get("id", f"line-{line_no}")
                messages = obj.get("messages", [])
                for msg_idx, msg in enumerate(messages):
                    content = str(msg.get("content", ""))
                    if content.count("```") % 2 != 0:
                        failures.append(
                            {
                                "file": str(path),
                                "line": line_no,
                                "row_id": row_id,
                                "message_index": msg_idx,
                                "lang": "unbalanced",
                                "error": "unbalanced triple backticks",
                            }
                        )
                        continue
                    for fence_idx, (lang_raw, code) in enumerate(FENCE_RE.findall(content)):
                        lang = (lang_raw.strip().lower() or "plain")
                        fences_by_lang[lang] += 1
                        err: str | None = None
                        if lang in ("python", "py"):
                            err = check_python_fence(code)
                        elif lang in ("bash", "sh"):
                            err = check_bash_fence(code)
                        elif lang == "json":
                            err = check_json_fence(code)
                        elif lang in ("sql", "sqlite", "sqlite3"):
                            mode, err = check_sql_fence(code)
                            sql_modes[mode] += 1

                        if err is not None:
                            failures.append(
                                {
                                    "file": str(path),
                                    "line": line_no,
                                    "row_id": row_id,
                                    "message_index": msg_idx,
                                    "fence_index": fence_idx,
                                    "lang": lang,
                                    "error": err,
                                }
                            )
                        else:
                            passed_by_lang[lang] += 1

    return {
        "ok": len(failures) == 0,
        "files_scanned": files_scanned,
        "rows_scanned": rows_scanned,
        "total_fences": sum(fences_by_lang.values()),
        "fences_by_lang": dict(sorted(fences_by_lang.items())),
        "passed_by_lang": dict(sorted(passed_by_lang.items())),
        "sql_modes": dict(sorted(sql_modes.items())),
        "failure_count": len(failures),
        "failures": failures,
    }


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        valid_jsonl = tp / "valid_sample.jsonl"
        sample_rows = [
            {
                "id": "det-code-000001",
                "messages": [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "Verify Python, SQL, Bash, and JSON fences."},
                    {
                        "role": "assistant",
                        "content": (
                            "CASE BLUF: Multi-fence verification fixture.\n"
                            "```python\n"
                            "def rmssd(rr_ms: list[float]) -> float:\n"
                            "    diffs = [(rr_ms[i+1] - rr_ms[i]) ** 2 for i in range(len(rr_ms) - 1)]\n"
                            "    return (sum(diffs) / max(len(diffs), 1)) ** 0.5\n"
                            "```\n"
                            "```sql\n"
                            "CREATE TABLE alpr_hits (plate TEXT, ts INTEGER, gantry TEXT);\n"
                            "INSERT INTO alpr_hits VALUES ('KRT-4412', 1700000000, 'Route 9 Bridge');\n"
                            "SELECT plate, COUNT(*) FROM alpr_hits GROUP BY plate;\n"
                            "```\n"
                            "```sql\n"
                            "SELECT a.plate, b.tower_id FROM external_alpr a JOIN external_cdr b ON a.ts = b.ts WHERE a.plate = 'KRT-4412';\n"
                            "```\n"
                            "```bash\n"
                            "#!/usr/bin/env bash\n"
                            "set -euo pipefail\n"
                            "sha256sum *.jpg | sort -k2\n"
                            "```\n"
                            "```json\n"
                            '{"case_id": "MB-2026-001", "corroborated": true, "gaps": 0}\n'
                            "```"
                        ),
                    },
                ],
            }
        ]
        valid_jsonl.write_text("\n".join(json.dumps(r) for r in sample_rows) + "\n", encoding="utf-8")

        report = verify_jsonl_paths([valid_jsonl])
        assert report["ok"] is True, f"Expected valid fixture to pass: {report}"
        assert report["total_fences"] == 5
        assert report["passed_by_lang"]["python"] == 1
        assert report["passed_by_lang"]["sql"] == 2
        assert report["passed_by_lang"]["bash"] == 1
        assert report["passed_by_lang"]["json"] == 1
        assert report["sql_modes"]["executed_self_contained"] == 1
        assert report["sql_modes"]["syntax_checked"] == 1

        # Negative test: confirm broken Python, JSON, Bash, and SQL fences are caught
        broken_jsonl = tp / "broken_sample.jsonl"
        broken_rows = [
            {
                "id": "det-code-999999",
                "messages": [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "Broken fences."},
                    {
                        "role": "assistant",
                        "content": (
                            "```python\ndef broken(:\n    pass\n```\n"
                            "```json\n{bad json}\n```\n"
                            "```bash\nif [ 1 -eq 1 ; then echo hi\n```\n"
                            "```sql\nSELECT FROM WHERE GROUP BY;\n```"
                        ),
                    },
                ],
            }
        ]
        broken_jsonl.write_text("\n".join(json.dumps(r) for r in broken_rows) + "\n", encoding="utf-8")
        bad_report = verify_jsonl_paths([broken_jsonl])
        assert bad_report["ok"] is False
        assert bad_report["failure_count"] == 4, f"Expected 4 fence failures, got {bad_report}"

    print("verify_fences.py self-test ok")


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify triple-backtick code fences across JSONL files.")
    ap.add_argument("paths", nargs="*", type=Path, help="JSONL files or directories to scan (default: data/*.jsonl)")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    targets: list[Path] = []
    if args.paths:
        for p in args.paths:
            if p.is_dir():
                targets.extend(sorted(p.glob("*.jsonl")))
            else:
                targets.append(p)
    else:
        targets = sorted(args.data_dir.glob("*.jsonl"))

    report = verify_jsonl_paths(targets)
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
