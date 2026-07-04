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
# GUI — minimalist design language
# ============================================================

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

APP_VERSION = "1.2.0"

# ---- Theme colors (light, dark) ----
COL_WINDOW = ("#F5F5F7", "#1E1E20")          # window background
COL_SIDEBAR = ("#EAEAEC", "#28282B")         # sidebar background
COL_SIDEBAR_SEP = ("#D5D5D8", "#3A3A3E")     # sidebar separator
COL_TITLEBAR = ("#EDEDEF", "#2A2A2D")        # top toolbar
COL_CARD = ("#FFFFFF", "#2C2C30")            # elevated cards
COL_CARD_BORDER = ("#E3E3E6", "#3D3D42")     # hairline borders
COL_SHADOW = ("#D0D0D4", "#111113")          # card shadow layer
COL_TEXT = ("#1D1D1F", "#F5F5F7")            # primary text
COL_TEXT_SECONDARY = ("#86868B", "#98989D")  # secondary text
COL_TEXT_TERTIARY = ("#AEAEB2", "#636366")   # captions / metadata
COL_ACCENT = ("#007AFF", "#0A84FF")          # accent blue
COL_ACCENT_HOVER = ("#0071E3", "#409CFF")
COL_ACCENT_SUBTLE = ("#E8F0FE", "#1A3A5C")  
COL_SUCCESS = ("#34C759", "#30D158")         # success green
COL_SUCCESS_HOVER = ("#28A745", "#28CD50")
COL_DESTRUCTIVE = ("#FF3B30", "#FF453A")     # destructive red
COL_DESTRUCTIVE_HOVER = ("#E0352B", "#FF6961")
COL_FIELD = ("#F2F2F4", "#3A3A3E")           # input fields
COL_NAV_ACTIVE = ("#DCDCE0", "#3A3A40")      # active navigation item
COL_PROGRESS_BG = ("#E5E5EA", "#38383C")     # progress bar background

SF_PRO = ".AppleSystemUIFont"   # Tk alias for system font
SF_MONO = "SF Mono"


def sf(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=SF_PRO, size=size, weight=weight)


