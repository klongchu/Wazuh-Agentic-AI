# README Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` into a professional Thai-first internal guide that explains project value, setup, usage, architecture, and operational limits in one document.

**Architecture:** Keep work scoped to documentation only. Replace current README structure with a clearer sequence: overview, features, requirements, setup, run, UI usage, architecture, data flow, limits, and future improvements. Preserve current system boundaries and configuration behavior exactly as implemented in code and described in `CLAUDE.md`.

**Tech Stack:** Markdown, Python application commands, Wazuh API, Wazuh indexer, OpenAI, Ollama

---

## File Structure

- Modify: `README.md` — rewrite content and section order in Thai-first style
- Reference: `CLAUDE.md` — source of command/architecture rules that README must match
- Reference: `app.py` — source of run commands, UI behavior, scheduling, and history behavior
- Reference: `agent_tools.py` — source of standalone CLI usage and tool/agent responsibilities
- Reference: `client.py` — source of `.env` loading, provider selection, and transport-layer boundaries
- Reference: `docs/superpowers/specs/2026-06-15-readme-refresh-design.md` — approved design for rewrite scope and tone

---

### Task 1: Re-outline `README.md`

**Files:**
- Modify: `README.md`
- Reference: `docs/superpowers/specs/2026-06-15-readme-refresh-design.md`

- [ ] **Step 1: Replace opening heading and summary**

Replace current opening section with this content:

```markdown
# Wazuh Agentic AI Integration

> ผู้ช่วยวิเคราะห์ความปลอดภัยสำหรับ Wazuh ที่ใช้ LLM วางแผนการสืบค้นข้อมูล ตีความผลลัพธ์ และสรุปผลการสอบสวนพร้อม audit trail
```

- [ ] **Step 2: Add overview section under summary**

Insert this section after the summary:

```markdown
## ภาพรวม

โปรเจกต์นี้ช่วยให้ผู้ใช้งานถามคำถามด้านความปลอดภัยด้วยภาษาธรรมชาติ เช่น

- "มีสัญญาณการ compromise ในช่วง 24 ชั่วโมงล่าสุดหรือไม่"
- "ช่วย correlate severity 12 events ในช่วง 7 วันที่ผ่านมา"
- "มีพฤติกรรมที่อาจบ่งชี้การ data exfiltration จาก endpoints หรือไม่"

จากนั้นระบบจะให้ LLM วางแผนการสอบสวนเอง เลือกว่าจะใช้ Wazuh queries แบบใด อ่านผลลัพธ์ที่ได้ ทำการไล่ตรวจสอบเพิ่มเติมตามบริบท และสรุปผลกลับมาเป็นคำตอบที่อ่านเข้าใจง่าย โดยทุกขั้นตอนที่เรียกใช้ tools จะถูกบันทึกเป็น audit trail เพื่อให้ตรวจสอบย้อนหลังได้
```

- [ ] **Step 3: Add key features section**

Insert this section below `## ภาพรวม`:

```markdown
## จุดเด่น

- **Natural-language investigation** — เริ่มจากคำถามภาษาธรรมชาติ แทนการเขียน query เองทุกครั้ง
- **Live investigation view** — ดูการทำงานของ agent แบบสดผ่าน web UI
- **Tool-call audit trail** — ทุก query และผลลัพธ์ที่เกี่ยวข้องถูกเก็บไว้ในรายงาน
- **Scheduled triage** — ตั้งเวลาให้ระบบรันงาน triage อัตโนมัติได้
- **Provider selection via `.env`** — เลือกใช้ `OpenAI` หรือ `Ollama` ได้จาก config เดียว
```

- [ ] **Step 4: Review README outline in diff**

Run:

```bash
git diff -- README.md
```

Expected: diff shows new title, summary, overview, and key-features sections in Thai.

- [ ] **Step 5: Commit outline rewrite**

```bash
git add README.md
git commit -m "docs: rewrite README overview structure"
```

---

### Task 2: Rewrite setup and run instructions

**Files:**
- Modify: `README.md`
- Reference: `CLAUDE.md`

- [ ] **Step 1: Replace requirements section with Thai-first wording**

Use this section:

```markdown
## Requirements

- **Python 3.10+**
- **Wazuh deployment** ที่เข้าถึงได้ผ่าน network (manager + indexer)
- **LLM provider** ที่พร้อมใช้งานอย่างน้อยหนึ่งแบบ:
  - `OpenAI` เมื่อใช้ `AI_PROVIDER=openai`
  - `Ollama` เมื่อใช้ `AI_PROVIDER=ollama`
- หากใช้ `Ollama` ควรเลือก model ที่รองรับ tool calling ได้ดีพอ เพราะ model ขนาดเล็กมาก (เช่น 3B-4B) มักเรียก tools ได้ไม่เสถียร
```

- [ ] **Step 2: Replace setup section with command and `.env` guidance**

Use this exact content:

