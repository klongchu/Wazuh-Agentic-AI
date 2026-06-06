## TEST
An LLM-driven security analyst for Wazuh. You ask a question in plain language
("correlate the severity-12 events over the last 20 days", "is data being
exfiltrated from my endpoints?"), and a local model plans its own investigation choosing which Wazuh queries to run, reading the results, and iterating until it can give a verdict. Every query it runs is logged as an
audit trail.


## Architecture

Three files, one job each:

| File | Role |
|------|------|
| `app.py` | Web UI (Flask) + process control. The only file you run. |
| `agent_tools.py` | The agentic loop and the tools the model can call. |
| `client.py` | Data layer: Wazuh API + indexer access. No logic |

The model reaches Wazuh two ways: the **Wazuh indexer API** (`:9200`, basic auth) for alerts/aggregations/timelines, and the **Wazuh server API** (`:55000`, token auth) for
live host inventory. 

## Requirements

- **Python 3.10+**
- **Ollama** running somewhere reachable, with a model pulled.
  Tool calling needs a capable model — Search at [Ollama](https://ollama.com/search)
  Small models (3B-4B) will not call tools reliably.
- A **Wazuh** deployment (manager + indexer) you can reach over the network.

## Setup

### 1. Install dependencies

```bash
pip install flask flask_cors ollama requests
```

### 2. Create a `.env` file

Place a `.env` in the same directory as `app.py`.

```ini
# -- Wazuh API (token auth, port 55000) --
WAZUH_HOST=https://<WAZUH_SERVER_IP>:55000
WAZUH_USER=your_api_user
WAZUH_PASS=your_api_password
WAZUH_SSL=false       # true only if you verify TLS certs

# -- Wazuh Indexer (basic auth, port 9200) --
INDEXER_HOST=https://<WAZUH_INDEXER_IP>:9200
INDEXER_USER=admin
INDEXER_PASS=your_indexer_password

# -- Ollama (the LLM backend) --
OLLAMA_HOST=http://127.0.0.1:11434   # where Ollama listens
OLLAMA_MODEL=qwen3      # the tool-calling model to use

# -- Optional tuning --
AGENTIC_MAX_STEPS=18            # max tool calls per investigation
UI_HOST=0.0.0.0                 # interface the web UI binds to
UI_PORT=5000                    # web UI port
```

Notes:

- If Ollama runs on a different machine (e.g. a GPU host), make sure it listens on the network (`OLLAMA_HOST=0.0.0.0:11434` on that host) and the port is open.


## Running

`app.py` has built-in process control - no `nohup`, no PID hunting.

```bash
python3 app.py start      # launch in the background (writes agent.pid + agent.log)
python3 app.py status     # is it running? on which port?
python3 app.py stop       # stop the background process cleanly
python3 app.py restart    # stop + start
python3 app.py run        # run in the FOREGROUND (Ctrl+C to quit; use for systemd)
```

Both spellings work: `python3 app.py stop` and `python3 app.py --stop`.

Then open the UI:

```
http://<host>:5000
```

### Using it

- **Run tab** - type a question, click **Run now**, confirm, and watch the
  agent investigate live (its tool calls, reasoning, and final verdict stream
  in). Click **Stop** to cancel a running investigation.
- **Reports tab** - every completed investigation is saved with its verdict and
  full tool-call audit trail. Reports render as formatted markdown.
- **Auto-run** - toggle the scheduler to fire a triage automatically every N
  hours over the last M hours of events.

## Areas for improvement

If you want to extend this, good directions:

- **More tools.** A `get_alert_detail` (pull one full event with every field),
  a `compare_time_windows` (this week vs. baseline), or an active-response hook
  (isolate a host) would extend what the agent can do.
- **Model selection in the UI.** Let the analyst pick the model per run instead
  of editing `.env`.
- **Surface the audit trail as a collapsible panel** in the live view, rather
  than only appending it to the saved report.
- **Persisted, searchable history.** History is currently a JSON file capped at
  50 runs; a small database would scale better and allow search.
- **Tighter convergence / cost control.** Larger models explore widely; a
  per-run tool-call budget surfaced in the UI, or a "quick vs. thorough" mode,
  would give users control over time/cost.
- **Multi-node / multi-tenant Wazuh.** The data layer assumes one manager and
  one indexer; supporting clusters would broaden its reach.
