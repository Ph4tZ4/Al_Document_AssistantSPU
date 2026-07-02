"""
AI Document Assistant
---------------------
Windows Desktop App (cross-platform code) that:
1. Scans all folders starting with "NewDocs" inside a selected source directory.
2. Sends each scanned PDF to the Gemini API to extract: Name, 13-digit ID Card, Loan Type.
3. Renames the file to Name_IDCard_LoanType.pdf.
4. Moves the file into a destination folder matching its Loan Type.
5. Moves unreadable / incomplete / corrupted files into a "Manual" folder for human review.
"""

from __future__ import annotations

import os
import re
import glob
import json
import shutil
import queue
import time
import threading
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox

# pyrefly: ignore [missing-import]
import google.generativeai as genai
from dotenv import load_dotenv

# Load GEMINI_API_KEY from a .env file next to this script (if it exists)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ============================================================
# CONFIGURATION — edit these to match your organization
# ============================================================

# The 4 valid loan types. The AI is forced to pick exactly one of these.
LOAN_TYPES = [
    "Type1",
    "Type2",
    "Type3",
    "Type4",
]

# Destination folder name for each loan type (created inside the output directory).
LOAN_TYPE_FOLDERS = {
    "Type1": "Type1",
    "Type2": "Type2",
    "Type3": "Type3",
    "Type4": "Type4",
}

MANUAL_FOLDER_NAME = "Manual"          # Folder for files that need human review
PROCESSED_FOLDER_PREFIX = "NewDocs"    # Source folders: NewDocs, NewDocs 2, NewDocs 3, ...
GEMINI_MODEL_NAME = "gemini-2.5-flash" # Or "gemini-2.5-pro" for higher accuracy

# ============================================================
# GEMINI PROMPT — the exact instruction sent with every PDF
# ============================================================

GEMINI_PROMPT = f"""You are a document data extraction system for a loan department.
You will receive a scanned PDF document (it may be a photo/scan, possibly in Thai or English).

Read the document carefully and extract EXACTLY these three fields:

1. "name": The full name of the applicant/customer (first name and last name, as written in the document).
2. "id_card": The 13-digit national ID card number. Return DIGITS ONLY, no spaces or dashes. It must be exactly 13 digits.
3. "loan_type": The type of loan. Look for "ประเภท" or "Type" in the document and map it as follows:
   - If the type is 1 or Type 1 or ประเภท 1, return "{LOAN_TYPES[0]}".
   - If the type is 2 or Type 2 or ประเภท 2, return "{LOAN_TYPES[1]}".
   - If the type is 3 or Type 3 or ประเภท 3, return "{LOAN_TYPES[2]}".
   - If the type is 4 or Type 4 or ประเภท 4, return "{LOAN_TYPES[3]}".
   The value MUST be exactly one of: "{LOAN_TYPES[0]}", "{LOAN_TYPES[1]}", "{LOAN_TYPES[2]}", "{LOAN_TYPES[3]}".

STRICT RULES:
- Respond with ONLY a single valid JSON object. No markdown, no code fences, no explanations.
- The JSON must have exactly these keys: "name", "id_card", "loan_type".
- If ANY field cannot be found or read with confidence, set that field's value to null.
- Do NOT guess or invent data. If the document is unreadable, return all fields as null.

Example of a valid response:
{{"name": "Somchai Jaidee", "id_card": "1234567890123", "loan_type": "{LOAN_TYPES[0]}"}}

Example when data is missing:
{{"name": null, "id_card": null, "loan_type": null}}
"""

# ============================================================
# CORE PROCESSING LOGIC
# ============================================================


