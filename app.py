import os, sys, json, queue, threading, time, logging, argparse
from datetime import datetime
from pathlib import Path
from collections import OrderedDict
from flask import Flask, Response, request, render_template_string, jsonify
from flask_cors import CORS

# ── Bootstrap ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import client as ag        # owns .env loading + config dict C
import agent_tools as agent   # the agentic tool-calling loop

app  = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("app")

AI_PROVIDER   = ag.C["AI_PROVIDER"]
AGENTIC_MODEL = ag.active_model()
MODEL_LABEL   = ag.provider_label()
UI_PORT       = ag.C["UI_PORT"]
UI_HOST       = ag.C["UI_HOST"]


# ── Shared state ──────────────────────────────────────────────────────────────
class State:
    def __init__(self):
        self.lock       = threading.Lock()   # one investigation at a time
        self.log_file   = ""
        self.sched_cfg  = {"enabled": False, "interval_minutes": 5, "hours": 4}
        self.sched_wake = threading.Event()
        self.history    = OrderedDict()
        self.hist_lock  = threading.Lock()
        self.hist_file  = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "investigations.json")
        self._load_history()

    def _load_history(self):
        try:
            if Path(self.hist_file).exists():
                for item in json.loads(Path(self.hist_file).read_text()):
                    self.history[item["id"]] = item
                log.info("Loaded %d investigations from history", len(self.history))
        except Exception as e:
            log.warning("Could not load history: %s", e)

    def _save_history(self):
        try:
            items = list(self.history.values())[-50:]   # keep last 50
            Path(self.hist_file).write_text(json.dumps(items, indent=2))
        except Exception as e:
            log.warning("Could not save history: %s", e)

ST = State()


# ──────────────────────────────────────────────────────────────────────────────
#  THE AGENTIC RUN  (shared by /agent and the scheduler)
# ──────────────────────────────────────────────────────────────────────────────
def _run_agentic(question, run_id, q=None):
    """
    Execute one agentic investigation. Streams events into queue `q` (if given)
    as SSE-ready text, and saves the final answer + audit trail to history.
    """
    ag.STOP_FLAG.clear()
    trace_lines = []     # human-readable trace for the live panel
    audit       = []     # structured tool-call record for the report

    def emit(kind, payload):
        # Build a readable line per event kind, push to the live queue.
        line = ""
        if kind == "thinking":
            line = f"\n[thinking] {payload}\n"
        elif kind == "tool_call":
            line = f"\n→ {payload['name']}({json.dumps(payload['args'])})\n"
            audit.append({"tool": payload["name"], "args": payload["args"],
                          "ts": datetime.now().isoformat()})
        elif kind == "tool_result":
            preview = json.dumps(payload["result"])
            if len(preview) > 600:
                preview = preview[:600] + "…"
            line = f"  ← {preview}\n"
        elif kind == "answer":
            line = f"\n\n{'='*60}\nFINAL ASSESSMENT\n{'='*60}\n{payload}\n"
        elif kind == "error":
            line = f"\n[error] {payload}\n"
        if line:
            trace_lines.append(line)
            if q is not None:
                q.put(line)

    final = ""
    try:
        final = agent.run_agent(question, emit=emit)
    except Exception as e:
        log.exception("Agentic run failed")
        if q is not None:
            q.put(f"\n[error] {e}\n")
        final = f"[error: {e}]"

    # Compose the saved report: the verdict, then the audit trail.
    audit_text = "\n".join(
        f"{i+1}. {a['tool']}({json.dumps(a['args'])})" for i, a in enumerate(audit)
    ) or "(no tool calls recorded)"
    report = (f"QUESTION: {question}\n\n{final}\n\n"
              f"{'─'*50}\nTOOL-CALL AUDIT TRAIL ({len(audit)} calls)\n{'─'*50}\n"
              f"{audit_text}")

    with ST.hist_lock:
        if run_id in ST.history:
            ST.history[run_id]["status"] = ("stopped" if ag.STOP_FLAG.is_set()
                                            else "completed")
            ST.history[run_id]["report"] = report
            ST.history[run_id]["ended"]  = datetime.now().strftime("%H:%M")
        while len(ST.history) > 50:
            ST.history.popitem(last=False)
        ST._save_history()

    if q is not None:
        q.put("__DONE__")
    return report


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/agent")
def agent_stream():
    """SSE endpoint: run an agentic investigation, stream the live trace."""
    question = (request.args.get("q") or "").strip()
    if not question:
        def bad():
            yield "data: [No question provided.]\n\n"
            yield "data: __DONE__\n\n"
        return Response(bad(), mimetype="text/event-stream")

    if not ST.lock.acquire(blocking=False):
        def busy():
            yield "data: [An investigation is already running. Wait for it to finish.]\n\n"
            yield "data: __DONE__\n\n"
        return Response(busy(), mimetype="text/event-stream")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    with ST.hist_lock:
        ST.history[run_id] = {
            "id": run_id, "label": question[:70],
            "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ended": None, "status": "running", "report": "",
        }

    q = queue.Queue()
    threading.Thread(target=_run_agentic, args=(question, run_id, q),
                     daemon=True).start()

    def generate():
        try:
            # Send the run_id first so the client can link to the report.
            yield f"data: __RUNID__{run_id}\n\n"
            while True:
                try:
                    chunk = q.get(timeout=30)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                if chunk == "__DONE__":
                    yield "data: __DONE__\n\n"
                    break
                for line in chunk.splitlines(keepends=True):
                    yield f"data: {line}\n\n"
        finally:
            ST.lock.release()

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/stop", methods=["POST"])
def stop():
    ag.STOP_FLAG.set()
    return {"ok": True}


