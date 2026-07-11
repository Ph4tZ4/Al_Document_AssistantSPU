# ระบบผู้ช่วยเอกสาร AI (กยศ.) — แผนภาพ Workflow ฉบับละเอียดที่สุดสำหรับ Miro (ภาษาไทย)

> **วิธีนำไปใช้ใน Miro**:
> 1. ในโปรแกรม Miro ให้กดเครื่องหมาย **+** หรือเมนู **Apps** ด้านซ้ายมือ แล้วค้นหาแอป **Mermaid**
> 2. คัดลอกโค้ดในบล็อก `mermaid` ของแต่ละหัวข้อด้านล่าง ไปวางในช่องของ Mermaid ใน Miro
> 3. กด **Generate** Miro จะสร้างแผนภาพให้อัตโนมัติ สามารถย้าย ปรับขนาด หรือเปลี่ยนสีได้ทันที

---

## 1. 🏗️ ภาพรวมสถาปัตยกรรมทั้งระบบ (System Architecture Overview)

```mermaid
graph TB
    subgraph USER_LAYER["👤 ชั้นผู้ใช้งาน"]
        USER["เจ้าหน้าที่ กยศ.<br/>เปิดโปรแกรมผู้ช่วยเอกสาร AI"]
    end

    subgraph APP_LAYER["🖥️ ชั้นแอปพลิเคชัน — โปรแกรมเดสก์ท็อป"]
        direction TB
        subgraph PYWEBVIEW["หน้าจอเว็บ pywebview"]
            direction LR
            HTML["web/index.html<br/>โครงสร้างหน้าเว็บ"]
            CSS["web/style.css<br/>สไตล์และรูปแบบ"]
            JS["web/app.js<br/>ตัวควบคุมหน้าบ้าน"]
        end

        ENTRY["app.py<br/>จุดเริ่มต้นโปรแกรม<br/>สะพานเชื่อม pywebview + API"]
    end

    subgraph CORE_LAYER["⚙️ ชั้นประมวลผลหลัก"]
        CORE["core.py<br/>เครื่องจักรประมวลผลเอกสาร"]
        
        subgraph MODULES["โมดูลย่อยภายใน"]
            CONFIG["จัดการการตั้งค่า<br/>โหลด / บันทึก Config"]
            HISTORY["จัดการประวัติ<br/>โหลด / เพิ่มประวัติ"]
            DISCOVERY["ค้นหาไฟล์<br/>ค้นหาโฟลเดอร์ / ค้นหาเอกสาร"]
            IMAGE_PREP["เตรียมรูปภาพ<br/>ย่อขนาด / แปลงรูปแบบ"]
            AI_EXTRACT["ดึงข้อมูลด้วย AI<br/>ส่งเอกสาร / รับผลลัพธ์"]
            VALIDATE["เครื่องตรวจสอบ<br/>ตรวจข้อมูล / ตรวจเลขบัตร"]
            FILE_OPS["จัดการไฟล์<br/>ย้ายไปโฟลเดอร์ / เปลี่ยนชื่อ"]
        end
    end

    subgraph EXTERNAL["☁️ บริการภายนอก"]
        GEMINI["Google Gemini API<br/>รุ่น gemini-3.1-flash-lite<br/>อ่านเอกสาร + ดึงข้อมูล"]
    end

    subgraph STORAGE["💾 ชั้นจัดเก็บข้อมูล"]
        CONFIG_JSON["config.json<br/>คีย์ API, เส้นทางโฟลเดอร์,<br/>ธีม, พร็อมท์"]
        HISTORY_JSON["history.json<br/>ประวัติการประมวลผล<br/>เก็บสูงสุด 200 รายการ"]
        SOURCE_DIR["📁 โฟลเดอร์ต้นทาง<br/>NewDocs / NewDocs 2 / ..."]
        OUTPUT_DIR["📁 โฟลเดอร์ปลายทาง<br/>Type1/ Type2/ Type3/<br/>Type4/ Manual/"]
    end

    USER --> ENTRY
    ENTRY --> PYWEBVIEW
    JS <-->|"เรียกผ่าน pywebview.api"| ENTRY
    ENTRY --> CORE
    CORE --> MODULES
    AI_EXTRACT -->|"เรียก API ผ่านอินเทอร์เน็ต"| GEMINI
    CONFIG --> CONFIG_JSON
    HISTORY --> HISTORY_JSON
    DISCOVERY --> SOURCE_DIR
    FILE_OPS --> OUTPUT_DIR
```

---

## 2. 🚀 ขั้นตอนการเริ่มต้นโปรแกรม (Application Startup Flow)

```mermaid
flowchart TD
    START(["▶️ เริ่มต้น<br/>python app.py"]) --> CHECK_PACK{"ตรวจสอบว่าเป็น<br/>ไฟล์ .exe ที่แพ็คแล้ว?"}
    
    CHECK_PACK -->|"ใช่ — เป็นไฟล์ .exe"| PATH_PACK["ใช้เส้นทางจาก<br/>PyInstaller Bundle"]
    CHECK_PACK -->|"ไม่ใช่ — โหมดพัฒนา"| PATH_DEV["ใช้เส้นทางของไฟล์<br/>ปัจจุบัน"]
    
    PATH_PACK --> CREATE_API["สร้างตัวจัดการ API<br/>- หน้าต่าง = ยังไม่มี<br/>- ตัวประมวลผล = ยังไม่มี<br/>- เธรดงาน = ยังไม่มี<br/>- ตัวนับเวลา = ยังไม่มี"]
    PATH_DEV --> CREATE_API
    
    CREATE_API --> FIND_HTML["ค้นหาไฟล์ web/index.html<br/>ในโฟลเดอร์ทรัพยากร"]
    
    FIND_HTML --> CREATE_WINDOW["สร้างหน้าต่างโปรแกรม<br/>- ชื่อ: ผู้ช่วยเอกสาร AI — กยศ.<br/>- ขนาด: 1200x800 พิกเซล<br/>- ขนาดต่ำสุด: 960x640<br/>- พื้นหลัง: สีเทาอ่อน"]
    
    CREATE_WINDOW --> BIND_API["ผูกหน้าต่างกับ<br/>ตัวจัดการ API"]
    
    BIND_API --> START_WEBVIEW["เปิดแสดงหน้าต่าง GUI<br/>เริ่ม pywebview"]
    
    START_WEBVIEW --> HTML_LOAD["เบราว์เซอร์โหลด<br/>HTML / CSS / JavaScript"]
    
    HTML_LOAD --> READY_EVENT{"เว็บพร้อมใช้งาน?"}
    
    READY_EVENT -->|"พร้อม"| BOOT_SYSTEM["เรียกฟังก์ชันเริ่มต้นระบบ"]
    READY_EVENT -->|"รอ 400 มิลลิวินาที"| BOOT_SYSTEM
    
    BOOT_SYSTEM --> LOAD_CONFIG["โหลดการตั้งค่า<br/>เรียกข้อมูลจาก Python"]
    LOAD_CONFIG --> SET_THEME["ตั้งค่าธีม<br/>โหมดสว่าง / โหมดมืด"]
    SET_THEME --> FILL_FIELDS["เติมค่าลงในฟอร์ม<br/>คีย์ API, โฟลเดอร์ต้นทาง,<br/>โฟลเดอร์ปลายทาง, พร็อมท์"]
    FILL_FIELDS --> REFRESH_COUNT["นับจำนวนเอกสาร<br/>ในโฟลเดอร์ต้นทาง"]
    
    BOOT_SYSTEM --> LOAD_DASHBOARD["โหลดข้อมูลแดชบอร์ด<br/>สถิติสะสมจากประวัติ"]
    LOAD_DASHBOARD --> RENDER_DASHBOARD["แสดงหน้าแดชบอร์ด<br/>- การ์ดสถิติ 4 ใบ<br/>- กราฟ 7 วัน<br/>- กิจกรรมล่าสุด"]
    
    BOOT_SYSTEM --> GO_DASH["เปิดหน้าแดชบอร์ด<br/>เป็นหน้าเริ่มต้น"]
    
    RENDER_DASHBOARD --> RUNNING(("✅ พร้อมใช้งาน"))
```

---

## 3. ⚙️ การจัดการการตั้งค่าระบบ (Configuration & Persistence Flow)

