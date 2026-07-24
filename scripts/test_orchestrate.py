#!/usr/bin/env python3
"""
Standard-library (unittest) test suite for scripts/orchestrate.py.

The module under test is loaded directly from its path with importlib (no package
import), and every place orchestrate.py would spawn a real model CLI or open a
socket is patched via unittest.mock — NO real claude/codex/gemini/grok/kimi
process and NO network call is ever made.

Run:
    cd /Users/davidbalan/Downloads/Projects/cybersecurity
    python3 -m unittest scripts.test_orchestrate -v
or:
    python3 scripts/test_orchestrate.py
"""

import contextlib
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Load the module under test straight from its file path (no package import).
# ---------------------------------------------------------------------------
_MOD_PATH = Path(__file__).resolve().parent / "orchestrate.py"
_spec = importlib.util.spec_from_file_location("orchestrate_under_test", _MOD_PATH)
orch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orch)


def _silence_stderr():
    """orchestrate.py logs progress/manifests to stderr; swallow it during tests."""
    return contextlib.redirect_stderr(io.StringIO())


class FakeProc:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ---------------------------------------------------------------------------
# merge(): weighted agreement + sort order
# ---------------------------------------------------------------------------
class TestMerge(unittest.TestCase):
    def _by_worker(self):
        A_fable = {"category": "sql-injection", "location": "app.py:10",
                   "severity": "high", "remediation": "short"}
        A_sol = {"category": "SQL-Injection", "location": "app.py:10",
                 "severity": "high",
                 "remediation": "a much longer and more detailed remediation text"}
        A_extra = {"category": "sql-injection", "location": "app.py:10",
                   "severity": "medium"}  # extra worker, NOT in weights -> default 1.0
        B_grok = {"category": "xss", "location": "web.py:5", "severity": "critical"}
        C_fable = {"category": "info-leak", "location": "log.py:3", "severity": "high"}
        return {
            "fable": [A_fable, C_fable],
            "sol": [A_sol],
            "grok": [B_grok],
            "extra": [A_extra],
        }

    def test_weighted_agreement_and_sort(self):
        weights = {"fable": 1.1, "sol": 1.2, "grok": 1.0}  # 'extra' absent -> 1.0
        out = orch.merge(self._by_worker(), weights)

        self.assertEqual(len(out), 3)

        # Sort: severity desc, then agreement_weight desc, then agreement_count desc.
        self.assertEqual(out[0]["category"], "xss")          # critical wins
        self.assertEqual(out[1]["category"], "sql-injection")  # high, weight 3.3
        self.assertEqual(out[2]["category"], "info-leak")      # high, weight 1.1

        sqli = out[1]
        # _key() lowercases+strips whitespace so "SQL-Injection" merges with "sql-injection".
        self.assertEqual(sqli["agreement_count"], 3)
        self.assertEqual(sqli["agreement"], ["extra", "fable", "sol"])  # sorted
        # 1.1 (fable) + 1.2 (sol) + 1.0 (extra default) = 3.3
        self.assertAlmostEqual(sqli["agreement_weight"], 3.3, places=3)
        # severity = max across reported severities (high beats medium)
        self.assertEqual(sqli["severity"], "high")
        self.assertTrue(sqli["severity_disagreement"])  # high vs medium
        # keeps the most detailed remediation seen
        self.assertEqual(sqli["remediation"],
                         "a much longer and more detailed remediation text")

        xss = out[0]
        self.assertAlmostEqual(xss["agreement_weight"], 1.0, places=3)
        self.assertEqual(xss["agreement_count"], 1)
        self.assertFalse(xss["severity_disagreement"])

        leak = out[2]
        self.assertAlmostEqual(leak["agreement_weight"], 1.1, places=3)

    def test_no_weights_defaults_to_one(self):
        out = orch.merge(self._by_worker())  # weights omitted entirely
        sqli = next(x for x in out if x["category"] == "sql-injection")
        # all three contributors default to weight 1.0
        self.assertAlmostEqual(sqli["agreement_weight"], 3.0, places=3)
        self.assertEqual(sqli["agreement_count"], 3)

    def test_empty_input(self):
        self.assertEqual(orch.merge({}, {}), [])


