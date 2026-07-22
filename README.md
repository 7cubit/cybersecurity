# /cubersecurity

**A multi-model defensive security review skill for [Claude Code](https://claude.com/claude-code).**

`/cubersecurity` turns a security question into a structured, cross-checked review.
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

- If you install this, it runs on **your** Claude / OpenAI / Google / xAI / Moonshot
  accounts — the ones you're logged into or whose keys you've set.
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

**Organizer** (one): Claude Opus 4.8 *(default)*, GPT-5.6 Terra, or Grok 4.5.

**Workers** (fan out in parallel):

| Worker | Effort | Driven via |
| --- | --- | --- |
| Claude Fable 5 | max | Claude Code / Anthropic API |
| GPT-5.6 Sol | max | Codex CLI / OpenAI API |
| Grok 4.5 | high | Grok CLI / xAI API |
| Gemini 3.1 Pro | high | Gemini CLI / Gemini API |
| Kimi K3 | max | Kimi CLI / Moonshot (OpenAI-compatible) API |

As configured, **all seven entries run via subscription CLIs — no API keys required.**
Exact model strings, per-provider invocation, and which subscription can drive which
model headlessly are documented in
[`references/model-roster.md`](references/model-roster.md). **Read that first** —
verifying access mode per model is the step most likely to trip you up.

> 📖 **Full feature reference:** [`FEATURES.md`](FEATURES.md) documents every mode,
> flag, config option, prompt-delivery method, guardrail, and extension point in
> depth. This README is the quick start; that's the manual.

## Install

Copy the folder into your Claude Code skills directory:

```bash
git clone https://github.com/7cubit/cubersecurity.git ~/.claude/skills/cubersecurity
```

Then, in Claude Code, just ask for a security review — or type `/cubersecurity`. The
skill triggers on natural phrasing too ("is this safe?", "review this for vulns",
"harden this config", "check these deps").

## Run the ensemble directly

For anything non-trivial, run the batch orchestrator:

```bash
pip install pyyaml   # only dependency; everything else is stdlib

python scripts/orchestrate.py --mode code_review --target /path/to/repo_or_diff
# modes:   code_review | infra_hardening | dependency_audit | threat_model | incident_triage
# --organizer opus|terra|grok
# --workers  fable,sol,grok,gemini,kimi   (default: all)
# --quick    use the cheaper 3-model subset
```

It reads [`scripts/roster.yaml`](scripts/roster.yaml), fans the target out
concurrently, merges the findings, runs the organizer's synthesis pass, and writes
`security-review.md`.

## 🛡️ Safety & scope

- **Blue-team only.** Identify → assess → remediate. No weaponized exploit code, no
  malware, no working proof-of-concept — impact is described conceptually.
- **Your artifacts only.** Works on static files you own or are explicitly authorized
  to review. It does **not** take live hosts/IPs as attack targets and does **not**
  scan networks.
- **No secrets in the repo.** Configuration references the *names* of environment
  variables, never their values. The `.gitignore` keeps generated reports, `.env`
  files, and caches out of version control. If you fork this, keep it that way.

## License

[MIT](LICENSE) — use it, fork it, adapt it. It's a scaffold; wire it to the models
*you* pay for.
