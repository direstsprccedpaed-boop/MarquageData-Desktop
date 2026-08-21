import customtkinter as ctk
from core.payload_builder import build_global_prompts, export_global_prompts


class TabLLM(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.batches: list[dict] = []
        self.current_batch_idx = 0

        ctk.CTkLabel(
            self, text="Génération du prompt global (tous les documents en une fois)",
            font=("", 16, "bold"),
        ).pack(pady=(15, 5))

        self.info_label = ctk.CTkLabel(self, text="Aucun document ingéré.", justify="left")
        self.info_label.pack(pady=5)

        config_row = ctk.CTkFrame(self, fg_color="transparent")
        config_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(config_row, text="Taille max par lot (caractères) :").pack(side="left")
        self.max_chars_var = ctk.StringVar(value="100000")
        ctk.CTkEntry(config_row, textvariable=self.max_chars_var, width=120).pack(side="left", padx=10)
        ctk.CTkLabel(
            config_row,
            text="(si le volume total dépasse cette taille, l'app découpe automatiquement en plusieurs lots)",
            text_color="gray",
        ).pack(side="left", padx=10)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_row, text="Générer le(s) prompt(s) global(aux)", command=self.generate_global).pack(side="left")
        ctk.CTkButton(btn_row, text="Exporter en fichiers .txt", command=self.export_files).pack(side="left", padx=10)

        nav_row = ctk.CTkFrame(self, fg_color="transparent")
        nav_row.pack(fill="x", padx=20, pady=5)
        self.batch_selector = ctk.CTkOptionMenu(nav_row, values=["—"], command=self.show_batch)
        self.batch_selector.pack(side="left")
        self.batch_info = ctk.CTkLabel(nav_row, text="")
        self.batch_info.pack(side="left", padx=15)

        self.preview = ctk.CTkTextbox(self, width=1100, height=400)
        self.preview.pack(padx=20, pady=10, fill="both", expand=True)

        self.copy_btn = ctk.CTkButton(
            self, text="Copier le prompt affiché dans le presse-papier", command=self.copy_current
        )
        self.copy_btn.pack(pady=5)

        ctk.CTkLabel(
            self,
            text="Copiez ce prompt dans votre LLM externe (ChatGPT, Claude, etc.), récupérez le tableau JSON "
                 "renvoyé, puis collez-le en une seule fois dans l'onglet 3-4 (Import & Mapping).",
            text_color="gray", wraplength=1000, justify="left",
        ).pack(padx=20, pady=(0, 10), anchor="w")

    def refresh(self):
        docs = self.state.documents
        nb_valides = len([d for d in docs if not d.erreur])
        self.info_label.configure(
            text=f"{nb_valides} document(s) valide(s) prêt(s) / {len(docs)} document(s) ingéré(s) au total."
        )

    def generate_global(self):
        docs = self.state.documents
        if not docs:
            self.info_label.configure(text="Aucun document ingéré — lancez d'abord un scan à l'onglet 1.")
            return
        try:
            max_chars = int(self.max_chars_var.get())
        except ValueError:
            max_chars = 100_000

        self.batches = build_global_prompts(docs, max_chars_per_batch=max_chars)
        if not self.batches:
            self.info_label.configure(text="Aucun document valide à traiter (tous en erreur d'extraction).")
            return

        labels = [f"Lot {i + 1}/{len(self.batches)} ({len(b['doc_ids'])} docs)" for i, b in enumerate(self.batches)]
        self.batch_selector.configure(values=labels)
        self.batch_selector.set(labels[0])
        self.current_batch_idx = 0
        self._render_batch(0)

        if len(self.batches) == 1:
            self.info_label.configure(
                text=f"1 seul lot généré — {len(self.batches[0]['doc_ids'])} document(s) regroupés dans un prompt unique."
            )
        else:
            self.info_label.configure(
                text=f"Volume trop important pour un seul prompt : {len(self.batches)} lots générés. "
                     f"Traitez-les un par un avec votre LLM, puis importez chaque réponse JSON séparément."
            )

    def show_batch(self, label: str):
        idx = int(label.split(" ")[1].split("/")[0]) - 1
        self.current_batch_idx = idx
        self._render_batch(idx)

    def _render_batch(self, idx: int):
        if not self.batches:
            return
        batch = self.batches[idx]
        self.preview.delete("1.0", "end")
        self.preview.insert("end", batch["prompt"])
        self.batch_info.configure(text=f"Documents inclus : {', '.join(batch['doc_ids'][:8])}" + (
            f" (+{len(batch['doc_ids']) - 8} autres)" if len(batch["doc_ids"]) > 8 else ""
        ))

    def copy_current(self):
        text = self.preview.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)

    def export_files(self):
        docs = self.state.documents
        if not docs:
            return
        try:
            max_chars = int(self.max_chars_var.get())
        except ValueError:
            max_chars = 100_000
        paths = export_global_prompts(docs, max_chars_per_batch=max_chars)
        self.info_label.configure(text=f"{len(paths)} fichier(s) de lot exporté(s) vers %APPDATA%/MarquageDataApp/data/prompts_globaux/")
