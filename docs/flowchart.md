# Flowchart: การประมวลผลเอกสารและการป้องกันเหตุการณ์ไม่คาดฝัน

แผนภาพนี้สอดคล้องกับโค้ดจริงใน `core.py` (`DocumentProcessor.run`) และ `app.py`
(`DesktopApp._run` / `start_processing` / `stop_processing`) รวมถึงจุดป้องกันความเสี่ยง
ที่เพิ่มเข้ามาเพื่อรองรับไฟดับ / เน็ตหลุด / ดิสก์เต็ม

## หลักการสำคัญ (ต่างจาก flowchart เดิม)

- **ไม่มีการอ่าน `history.json` เพื่อหาจุด resume** — `history.json` ใช้เก็บ *สรุปผลของแต่ละ
  รอบ* สำหรับหน้าประวัติเท่านั้น ไม่ได้เป็นตัวบอกว่าไฟล์ไหนทำไปแล้ว
- **จุด resume จริงคือโฟลเดอร์ต้นทาง** — ไฟล์จะถูกย้ายออกจากต้นทางก็ต่อเมื่อประมวลผล
  **สำเร็จสมบูรณ์แล้วเท่านั้น** (`move_to_loan_folder` / `move_to_manual`) ดังนั้นทุกครั้งที่
  กด "เริ่มประมวลผล" ระบบจะสแกนโฟลเดอร์ต้นทางใหม่ (`find_newdocs_folders` + `find_pdfs`)
  แล้วเจอเฉพาะไฟล์ที่ยังไม่เสร็จโดยอัตโนมัติ — ไม่ต้องพึ่ง checkpoint ไฟล์ใด ๆ
- **การหยุดแบบ graceful (`stop_flag`)** ถูกตรวจสอบระหว่างไฟล์เท่านั้น (ไม่ใช่กลางไฟล์)
  ไฟล์ที่กำลังประมวลผลอยู่จะทำจนเสร็จก่อนจึงหยุด

```mermaid
flowchart TD
    START([เริ่มทำงาน หรือกด 'เริ่มประมวลผล'<br/>app.py: start_processing]) --> SCAN

    SCAN["สแกนโฟลเดอร์ต้นทางสด ๆ<br/>find_newdocs_folders + find_pdfs<br/>(ไฟล์ที่เคยทำสำเร็จจะไม่เจอ เพราะถูกย้ายออกไปแล้ว)"] --> CHECK

    CHECK{มีไฟล์ค้างอยู่ใน<br/>โฟลเดอร์ต้นทางไหม?}
    CHECK -- ไม่มีไฟล์เหลือ --> DONE_ALL[ประมวลผลเสร็จสิ้นครบทุกไฟล์<br/>บันทึก history.json ผ่าน<br/>_atomic_write_json (เขียนแบบ atomic)]
    CHECK -- มีไฟล์เหลือ --> STOPCHECK

    STOPCHECK{ผู้ใช้กดปุ่ม 'หยุด'?<br/>stop_flag.is_set&#40;&#41;}
    STOPCHECK -- กดหยุด --> GRACEFUL
    STOPCHECK -- ไม่ได้กด --> PICK

    PICK["หยิบไฟล์ถัดไป 1 ไฟล์<br/>ส่งให้ AI ผ่าน extract_data / _call_ai"] --> AICHECK

    AICHECK{AI เรียกสำเร็จ<br/>และอ่านข้อมูลได้?}
    AICHECK -- "เน็ตหลุด/error ทั่วไป<br/>(retry 3 ครั้งถ้าเป็น 429/quota)" --> MANUAL1
    AICHECK -- อ่านได้ --> VALIDATE

    VALIDATE{ผ่านการตรวจสอบ<br/>4 red box ไหม?}
    VALIDATE -- ไม่ผ่าน --> MANUAL2["move_to_manual<br/>(ครอบด้วย try/except)"]
    VALIDATE -- ผ่าน --> SAFEMOVE

    MANUAL1["move_to_manual<br/>(ครอบด้วย try/except)"] --> MOVEFAIL1
    MANUAL2 --> MOVEFAIL2

    MOVEFAIL1{ย้ายไป Manual สำเร็จ?}
    MOVEFAIL1 -- "ล้มเหลว (เช่นดิสก์เต็ม)<br/>ไม่ raise ทำให้ loop หยุด<br/>ไฟล์ยังอยู่ในต้นทาง" --> RESULT_ERR1[emit_result: error<br/>ข้ามไปไฟล์ถัดไป]
    MOVEFAIL1 -- สำเร็จ --> RESULT_MANUAL1[emit_result: manual<br/>total_manual += 1]

    MOVEFAIL2{ย้ายไป Manual สำเร็จ?}
    MOVEFAIL2 -- ล้มเหลว --> RESULT_ERR2[emit_result: error<br/>ข้ามไปไฟล์ถัดไป]
    MOVEFAIL2 -- สำเร็จ --> RESULT_MANUAL2[emit_result: manual<br/>total_manual += 1]

    SAFEMOVE["move_to_loan_folder<br/>ใช้ _safe_move&#40;&#41;<br/>(ครอบด้วย try/except)"] --> SAFEMOVECHECK

    SAFEMOVECHECK{ย้ายไปโฟลเดอร์ประเภทกู้สำเร็จ?}
    SAFEMOVECHECK -- ล้มเหลว --> FALLBACK["fallback: move_to_manual<br/>(ครอบด้วย try/except ชั้นนอก)"]
    SAFEMOVECHECK -- สำเร็จ --> RESULT_OK[emit_result: success<br/>total_ok += 1]

    FALLBACK --> CHECK

    RESULT_ERR1 --> CHECK
    RESULT_MANUAL1 --> CHECK
    RESULT_ERR2 --> CHECK
    RESULT_MANUAL2 --> CHECK
    RESULT_OK --> CHECK

    GRACEFUL["กลไกหยุดอย่างปลอดภัย (Graceful Stop)<br/>ไม่ตัดไฟล์ที่กำลังทำอยู่ ทำจนเสร็จก่อน<br/>แล้วจึงหยุด loop"] --> SAVEHIST

    SAVEHIST["บันทึกสถานะล่าสุดลง history.json<br/>ผ่าน append_history -> _atomic_write_json<br/>(เขียนไฟล์ tmp แล้ว os.replace แบบ atomic)"] --> IDLE

    DONE_ALL --> IDLE
    IDLE([ระบบหยุดนิ่ง รอผู้ใช้กด<br/>'เริ่มประมวลผล' อีกครั้ง])

    CRASH["เหตุไม่คาดฝันกลางทาง<br/>(ไฟดับ / โปรแกรมถูกฆ่า / เน็ตหลุดหนัก)"] -.-> RECOVER
    RECOVER["ไม่มี exception ให้จับ<br/>ไฟล์ที่กำลังทำอยู่ยังไม่ถูกย้าย (ปลอดภัย)<br/>ไฟล์ก่อนหน้าทั้งหมดถูกย้ายสำเร็จแล้ว (ปลอดภัย)<br/>รอบนี้จะไม่ถูกบันทึกใน history.json"] -.-> START

    style GRACEFUL fill:#ffe0cc,stroke:#e06c00
    style CRASH fill:#ffd6d6,stroke:#c62828
    style RECOVER fill:#fff3cd,stroke:#e0a800
    style SAFEMOVE fill:#d6f5d6,stroke:#2e7d32
    style SAVEHIST fill:#d6f5d6,stroke:#2e7d32
```

