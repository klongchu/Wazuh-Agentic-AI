# Wazuh Agentic AI Integration

> ผู้ช่วยวิเคราะห์ความปลอดภัยสำหรับ Wazuh ที่ใช้ LLM วางแผนการสืบค้นข้อมูล ตีความผลลัพธ์ และสรุปผลการสอบสวนพร้อม audit trail

## ภาพรวม

โปรเจกต์นี้ช่วยให้ผู้ใช้งานถามคำถามด้านความปลอดภัยด้วยภาษาธรรมชาติ เช่น

- "มีสัญญาณการ compromise ในช่วง 24 ชั่วโมงล่าสุดหรือไม่"
- "ช่วย correlate severity 12 events ในช่วง 7 วันที่ผ่านมา"
- "มีพฤติกรรมที่อาจบ่งชี้การ data exfiltration จาก endpoints หรือไม่"

จากนั้นระบบจะให้ LLM วางแผนการสอบสวนเอง เลือกว่าจะใช้ Wazuh queries แบบใด อ่านผลลัพธ์ที่ได้ ทำการไล่ตรวจสอบเพิ่มเติมตามบริบท และสรุปผลกลับมาเป็นคำตอบที่อ่านเข้าใจง่าย โดยทุกขั้นตอนที่เรียกใช้ tools จะถูกบันทึกเป็น audit trail เพื่อให้ตรวจสอบย้อนหลังได้

## จุดเด่น

- **Natural-language investigation** — เริ่มจากคำถามภาษาธรรมชาติ แทนการเขียน query เองทุกครั้ง
- **Live investigation view** — ดูการทำงานของ agent แบบสดผ่าน web UI
- **Tool-call audit trail** — ทุก query และผลลัพธ์ที่เกี่ยวข้องถูกเก็บไว้ในรายงาน
- **Scheduled triage** — ตั้งเวลาให้ระบบรันงาน triage อัตโนมัติได้
- **Provider selection via `.env`** — เลือกใช้ `OpenAI` หรือ `Ollama` ได้จาก config เดียว

## Requirements

- **Python 3.10+**
- **Wazuh deployment** ที่เข้าถึงได้ผ่าน network (manager + indexer)
- **LLM provider** ที่พร้อมใช้งานอย่างน้อยหนึ่งแบบ:
  - `OpenAI` เมื่อใช้ `AI_PROVIDER=openai`
  - `Ollama` เมื่อใช้ `AI_PROVIDER=ollama`
- หากใช้ `Ollama` ควรเลือก model ที่รองรับ tool calling ได้ดีพอ เพราะ model ขนาดเล็กมาก (เช่น 3B-4B) มักเรียก tools ได้ไม่เสถียร

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

## Run agent loop without UI

หากต้องการทดสอบ agent โดยไม่เปิดหน้าเว็บ สามารถเรียก `agent_tools.py` ตรงได้

```bash
python agent_tools.py "Are there any signs of compromise in the last 24 hours?"
python agent_tools.py --agent 001 "Correlate severity 12 events over last 7 days"
```

## การใช้งานผ่าน UI

เปิด browser ไปที่:

```text
http://<host>:5000
```

จากนั้นใช้งานหลักได้ 3 ส่วน:

- **Run** — พิมพ์คำถาม, เริ่มการสอบสวน, ดู stream ของ tool calls / reasoning / final verdict แบบสด, และกด **Stop** เพื่อยกเลิกได้
- **Reports** — ดูผลการสอบสวนที่บันทึกไว้ย้อนหลัง พร้อม verdict และ audit trail
- **Schedule / Auto-run** — ตั้งให้ระบบรัน triage อัตโนมัติทุก N ชั่วโมง โดยดูข้อมูลย้อนหลัง M ชั่วโมง

## Architecture

ระบบแบ่งออกเป็น 3 ส่วนหลัก โดยแต่ละไฟล์มีขอบเขตความรับผิดชอบชัดเจน

| File | Role |
| ---- | ---- |
| `app.py` | Flask app, HTTP routes, process control, SSE streaming, scheduler, และ investigation history |
| `agent_tools.py` | agent loop, system prompt, tool registry, provider adapter, และ orchestration ของการสอบสวน |
| `client.py` | data layer สำหรับ config loading, Wazuh API auth, indexer queries, inventory access, และ shared helpers |

แนวคิดสำคัญคือให้ `client.py` คืน raw facts และ transport errors เท่านั้น ขณะที่การตีความและการตัดสินใจเชิง investigation อยู่ใน `agent_tools.py`

## Data flow

เส้นทางการทำงานหลักของระบบเป็นดังนี้:

1. ผู้ใช้ส่งคำถามจาก browser ผ่าน route `/agent` ใน `app.py`
2. `app.py` เริ่ม thread ใหม่เพื่อรัน `_run_agentic()`
3. `_run_agentic()` เรียก `run_agent()` จาก `agent_tools.py`
4. `run_agent()` ส่ง message history ไปยัง provider ที่เลือกไว้ (`OpenAI` หรือ `Ollama`) พร้อม tool schemas
5. เมื่อ model ขอเรียก tool ระบบจะ map ไปยัง Python functions ใน `agent_tools.py`
6. tools เหล่านั้นเรียก `client.py` เพื่อ query `Wazuh API` หรือ `Wazuh indexer`
7. ผลลัพธ์ถูก stream กลับไปยัง UI แบบสดผ่าน SSE และถูกบันทึกลง `investigations.json` เป็นประวัติรายงาน

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
