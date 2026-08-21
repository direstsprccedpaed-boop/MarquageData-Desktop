from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from core.payload_builder import build_prompt, export_batch, export_individual


class TabLLM(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app

        ctk.CTkLabel(self, text="G\u00e9n\u00e9ration des prompts d'extraction LLM (mode sparse)", font=("", 16, "bold")).pack(pady=(15, 5))

        self.info_label = ctk.CTkLabel(self, text="Aucun document ing\u00e9r\u00e9.")
        self.info_label.pack(pady=5)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_row, text="Exporter le batch JSON", command=self.export_batch).pack(side="left")
        ctk.CTkButton(btn_row, text="Exporter en fichiers individuels", command=self.export_individual).pack(side="left", padx=10)

        self.doc_selector = ctk.CTkOptionMenu(self, values=["\u2014"], command=self.show_prompt)
        self.doc_selector.pack(padx=20, pady=5, anchor="w")

        self.preview = ctk.CTkTextbox(self, width=1100, height=450)
        self.preview.pack(padx=20, pady=10, fill="both", expand=True)

        self.copy_btn = ctk.CTkButton(self, text="Copier le prompt affich\u00e9 dans le presse-papier", command=self.copy_current)
        self.copy_btn.pack(pady=5)

    def refresh(self):
        docs = self.state.documents
        self.info_label.configure(text=f"{len(docs)} document(s) pr\u00eat(s) pour la g\u00e9n\u00e9ration de prompts.")
        ids = [d.doc_id for d in docs if not d.erreur] or ["\u2014"]
        self.doc_selector.configure(values=ids)
        if ids and ids[0] != "\u2014":
            self.doc_selector.set(ids[0])
            self.show_prompt(ids[0])

    def show_prompt(self, doc_id):
        doc = next((d for d in self.state.documents if d.doc_id == doc_id), None)
        self.preview.delete("1.0", "end")
        if doc:
            self.preview.insert("end", build_prompt(doc))

    def copy_current(self):
        text = self.preview.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)

    def export_batch(self):
        if not self.state.documents:
            return
        path = export_batch(self.state.documents)
        self.info_label.configure(text=f"Batch export\u00e9 : {path}")

    def export_individual(self):
        if not self.state.documents:
            return
        paths = export_individual(self.state.documents)
        self.info_label.configure(text=f"{len(paths)} fichier(s) individuel(s) export\u00e9(s).")
