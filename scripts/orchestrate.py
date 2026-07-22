#!/usr/bin/env python3
"""
/cubersecurity ensemble orchestrator (reference implementation).

Fans a *static, user-owned* target out to a set of frontier models running in
parallel, each producing structured security findings, then merges them (with
per-model agreement as a confidence signal) and runs an organizer synthesis pass
to produce a prioritized, defensive review.

Scope: this operates on artifacts you provide (a repo path, a file, a diff, a
config, a manifest, an architecture description, or logs). It does NOT take a live
host as an attack target, does not scan networks, and instructs every worker to
identify/assess/remediate rather than emit weaponized output. Keep it that way.

Bring your own access: every model is driven through YOUR logged-in CLI subscription
or YOUR own API key (read from the env var named in roster.yaml). This script holds
no credentials and must not be pointed at anyone else's accounts.

Deps: PyYAML (`pip install pyyaml`); everything else is stdlib. CLI adapters shell
out to your subscription-authenticated CLIs; API adapters use an OpenAI-compatible
HTTP endpoint. See references/model-roster.md and roster.yaml.
"""

from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

HERE = Path(__file__).resolve().parent

CHARTER = textwrap.dedent("""\
    You are a defensive (blue-team) security reviewer. You are analyzing an artifact
    the operator OWNS or is AUTHORIZED to review. Your job is to IDENTIFY security
    issues, ASSESS their risk, and RECOMMEND concrete remediations. Do NOT produce
    working exploit code, malware, or a weaponized proof-of-concept; describe impact
    conceptually only. Do NOT assume or invent access to any live/remote system —
    reason only about the static artifact given to you.
""")

MODES = {
    "code_review": textwrap.dedent("""\
        MODE: Secure code review. Examine the code for: injection (SQL/command/
        template/LDAP), broken authentication/authorization (missing checks, IDOR,
        broken access control), secrets committed in code, unsafe deserialization,
        SSRF, path traversal, XXE, weak/misused cryptography, race conditions,
        insecure defaults, and logic bugs with a security impact."""),
    "infra_hardening": textwrap.dedent("""\
        MODE: Infrastructure / configuration hardening review. Compare this config
        against hardening baselines. Look for: exposed surfaces, over-broad
        permissions/roles, missing TLS or authentication, default or weak
        credentials, permissive CORS/firewall rules, poor secrets handling, and
        gaps in backups or logging."""),
    "dependency_audit": textwrap.dedent("""\
        MODE: Dependency / supply-chain audit. Examine these manifests/lockfiles
        for: known-vulnerable package versions, typosquatting, unmaintained or
        abandoned packages, risky transitive dependencies, install-time script
        risks, and license/provenance concerns."""),
    "threat_model": textwrap.dedent("""\
        MODE: Threat model. Enumerate assets, trust boundaries, and entry points.
        Walk STRIDE (Spoofing, Tampering, Repudiation, Information disclosure,
        Denial of service, Elevation of privilege) per boundary. Propose defensive
        controls and rank residual risk. Emit each threat as a finding."""),
    "incident_triage": textwrap.dedent("""\
        MODE: Incident triage (analysis & response only). Establish a timeline,
        identify indicators of compromise, scope likely impact/blast radius, and
        recommend containment, eradication, and recovery steps. Emit each
        observation/recommendation as a finding."""),
}

SCHEMA_INSTRUCTION = textwrap.dedent("""\
    Return ONLY a JSON array (no prose, no markdown fences) of findings. Each object:
      "title":       short imperative description
      "severity":    one of critical|high|medium|low|info
      "category":    e.g. sql-injection, broken-access-control, secret-in-code
      "location":    file:line, config key, component, or trust boundary
      "evidence":    the specific excerpt that shows the issue
      "impact":      what an attacker gains if unfixed (conceptual, no working PoC)
      "remediation": concrete fix, ideally a secure-by-default rewrite
      "confidence":  one of high|medium|low
    If you find nothing, return [].
""")

# ---------- target loading ----------

RELEVANT_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb",
                ".php", ".c", ".cc", ".cpp", ".h", ".sh", ".sql", ".yaml", ".yml",
                ".json", ".toml", ".tf", ".conf", ".ini", ".env", ".dockerfile",
                ".txt", ".md", ".log"}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "__pycache__"}
MAX_TARGET_CHARS = 180_000  # keep the fan-out prompt bounded