```mermaid
flowchart TD
    subgraph LOAD_CONFIG["📖 ขั้นตอนการโหลดการตั้งค่า"]
        L1["เรียกฟังก์ชันโหลดการตั้งค่า"] --> L2["สร้างค่าเริ่มต้น<br/>คีย์ API: ว่าง<br/>โฟลเดอร์ต้นทาง: ว่าง<br/>โฟลเดอร์ปลายทาง: ว่าง<br/>ธีม: สว่าง<br/>พร็อมท์: ว่าง"]
        L2 --> L3{"อ่านไฟล์ config.json<br/>ได้หรือไม่?"}
        L3 -->|"อ่านได้"| L4["รวมค่าจากไฟล์<br/>เข้ากับค่าเริ่มต้น"]
        L3 -->|"อ่านไม่ได้<br/>ไฟล์ไม่มี/เสียหาย"| L5["ใช้ค่าเริ่มต้น"]
        L4 --> L6{"คีย์ API ว่างอยู่?"}
        L5 --> L6
        L6 -->|"ว่าง"| L7["ดึงจากตัวแปรสภาพแวดล้อม<br/>GEMINI_API_KEY"]
        L6 -->|"มีค่าแล้ว"| L8{"พร็อมท์ว่าง?"}
        L7 --> L8
        L8 -->|"ว่าง"| L9["ใช้พร็อมท์เริ่มต้น<br/>ที่ฝังไว้ในโปรแกรม"]
        L8 -->|"มีค่าแล้ว"| L10["✅ ส่งค่าตั้งค่ากลับ"]
        L9 --> L10
    end

    subgraph SAVE_CONFIG["💾 ขั้นตอนการบันทึกการตั้งค่า"]
        S1["เรียกฟังก์ชันบันทึกการตั้งค่า<br/>พร้อมค่าใหม่"] --> S2["โหลดค่าปัจจุบัน"]
        S2 --> S3["รวมเฉพาะ key ที่<br/>อยู่ในรายการที่อนุญาต"]
        S3 --> S4["เขียนไฟล์ config.json<br/>รูปแบบ UTF-8 ย่อหน้า 2 ช่อง"]
        S4 --> S5["✅ ส่งค่าตั้งค่าที่อัพเดทแล้วกลับ"]
    end

    subgraph CONFIG_PATH["📂 ตำแหน่งจัดเก็บไฟล์ตั้งค่า"]
        P1{"ระบบปฏิบัติการ?"}
        P1 -->|"วินโดวส์"| P2["โฟลเดอร์ AppData<br/>ของผู้ใช้วินโดวส์"]
        P1 -->|"แมค"| P3["โฟลเดอร์ Library/<br/>Application Support/"]
        P1 -->|"ลินุกซ์"| P4["โฟลเดอร์ .config/<br/>ของผู้ใช้"]
        P2 --> P5["config.json<br/>history.json"]
        P3 --> P5
        P4 --> P5
    end
```

---

## 4. 📄 ขั้นตอนหลักการประมวลผลเอกสาร (Main Document Processing Flow)

```mermaid
flowchart TD
    START_PROC(["▶️ กดปุ่ม<br/>เริ่มประมวลผล"]) --> JS_START["เรียกฟังก์ชันเริ่มประมวลผล<br/>ในตัวควบคุมหน้าบ้าน"]
    
    JS_START --> CHECK_API{"มีคีย์ API<br/>หรือยัง?"}
    CHECK_API -->|"ยังไม่มี"| TOAST_API["❌ แจ้งเตือน: กรุณาตั้งค่า<br/>คีย์ API ก่อน<br/>เปลี่ยนไปหน้าตั้งค่า"]
    CHECK_API -->|"มีแล้ว"| CHECK_DIRS{"เลือกโฟลเดอร์<br/>ต้นทางและปลายทาง<br/>แล้วหรือยัง?"}
    
    CHECK_DIRS -->|"ยังไม่ได้เลือก"| TOAST_DIRS["❌ แจ้งเตือน: กรุณาเลือก<br/>โฟลเดอร์ก่อน"]
    CHECK_DIRS -->|"เลือกแล้ว"| CHECK_CONN{"เชื่อมต่อกับ<br/>Python ได้หรือไม่?"}
    
    CHECK_CONN -->|"ไม่ได้ — โหมดตัวอย่าง"| TOAST_DEMO["❌ แจ้งเตือน: โหมดตัวอย่าง<br/>ต้องเชื่อมต่อ Python"]
    CHECK_CONN -->|"เชื่อมต่อได้"| PREP_UI["เตรียมหน้าจอ<br/>- ล้างผลลัพธ์เก่า / ล้างบันทึก<br/>- ตั้งความคืบหน้า = 0%<br/>- ปิดปุ่มเริ่ม / เปิดปุ่มหยุด"]
    
    PREP_UI --> COUNT_FILES["นับจำนวนเอกสาร<br/>ในโฟลเดอร์ต้นทาง"]
    COUNT_FILES --> CALL_PY["ส่งคำสั่งไปยัง Python<br/>เรียก start_processing"]
    
    CALL_PY --> PY_RECV["Python รับคำสั่ง<br/>ที่ฝั่ง app.py"]
    
    PY_RECV --> CHECK_WORKER{"มีเธรดงาน<br/>กำลังทำงานอยู่?"}
    CHECK_WORKER -->|"มี — กำลังทำอยู่"| ERR_BUSY["❌ ส่งข้อผิดพลาด:<br/>กำลังประมวลผลอยู่แล้ว"]
    CHECK_WORKER -->|"ไม่มี — ว่างอยู่"| LOAD_CFG["โหลดการตั้งค่า<br/>ดึงคีย์ API, โฟลเดอร์ต้นทาง,<br/>โฟลเดอร์ปลายทาง"]
    
    LOAD_CFG --> CHECK_VALID{"ข้อมูลครบถ้วน<br/>หรือไม่?"}
    CHECK_VALID -->|"ไม่ครบ"| ERR_INVALID["❌ ส่งข้อผิดพลาด:<br/>ข้อมูลไม่ครบ"]
    CHECK_VALID -->|"ครบถ้วน"| CREATE_DIRS["สร้างโฟลเดอร์ปลายทาง<br/>ถ้ายังไม่มี"]
    
    CREATE_DIRS --> CREATE_PROC["สร้างตัวประมวลผลเอกสาร<br/>- คีย์ API<br/>- พร็อมท์ (กำหนดเอง หรือ เริ่มต้น)<br/>- ฟังก์ชันส่งบันทึก<br/>- ฟังก์ชันส่งผลลัพธ์"]
    
    CREATE_PROC --> CHECK_PROC_OK{"สร้างสำเร็จ<br/>หรือไม่?"}
    CHECK_PROC_OK -->|"ไม่สำเร็จ"| ERR_MODEL["❌ ส่งข้อผิดพลาด:<br/>เริ่มต้นโมเดลไม่สำเร็จ"]
    CHECK_PROC_OK -->|"สำเร็จ"| START_TICKER["เริ่มเธรดนับเวลา<br/>ส่งเวลาที่ผ่านไปทุก 1 วินาที<br/>ไปแสดงบนหน้าจอ"]
    
    START_TICKER --> START_WORKER["เริ่มเธรดงานประมวลผล<br/>ทำงานเบื้องหลัง"]
    
    START_WORKER --> EXEC_PROCESS["⚙️ เรียกฟังก์ชันประมวลผลหลัก<br/>(ดูแผนภาพที่ 5)"]
    
    EXEC_PROCESS --> CHECK_DONE{"ประมวลผลเสร็จ<br/>โดยปกติ?"}
    CHECK_DONE -->|"เสร็จปกติ"| CHECK_COUNT{"มีเอกสาร<br/>ที่ประมวลผลได้?"}
    CHECK_DONE -->|"เกิดข้อผิดพลาดร้ายแรง"| LOG_FATAL["📝 บันทึก: เกิดข้อผิดพลาด<br/>สร้างผลสรุปว่าง"]
    
    CHECK_COUNT -->|"มี"| SAVE_HIST["บันทึกประวัติการทำงาน<br/>เก็บสูงสุด 200 รายการ"]
    CHECK_COUNT -->|"ไม่มี"| SEND_SUMMARY
    SAVE_HIST --> SEND_SUMMARY
    LOG_FATAL --> SEND_SUMMARY
    
    SEND_SUMMARY["ส่งผลสรุปกลับไปหน้าจอ"] --> RECV_SUMMARY["หน้าจอรับผลสรุป<br/>- เปิดปุ่มเริ่มใหม่<br/>- แสดงเวลาทั้งหมด<br/>- อัพเดทสถิติ<br/>- แจ้งเตือนผลสรุป<br/>- โหลดแดชบอร์ดใหม่"]
    
    RECV_SUMMARY --> END_PROC(("✅ เสร็จสิ้น"))
```