@app.route("/history")
def history():
    with ST.hist_lock:
        items = [{"id": v["id"], "label": v["label"], "started": v["started"],
                  "ended": v["ended"], "status": v["status"],
                  "report": v.get("report", "")}
                 for v in reversed(list(ST.history.values()))]
    return jsonify(items)


@app.route("/history/<run_id>", methods=["GET"])
def get_report(run_id):
    with ST.hist_lock:
        item = ST.history.get(run_id)
    return (jsonify(item) if item else (jsonify({"error": "not found"}), 404))


@app.route("/history/<run_id>", methods=["DELETE"])
def delete_report(run_id):
    with ST.hist_lock:
        if run_id not in ST.history:
            return jsonify({"error": "not found"}), 404
        del ST.history[run_id]
        ST._save_history()
    return jsonify({"ok": True})


@app.route("/schedule", methods=["POST"])
def set_schedule():
    ST.sched_cfg.update(request.get_json() or {})
    ST.sched_wake.set()
    return jsonify(ST.sched_cfg)


@app.route("/status")
def status():
    return jsonify({
        "running": ST.lock.locked(),
        "provider": AI_PROVIDER,
        "model": AGENTIC_MODEL,
        "label": MODEL_LABEL,
        "schedule": ST.sched_cfg,
    })


# ── Scheduler ─────────────────────────────────────────────────────────────────
def _scheduler():
    """Fires an agentic triage on a timer: 'perform alert triage on the last N hours'."""
    while True:
        cfg = ST.sched_cfg
        if not cfg["enabled"]:
            ST.sched_wake.wait(60); ST.sched_wake.clear(); continue
        last = getattr(ST, "_last_sched", 0)
        wait = max(0, last + cfg["interval_minutes"]*60 - time.time())
        if wait > 0:
            ST.sched_wake.wait(wait); ST.sched_wake.clear(); continue
        if ST.lock.acquire(blocking=False):
            run_id   = "sched_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            hours    = cfg.get("hours", 24)
            question = f"perform alert triage on the last {hours} hours"
            with ST.hist_lock:
                ST.history[run_id] = {
                    "id": run_id, "label": f"Scheduled — {question}",
                    "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "ended": None, "status": "running", "report": "",
                }
            try:
                _run_agentic(question, run_id, q=None)
            finally:
                ST.lock.release()
                ST._last_sched = time.time()