```markdown
## Setup

### 1. Install dependencies

```bash
pip install flask flask_cors ollama openai requests
```

### 2. Create `.env`

สร้างไฟล์ `.env` ไว้ใน directory เดียวกับ `app.py` เพราะ `client.py` จะโหลดไฟล์นี้ตอน import

```ini
# -- Wazuh API (token auth, port 55000) --
WAZUH_HOST=https://<WAZUH_SERVER_IP>:55000
WAZUH_USER=your_api_user
WAZUH_PASS=your_api_password
WAZUH_SSL=false

# -- Wazuh Indexer (basic auth, port 9200) --
INDEXER_HOST=https://<WAZUH_INDEXER_IP>:9200
INDEXER_USER=admin
INDEXER_PASS=your_indexer_password

# -- LLM provider selection --
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1
# Optional: OpenAI-compatible gateway
# OPENAI_BASE_URL=https://your-endpoint/v1

# -- Ollama (optional alternative provider) --
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3

# -- Optional tuning --
AGENTIC_MAX_STEPS=18
UI_HOST=0.0.0.0
UI_PORT=5000
```

Notes:

- ค่า default provider คือ `openai`
- หากใช้ `AI_PROVIDER=openai` ต้องกำหนด `OPENAI_API_KEY`
- หากต้องการใช้ `Ollama` ให้เปลี่ยนเป็น `AI_PROVIDER=ollama` และตั้งค่า `OLLAMA_HOST` / `OLLAMA_MODEL`
- หาก config ไม่ครบหรือ provider ติดต่อไม่ได้ การรันจะจบด้วย error ที่ชัดเจน ไม่มี automatic fallback
```

- [ ] **Step 3: Replace run section with repo-aligned commands**

Use this section:

```markdown
## Run application

`app.py` เป็น entrypoint ของระบบ และมี process control มาให้ในตัว

```bash
python app.py run
python app.py start
python app.py stop
python app.py restart
python app.py status
```

สามารถระบุ flags เพิ่มได้ เช่น

```bash
python app.py run --host 0.0.0.0 --port 5000
python app.py start --host 0.0.0.0 --port 5000
```

เมื่อรันแบบ background ระบบจะเขียน `agent.pid` และ `agent.log` โดยอัตโนมัติ เว้นแต่จะ override ด้วย `--log-file`
```

- [ ] **Step 4: Add standalone CLI section for direct investigation runs**

Insert after `## Run application`:

```markdown
## Run agent loop without UI

หากต้องการทดสอบ agent โดยไม่เปิดหน้าเว็บ สามารถเรียก `agent_tools.py` ตรงได้

```bash
python agent_tools.py "Are there any signs of compromise in the last 24 hours?"
python agent_tools.py --agent 001 "Correlate severity 12 events over last 7 days"
```
```

- [ ] **Step 5: Review setup/run diff**

Run:

```bash
git diff -- README.md
```

Expected: requirements, setup, `.env`, app commands, and direct CLI usage are all rewritten in Thai-first wording.

- [ ] **Step 6: Commit setup/run rewrite**

```bash
git add README.md
git commit -m "docs: rewrite README setup and run guide"
```

---

### Task 3: Rewrite usage, architecture, and operational context

**Files:**
- Modify: `README.md`
- Reference: `CLAUDE.md`

- [ ] **Step 1: Replace usage section with UI-focused Thai wording**

Use this section:

```markdown
## การใช้งานผ่าน UI

เปิด browser ไปที่:

```text
http://<host>:5000
```

จากนั้นใช้งานหลักได้ 3 ส่วน:

- **Run** — พิมพ์คำถาม, เริ่มการสอบสวน, ดู stream ของ tool calls / reasoning / final verdict แบบสด, และกด **Stop** เพื่อยกเลิกได้
- **Reports** — ดูผลการสอบสวนที่บันทึกไว้ย้อนหลัง พร้อม verdict และ audit trail
- **Schedule / Auto-run** — ตั้งให้ระบบรัน triage อัตโนมัติทุก N ชั่วโมง โดยดูข้อมูลย้อนหลัง M ชั่วโมง
```

- [ ] **Step 2: Replace architecture section with internal-team framing**

Use this section:

```markdown
## Architecture

ระบบแบ่งออกเป็น 3 ส่วนหลัก โดยแต่ละไฟล์มีขอบเขตความรับผิดชอบชัดเจน

| File | Role |
|------|------|
| `app.py` | Flask app, HTTP routes, process control, SSE streaming, scheduler, และ investigation history |
| `agent_tools.py` | agent loop, system prompt, tool registry, provider adapter, และ orchestration ของการสอบสวน |
| `client.py` | data layer สำหรับ config loading, Wazuh API auth, indexer queries, inventory access, และ shared helpers |

แนวคิดสำคัญคือให้ `client.py` คืน raw facts และ transport errors เท่านั้น ขณะที่การตีความและการตัดสินใจเชิง investigation อยู่ใน `agent_tools.py`
```