class Tooltip:
    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._tip_window = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _e=None):
        if self._tip_window:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        tw = self._tip_window = ctk.CTkToplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        lbl = ctk.CTkLabel(
            tw, text=self._text, font=sf(11),
            fg_color=COL_CARD, text_color=COL_TEXT,
            corner_radius=6, padx=10, pady=4)
        lbl.pack()

    def _hide(self, _e=None):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Document Assistant")
        self.geometry("1020x720")
        self.minsize(840, 580)
        self.configure(fg_color=COL_WINDOW)

        self.source_dir = ctk.StringVar(value="")
        self.output_dir = ctk.StringVar(value="")
        self.api_key = ctk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.processor: DocumentProcessor | None = None
        self.worker: threading.Thread | None = None

        self._sidebar_visible = True
        self._sidebar_collapsed = False
        self._active_nav = "process"

        # Statistics
        self._stat_ok = 0
        self._stat_manual = 0
        self._stat_total = 0
        self._processing_start: float | None = None

        self._build_ui()
        self._poll_log_queue()

    # ---------- UI construction ----------

    def _build_ui(self):
        # Base window container
        self.window = ctk.CTkFrame(
            self, corner_radius=0, fg_color=COL_WINDOW, border_width=0)
        self.window.pack(fill="both", expand=True)
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_columnconfigure(1, weight=1)

        self._build_titlebar()
        self._build_sidebar()
        self._build_content()
        self._show_page("process")

    # ----- Top Toolbar -----

    def _build_titlebar(self):
        self.titlebar = ctk.CTkFrame(
            self.window, height=50, corner_radius=0, fg_color=COL_TITLEBAR,
            border_width=0)
        self.titlebar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.titlebar.grid_propagate(False)
        self.titlebar.grid_columnconfigure(2, weight=1)

        sidebar_toggle = ctk.CTkButton(
            self.titlebar, text="Menu", width=60, height=28, corner_radius=6,
            fg_color="transparent", hover_color=COL_NAV_ACTIVE,
            text_color=COL_TEXT_SECONDARY, font=sf(12, "bold"),
            command=self._toggle_sidebar)
        sidebar_toggle.grid(row=0, column=1, padx=12, pady=11)
        Tooltip(sidebar_toggle, "Toggle Sidebar")

        title = ctk.CTkLabel(
            self.titlebar, text="AI Document Assistant",
            font=sf(13, "bold"), text_color=COL_TEXT)
        title.grid(row=0, column=2)

        self.appearance_btn = ctk.CTkSegmentedButton(
            self.titlebar, values=["Light", "Dark"], width=130, height=28,
            corner_radius=6, font=sf(11),
            fg_color=COL_FIELD, selected_color=COL_CARD,
            selected_hover_color=COL_CARD,
            unselected_color=COL_FIELD, unselected_hover_color=COL_NAV_ACTIVE,
            text_color=COL_TEXT,
            command=self._set_appearance)
        self.appearance_btn.set("Dark" if ctk.get_appearance_mode() == "Dark" else "Light")
        self.appearance_btn.grid(row=0, column=3, padx=16, pady=11)

    # ----- Sidebar -----

    def _build_sidebar(self):
        self._sidebar_container = ctk.CTkFrame(
            self.window, fg_color="transparent", corner_radius=0)
        self._sidebar_container.grid(
            row=1, column=0, sticky="nsw", padx=0, pady=0)
        self._sidebar_container.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self._sidebar_container, width=220, corner_radius=0,
            fg_color=COL_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Right-edge border line
        self._sidebar_sep = ctk.CTkFrame(
            self._sidebar_container, width=1, fg_color=COL_SIDEBAR_SEP,
            corner_radius=0)
        self._sidebar_sep.grid(row=0, column=1, sticky="ns")

        # Branding
        self._sidebar_name = ctk.CTkLabel(
            self.sidebar, text="Document Assistant",
            font=sf(14, "bold"), text_color=COL_TEXT)
        self._sidebar_name.pack(pady=(28, 2))
        self._sidebar_sub = ctk.CTkLabel(
            self.sidebar, text="System Manager",
            font=sf(11), text_color=COL_TEXT_TERTIARY)
        self._sidebar_sub.pack(pady=(0, 24))

        self._nav_header = ctk.CTkLabel(
            self.sidebar, text="  NAVIGATION", font=sf(10, "bold"),
            text_color=COL_TEXT_TERTIARY, anchor="w")
        self._nav_header.pack(fill="x", padx=12, pady=(0, 4))

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in [
            ("process", "Process Documents"),
            ("settings", "Settings"),
        ]:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                height=36, corner_radius=6, font=sf(13),
                fg_color="transparent", hover_color=COL_NAV_ACTIVE,
                text_color=COL_TEXT,
                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = btn

        # Status and version at bottom
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=16)

        self._version_label = ctk.CTkLabel(
            bottom, text=f"v{APP_VERSION}", font=sf(10),
            text_color=COL_TEXT_TERTIARY)
        self._version_label.pack(side="bottom", pady=(4, 0))

        self.status_label = ctk.CTkLabel(
            bottom, text="Status: Ready", font=sf(11),
            text_color=COL_TEXT_SECONDARY)
        self.status_label.pack(side="bottom")

    # ----- Content Area -----

    def _build_content(self):
        self.content = ctk.CTkFrame(
            self.window, corner_radius=0, fg_color="transparent")
        self.content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        self.pages: dict[str, ctk.CTkFrame] = {
            "process": self._build_process_page(),
            "settings": self._build_settings_page(),
        }

    def _card(self, parent, shadow: bool = True) -> ctk.CTkFrame:
        if shadow:
            wrapper = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
            shadow_frame = ctk.CTkFrame(
                wrapper, corner_radius=10, fg_color=COL_SHADOW,
                border_width=0)
            shadow_frame.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0,
                               x=0, y=2)
            card = ctk.CTkFrame(
                wrapper, corner_radius=8, fg_color=COL_CARD,
                border_width=1, border_color=COL_CARD_BORDER)
            card.pack(fill="both", expand=True)
            card._shadow_wrapper = wrapper
            return card
        return ctk.CTkFrame(
            parent, corner_radius=8, fg_color=COL_CARD,
            border_width=1, border_color=COL_CARD_BORDER)

    def _pack_card(self, card, **pack_kwargs):
        target = getattr(card, "_shadow_wrapper", card)
        target.pack(**pack_kwargs)

    def _section_label(self, parent, text: str) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text=text.upper(), font=sf(10, "bold"),
            text_color=COL_TEXT_TERTIARY, anchor="w")
        return lbl

    def _field_row(self, card, label, variable, browse_cmd=None, show=None, row=0):
        self._section_label(card, label).grid(
            row=row, column=0, sticky="w", padx=18,
            pady=(16 if row == 0 else 8, 0))
        entry = ctk.CTkEntry(
            card, textvariable=variable, show=show, height=34,
            corner_radius=6, border_width=1, border_color=COL_CARD_BORDER,
            fg_color=COL_FIELD, text_color=COL_TEXT, font=sf(13),
            placeholder_text="Click Browse to select" if browse_cmd else "")
        entry.grid(row=row + 1, column=0, sticky="ew", padx=(18, 8), pady=(4, 8))
        if browse_cmd:
            browse_btn = ctk.CTkButton(
                card, text="Browse", width=80, height=34, corner_radius=6,
                fg_color=COL_FIELD, hover_color=COL_NAV_ACTIVE,
                text_color=COL_TEXT, font=sf(12),
                border_width=1, border_color=COL_CARD_BORDER,
                command=browse_cmd)
            browse_btn.grid(row=row + 1, column=1, padx=(0, 18), pady=(4, 8))
        return entry

    def _build_process_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color="transparent")

        header = ctk.CTkLabel(page, text="Process Documents",
                              font=sf(26, "bold"), text_color=COL_TEXT, anchor="w")
        header.pack(fill="x", padx=28, pady=(24, 0))
        sub = ctk.CTkLabel(
            page,
            text="Rename and sort contracts automatically using the Gemini API.",
            font=sf(13), text_color=COL_TEXT_SECONDARY, anchor="w")
        sub.pack(fill="x", padx=28, pady=(2, 16))

        # Folders setup card
        folders_card = self._card(page)
        self._pack_card(folders_card, fill="x", padx=28)
        folders_card.grid_columnconfigure(0, weight=1)
        self._field_row(folders_card, "Source Directory",
                        self.source_dir, self._pick_source, row=0)
        self._field_row(folders_card, "Output Directory",
                        self.output_dir, self._pick_output, row=2)

        self._file_count_label = ctk.CTkLabel(
            folders_card, text="", font=sf(11),
            text_color=COL_TEXT_TERTIARY, anchor="w")
        self._file_count_label.grid(
            row=4, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 14))

        # Actions
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(14, 0))
        self.start_btn = ctk.CTkButton(
            actions, text="Start Processing", height=38, corner_radius=8,
            fg_color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            font=sf(13, "bold"), command=self._start)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.stop_btn = ctk.CTkButton(
            actions, text="Stop", height=38, corner_radius=8,
            fg_color=COL_DESTRUCTIVE, hover_color=COL_DESTRUCTIVE_HOVER,
            font=sf(13, "bold"), state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # Progress bar
        self._progress_frame = ctk.CTkFrame(page, fg_color="transparent", height=6)
        self._progress_frame.pack(fill="x", padx=28, pady=(10, 0))
        self._progress_frame.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(
            self._progress_frame, height=4, corner_radius=2,
            fg_color=COL_PROGRESS_BG, progress_color=COL_ACCENT)
        self.progress_bar.pack(fill="x", pady=1)
        self.progress_bar.set(0)

        # Stats row
        stats_frame = ctk.CTkFrame(page, fg_color="transparent")
        stats_frame.pack(fill="x", padx=28, pady=(6, 10))
        self._stat_labels: dict[str, ctk.CTkLabel] = {}
        for key, label in [
            ("ok", "Sorted"),
            ("manual", "Manual Review"),
            ("elapsed", "Time Elapsed"),
        ]:
            f = ctk.CTkFrame(stats_frame, fg_color="transparent")
            f.pack(side="left", expand=True)
            lbl = ctk.CTkLabel(
                f, text=f"{label}: —", font=sf(11),
                text_color=COL_TEXT_TERTIARY)
            lbl.pack()
            self._stat_labels[key] = lbl

        # Log Card
        log_card = self._card(page)
        self._pack_card(log_card, fill="both", expand=True, padx=28, pady=(0, 22))

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=18, pady=(14, 0))
        self._section_label(log_header, "Activity Log").pack(side="left")
        self._clear_log_btn = ctk.CTkButton(
            log_header, text="Clear", width=56, height=22, corner_radius=5,
            fg_color="transparent", hover_color=COL_NAV_ACTIVE,
            text_color=COL_TEXT_TERTIARY, font=sf(11),
            command=self._clear_log)
        self._clear_log_btn.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_card, corner_radius=6, fg_color=COL_FIELD,
            text_color=COL_TEXT, border_width=0,
            font=ctk.CTkFont(family=SF_MONO, size=12),
            wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(8, 14))
        self.log_box.configure(state="disabled")
        return page

    def _build_settings_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.content, fg_color="transparent")

        header = ctk.CTkLabel(page, text="Settings",
                              font=sf(26, "bold"), text_color=COL_TEXT, anchor="w")
        header.pack(fill="x", padx=28, pady=(24, 4))
        sub = ctk.CTkLabel(
            page, text="Configure your credentials and system preferences.",
            font=sf(13), text_color=COL_TEXT_SECONDARY, anchor="w")
        sub.pack(fill="x", padx=28, pady=(0, 16))

        # API Credentials Card
        api_card = self._card(page)
        self._pack_card(api_card, fill="x", padx=28)
        api_card.grid_columnconfigure(0, weight=1)

        self._section_label(api_card, "Gemini API Key").grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 0))
        self._api_entry = ctk.CTkEntry(
            api_card, textvariable=self.api_key, show="•", height=34,
            corner_radius=6, border_width=1, border_color=COL_CARD_BORDER,
            fg_color=COL_FIELD, text_color=COL_TEXT, font=sf(13),
            placeholder_text="Enter API key")
        self._api_entry.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(4, 8))

        btn_row = ctk.CTkFrame(api_card, fg_color="transparent")
        btn_row.grid(row=1, column=1, padx=(0, 18), pady=(4, 8))
        self._api_show = False
        self._toggle_api_btn = ctk.CTkButton(
            btn_row, text="Show", width=50, height=34, corner_radius=6,
            fg_color=COL_FIELD, hover_color=COL_NAV_ACTIVE,
            text_color=COL_TEXT, font=sf(12),
            border_width=1, border_color=COL_CARD_BORDER,
            command=self._toggle_api_visibility)
        self._toggle_api_btn.pack(side="left", padx=(0, 4))

        self._save_api_btn = ctk.CTkButton(
            btn_row, text="Save", width=60, height=34, corner_radius=6,
            fg_color=COL_SUCCESS, hover_color=COL_SUCCESS_HOVER,
            text_color="#FFFFFF", font=sf(12, "bold"),
            command=self._save_api_key)
        self._save_api_btn.pack(side="left")

        self._api_status = ctk.CTkLabel(
            api_card,
            text="Stored in memory for the current session.",
            font=sf(11), text_color=COL_TEXT_TERTIARY, anchor="w")
        self._api_status.grid(
            row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 16))

        # Configuration Parameters
        self._section_label(page, "Configuration").pack(
            fill="x", padx=32, pady=(20, 6), anchor="w")
        info_card = self._card(page)
        self._pack_card(info_card, fill="x", padx=28)
        info_card.grid_columnconfigure(1, weight=1)
        for i, (k, v) in enumerate([
            ("Model", GEMINI_MODEL_NAME),
            ("Source prefix", PROCESSED_FOLDER_PREFIX),
            ("Manual folder", MANUAL_FOLDER_NAME),
            ("Loan types", ", ".join(LOAN_TYPES)),
        ]):
            ctk.CTkLabel(info_card, text=k, font=sf(12),
                         text_color=COL_TEXT_SECONDARY, anchor="w", width=180
                         ).grid(row=i, column=0, sticky="w", padx=18,
                                pady=(16 if i == 0 else 6, 16 if i == 3 else 0))
            ctk.CTkLabel(info_card, text=v, font=sf(12, "bold"),
                         text_color=COL_TEXT, anchor="w"
                         ).grid(row=i, column=1, sticky="w",
                                pady=(16 if i == 0 else 6, 16 if i == 3 else 0))

        # About App
        self._section_label(page, "About").pack(
            fill="x", padx=32, pady=(20, 6), anchor="w")
        about_card = self._card(page)
        self._pack_card(about_card, fill="x", padx=28, pady=(0, 22))

        about_inner = ctk.CTkFrame(about_card, fg_color="transparent")
        about_inner.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(
            about_inner, text="AI Document Assistant",
            font=sf(15, "bold"), text_color=COL_TEXT, anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(
            about_inner,
            text=f"Version {APP_VERSION}  •  CustomTkinter + Google Gemini",
            font=sf(11), text_color=COL_TEXT_TERTIARY, anchor="w"
        ).pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(
            about_inner,
            text="Extracts metadata from contracts, then automatically renames and sorts files.",
            font=sf(12), text_color=COL_TEXT_SECONDARY, anchor="w", justify="left"
        ).pack(fill="x", pady=(8, 0))

        return page

    # ---- Sidebar Toggle ----

    def _toggle_sidebar(self):
        if self._sidebar_collapsed:
            self.sidebar.configure(width=220)
            first_btn = list(self._nav_buttons.values())[0]
            self._sidebar_name.pack(pady=(28, 2), before=first_btn)
            self._sidebar_sub.pack(pady=(0, 24), after=self._sidebar_name)
            self._nav_header.pack(fill="x", padx=12, pady=(0, 4), after=self._sidebar_sub)
            for key, btn in self._nav_buttons.items():
                label = "Process Documents" if key == "process" else "Settings"
                btn.configure(text=label, anchor="w", width=0)
            self._version_label.configure(text=f"v{APP_VERSION}")
            self._sidebar_collapsed = False
        elif self._sidebar_visible:
            self.sidebar.configure(width=56)
            self._sidebar_name.pack_forget()
            self._sidebar_sub.pack_forget()
            self._nav_header.pack_forget()
            for key, btn in self._nav_buttons.items():
                short = "Proc" if key == "process" else "Set"
                btn.configure(text=short, anchor="center", width=36)
            self._version_label.configure(text="")
            self._sidebar_collapsed = True
        else:
            self._sidebar_container.grid()
            self._sidebar_visible = True

    def _set_appearance(self, value: str):
        mode = "dark" if "Dark" in value else "light"
        ctk.set_appearance_mode(mode)

    def _show_page(self, key: str):
        self._active_nav = key
        for k, btn in self._nav_buttons.items():
            btn.configure(fg_color=COL_NAV_ACTIVE if k == key else "transparent")
        for k, page in self.pages.items():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)

    # ---------- Callbacks ----------

    def _pick_source(self):
        path = filedialog.askdirectory(
            title="Select Source Directory")
        if path:
            self.source_dir.set(path)
            if not self.output_dir.get():
                self.output_dir.set(path)
            self._update_file_count(path)

    def _pick_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir.set(path)

    def _update_file_count(self, source_path: str):
        try:
            folders = DocumentProcessor.find_newdocs_folders(source_path)
            total = 0
            for f in folders:
                total += len(DocumentProcessor.find_pdfs(f))
            folder_count = len(folders)
            if total > 0:
                self._file_count_label.configure(
                    text=f"{folder_count} folder(s) found  •  {total} PDF(s) ready to process",
                    text_color=COL_ACCENT)
            else:
                self._file_count_label.configure(
                    text="No PDFs found in source folders",
                    text_color=COL_DESTRUCTIVE)
        except Exception:
            self._file_count_label.configure(text="", text_color=COL_TEXT_TERTIARY)

    def _toggle_api_visibility(self):
        self._api_show = not self._api_show
        self._api_entry.configure(show="" if self._api_show else "•")
        self._toggle_api_btn.configure(text="Hide" if self._api_show else "Show")

    def _save_api_key(self):
        key = self.api_key.get().strip()
        if key:
            self._save_api_btn.configure(text="Saved", state="disabled")
            self._api_status.configure(
                text="API key saved to current session.",
                text_color=COL_SUCCESS)
            self.after(2000, lambda: (
                self._save_api_btn.configure(text="Save", state="normal"),
                self._api_status.configure(
                    text="Stored in memory for the current session.",
                    text_color=COL_TEXT_TERTIARY),
            ))

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _start(self):
        src = self.source_dir.get().strip()
        out = self.output_dir.get().strip() or src
        key = self.api_key.get().strip()

        if not key:
            messagebox.showerror("Missing API Key",
                                 "Please enter your Gemini API key in Settings.")
            return
        if not src or not os.path.isdir(src):
            messagebox.showerror("Invalid Source",
                                 "Please select a valid source directory.")
            return
        os.makedirs(out, exist_ok=True)

        self._stat_ok = 0
        self._stat_manual = 0
        self._stat_total = 0
        self._processing_start = time.time()

        folders = DocumentProcessor.find_newdocs_folders(src)
        for f in folders:
            self._stat_total += len(DocumentProcessor.find_pdfs(f))

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Status: Processing", text_color=COL_ACCENT)
        self.progress_bar.set(0)
        self._update_stats()
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

    def _update_stats(self):
        self._stat_labels["ok"].configure(
            text=f"Sorted: {self._stat_ok}")
        self._stat_labels["manual"].configure(
            text=f"Manual Review: {self._stat_manual}")
        if self._processing_start:
            elapsed = int(time.time() - self._processing_start)
            m, s = divmod(elapsed, 60)
            self._stat_labels["elapsed"].configure(text=f"Time Elapsed: {m}:{s:02d}")
        else:
            self._stat_labels["elapsed"].configure(text="Time Elapsed: —")

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
                    self.status_label.configure(
                        text="Status: Ready", text_color=COL_TEXT_SECONDARY)
                    self.progress_bar.set(1.0)
                    self._update_stats()
                    continue

                if "[OK]" in msg:
                    self._stat_ok += 1
                elif "[MANUAL]" in msg:
                    self._stat_manual += 1

                done = self._stat_ok + self._stat_manual
                if self._stat_total > 0:
                    self.progress_bar.set(done / self._stat_total)
                self._update_stats()

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
