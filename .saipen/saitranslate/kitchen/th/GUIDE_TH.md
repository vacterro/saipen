<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# คู่มือ SAIPEN (ไทย)

[TRANSLATED TH]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## เริ่มต้นอย่างรวดเร็ว

## คำสั่ง

## สิ่งที่ควรรู้
- กลับมาแล้วเจอการเปลี่ยนแปลงที่ยังไม่ได้ commit? เป็นเรื่องปกติ -- SAIPEN จะ commit ตอน `ship` เท่านั้น ไม่ใช่ทุกขั้นตอน เอเจนต์จะตรวจสอบก่อนว่าการเปลี่ยนแปลงนั้นเป็นของใคร ก่อนที่จะแตะต้องอะไร
- อยากให้มันจำการตัดสินใจด้านสถาปัตยกรรมจริงๆ ไหม? ใส่ไว้ใน `.saipen/KNOWLEDGE/` เป็นไฟล์ `decisions.md` หรือไฟล์ที่มีหมายเลข `ADR-001.md`
- เครื่องนี้ไม่มี git หรือ shell? เอเจนต์จะบอกตรงๆ (`mode`, `WAIT: <category> -- <คำถาม>`) แทนที่จะเดา (หมวดหมู่เป็นหนึ่งในเจ็ด: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; บอกว่าคำตอบแบบไหนที่จะปลดล็อคสถานการณ์)
- อยากได้ตาข่ายนิรภัยไหม? `python <saipen-clone>/tools/install_hook.py` จะติดตั้งการตรวจสอบก่อน commit