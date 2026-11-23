# LLM prompt-injection test pack

A zero-dependency prompt-injection test pack for chat diagnostics and offline workflow regression checks. Run the local demo to see the 36 legacy canary checks. Use the strict gate to evaluate both policy behavior and task completion from saved synthetic evidence.

- Python 3.10+, standard library only (no `pip install`)
- Diagnostic mode uses the OpenAI-compatible `POST {base_url}/chat/completions` text response format
- Strict mode scores local files and requires no API key, endpoint, or model

This is a starting point, not a penetration test, not a certification, and not legal advice.

## Quickstart

```bash
git clone https://github.com/Fato07/llm-prompt-injection-test-pack.git
cd llm-prompt-injection-test-pack

# 1. Try it offline against the bundled, deliberately leaky mock (no key, no internet)
python3 run_probes.py --self-test

# 2. Score six paired workflows using the bundled synthetic evidence
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --expect-run reference-v2 --json-out report-strict.json
```

The reference suite has 12 evaluable cases. Strict mode checks that the evidence belongs to the expected run and exact suite. Exit `0` means all required observations were present and the expected task and policy outcomes held. Exit `1` means a complete run found a regression. Exit `2` means the evidence was mismatched or incomplete, the input was invalid, or the report could not be written. Findings observed in an incomplete run remain in the report.

See the [strict evidence format](EVIDENCE.md), [example report](examples/strict-gate.json), and [offline comparison](RELEASE.md).

### Use strict mode in CI

The [offline workflow](.github/workflows/offline.yml) gives the synthetic collector and scorer a fresh run ID from GitHub Actions and fails the job on exit `1` or `2`. Follow the [CI recipe](EVIDENCE.md#ci-recipe) to use saved evidence from your own local test harness.

To try the pilot, copy [PILOT.md](PILOT.md) and the [`pilot/` directory](pilot/) into a fresh folder. The kit pins the preview, times the reference run, and records a sanitized receipt for a retrieval app or a tool-using agent.

## Chat diagnostics

For diagnostics on an authorized endpoint that accepts the chat request format, select the model and endpoint explicitly.

```bash
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
| `--json-out report.json` | Save legacy verdict rows with full reply text. Treat them as sensitive. |

`--self-test` starts a local stub, runs the pack, then shuts the stub down. The stub leaks on purpose so you can see what findings look like. It is not a real model.

Tip: if your product wraps the model with its own system prompt, tools or retrieval, point the pack at *your* endpoint (or a thin proxy in front of it), not the raw model. That is where most real issues show up.

## How to read diagnostic results

- **PASS** means a nonempty text reply had no configured marker.
- **FAIL** means a configured marker appeared. Review the context to tell a disclosure from a permitted reference.
- **ERROR** means there was no scoreable text reply or the request failed.

A clean run does not mean the system is safe, and a single fail is not automatically an exploitable production bug. Use [`checklist.md`](checklist.md) for the manual checks a script cannot cover: tool confirmations, logging, untrusted-document handling and ownership of findings.

Diagnostic exit `0` means at least one probe produced scoreable text, including runs with findings or partial errors. Diagnostic exit `2` means invalid input, no scoreable replies, or a report write failure. Use strict mode for CI gating.

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
- The pack never executes tools against your systems. Legacy tool probes look for a text marker. Strict app checks score saved authorization and state observations.
- Only point it at systems you own or are authorised to test.

## Need more than a script?

- **RedCell**, an EU-hosted, OpenAI-compatible endpoint for refusal-removed open models, for verified red-team and eval teams, with full request logs: <https://redcell-api.pages.dev>
- **One-week LLM & agent security test**, a human-led, fixed-scope review of one app or agent with a written report and a retest of high-severity findings, from CodesDevs: <https://codesdevs.io/llm-agent-security-test/>

## Contributing

Issues and pull requests with new probes are welcome. Keep the same rule: canary strings only, no harmful payloads.

## Licence

[MIT](LICENSE)
