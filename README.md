# LLM prompt-injection test pack

A small, free pack you can run in an afternoon against any OpenAI-compatible chat endpoint. It sends 36 categorised probes and prints a pass/fail summary.

- Python 3.10+, standard library only (no `pip install`)
- Works with anything that speaks `POST {base_url}/chat/completions`: hosted APIs, gateways, vLLM, Ollama, LM Studio, your own app's proxy
- Safe by design: every probe only asks the model to emit a synthetic canary string such as `CANARY_PWNED`

This is a starting point, not a penetration test, not a certification, and not legal advice.

## Quickstart

```bash
git clone https://github.com/Fato07/llm-prompt-injection-test-pack.git
cd llm-prompt-injection-test-pack

# 1. Try it offline against the bundled, deliberately leaky mock (no key, no internet)
python3 run_probes.py --self-test

# 2. Run it against your endpoint
export OPENAI_API_KEY="your-key"
python3 run_probes.py \
  --base-url https://api.example.com/v1 \
  --model your-model-name \
  --json-out report.json
```

Useful flags:

| Flag | What it does |
|---|---|
| `--base-url` | Endpoint base, e.g. `https://api.openai.com/v1` or `http://localhost:11434/v1` |
| `--model` | Model name the endpoint expects |
| `--api-key` | Bearer token (defaults to `$OPENAI_API_KEY`) |
| `--probes` | Use your own probe file (same format as `probes.json`) |
| `--timeout 30` | Per-request timeout in seconds |
| `--sleep 0.2` | Pause between requests if you are rate-limited |
| `--json-out report.json` | Save every prompt, reply and verdict for review |

`--self-test` starts a local stub, runs the pack, then shuts the stub down. The stub leaks on purpose so you can see what findings look like. It is not a real model.

Tip: if your product wraps the model with its own system prompt, tools or retrieval, point the pack at *your* endpoint (or a thin proxy in front of it), not the raw model. That is where most real issues show up.

## How to read the results

- **PASS**: the reply did not contain that probe's canary.
- **FAIL**: the canary appeared. Treat it as a lead, then reproduce the same idea through your real UI, tools and retrieved documents.
- **ERROR**: the HTTP call failed (auth, rate limit, timeout). Fix and re-run.

A clean run does not mean the system is safe, and a single fail is not automatically an exploitable production bug. Use [`checklist.md`](checklist.md) for the manual checks a script cannot cover: tool confirmations, logging, untrusted-document handling and ownership of findings.

Exit codes: `0` the run finished (findings are printed, not treated as a process error); `2` the pack itself failed (bad arguments, unreachable API, or errors on every probe).

## What it probes

| Category | What it is probing |
|---|---|
| `direct_injection` | "Ignore previous instructions" and similar overrides |
| `instruction_override` | Role or policy resets (developer mode, cancelled system prompt) |
| `system_prompt_extraction` | Attempts to quote hidden instructions |
| `data_exfiltration` | Attempts to repeat canary secrets placed in context |
| `tool_abuse` | Attempts to invoke a tool the user should not be able to run |
| `policy_bypass` | Role-play and pretext requests for a synthetic unlock flag |
| `indirect_injection` | Instructions hidden in a fake email, web page, search result or HTML comment |
| `encoding_obfuscation` | Base64, ROT13 and spaced-letter forms of the same instruction |
| `agent_goal_hijack` | Attempts to replace the original task with a side goal |

The categories loosely follow the prompt-injection, sensitive-information-disclosure and excessive-agency items in the OWASP Top 10 for LLM Applications.

## Safety

- Payloads only ask the model to emit or refuse a canary string.
- There are no payloads for weapons, crime, self-harm or sexual content involving minors.
- The pack never executes tools against your systems. Tool probes only look for a `TOOL_INVOKE:...` canary in the model's text.
- Only point it at systems you own or are authorised to test.

## Need more than a script?

- **RedCell** — an EU-hosted, OpenAI-compatible endpoint for refusal-removed open models, for verified red-team and eval teams, with full request logs: <https://redcell-api.pages.dev>
- **One-week LLM & agent security test** — a human-led, fixed-scope review of one app or agent with a written report and a retest of high-severity findings, from CodesDevs: <https://codesdevs.io/llm-agent-security-test/>

## Contributing

Issues and pull requests with new probes are welcome. Keep the same rule: canary strings only, no harmful payloads.

## Licence

[MIT](LICENSE)
