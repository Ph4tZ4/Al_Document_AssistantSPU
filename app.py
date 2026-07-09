"""
AI Document Assistant — Desktop app (pywebview)
-----------------------------------------------
Loads the HTML/CSS/JS interface in web/ inside a native window and exposes a
Python API bridge to the processing engine in core.py.

Run in development:
    python app.py

Build a Windows .exe (must be run ON Windows):
    pyinstaller --noconfirm --onefile --windowed --name "AI_Document_Assistant" \
        --add-data "web;web" --add-data "fonts;fonts" app.py
"""

from __future__ import annotations

import os
import sys
import threading
import time
import json
from datetime import datetime

import webview

import core


def resource_dir() -> str:
    """Directory that contains bundled resources (web/, fonts/).

    Handles both normal execution and a PyInstaller one-file bundle."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))



class Api:
    """Methods here are callable from JavaScript via window.pywebview.api.*"""

    def __init__(self):
        self.window: webview.Window | None = None
        self.processor: core.DocumentProcessor | None = None
        self.worker: threading.Thread | None = None
        self.ticker: threading.Thread | None = None

    def bind(self, window):
        self.window = window

    # ---------- JS bridge helpers ----------

    def _js(self, fn: str, payload=None):
        if not self.window:
            return
        try:
            arg = json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
            self.window.evaluate_js(f"window.{fn} && window.{fn}({arg});")
        except Exception:
            pass

    # ---------- Config ----------

    def get_config(self) -> dict:
        return core.load_config()

    def save_config(self, cfg: dict) -> dict:
        return core.save_config(cfg or {})

    def get_default_prompt(self) -> str:
        return core.default_prompt()

    # ---------- Folder picker ----------

    def pick_folder(self) -> str:
        if not self.window:
            return ""
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return ""
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def count_documents(self, source_dir: str) -> dict:
        try:
            folders, documents = core.DocumentProcessor.count_documents(source_dir)
            return {"folders": folders, "documents": documents}
        except Exception:
            return {"folders": 0, "documents": 0}

    # ---------- Connection test ----------

    def test_connection(self, api_key: str) -> dict:
        api_key = (api_key or "").strip()
        if not api_key:
            return {"ok": False, "message": "กรุณากรอกคีย์ API ก่อน"}
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(core.GEMINI_MODEL_NAME)
            model.generate_content("ping")
            core.save_config({"api_key": api_key})
            return {"ok": True, "message": "เชื่อมต่อสำเร็จ พร้อมใช้งาน ✓"}
        except Exception as e:
            msg = str(e)
            if "API_KEY" in msg or "invalid" in msg.lower() or "401" in msg or "403" in msg:
                return {"ok": False, "message": "คีย์ API ไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง"}
            return {"ok": False, "message": f"เชื่อมต่อไม่สำเร็จ: {msg[:120]}"}

    # ---------- Processing ----------

    def start_processing(self) -> dict:
        if self.worker and self.worker.is_alive():
            return {"error": "กำลังประมวลผลอยู่แล้ว"}

        cfg = core.load_config()
        api_key = (cfg.get("api_key") or "").strip()
        source = cfg.get("source_dir") or ""
        output = cfg.get("output_dir") or ""

        if not api_key:
            return {"error": "ยังไม่ได้ตั้งค่าคีย์ API"}
        if not source or not os.path.isdir(source):
            return {"error": "โฟลเดอร์ต้นทางไม่ถูกต้อง"}
        if not output:
            return {"error": "ยังไม่ได้เลือกโฟลเดอร์ปลายทาง"}
        os.makedirs(output, exist_ok=True)

        try:
            self.processor = core.DocumentProcessor(
                api_key,
                prompt=cfg.get("prompt"),
                log_fn=lambda m: self._js("onLog", m),
                result_fn=lambda r: self._js("onResult", r),
            )
        except Exception as e:
            return {"error": f"เริ่มต้นโมเดลไม่สำเร็จ: {e}"}

        self._start_ticker()
        self.worker = threading.Thread(
            target=self._run, args=(source, output), daemon=True)
        self.worker.start()
        return {"ok": True}

    def _start_ticker(self):
        start = time.time()
        stop = self.processor.stop_flag if self.processor else threading.Event()

        def tick():
            while self.worker is None or self.worker.is_alive():
                elapsed = int(time.time() - start)
                self._js("onTick", f"{elapsed // 60}:{elapsed % 60:02d}")
                time.sleep(1)
        self.ticker = threading.Thread(target=tick, daemon=True)
        self.ticker.start()

    def _run(self, source: str, output: str):
        try:
            summary = self.processor.run(source, output)
        except Exception as e:
            self._js("onLog", {
                "time": core.thai_datetime(datetime.now(), with_seconds=True),
                "step": "เกิดข้อผิดพลาด",
                "level": "error",
                "message": f"ระบบหยุดทำงานกะทันหันระหว่างประมวลผล: {e}",
            })
            summary = {"total": 0, "success": 0, "manual": 0, "elapsed": 0, "elapsed_label": "0:00"}

        if summary.get("total", 0) > 0:
            core.append_history({
                "date": core.thai_datetime(datetime.now()),
                "timestamp": datetime.now().isoformat(),
                "total": summary["total"],
                "success": summary["success"],
                "manual": summary["manual"],
                "elapsed_label": summary["elapsed_label"],
            })
        self._js("onDone", summary)

    def stop_processing(self) -> dict:
        if self.processor:
            self.processor.stop_flag.set()
        return {"ok": True}

    # ---------- History & dashboard ----------

    def get_history(self) -> list:
        return core.load_history()

    def get_dashboard(self) -> dict:
        history = core.load_history()
        total = sum(h.get("total", 0) for h in history)
        success = sum(h.get("success", 0) for h in history)
        manual = sum(h.get("manual", 0) for h in history)
        rate = round(success / total * 100) if total else 0

        recent = [{
            "date": h.get("date", ""),
            "total": h.get("total", 0),
            "success": h.get("success", 0),
            "manual": h.get("manual", 0),
        } for h in history[:5]]

        # Chart: aggregate the latest runs (up to 7) newest-last.
        chart = []
        for h in reversed(history[:7]):
            label = (h.get("date", "") or "").split(" ")
            chart.append({
                "label": f"{label[0]} {label[1]}" if len(label) >= 2 else "",
                "total": h.get("total", 0),
                "success": h.get("success", 0),
            })

        return {"total": total, "success": success, "manual": manual, "rate": rate,
                "chart": chart, "recent": recent}


def main():
    api = Api()
    index = os.path.join(resource_dir(), "web", "index.html")
    window = webview.create_window(
        "ผู้ช่วยเอกสาร AI — กยศ.",
        index,
        js_api=api,
        width=1200,
        height=800,
        min_size=(960, 640),
        background_color="#f6f7fb",
    )
    api.bind(window)
    webview.start()


if __name__ == "__main__":
    main()