class DocumentProcessor:
    def __init__(self, api_key: str, log_fn):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            generation_config={"response_mime_type": "application/json"},
        )
        self.log = log_fn
        self.stop_flag = threading.Event()

    # ---------- Folder discovery ----------

    @staticmethod
    def find_newdocs_folders(source_dir: str) -> list:
        """Find all folders starting with 'NewDocs' (NewDocs, NewDocs 2, NewDocs 3, ...).

        If the selected source directory itself starts with 'NewDocs', use it directly."""
        if os.path.basename(os.path.normpath(source_dir)).startswith(PROCESSED_FOLDER_PREFIX):
            return [source_dir]
        pattern = os.path.join(source_dir, PROCESSED_FOLDER_PREFIX + "*")
        return sorted(p for p in glob.glob(pattern) if os.path.isdir(p))

    @staticmethod
    def find_pdfs(folder: str) -> list:
        pdfs = glob.glob(os.path.join(folder, "*.pdf"))
        pdfs += glob.glob(os.path.join(folder, "*.PDF"))
        return sorted(set(pdfs))

    # ---------- AI extraction ----------

    def extract_data(self, pdf_path: str) -> dict | None:
        """Send the PDF to Gemini and return the parsed JSON dict, or None on failure."""
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            if not pdf_bytes:
                self.log(f"  [ERROR] Empty file: {os.path.basename(pdf_path)}")
                return None

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(
                        [
                            {"mime_type": "application/pdf", "data": pdf_bytes},
                            GEMINI_PROMPT,
                        ]
                    )
                    raw = (response.text or "").strip()
                    # Strip accidental markdown fences, just in case
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
                    return json.loads(raw)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                        # Extract retry delay from error message if possible
                        wait_match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
                        wait_time = float(wait_match.group(1)) + 2 if wait_match else 40
                        if attempt < max_retries - 1:
                            self.log(f"  [RATE LIMIT] Waiting {wait_time:.0f}s before retry ({attempt + 1}/{max_retries})...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self.log(f"  [ERROR] Rate limit exceeded after {max_retries} retries.")
                            return None
                    else:
                        raise
        except json.JSONDecodeError:
            self.log("  [ERROR] AI returned invalid JSON.")
            return None
        except Exception as e:
            self.log(f"  [ERROR] AI/file error: {e}")
            return None

    # ---------- Validation ----------

    @staticmethod
    def validate(data: dict) -> str | None:
        """Return an error message if data is invalid, else None."""
        if not isinstance(data, dict):
            return "AI response is not a JSON object."
        name = data.get("name")
        id_card = data.get("id_card")
        loan_type = data.get("loan_type")
        if not name or not str(name).strip():
            return "Missing name."
        if not id_card or not re.fullmatch(r"\d{13}", str(id_card)):
            return f"Invalid ID card: {id_card!r} (must be 13 digits)."
        if loan_type not in LOAN_TYPES:
            return f"Unknown loan type: {loan_type!r}."
        return None

    @staticmethod
    def sanitize_filename(text: str) -> str:
        """Remove characters that are invalid in Windows filenames."""
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text)).strip()
        return re.sub(r"\s+", " ", text)

    # ---------- File operations ----------

    @staticmethod
    def unique_path(path: str) -> str:
        """If path exists, append (1), (2), ... to avoid overwriting."""
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        i = 1
        while os.path.exists(f"{base} ({i}){ext}"):
            i += 1
        return f"{base} ({i}){ext}"

    def move_to_manual(self, pdf_path: str, output_dir: str, reason: str):
        manual_dir = os.path.join(output_dir, MANUAL_FOLDER_NAME)
        os.makedirs(manual_dir, exist_ok=True)
        dest = self.unique_path(os.path.join(manual_dir, os.path.basename(pdf_path)))
        shutil.move(pdf_path, dest)
        self.log(f"  [MANUAL] {os.path.basename(pdf_path)} -> Manual ({reason})")

    def move_to_loan_folder(self, pdf_path: str, output_dir: str, data: dict):
        name = self.sanitize_filename(data["name"])
        id_card = str(data["id_card"])
        loan_type = data["loan_type"]
        folder_name = LOAN_TYPE_FOLDERS[loan_type]

        dest_dir = os.path.join(output_dir, folder_name)
        os.makedirs(dest_dir, exist_ok=True)

        new_name = f"{name}_{id_card}_{self.sanitize_filename(loan_type)}.pdf"
        dest = self.unique_path(os.path.join(dest_dir, new_name))
        shutil.move(pdf_path, dest)
        self.log(f"  [OK] -> {folder_name}{os.sep}{os.path.basename(dest)}")

    # ---------- Main loop ----------

    def run(self, source_dir: str, output_dir: str):
        folders = self.find_newdocs_folders(source_dir)
        if not folders:
            self.log(f"[WARN] No '{PROCESSED_FOLDER_PREFIX}*' folders found in {source_dir}")
            return

        total_ok = total_manual = 0
        for folder in folders:
            if self.stop_flag.is_set():
                break
            pdfs = self.find_pdfs(folder)
            self.log(f"[FOLDER] {os.path.basename(folder)} — {len(pdfs)} PDF(s)")

            for pdf_path in pdfs:
                if self.stop_flag.is_set():
                    break
                self.log(f"  Processing: {os.path.basename(pdf_path)}")
                data = self.extract_data(pdf_path)

                if data is None:
                    self.move_to_manual(pdf_path, output_dir, "AI could not read file")
                    total_manual += 1
                    continue

                error = self.validate(data)
                if error:
                    self.move_to_manual(pdf_path, output_dir, error)
                    total_manual += 1
                    continue

                try:
                    self.move_to_loan_folder(pdf_path, output_dir, data)
                    total_ok += 1
                except Exception as e:
                    self.log(f"  [ERROR] Move failed: {e}")
                    self.move_to_manual(pdf_path, output_dir, f"move error: {e}")
                    total_manual += 1

        self.log(f"[DONE] Sorted: {total_ok} | Manual review: {total_manual}")


