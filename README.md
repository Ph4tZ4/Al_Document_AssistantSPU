# AI Document Assistant (ระบบผู้ช่วยจัดการเอกสารด้วย AI)

โปรแกรมสำหรับเจ้าหน้าที่บนระบบปฏิบัติการ Windows (Desktop Application) ช่วยลดภาระงานจัดการเอกสารสัญญากู้ยืม โดยใช้ความสามารถของ **Google Gemini API** ในการอ่านเอกสาร PDF สแกน เพื่อดึงข้อมูลสำคัญ ได้แก่ **ชื่อ-นามสกุล / เลขประจำตัวประชาชน 13 หลัก / ประเภทการกู้** จากนั้นระบบจะทำการเปลี่ยนชื่อไฟล์ตามรูปแบบที่กำหนด และคัดแยกเอกสารเข้าสู่โฟลเดอร์ตามประเภทโดยอัตโนมัติ สำหรับไฟล์ที่ AI ไม่สามารถอ่านได้หรือข้อมูลไม่ครบถ้วน จะถูกย้ายไปที่โฟลเดอร์ `Manual` เพื่อให้เจ้าหน้าที่ตรวจสอบด้วยตนเอง

---

## 🌟 คุณสมบัติเด่น

1. **ส่วนติดต่อผู้ใช้งาน (GUI) ทันสมัย**: ใช้งานง่ายด้วย Dark Mode สบายตา มีปุ่มเลือกโฟลเดอร์ และกล่องแสดงสถานะการทำงานแบบ Real-time
2. **อ่านเอกสารด้วย AI**: รองรับไฟล์ PDF สแกนหรือภาพถ่ายเอกสาร ทั้งภาษาไทยและภาษาอังกฤษ
3. **ตรวจสอบความถูกต้อง (Validation)**: เช็คเลขบัตรประชาชนให้ครบ 13 หลัก และตรวจสอบประเภทการกู้ให้ถูกต้องตามเกณฑ์
4. **จัดระเบียบไฟล์อัตโนมัติ**:
   - เปลี่ยนชื่อไฟล์เป็น: `ชื่อ-นามสกุล_เลขบัตรประชาชน_ประเภทการกู้.pdf` (เช่น `Somchai Jaidee_1234567890123_Type1.pdf`)
   - ย้ายไฟล์ไปเก็บในโฟลเดอร์ตามประเภทสินเชื่อ (เช่น `Type1/`, `Type2/`, `Type3/`, `Type4/`)
5. **ระบบจัดการไฟล์ที่มีปัญหา**: ย้ายไฟล์ที่อ่านไม่ได้หรือไม่ครบถ้วนไปที่โฟลเดอร์ `Manual/` ทันที ป้องกันเอกสารสูญหาย
6. **ระบบป้องกันไฟล์ซ้ำ**: หากชื่อไฟล์ปลายทางซ้ำ ระบบจะเติมตัวเลขต่อท้าย เช่น `(1)`, `(2)` โดยอัตโนมัติ ไม่มีการทับซ้อนไฟล์เดิม

---

## 🚀 วิธีการใช้งานโปรแกรมสำหรับเจ้าหน้าที่

