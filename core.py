"""
AI Document Assistant — Core processing logic
---------------------------------------------
GUI-independent engine used by the pywebview desktop app (app.py).

Responsibilities:
1. Discover documents (PDFs / images) inside "NewDocs*" source folders.
2. Send each document to Google Gemini to extract the borrower name,
   13-digit national ID (in two places), loan type and signature status.
3. Validate the 4 "red box" checks and rename + move the file into a
   loan-type folder, or into the "Manual" folder when review is needed.
4. Persist user settings and processing history as JSON so the dashboard,
   history and settings pages can read/write them.
"""

from __future__ import annotations

import os
import re
import sys
import glob
import json
import shutil
import time
import threading
import io
from datetime import datetime

from PIL import Image

# pyrefly: ignore [missing-import]
import google.generativeai as genai

# ============================================================
# CONFIGURATION
# ============================================================

LOAN_TYPES = ["Type1", "Type2", "Type3", "Type4"]

LOAN_TYPE_FOLDERS = {
    "Type1": "Type1",
    "Type2": "Type2",
    "Type3": "Type3",
    "Type4": "Type4",
}

MANUAL_FOLDER_NAME = "Manual"
PROCESSED_FOLDER_PREFIX = "NewDocs"
GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}

MAX_IMAGE_DIMENSION = 2048
MAX_IMAGE_DIMENSION_RETRY = 3072
JPEG_QUALITY = 85

SUPPORTED_LABEL = "PDF, JPG, PNG, TIFF"

# ============================================================
# THAI DATE/TIME HELPERS (used in logs, history, dashboard)
# ============================================================

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thai_datetime(dt: datetime, with_seconds: bool = False) -> str:
    time_fmt = "%H:%M:%S" if with_seconds else "%H:%M"
    return f"{dt.day:02d} {TH_MONTHS[dt.month - 1]} {dt.year + 543} {dt.strftime(time_fmt)}"


# ============================================================
# GEMINI PROMPT
# ============================================================