# ============================================================
# GUI
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Document Assistant")
        self.geometry("760x600")
        self.minsize(640, 500)

        self.source_dir = ctk.StringVar(value="")
        self.output_dir = ctk.StringVar(value="")
        self.api_key = ctk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.processor: DocumentProcessor | None = None
        self.worker: threading.Thread | None = None

        self._build_ui()
        self._poll_log_queue()

    # ---------- UI construction ----------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        header = ctk.CTkLabel(self, text="AI Document Assistant",
                              font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=(16, 4))
        sub = ctk.CTkLabel(self, text="Scan NewDocs folders → Extract data with Gemini → Rename & sort PDFs",
                           text_color="gray")
        sub.pack(pady=(0, 8))

        # API key row
        row_api = ctk.CTkFrame(self)
        row_api.pack(fill="x", **pad)
        ctk.CTkLabel(row_api, text="Gemini API Key:", width=130, anchor="w").pack(side="left", padx=8)
        ctk.CTkEntry(row_api, textvariable=self.api_key, show="*").pack(
            side="left", fill="x", expand=True, padx=8, pady=8)

        # Source dir row
        row_src = ctk.CTkFrame(self)
        row_src.pack(fill="x", **pad)
        ctk.CTkLabel(row_src, text="Source Directory:", width=130, anchor="w").pack(side="left", padx=8)
        ctk.CTkEntry(row_src, textvariable=self.source_dir).pack(
            side="left", fill="x", expand=True, padx=8, pady=8)
        ctk.CTkButton(row_src, text="Browse…", width=90,
                      command=self._pick_source).pack(side="left", padx=8)

        # Output dir row
        row_out = ctk.CTkFrame(self)
        row_out.pack(fill="x", **pad)
        ctk.CTkLabel(row_out, text="Output Directory:", width=130, anchor="w").pack(side="left", padx=8)
        ctk.CTkEntry(row_out, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=8, pady=8)
        ctk.CTkButton(row_out, text="Browse…", width=90,
                      command=self._pick_output).pack(side="left", padx=8)

        # Buttons row
        row_btn = ctk.CTkFrame(self, fg_color="transparent")
        row_btn.pack(fill="x", **pad)
        self.start_btn = ctk.CTkButton(row_btn, text="▶  Start Processing",
                                       height=40, command=self._start)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.stop_btn = ctk.CTkButton(row_btn, text="■  Stop", height=40,
                                      fg_color="#8b2e2e", hover_color="#6e2424",
                                      state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # Log box
        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Courier", size=12))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.log_box.configure(state="disabled")

    # ---------- Callbacks ----------

    def _pick_source(self):
        path = filedialog.askdirectory(title="Select Source Directory (contains NewDocs folders)")
        if path:
            self.source_dir.set(path)
            if not self.output_dir.get():
                self.output_dir.set(path)  # default output = source

    def _pick_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir.set(path)

    def _start(self):
        src = self.source_dir.get().strip()
        out = self.output_dir.get().strip() or src
        key = self.api_key.get().strip()

        if not key:
            messagebox.showerror("Missing API Key", "Please enter your Gemini API key.")
            return
        if not src or not os.path.isdir(src):
            messagebox.showerror("Invalid Source", "Please select a valid source directory.")
            return
        os.makedirs(out, exist_ok=True)

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log(f"=== Started at {datetime.now():%Y-%m-%d %H:%M:%S} ===")

        self.processor = DocumentProcessor(api_key=key, log_fn=self.log)
        self.worker = threading.Thread(
            target=self._run_worker, args=(src, out), daemon=True)
        self.worker.start()

    def _run_worker(self, src: str, out: str):
        try:
            self.processor.run(src, out)
        except Exception as e:
            self.log(f"[FATAL] {e}")
        finally:
            self.log_queue.put("__WORKER_DONE__")

    def _stop(self):
        if self.processor:
            self.processor.stop_flag.set()
            self.log("[INFO] Stop requested — finishing current file…")

    # ---------- Logging (thread-safe via queue) ----------

    def log(self, message: str):
        self.log_queue.put(message)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__WORKER_DONE__":
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    continue
                self.log_box.configure(state="normal")
                self.log_box.insert("end", msg + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()