# ---------------------------------------------------------------------------
# parse_findings(): None (prose) / [] (empty) / dict-filter (mixed)
# ---------------------------------------------------------------------------
class TestParseFindings(unittest.TestCase):
    def test_prose_returns_none(self):
        # A refusal / prose with no JSON array at all is a NON-CONTRIBUTION.
        self.assertIsNone(orch.parse_findings("I refuse; there is no JSON here."))
        self.assertIsNone(orch.parse_findings(""))
        self.assertIsNone(orch.parse_findings("```"))

    def test_empty_array_is_clean_bill(self):
        self.assertEqual(orch.parse_findings("[]"), [])
        self.assertEqual(orch.parse_findings("   []   "), [])

    def test_clean_array_of_dicts(self):
        out = orch.parse_findings('[{"title":"a","severity":"low"}]')
        self.assertEqual(out, [{"title": "a", "severity": "low"}])

    def test_fenced_json_block(self):
        raw = '```json\n[{"title":"x"}]\n```'
        self.assertEqual(orch.parse_findings(raw), [{"title": "x"}])

    def test_mixed_array_keeps_only_dicts(self):
        raw = '[{"title":"a"}, 5, "s", null, {"title":"b"}, [1,2]]'
        out = orch.parse_findings(raw)
        self.assertEqual(out, [{"title": "a"}, {"title": "b"}])

    def test_array_embedded_in_prose_is_sliced(self):
        raw = 'Here are the findings I identified: [{"title":"z"}] -- done.'
        self.assertEqual(orch.parse_findings(raw), [{"title": "z"}])

    def test_scalar_bracket_in_prose_never_crashes_merge(self):
        # Documented behaviour: "[1]" sliced out of prose is filtered to [] (dicts
        # only) so a stray scalar can never reach merge() and crash it. It does NOT
        # raise, and merge() consumes it without error.
        out = orch.parse_findings("Confidence: [1] out of 5")
        self.assertEqual(out, [])
        # feed it through merge to prove no 'int has no attribute get' crash
        self.assertEqual(orch.merge({"w": out}, {}), [])


