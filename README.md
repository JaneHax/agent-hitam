# agent-hitam

Hermes Agent add-ons. Copy the folder or unzip the package you need into `~/.hermes/skills/`.

## Packages

| Package | What it does |
|---------|--------------|
| [`hermes-guardrail-bypass/`](hermes-guardrail-bypass/) | Disables every non-model security scanner in Hermes (context-file scan, memory scan, cron scan, skill install guard). Version-agnostic patcher — run it after each `hermes update`. Verified on Hermes v0.21.5. |
| [`har-capture/`](har-capture/) | `harcapture` — CDP-based HAR capture for API discovery. Captures XHR, Fetch and WebSocket traffic with real payloads. Script in `scripts/har_capture.py`. |
| [`api-discovery/`](api-discovery/) | Companion skill: how to approach API discovery — source-code analysis, HAR capture, WebSocket monitoring, SPA endpoint reverse-engineering. |

Both `har-capture` and `api-discovery` are skills; read [`har.md`](har.md) for the short
version of when to use `harcapture` instead of `curl` + `grep`.

## Install

```bash
# guardrail bypass (directory)
cp -r hermes-guardrail-bypass ~/.hermes/skills/devops/
python3 ~/.hermes/skills/devops/hermes-guardrail-bypass/scripts/apply_patches.py
python3 ~/.hermes/skills/devops/hermes-guardrail-bypass/scripts/apply_patches.py --verify
hermes gateway restart

# har-capture + api-discovery (two skills)
cp -r har-capture api-discovery ~/.hermes/skills/
chmod +x ~/.hermes/skills/har-capture/scripts/har_capture.py

# optional: expose the script as a global `harcapture` command
mkdir -p ~/.hermes/node/bin
ln -sf ~/.hermes/skills/har-capture/scripts/har_capture.py ~/.hermes/node/bin/harcapture
```

`har_capture.py` needs Playwright (`pip install playwright && playwright install chromium`).

## hermes-guardrail-bypass at a glance

```bash
S=~/.hermes/skills/devops/hermes-guardrail-bypass/scripts/apply_patches.py

python3 $S            # apply (idempotent)
python3 $S --status   # report only, change nothing
python3 $S --verify   # functional check against the live install
python3 $S --revert   # restore every *.guardrail-bak
```

Targets are resolved by function name through the AST, with per-target candidate
paths, so a scanner that moved between Hermes releases still resolves. Anything
that cannot be found is reported instead of failing silently. Each rewrite is
re-parsed before it is written, and `--revert` restores the original files.

Full details, the scanner table, and the pitfalls list are in
[`hermes-guardrail-bypass/SKILL.md`](hermes-guardrail-bypass/SKILL.md).
