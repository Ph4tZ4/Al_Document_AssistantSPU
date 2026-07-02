# AI Document Assistant

A Windows desktop app that reads scanned PDF loan documents with the Gemini API, extracts
**Name / 13-digit ID Card / Loan Type**, renames each file to `Name_IDCard_LoanType.pdf`,
and sorts them into folders by loan type. Unreadable or incomplete files go to a `Manual`
folder for human review.

## How It Works

1. Select a **Source Directory** that contains folders named `NewDocs`, `NewDocs 2`, `NewDocs 3`, …
2. Enter your **Gemini API key** (get one at https://aistudio.google.com/apikey).
3. Click **Start Processing**. Each PDF is sent to Gemini 1.5 Flash, validated, renamed, and moved:
   - `Personal_Loan/`, `Home_Loan/`, `Car_Loan/` — sorted successes
   - `Manual/` — files the AI could not read, missing/invalid data, or corrupted PDFs

Customize the loan types in `main.py` (`LOAN_TYPES` and `LOAN_TYPE_FOLDERS`).

## Run in Development (Mac or Windows)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Optionally set the API key via environment variable so it pre-fills the field:

```bash
export GEMINI_API_KEY="your-key"   # Windows: set GEMINI_API_KEY=your-key
```

## Building the Windows .exe (from a Mac)

**Important:** PyInstaller cannot cross-compile. A Windows `.exe` must be built *on Windows*.
You have three options, from easiest to most manual:

### Option A — GitHub Actions (recommended, fully automated)

This repo already includes `.github/workflows/build-windows.yml`.

1. Push this repo to GitHub:
   ```bash
   git add .
   git commit -m "AI Document Assistant"
   git push origin main
   ```
2. On GitHub, go to **Actions → Build Windows EXE → Run workflow**.
3. When the job finishes, download the **AI_Document_Assistant_Windows** artifact —
   it contains `AI_Document_Assistant.exe`, ready to run on any Windows 10/11 machine.

### Option B — Windows VM on your Mac

1. Install a Windows 11 VM using [UTM](https://mac.getutm.app/) (Apple Silicon) or
   Parallels / VMware Fusion.
2. Inside the VM, install Python 3.12 from https://python.org (check "Add to PATH").
3. Copy the project into the VM, then run:
   ```bat
   pip install -r requirements.txt
   pyinstaller --noconfirm --onefile --windowed --name "AI_Document_Assistant" --collect-all customtkinter main.py
   ```
4. The executable will be at `dist\AI_Document_Assistant.exe`.

### Option C — Any real Windows PC

Same steps as Option B, on a colleague's Windows machine.

### PyInstaller flags explained

| Flag | Purpose |
|------|---------|
| `--onefile` | Single self-contained `.exe` |
| `--windowed` | No console window (GUI-only app) |
| `--collect-all customtkinter` | Bundles customtkinter's theme/asset files (required) |

## Notes

- The Gemini API requires internet access on the staff PC.
- API key is never hardcoded; staff enter it in the GUI (or via `GEMINI_API_KEY` env var).
- Duplicate output filenames are auto-suffixed with `(1)`, `(2)`, … — nothing is overwritten.