# ── Page ──────────────────────────────────────────────────────────────────────
HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Agentic Security Analyst</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0d1117;--panel:#111827;--panel2:#161b22;--line:#263041;--line2:#30363d;--text:#e6edf3;--muted:#8b949e;--blue:#58a6ff;--green:#3fb950;--orange:#f0883e;--red:#f85149}
body{font-family:Inter,Segoe UI,system-ui,sans-serif;background:radial-gradient(circle at top,#111827 0,#0d1117 45%);color:var(--text);min-height:100vh;height:100vh;display:flex;flex-direction:column;overflow:hidden}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--line2);background:rgba(13,17,23,.92);backdrop-filter:blur(12px);flex:0 0 auto}
.brand-title{font-weight:700;letter-spacing:.02em}.brand-sub{font-size:12px;color:var(--muted);margin-top:2px}
.topbar-badges{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.badge{font-size:11px;padding:4px 10px;border-radius:999px;background:#1f2937;border:1px solid var(--line2);color:var(--text)}
.badge.state-idle{color:#c9d1d9}.badge.state-running{color:var(--green)}.badge.state-stopped{color:var(--orange)}.badge.state-error{color:var(--red)}
.icon-btn{background:#1f2937;border:1px solid var(--line2);color:var(--text);border-radius:10px;padding:7px 11px;cursor:pointer}
.icon-btn:hover{border-color:var(--blue)}
.shell{display:grid;grid-template-columns:300px minmax(0,1fr);gap:14px;min-height:0;min-width:0;flex:1 1 auto;height:calc(100vh - 73px);padding:14px;transition:grid-template-columns .2s ease;overflow:hidden}
.shell.sidebar-collapsed{grid-template-columns:84px minmax(0,1fr)}
.history-sidebar,.console-pane{min-height:0;min-width:0;background:rgba(17,24,39,.84);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.22)}
.console-pane{display:flex;flex-direction:column;min-height:0}
.history-sidebar{display:flex;flex-direction:column;min-height:0}
.hist-list{overflow:auto;max-height:none;min-height:0;flex:1 1 auto;padding:10px}
.live-wrap{display:flex;flex-direction:column;min-height:0;flex:1 1 auto}
.report-shell{border-top:1px solid var(--line2);display:flex;flex-direction:column;min-height:0;flex:1 1 42%;background:#0b1220;overflow:hidden}
#report-out{flex:1 1 auto;min-height:0;overflow:auto}
#live-out{flex:1 1 auto;min-height:0;overflow:auto;font-size:13px}
#live-out,#report-out{padding:14px;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.sidebar-head{display:flex;justify-content:space-between;align-items:center;padding:14px 14px 10px;border-bottom:1px solid var(--line2)}
.sidebar-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.hi{padding:10px 10px;border:1px solid transparent;border-radius:12px;cursor:pointer;margin-bottom:8px;background:rgba(255,255,255,.02)}
.hi:hover{border-color:#2b3b52;background:#172131}.hi.active{border-color:#1f6feb;background:#13263f}
.hl{font-size:12px;line-height:1.35;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hm{margin-top:4px;font-size:10px;color:var(--muted);display:flex;gap:6px;align-items:center;flex-wrap:wrap}.ds{width:7px;height:7px;border-radius:50%}.ds.running{background:var(--green);animation:blink 1.2s infinite}.ds.completed{background:var(--green)}.ds.stopped{background:var(--orange)}.ds.error{background:var(--red)}
.hbtn{margin-left:auto;font-size:10px;padding:2px 7px;background:#1f2937;color:var(--text);border:1px solid var(--line2);border-radius:8px;cursor:pointer}
.hbtn:hover{border-color:var(--blue)}
.controls{padding:14px;border-bottom:1px solid var(--line2);background:linear-gradient(180deg,rgba(255,255,255,.02),transparent)}
.prompt-row{display:flex;gap:10px;align-items:stretch}
#nl-input{flex:1;min-width:0;background:#0b1220;border:1px solid #2d3b50;border-radius:14px;color:var(--text);font-size:14px;padding:14px 16px;font-family:inherit}
#nl-input:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px rgba(88,166,255,.12)}
#nl-input::placeholder{color:#667085}
.filter-row{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.btn-primary,.btn-stop{border:none;border-radius:14px;padding:0 18px;font-weight:600;cursor:pointer;min-width:108px}
.btn-primary{background:linear-gradient(180deg,#2f81f7,#1f6feb);color:#fff;display:inline-flex;align-items:center;justify-content:center;gap:8px}.btn-primary:hover:not(:disabled){filter:brightness(1.05)}.btn-primary:disabled{opacity:.68;cursor:not-allowed}.btn-primary.loading::before{content:"";width:13px;height:13px;border:2px solid rgba(255,255,255,.38);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite}
.btn-stop{background:#da3633;color:#fff}.btn-stop:hover:not(:disabled){filter:brightness(1.05)}
.preview{display:none;margin-top:12px;padding:12px 14px;border:1px solid var(--line2);border-radius:14px;background:#0b1220}
.preview .confirm-q{color:var(--text);font-size:14px;margin-bottom:6px}.preview .confirm-note{color:var(--muted);font-size:12px;margin-bottom:10px}.confirm-yes,.confirm-no{padding:8px 14px;border-radius:10px;font-size:12px}.confirm-yes{background:#238636;color:#fff;border:none}.confirm-no{background:#1f2937;color:var(--text);border:1px solid var(--line2);margin-left:8px}
.toolbar{display:flex;gap:8px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line2);font-size:12px;color:var(--muted)}
.toggle-pill{padding:4px 10px;border-radius:999px;background:#172131;color:#cbd5e1}
.live-header{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid var(--line2)}
.live-dot{width:8px;height:8px;border-radius:50%;background:#667085}.live-dot.running{background:var(--green);animation:blink 1.2s infinite}.live-dot.error{background:var(--red)}
.live-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.elapsed{font-size:11px;color:#667085}
.stream-row{padding:10px 12px;border:1px solid transparent;border-radius:14px;margin-bottom:10px;background:rgba(255,255,255,.02)}.event-thinking{color:#aeb8c6;background:#0f172a;border-color:#243044}.event-tool_call{border-color:#284c7a;background:#0b1220}.event-tool_result{border-color:#30363d;background:#111827}.event-answer{border-color:#2d4a33;background:#0f1b13;color:#dff7e3;font-weight:500}.event-error{border-color:#5a1d1d;background:#220f12;color:#ffd6d6}
.status-bar{padding:10px 14px;border-top:1px solid var(--line2);display:flex;gap:8px;align-items:center;font-size:11px;color:var(--muted)}
.report-head{padding:10px 14px;border-bottom:1px solid var(--line2);display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px}
#report-out .md-h{font-weight:700;color:var(--text);margin:14px 0 6px}.md-h1{font-size:18px}.md-h2{font-size:15px;color:var(--blue)}.md-h3{font-size:14px;color:#79c0ff}.md-h4{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
#report-out .md-p{margin:4px 0;color:#c9d1d9}#report-out .md-ul,#report-out .md-ol{margin:4px 0 8px 4px;padding-left:22px;color:#c9d1d9}#report-out .md-ul li,#report-out .md-ol li{margin:3px 0}#report-out .md-sp{height:8px}#report-out .md-hr{border:none;border-top:1px solid var(--line2);margin:14px 0}#report-out code{background:#111827;border:1px solid var(--line2);border-radius:6px;padding:1px 5px;font-size:12px;color:#79c0ff}#report-out strong{color:#fff}#report-out em{color:#d2a8ff;font-style:italic}#report-out .md-pre{background:#111827;border:1px solid var(--line2);border-radius:14px;padding:10px 12px;overflow-x:auto;font-size:12px;color:#c9d1d9;margin:8px 0;white-space:pre}
.empty-state{padding:18px;color:var(--muted)}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes spin{to{transform:rotate(360deg)}}
@media (max-width: 1100px){.shell{grid-template-columns:1fr}.history-sidebar{order:2}.console-pane{order:1}.hist-list{max-height:240px}.shell.sidebar-collapsed{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">
    <div class="brand-title">Wazuh Agentic Security Analyst</div>
    <div class="brand-sub">SOC Live Console</div>
  </div>
  <div class="topbar-badges">
    <span class="badge" id="model-badge">{{ model }}</span>
    <span class="badge state-idle" id="status-badge">idle</span>
    <button class="icon-btn" id="sidebar-toggle" onclick="toggleSidebar()">Sidebar</button>
  </div>
</header>
<main class="shell" id="shell">
  <aside class="history-sidebar" id="history-sidebar">
    <div class="sidebar-head"><div class="sidebar-title">Investigation history</div><span class="badge" id="history-count">0</span></div>
    <div class="hist-list" id="hist-list"><div class="empty-state">No investigations yet.</div></div>
  </aside>
  <section class="console-pane">
    <div class="controls">
      <div class="prompt-row">
        <input id="nl-input" type="text" autocomplete="off" spellcheck="false" value="ช่วยวิเคราะห์ alert severity 12 ขึ้นไป ในช่วง 4 ชั่วโมงล่าสุด" placeholder="พิมพ์คำถามด้านความปลอดภัยเป็นภาษาไทย" onkeydown="if(event.key==='Enter')askConfirm()">
        <button class="btn-primary" id="run-btn" onclick="askConfirm()">Run now</button>
        <button class="btn-stop" id="stop-btn" onclick="stopRun()" disabled>Stop</button>
      </div>
      <div class="filter-row">
        <span class="toggle-pill">Filter</span>
        <span>Hours</span>
        <input type="number" id="run-hours" value="4" min="1" max="720" style="width:70px;background:#0b1220;border:1px solid var(--line2);border-radius:10px;color:var(--text);padding:6px 8px">
        <span>Level</span>
        <input type="number" id="run-level" value="12" min="0" max="15" style="width:70px;background:#0b1220;border:1px solid var(--line2);border-radius:10px;color:var(--text);padding:6px 8px">
      </div>
      <div class="preview" id="nl-preview"></div>
    </div>
    <div class="toolbar">
      <span class="toggle-pill">วิเคราะห์อัตโนมัติ</span>
      <label class="toggle-pill"><input type="checkbox" id="sched-on" onchange="updateSched()" style="margin-right:6px">วิเคราะห์อัตโนมัติ</label>
      <span>ทุก</span>
      <input type="number" id="sched-minutes" value="5" min="1" max="1440" onchange="updateSched()" style="width:70px;background:#0b1220;border:1px solid var(--line2);border-radius:10px;color:var(--text);padding:6px 8px">
      <span>นาที</span>
      <span>ย้อนหลัง</span>
      <input type="number" id="sched-window" value="4" min="1" max="336" onchange="updateSched()" style="width:70px;background:#0b1220;border:1px solid var(--line2);border-radius:10px;color:var(--text);padding:6px 8px">
      <span>ชั่วโมง</span>
      <span class="toggle-pill" id="sched-status">ปิด</span>
    </div>
    <div class="live-wrap">
      <div class="live-header"><div class="live-dot" id="dot"></div><span class="live-title" id="live-title">Output</span><span class="elapsed" id="elapsed"></span><button id="copy-live-btn" onclick="copyLive()" style="margin-left:auto;font-size:11px;padding:6px 10px;background:#1f2937;color:#c9d1d9;border:1px solid var(--line2);border-radius:10px;cursor:pointer">Copy</button></div>
      <div id="live-out">พร้อมใช้งาน แก้ prompt ภาษาไทยด้านบน แล้วกด Run now ได้เลย</div>
      <div class="status-bar"><span id="status-text">idle</span><span style="margin-left:auto" id="last-run"></span></div>
    </div>
    <div class="report-shell">
      <div class="report-head"><span id="report-header-text">Select an investigation from sidebar</span><button id="copy-btn" onclick="copyReport()" style="margin-left:auto;font-size:11px;padding:6px 10px;background:#1f2937;color:#c9d1d9;border:1px solid var(--line2);border-radius:10px;cursor:pointer;display:none">Copy</button></div>
      <div id="report-out"><div class="empty-state">Report appears here when you select run.</div></div>
    </div>
  </section>
</main>
<script>
let _es=null,_running=false,_t0=0,_timer=null,_liveBuffer='',_pendingQ=null,_histData=[],_activeId=null,_curRunId=null,_sidebarCollapsed=false;
function toggleSidebar(){_sidebarCollapsed=!_sidebarCollapsed;document.getElementById('shell').classList.toggle('sidebar-collapsed',_sidebarCollapsed)}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function switchBadge(state){const b=document.getElementById('status-badge');b.className='badge state-'+state;b.textContent=state}
function switchStateDot(state){const d=document.getElementById('dot');d.className='live-dot'+(state==='running'?' running':state==='error'?' error':'')}
function askConfirm(){const q=document.getElementById('nl-input').value.trim();if(!q||_running)return;_pendingQ={q,hours:+document.getElementById('run-hours').value||4,level:+document.getElementById('run-level').value||12};const p=document.getElementById('nl-preview');p.style.display='block';p.innerHTML='<div class="confirm-q">Run agentic investigation?<br><strong>"'+esc(q)+'"</strong></div><div class="confirm-note">Filter: last '+_pendingQ.hours+' hours, min level '+_pendingQ.level+'.</div><button class="confirm-yes" onclick="confirmRun()">Yes, do it</button><button class="confirm-no" onclick="cancelConfirm()">Cancel</button>'}
function cancelConfirm(){_pendingQ=null;document.getElementById('nl-preview').style.display='none'}
function confirmRun(){const p=_pendingQ;document.getElementById('nl-preview').style.display='none';if(!p)return;startAgent(p.q,p.hours,p.level)}
function appendLive(kind,text){const out=document.getElementById('live-out');const row=document.createElement('div');row.className='stream-row event-'+kind;row.textContent=text;out.appendChild(row);out.scrollTop=out.scrollHeight}
function startAgent(question,hours,level){if(_running)return;const out=document.getElementById('live-out');out.innerHTML='';_liveBuffer='';_curRunId=null;document.getElementById('live-title').textContent='Investigating';switchBadge('running');switchStateDot('running');setRunning(true);_t0=Date.now();_timer=setInterval(()=>{document.getElementById('elapsed').textContent=Math.floor((Date.now()-_t0)/1000)+'s'},1000);const scopedQuestion=question+' (Filter last '+hours+' hours, min level '+level+')';_es=new EventSource('/agent?q='+encodeURIComponent(scopedQuestion));_es.onmessage=(e)=>{const d=e.data;if(d==='__DONE__'){finish(false);return}if(d.startsWith('__RUNID__')){_curRunId=d.slice(9);return}_liveBuffer+=d+'\n';const t=d.trim();if(t.startsWith('[thinking]'))appendLive('thinking',t);else if(t.startsWith('→'))appendLive('tool_call',t);else if(t.startsWith('←'))appendLive('tool_result',t);else if(t.startsWith('[error]'))appendLive('error',t);else if(t.includes('FINAL ASSESSMENT'))appendLive('answer',t);else appendLive('tool_result',t)};_es.onerror=()=>{finish(true)}}
function stopRun(){fetch('/stop',{method:'POST'});if(_es){_es.close();_es=null}clearInterval(_timer);setRunning(false);document.getElementById('elapsed').textContent='';document.getElementById('live-title').textContent='Output — stopped';switchBadge('stopped');switchStateDot('');const note=document.createElement('div');note.className='stream-row event-error';note.textContent='Stopped by user. A model step already in progress may finish in the background, but its result is discarded.';document.getElementById('live-out').appendChild(note);_loadHistoryData()}
function finish(err){clearInterval(_timer);if(_es){_es.close();_es=null}setRunning(false);switchBadge(err?'error':'idle');switchStateDot(err?'error':'');document.getElementById('elapsed').textContent='';document.getElementById('live-title').textContent='Output';document.getElementById('last-run').textContent='completed '+new Date().toLocaleTimeString();_loadHistoryData()}
function setRunning(on){_running=on;const rb=document.getElementById('run-btn');document.getElementById('stop-btn').disabled=!on;rb.disabled=on;rb.classList.toggle('loading',on);rb.textContent=on?'Running…':'Run now';document.getElementById('status-text').textContent=on?'investigating…':'idle'}
function _loadHistoryData(){return fetch('/history').then(r=>r.json()).then(items=>{_histData=items;_renderHistory();return items})}
function loadHistory(){_loadHistoryData()}
function _renderHistory(){const el=document.getElementById('hist-list');document.getElementById('history-count').textContent=String(_histData.length);if(!_histData.length){el.innerHTML='<div class="empty-state">No investigations yet.</div>';return}el.innerHTML=_histData.map(i=>{const active=i.id===_activeId?' active':'';const color=i.status==='error'?'#f85149':i.status==='running'?'#3fb950':i.status==='stopped'?'#f0883e':'#667085';const copyBtn=i.report?'<button class="hbtn" data-copy="'+i.id+'">Copy</button>':'';const delBtn='<button class="hbtn" data-del="'+i.id+'">✕</button>';return '<div class="hi'+active+'" data-id="'+i.id+'"><div class="hl">'+esc(i.label)+'</div><div class="hm"><span class="ds '+i.status+'"></span><span>'+i.started+(i.ended?' — '+i.ended:'')+'</span><span style="margin-left:auto;color:'+color+'">'+i.status+'</span>'+copyBtn+delBtn+'</div></div>'}).join('');el.querySelectorAll('.hi').forEach(div=>div.addEventListener('click',()=>showReport(div.dataset.id)));el.querySelectorAll('[data-copy]').forEach(btn=>btn.addEventListener('click',e=>{e.stopPropagation();copySingle(btn.dataset.copy)}));el.querySelectorAll('[data-del]').forEach(btn=>btn.addEventListener('click',e=>{e.stopPropagation();deleteInv(btn.dataset.del)}))}
function showReport(id){_activeId=id;fetch('/history/'+id).then(r=>r.json()).then(d=>{const out=document.getElementById('report-out');const hdr=document.getElementById('report-header-text');const cb=document.getElementById('copy-btn');if(d.status==='running'){hdr.textContent='Investigation running — see the Live panel';out.innerHTML='<div class="empty-state">Report will appear here when the investigation completes.</div>';cb.style.display='none'}else{hdr.textContent=d.label||d.id;out.innerHTML=renderMD(d.report||'[No report available]');out.scrollTop=0;cb.style.display=d.report?'inline-block':'none'}_renderHistory()})}
function renderMD(src){const lines=(src||'').split('\n');let html='',inUL=false,inOL=false,inCode=false,codeBuf=[];const closeLists=()=>{if(inUL){html+='</ul>';inUL=false}if(inOL){html+='</ol>';inOL=false}};const inline=(t)=>esc(t).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>');for(let raw of lines){const line=raw.replace(/\s+$/,'');if(line.trim().startsWith('```')){if(inCode){html+='<pre class="md-pre">'+esc(codeBuf.join('\n'))+'</pre>';codeBuf=[];inCode=false}else{closeLists();inCode=true}continue}if(inCode){codeBuf.push(raw);continue}if(/^\s*[-─=]{3,}\s*$/.test(line)){closeLists();html+='<hr class="md-hr">';continue}let m;if((m=line.match(/^(#{1,4})\s+(.*)/))){closeLists();html+='<div class="md-h md-h'+m[1].length+'">'+inline(m[2])+'</div>';continue}if((m=line.match(/^\s*[-*]\s+(.*)/))){if(!inUL){closeLists();html+='<ul class="md-ul">';inUL=true}html+='<li>'+inline(m[1])+'</li>';continue}if((m=line.match(/^\s*\d+[.)]\s+(.*)/))){if(!inOL){closeLists();html+='<ol class="md-ol">';inOL=true}html+='<li>'+inline(m[1])+'</li>';continue}if(line.trim()===''){closeLists();html+='<div class="md-sp"></div>';continue}closeLists();html+='<div class="md-p">'+inline(line)+'</div>'}if(inCode)html+='<pre class="md-pre">'+esc(codeBuf.join('\n'))+'</pre>';closeLists();return html}
function copyReport(){const t=document.getElementById('report-out').innerText;const b=document.getElementById('copy-btn');navigator.clipboard.writeText(t).then(()=>{b.textContent='Copied!';setTimeout(()=>{b.textContent='Copy'},2000)})}
function copySingle(id){const it=_histData.find(i=>i.id===id);if(!it||!it.report)return;navigator.clipboard.writeText(it.report)}
function deleteInv(id){if(!confirm('Delete this investigation?'))return;fetch('/history/'+id,{method:'DELETE'}).then(r=>r.json()).then(d=>{if(d.ok){if(_activeId===id){document.getElementById('report-out').innerHTML='<div class="empty-state">Report appears here when you select run.</div>';document.getElementById('report-header-text').textContent='Select an investigation from sidebar';document.getElementById('copy-btn').style.display='none';_activeId=null}_loadHistoryData()}})}
function copyLive(){const b=document.getElementById('copy-live-btn');navigator.clipboard.writeText(_liveBuffer).then(()=>{b.textContent='Copied!';setTimeout(()=>{b.textContent='Copy'},2000)})}
function updateSched(){fetch('/schedule',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:document.getElementById('sched-on').checked,interval_minutes:+document.getElementById('sched-minutes').value,hours:+document.getElementById('sched-window').value})}).then(r=>r.json()).then(d=>{document.getElementById('sched-status').textContent=d.enabled?'เปิด — ทุก '+d.interval_minutes+' นาที':'ปิด'})}
setInterval(_loadHistoryData,15000);_loadHistoryData();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML, model=MODEL_LABEL)


PID_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.pid")
LOG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")

def _read_pid():
    try:
        pid = int(Path(PID_FILE).read_text().strip())
        os.kill(pid, 0)        # raises if not running
        return pid
    except Exception:
        return None

def _serve(args):
    """Actually start the Flask server (foreground in this process)."""
    ST.log_file = args.log_file
    threading.Thread(target=_scheduler, daemon=True).start()
    print("Wazuh Agentic Security Analyst")
    print(f"  Provider: {AI_PROVIDER}")
    print(f"  Model   : {AGENTIC_MODEL}")
    print(f"  UI      : http://{args.host}:{args.port}")
    print(f"  History : {ST.hist_file}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)

def main():
    # Accept both styles: "app.py stop" and "app.py --stop".
    _aliases = {"--start":"start","--stop":"stop","--restart":"restart",
                "--status":"status","--run":"run"}
    sys.argv[1:] = [_aliases.get(a, a) for a in sys.argv[1:]]

    p = argparse.ArgumentParser(description="Wazuh Agentic Security Analyst")
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "start", "stop", "restart", "status"],
                   help="run=foreground (default), start=background, "
                        "stop=stop background, restart, status")
    p.add_argument("--port", type=int, default=UI_PORT)
    p.add_argument("--host", default=UI_HOST)
    p.add_argument("--log-file", default="")
    args = p.parse_args()

    # ── stop ──────────────────────────────────────────────────────────────────
    if args.command == "stop":
        pid = _read_pid()
        if not pid:
            print("Not running (no live PID file).")
            Path(PID_FILE).unlink(missing_ok=True)
            return
        import signal as _sig
        os.kill(pid, _sig.SIGTERM)
        for _ in range(20):                 # wait up to ~5s for clean exit
            time.sleep(0.25)
            try: os.kill(pid, 0)
            except OSError: break
        else:
            os.kill(pid, _sig.SIGKILL)       # force if it did not stop
        Path(PID_FILE).unlink(missing_ok=True)
        print(f"Stopped (PID {pid}).")
        return

    # ── status ────────────────────────────────────────────────────────────────
    if args.command == "status":
        pid = _read_pid()
        print(f"Running (PID {pid}). UI: http://{args.host}:{args.port}"
              if pid else "Not running.")
        return

    # ── restart ─────────────────────────────────────────────────────────────--
    if args.command == "restart":
        pid = _read_pid()
        if pid:
            import signal as _sig
            os.kill(pid, _sig.SIGTERM); time.sleep(1)
            try: os.kill(pid, 0); os.kill(pid, _sig.SIGKILL)
            except OSError: pass
            Path(PID_FILE).unlink(missing_ok=True)
            print(f"Stopped old instance (PID {pid}).")
        args.command = "start"   # fall through to start

    # ── start (background) ─────────────────────────────────────────────────────
    if args.command == "start":
        if _read_pid():
            print(f"Already running (PID {_read_pid()}). Use 'stop' or 'restart'.")
            return
        # Re-launch this script in 'run' mode as a detached child, logging to file.
        import subprocess
        logf = open(args.log_file or LOG_FILE, "a")
        child = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "run",
             "--port", str(args.port), "--host", args.host],
            stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
            start_new_session=True)          # detach from this terminal
        Path(PID_FILE).write_text(str(child.pid))
        time.sleep(1.5)
        if _read_pid():
            print(f"Started in background (PID {child.pid}).")
            print(f"  UI   : http://{args.host}:{args.port}")
            print(f"  Log  : {args.log_file or LOG_FILE}")
            print(f"  Stop : python3 {os.path.basename(__file__)} stop")
        else:
            print("Failed to start — check the log file.")
        return

    # ── run (foreground, default) ──────────────────────────────────────────────
    # When launched as a background child we are the server process; record our
    # own PID so 'stop' can find us even if the parent already exited.
    Path(PID_FILE).write_text(str(os.getpid()))
    import atexit, signal as _sig
    atexit.register(lambda: Path(PID_FILE).unlink(missing_ok=True))
    _sig.signal(_sig.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit))
    try:
        _serve(args)
    finally:
        Path(PID_FILE).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