- [ ] **Step 3: Add data-flow section tied to real execution path**

Insert this section after `## Architecture`:

```markdown
## Data flow

เส้นทางการทำงานหลักของระบบเป็นดังนี้:

1. ผู้ใช้ส่งคำถามจาก browser ผ่าน route `/agent` ใน `app.py`
2. `app.py` เริ่ม thread ใหม่เพื่อรัน `_run_agentic()`
3. `_run_agentic()` เรียก `run_agent()` จาก `agent_tools.py`
4. `run_agent()` ส่ง message history ไปยัง provider ที่เลือกไว้ (`OpenAI` หรือ `Ollama`) พร้อม tool schemas
5. เมื่อ model ขอเรียก tool ระบบจะ map ไปยัง Python functions ใน `agent_tools.py`
6. tools เหล่านั้นเรียก `client.py` เพื่อ query `Wazuh API` หรือ `Wazuh indexer`
7. ผลลัพธ์ถูก stream กลับไปยัง UI แบบสดผ่าน SSE และถูกบันทึกลง `investigations.json` เป็นประวัติรายงาน
```

- [ ] **Step 4: Add current limits and future improvements sections**

Append these sections near the end of `README.md`:

```markdown
## ข้อจำกัดปัจจุบัน

- ระบบออกแบบบนสมมติฐานว่าใช้ Wazuh manager และ indexer อย่างละหนึ่งชุด
- investigation history ถูกเก็บแบบ file-backed ใน `investigations.json` ไม่ใช่ database
- frontend อยู่ใน `app.py` เป็น inline HTML/CSS/JS ยังไม่ได้แยกเป็น components
- ในแต่ละช่วงเวลาจะมี investigation ที่รันได้เพียงหนึ่งงานผ่าน lock กลางของระบบ

## แนวทางพัฒนาต่อ

- เพิ่ม tools สำหรับ drill-down หรือ correlation ที่ละเอียดขึ้น
- เปิดให้เลือก model/provider จาก UI ในอนาคต หากต้องการ
- ปรับประสบการณ์การดู audit trail ให้สะดวกขึ้นระหว่าง live run
- เปลี่ยน history storage ไปสู่ database หากต้องรองรับการค้นหาและปริมาณข้อมูลมากขึ้น
- รองรับ Wazuh แบบ multi-node หรือ multi-tenant ใน data layer
```
```

- [ ] **Step 5: Review final README diff**

Run:

```bash
git diff -- README.md
```

Expected: README now reads like one coherent Thai-first internal guide, not a patchwork of old English sections.

- [ ] **Step 6: Commit usage/architecture rewrite**

```bash
git add README.md
git commit -m "docs: rewrite README architecture and usage"
```

---

### Task 4: Final documentation verification

**Files:**
- Modify: `README.md`
- Reference: `CLAUDE.md`, `app.py`, `agent_tools.py`, `client.py`

- [ ] **Step 1: Verify command consistency against repo guidance**

Run:

```bash
git diff -- README.md CLAUDE.md
```

Expected: README commands match `CLAUDE.md` conventions for `python app.py ...` and `python agent_tools.py ...`.

- [ ] **Step 2: Verify key phrases exist in README**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('README.md').read_text(encoding='utf-8')
checks = [
    '## ภาพรวม',
    '## จุดเด่น',
    '## Setup',
    '## Run application',
    '## Run agent loop without UI',
    '## การใช้งานผ่าน UI',
    '## Architecture',
    '## Data flow',
    '## ข้อจำกัดปัจจุบัน',
]
missing = [c for c in checks if c not in text]
print('MISSING:', missing)
PY
```

Expected: `MISSING: []`

- [ ] **Step 3: Review rendered markdown mentally from source**

Read through `README.md` and confirm:

- opening no longer starts with `## TEST`
- Thai prose is consistent
- technical terms remain in English where needed
- no duplicate sections remain from old structure
- code fences are balanced

- [ ] **Step 4: Commit final README polish**

```bash
git add README.md
git commit -m "docs: polish Thai README for internal teams"
```

---

## Spec Coverage Check

- Thai-first professional tone — covered by Tasks 1, 2, and 3
- internal-team audience balance between usage and architecture — covered by Tasks 1 and 3
- new content order: overview → features → requirements → setup → run → usage → architecture → data flow → limits — covered by Tasks 1, 2, 3, and 4
- provider and `.env` behavior preserved — covered by Task 2
- role of `app.py`, `agent_tools.py`, `client.py` clarified — covered by Task 3
- commands aligned with repo guidance — covered by Tasks 2 and 4
- no code behavior changes — enforced by all tasks staying inside `README.md`

## Self-Review

- Placeholder scan: no TBD/TODO/generic filler steps
- Type consistency: paths, section names, and commands are used consistently across tasks
- Scope check: plan changes only `README.md`, with other files used as references only