---

## 5. 🔄 ลูปการประมวลผลหลัก (Core Processing Loop)

```mermaid
flowchart TD
    RUN_START(["⚙️ เริ่มประมวลผล"]) --> LOG_START["📝 บันทึก: เริ่มต้น<br/>ค้นหาโฟลเดอร์เอกสาร"]
    
    LOG_START --> FIND_FOLDERS["ค้นหาโฟลเดอร์ NewDocs*<br/>ในโฟลเดอร์ต้นทาง"]
    
    FIND_FOLDERS --> CHECK_NAME{"โฟลเดอร์ต้นทาง<br/>ชื่อขึ้นต้นด้วย<br/>'NewDocs' หรือไม่?"}
    CHECK_NAME -->|"ใช่"| USE_SINGLE["ใช้โฟลเดอร์ต้นทาง<br/>เป็นโฟลเดอร์เดียว"]
    CHECK_NAME -->|"ไม่ใช่"| FIND_GLOB["ค้นหาด้วยรูปแบบ NewDocs*<br/>เรียงตามตัวอักษร"]
    
    USE_SINGLE --> CHECK_FOUND{"พบโฟลเดอร์<br/>หรือไม่?"}
    FIND_GLOB --> CHECK_FOUND
    
    CHECK_FOUND -->|"ไม่พบเลย"| LOG_NOT_FOUND["📝 บันทึก: ❌ ไม่พบโฟลเดอร์<br/>ที่ชื่อขึ้นต้นด้วย NewDocs"]
    CHECK_FOUND -->|"พบ"| INIT_COUNTERS["ตั้งตัวนับ<br/>จำนวนสำเร็จ = 0<br/>จำนวนตรวจสอบ = 0<br/>ลำดับ = 0"]
    
    LOG_NOT_FOUND --> RETURN_SUM
    
    INIT_COUNTERS --> LOOP_FOLDERS{"📁 วนลูปแต่ละโฟลเดอร์"}
    
    LOOP_FOLDERS --> CHECK_STOP_1{"ผู้ใช้สั่งหยุด<br/>หรือไม่?"}
    CHECK_STOP_1 -->|"สั่งหยุด"| RETURN_SUM
    CHECK_STOP_1 -->|"ยังไม่หยุด"| FIND_DOCS["ค้นหาเอกสารในโฟลเดอร์<br/>.pdf, .jpg, .png, .tiff ฯลฯ"]
    
    FIND_DOCS --> LOG_FOLDER["📝 บันทึก: พบโฟลเดอร์ X<br/>มีเอกสาร N ไฟล์"]
    
    LOG_FOLDER --> LOOP_DOCS{"📄 วนลูปแต่ละเอกสาร"}
    
    LOOP_DOCS --> CHECK_STOP_2{"ผู้ใช้สั่งหยุด<br/>หรือไม่?"}
    CHECK_STOP_2 -->|"สั่งหยุด"| LOG_STOP["📝 บันทึก: ⚠️ ผู้ใช้<br/>สั่งหยุดกลางคัน"]
    LOG_STOP --> RETURN_SUM
    CHECK_STOP_2 -->|"ยังไม่หยุด"| INC_INDEX["เพิ่มลำดับ +1"]
    
    INC_INDEX --> LOG_FILE["📝 บันทึก: กำลังประมวลผล<br/>ไฟล์ที่ N: ชื่อไฟล์"]
    
    LOG_FILE --> AI_EXTRACT["ดึงข้อมูลจากเอกสารด้วย AI<br/>(ดูแผนภาพที่ 6)"]
    
    AI_EXTRACT --> CHECK_DATA{"AI ดึงข้อมูล<br/>ได้หรือไม่?"}
    
    CHECK_DATA -->|"ไม่ได้ — ข้อมูลว่าง"| MOVE_MANUAL_1["ย้ายไป Manual/<br/>เหตุผล: AI อ่านไฟล์ไม่ได้"]
    MOVE_MANUAL_1 --> INC_MANUAL_1["จำนวนตรวจสอบ +1"]
    INC_MANUAL_1 --> EMIT_MANUAL_1["ส่งผลลัพธ์ไปหน้าจอ<br/>สถานะ: ต้องตรวจสอบ"]
    EMIT_MANUAL_1 --> LOOP_DOCS
    
    CHECK_DATA -->|"ได้ — มีข้อมูล"| VALIDATE_DATA["ตรวจสอบความถูกต้อง<br/>(ดูแผนภาพที่ 7)"]
    
    VALIDATE_DATA --> CHECK_VALID{"ผ่านการตรวจสอบ<br/>ทุกเงื่อนไข?"}
    
    CHECK_VALID -->|"ไม่ผ่าน — มีข้อผิดพลาด"| LOG_INVALID["📝 บันทึก: ⚠️ ข้อมูล<br/>ไม่ผ่านเกณฑ์"]
    LOG_INVALID --> MOVE_MANUAL_2["ย้ายไป Manual/<br/>พร้อมระบุเหตุผล"]
    MOVE_MANUAL_2 --> INC_MANUAL_2["จำนวนตรวจสอบ +1"]
    INC_MANUAL_2 --> EMIT_MANUAL_2["ส่งผลลัพธ์ไปหน้าจอ<br/>สถานะ: ต้องตรวจสอบ"]
    EMIT_MANUAL_2 --> LOOP_DOCS
    
    CHECK_VALID -->|"ผ่านทุกเงื่อนไข"| LOG_PASS["📝 บันทึก: ✅ ไฟล์<br/>ผ่านการตรวจสอบครบ"]
    
    LOG_PASS --> MOVE_LOAN["ย้ายไปโฟลเดอร์ตามลักษณะเงินกู้<br/>(ดูแผนภาพที่ 8)"]
    
    MOVE_LOAN --> CHECK_MOVE_OK{"ย้ายไฟล์สำเร็จ<br/>หรือไม่?"}
    
    CHECK_MOVE_OK -->|"สำเร็จ"| INC_OK["จำนวนสำเร็จ +1"]
    INC_OK --> EMIT_OK["ส่งผลลัพธ์ไปหน้าจอ<br/>สถานะ: สำเร็จ"]
    EMIT_OK --> LOOP_DOCS
    
    CHECK_MOVE_OK -->|"ไม่สำเร็จ — เกิดข้อผิดพลาด"| LOG_MOVE_ERR["📝 บันทึก: ❌ ย้ายไฟล์<br/>ไม่สำเร็จ"]
    LOG_MOVE_ERR --> MOVE_MANUAL_3["ย้ายไป Manual/"]
    MOVE_MANUAL_3 --> INC_MANUAL_3["จำนวนตรวจสอบ +1"]
    INC_MANUAL_3 --> EMIT_MANUAL_3["ส่งผลลัพธ์ไปหน้าจอ<br/>สถานะ: ต้องตรวจสอบ"]
    EMIT_MANUAL_3 --> LOOP_DOCS
    
    LOOP_DOCS -->|"หมดทุกไฟล์<br/>ในโฟลเดอร์"| LOOP_FOLDERS
    
    LOOP_FOLDERS -->|"หมดทุกโฟลเดอร์"| LOG_DONE["📝 บันทึก: ✅ ประมวลผลเสร็จสิ้น<br/>สำเร็จ X ไฟล์<br/>ต้องตรวจสอบ Y ไฟล์<br/>ใช้เวลา M นาที S วินาที"]
    
    LOG_DONE --> RETURN_SUM["ส่งผลสรุปกลับ<br/>จำนวนทั้งหมด, สำเร็จ,<br/>ต้องตรวจสอบ, เวลาที่ใช้"]
    
    RETURN_SUM --> RUN_END(("🏁 จบ"))
```

---

## 6. 🤖 กระบวนการส่งเอกสารให้ AI ดึงข้อมูล (AI Data Extraction Pipeline)

