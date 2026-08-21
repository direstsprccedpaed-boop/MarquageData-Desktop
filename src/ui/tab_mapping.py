from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from core.importer import import_json_files, import_json_text_global
from core.normalizer import (
    load_mapping, save_mapping, collect_source_codes, apply_mapping,
    upsert_alias, auto_map_from_bpu,
)
from core.excel_builder import parse_bpu_structure


class TabMapping(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.state.mapping = load_mapping()
        self.codes_bpu: dict = {}
        self.bpu_path: Path | None = None
        self.suggestions: dict[str, str] = {}

        ctk.CTkLabel(self, text="Import JSON global & Mapping d'alias PN → BPUF", font=("", 16, "bold")).pack(pady=(15, 5))

        ctk.CTkLabel(
            self,
            text="Collez ici le tableau JSON global renvoyé par votre LLM. Si plusieurs lots ont été nécessaires "
                 "(onglet 2), répétez l'import pour chaque réponse — les commandes s'accumulent.",
            text_color="gray", wraplength=1050, justify="left",
        ).pack(padx=20, pady=(0, 10), anchor="w")

        self.paste_box = ctk.CTkTextbox(self, width=1100, height=160)
        self.paste_box.pack(padx=20, pady=5)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(btn_row, text="Importer le JSON collé", command=self.import_pasted).pack(side="left")
        ctk.CTkButton(btn_row, text="Ou sélectionner fichier(s) JSON…", command=self.import_files).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Réinitialiser les commandes importées", command=self.reset_commandes).pack(side="left", padx=10)

        self.audit_label = ctk.CTkLabel(self, text="Aucun import.", justify="left", wraplength=1050)
        self.audit_label.pack(pady=5, anchor="w", padx=20)

        ctk.CTkLabel(
            self, text="Auto-mapping via le BPUF cible (les commandes reprennent souvent déjà la nomenclature du DQE)",
            font=("", 13, "bold"),
        ).pack(pady=(15, 5))

        bpu_row = ctk.CTkFrame(self, fg_color="transparent")
        bpu_row.pack(fill="x", padx=20, pady=5)
        self.bpu_path_var = ctk.StringVar()
        ctk.CTkEntry(bpu_row, textvariable=self.bpu_path_var, width=650).pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkButton(bpu_row, text="Choisir le BPUF cible (.xlsx)…", command=self.browse_bpu).pack(side="left")
        ctk.CTkButton(bpu_row, text="Lancer l'auto-mapping", command=self.run_auto_mapping).pack(side="left", padx=10)

        self.auto_summary = ctk.CTkLabel(self, text="", text_color="gray", wraplength=1050, justify="left")
        self.auto_summary.pack(pady=5, anchor="w", padx=20)

        ctk.CTkLabel(
            self,
            text="Codes restants à qualifier (une suggestion pré-remplie provient de la similarité de désignation — "
                 "vérifiez-la ou corrigez-la avant de valider)",
            font=("", 13, "bold"),
        ).pack(pady=(10, 5))

        self.mapping_frame = ctk.CTkScrollableFrame(self, width=1100, height=200)
        self.mapping_frame.pack(padx=20, pady=10, fill="both", expand=True)
        self.mapping_entries: dict[str, ctk.CTkEntry] = {}

        ctk.CTkButton(self, text="Appliquer le mapping", command=self.apply_mapping_click).pack(pady=10)

    def import_pasted(self):
        text = self.paste_box.get("1.0", "end").strip()
        if not text:
            return
        commandes, rapport = import_json_text_global(text)
        self.state.commandes_extraites.extend(commandes)
        self._update_audit(commandes, rapport)
        self.paste_box.delete("1.0", "end")
        self._refresh_orphans()

    def import_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("JSON", "*.json")])
        if not paths:
            return
        commandes, rapport = import_json_files([Path(p) for p in paths])
        self.state.commandes_extraites.extend(commandes)
        self._update_audit(commandes, rapport)
        self._refresh_orphans()

    def _update_audit(self, commandes, rapport):
        total_now = len(self.state.commandes_extraites)
        self.audit_label.configure(
            text=f"+{len(commandes)} commande(s) valide(s) ajoutée(s) (total cumulé: {total_now}) | "
                 f"{rapport.total_lignes} ligne(s) sur cet import | "
                 f"{len(rapport.anomalies)} anomalie(s): {'; '.join(rapport.anomalies[:5])}"
        )

    def reset_commandes(self):
        self.state.commandes_extraites = []
        self.audit_label.configure(text="Commandes importées réinitialisées.")
        self._refresh_orphans()

    def browse_bpu(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.bpu_path_var.set(path)
            self.bpu_path = Path(path)
            self.state.bpu_path = self.bpu_path  # partage avec l'onglet 6 (Export DQE)

    def run_auto_mapping(self):
        if not self.bpu_path_var.get():
            self.auto_summary.configure(text="Choisissez d'abord le fichier BPUF cible (.xlsx).")
            return
        self.bpu_path = Path(self.bpu_path_var.get())
        self.state.bpu_path = self.bpu_path

        codes_bpu, sections, meta = parse_bpu_structure(self.bpu_path)
        self.codes_bpu = codes_bpu

        mapping_avant = len(self.state.mapping)
        self.state.mapping, self.suggestions, sans_suggestion = auto_map_from_bpu(
            self.state.commandes_extraites, codes_bpu, self.state.mapping,
        )
        save_mapping(self.state.mapping)
        nb_auto = len(self.state.mapping) - mapping_avant

        self.auto_summary.configure(
            text=f"BPUF cible : {meta['nb_codes']} codes / {meta['nb_sections']} sections détectés. "
                 f"{nb_auto} code(s) auto-mappé(s) par identité (correspondance exacte avec le BPUF). "
                 f"{len(self.suggestions)} suggestion(s) par similarité de désignation à valider ci-dessous. "
                 f"{len(sans_suggestion)} code(s) sans aucune suggestion fiable — saisie manuelle nécessaire."
        )
        self._refresh_orphans()

    def _refresh_orphans(self):
        for widget in self.mapping_frame.winfo_children():
            widget.destroy()
        self.mapping_entries.clear()

        codes = collect_source_codes(self.state.commandes_extraites)
        orphans = sorted(c for c in codes if c not in self.state.mapping)
        for code in orphans:
            row = ctk.CTkFrame(self.mapping_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{code} → ", width=100).pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text="code cible BPUF (ex: J7)")
            suggestion = self.suggestions.get(code)
            if suggestion:
                entry.insert(0, suggestion)
                ctk.CTkLabel(row, text="(suggéré, à vérifier)", text_color="orange").pack(side="left", padx=5)
            entry.pack(side="left", fill="x", expand=True)
            self.mapping_entries[code] = entry

    def apply_mapping_click(self):
        for code_src, entry in self.mapping_entries.items():
            target = entry.get().strip()
            if target:
                self.state.mapping = upsert_alias(self.state.mapping, code_src, target)
        save_mapping(self.state.mapping)

        lignes_mappees, a_qualifier = apply_mapping(self.state.commandes_extraites, self.state.mapping)
        self.state.lignes_mappees = lignes_mappees
        self.state.a_qualifier = a_qualifier
        self.audit_label.configure(
            text=f"Mapping appliqué : {len(lignes_mappees)} lignes | {len(a_qualifier)} code(s) à qualifier: {', '.join(a_qualifier[:10])}"
        )
        self._refresh_orphans()
        self.app.refresh_all()

    def refresh(self):
        self._refresh_orphans()