# ---------------------------------------------------------------------------
# to_sarif(): shape + level mapping + startLine + missing-field safety
# ---------------------------------------------------------------------------
class TestSarif(unittest.TestCase):
    def _merged(self):
        return [
            {"category": "sql-injection", "severity": "critical",
             "location": "app.py:42", "title": "SQLi", "confidence": "high",
             "agreement_count": 2, "agreement_weight": 2.3, "agreement": ["a", "b"],
             "evidence": "e", "impact": "i", "remediation": "r"},
            {"category": "xss", "severity": "medium", "location": "web.py",
             "title": "XSS"},                        # no line -> no region; warning
            {"severity": "low", "location": ""},      # no category/title -> defaults
            {"category": "misc", "severity": "totally-bogus"},  # unknown sev -> note
        ]

    def test_document_shape(self):
        import json
        doc = json.loads(orch.to_sarif(self._merged(), "code_review"))
        self.assertEqual(doc["version"], "2.1.0")
        self.assertIn("sarif-2.1.0", doc["$schema"])
        run = doc["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "cybersecurity-ensemble")
        self.assertEqual(run["properties"]["mode"], "code_review")
        self.assertEqual(len(run["results"]), 4)
        rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
        self.assertIn("sql-injection", rule_ids)
        self.assertIn("finding", rule_ids)  # missing-category finding

    def test_level_mapping_and_startline(self):
        import json
        results = json.loads(orch.to_sarif(self._merged(), "code_review"))["runs"][0]["results"]
        r0, r1, r2, r3 = results

        # critical -> error, with a startLine region
        self.assertEqual(r0["level"], "error")
        self.assertEqual(r0["ruleId"], "sql-injection")
        self.assertEqual(
            r0["locations"][0]["physicalLocation"]["region"]["startLine"], 42)
        self.assertEqual(r0["message"]["text"], "SQLi")

        # medium -> warning, no region because location had no line
        self.assertEqual(r1["level"], "warning")
        self.assertNotIn("region", r1["locations"][0]["physicalLocation"])
        self.assertEqual(
            r1["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "web.py")

        # low -> note; missing category -> "finding"; missing title/impact -> fallback;
        # empty location -> "unknown" uri, no region
        self.assertEqual(r2["level"], "note")
        self.assertEqual(r2["ruleId"], "finding")
        self.assertEqual(r2["message"]["text"], "security finding")
        self.assertEqual(
            r2["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "unknown")
        self.assertNotIn("region", r2["locations"][0]["physicalLocation"])

        # unknown severity -> default note
        self.assertEqual(r3["level"], "note")

    def test_properties_carry_agreement_metadata(self):
        import json
        r0 = json.loads(orch.to_sarif(self._merged(), "code_review"))["runs"][0]["results"][0]
        props = r0["properties"]
        self.assertEqual(props["severity"], "critical")
        self.assertEqual(props["agreement_count"], 2)
        self.assertEqual(props["agreement_weight"], 2.3)
        self.assertEqual(props["agreement"], ["a", "b"])

    def test_empty_findings_produces_valid_sarif(self):
        import json
        doc = json.loads(orch.to_sarif([], "threat_model"))
        self.assertEqual(doc["runs"][0]["results"], [])
        self.assertEqual(doc["runs"][0]["tool"]["driver"]["rules"], [])


# ---------------------------------------------------------------------------
# _split_location(): edge cases
# ---------------------------------------------------------------------------
class TestSplitLocation(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(orch._split_location(""), ("unknown", None))
        self.assertEqual(orch._split_location(None), ("unknown", None))
        self.assertEqual(orch._split_location("app.py:42"), ("app.py", 42))
        self.assertEqual(orch._split_location("app.py:10-20"), ("app.py", 10))
        self.assertEqual(orch._split_location("component X"), ("component X", None))
        self.assertEqual(orch._split_location("  app.py:7  "), ("app.py", 7))
        # a leading-colon "location" has an empty file part -> not treated as file:line
        self.assertEqual(orch._split_location(":42"), (":42", None))
        # greedy match keeps a Windows drive path intact
        self.assertEqual(orch._split_location(r"C:\Users\x:15"), (r"C:\Users\x", 15))
        # line 0 is a valid parse here, but to_sarif drops it (see region test)
        self.assertEqual(orch._split_location("f.py:0"), ("f.py", 0))


# ---------------------------------------------------------------------------
# _redact() and _redact_literals()
# ---------------------------------------------------------------------------
class TestRedact(unittest.TestCase):
    def test_redacts_known_token_shapes(self):
        aws = "AKIAIOSFODNN7EXAMPLE"
        out, n = orch._redact(f"aws_key = {aws}")
        self.assertGreaterEqual(n, 1)
        self.assertNotIn(aws, out)
        self.assertIn("[REDACTED-SECRET]", out)

    def test_redacts_openai_style_key(self):
        key = "sk-" + "A1b2C3d4E5f6G7h8"
        out, n = orch._redact(f"token: {key}")
        self.assertGreaterEqual(n, 1)
        self.assertNotIn(key, out)

    def test_keyword_value_pattern(self):
        out, n = orch._redact('password = "supersecret123"')
        self.assertGreaterEqual(n, 1)
        self.assertNotIn("supersecret123", out)

    def test_clean_text_unchanged(self):
        clean = "def add(a, b):\n    return a + b\n"
        out, n = orch._redact(clean)
        self.assertEqual(n, 0)
        self.assertEqual(out, clean)


class TestRedactLiterals(unittest.TestCase):
    def test_longest_first_prevents_superstring_leak(self):
        # A superstring's tail ("BBBB") must NOT survive because a substring got
        # redacted first. Longest-first ordering guarantees full masking.
        text = "aaaAAAA and aaaAAAABBBB"
        out, n = orch._redact_literals(text, {"aaaAAAA", "aaaAAAABBBB"})
        self.assertEqual(out, "[REDACTED-SECRET] and [REDACTED-SECRET]")
        self.assertNotIn("BBBB", out)
        self.assertEqual(n, 2)

    def test_short_literals_are_ignored(self):
        # Literals shorter than 4 chars (and empties) are skipped to avoid nuking
        # everything; only "abcd" (len 4) is masked.
        text = "abcd and ab and xy"
        out, n = orch._redact_literals(text, {"", "ab", "xy", "abcd"})
        self.assertIn("[REDACTED-SECRET]", out)
        self.assertIn("ab and xy", out)   # the short ones survive
        self.assertEqual(n, 1)

    def test_no_matches(self):
        out, n = orch._redact_literals("nothing here", {"absent-secret"})
        self.assertEqual(out, "nothing here")
        self.assertEqual(n, 0)


# ---------------------------------------------------------------------------
# _worker_cap() / _worker_weight(): coercion + fallbacks
# ---------------------------------------------------------------------------
class TestWorkerCap(unittest.TestCase):
    def test_valid_and_string_coercion(self):
        self.assertEqual(orch._worker_cap({"max_chars": 5000}, 99), 5000)
        self.assertEqual(orch._worker_cap({"max_chars": "5000"}, 99), 5000)

    def test_fallbacks(self):
        self.assertEqual(orch._worker_cap({}, 42), 42)               # unset
        self.assertEqual(orch._worker_cap({"max_chars": 0}, 42), 42)   # non-positive
        self.assertEqual(orch._worker_cap({"max_chars": -7}, 42), 42)  # negative
        self.assertEqual(orch._worker_cap({"max_chars": "abc"}, 42), 42)  # unparseable
        self.assertEqual(orch._worker_cap({"max_chars": None}, 42), 42)   # None


class TestWorkerWeight(unittest.TestCase):
    def test_valid_and_string_coercion(self):
        self.assertEqual(orch._worker_weight({"weight": 1.5}), 1.5)
        self.assertEqual(orch._worker_weight({"weight": "2"}), 2.0)

    def test_fallbacks(self):
        self.assertEqual(orch._worker_weight({}), 1.0)               # unset
        self.assertEqual(orch._worker_weight({"weight": 0}), 1.0)      # non-positive
        self.assertEqual(orch._worker_weight({"weight": -3}), 1.0)     # negative
        self.assertEqual(orch._worker_weight({"weight": "x"}), 1.0)    # unparseable
        self.assertEqual(orch._worker_weight({"weight": None}), 1.0)   # None


# ---------------------------------------------------------------------------
# _cap(): truncation with a custom max_chars
# ---------------------------------------------------------------------------
class TestCap(unittest.TestCase):
    def test_short_text_untouched(self):
        with _silence_stderr():
            self.assertEqual(orch._cap("hello", "x", 100), "hello")

    def test_truncates_with_announcement(self):
        with _silence_stderr():
            out = orch._cap("X" * 100, "big file", max_chars=20)
        self.assertTrue(out.startswith("X" * 20))
        self.assertEqual(out.count("X"), 20)         # body actually truncated
        self.assertIn("truncated at 20", out)        # announced, never silent
        self.assertNotIn("X" * 21, out)


# ---------------------------------------------------------------------------
# read_target(): typo SystemExit, inline heuristic, single-file cap,
#                directory walk skipping a planted .env, and stdin.
# ---------------------------------------------------------------------------
class TestReadTarget(unittest.TestCase):
    def test_typo_pathshaped_target_exits(self):
        # absolute-looking path that does not exist -> loud SystemExit, not "review"
        with _silence_stderr(), self.assertRaises(SystemExit):
            orch.read_target("/no/such/dir/definitely_missing.py")

    def test_typo_suffix_target_exits(self):
        # bare filename with a source suffix that doesn't exist -> SystemExit
        with _silence_stderr(), self.assertRaises(SystemExit):
            orch.read_target("totally_missing_xyz_typo.py")

    def test_inline_description_when_not_pathshaped(self):
        desc = "A stateless service that validates JWTs and talks to Postgres"
        with _silence_stderr():
            out = orch.read_target(desc)
        self.assertIn(desc, out)      # treated as inline text, returned verbatim

    def test_single_file_is_capped(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "big.py"
            fp.write_text("Z" * 500)
            with _silence_stderr():
                out = orch.read_target(str(fp), max_chars=20)
        self.assertIn("### FILE:", out)
        self.assertIn("truncated at 20", out)
        self.assertNotIn("Z" * 100, out)     # body was capped

    def test_directory_walk_skips_planted_env_secret(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "app.py").write_text("import os  # ordinary source\n")
            # a secret file that MUST be skipped and never transmitted
            (Path(d) / ".env").write_text("AWS=AKIAIOSFODNN7EXAMPLE\n")
            with _silence_stderr():
                out = orch.read_target(d)
        self.assertIn("app.py", out)                 # reviewable file included
        self.assertIn("import os", out)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", out)  # .env content never sent
        self.assertNotIn("### FILE: .env", out)

    def test_directory_walk_redacts_secret_in_reviewed_file(self):
        with tempfile.TemporaryDirectory() as d:
            # a *reviewable* file (.py) that happens to hold a hardcoded key ->
            # file is included but the key is redacted in place.
            (Path(d) / "cfg.py").write_text('API = "AKIAIOSFODNN7EXAMPLE"\n')
            with _silence_stderr():
                out = orch.read_target(d)
        self.assertIn("cfg.py", out)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", out)
        self.assertIn("[REDACTED-SECRET]", out)

    def test_stdin_pipe(self):
        piped = "diff --git a/x b/x\n+password = leak\n"
        with _silence_stderr(), mock.patch.object(orch.sys, "stdin",
                                                  io.StringIO(piped)):
            out = orch.read_target("-")
        self.assertIn("### PIPED INPUT", out)
        self.assertIn("diff --git", out)


# ---------------------------------------------------------------------------
# run_cli(): argv token substitution ({prompt}/{prompt_file}/stdin) and the
# inline-byte-size guard. subprocess.run is patched — no real CLI is executed.
# ---------------------------------------------------------------------------
class TestRunCli(unittest.TestCase):
    def test_stdin_delivery_no_token(self):
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(0, "OUT", "")) as m:
            out = orch.run_cli("claude -p --model claude-opus-4-8", "PROMPT-BODY", 30)
        self.assertEqual(out, "OUT")
        args, kwargs = m.call_args
        self.assertEqual(args[0], ["claude", "-p", "--model", "claude-opus-4-8"])
        self.assertEqual(kwargs.get("input"), "PROMPT-BODY")   # piped on stdin
        # stdin= must NOT be forced to DEVNULL when piping the prompt in
        self.assertNotIn("stdin", kwargs)

    def test_inline_prompt_token_substitution(self):
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(0, "OK", "")) as m:
            orch.run_cli("kimi -m k3 -p {prompt}", "hello world", 30)
        args, kwargs = m.call_args
        self.assertEqual(args[0], ["kimi", "-m", "k3", "-p", "hello world"])
        # inline/file delivery redirects stdin from /dev/null (never blocks on a TTY)
        self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL)
        self.assertNotIn("input", kwargs)

    def test_literal_prompt_token_inside_content_not_mangled(self):
        # INVARIANT: a literal "{prompt}" appearing INSIDE the reviewed content must
        # survive verbatim — only the roster TEMPLATE token is substituted.
        content = "review this: {prompt} and {prompt_file} should stay literal"
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(0, "OK", "")) as m:
            orch.run_cli("kimi -p {prompt}", content, 30)
        args, _ = m.call_args
        self.assertEqual(args[0], ["kimi", "-p", content])

    def test_prompt_file_delivery_writes_and_cleans_up(self):
        captured = {}

        def fake_run(argv, **kwargs):
            path = argv[-1]
            captured["argv"] = argv
            captured["exists_during_call"] = os.path.exists(path)
            captured["content"] = Path(path).read_text()
            captured["stdin"] = kwargs.get("stdin")
            captured["path"] = path
            return FakeProc(0, "OK", "")

        with mock.patch.object(orch.subprocess, "run", side_effect=fake_run):
            out = orch.run_cli("grok --prompt-file {prompt_file}", "FILE-PROMPT-BODY", 30)

        self.assertEqual(out, "OK")
        self.assertEqual(captured["argv"][0], "grok")
        self.assertEqual(captured["argv"][1], "--prompt-file")
        self.assertTrue(captured["exists_during_call"])
        self.assertEqual(captured["content"], "FILE-PROMPT-BODY")
        self.assertEqual(captured["stdin"], subprocess.DEVNULL)
        # temp file is removed in the finally block after the call returns
        self.assertFalse(os.path.exists(captured["path"]))

    def test_literal_content_not_mangled_via_stdin(self):
        # stdin delivery must also pass a literal {prompt} through untouched.
        content = "here is a {prompt} token in the target"
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(0, "OK", "")) as m:
            orch.run_cli("claude -p", content, 30)
        _, kwargs = m.call_args
        self.assertEqual(kwargs.get("input"), content)

    def test_inline_byte_size_guard_raises_and_never_execs(self):
        oversize = "a" * (orch.MAX_INLINE_PROMPT_BYTES + 1)
        with mock.patch.object(orch.subprocess, "run") as m:
            with self.assertRaises(RuntimeError) as ctx:
                orch.run_cli("kimi -p {prompt}", oversize, 30)
        self.assertIn("inline argv delivery", str(ctx.exception))
        m.assert_not_called()   # guard fires BEFORE any subprocess is spawned

    def test_inline_at_exactly_the_limit_is_allowed(self):
        exact = "a" * orch.MAX_INLINE_PROMPT_BYTES  # == limit, must NOT raise
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(0, "OK", "")) as m:
            orch.run_cli("kimi -p {prompt}", exact, 30)
        m.assert_called_once()

    def test_nonzero_exit_raises_with_redacted_stderr(self):
        leak = "AKIAIOSFODNN7EXAMPLE"
        with mock.patch.object(orch.subprocess, "run",
                               return_value=FakeProc(2, "", f"auth failed key {leak}")):
            with self.assertRaises(RuntimeError) as ctx:
                orch.run_cli("claude -p", "PROMPT", 30)
        msg = str(ctx.exception)
        self.assertIn("CLI exit 2", msg)
        self.assertNotIn(leak, msg)                 # secret scrubbed from error text
        self.assertIn("[REDACTED-SECRET]", msg)


# ---------------------------------------------------------------------------
# _write_private(): owner-only 0600
# ---------------------------------------------------------------------------
class TestWritePrivate(unittest.TestCase):
    def test_creates_file_mode_0600(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.md")
            orch._write_private(path, "sensitive report body")
            self.assertEqual(Path(path).read_text(), "sensitive report body")
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)

    def test_tightens_existing_loose_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "existing.sarif")
            Path(path).write_text("old")
            os.chmod(path, 0o644)   # world-readable to start
            orch._write_private(path, "new content")
            self.assertEqual(Path(path).read_text(), "new content")
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)