## จุดป้องกันความเสี่ยงที่เพิ่มเข้ามา (แก้ไขในโค้ดแล้ว)

| ความเสี่ยงเดิม | การป้องกันที่เพิ่ม | ตำแหน่งโค้ด |
|---|---|---|
| `shutil.move` ข้าม filesystem/ไดรฟ์ อาจเหลือไฟล์ปลายทางไม่สมบูรณ์ถ้าไฟดับกลาง copy | เพิ่ม `DocumentProcessor._safe_move`: copy ไปไฟล์ชั่วคราว `.part` ก่อน, `fsync`, แล้ว `os.replace` (atomic rename) ไปชื่อจริง จากนั้นจึงลบไฟล์ต้นฉบับ ถ้าถูกขัดจังหวะ จะเหลือแค่ไฟล์ `.part` ค้าง ไฟล์จริงในต้นทางยังอยู่ครบ | `core.py` — `_safe_move`, ใช้ใน `move_to_manual` และ `move_to_loan_folder` |
| `config.json` / `history.json` / prompt version files เขียนแบบตรง ๆ (`open(...,"w")` + `json.dump`) เสี่ยง JSON เสียหายถ้าไฟดับตอนเขียน | เปลี่ยนให้ทุกจุดเขียนผ่าน `_atomic_write_json` ที่มีอยู่แล้วในไฟล์ (เขียนลง temp file, `fsync`, แล้ว `os.replace`) | `core.py` — `save_config`, `_write_prompt_version_file`, `append_history` |
| กรณีดิสก์เต็มระหว่างย้ายไฟล์ไป Manual (สาขา "AI อ่านไม่ได้" และ "validate ไม่ผ่าน") ไม่มี `try/except` ครอบ ทำให้ exception ลอยขึ้นไปหยุดทั้ง batch | ครอบทั้งสองจุดด้วย `try/except` — ถ้าย้ายไม่สำเร็จ จะ log error, `emit_result` เป็น "error" แล้ว `continue` ไปไฟล์ถัดไปโดยไม่ทำให้ loop หยุดทั้งหมด ไฟล์ที่ย้ายไม่สำเร็จยังอยู่ในต้นทาง รอถูกลองใหม่อัตโนมัติในรอบถัดไป | `core.py` — ใน `DocumentProcessor.run()` สาขา `data is None` และสาขา `validate` error |

## จุดที่ยังเป็นข้อจำกัดโดยธรรมชาติ (ไม่สามารถป้องกันได้ 100%)

- ถ้าไฟดับ**ระหว่าง**การเรียก AI (ก่อนได้ผลลัพธ์) ไฟล์นั้นจะยังไม่ถูกย้ายไปไหน ปลอดภัย
  แต่ round นั้นจะไม่ถูกบันทึกลง `history.json` เพราะ `append_history` ถูกเรียกหลัง
  `processor.run()` คืนค่าสำเร็จเท่านั้น (`app.py: _run`) — ไม่กระทบไฟล์งานจริง กระทบแค่
  ประวัติการแสดงผล
