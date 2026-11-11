# /cybersecurity

**A multi-model defensive security review skill for [Claude Code](https://claude.com/claude-code).**

`/cybersecurity` turns a security question into a structured, cross-checked review.
It fans one target (a repo, diff, config, dependency manifest, architecture doc, or
log) out to several frontier models **in parallel**, has each one analyze it
independently, then merges and reconciles their findings into a single prioritized
report — using how many models agreed on each issue as a built-in confidence signal.

No single model catches everything. They have different training, different blind
spots, and different false-positive habits. Running them as an ensemble and taking
the union of high-confidence findings catches more real issues, and their
*disagreements* surface exactly the ambiguous cases a human should look at.

It is deliberately a **blue-team** tool: it identifies, assesses, and remediates. It
does **not** produce exploit code, and it does **not** attack live systems.

---

## 🔑 Bring your own access — this repo never uses anyone else's

**Important:** this skill contains **no API keys and no credentials.** Every model it
drives authenticates against **your own** logged-in CLI subscription or **your own**
API key, read from an environment variable *on your machine*.

- If you install this, it runs on **your** Claude / Codex / xAI / Moonshot accounts —
  the ones you're logged into or whose keys you've set.
- It will **not** call, borrow, or bill anyone else's accounts, and you must not
  configure it to.
- Don't have a subscription for one of the models? Just delete it from the worker
  list in [`scripts/roster.yaml`](scripts/roster.yaml). The ensemble degrades
  gracefully to whatever you actually have — two good models still beat one.

Nothing sensitive should ever end up in this repo; see the `.gitignore` and the
"Safety" section below.

---

## What it reviews (pick a mode)

| Mode | Give it | It looks for |
| --- | --- | --- |
| `code_review` | a repo, file set, PR, or diff | injection, broken auth/access control, secrets in code, SSRF, path traversal, unsafe deserialization, weak crypto, logic bugs |
| `infra_hardening` | IaC / config (Docker, Compose, NGINX, Caddy, systemd, Postgres, cloud/DNS) | exposed surfaces, over-broad roles, missing TLS/authn, default creds, permissive CORS/firewall, secrets & logging gaps |
| `dependency_audit` | manifests / lockfiles | known-vulnerable versions, typosquats, abandoned packages, risky transitive deps, install-time script risk |
| `threat_model` | an architecture / design description | assets, trust boundaries, and a STRIDE walk per boundary, with ranked residual risk |
| `incident_triage` | logs or an incident description | timeline, indicators of compromise, blast radius, and containment/eradication/recovery steps |

## How it works — four phases

1. **Scope & recon** — an *organizer* model reads the target, confirms it's a static
   artifact you own, and writes a short checklist so every model reviews comparably.
2. **Independent parallel analysis** — the same brief goes to every *worker* model at
   once. Each returns findings as JSON. They never see each other's output —
   independence is the whole point.
3. **Cross-check & merge** — duplicate findings are collapsed; each surviving one is
   tagged with how many models raised it (`agreement`).
4. **Synthesis & decision** — the organizer resolves conflicts, drops clear false
   positives (with a reason), and writes the final prioritized report.

## The roster

Live-verified **2026-11-11** against a real target (this repo's own orchestrator).

**Organizer** (one): Claude Opus 5.5 *(default)*, gpt-6-luna, Grok 4.7, or — opt-in —
Claude Fable 5.2.

**Workers** (fan out in parallel — up to six models across five families):

| Worker (key) | Model id | Effort | Weight | Driven via |
| --- | --- | --- | --- | --- |
| Claude Opus 5.5 (`opus`) | `claude-opus-5-5` | high (`xhigh` to escalate) | 1.3 | Claude Code / Anthropic API |
| Claude Sonnet 5.5 (`sonnet`) | `claude-sonnet-5-5` | high | 1.0 | Claude Code / Anthropic API |
| gpt-6-luna (`codex`) | `gpt-6-luna` | high | 1.1 | `codex exec` (ChatGPT subscription) |
| Grok 4.7 (`grok`) | `grok-4.7` | low (high overruns the time limit) | 1.0 | Grok CLI / xAI API |
| Gemini 4 Carbon (`gemini`) | `gemini-4-carbon-high` | high | 1.0 | Antigravity (AGY) CLI / Gemini API |
| Kimi K3 (`kimi`) — *optional* | `kimi-code/k3` | CLI default | 0.9 | Kimi CLI / Moonshot (OpenAI-compatible) API |

As configured, **every entry runs via a subscription CLI — no API keys required.**
Exact model strings, per-provider invocation, and which subscription can drive which
model headlessly are documented in
[`references/model-roster.md`](references/model-roster.md). **Read that first** —
verifying access mode per model is the step most likely to trip you up.

**Optional seats.** A worker marked `optional: true` carries a `probe` command. If the
probe succeeds the seat joins; if not it is *skipped* — not sent the target, not counted,
and listed in the report as "skipped (optional, unavailable)" rather than as a failure.
Kimi is set up this way, so a lapsed subscription costs nothing and a renewed one is
picked up automatically.

**Opt-in seats** (defined, but not on the default panel — name them with `--workers`):
**Claude Fable 5.2** (`fable`) — it works, but costs about twice Opus 5.5 and its safety
measures can decline security work with a *successful but empty* response; **Gemini 4
Argon** (`gemini_argon`) and **Gemini 3.8 Flash** (`gemini_flash`, used by `--quick`) —
same family as the default Gemini seat, so only one Google model sits on the panel.

**Gemini is back (2026-11-11).** It was disabled in September for hard-blocking real
targets. All three current Gemini models returned parseable findings on a real
~43,000-char target; the earlier blocks were on larger (71,000–90,000-char) targets, so
treat that as proof at the size the seat is actually sent, not as a guarantee. If a
block returns, the engine reports the seat as failed — drop it, never reword the prompt.

**Model ids go stale.** The OpenAI seat was silently dead before this refresh because
the ChatGPT plan had stopped serving `gpt-6-astra`. If a seat fails with "model not
supported", check what your CLI lists now and update `scripts/roster.yaml`.

**Jev second opinion (optional, outside the engine).** If the Claude running the skill
has the Jev judging tools (`mcp__jev__*`), it labels each merged finding *verified /
contradicted / unsupported* after the report is written. Jev only labels — it never
drops or approves a finding, it is not a panel seat, and this repo stores no Jev key or
configuration. See `SKILL.md`.

> 📖 **Full feature reference:** [`FEATURES.md`](FEATURES.md) documents every mode,
> flag, config option, prompt-delivery method, guardrail, and extension point in
> depth. This README is the quick start; that's the manual.

## Install

Copy the folder into your Claude Code skills directory:

```bash
git clone https://github.com/7cubit/cybersecurity.git ~/.claude/skills/cybersecurity
```

Then, in Claude Code, just ask for a security review — or type `/cybersecurity`. The
skill triggers on natural phrasing too ("is this safe?", "review this for vulns",
"harden this config", "check these deps").

## Run the ensemble directly

For anything non-trivial, run the batch orchestrator:

```bash
pip install pyyaml   # only dependency; everything else is stdlib

python scripts/orchestrate.py --mode code_review --target /path/to/repo_or_diff
# modes:   code_review | infra_hardening | dependency_audit | threat_model | incident_triage
# --organizer opus|codex|grok|fable
# --workers  opus,sonnet,codex,grok,gemini,kimi   (default; kimi is optional — skipped if unavailable)
#            opt-in seats: fable, gemini_argon, gemini_flash
# --quick    cheaper 3-model subset (sonnet,grok,gemini_flash)
# --dry-run  print exactly what would be sent to which providers, then exit
# --sarif PATH  also write findings as SARIF 2.1.0 for CI code scanning
# --secret-scanner regex|gitleaks|trufflehog   extra redaction pass (regex is the default)
# --max-chars N  override the default per-model input cap

# piping works too — this reviews your actual diff:
git diff main | python scripts/orchestrate.py --mode code_review --target /dev/stdin --quick
```

It reads [`scripts/roster.yaml`](scripts/roster.yaml), fans the target out
concurrently, merges the findings, runs the organizer's synthesis pass, and writes
`security-review.md`. It can also emit SARIF for CI code scanning (`--sarif`), and
`--dry-run` previews the whole transmit manifest before anything leaves your machine.

## 🛡️ Safety & scope

- **Blue-team only.** Identify → assess → remediate. No weaponized exploit code, no
  malware, no working proof-of-concept — impact is described conceptually.
- **Your artifacts only.** Works on static files you own or are explicitly authorized
  to review. It does **not** take live hosts/IPs as attack targets and does **not**
  scan networks.
- **No secrets in the repo.** Configuration references the *names* of environment
  variables, never their values. The `.gitignore` keeps generated reports, `.env`
  files, and caches out of version control. If you fork this, keep it that way.
- **Preview before you send.** `--dry-run` prints exactly what would be sent to which
  providers — bytes, per-model caps, and redaction counts — before anything leaves
  your machine. `--secret-scanner gitleaks|trufflehog` adds a second redaction pass
  on top of the built-in regex one when those tools are installed.

## License

[MIT](LICENSE) — use it, fork it, adapt it. It's a scaffold; wire it to the models
*you* pay for.