1. **เลือกโฟลเดอร์ต้นทาง (Source Directory)**: คลิกปุ่ม **Browse...** เพื่อเลือกโฟลเดอร์ที่เก็บไฟล์ PDF เอกสาร (โดยภายในโฟลเดอร์จะมีโฟลเดอร์ย่อยชื่อ `NewDocs`, `NewDocs 2` ฯลฯ)
2. **กรอก Gemini API Key**: ใส่รหัส API Key ของคุณในช่อง (สามารถขอรับ API Key ฟรีได้ที่ https://aistudio.google.com/apikey)
3. **กดปุ่ม Start Processing**: ระบบจะเริ่มสแกนเอกสาร ส่งให้ AI วิเคราะห์ เปลี่ยนชื่อ และย้ายโฟลเดอร์ทันที
   - แฟ้มรายการสำเร็จ -> ถูกย้ายไปที่โฟลเดอร์ `Type1/`, `Type2/`, `Type3/`, `Type4/`
   - แฟ้มต้องตรวจสอบเพิ่ม -> ถูกย้ายไปที่โฟลเดอร์ `Manual/`

> **หมายเหตุ:** สามารถปรับแต่งประเภทการกู้และชื่อโฟลเดอร์ได้ที่ส่วน Config ด้านบนของไฟล์ `main.py` (`LOAN_TYPES` และ `LOAN_TYPE_FOLDERS`)

---

## 💻 การรันโปรแกรมในโหมดพัฒนา (Development Mode)

สามารถรันโค้ดได้ทั้งบน macOS และ Windows โดยใช้คำสั่งต่อไปนี้:

```bash
# 1. สร้าง Virtual Environment
python -m venv .venv

# 2. เปิดใช้งาน Virtual Environment
# สำหรับ macOS/Linux:
source .venv/bin/activate
# สำหรับ Windows (Command Prompt):
.venv\Scripts\activate.bat
# สำหรับ Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. ติดตั้งไลบรารีที่จำเป็น
pip install -r requirements.txt

# 4. รันโปรแกรม (หน้าตาใหม่แบบ Dashboard)
python app.py
```

> **หมายเหตุ:** `app.py` คือโปรแกรมหลักหน้าตาใหม่ (UI เว็บครอบด้วย pywebview) ส่วน `main.py` เป็น GUI แบบเดิม (customtkinter) ที่ยังเก็บไว้ใช้ได้

หากต้องการตั้งค่า API Key ล่วงหน้าผ่าน Environment Variable เพื่อให้ระบบแสดงรหัสในช่องกรอกให้อัตโนมัติ:
```bash
# สำหรับ macOS/Linux:
export GEMINI_API_KEY="รหัส-api-key-ของคุณ"

# สำหรับ Windows (Command Prompt):
set GEMINI_API_KEY=รหัส-api-key-ของคุณ

# สำหรับ Windows (PowerShell):
$env:GEMINI_API_KEY="รหัส-api-key-ของคุณ"
```

---

## 📦 วิธีการแปลงโปรแกรมเป็นไฟล์ .exe สำหรับ Windows

> [!IMPORTANT]
> **ข้อสำคัญเรื่องระบบปฏิบัติการ:** เครื่องมือ `PyInstaller` **ไม่สามารถข้ามระบบปฏิบัติการ (Cross-compile) ได้** หมายความว่าหากต้องการสร้างไฟล์ `.exe` สำหรับ Windows **จำเป็นต้องรันคำสั่งสร้างบนเครื่อง Windows เท่านั้น** (ไม่สามารถใช้ macOS สร้างไฟล์ `.exe` ได้โดยตรง)

สามารถเลือกวิธีการแปลงเป็นไฟล์ `.exe` ได้ 2 วิธีหลัก ดังนี้:

### วิธีที่ 1: แนะนำที่สุด — แปลงบนเครื่อง Windows โดยตรง (หรือใช้ Windows VM / เครื่องของร่วมงาน)

หากคุณใช้คอมพิวเตอร์ Windows อยู่แล้ว หรือรันระบบจำลอง Windows (เช่น Parallels, VMware, UTM บน macOS) ให้ทำตามขั้นตอนดังนี้:

1. **ติดตั้ง Python 3.12** สำหรับ Windows จาก https://python.org (อย่าลืมติ๊กถูกที่ช่อง **"Add Python to PATH"** ตอนติดตั้ง)
2. เปิดหน้าต่าง **Command Prompt (cmd)** หรือ **PowerShell** แล้วเข้าไปที่โฟลเดอร์โปรเจกต์
3. ติดตั้งไลบรารีและเครื่องมือ `PyInstaller`:
   ```bat
   pip install -r requirements.txt
   pip install pyinstaller
   ```
4. รันคำสั่งเพื่อสร้างไฟล์ `.exe`:
   ```bat
   pyinstaller --noconfirm --onefile --windowed --name "AI_Document_Assistant" --add-data "web;web" --add-data "fonts;fonts" --collect-all webview app.py
   ```
5. เมื่อการทำงานเสร็จสิ้น คุณจะได้ไฟล์สำหรับนำไปแจกจ่ายให้เจ้าหน้าที่ใช้งานได้ทันทีอยู่ที่:
   👉 **`dist\AI_Document_Assistant.exe`**

#### 🛠 คำอธิบายพารามิเตอร์ของ PyInstaller
| พารามิเตอร์ | ความหมายและประโยชน์ |
| :--- | :--- |
| `--onefile` | บีบอัดโปรแกรมและไลบรารีทั้งหมดให้อยู่ในไฟล์ `.exe` เพียงไฟล์เดียว ง่ายต่อการนำไปใช้งาน |
| `--windowed` | ไม่แสดงหน้าต่างหน้าจอ Command Prompt / Terminal สีดำเวลาเปิดโปรแกรม (แสดงเฉพาะหน้าต่าง GUI) |
| `--name "..."` | กำหนดชื่อไฟล์โปรแกรม `.exe` ที่ได้ผลลัพธ์ |
| `--add-data "web;web"` | **(จำเป็นมาก)** รวมโฟลเดอร์ `web` (HTML/CSS/JS ของหน้าโปรแกรม) เข้าไปในไฟล์ `.exe` |
| `--add-data "fonts;fonts"` | รวมฟอนต์ภาษาไทย (Sarabun) ไว้ใช้แบบออฟไลน์ |
| `--collect-all webview` | **(จำเป็นมาก)** ดึงไฟล์ของไลบรารี pywebview มารวมไว้ ไม่เช่นนั้นหน้าต่างโปรแกรมจะเปิดไม่ติด |
| `--noconfirm` | เขียนทับโฟลเดอร์ผลลัพธ์เดิมโดยไม่ต้องถามยืนยัน |

---

### วิธีที่ 2: แปลงแบบอัตโนมัติผ่าน GitHub Actions (ไม่ต้องใช้เครื่อง Windows)

ในโปรเจกต์นี้มีไฟล์ตั้งค่า `.github/workflows/build-windows.yml` เตรียมไว้ให้แล้ว สามารถสร้างไฟล์ `.exe` ผ่านระบบคลาวด์ของ GitHub ได้ฟรี:

1. อัปโหลดโค้ดโปรเจกต์นี้ขึ้นไปที่ GitHub Repository ของคุณ:
   ```bash
   git add .
   git commit -m "Add Thai README and prepare for Windows build"
   git push origin main
   ```
2. ไปที่หน้าเว็บไซต์ GitHub Repository ของคุณ คลิกที่แท็บ **Actions**
3. เลือกหัวข้อ **Build Windows EXE** ทางเมนูด้านซ้าย แล้วคลิกปุ่ม **Run workflow**
4. รอระบบทำงานประมาณ 2-3 นาที เมื่อเสร็จแล้วให้คลิกเข้าไปที่เวิร์กโฟลว์นั้นเพื่อดาวน์โหลดไฟล์ **`AI_Document_Assistant_Windows`** (ด้านล่างในส่วน Artifacts) ซึ่งภายในจะมีไฟล์ `AI_Document_Assistant.exe` ที่พร้อมใช้งานบน Windows 10/11 ทันที

---

## �️ วิธีสร้างตัวติดตั้ง (Installer) แบบคลิกเดียวจบ พร้อมตัวถอนการติดตั้ง

โปรเจกต์นี้เตรียมไฟล์สำหรับสร้าง **ตัวติดตั้ง (Installer)** ที่มี **ตัวถอนการติดตั้ง (Uninstaller)** ในตัวไว้ให้แล้ว ทั้ง Windows และ macOS

### Windows — `AI_Document_Assistant_Setup.exe`

ใช้เครื่องมือ [Inno Setup](https://jrsoftware.org/isinfo.php) (ฟรี) สร้างไฟล์ Setup.exe ที่:
- ติดตั้งโปรแกรมลง `Program Files`, สร้างช็อตคัตที่ Start Menu และ Desktop
- ลงทะเบียนตัวถอนการติดตั้งอัตโนมัติที่ **Settings > Apps > Installed apps** (Control Panel) — เจ้าหน้าที่กด Uninstall ได้เลยโดยไม่ต้องลบมือ

วิธีสร้าง (ต้องรันบนเครื่อง Windows หรือผ่าน GitHub Actions):

1. สร้างไฟล์ `.exe` ตัวโปรแกรมก่อน (ดูวิธีที่ 1 ด้านบน) ให้ได้ `dist\AI_Document_Assistant.exe`
2. ติดตั้ง [Inno Setup 6](https://jrsoftware.org/isdl.php)
3. รันคำสั่ง:
   ```bat
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\windows\setup.iss
   ```
4. ได้ไฟล์ `dist_installer\AI_Document_Assistant_Setup.exe` — แจกให้เจ้าหน้าที่ดับเบิลคลิกเพื่อติดตั้งได้ทันที

หรือใช้ GitHub Actions อัตโนมัติ: ไปที่แท็บ **Actions > Build Windows EXE > Run workflow** ระบบจะสร้างทั้งไฟล์ `.exe` ธรรมดา และไฟล์ตัวติดตั้ง `AI_Document_Assistant_Windows_Installer` ให้ดาวน์โหลด

### macOS — `AI_Document_Assistant_macOS.dmg`

สคริปต์ `installer/mac/build_dmg.sh` จะสร้างแอป `.app` ด้วย PyInstaller แล้วบรรจุลงไฟล์ `.dmg` ที่มี:
- ไอคอนแอป + ช็อตคัตลาก (drag) ไปยังโฟลเดอร์ Applications เพื่อ "ติดตั้ง"
- สคริปต์ `Uninstall AI Document Assistant.command` สำหรับถอนการติดตั้ง (ดับเบิลคลิกเพื่อลบแอปและข้อมูลที่บันทึกไว้)

วิธีสร้าง (ต้องรันบนเครื่อง macOS):
```bash
bash installer/mac/build_dmg.sh
```
ได้ไฟล์ `dist_installer/AI_Document_Assistant_macOS.dmg`

หรือใช้ GitHub Actions: ไปที่แท็บ **Actions > Build macOS DMG > Run workflow**

---

## �📌 ข้อควรทราบเพิ่มเติมสำหรับผู้ดูแลระบบ
- เครื่องคอมพิวเตอร์ Windows ของเจ้าหน้าที่ที่จะใช้งานโปรแกรมนี้ **ต้องเชื่อมต่ออินเทอร์เน็ต** เพื่อส่งเอกสารไปวิเคราะห์ที่ Google Gemini API
- โปรแกรมถูกออกแบบมาเรื่องความปลอดภัย โดยไม่ฝังรหัส API Key ไว้ในโค้ด เจ้าหน้าที่สามารถกรอกเองหน้าโปรแกรม หรือผู้ดูแลระบบตั้งค่าผ่าน Environment Variable ในเครื่องของเจ้าหน้าที่ได้
