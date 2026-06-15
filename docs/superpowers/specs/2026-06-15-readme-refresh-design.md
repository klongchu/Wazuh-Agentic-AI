# README Refresh Design

Date: 2026-06-15

## Goal

ปรับ `README.md` ใหม่ให้เป็นเอกสารภาษาไทยแบบมืออาชีพ โดยใช้ภาษาไทยเป็นหลัก แต่คง technical terms, commands, environment variables, และชื่อไฟล์เป็นภาษาอังกฤษ เพื่อให้ทีมภายในเข้าใจทั้งภาพรวมระบบ วิธีติดตั้ง/ใช้งาน และโครงสร้างสถาปัตยกรรมได้จากเอกสารเดียว

## Audience

กลุ่มผู้อ่านหลักคือทีมภายในที่ต้องทั้ง:

- ทดลองรันระบบได้เอง
- เข้าใจข้อพึ่งพาและการตั้งค่าเบื้องต้น
- มองเห็น architecture, data flow, และข้อจำกัดของระบบก่อนลงมือแก้โค้ด

กลุ่มรองคือผู้พัฒนาที่จะเข้ามาต่อยอดระบบภายหลัง

## Problems In Current README

จาก `README.md` ปัจจุบัน:

- เปิดเอกสารด้วย `## TEST` ทำให้ภาพลักษณ์ไม่พร้อมใช้งานจริง
- มีข้อมูล setup และ architecture อยู่แล้ว แต่การเรียบเรียงยังไม่เหมาะกับเอกสารสำหรับทีมภายใน
- ยังไม่สื่อ value proposition และ use cases ของระบบตั้งแต่ต้น
- ยังไม่เชื่อมโยงโครงสร้างไฟล์กับ flow การใช้งานจริงให้ชัด
- ภาษายังไม่สม่ำเสมอในเชิงเอกสารมืออาชีพ

## Scope

In scope:

- เขียน `README.md` ใหม่ทั้งฉบับหรือแทนที่เนื้อหาหลักเดิมด้วยโครงใหม่
- ใช้ภาษาไทยเป็นหลัก โดยคงคำเทคนิคภาษาอังกฤษที่สำคัญ
- เพิ่มลำดับเนื้อหาที่เหมาะกับทีมภายใน: ภาพรวม → features → requirements → setup → run → usage → architecture → constraints
- ปรับตัวอย่าง `.env` และคำอธิบายให้สอดคล้องกับสถานะปัจจุบันของระบบ
- ทำให้ command examples สอดคล้องกับเอกสารใน `CLAUDE.md`

Out of scope:

- เปลี่ยนพฤติกรรมโค้ดจริง
- เพิ่ม screenshots, GIFs, หรือ assets ใหม่
- เปลี่ยนชื่อโปรเจกต์หรือรีแบรนด์ผลิตภัณฑ์
- เขียนเอกสารแยกสำหรับ deployment, security hardening, หรือ contributor guide

## Content Strategy

README ใหม่จะใช้แนวทาง “Balanced internal README” คือให้เอกสารเดียวตอบทั้งมุม operator และ developer แบบไม่หนักไปด้านใดด้านหนึ่ง

ลำดับเนื้อหาที่เสนอ:

1. **Project title + one-line summary**
   - อธิบายสั้นว่าระบบนี้คือ LLM-driven security analyst สำหรับ Wazuh
2. **ระบบนี้ทำอะไร**
   - อธิบาย workflow ระดับสูงจากคำถามภาษาธรรมชาติไปสู่การสืบค้นข้อมูลและสรุปผล
3. **จุดเด่นของระบบ**
   - live investigation, audit trail, scheduled triage, provider selection
4. **Requirements**
   - Python, Wazuh, indexer, OpenAI/Ollama prerequisites
5. **Setup**
   - install dependencies
   - create `.env`
   - explain provider selection and key variables
6. **Run application**
   - `python app.py run|start|stop|restart|status`
7. **การใช้งานผ่าน UI**
   - Run, Reports, Schedule/Auto-run behavior
8. **Architecture**
   - ownership ของ `app.py`, `agent_tools.py`, `client.py`
9. **Data flow**
   - request path ตั้งแต่ browser ถึง Wazuh APIs
10. **ข้อจำกัดปัจจุบัน**
   - single manager/indexer, file-backed history, non-componentized frontend
11. **แนวทางพัฒนาต่อ**
   - เก็บส่วน improvement ideas ที่ยังเกี่ยวข้อง

## Writing Style

