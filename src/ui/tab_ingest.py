import threading
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from core.ingest import scan_folder


class TabIngest(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.cancel_requested = False

        ctk.CTkLabel(self, text="Dossier source des pi\u00e8ces historiques", font=("", 16, "bold")).pack(pady=(15, 5))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        self.path_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(row, textvariable=self.path_var, width=700)
        self.entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkButton(row, text="Parcourir\u2026", command=self.browse).pack(side="left")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)
        self.scan_btn = ctk.CTkButton(btn_row, text="Lancer le scan", command=self.start_scan)
        self.scan_btn.pack(side="left")
        self.cancel_btn = ctk.CTkButton(btn_row, text="Annuler", command=self.cancel_scan, state="disabled")
        self.cancel_btn.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(self, width=800)
        self.progress.set(0)
        self.progress.pack(padx=20, pady=10)

        self.status_label = ctk.CTkLabel(self, text="En attente\u2026")
        self.status_label.pack(pady=5)

        self.textbox = ctk.CTkTextbox(self, width=1100, height=450)
        self.textbox.pack(padx=20, pady=10, fill="both", expand=True)

    def browse(self):
        folder = filedialog.askdirectory(title="Choisir le dossier source")
        if folder:
            self.path_var.set(folder)

    def start_scan(self):
        folder = self.path_var.get().strip()
        if not folder or not Path(folder).exists():
            self.status_label.configure(text="Chemin invalide.")
            return
        self.cancel_requested = False
        self.scan_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.progress.set(0)

        thread = threading.Thread(target=self._run_scan, args=(Path(folder),), daemon=True)
        thread.start()

    def cancel_scan(self):
        self.cancel_requested = True

    def _progress_callback(self, current, total, filename):
        pct = current / total if total else 0
        self.after(0, lambda: self.progress.set(pct))
        self.after(0, lambda: self.status_label.configure(text=f"[{current}/{total}] {filename}"))

    def _run_scan(self, folder: Path):
        docs = scan_folder(
            folder,
            progress_callback=self._progress_callback,
            cancel_flag=lambda: self.cancel_requested,
        )
        self.state.documents = docs
        self.after(0, lambda: self._on_scan_done(docs))

    def _on_scan_done(self, docs):
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text=f"Scan termin\u00e9 : {len(docs)} document(s) trait\u00e9(s).")
        for d in docs:
            marker = "[OCR]" if d.ocr_utilise else ""
            err = f" \u2014 ERREUR: {d.erreur}" if d.erreur else ""
            self.textbox.insert("end", f"{d.doc_id} | {d.type_fichier} | {d.nb_caracteres} car. {marker}{err}\n")
        self.app.refresh_all()