```mermaid
flowchart TD
    EXT_START(["🤖 เริ่มดึงข้อมูล<br/>จากเอกสาร"]) --> CHECK_EXT{"ชนิดของไฟล์<br/>เอกสาร?"}
    
    CHECK_EXT -->|"ไฟล์ PDF"| READ_PDF["เปิดไฟล์ PDF<br/>อ่านข้อมูลดิบ"]
    CHECK_EXT -->|"ไฟล์รูปภาพ<br/>.jpg .png ฯลฯ"| IMG_FLOW["เข้าสู่กระบวนการ<br/>จัดการรูปภาพ"]
    
    subgraph IMG_PIPELINE["🖼️ กระบวนการจัดการรูปภาพ"]
        IMG_FLOW --> PREP_LOW["เตรียมรูปภาพ<br/>ขนาดสูงสุด 2,048 พิกเซล"]
        PREP_LOW --> OPEN_IMG["เปิดรูปภาพ<br/>แปลงเป็นรูปแบบ RGB"]
        OPEN_IMG --> CHECK_SIZE{"ขนาดเกิน<br/>2,048 พิกเซล?"}
        CHECK_SIZE -->|"เกิน"| RESIZE_LOW["ย่อขนาดด้วยอัลกอริทึม LANCZOS<br/>ให้ด้านยาวสุด = 2,048 พิกเซล<br/>📝 บันทึก: ปรับขนาดรูป"]
        CHECK_SIZE -->|"ไม่เกิน"| KEEP_LOW["คงขนาดเดิม"]
        RESIZE_LOW --> KEEP_LOW
        KEEP_LOW --> SAVE_LOW["บันทึกเป็น JPEG<br/>คุณภาพ 85%<br/>เปิดการบีบอัดขั้นสูง"]
        SAVE_LOW --> CALL_AI_LOW["ส่งรูปภาพให้ AI<br/>ชนิด: image/jpeg"]
        CALL_AI_LOW --> CHECK_IDS{"AI อ่านเลขบัตร<br/>13 หลักได้หรือไม่?<br/>(อย่างน้อย 1 ตำแหน่ง)"}
        CHECK_IDS -->|"อ่านได้"| RETURN_OK["✅ ส่งข้อมูลกลับ"]
        CHECK_IDS -->|"อ่านไม่ได้ / ไม่ชัด"| LOG_RETRY["📝 บันทึก: ⚠️ อ่านเลขบัตร<br/>ไม่ชัดเจน<br/>ลองใหม่ด้วยความละเอียดสูงขึ้น"]
        LOG_RETRY --> PREP_HIGH["เตรียมรูปภาพ<br/>ขนาดสูงสุด 3,072 พิกเซล"]
        PREP_HIGH --> RESIZE_HIGH["ย่อขนาดให้ด้านยาวสุด<br/>= 3,072 พิกเซล"]
        RESIZE_HIGH --> SAVE_HIGH["บันทึกเป็น JPEG<br/>คุณภาพ 85%"]
        SAVE_HIGH --> CALL_AI_HIGH["ส่งรูปภาพให้ AI อีกครั้ง"]
        CALL_AI_HIGH --> CHECK_IDS_2{"AI อ่านเลขบัตร<br/>ได้หรือไม่?"}
        CHECK_IDS_2 -->|"อ่านได้"| RETURN_OK
        CHECK_IDS_2 -->|"ยังอ่านไม่ได้"| RETURN_PARTIAL["⚠️ ส่งข้อมูลที่อ่านได้กลับ<br/>(ถ้ามี)"]
    end
    
    READ_PDF --> CHECK_READ_OK{"อ่านไฟล์<br/>สำเร็จหรือไม่?"}
    CHECK_READ_OK -->|"ไม่สำเร็จ"| LOG_READ_ERR["📝 บันทึก: ❌ เปิดไฟล์ไม่ได้<br/>ไฟล์อาจถูกล็อกหรือเสียหาย"]
    CHECK_READ_OK -->|"สำเร็จ"| CHECK_EMPTY{"ไฟล์ว่างเปล่า<br/>หรือไม่?"}
    CHECK_EMPTY -->|"ว่างเปล่า"| LOG_EMPTY["📝 บันทึก: ❌ ไฟล์<br/>ไม่มีข้อมูลภายใน"]
    CHECK_EMPTY -->|"มีข้อมูล"| CALL_AI_PDF["ส่งไฟล์ PDF ให้ AI<br/>ชนิด: application/pdf"]
    LOG_READ_ERR --> RETURN_NULL["ส่งค่าว่างกลับ (ไม่มีข้อมูล)"]
    LOG_EMPTY --> RETURN_NULL
    
    subgraph CALL_GEMINI["☁️ กระบวนการเชื่อมต่อ Gemini API"]
        CALL_AI_PDF --> ATTEMPT_INIT["เริ่มลองส่ง<br/>ครั้งที่ 1 จาก 3 ครั้ง"]
        ATTEMPT_INIT --> LOG_SEND["📝 บันทึก: กำลังส่งเอกสาร<br/>ให้ AI อ่านและตรวจสอบ"]
        LOG_SEND --> SEND_GEMINI["ส่งไฟล์เอกสาร + พร็อมท์<br/>ไปยัง Gemini API<br/>รูปแบบตอบกลับ: JSON"]
        SEND_GEMINI --> CHECK_RESP{"การส่ง<br/>สำเร็จหรือไม่?"}
        CHECK_RESP -->|"สำเร็จ"| STRIP_MD["ลบรูปแบบ markdown<br/>ที่ติดมาออก"]
        STRIP_MD --> PARSE_JSON{"แปลง JSON<br/>สำเร็จหรือไม่?"}
        PARSE_JSON -->|"สำเร็จ"| RETURN_JSON["✅ ส่งข้อมูลกลับ"]
        PARSE_JSON -->|"ไม่สำเร็จ"| LOG_JSON_ERR["📝 บันทึก: ❌ AI ส่งข้อมูลกลับ<br/>ในรูปแบบที่อ่านไม่ได้<br/>ส่งค่าว่างกลับ"]
        
        CHECK_RESP -->|"ผิดพลาด 429<br/>ผู้ใช้หนาแน่น"| CHECK_RETRY_LIMIT{"ลองอีกได้<br/>หรือไม่?"}
        CHECK_RETRY_LIMIT -->|"ได้ — ยังไม่ครบ 3 ครั้ง"| CALC_WAIT["คำนวณเวลารอ<br/>จากข้อความผิดพลาด<br/>ค่าเริ่มต้น: 40 วินาที"]
        CALC_WAIT --> LOG_WAIT["📝 บันทึก: ⚠️ AI มีผู้ใช้<br/>หนาแน่น รอ N วินาที"]
        LOG_WAIT --> SLEEP_WAIT["หยุดรอตามเวลาที่กำหนด"]
        SLEEP_WAIT --> ATTEMPT_INIT
        CHECK_RETRY_LIMIT -->|"ไม่ได้ — ครบ 3 ครั้งแล้ว"| LOG_RATE_ERR["📝 บันทึก: ❌ เชื่อมต่อ AI<br/>ไม่สำเร็จ ส่งค่าว่างกลับ"]
        
        CHECK_RESP -->|"ผิดพลาดอื่น ๆ"| LOG_OTHER_ERR["📝 บันทึก: ❌ เกิดข้อผิดพลาด<br/>ขณะเชื่อมต่อ AI<br/>ส่งค่าว่างกลับ"]
    end
```

---

## 7. ✅ เงื่อนไขการตรวจสอบความถูกต้อง 4 ด่าน (Validation Logic)