- ภาษาไทยเป็นหลัก
- คงคำต่อไปนี้เป็นภาษาอังกฤษเมื่อช่วยให้ชัดกว่า: `README`, `Quickstart`, `Features`, `Architecture`, `Data flow`, `Run`, `Reports`, `Schedule`, `.env`, `OpenAI`, `Ollama`, `Wazuh API`, `indexer`
- ใช้น้ำเสียงมืออาชีพ กระชับ อ่านง่าย
- หลีกเลี่ยงภาษาการตลาดเกินจริง
- ใช้ bullet lists และ section headings ให้สแกนง่าย
- คำสั่ง shell และ config blocks คงเป็นภาษาอังกฤษทั้งหมด

## Proposed Structure

```markdown
# Wazuh Agentic AI Integration

> ผู้ช่วยวิเคราะห์ความปลอดภัยสำหรับ Wazuh ที่ใช้ LLM วางแผนการสืบค้นข้อมูล ตีความผลลัพธ์ และสรุปผลการสอบสวนพร้อม audit trail

## ภาพรวม
## จุดเด่น
## Requirements
## Setup
### 1. Install dependencies
### 2. Create `.env`
## Run application
## การใช้งานผ่าน UI
## Architecture
## Data flow
## ข้อจำกัดปัจจุบัน
## แนวทางพัฒนาต่อ
```

## Architecture Notes To Preserve

เนื้อหา README ต้องยังสะท้อน boundary เดิมของระบบ:

- `app.py` เป็น entrypoint และถือ ownership ของ Flask app, process control, SSE, schedule, history
- `agent_tools.py` เป็น agent loop และ tool surface
- `client.py` เป็น data layer และ config loading

ไม่ควรอธิบายจนละเอียดเท่าคู่มือนักพัฒนาเต็มรูปแบบ แต่ต้องพอให้ทีมภายในมองภาพรวมระบบได้โดยไม่ต้องเปิดไฟล์ทันที

## Configuration Notes To Preserve

README ใหม่ต้องยังบอกชัดว่า:

- provider ถูกเลือกผ่าน `.env` ด้วย `AI_PROVIDER=openai|ollama`
- ค่า default คือ OpenAI
- ถ้าใช้ OpenAI ต้องมี `OPENAI_API_KEY`
- Ollama เป็น optional alternative เมื่อสลับ provider
- `client.py` โหลด `.env` ตอน import

## Command Conventions

เพื่อให้สอดคล้องกับ repo guidance ปัจจุบัน ควรใช้ตัวอย่าง command รูปแบบ:

```bash
python app.py run
python app.py start
python app.py stop
python app.py restart
python app.py status
```

และเสริมว่า flags เช่น `--host` และ `--port` ใช้ได้

## Error Handling In Documentation

README ควรสื่อข้อผิดพลาดเชิงปฏิบัติการที่พบบ่อยอย่างสั้นและตรง:

- `.env` ไม่ครบ → provider call ใช้งานไม่ได้
- Wazuh API / indexer reachable ไม่ได้ → tools query ไม่สำเร็จ
- Ollama model เล็กเกินไป → tool calling ไม่เสถียร

ไม่ต้องทำ troubleshooting section ยาว แต่ควรฝัง warning ไว้ใน Setup/Requirements/Notes

## Success Criteria

ถือว่างานสำเร็จเมื่อ `README.md` ใหม่:

1. เปิดอ่านแล้วอธิบายโปรเจกต์ได้ชัดใน 1-2 นาทีแรก
2. ทีมภายในสามารถติดตั้งและรันระบบตามเอกสารได้
3. ผู้อ่านเข้าใจ role ของ `app.py`, `agent_tools.py`, `client.py` โดยไม่ต้องเดา
4. ภาษาโดยรวมเป็นไทยมืออาชีพ สม่ำเสมอ
5. technical commands และ config examples ยัง copy ไปใช้ได้ตรง

## Likely File Changes

- Modify: `README.md`

## Ambiguity Resolution

- “ภาษาไทยเป็นหลัก” ตีความเป็น prose ภาษาไทย แต่คง code/config/commands และชื่อเทคนิคสำคัญเป็นอังกฤษ
- “มืออาชีพ” ตีความเป็นสำนวนตรง ชัด เรียบ ไม่เล่นมุก ไม่โฆษณาเกินจริง
- “เน้นทีมภายใน” ตีความเป็นเอกสารที่ balance ระหว่าง usage และ architecture มากกว่าเอกสาร marketing หรือ contributor-only

## Self-review

- Placeholder scan: none
- Internal consistency: structure, audience, and scope align
- Scope check: limited to README rewrite only
- Ambiguity check: language, tone, and audience clarified explicitly
