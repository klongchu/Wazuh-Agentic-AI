# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup

Install runtime dependencies called out in [README.md](README.md):

```bash
pip install flask flask_cors ollama openai requests
```

Create `.env` beside `app.py` with Wazuh API, indexer, and LLM provider settings. `client.py` loads this file at import time.

LLM provider is selected globally through `.env` via `AI_PROVIDER=openai|ollama`. Default provider is OpenAI; `OPENAI_API_KEY` is required unless provider is switched to Ollama.

### Run app

`app.py` is entrypoint and includes built-in process control:

```bash
python app.py run
python app.py start
python app.py stop
python app.py restart
python app.py status
```

Flags also work:

```bash
python app.py run --host 0.0.0.0 --port 5000
python app.py start --host 0.0.0.0 --port 5000
```

Background mode writes `agent.pid` and logs to `agent.log` unless `--log-file` is passed.

### Run agent loop without UI

`agent_tools.py` has standalone CLI for direct investigation runs:

```bash
python agent_tools.py "Are there any signs of compromise in the last 24 hours?"
python agent_tools.py --agent 001 "Correlate severity 12 events over last 7 days"
```

### Data-layer sanity check

`client.py` is not runnable app code; running it only prints reminder to use `app.py`.

## Architecture

Repo split into three layers. Keep boundaries intact.

### 1. Web/UI and process control — `app.py`

[app.py](app.py) owns:

- Flask app and all HTTP routes
- single-investigation locking (`State.lock`) so only one run executes at once
- SSE streaming from backend to browser via `/agent`
- scheduler thread for periodic triage via `/schedule`
- persistence of investigation history in `investigations.json` with cap of last 50 runs
- foreground/background lifecycle management (`run`, `start`, `stop`, `restart`, `status`)
- full browser UI as one large inline `HTML` string rendered by `/`

Important pattern: `_run_agentic()` is shared by interactive runs and scheduled runs. It collects live trace lines for streaming and structured audit entries for saved reports.

### 2. Agent loop and tool surface — `agent_tools.py`

[agent_tools.py](agent_tools.py) owns agent behavior:

- system prompt that defines investigation strategy, time-window defaults, and convergence rules
- tool implementations that convert model requests into Wazuh/indexer queries
- `TOOLS` registry plus JSON schemas exposed to provider tool calling
- provider adapter layer that maps shared message history to OpenAI or Ollama request shape
- `run_agent()` loop: send messages through provider adapter, execute requested tools, append tool results back into conversation, stop on final prose answer or step cap
- `STOP_FLAG` checks so UI stop button can cancel investigation cleanly between model/tool steps

Tooling split matters:

- broad alert discovery: `search_alerts`, `aggregate_alerts`, `get_active_agents`
- host drill-down: `get_agent_timeline`, `get_event_sequence`, `get_inventory`
- correlation/baseline: `find_entity_across_agents`, `get_rule_frequency`, `get_vulnerabilities`, `list_agents`

Important behavior from prompt/code:

- default investigation window is intentionally broad when user gives none
- model is pushed to investigate itself, not defer follow-up work to analyst
- hard cap from `AGENTIC_MAX_STEPS`; if reached, code forces final prose answer without tools

### 3. External integrations and config — `client.py`

[client.py](client.py) is thin data layer. Keep business judgment out of it.

It owns:

- `.env` loading at import time
- config dictionary `C`
- active provider/model helpers used by `app.py` and `agent_tools.py`
- Wazuh API auth/token refresh via `_auth()` and `wget()`
- Wazuh indexer queries via `_ix_post()`, `ix_search()`, `ix_agg()`
- raw inventory fetches via `inventory()`
- rule baseline helper `_rule_baseline_freq()`
- shared cancellation primitive `STOP_FLAG`

Design intent: `client.py` should return raw facts and transport errors; `agent_tools.py` decides meaning.

## Data flow

Normal investigation path:

1. Browser calls `/agent` in [app.py](app.py).
2. `app.py` starts thread running `_run_agentic(question, run_id, q)`.
3. `_run_agentic()` calls `agent.run_agent()` from [agent_tools.py](agent_tools.py).
4. `run_agent()` calls the configured provider (OpenAI by default, or Ollama when `AI_PROVIDER=ollama`) with tool schemas.
5. Tool implementation calls functions in [client.py](client.py) against either Wazuh server API (`:55000`) or indexer API (`:9200`).
6. Tool results stream back to UI as SSE and are also recorded into saved report audit trail.
7. Final report is stored in `investigations.json`.

## Project-specific constraints

- Repo assumes one Wazuh manager and one indexer; no cluster abstraction in code.
- Live host inventory uses Wazuh server API, while alert/timeline/correlation work mostly use indexer queries.
- Agent name/ID resolution is cached in `_agent_cache` inside [agent_tools.py](agent_tools.py).
- Frontend is not templated or componentized; changing UI means editing inline HTML/CSS/JS string in [app.py](app.py).
- History storage is file-backed JSON, not database-backed.

## What is not present

As checked in current repo state:

- no dedicated test suite
- no lint/format config
- no package manager or build system beyond direct `pip install`
- no `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md`