```mermaid
flowchart TD
    VAL_START(["✅ เริ่มตรวจสอบ<br/>ความถูกต้อง"]) --> CHECK_DICT{"ข้อมูลจาก AI<br/>เป็นรูปแบบ JSON<br/>ที่ถูกต้องหรือไม่?"}
    
    CHECK_DICT -->|"ไม่ถูกต้อง"| ERR_DICT["❌ ข้อมูลจาก AI<br/>ไม่ใช่รูปแบบ JSON"]
    
    CHECK_DICT -->|"ถูกต้อง"| EXTRACT_FIELDS["ดึงค่าจากข้อมูล:<br/>- ชื่อ-นามสกุล<br/>- เลขบัตรตำแหน่งบน<br/>- เลขบัตรในเนื้อหา<br/>- ลักษณะเงินกู้<br/>- ลายเซ็น"]
    
    EXTRACT_FIELDS --> CHECK_NAME{"🔴 ด่านที่ 1<br/>พบชื่อ-นามสกุล<br/>หรือไม่?"}
    
    CHECK_NAME -->|"ไม่พบ / ว่างเปล่า"| ERR_NAME["❌ ไม่พบชื่อ-นามสกุล"]
    
    CHECK_NAME -->|"พบ"| PREP_ID{"ตรวจสอบเลขบัตรประชาชน:<br/>ตำแหน่งบน = ตรงรูปแบบ 13 หลัก?<br/>ตำแหน่งล่าง = ตรงรูปแบบ 13 หลัก?"}
    
    PREP_ID --> CHECK_ID_EXISTS{"🔴 ด่านที่ 2<br/>อ่านเลขบัตร 13 หลัก<br/>ได้อย่างน้อย 1 ตำแหน่ง?"}
    
    CHECK_ID_EXISTS -->|"อ่านไม่ได้ทั้ง 2 ตำแหน่ง"| ERR_ID_NONE["❌ อ่านเลขบัตร<br/>13 หลักไม่ได้"]
    
    CHECK_ID_EXISTS -->|"อ่านได้"| CHECK_ID_BOTH{"อ่านได้ทั้ง<br/>2 ตำแหน่ง?"}
    
    CHECK_ID_BOTH -->|"ได้ทั้งคู่"| CHECK_ID_MATCH{"เลขบัตรตำแหน่งบน<br/>ตรงกับตำแหน่งล่าง<br/>หรือไม่?"}
    CHECK_ID_MATCH -->|"ไม่ตรงกัน"| ERR_ID_MISMATCH["❌ เลขบัตรบนและล่าง<br/>ไม่ตรงกัน"]
    CHECK_ID_MATCH -->|"ตรงกัน"| CHOOSE_ID
    CHECK_ID_BOTH -->|"ได้แค่ตำแหน่งเดียว"| CHOOSE_ID
    
    CHOOSE_ID["เลือกเลขบัตรที่อ่านได้<br/>ใช้ตำแหน่งบน หรือ ล่าง"] --> CHECK_CHECKSUM{"🔴 ด่านที่ 2.5<br/>ตรวจ Checksum<br/>เลขบัตรประชาชน<br/>ด้วยอัลกอริทึม Mod-11"}
    
    CHECK_CHECKSUM --> DETAIL_CHECKSUM["วิธีตรวจสอบ Checksum:<br/>1. ดึงตัวเลข 12 หลักแรก<br/>2. คูณหลักที่ i ด้วย (13 - i)<br/>3. รวมผลลัพธ์ทั้งหมด<br/>4. หลักตรวจสอบ = (11 - ผลรวม mod 11) mod 10<br/>5. หลักตรวจสอบต้องตรงกับหลักที่ 13"]
    
    DETAIL_CHECKSUM --> CHECK_CS_OK{"Checksum<br/>ถูกต้องหรือไม่?"}
    CHECK_CS_OK -->|"ไม่ถูกต้อง"| ERR_CHECKSUM["❌ เลขบัตรประชาชน<br/>ไม่ถูกต้อง<br/>(หลักตรวจสอบไม่ผ่าน)"]
    
    CHECK_CS_OK -->|"ถูกต้อง"| CHECK_LOAN{"🔴 ด่านที่ 3<br/>ลักษณะเงินกู้<br/>อยู่ในรายการ<br/>ที่กำหนดหรือไม่?<br/>(Type1 - Type4)"}
    
    CHECK_LOAN -->|"ไม่อยู่ในรายการ"| ERR_LOAN["❌ ไม่พบลักษณะเงินกู้<br/>ที่ถูกต้อง"]
    
    CHECK_LOAN -->|"อยู่ในรายการ"| CHECK_SIGN{"🔴 ด่านที่ 4<br/>มีลายเซ็นผู้กู้<br/>หรือไม่?<br/>(signed = true)"}
    
    CHECK_SIGN -->|"ไม่มีลายเซ็น"| ERR_SIGN["❌ ไม่พบลายเซ็นผู้กู้"]
    
    CHECK_SIGN -->|"มีลายเซ็น"| VAL_PASS["✅ ผ่านทุกเงื่อนไข<br/>ไม่มีข้อผิดพลาด"]
    
    ERR_DICT --> GO_MANUAL["📁 → โฟลเดอร์ Manual/"]
    ERR_NAME --> GO_MANUAL
    ERR_ID_NONE --> GO_MANUAL
    ERR_ID_MISMATCH --> GO_MANUAL
    ERR_CHECKSUM --> GO_MANUAL
    ERR_LOAN --> GO_MANUAL
    ERR_SIGN --> GO_MANUAL
```

---

## 8. 📁 การย้ายและเปลี่ยนชื่อไฟล์ (File Operations Flow)

```mermaid
flowchart TD
    subgraph MOVE_SUCCESS["✅ ย้ายไฟล์ที่ผ่านการตรวจสอบ"]
        ML1["รับข้อมูล: เส้นทางไฟล์,<br/>โฟลเดอร์ปลายทาง,<br/>ข้อมูลจาก AI"] --> ML2["ดึงเลขบัตรประชาชน<br/>จากข้อมูล AI<br/>(ตำแหน่งบน หรือ ล่าง)"]
        ML2 --> ML3["ดึงลักษณะเงินกู้<br/>เช่น Type1"]
        ML3 --> ML4["หาชื่อโฟลเดอร์ปลายทาง<br/>จากตารางกำหนด<br/>เช่น Type1 → Type1"]
        ML4 --> ML5["สร้างโฟลเดอร์ปลายทาง<br/>ถ้ายังไม่มี"]
        ML5 --> ML6["สร้างชื่อไฟล์ใหม่:<br/>เลขบัตร + นามสกุลไฟล์เดิม<br/>เช่น 1234567890123.pdf"]
        ML6 --> ML7{"ชื่อไฟล์ซ้ำ<br/>ในโฟลเดอร์ปลายทาง?"}
        ML7 -->|"ซ้ำ"| ML8["เติมตัวเลขต่อท้าย<br/>เช่น 1234567890123 (1).pdf<br/>หรือ 1234567890123 (2).pdf"]
        ML7 -->|"ไม่ซ้ำ"| ML9["ใช้ชื่อเดิม"]
        ML8 --> ML10["ย้ายไฟล์ไปปลายทาง"]
        ML9 --> ML10
        ML10 --> ML11["📝 บันทึก: ✅ จัดเก็บเรียบร้อย<br/>โฟลเดอร์ Type1<br/>ชื่อ 1234567890123.pdf"]
    end

    subgraph MOVE_MANUAL["⚠️ ย้ายไฟล์ที่ต้องตรวจสอบด้วยตนเอง"]
        MM1["รับข้อมูล: เส้นทางไฟล์,<br/>โฟลเดอร์ปลายทาง,<br/>เหตุผล"] --> MM2["สร้างโฟลเดอร์ Manual/<br/>ถ้ายังไม่มี"]
        MM2 --> MM3{"ชื่อไฟล์ซ้ำ<br/>ใน Manual/?"}
        MM3 -->|"ซ้ำ"| MM4["เติมตัวเลขต่อท้าย<br/>(1), (2), ..."]
        MM3 -->|"ไม่ซ้ำ"| MM5["ใช้ชื่อเดิม"]
        MM4 --> MM6["ย้ายไฟล์ไป Manual/"]
        MM5 --> MM6
        MM6 --> MM7["📝 บันทึก: ⚠️ ย้ายไฟล์ไป<br/>โฟลเดอร์ตรวจสอบด้วยตนเอง<br/>เนื่องจาก: ระบุเหตุผล"]
    end

    subgraph OUT_STRUCT["📂 โครงสร้างโฟลเดอร์ปลายทาง"]
        OUT["โฟลเดอร์ปลายทาง/"]
        OUT --> T1["📁 Type1/<br/>เอกสารลักษณะที่ 1"]
        OUT --> T2["📁 Type2/<br/>เอกสารลักษณะที่ 2"]
        OUT --> T3["📁 Type3/<br/>เอกสารลักษณะที่ 3"]
        OUT --> T4["📁 Type4/<br/>เอกสารลักษณะที่ 4"]
        OUT --> MAN["📁 Manual/<br/>เอกสารที่ต้องตรวจสอบ"]
        T1 --> F1["1234567890123.pdf"]
        T1 --> F2["9876543210987.pdf"]
        T1 --> F3["1234567890123 (1).pdf"]
        MAN --> FM1["เอกสารอ่านไม่ได้.pdf"]
        MAN --> FM2["เอกสารไม่มีลายเซ็น.jpg"]
    end
```