def read_target(target: str) -> str:
    p = Path(target)
    if not p.exists():
        # treat as an inline description (e.g. an architecture summary for threat_model)
        return target
    if p.is_file():
        return f"### FILE: {p}\n{_read(p)}"
    chunks, total = [], 0
    for f in sorted(p.rglob("*")):
        if f.is_dir() or any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.suffix.lower() not in RELEVANT_EXT and f.name.lower() != "dockerfile":
            continue
        body = _read(f)
        block = f"### FILE: {f.relative_to(p)}\n{body}\n"
        if total + len(block) > MAX_TARGET_CHARS:
            chunks.append(f"\n[... truncated at {MAX_TARGET_CHARS} chars; "
                          f"review the remaining files in a follow-up run ...]\n")
            break
        chunks.append(block)
        total += len(block)
    return "".join(chunks) if chunks else f"[no reviewable files found under {p}]"


def _read(f: Path) -> str:
    try:
        return f.read_text(errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"[unreadable: {e}]"


def build_prompt(mode: str, target_text: str, brief: str) -> str:
    return "\n".join([CHARTER, MODES[mode], "", brief, "",
                      "=== TARGET ===", target_text, "=== END TARGET ===",
                      "", SCHEMA_INSTRUCTION])


# ---------- model adapters ----------

def run_cli(cmd_template: str, prompt: str, timeout: int) -> str:
    # Prompt is delivered on stdin; the {prompt_file}/{prompt} tokens in the
    # roster cmd are just markers of intent and are stripped here.
    cmd = re.sub(r"\{prompt(_file)?\}", "", cmd_template).strip()
    proc = subprocess.run(cmd, shell=True, input=prompt, text=True,
                          capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"CLI exit {proc.returncode}: {proc.stderr[:400]}")
    return proc.stdout


def run_api(cfg: dict, prompt: str, timeout: int) -> str:
    # OpenAI-compatible chat/completions (works for xAI, Moonshot, OpenAI-style).
    key = os.environ.get(cfg.get("api_key_env", ""), "")
    if not key:
        raise RuntimeError(f"missing env {cfg.get('api_key_env')}")
    body = json.dumps({
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "Return only the requested JSON array."},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    req = urlrequest.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urlerror.HTTPError as e:
        raise RuntimeError(f"API {e.code}: {e.read()[:400].decode(errors='replace')}")
    return data["choices"][0]["message"]["content"]


def call_model(cfg: dict, prompt: str, timeout: int) -> str:
    if cfg.get("mode") == "api":
        return run_api(cfg, prompt, timeout)
    return run_cli(cfg["cmd"], prompt, timeout)


# ---------- findings parsing & merge ----------

def parse_findings(raw: str) -> list[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    # grab the outermost JSON array even if the model added stray prose
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _key(f: dict) -> str:
    cat = re.sub(r"\s+", "", str(f.get("category", "")).lower())
    loc = re.sub(r"\s+", "", str(f.get("location", "")).lower())
    return f"{cat}|{loc}"


def merge(by_worker: dict[str, list[dict]]) -> list[dict]:
    merged: dict[str, dict] = {}
    for worker, findings in by_worker.items():
        for f in findings:
            k = _key(f)
            if k not in merged:
                merged[k] = {**f, "agreement": set(), "severities": []}
            merged[k]["agreement"].add(worker)
            merged[k]["severities"].append(str(f.get("severity", "info")).lower())
            # keep the most detailed remediation seen
            if len(str(f.get("remediation", ""))) > len(str(merged[k].get("remediation", ""))):
                merged[k]["remediation"] = f.get("remediation", "")
    out = []
    for m in merged.values():
        sevs = m.pop("severities")
        m["agreement"] = sorted(m["agreement"])
        m["agreement_count"] = len(m["agreement"])
        m["severity"] = max(sevs, key=lambda s: SEV_RANK.get(s, 0))
        m["severity_disagreement"] = len(set(sevs)) > 1
        out.append(m)
    out.sort(key=lambda x: (-SEV_RANK.get(x["severity"], 0), -x["agreement_count"]))
    return out


# ---------- organizer passes ----------

def organizer_brief(org_cfg: dict, mode: str, target_text: str, timeout: int) -> str:
    prompt = (CHARTER + MODES[mode] +
              "\n\nPhase 1 — scoping. In <=8 bullet points, list the concrete areas a "
              "reviewer should check for THIS target. Confirm the target looks like a "
              "static, owned artifact. Output only the bullet checklist.\n\n"
              "=== TARGET (excerpt) ===\n" + target_text[:20_000])
    try:
        return "Phase-1 checklist:\n" + call_model(org_cfg, prompt, timeout).strip()
    except Exception as e:  # noqa: BLE001
        return f"(recon skipped: {e})"


def organizer_synthesis(org_cfg: dict, mode: str, brief: str,
                        merged: list[dict], failures: list[str], timeout: int) -> str:
    payload = json.dumps(merged, indent=2, default=list)[:120_000]
    prompt = (CHARTER +
              "\nPhase 4 — synthesis. Below are de-duplicated findings from an "
              "ensemble of models, each tagged with how many workers raised it "
              "(agreement_count) and whether they disagreed on severity. "
              "Resolve remaining conflicts, drop clear false positives (state a "
              "one-line reason), and write the final defensive report.\n\n"
              "Use EXACTLY this markdown structure:\n"
              "# Security review: <target> (" + mode + ")\n"
              "## Summary\n## Findings\n"
              "### [SEVERITY] <title>  (agreement: N, confidence: <level>)\n"
              "- **Where:** ...\n- **Evidence:** ...\n- **Impact:** ...\n- **Fix:** ...\n"
              "## Lower-confidence / worth a look\n## What was checked\n\n"
              f"{brief}\n\nMerged findings JSON:\n{payload}")
    try:
        report = call_model(org_cfg, prompt, timeout)
    except Exception as e:  # noqa: BLE001
        report = _fallback_report(mode, merged)  # deterministic if organizer fails
        report += f"\n\n_(organizer synthesis unavailable: {e}; showing merged findings)_"
    if failures:
        report += "\n\n## Ensemble notes\n" + "\n".join(f"- {x}" for x in failures)
    return report


def _fallback_report(mode: str, merged: list[dict]) -> str:
    lines = [f"# Security review ({mode})", "", "## Findings", ""]
    for f in merged:
        lines += [f"### [{f['severity'].upper()}] {f.get('title','(untitled)')}  "
                  f"(agreement: {f['agreement_count']}, confidence: {f.get('confidence','?')})",
                  f"- **Where:** {f.get('location','?')}",
                  f"- **Evidence:** {f.get('evidence','')}",
                  f"- **Impact:** {f.get('impact','')}",
                  f"- **Fix:** {f.get('remediation','')}", ""]
    return "\n".join(lines)


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser(description="/cubersecurity ensemble orchestrator")
    ap.add_argument("--mode", required=True, choices=list(MODES))
    ap.add_argument("--target", required=True,
                    help="repo path, file, diff, config, manifest, or inline description")
    ap.add_argument("--organizer", default=None, help="organizer key from roster.yaml")
    ap.add_argument("--workers", default=None,
                    help="comma-separated worker keys (default: roster defaults)")
    ap.add_argument("--quick", action="store_true", help="use the cheaper worker subset")
    ap.add_argument("--skip-recon", action="store_true", help="skip Phase-1 organizer pass")
    ap.add_argument("--roster", default=str(HERE / "roster.yaml"))
    ap.add_argument("--out", default="security-review.md")
    args = ap.parse_args()

    roster = yaml.safe_load(Path(args.roster).read_text())
    d = roster.get("defaults", {})
    timeout = int(d.get("timeout_seconds", 600))

    org_key = args.organizer or d.get("organizer", "opus")
    org_cfg = roster["organizers"][org_key]

    if args.workers:
        worker_keys = [w.strip() for w in args.workers.split(",")]
    else:
        worker_keys = d.get("quick_workers" if args.quick else "workers", [])
    worker_cfgs = {k: roster["workers"][k] for k in worker_keys}

    print(f"[*] mode={args.mode} organizer={org_key} workers={worker_keys}", file=sys.stderr)
    target_text = read_target(args.target)

    brief = ("Phase-1 checklist: (skipped)" if args.skip_recon
             else organizer_brief(org_cfg, args.mode, target_text, timeout))
    print("[*] phase 1 done", file=sys.stderr)

    prompt = build_prompt(args.mode, target_text, brief)
    by_worker: dict[str, list[dict]] = {}
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=int(d.get("concurrency", 5))) as ex:
        futs = {ex.submit(call_model, cfg, prompt, timeout): name
                for name, cfg in worker_cfgs.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                findings = parse_findings(fut.result())
                by_worker[name] = findings
                print(f"[+] {name}: {len(findings)} findings", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{name} failed: {e}")
                print(f"[!] {name} failed: {e}", file=sys.stderr)

    merged = merge(by_worker)
    print(f"[*] merged into {len(merged)} unique findings", file=sys.stderr)

    report = organizer_synthesis(org_cfg, args.mode, brief, merged, failures, timeout)
    Path(args.out).write_text(report)
    print(f"[✓] report written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
