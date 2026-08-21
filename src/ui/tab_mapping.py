from tkinter import filedialog
import customtkinter as ctk
from core.importer import import_json_files, import_json_text_global
from core.normalizer import load_mapping, save_mapping, collect_source_codes, apply_mapping, upsert_alias


class TabMapping(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.state.mapping = load_mapping()

        ctk.CTkLabel(self, text="Import JSON global & Mapping d'alias PN → BPUF", font=("", 16, "bold")).pack(pady=(15, 5))

        ctk.CTkLabel(
            self,
            text="Collez ici le tableau JSON global renvoyé par votre LLM (une réponse couvrant tous les documents "
                 "d'un lot). Si votre historique a nécessité plusieurs lots (onglet 2), répétez cette opération "
                 "pour chaque réponse — les commandes s'accumulent, rien n'est perdu entre deux imports.",
            text_color="gray", wraplength=1050, justify="left",
        ).pack(padx=20, pady=(0, 10), anchor="w")

        self.paste_box = ctk.CTkTextbox(self, width=1100, height=220)
        self.paste_box.pack(padx=20, pady=5)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(btn_row, text="Importer le JSON collé", command=self.import_pasted).pack(side="left")
        ctk.CTkButton(btn_row, text="Ou sélectionner fichier(s) JSON…", command=self.import_files).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Réinitialiser les commandes importées", command=self.reset_commandes).pack(side="left", padx=10)

        self.audit_label = ctk.CTkLabel(self, text="Aucun import.", justify="left", wraplength=1050)
        self.audit_label.pack(pady=5, anchor="w", padx=20)

        ctk.CTkLabel(self, text="Codes orphelins — à qualifier manuellement", font=("", 13, "bold")).pack(pady=(15, 5))

        self.mapping_frame = ctk.CTkScrollableFrame(self, width=1100, height=220)
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
        from pathlib import Path
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
