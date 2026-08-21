from tkinter import filedialog
import customtkinter as ctk
from core.importer import import_json_files, parse_json_text
from core.normalizer import load_mapping, save_mapping, collect_source_codes, apply_mapping, upsert_alias


class TabMapping(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.state.mapping = load_mapping()

        ctk.CTkLabel(self, text="Import JSON & Mapping d'alias PN \u2192 BPUF", font=("", 16, "bold")).pack(pady=(15, 5))

        import_row = ctk.CTkFrame(self, fg_color="transparent")
        import_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(import_row, text="S\u00e9lectionner fichiers JSON\u2026", command=self.import_files).pack(side="left")

        self.audit_label = ctk.CTkLabel(self, text="Aucun import.", justify="left")
        self.audit_label.pack(pady=5, anchor="w", padx=20)

        paste_row = ctk.CTkFrame(self, fg_color="transparent")
        paste_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(paste_row, text="Ou coller une r\u00e9ponse JSON unique :").pack(anchor="w")
        self.paste_box = ctk.CTkTextbox(self, width=1100, height=150)
        self.paste_box.pack(padx=20, pady=5)
        ctk.CTkButton(self, text="Valider le JSON coll\u00e9", command=self.validate_pasted).pack(pady=5)

        ctk.CTkLabel(self, text="Codes orphelins \u2014 \u00e0 qualifier manuellement", font=("", 13, "bold")).pack(pady=(15, 5))

        self.mapping_frame = ctk.CTkScrollableFrame(self, width=1100, height=250)
        self.mapping_frame.pack(padx=20, pady=10, fill="both", expand=True)
        self.mapping_entries: dict[str, ctk.CTkEntry] = {}

        ctk.CTkButton(self, text="Appliquer le mapping", command=self.apply_mapping_click).pack(pady=10)

    def import_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("JSON", "*.json")])
        if not paths:
            return
        from pathlib import Path
        commandes, rapport = import_json_files([Path(p) for p in paths])
        self.state.commandes_extraites.extend(commandes)
        self.audit_label.configure(
            text=f"{len(commandes)} commande(s) valide(s) | {rapport.total_lignes} lignes | "
                 f"{len(rapport.anomalies)} anomalie(s): {'; '.join(rapport.anomalies[:5])}"
        )
        self._refresh_orphans()

    def validate_pasted(self):
        text = self.paste_box.get("1.0", "end").strip()
        if not text:
            return
        commande, anomalies = parse_json_text(text)
        if commande:
            self.state.commandes_extraites.append(commande)
            self.audit_label.configure(text=f"Commande {commande.doc_id} ajout\u00e9e. Anomalies: {len(anomalies)}")
        else:
            self.audit_label.configure(text=f"JSON invalide: {'; '.join(anomalies)}")
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
            ctk.CTkLabel(row, text=f"{code} \u2192 ", width=100).pack(side="left")
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
            text=f"Mapping appliqu\u00e9 : {len(lignes_mappees)} lignes | {len(a_qualifier)} code(s) \u00e0 qualifier: {', '.join(a_qualifier[:10])}"
        )
        self._refresh_orphans()
        self.app.refresh_all()

    def refresh(self):
        self._refresh_orphans()