# ---------------------------------------------------------------------------
# Regression tests for defects found by the adversarial review pass (2026-07-24)
# ---------------------------------------------------------------------------
class TestReviewRegressions(unittest.TestCase):
    def test_sarif_location_file_line_col(self):
        # file:line:col must not swallow the line into the path and use the column as the line
        self.assertEqual(orch._split_location("src/auth.py:42:8"), ("src/auth.py", 42))
        self.assertEqual(orch._split_location("src/auth.py:42:8-12"), ("src/auth.py", 42))
        self.assertEqual(orch._split_location("C:/proj/file.py:10"), ("C:/proj/file.py", 10))
        self.assertEqual(orch._split_location("pkg/mod.go:7"), ("pkg/mod.go", 7))
        # regression must not break the plain forms
        self.assertEqual(orch._split_location("a/b.py:42"), ("a/b.py", 42))
        self.assertEqual(orch._split_location("component X"), ("component X", None))

    def test_trufflehog_runs_offline(self):
        # trufflehog MUST carry --no-verification, else it phones each secret's vendor API
        # with the candidate credential (exfiltration). Capture the argv it would run.
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return FakeProc(stdout="")   # no findings

        with mock.patch.object(orch.shutil, "which", return_value="/usr/bin/trufflehog"), \
             mock.patch.object(orch.subprocess, "run", side_effect=fake_run), \
             _silence_stderr():
            orch._scan_secrets_external("trufflehog", "some blob")
        self.assertIn("--no-verification", seen.get("argv", []))
        self.assertIn("--no-update", seen["argv"])

    def test_scanner_never_raises_on_setup_failure(self):
        # a temp-fs failure must degrade to regex-only (empty set), never abort the run
        with mock.patch.object(orch.shutil, "which", return_value="/usr/bin/gitleaks"), \
             mock.patch.object(orch.tempfile, "mkstemp", side_effect=OSError("temp fs full")), \
             _silence_stderr():
            self.assertEqual(orch._scan_secrets_external("gitleaks", "blob"), set())

    def test_write_private_tightens_via_fchmod(self):
        # the descriptor is tightened to 0600 with fchmod (before the sensitive bytes land)
        called = {}
        real = os.fchmod

        def rec(fd, mode):
            called["mode"] = mode
            return real(fd, mode)

        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(orch.os, "fchmod", side_effect=rec):
            orch._write_private(os.path.join(d, "r.md"), "secret body")
        self.assertEqual(called.get("mode"), 0o600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