GEMINI_PROMPT = f"""You are a document data extraction and verification system for a loan department.
You will receive a scanned document (PDF or photo/image, possibly in Thai or English).
It is a Thai student-loan confirmation form (แบบยืนยันการเบิกเงินกู้ยืม กองทุนเงินให้กู้ยืมเพื่อการศึกษา).

Read the document carefully and extract EXACTLY these fields:

1. "name": The full name of the applicant/borrower (first name and last name, as written in the document, e.g. after "ข้าพเจ้า").
2. "id_card_top": The 13-digit national ID number printed near the TOP of the document,
   next to or under the barcode area (usually printed as digits under/beside the barcode).
   Return DIGITS ONLY, no spaces or dashes. It must be exactly 13 digits.
3. "id_card_body": The 13-digit national ID number written in the document body,
   on the line labelled "เลขบัตรประจำตัวประชาชน" (usually in section 1, near the applicant's name).
   Return DIGITS ONLY, no spaces or dashes. It must be exactly 13 digits.
4. "loan_type": Find the line in the header/title area that starts with "ลักษณะที่" and read the number that follows:
   - "ลักษณะที่ 1" -> return "{LOAN_TYPES[0]}"
   - "ลักษณะที่ 2" -> return "{LOAN_TYPES[1]}"
   - "ลักษณะที่ 3" -> return "{LOAN_TYPES[2]}"
   - "ลักษณะที่ 4" -> return "{LOAN_TYPES[3]}"
   If "ลักษณะที่" is not present, fall back to "ประเภท" or "Type" with the same number mapping.
   The value MUST be exactly one of: "{LOAN_TYPES[0]}", "{LOAN_TYPES[1]}", "{LOAN_TYPES[2]}", "{LOAN_TYPES[3]}".
5. "signed": true or false. Look at the signature area near the BOTTOM of the document
   (the lines labelled "ลงชื่อ" for ผู้กู้ยืมเงิน / ผู้แทนโดยชอบธรรม / พยาน).
   Return true if the borrower's signature line ("ลงชื่อ ... ผู้กู้ยืมเงิน") contains ANY handwriting,
   signature, mark, or even a single dot or tiny stroke on the line. Be LENIENT: any visible ink
   on that signature line counts as signed. Return false ONLY if the borrower's signature line is
   completely blank.
6. "tuition_fee": The tuition/education fee amount (ค่าเล่าเรียน / ค่าเทอม / ค่าลงทะเบียนเรียน).
   Return the amount as a NUMBER ONLY (no commas, no currency symbol, no "บาท"). e.g. 25000 or 25000.50.
7. "living_allowance_monthly": The MONTHLY living allowance amount (ค่าครองชีพต่อเดือน / เดือนละ).
   Return the per-month amount as a NUMBER ONLY.
8. "living_allowance_months": The NUMBER OF MONTHS the living allowance is paid for
   (จำนวนเดือน, e.g. "เป็นเวลา 12 เดือน" -> 12). Return an integer NUMBER ONLY.
9. "living_allowance_total": The TOTAL living allowance amount for all months combined
   (ค่าครองชีพรวม = ค่าครองชีพต่อเดือน x จำนวนเดือน). Return a NUMBER ONLY. If not printed explicitly
   but both monthly amount and months are known, you may compute it.
10. "net_total": The grand NET TOTAL amount of the whole form (รวมสุทธิ / รวมทั้งสิ้น / ยอดรวมสุทธิ),
   typically tuition_fee + living_allowance_total. Return a NUMBER ONLY.

STRICT RULES:
- Respond with ONLY a single valid JSON object. No markdown, no code fences, no explanations.
- The JSON must have exactly these keys: "name", "id_card_top", "id_card_body", "loan_type", "signed",
  "tuition_fee", "living_allowance_monthly", "living_allowance_months", "living_allowance_total", "net_total".
- Read "id_card_top" and "id_card_body" INDEPENDENTLY from their own locations. Do NOT copy one
  into the other; if one of them cannot be read, set only that one to null.
- For all money/number fields return plain numbers WITHOUT thousands separators or currency text.
- If ANY field cannot be found or read with confidence, set that field's value to null.
- Do NOT guess or invent data. If the document is unreadable, return all fields as null.

Example of a valid response:
{{"name": "Somchai Jaidee", "id_card_top": "1234567890123", "id_card_body": "1234567890123", "loan_type": "{LOAN_TYPES[0]}", "signed": true, "tuition_fee": 25000, "living_allowance_monthly": 3000, "living_allowance_months": 12, "living_allowance_total": 36000, "net_total": 61000}}

Example when data is missing:
{{"name": null, "id_card_top": null, "id_card_body": null, "loan_type": null, "signed": null, "tuition_fee": null, "living_allowance_monthly": null, "living_allowance_months": null, "living_allowance_total": null, "net_total": null}}
"""


# ============================================================
# PERSISTENCE (settings + history)
# ============================================================

def app_data_dir() -> str:
    """Return a writable directory for storing config/history.

    Uses %APPDATA% on Windows, ~/Library/Application Support on macOS,
    else ~/.config. Falls back to the executable directory."""
    try:
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        path = os.path.join(base, "AI_Document_Assistant")
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_data_dir(), "config.json")
HISTORY_PATH = os.path.join(app_data_dir(), "history.json")
PROMPT_VERSIONS_PATH = os.path.join(app_data_dir(), "prompt_versions.json")

DEFAULT_CONFIG = {
    "api_key": "",
    "source_dir": "",
    "output_dir": "",
    "theme": "light",
    "prompt": "",
}


def default_prompt() -> str:
    """The built-in Gemini extraction prompt (used as fallback and for 'reset to default')."""
    return GEMINI_PROMPT


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    # Environment variable takes priority only when no key is saved yet.
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("GEMINI_API_KEY", "")
    # No custom prompt saved yet -> fall back to the built-in default.
    if not cfg.get("prompt") or not str(cfg.get("prompt")).strip():
        cfg["prompt"] = GEMINI_PROMPT
    return cfg