---

## 9. 🔗 การสื่อสารระหว่างหน้าบ้านและหลังบ้าน (Frontend-Backend Communication)

```mermaid
sequenceDiagram
    participant U as 👤 ผู้ใช้งาน
    participant JS as 🌐 หน้าบ้าน<br/>(app.js)
    participant API as 🐍 สะพาน API<br/>(app.py)
    participant CORE as ⚙️ เครื่องจักร<br/>(core.py)
    participant GEMINI as ☁️ Gemini AI
    participant FS as 💾 ระบบไฟล์

    Note over U,FS: === 🔧 ขั้นตอนการตั้งค่า ===
    U->>JS: เปิดหน้าตั้งค่า
    JS->>API: ขอข้อมูลการตั้งค่า
    API->>CORE: โหลดการตั้งค่า
    CORE->>FS: อ่านไฟล์ config.json
    FS-->>CORE: ข้อมูล JSON
    CORE-->>API: ส่งการตั้งค่ากลับ
    API-->>JS: ส่งการตั้งค่ากลับ
    JS->>U: แสดงคีย์ API, เส้นทางโฟลเดอร์

    U->>JS: กรอกคีย์ API + กดทดสอบ
    JS->>API: ทดสอบการเชื่อมต่อ
    API->>GEMINI: ตั้งค่าคีย์ + ส่งคำว่า "ping"
    GEMINI-->>API: ตอบกลับสำเร็จ
    API->>CORE: บันทึกคีย์ API
    CORE->>FS: เขียนไฟล์ config.json
    API-->>JS: เชื่อมต่อสำเร็จ ✓
    JS->>U: แสดงผล "เชื่อมต่อสำเร็จ"

    Note over U,FS: === 📄 ขั้นตอนการประมวลผลเอกสาร ===
    U->>JS: กด "เริ่มประมวลผล"
    JS->>API: เริ่มการประมวลผล
    API->>CORE: สร้างตัวประมวลผลเอกสาร
    CORE-->>API: ตัวประมวลผลพร้อมใช้งาน
    API->>API: สร้างเธรดนับเวลา (ส่งทุก 1 วินาที)
    API->>API: สร้างเธรดงานประมวลผล (ทำงานเบื้องหลัง)
    API-->>JS: เริ่มต้นสำเร็จ

    loop ทุก 1 วินาที (เธรดนับเวลา)
        API->>JS: ส่งเวลาที่ผ่านไป เช่น "0:05"
        JS->>U: อัพเดทเวลาบนหน้าจอ
    end

    loop แต่ละเอกสาร (เธรดงาน)
        CORE->>FS: อ่านไฟล์เอกสาร
        FS-->>CORE: ข้อมูลไฟล์
        CORE->>JS: ส่งบันทึก: กำลังเปิดไฟล์
        JS->>U: แสดงบันทึกการทำงาน
        
        CORE->>GEMINI: ส่งเอกสาร + พร็อมท์
        GEMINI-->>CORE: ข้อมูล JSON
        CORE->>JS: ส่งบันทึก: AI ตรวจสอบแล้ว
        
        CORE->>CORE: ตรวจสอบความถูกต้อง
        
        alt ผ่านการตรวจสอบ
            CORE->>FS: ย้ายไฟล์ → โฟลเดอร์ตามลักษณะ
            CORE->>JS: ส่งผลลัพธ์: สำเร็จ
            CORE->>JS: ส่งบันทึก: ✅ จัดเก็บเรียบร้อย
        else ไม่ผ่านการตรวจสอบ
            CORE->>FS: ย้ายไฟล์ → Manual/
            CORE->>JS: ส่งผลลัพธ์: ต้องตรวจสอบ
            CORE->>JS: ส่งบันทึก: ⚠️ ย้ายไปตรวจสอบ
        end
        
        JS->>U: อัพเดทตาราง + แถบความคืบหน้า
    end

    CORE-->>API: ผลสรุปการทำงาน
    API->>CORE: บันทึกประวัติ
    CORE->>FS: เขียนไฟล์ history.json
    API->>JS: ส่งผลสรุปสุดท้าย
    JS->>U: แสดงผลสรุป + แจ้งเตือน
```

---

## 10. 📊 โครงสร้างข้อมูลที่ AI ดึงจากเอกสาร (Gemini Prompt & AI Response Structure)

```mermaid
graph LR
    subgraph DOC_INPUT["📄 เอกสารนำเข้า"]
        DOC["แบบยืนยันการเบิกเงินกู้ยืม<br/>กองทุนเงินให้กู้ยืมเพื่อการศึกษา<br/>(กยศ.)"]
    end

    subgraph AI_PROMPT["📝 คำสั่งที่ส่งให้ AI (พร็อมท์)"]
        C1["1. ดึงชื่อ-นามสกุลผู้กู้"]
        C2["2. ดึงเลขบัตร 13 หลัก<br/>จากตำแหน่งบนสุด (ใต้บาร์โค้ด)"]
        C3["3. ดึงเลขบัตร 13 หลัก<br/>จากในเนื้อหาเอกสาร"]
        C4["4. ดึงลักษณะเงินกู้<br/>ลักษณะที่ 1-4"]
        C5["5. ตรวจลายเซ็นผู้กู้<br/>มี หรือ ไม่มี"]
        C6["6. ดึงค่าเล่าเรียน"]
        C7["7. ดึงค่าครองชีพต่อเดือน"]
        C8["8. ดึงจำนวนเดือน"]
        C9["9. ดึงค่าครองชีพรวม"]
        C10["10. ดึงยอดรวมสุทธิ"]
    end

    subgraph AI_RESP["📤 ผลลัพธ์จาก AI (รูปแบบ JSON)"]
        RESP["{<br/>  ชื่อ: 'สมชาย ใจดี',<br/>  เลขบัตรบน: '1234567890123',<br/>  เลขบัตรล่าง: '1234567890123',<br/>  ลักษณะเงินกู้: 'Type1',<br/>  ลายเซ็น: มี,<br/>  ค่าเล่าเรียน: 25000,<br/>  ค่าครองชีพต่อเดือน: 3000,<br/>  จำนวนเดือน: 12,<br/>  ค่าครองชีพรวม: 36000,<br/>  ยอดรวมสุทธิ: 61000<br/>}"]
    end

    DOC --> AI_PROMPT
    AI_PROMPT --> AI_RESP
```

---

## 11. 🖥️ หน้าจอและการนำทาง (UI Pages & Navigation Flow)

```mermaid
stateDiagram-v2
    [*] --> Dashboard: เปิดโปรแกรม

    Dashboard --> Process: คลิกเมนู "ประมวลผลเอกสาร"
    Dashboard --> History: คลิกเมนู "ประวัติการทำงาน"
    Dashboard --> Settings: คลิกเมนู "ตั้งค่า"
    Dashboard --> Process: คลิก "ประมวลผลเอกสารชุดใหม่"
    Dashboard --> History: คลิก "ดูประวัติการทำงาน"

    Process --> Dashboard: คลิกเมนู "หน้าหลัก"
    Process --> History: คลิกเมนู "ประวัติการทำงาน"
    Process --> Settings: คลิกเมนู "ตั้งค่า"

    History --> Dashboard: คลิกเมนู "หน้าหลัก"
    History --> Process: คลิกเมนู "ประมวลผลเอกสาร"
    History --> Settings: คลิกเมนู "ตั้งค่า"

    Settings --> Dashboard: คลิกเมนู "หน้าหลัก"
    Settings --> Process: คลิกเมนู "ประมวลผลเอกสาร"
    Settings --> History: คลิกเมนู "ประวัติการทำงาน"

    state Dashboard {
        [*] --> LoadDash
        LoadDash --> ShowStats: แสดง 4 การ์ด
        ShowStats --> ShowChart: แสดงกราฟ 7 วัน
        ShowChart --> ShowRecent: แสดง 5 รายการล่าสุด
    }

    state Process {
        [*] --> ChooseFolder
        ChooseFolder --> ClickStart: กด "เริ่มประมวลผล"
        ClickStart --> ProcDocs: ระบบทำงาน
        ProcDocs --> ViewResults: แสดงผลในตาราง
        ProcDocs --> ViewLogs: แสดงบันทึกแบบเรียลไทม์
        ViewResults --> FilterResults: กรองผล (ทั้งหมด/สำเร็จ/ต้องตรวจสอบ)
        ViewResults --> SearchResults: ค้นหา (ชื่อไฟล์/ผู้กู้)
        ViewResults --> PaginateResults: แบ่งหน้าผลลัพธ์
    }

    state Settings {
        [*] --> APIKeyConfig
        APIKeyConfig --> TestConnection: กดทดสอบ
        TestConnection --> ConfirmModal1: พิมพ์คำยืนยัน
        APIKeyConfig --> PromptConfig
        PromptConfig --> SavePrompt: กด "บันทึกพร็อมท์"
        SavePrompt --> ConfirmModal2: พิมพ์คำยืนยัน
        APIKeyConfig --> FolderConfig
        FolderConfig --> SaveAll: กด "บันทึกการตั้งค่า"
    }
```

