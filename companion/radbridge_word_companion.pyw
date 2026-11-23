#!/usr/bin/env python3
"""
RadBridge Microsoft Word Direct Companion (Python & Tkinter)
Native floating HUD and direct Word integration for Windows.
"""

import os
import sys
import json
import uuid
import tempfile
import threading
import subprocess
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request
import urllib.error

import tkinter as tk
from tkinter import messagebox, ttk


def parse_launch_uri(uri):
    clean = uri.strip()
    if clean.startswith("radbridge-word://"):
        clean = clean[len("radbridge-word://"):]
    if clean.startswith("open?"):
        clean = clean[len("open?"):]
    elif clean.startswith("open/?"):
        clean = clean[len("open/?"):]
    elif clean.startswith("?"):
        clean = clean[1:]
    
    parsed = parse_qs(clean)
    params = {}
    for k, v in parsed.items():
        params[k] = v[0] if v else ""
    return params


class WordCompanionApp:
    def __init__(self, root, params):
        self.root = root
        self.params = params
        self.server = params.get("server", "https://airscan.dynu.net").rstrip("/")
        self.order_id = int(params.get("order_id", 0))
        self.accession = params.get("accession", "")
        self.patient_name = params.get("patient_name", "Unknown")
        self.patient_id = params.get("patient_id", "")
        self.study = params.get("study", "")
        self.token = params.get("token", "")
        self.version_no = int(params.get("version_no", 0))
        self.status = params.get("status", "DRAFT")

        # Create isolated sandbox directory
        self.session_id = uuid.uuid4().hex
        self.work_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
            "RadBridge", "Sessions", f"Order_{self.order_id}_{self.accession}_{self.session_id}"
        )
        os.makedirs(self.work_dir, exist_ok=True)
        self.local_docx = os.path.join(self.work_dir, f"{self.accession}.docx")

        self.setup_ui()
        self.download_and_launch()

    def setup_ui(self):
        self.root.title(f"RadBridge Reporter — {self.patient_name}")
        self.root.geometry("520x230+800+40")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0b1322")

        # Header Title
        title_frame = tk.Frame(self.root, bg="#0b1322")
        title_frame.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(
            title_frame, text="🩺 RadBridge Direct Word Reporter",
            font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#0b1322"
        ).pack(side="left")

        self.lbl_badge = tk.Label(
            title_frame, text=f"{self.status} · v{self.version_no}",
            font=("Segoe UI", 9, "bold"), fg="#34d399", bg="#1e293b", padx=8, pady=2
        )
        self.lbl_badge.pack(side="right")

        # Patient Info Card
        card = tk.Frame(self.root, bg="#131d2f", bd=1, relief="solid")
        card.pack(fill="x", padx=14, pady=6)

        tk.Label(
            card, text=f"👤 {self.patient_name}",
            font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#131d2f"
        ).pack(anchor="w", padx=10, pady=(6, 2))

        tk.Label(
            card, text=f"🆔 {self.patient_id}   |   📋 Acc: {self.accession}   |   🔬 {self.study}",
            font=("Segoe UI", 8), fg="#94a3b8", bg="#131d2f"
        ).pack(anchor="w", padx=10, pady=(0, 2))

        tk.Label(
            card, text="🛡️ نظام الحماية مفعل: يتم التحقق من بيانات المريض عند الحفظ تلقائياً لمنع أي اختلاط.",
            font=("Segoe UI", 7), fg="#64748b", bg="#131d2f"
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Buttons Frame
        btn_frame = tk.Frame(self.root, bg="#0b1322")
        btn_frame.pack(fill="x", padx=14, pady=6)

        self.btn_draft = tk.Button(
            btn_frame, text="💾 حفظ مسودة (Draft)", font=("Segoe UI", 9, "bold"),
            bg="#1d4ed8", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
            bd=0, padx=12, pady=6, cursor="hand2", command=lambda: self.sync("DRAFT")
        )
        self.btn_draft.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_verify = tk.Button(
            btn_frame, text="🩺 مراجعة (Verify)", font=("Segoe UI", 9, "bold"),
            bg="#0f766e", fg="#ffffff", activebackground="#0d9488", activeforeground="#ffffff",
            bd=0, padx=12, pady=6, cursor="hand2", command=self.on_verify
        )
        self.btn_verify.pack(side="left", expand=True, fill="x", padx=4)

        self.btn_finalize = tk.Button(
            btn_frame, text="🔒 اعتماد نهائي (Finalize)", font=("Segoe UI", 9, "bold"),
            bg="#991b1b", fg="#ffffff", activebackground="#b91c1c", activeforeground="#ffffff",
            bd=0, padx=12, pady=6, cursor="hand2", command=self.on_finalize
        )
        self.btn_finalize.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Status Bar
        self.lbl_status = tk.Label(
            self.root, text="🟢 متصل بالخادم · جاهز للكتابة والحفظ",
            font=("Segoe UI", 8), fg="#38bdf8", bg="#0b1322"
        )
        self.lbl_status.pack(fill="x", padx=14, pady=(4, 8))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def download_and_launch(self):
        def _task():
            try:
                url = f"{self.server}/api/reports/{self.order_id}/word-direct-file?token={self.token}"
                req = urllib.request.Request(url, headers={"User-Agent": "RadBridgeWordCompanion/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp, open(self.local_docx, "wb") as f:
                    f.write(resp.read())

                # Open in local Word
                if sys.platform == "win32":
                    os.startfile(self.local_docx)
                else:
                    subprocess.Popen(["xdg-open", self.local_docx])
            except Exception as e:
                self.lbl_status.config(text=f"❌ فشل فتح الملف: {e}", fg="#f87171")
                messagebox.showerror("خطأ", f"فشل تنزيل ملف التقرير من السيرفر:\n{e}")

        threading.Thread(target=_task, daemon=True).start()

    def sync(self, action):
        self.lbl_status.config(text="⏳ جاري إرسال البيانات والتحقق من أمان الملف...", fg="#fbbf24")
        self.root.update()

        def _task():
            try:
                boundary = uuid.uuid4().hex
                body = []

                fields = {
                    "token": self.token,
                    "action": action,
                    "base_version_no": str(self.version_no),
                    "commit_id": uuid.uuid4().hex,
                }
                for k, v in fields.items():
                    body.append(f"--{boundary}\r\n".encode("utf-8"))
                    body.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
                    body.append(f"{v}\r\n".encode("utf-8"))

                filename = os.path.basename(self.local_docx)
                body.append(f"--{boundary}\r\n".encode("utf-8"))
                body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode("utf-8"))
                body.append(b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n")
                
                with open(self.local_docx, "rb") as fh:
                    body.append(fh.read())
                body.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

                payload = b"".join(body)
                sync_url = f"{self.server}/api/reports/{self.order_id}/word-direct-sync"
                req = urllib.request.Request(
                    sync_url,
                    data=payload,
                    headers={
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "User-Agent": "RadBridgeWordCompanion/1.0"
                    },
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=35) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)

                if data.get("ok"):
                    self.version_no = int(data.get("version_no", self.version_no))
                    self.status = data.get("status", self.status)
                    self.lbl_badge.config(text=f"{self.status} · v{self.version_no}")

                    if action == "FINAL":
                        self.lbl_status.config(text="✅ تم الاعتماد النهائي بنجاح وتم قفل التقرير!", fg="#34d399")
                        messagebox.showinfo("تم الاعتماد بنجاح", "✅ تم اعتماد التقرير الطبي نهائياً وإصدار PDF بنجاح وحفظه في الأرشيف وقفل الحالة.")
                        self.on_close()
                        return

                    if action == "VERIFY":
                        self.lbl_status.config(text=f"🩺 تم توثيق ومراجعة التقرير بنجاح (نسخة {self.version_no}).", fg="#2dd4bf")
                        return

                    self.lbl_status.config(text=f"💾 تم حفظ المسودة (نسخة {self.version_no}) بنجاح على السيرفر.", fg="#38bdf8")

            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8")
                try:
                    err_obj = json.loads(err_text)
                    if err_obj.get("error") == "PATIENT_MISMATCH":
                        self.lbl_status.config(text="❌ خطأ أمان: عدم تطابق بيانات المريض!", fg="#f87171")
                        messagebox.showerror(
                            "حظر الحفظ - عدم تطابق بيانات المريض",
                            f"⚠️ تنبيه أمان طبي عالي (ZERO-MIXUP VIOLATION):\n\n"
                            f"بيانات المريض في المستند لا تتطابق مع المريض المفتوح في السيستم!\n\n"
                            f"المتوقع: PID={err_obj.get('expected_patient_id')} | Acc={err_obj.get('expected_accession')}\n"
                            f"الموجود: PID={err_obj.get('found_patient_id')} | Acc={err_obj.get('found_accession')}\n\n"
                            f"تم حظر الحفظ فوراً لحماية بيانات المرضى من الاختلاط."
                        )
                        return
                    self.lbl_status.config(text=f"❌ خطأ: {err_obj.get('message', e.reason)}", fg="#f87171")
                except Exception:
                    self.lbl_status.config(text=f"❌ خطأ: {e.code} - {e.reason}", fg="#f87171")
            except Exception as e:
                self.lbl_status.config(text=f"❌ خطأ: {e}", fg="#f87171")

        threading.Thread(target=_task, daemon=True).start()

    def on_verify(self):
        if messagebox.askyesno("تأكيد المراجعة", f"تأكيد مراجعة وتوثيق التقرير (Verify)؟\n\nالمريض: {self.patient_name}\nرقم الفحص: {self.accession}"):
            self.sync("VERIFY")

    def on_finalize(self):
        if messagebox.askyesno(
            "تأكيد الاعتماد النهائي",
            f"⚠️ هل أنت متأكد من الاعتماد النهائي للتقرير الطبي؟\n\n"
            f"المريض: {self.patient_name}\nالفحص: {self.study}\n\n"
            f"تنبيه: بعد الاعتماد النهائي سيتم قفل التقرير وتوليد ملف PDF الرسمي وإرساله للمريض والأرشيف ولن يمكن تعديل التقرير مباشرة."
        ):
            self.sync("FINAL")

    def on_close(self):
        try:
            import shutil
            if os.path.exists(self.work_dir):
                shutil.rmtree(self.work_dir, ignore_errors=True)
        except Exception:
            pass
        self.root.destroy()


def main():
    uri = sys.argv[1] if len(sys.argv) > 1 else ""
    params = parse_launch_uri(uri)
    if not params.get("order_id") or not params.get("token"):
        print("Usage: radbridge_word_companion.pyw <radbridge-word://open?...>")
        sys.exit(1)

    root = tk.Tk()
    app = WordCompanionApp(root, params)
    root.mainloop()


if __name__ == "__main__":
    main()
