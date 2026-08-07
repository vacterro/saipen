<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# คู่มือ SAIPEN (ไทย)

SAIPEN คือสมุดบันทึกในโฟลเดอร์ .saipen/ สำหรับเอเจนต์ AI

AI agents have one fatal flaw: they forget. Close the window and everything they learned about your project is gone — what you were building, what failed, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch. SAIPEN is the fix: a persistent notebook in the .saipen/ folder. The agent reads STATE and BOARD on startup, sees exactly where it left off, and gets back to work without a single repeated word.

**คีย์ลัด:** `cc` ให้ Goal Mode ที่กำลังทำงานอยู่ดำเนินต่อ, `sss` แสดงสถานะโดยไม่แตะโค้ด และ `ss` บันทึกจุดตรวจสอบแล้วหยุด [ดูแผนที่ปุ่มลัดทั้ง 15 รายการ](../saipen/RFC.md#110-command-surface) ปุ่มอักษรซีริลลิกที่มีรูปเหมือนกันก็ใช้ได้: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`

## เริ่มต้นอย่างรวดเร็ว

1. **ติดตั้งเพียงครั้งเดียวต่อเครื่อง:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **เริ่มโปรเจ็กต์:**
> `saipen set`

3. **ทำงาน:**
> `saipen`

## คำสั่ง

| คำสั่ง | การกระทำ |
|---|---|
| `saipen set` | เริ่มต้นโฟลเดอร์หน่วยความจำ `.saipen/` |
| `saipen continue` | ดำเนินการทำงานจากบันทึก |
| `saipen stop` | บันทึกความคืบหน้า & หยุด |
| `saipen status` | อ่านกระดาน & สถานะ |
| `saipen goal <text>` | ปรับเปลี่ยนไปยังเป้าหมายใหม่ |
| `saipen clean` | ทำความสะอาดที่เก็บข้อมูลอย่างลึกซึ้ง |
| `saipen translate` | สร้างงานแปลภาษา 32 ภาษาแยกต่างหาก |
| `saipen markhunt` | ตรวจสอบเชิงลึกไม่จำกัด -- บันทึกสิ่งที่พบเท่านั้น ไม่แก้ไข |
| `saipen prepare` | แพ็คงานเพื่อส่งต่อให้เอเจนต์ถัดไป |
| `saipen ship` | เรียกใช้โฟลว์การเปิดตัว |

## สิ่งที่ควรรู้
- กลับมาแล้วเจอการเปลี่ยนแปลงที่ยังไม่ได้ commit? เป็นเรื่องปกติ -- SAIPEN จะ commit ตอน `ship` เท่านั้น ไม่ใช่ทุกขั้นตอน เอเจนต์จะตรวจสอบก่อนว่าการเปลี่ยนแปลงนั้นเป็นของใคร ก่อนที่จะแตะต้องอะไร
- อยากให้มันจำการตัดสินใจด้านสถาปัตยกรรมจริงๆ ไหม? ใส่ไว้ใน `.saipen/KNOWLEDGE/` เป็นไฟล์ `decisions.md` หรือไฟล์ที่มีหมายเลข `ADR-001.md`
- เครื่องนี้ไม่มี git หรือ shell? เอเจนต์จะบอกตรงๆ (`mode`, `WAIT: <category> -- <คำถาม>`) แทนที่จะเดา (หมวดหมู่เป็นหนึ่งในเจ็ด: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; บอกว่าคำตอบแบบไหนที่จะปลดล็อคสถานการณ์)
- อยากได้ตาข่ายนิรภัยไหม? `python <saipen-clone>/tools/install_hook.py` จะติดตั้งการตรวจสอบก่อน commit

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.