---

## 12. 🔐 ระบบยืนยันความปลอดภัย (Security & Confirmation Flow)

```mermaid
flowchart TD
    subgraph CONFIRM_FLOW["🔐 กระบวนการยืนยันก่อนเปลี่ยนแปลง"]
        CF1["ผู้ใช้เปลี่ยนค่าสำคัญ<br/>(คีย์ API หรือ พร็อมท์)"] --> CF2["เปิดหน้าต่างยืนยัน<br/>แสดงหัวข้อ + คำอธิบาย"]
        CF2 --> CF3["แสดงคำที่ต้องพิมพ์<br/>เช่น 'confirm change api'<br/>หรือ 'confirm change prompt'"]
        CF3 --> CF4["ผู้ใช้พิมพ์คำยืนยัน"]
        CF4 --> CF5{"พิมพ์ตรงกับ<br/>คำที่กำหนด?"}
        CF5 -->|"ตรง"| CF6["ปุ่ม 'ยืนยัน' เปิดให้กดได้"]
        CF5 -->|"ไม่ตรง"| CF7["ปุ่ม 'ยืนยัน' ยังกดไม่ได้"]
        CF7 --> CF4
        CF6 --> CF8{"ผู้ใช้เลือก?"}
        CF8 -->|"กดยืนยัน"| CF9["✅ ดำเนินการเปลี่ยนแปลง"]
        CF8 -->|"กดยกเลิก / กด ESC"| CF10["❌ ยกเลิก ไม่เปลี่ยนแปลง"]
    end

    subgraph API_KEY_CHANGE["🔑 ขั้นตอนเปลี่ยนคีย์ API"]
        AK1["กรอกคีย์ API ใหม่"] --> AK2{"คีย์เปลี่ยนจาก<br/>ค่าเดิมหรือไม่?"}
        AK2 -->|"เปลี่ยน"| AK3["เปิดหน้าต่างยืนยัน<br/>พิมพ์ 'confirm change api'"]
        AK2 -->|"ไม่เปลี่ยน"| AK4["บันทึกโดยไม่ต้องถาม"]
        AK3 --> AK5{"ยืนยัน?"}
        AK5 -->|"ยืนยัน"| AK6["บันทึกการตั้งค่า<br/>แจ้ง: บันทึกเรียบร้อย"]
        AK5 -->|"ยกเลิก"| AK7["แจ้ง: ยกเลิกแล้ว"]
    end

    subgraph PROMPT_CHANGE["📝 ขั้นตอนเปลี่ยนพร็อมท์"]
        PC1["แก้ไขข้อความพร็อมท์"] --> PC2{"พร็อมท์เปลี่ยน<br/>จากค่าเดิมหรือไม่?"}
        PC2 -->|"เปลี่ยน"| PC3["เปิดหน้าต่างยืนยัน<br/>พิมพ์ 'confirm change prompt'"]
        PC2 -->|"ไม่เปลี่ยน"| PC4["แจ้ง: ยังไม่มีการเปลี่ยนแปลง"]
        PC3 --> PC5{"ยืนยัน?"}
        PC5 -->|"ยืนยัน"| PC6["บันทึกการตั้งค่า<br/>แจ้ง: บันทึกเรียบร้อย"]
        PC5 -->|"ยกเลิก"| PC7["แจ้ง: ยกเลิกแล้ว"]
    end

    subgraph API_KEY_CLEAN["🧹 การทำความสะอาดคีย์ API"]
        AC1["ผู้ใช้คัดลอกวางคีย์ API"] --> AC2["เริ่มทำความสะอาด"]
        AC2 --> AC3["1. ลบอักขระที่มองไม่เห็น<br/>(ช่องว่างความกว้างศูนย์)"]
        AC3 --> AC4["2. ตัดช่องว่าง<br/>หน้า-หลังออก"]
        AC4 --> AC5["3. ลบเครื่องหมายคำพูด<br/>ที่ครอบอยู่ (' หรือ \")"]
        AC5 --> AC6["✅ คีย์ API ที่สะอาดพร้อมใช้"]
    end
```

---

## 13. 🔄 การอัพเดทข้อมูลแบบเรียลไทม์ (Real-time Update Flow)

```mermaid
flowchart LR
    subgraph PY_THREADS["🐍 เธรดใน Python"]
        WORKER["เธรดงานประมวลผล<br/>(ทำงานเบื้องหลัง)"]
        TICKER["เธรดนับเวลา<br/>(ส่งทุก 1 วินาที)"]
    end

    subgraph JS_CALLBACKS["🌐 ตัวรับข้อมูลใน JavaScript"]
        ON_LOG["รับบันทึกการทำงาน"]
        ON_RESULT["รับผลลัพธ์แต่ละไฟล์"]
        ON_TICK["รับเวลาที่ผ่านไป"]
        ON_DONE["รับผลสรุปสุดท้าย"]
    end

    subgraph UI_UPDATES["🖥️ ส่วนที่อัพเดทบนหน้าจอ"]
        LOG_LIST["📋 รายการบันทึก<br/>แสดงบันทึกการทำงาน<br/>สูงสุด 300 รายการ"]
        RESULT_TABLE["📊 ตารางผลลัพธ์<br/>แสดงผลแต่ละไฟล์<br/>พร้อมแบ่งหน้า"]
        MINI_STATS["📈 สถิติย่อ<br/>- ไฟล์คงเหลือ<br/>- สำเร็จ<br/>- ต้องตรวจสอบ<br/>- ความคืบหน้า"]
        PROGRESS["📊 แถบความคืบหน้า"]
        TIMER["⏱️ ตัวนับเวลา<br/>เวลาที่ใช้"]
        DASHBOARD["📊 แดชบอร์ด<br/>การ์ดสถิติ + กราฟ"]
    end

    WORKER -->|"ส่งบันทึก"| ON_LOG
    WORKER -->|"ส่งผลลัพธ์"| ON_RESULT
    TICKER -->|"ส่งเวลา"| ON_TICK
    WORKER -->|"ส่งผลสรุป"| ON_DONE

    ON_LOG --> LOG_LIST
    ON_RESULT --> RESULT_TABLE
    ON_RESULT --> MINI_STATS
    ON_RESULT --> PROGRESS
    ON_RESULT --> DASHBOARD
    ON_TICK --> TIMER
    ON_DONE --> MINI_STATS
    ON_DONE --> PROGRESS
    ON_DONE --> DASHBOARD
```

---

## 14. 📦 การสร้างและแจกจ่ายโปรแกรม (Build & Deployment Flow)

