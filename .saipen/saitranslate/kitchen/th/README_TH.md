<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**โพรโทคอลความต่อเนื่องสำหรับ AI coding agent** หน่วยความจำโปรเจกต์ถาวรในรูปแบบมาร์กดาวน์ธรรมดา เพื่อให้ agent ตัวใหม่ที่ไม่มีประวัติการแชตสามารถรัน `/saipen continue` แล้วกลับมาทำงานต่อได้ภายในเวลาไม่ถึงหนึ่งนาที -- ไม่ต้องบรีฟงานใหม่ ใช้ได้กับทุกค่าย ทุกวัน

**คำสั่งเดียว ศูนย์การสูญเสียความจำ**

**v7.151.0** | [ข้อกำหนด](SPEC.md) | [คู่มือ](GUIDE.md) | [RFC](saipen/RFC.md) | [สไตล์](saipen/STYLE.md) | [UI](saipen/UI.md) | [การปฏิบัติตามมาตรฐาน](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

### สถานะโปรเจกต์ > หน่วยความจำของโมเดล
หน่วยความจำเก็บอยู่ในโปรเจกต์ ไม่ใช่ในหัวของโมเดล `Project -> Memory -> LLM` เปลี่ยนเป็น `Project -> SAIPEN State -> LLM`

### ตรรกะหลักและการรับประกันของโพรโทคอล
- **Core State Machine**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Zero-Prompt Autonomy**: ไม่เหลืองานค้าง? เปลี่ยนสถานะอัตโนมัติ `HUNT` (สแกนหาบั๊ก) → `ADD` (พัฒนาฟีเจอร์) → วนลูป `HUNT` โดยไม่ต้องตั้งคำถามใดๆ
- **Explicit Triggers**: `/saipen clean` (เก็บกวาดเรโป), `/saipen translate` (โฟลเดอร์แยก `.saipen/saitranslate/`), `/saipen markhunt` (ตรวจสอบแบบดรายรันไม่จำกัดจำนวน บันทึกผลอย่างเดียว), `/saipen prepare` (แพ็กเกจงานสำหรับส่งต่อ), `/saipen validate` (ตรวจสอบความถูกต้องตามข้อกำหนด), `/saipen goal` (ประมวลผลงานแบบอัตโนมัติเป็นระลอก) คำสั่งควบคุม/เมทา: `/saipen status` (รายงานแบบอ่านอย่างเดียว), `/saipen stop` (สร้างจุดเช็กพอยต์และหยุดทำงาน) รายการทั้งหมด: RFC.md § 1.10
- **Strict Reliability**: การพาร์สอินพุตแบบกลุ่ม (ตั๋วทีละใบอย่างแม่นยำ), การยอมรับ dirty-tree (ไม่ลบงานที่ยังไม่ได้ commit), การเซ็นเซอร์ความลับ (`sk-***`)

## โปรเจกต์ที่ขับเคลื่อนด้วย SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — เครื่องมือจัดการพรอมต์ประสิทธิภาพสูงที่รวมเข้ากับโพรโทคอลความจำ SAIPEN โดยตรง

## สองชั้นการทำงาน (Two Layers)

| ชั้น | จำเป็น | วัตถุประสงค์ |
|---|---|---|
| **Core** | ✅ | สานต่อการทำงานได้อย่างปลอดภัย |
| **Maintenance** | ทำงานบน Core | พัฒนาซอฟต์แวร์ต่อเนื่องโดยไม่ต้องมอบหมายงาน |

**การพัฒนาโดยอัตโนมัติ (Automated Evolution)** เมื่อไม่มีงานค้างเหลืออยู่ เพียงพิมพ์ `/saipen`: `HUNT` จะตรวจสอบหาบั๊ก โค้ดที่ไม่ใช้แล้ว หรือเทสต์ที่ล้มเหลว เมื่อสะอาดแล้ว? `ADD` จะสร้างความสามารถที่จำเป็นถัดไป ตรวจสอบความถูกต้อง แล้วกลับไปล่าบั๊กอีกครั้ง เมื่อผลิตภัณฑ์สมบูรณ์แล้ว -> หยุดทำงานอย่างเรียบร้อย

**โหมด GOAL** `/saipen goal <สิ่งที่คุณต้องการ>` จะปรับเปลี่ยนกระดานงาน (ตั๋วเก่าจะถูกลดความสำคัญลง แต่ไม่เคยถูกลบ) และดำเนินตามวัตถุประสงค์ใหม่ไปข้างหน้า -- ไม่มีคำถามประเภท "จะให้ฉันทำต่อไหม?" ระหว่างตั๋วงาน ไม่เคยข้าม VERIFY/REVIEW ขั้นตอน SHIP จะ auto-push ไปยัง remote ที่มีอยู่โดยอัตโนมัติ หากเป็นเรโปใหม่จะถามเพียงครั้งเดียว การ SHIP วัตถุประสงค์ไม่ใช่จุดสิ้นสุดการทำงานเช่นกัน -- แต่จะเข้าสู่ขั้นตอนการดูแลรักษาแบบอัตโนมัติ HUNT/ADD ทันที จนกว่าผลิตภัณฑ์จะสมบูรณ์ ติดขัด หรือรันจนครบโควตา (3 ระลอก / 20 ตั๋วงาน จากนั้นจะสร้างจุดเช็กพอยต์และรายงานผล)

## เริ่มต้นใช้งานอย่างรวดเร็ว (Quick Start)

**1. ติดตั้งครั้งเดียวต่อเครื่อง** -- เพื่อให้ Claude Code, Gemini, OpenCode, Aider, Antigravity รู้จัก:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. เริ่มต้นโปรเจกต์** -- เปิด agent ในโฟลเดอร์ของคุณ แล้วพิมพ์:
> `saipen set`

ไม่ได้ติดตั้ง? คัดลอกหนึ่งบรรทัดนี้วางให้ agent ตัวใดก็ได้:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

แพลตฟอร์มไม่ได้อยู่ในรายการข้างต้น (DeepSeek, Qwen, standalone OpenAI ฯลฯ)?
หมายเหตุแยกตามแพลตฟอร์มอยู่ใน `extensions/adapters/`

## ลิงก์เอกสารและข้อกำหนด
- **[SPEC.md](SPEC.md)** -- สถาปัตยกรรมอย่างเป็นทางการ เป้าหมายการออกแบบ และแบบทดสอบ
- **[RFC.md](saipen/RFC.md)** -- ข้อกำหนดมาตรฐานที่ถูกรันโดย agent
- **[GUIDE.md](GUIDE.md)** -- คู่มือสำหรับมนุษย์และคำอธิบายแบบเข้าใจง่าย:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- ข้อกำหนดรูปแบบการสื่อสารและน้ำเสียงของ agent
- **[UI.md](saipen/UI.md)** -- แนวทางการออกแบบ UI สไตล์ Vintage Golden
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- สถานการณ์ทดสอบพฤติกรรมและกฎการตรวจสอบความถูกต้อง

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