def save_config(cfg: dict) -> dict:
    current = load_config()
    previous_prompt = current.get("prompt") or ""
    current.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    # Prompt versioning: keep a history of every prompt that has been used.
    new_prompt = (cfg.get("prompt") or "").strip() if "prompt" in cfg else ""
    if new_prompt and new_prompt != previous_prompt.strip():
        append_prompt_version(new_prompt)
    return current


# ---------- Prompt version history ----------

def load_prompt_versions() -> list:
    """Return prompt versions, newest first. Seeds the file with the current
    prompt (or built-in default) on first use so there is always a v1."""
    versions = []
    try:
        with open(PROMPT_VERSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                versions = data
    except Exception:
        pass
    if not versions:
        current = load_config().get("prompt") or GEMINI_PROMPT
        versions = [_make_prompt_version(1, current)]
        _write_prompt_versions(versions)
    return versions


def _make_prompt_version(version: int, prompt: str) -> dict:
    now = datetime.now()
    return {
        "version": version,
        "timestamp": now.isoformat(),
        "date": thai_datetime(now),
        "prompt": prompt,
    }


def _write_prompt_versions(versions: list):
    try:
        with open(PROMPT_VERSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(versions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def append_prompt_version(prompt: str) -> list:
    """Save a new prompt version (newest first). Skips exact duplicates of the
    latest version. Keeps up to 50 versions."""
    prompt = (prompt or "").strip()
    if not prompt:
        return load_prompt_versions()
    versions = load_prompt_versions()
    if versions and versions[0].get("prompt", "").strip() == prompt:
        return versions
    next_num = max((v.get("version", 0) for v in versions), default=0) + 1
    versions.insert(0, _make_prompt_version(next_num, prompt))
    versions = versions[:50]
    _write_prompt_versions(versions)
    return versions


def load_history() -> list:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def append_history(entry: dict) -> list:
    history = load_history()
    history.insert(0, entry)
    history = history[:200]  # keep the latest 200 runs
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return history


# ============================================================
# CORE PROCESSING
# ============================================================

# Actionable fix suggestions shown alongside error/warning logs so staff know
# how to correct a file that failed processing.
FIX_HINTS = {
    "ไม่พบชื่อ-นามสกุล": "ตรวจสอบว่าเอกสารสแกนครบทั้งหน้าและช่องชื่อ-นามสกุลไม่ถูกบัง/เลือน หากเลือนให้สแกนใหม่ด้วยความละเอียดสูงขึ้นแล้วนำเข้าประมวลผลอีกครั้ง",
    "อ่านเลขบัตร 13 หลักไม่ได้": "สแกนเอกสารใหม่ให้คมชัดขึ้น (300 dpi ขึ้นไป) โดยให้เห็นเลขบัตรใต้บาร์โค้ดและในเนื้อเอกสารครบ 13 หลัก แล้วนำเข้าประมวลผลอีกครั้ง",
    "เลขบัตรบน/ล่างไม่ตรงกัน": "เปิดไฟล์ในโฟลเดอร์ Manual เพื่อเทียบเลขบัตรทั้งสองจุดด้วยตนเอง หากเอกสารพิมพ์เลขผิดให้แจ้งผู้กู้แก้ไขเอกสารแล้วสแกนใหม่",
    "เลขบัตรประชาชนไม่ถูกต้อง (หลักตรวจสอบไม่ผ่าน)": "เลขบัตรที่อ่านได้ไม่ผ่านการตรวจสอบหลักสุดท้าย อาจเกิดจากสแกนไม่ชัดหรือกรอกเลขผิด ให้ตรวจเลขบัตรในเอกสารจริงแล้วสแกนใหม่ให้คมชัด",
    "ไม่พบประเภทการกู้": "ตรวจสอบว่าส่วนหัวเอกสารที่ระบุ \"ลักษณะที่ ...\" ถูกสแกนติดมาครบ ไม่ถูกตัดขอบ หากขาดให้สแกนใหม่ทั้งหน้า",
    "ไม่พบลายเซ็นผู้กู้": "ให้ผู้กู้ลงลายมือชื่อในช่อง \"ลงชื่อ ... ผู้กู้ยืมเงิน\" ให้เรียบร้อย แล้วสแกนเอกสารและนำเข้าประมวลผลอีกครั้ง",
    "AI อ่านไฟล์ไม่ได้": "ตรวจสอบว่าไฟล์เปิดได้ปกติและเป็นเอกสารแบบยืนยันการเบิกเงินกู้ หากไฟล์เสียหายให้สแกนใหม่เป็น PDF หรือ JPG แล้วนำเข้าประมวลผลอีกครั้ง",
}


def fix_hint(reason: str) -> str:
    """Return an actionable suggestion for a known failure reason."""
    return FIX_HINTS.get(reason, "")


class DocumentProcessor:
    def __init__(self, api_key: str, prompt: str | None = None, log_fn=None, result_fn=None):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            generation_config={"response_mime_type": "application/json"},
        )
        self.prompt = prompt.strip() if prompt and prompt.strip() else GEMINI_PROMPT
        self.log = log_fn or (lambda *_: None)
        self.emit_result = result_fn or (lambda *_: None)
        self.stop_flag = threading.Event()

    # ---------- Logging (structured, user-friendly) ----------

    def _log(self, step: str, message: str, level: str = "info", hint: str = ""):
        """Emit a structured log entry: timestamp + processing step + a plain,
        non-technical message so office staff can understand what happened.
        level is one of: info, success, warning, error.
        hint (optional) is an actionable suggestion on how to fix the problem."""
        self.log({
            "time": thai_datetime(datetime.now(), with_seconds=True),
            "step": step,
            "level": level,
            "message": message,
            "hint": hint,
        })

    # ---------- Folder discovery ----------

    @staticmethod
    def find_newdocs_folders(source_dir: str) -> list:
        if os.path.basename(os.path.normpath(source_dir)).startswith(PROCESSED_FOLDER_PREFIX):
            return [source_dir]
        pattern = os.path.join(source_dir, PROCESSED_FOLDER_PREFIX + "*")
        return sorted(p for p in glob.glob(pattern) if os.path.isdir(p))

    @staticmethod
    def find_pdfs(folder: str) -> list:
        docs = []
        for path in glob.glob(os.path.join(folder, "*")):
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf" or ext in IMAGE_EXTENSIONS:
                docs.append(path)
        return sorted(set(docs))

    @classmethod
    def count_documents(cls, source_dir: str) -> tuple[int, int]:
        """Return (folder_count, document_count) for a source directory."""
        folders = cls.find_newdocs_folders(source_dir)
        total = sum(len(cls.find_pdfs(f)) for f in folders)
        return len(folders), total

    # ---------- Image preparation ----------

    def prepare_image(self, image_path: str, max_dim: int = MAX_IMAGE_DIMENSION) -> bytes | None:
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                w, h = img.size
                longest = max(w, h)
                if longest > max_dim:
                    scale = max_dim / longest
                    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
                    img = img.resize(new_size, Image.LANCZOS)
                    self._log("ย่อขนาดรูปภาพ", f"ปรับขนาดรูป {os.path.basename(image_path)} จาก {w}x{h} เป็น {new_size[0]}x{new_size[1]} พิกเซล เพื่อให้ประมวลผลได้เร็วขึ้น")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                return buf.getvalue()
        except Exception as e:
            self._log("เปิดไฟล์", f"ไม่สามารถเปิดไฟล์รูปภาพ {os.path.basename(image_path)} ได้ ไฟล์อาจเสียหายหรือไม่ใช่ชนิดไฟล์ที่รองรับ", "error",
                      hint=f"ลองเปิดไฟล์ด้วยโปรแกรมดูรูปภาพ หากเปิดไม่ได้ให้สแกนเอกสารใหม่และบันทึกเป็นไฟล์ {SUPPORTED_LABEL} ก่อนนำเข้าประมวลผลอีกครั้ง")
            return None

    # ---------- AI extraction ----------

    def extract_data(self, pdf_path: str) -> dict | None:
        ext = os.path.splitext(pdf_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            data = None
            for max_dim in (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION_RETRY):
                file_bytes = self.prepare_image(pdf_path, max_dim)
                if not file_bytes:
                    return None
                data = self._call_ai(file_bytes, "image/jpeg")
                if data is not None and self._ids_readable(data):
                    return data
                if max_dim != MAX_IMAGE_DIMENSION_RETRY:
                    self._log("ตรวจสอบด้วย AI", f"อ่านเลขบัตรประชาชนในไฟล์ {os.path.basename(pdf_path)} ไม่ชัดเจน กำลังลองอ่านใหม่ด้วยความละเอียดสูงขึ้น", "warning")
            return data
        try:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            self._log("เปิดไฟล์", f"ไม่สามารถเปิดไฟล์ {os.path.basename(pdf_path)} ได้ ไฟล์อาจถูกล็อกหรือเสียหาย", "error",
                      hint="ปิดโปรแกรมอื่นที่อาจเปิดไฟล์นี้ค้างอยู่ แล้วลองประมวลผลใหม่ หากยังไม่ได้ให้สแกนเอกสารใหม่แทนไฟล์เดิม")
            return None
        if not file_bytes:
            self._log("เปิดไฟล์", f"ไฟล์ {os.path.basename(pdf_path)} ไม่มีข้อมูลภายใน (ไฟล์ว่างเปล่า)", "error",
                      hint="ไฟล์นี้บันทึกมาไม่สมบูรณ์ ให้สแกนเอกสารใหม่แล้วนำไฟล์ใหม่มาแทนที่ก่อนประมวลผลอีกครั้ง")
            return None
        return self._call_ai(file_bytes, "application/pdf")

    @staticmethod
    def _ids_readable(data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        id_top = data.get("id_card_top") or data.get("id_card")
        id_body = data.get("id_card_body")
        return bool(
            (id_top and re.fullmatch(r"\d{13}", str(id_top)))
            or (id_body and re.fullmatch(r"\d{13}", str(id_body)))
        )

    def _call_ai(self, file_bytes: bytes, mime_type: str) -> dict | None:
        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._log("ตรวจสอบด้วย AI", "กำลังส่งเอกสารให้ระบบ AI อ่านและตรวจสอบข้อมูล")
                    response = self.model.generate_content(
                        [
                            {"mime_type": mime_type, "data": file_bytes},
                            self.prompt,
                        ]
                    )
                    raw = (response.text or "").strip()
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
                    return json.loads(raw)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                        wait_match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
                        wait_time = float(wait_match.group(1)) + 2 if wait_match else 40
                        if attempt < max_retries - 1:
                            self._log("เชื่อมต่อ AI", f"ระบบ AI มีผู้ใช้งานหนาแน่นในขณะนี้ กำลังรอ {wait_time:.0f} วินาทีแล้วลองใหม่อีกครั้ง (ครั้งที่ {attempt + 1}/{max_retries})", "warning")
                            time.sleep(wait_time)
                            continue
                        self._log("เชื่อมต่อ AI", "เชื่อมต่อระบบ AI ไม่สำเร็จเนื่องจากมีผู้ใช้งานหนาแน่น กรุณาลองประมวลผลไฟล์นี้ใหม่อีกครั้งภายหลัง", "error",
                                  hint="รอประมาณ 1-2 นาทีแล้วกด \"เริ่มประมวลผล\" อีกครั้ง ไฟล์ที่ค้างอยู่ในโฟลเดอร์ต้นทางจะถูกประมวลผลต่อโดยอัตโนมัติ")
                        return None
                    raise
        except json.JSONDecodeError:
            self._log("ตรวจสอบด้วย AI", "ระบบ AI ส่งข้อมูลกลับมาในรูปแบบที่ไม่สามารถอ่านได้ ไฟล์นี้จะถูกส่งไปตรวจสอบด้วยตนเอง", "error",
                      hint="ลองประมวลผลไฟล์นี้ใหม่อีกครั้ง หากยังไม่ได้ให้สแกนเอกสารใหม่ให้คมชัดขึ้นก่อนนำเข้าระบบ")
            return None
        except Exception as e:
            self._log("เชื่อมต่อ AI", f"เกิดข้อผิดพลาดขณะเชื่อมต่อระบบ AI: {str(e)[:150]}", "error",
                      hint="ตรวจสอบการเชื่อมต่ออินเทอร์เน็ตและคีย์ API ในหน้าตั้งค่า จากนั้นกด \"เริ่มประมวลผล\" ใหม่อีกครั้ง")
            return None

    # ---------- Validation ----------

    @staticmethod
    def is_valid_thai_id(id_number) -> bool:
        """Offline validity check for a 13-digit Thai national ID using the
        official checksum (mod 11) algorithm.

        The first 12 digits are weighted 13..2, summed, then the check digit is
        (11 - (sum % 11)) % 10 and must equal the 13th digit."""
        digits = re.sub(r"\D", "", str(id_number or ""))
        if len(digits) != 13:
            return False
        total = sum(int(digits[i]) * (13 - i) for i in range(12))
        check = (11 - (total % 11)) % 10
        return check == int(digits[12])

    @classmethod
    def validate(cls, data: dict) -> str | None:
        if not isinstance(data, dict):
            return "AI response is not a JSON object."
        name = data.get("name")
        id_top = data.get("id_card_top") or data.get("id_card")
        id_body = data.get("id_card_body")
        loan_type = data.get("loan_type")
        signed = data.get("signed")
        if not name or not str(name).strip():
            return "ไม่พบชื่อ-นามสกุล"
        top_ok = bool(id_top and re.fullmatch(r"\d{13}", str(id_top)))
        body_ok = bool(id_body and re.fullmatch(r"\d{13}", str(id_body)))
        if not top_ok and not body_ok:
            return "อ่านเลขบัตร 13 หลักไม่ได้"
        if top_ok and body_ok and str(id_top) != str(id_body):
            return "เลขบัตรบน/ล่างไม่ตรงกัน"
        id_card = str(id_top) if top_ok else str(id_body)
        if not cls.is_valid_thai_id(id_card):
            return "เลขบัตรประชาชนไม่ถูกต้อง (หลักตรวจสอบไม่ผ่าน)"
        if loan_type not in LOAN_TYPES:
            return "ไม่พบประเภทการกู้"
        if signed is not True:
            return "ไม่พบลายเซ็นผู้กู้"
        return None

    @staticmethod
    def sanitize_filename(text: str) -> str:
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text)).strip()
        return re.sub(r"\s+", " ", text)

    # ---------- File operations ----------

    @staticmethod
    def unique_path(path: str) -> str:
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        i = 1
        while os.path.exists(f"{base} ({i}){ext}"):
            i += 1
        return f"{base} ({i}){ext}"

    def move_to_manual(self, pdf_path: str, output_dir: str, reason: str) -> str:
        manual_dir = os.path.join(output_dir, MANUAL_FOLDER_NAME)
        os.makedirs(manual_dir, exist_ok=True)
        dest = self.unique_path(os.path.join(manual_dir, os.path.basename(pdf_path)))
        shutil.move(pdf_path, dest)
        self._log("จัดเก็บไฟล์", f"ย้ายไฟล์ {os.path.basename(pdf_path)} ไปที่โฟลเดอร์ตรวจสอบด้วยตนเอง (Manual) เนื่องจาก: {reason}", "warning",
                  hint=fix_hint(reason))
        return os.path.basename(dest)

    def move_to_loan_folder(self, pdf_path: str, output_dir: str, data: dict) -> str:
        id_card = str(data.get("id_card_top") or data.get("id_card") or data.get("id_card_body"))
        loan_type = data["loan_type"]
        folder_name = LOAN_TYPE_FOLDERS[loan_type]
        dest_dir = os.path.join(output_dir, folder_name)
        os.makedirs(dest_dir, exist_ok=True)
        ext = os.path.splitext(pdf_path)[1].lower() or ".pdf"
        new_name = f"{id_card}{ext}"
        dest = self.unique_path(os.path.join(dest_dir, new_name))
        shutil.move(pdf_path, dest)
        self._log("จัดเก็บไฟล์", f"จัดเก็บไฟล์เรียบร้อยที่โฟลเดอร์ {folder_name} ด้วยชื่อไฟล์ {os.path.basename(dest)}", "success")
        return os.path.basename(dest)

    # ---------- Main loop ----------

    def run(self, source_dir: str, output_dir: str) -> dict:
        """Process every document. Emits per-file results through result_fn and
        returns a summary dict. Safe against being stopped mid-run."""
        started = time.time()
        self.started_at = started
        self.total_ok = 0
        self.total_manual = 0
        self._log("เริ่มต้น", "เริ่มต้นค้นหาโฟลเดอร์เอกสารที่ต้องประมวลผล")
        folders = self.find_newdocs_folders(source_dir)
        if not folders:
            self._log("ค้นหาไฟล์", f"ไม่พบโฟลเดอร์เอกสารใหม่ (ชื่อขึ้นต้นด้วย '{PROCESSED_FOLDER_PREFIX}') ในโฟลเดอร์ต้นทางที่เลือกไว้", "error",
                      hint=f"สร้างโฟลเดอร์ชื่อขึ้นต้นด้วย '{PROCESSED_FOLDER_PREFIX}' ในโฟลเดอร์ต้นทาง แล้วนำไฟล์เอกสารไปวางไว้ในนั้นก่อนเริ่มประมวลผล")

        self.planned_total = sum(len(self.find_pdfs(f)) for f in folders)
        index = 0
        for folder in folders:
            if self.stop_flag.is_set():
                break
            pdfs = self.find_pdfs(folder)
            self._log("ค้นหาไฟล์", f"พบโฟลเดอร์ {os.path.basename(folder)} มีเอกสารทั้งหมด {len(pdfs)} ไฟล์")

            for pdf_path in pdfs:
                if self.stop_flag.is_set():
                    self._log("หยุดการทำงาน", "ผู้ใช้งานสั่งหยุดการประมวลผลกลางคัน", "warning")
                    break
                index += 1
                filename = os.path.basename(pdf_path)
                self._log("เปิดไฟล์", f"กำลังประมวลผลไฟล์ที่ {index}: {filename}")
                data = self.extract_data(pdf_path)

                if data is None:
                    dest_name = self.move_to_manual(pdf_path, output_dir, "AI อ่านไฟล์ไม่ได้")
                    self.total_manual += 1
                    self.emit_result(self._result(index, filename, None, "manual", "AI อ่านไฟล์ไม่ได้", rel_path=f"Manual/{dest_name}"))
                    continue

                error = self.validate(data)
                if error:
                    self._log("ตรวจสอบความถูกต้อง", f"ไฟล์ {filename} ข้อมูลไม่ผ่านเกณฑ์: {error}", "warning", hint=fix_hint(error))
                    dest_name = self.move_to_manual(pdf_path, output_dir, error)
                    self.total_manual += 1
                    self.emit_result(self._result(index, filename, data, "manual", error, rel_path=f"Manual/{dest_name}"))
                    continue

                try:
                    self._log("ตรวจสอบความถูกต้อง", f"ไฟล์ {filename} ผ่านการตรวจสอบครบทุกเงื่อนไข", "success")
                    dest_name = self.move_to_loan_folder(pdf_path, output_dir, data)
                    self.total_ok += 1
                    loan_folder = LOAN_TYPE_FOLDERS[data["loan_type"]]
                    self.emit_result(self._result(index, filename, data, "success", "", rel_path=f"{loan_folder}/{dest_name}"))
                except Exception as e:
                    self._log("จัดเก็บไฟล์", f"ไม่สามารถย้ายไฟล์ {filename} ได้: {e}", "error",
                              hint="ตรวจสอบว่าโฟลเดอร์ปลายทางยังอยู่ ไม่ถูกลบหรือเปลี่ยนชื่อ มีพื้นที่ว่างเพียงพอ และมีสิทธิ์เขียนไฟล์ จากนั้นลองประมวลผลใหม่")
                    dest_name = self.move_to_manual(pdf_path, output_dir, f"move error: {e}")
                    self.total_manual += 1
                    self.emit_result(self._result(index, filename, data, "manual", f"ย้ายไฟล์ไม่สำเร็จ: {e}", rel_path=f"Manual/{dest_name}"))

        elapsed = int(time.time() - started)
        done = self.total_ok + self.total_manual
        stopped = self.stop_flag.is_set()
        remaining = max(0, self.planned_total - done)
        if stopped and remaining:
            self._log("หยุดการทำงาน",
                      f"หยุดการประมวลผลกลางคัน — ประมวลผลไปแล้ว {done} จาก {self.planned_total} ไฟล์ เหลืออีก {remaining} ไฟล์",
                      "warning",
                      hint="ไฟล์ที่ยังไม่ได้ประมวลผลยังอยู่ในโฟลเดอร์ต้นทาง กด \"เริ่มประมวลผล\" อีกครั้งเพื่อประมวลผลไฟล์ที่เหลือต่อได้ทันที")
        else:
            avg = round(elapsed / done, 1) if done else 0
            self._log("เสร็จสิ้น", f"ประมวลผลเสร็จสิ้นทั้งหมด — สำเร็จ {self.total_ok} ไฟล์ ต้องตรวจสอบเพิ่มเติม {self.total_manual} ไฟล์ ใช้เวลารวม {elapsed // 60} นาที {elapsed % 60} วินาที (เฉลี่ย {avg} วินาที/ไฟล์)", "success")
        return self.summary(status="stopped" if (stopped and remaining) else "completed")

    def summary(self, status: str = "completed") -> dict:
        """Build a summary from the current counters. Also used to salvage a
        partial summary when the run crashes mid-way."""
        elapsed = int(time.time() - getattr(self, "started_at", time.time()))
        done = getattr(self, "total_ok", 0) + getattr(self, "total_manual", 0)
        planned = getattr(self, "planned_total", done)
        return {
            "total": done,
            "success": getattr(self, "total_ok", 0),
            "manual": getattr(self, "total_manual", 0),
            "planned": planned,
            "remaining": max(0, planned - done),
            "status": status,
            "elapsed": elapsed,
            "elapsed_label": f"{elapsed // 60}:{elapsed % 60:02d}",
            "avg_seconds": round(elapsed / done, 1) if done else 0,
        }

    @staticmethod
    def _to_number(value):
        """Coerce an AI-extracted amount into a number, or None if not parseable.
        Strips commas, currency words and spaces so '25,000 บาท' -> 25000.0."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        if cleaned in ("", "-", ".", "-."):
            return None
        try:
            num = float(cleaned)
        except ValueError:
            return None
        return int(num) if num.is_integer() else num

    @classmethod
    def _result(cls, index: int, filename: str, data: dict | None, status: str, reason: str, rel_path: str = "") -> dict:
        data = data or {}
        return {
            "index": index,
            "filename": filename,
            "name": data.get("name") or "-",
            "id_card": str(data.get("id_card_top") or data.get("id_card") or data.get("id_card_body") or "-"),
            "loan_type": data.get("loan_type") or "-",
            "signed": bool(data.get("signed")),
            "tuition_fee": cls._to_number(data.get("tuition_fee")),
            "living_allowance_monthly": cls._to_number(data.get("living_allowance_monthly")),
            "living_allowance_months": cls._to_number(data.get("living_allowance_months")),
            "living_allowance_total": cls._to_number(data.get("living_allowance_total")),
            "net_total": cls._to_number(data.get("net_total")),
            "status": status,
            "reason": reason,
            "rel_path": rel_path,
        }