```mermaid
flowchart TD
    subgraph DEV_MODE["💻 โหมดพัฒนา (Development)"]
        D1["สร้าง Virtual Environment"] --> D2["เปิดใช้งาน venv"]
        D2 --> D3["ติดตั้งไลบรารี<br/>ที่จำเป็นทั้งหมด"]
        D3 --> D4["รัน python app.py<br/>(หน้าตาใหม่ — pywebview)"]
        D3 --> D5["รัน python main.py<br/>(หน้าตาเก่า — customtkinter)"]
    end

    subgraph BUILD_WIN["🔨 สร้างบนเครื่องวินโดวส์"]
        W1["เปิดหน้าต่างคำสั่ง<br/>บนวินโดวส์"] --> W2["ติดตั้ง PyInstaller"]
        W2 --> W3["สั่ง PyInstaller<br/>--onefile: รวมเป็นไฟล์เดียว<br/>--windowed: ไม่แสดงหน้าจอดำ<br/>--add-data: รวมโฟลเดอร์เว็บและฟอนต์<br/>--collect-all: รวมไลบรารี pywebview"]
        W3 --> W4["📦 ได้ไฟล์<br/>AI_Document_Assistant.exe"]
    end

    subgraph BUILD_CI["☁️ สร้างอัตโนมัติผ่าน GitHub Actions"]
        CI1["อัปโหลดโค้ดขึ้น GitHub"] --> CI2["GitHub Actions ทำงาน<br/>Build Windows EXE"]
        CI2 --> CI3["เครื่องวินโดวส์บนคลาวด์<br/>ของ GitHub"]
        CI3 --> CI4["ติดตั้งไลบรารี + สร้างไฟล์ .exe"]
        CI4 --> CI5["📦 ไฟล์ .exe พร้อมดาวน์โหลด<br/>จากหน้า Actions"]
    end

    subgraph DEPLOY["🚀 การแจกจ่ายให้เจ้าหน้าที่"]
        W4 --> DEP1["แจกจ่ายไฟล์ .exe<br/>ให้เจ้าหน้าที่"]
        CI5 --> DEP1
        DEP1 --> DEP2["เจ้าหน้าที่ดับเบิ้ลคลิก<br/>เปิดโปรแกรมได้ทันที"]
        DEP2 --> DEP3["ไม่ต้องติดตั้ง Python<br/>ไม่ต้องมีไลบรารี<br/>ต้องมีอินเทอร์เน็ตเท่านั้น"]
    end
```

---

## 15. 📋 สรุปการไหลของข้อมูลทั้งระบบ (Complete Data Flow Summary)

```mermaid
graph TB
    subgraph DATA_INPUT["📥 ข้อมูลนำเข้า"]
        I1["📁 โฟลเดอร์ต้นทาง<br/>NewDocs/, NewDocs 2/, ..."]
        I2["📄 เอกสาร<br/>PDF, JPG, PNG, TIFF ฯลฯ"]
        I3["🔑 คีย์ API<br/>สำหรับเชื่อมต่อ Gemini"]
        I4["📝 พร็อมท์กำหนดเอง<br/>(ตั้งค่าได้)"]
    end

    subgraph PIPELINE["⚙️ ท่อประมวลผล"]
        direction TB
        P1["1️⃣ ค้นหาไฟล์<br/>ค้นหาโฟลเดอร์ NewDocs*<br/>แล้วค้นหาเอกสารภายใน"]
        P2["2️⃣ เตรียมรูปภาพ<br/>ย่อขนาดเหลือ 2,048 พิกเซล<br/>แปลงเป็น JPEG"]
        P3["3️⃣ ส่งให้ AI ดึงข้อมูล<br/>ส่งเอกสารไปยัง Gemini API"]
        P4["4️⃣ แปลงคำตอบ<br/>แปลง JSON + ลบ markdown"]
        P5["5️⃣ ตรวจสอบความถูกต้อง<br/>ชื่อ + เลขบัตร x2<br/>+ ลักษณะเงินกู้ + ลายเซ็น"]
        P6["6️⃣ ตรวจ Checksum<br/>เลขบัตรประชาชน<br/>ด้วยอัลกอริทึม Mod-11"]
        P7["7️⃣ จัดเส้นทางไฟล์<br/>ย้ายไปโฟลเดอร์ตามลักษณะ<br/>หรือไป Manual"]
        P8["8️⃣ เปลี่ยนชื่อไฟล์<br/>ชื่อใหม่ = เลขบัตร.นามสกุล"]
    end

    subgraph DATA_OUTPUT["📤 ข้อมูลผลลัพธ์"]
        O1["📁 Type1/<br/>เอกสารลักษณะที่ 1"]
        O2["📁 Type2/<br/>เอกสารลักษณะที่ 2"]
        O3["📁 Type3/<br/>เอกสารลักษณะที่ 3"]
        O4["📁 Type4/<br/>เอกสารลักษณะที่ 4"]
        O5["📁 Manual/<br/>เอกสารที่ต้องตรวจสอบ"]
        O6["📊 ข้อมูลแดชบอร์ด<br/>สถิติการทำงานสะสม"]
        O7["📋 ประวัติการทำงาน<br/>ผลการประมวลผลย้อนหลัง"]
        O8["📝 บันทึกแบบเรียลไทม์<br/>ขั้นตอนการทำงานโดยละเอียด"]
    end

    I1 --> P1
    I2 --> P1
    I3 --> P3
    I4 --> P3
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
    P6 --> P7
    P7 --> P8
    P8 --> O1
    P8 --> O2
    P8 --> O3
    P8 --> O4
    P7 --> O5
    P7 --> O6
    P7 --> O7
    P7 --> O8
```

---

## 16. ⚠️ การจัดการข้อผิดพลาดทุกกรณี (Error Handling & Edge Cases)

```mermaid
flowchart TD
    subgraph ERRORS["⚠️ สถานการณ์ข้อผิดพลาดทั้งหมด และวิธีจัดการ"]
        direction TB
        
        E1["❌ ไม่มีคีย์ API"] --> H1["แจ้งเตือน: กรุณาตั้งค่าคีย์ API<br/>เปลี่ยนไปหน้าตั้งค่าอัตโนมัติ"]
        
        E2["❌ โฟลเดอร์ต้นทาง<br/>ไม่ถูกต้อง"] --> H2["ส่งข้อผิดพลาด:<br/>โฟลเดอร์ต้นทางไม่ถูกต้อง"]
        
        E3["❌ ไม่พบโฟลเดอร์<br/>NewDocs*"] --> H3["บันทึก: ไม่พบโฟลเดอร์<br/>เอกสารใหม่ในโฟลเดอร์ที่เลือก"]
        
        E4["❌ เปิดไฟล์ไม่ได้<br/>(ถูกล็อก / เสียหาย)"] --> H4["บันทึก: เปิดไฟล์ไม่ได้<br/>→ ย้ายไปโฟลเดอร์ Manual/"]
        
        E5["❌ ไฟล์ว่างเปล่า<br/>ไม่มีข้อมูลภายใน"] --> H5["บันทึก: ไฟล์ไม่มีข้อมูล<br/>→ ย้ายไปโฟลเดอร์ Manual/"]
        
        E6["❌ AI อ่านเอกสาร<br/>ไม่ได้"] --> H6["บันทึก: AI อ่านไม่ได้<br/>→ ย้ายไปโฟลเดอร์ Manual/"]
        
        E7["❌ คำตอบจาก AI<br/>ไม่ใช่ JSON ที่ถูกต้อง"] --> H7["บันทึก: ข้อมูล AI อ่านไม่ได้<br/>→ ย้ายไปโฟลเดอร์ Manual/"]
        
        E8["❌ ผู้ใช้หนาแน่น (429)<br/>ส่งคำขอเกินโควต้า"] --> H8["รอตามเวลาที่กำหนด<br/>ลองส่งใหม่สูงสุด 3 ครั้ง"]
        
        E9["❌ รูปภาพอ่านเลขบัตร<br/>ไม่ชัดเจน"] --> H9["ลองใหม่ด้วยความละเอียด<br/>3,072 พิกเซล (สูงขึ้น)"]
        
        E10["❌ ข้อมูลไม่ผ่าน<br/>การตรวจสอบ 4 ด่าน"] --> H10["บันทึก: ข้อมูลไม่ผ่านเกณฑ์<br/>→ ย้ายไป Manual/<br/>พร้อมระบุเหตุผลที่ไม่ผ่าน"]
        
        E11["❌ ย้ายไฟล์ไม่สำเร็จ<br/>(ไม่มีสิทธิ์ / ดิสก์เต็ม)"] --> H11["บันทึก: ย้ายไฟล์ไม่ได้<br/>→ ย้ายไป Manual/ แทน"]
        
        E12["❌ ผู้ใช้กดหยุด<br/>ระหว่างประมวลผล"] --> H12["บันทึก: ผู้ใช้สั่งหยุด<br/>จบการทำงานหลังไฟล์<br/>ปัจจุบันเสร็จ"]
        
        E13["❌ เกิดข้อผิดพลาดร้ายแรง<br/>ระหว่างประมวลผล"] --> H13["บันทึก: ระบบหยุดทำงาน<br/>กะทันหัน<br/>ส่งผลสรุปว่างกลับ"]
        
        E14["❌ ชื่อไฟล์ปลายทาง<br/>ซ้ำกัน"] --> H14["เติมตัวเลขต่อท้าย (1), (2), ...<br/>ไม่มีการทับไฟล์เดิม"]
    end
```
