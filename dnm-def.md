# Deferred / deliberately not built

Things that were asked for, or that surfaced during work, and were *not* implemented —
with the reasoning. See `qa.md` for the full running log.

---

## 2026-08-16 — semantic dedup in `merge()` (deferred)

**Surfaced by:** the validation run for the model refresh (see `qa.md`, 2026-08-16).

**What's wrong:** `_key()` in `scripts/orchestrate.py` keys findings on an exact string
match of `category|location`. Six models phrase both fields differently, so a live
six-worker run merged 55 raw findings into 52 — three merges, where the six models had
independently found the same four critical bugs. `agreement_count` and
`agreement_weight` are therefore largely inert as mechanically computed, even though the
per-model `weight` values are documented as a core confidence mechanism.

**Why it isn't fixed here:** the request was "update to the newest models." A dedup
rewrite is an independent change to the skill's core scoring, with a real failure mode
in the opposite direction — over-merging two genuinely distinct findings that happen to
share a file is worse than under-merging, because it hides a real issue instead of
merely repeating one. That needs its own design and its own test fixtures, not a
drive-by edit inside a version bump.

**Why it isn't blocking:** the shipped markdown report still comes out right. `merge()`
retains each fragment's `agreement` list of *worker names*, so the organizer receives six
near-duplicate rows tagged `["opus"]`, `["grok"]`, … and unions them itself — that is how
the validation run reported `agreement: 6` on its four criticals.

**But that is not a backstop.** The organizer is handed `json.dumps(merged)`, not the raw
worker payloads, and its prompt *tells* it the `agreement_count` tags are meaningful — so
the recovery depends on it noticing the duplication rather than trusting the tag. And two
consumers read `merge()` output directly, with no organizer in the path at all:

- the **SARIF export** (`--sarif`), which is what feeds CI code scanning, and
- **`_fallback_report()`**, used whenever the organizer call fails.

Both inherit the fragmentation unmitigated. (`--skip-recon` does *not* belong on that
list — it skips Phase 1 only; Phase 4 always runs. An earlier draft of this note claimed
otherwise and was wrong.)

**If picked up:** normalize `category` against a controlled vocabulary, reduce
`location` to a file/component identity rather than a line number, and fall back to
embedding or title similarity — then prove it on a fixture where two distinct findings
share a file, not just on one where six models describe one finding six ways.

---

## 2026-08-16 — byte-aware capping for inline workers (deferred)

**Surfaced by:** the pre-ship review of the model refresh (Codex / GPT-5.6 Sol, diff
review). Confirmed against the source.

**What's wrong:** the two limits are measured in different units.

- `_cap()` (`orchestrate.py:259`) truncates the target by `len(text)` — **characters**.
- `run_cli()` (`orchestrate.py:407`) rejects the assembled prompt by
  `len(prompt.encode("utf-8"))` — **bytes**, against `MAX_INLINE_PROMPT_BYTES = 100_000`.

For ASCII the two are the same and the 80,000-char inline cap is comfortably safe. For a
heavily multibyte target — CJK, Cyrillic, emoji — 80,000 characters can be two to four
times that in bytes, so the prompt blows the byte ceiling and the worker raises before it
launches. The ensemble then runs a voter short.

**Severity is limited by design, not by luck:** it fails **loudly**, with an error that
names the fix, rather than truncating silently. A degraded run is visible. That is the
difference between this and the Kimi-alias outage, which was invisible.

**Why it isn't fixed here:** it is pre-existing — it has affected the `kimi` seat since
inline delivery was introduced — and the fix touches `orchestrate.py`'s input path, which
this change deliberately left untouched (the whole change is roster + docs, and the
49-test suite passes precisely because no code moved). Patching a security tool's input
handling as an unreviewed drive-by at the end of a version bump is how a small correctness
fix becomes a new bug. It deserves its own change with its own multibyte test fixtures.

**Honest caveat about this change's role:** restoring the `gemini` seat **doubled the
exposure**, from one inline worker to two. It did not create the bug, but it made it
twice as likely to bite.

**Workaround until fixed:** on a CJK-heavy target, set `max_chars` to ~30,000 on the
`kimi` and `gemini` entries, or switch them to `mode: api`.

**If picked up:** give `_cap()` an optional byte budget and apply it for workers whose
`cmd` contains `{prompt}`, truncating on an encoded-length basis rather than a character
count — then test with a fixture that is genuinely multibyte, not ASCII padded to length.
