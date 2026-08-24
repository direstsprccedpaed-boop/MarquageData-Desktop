from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from core.excel_builder import parse_bpu_structure, generate_dqe_from_bpu, verify_formulas
from core.paths import app_data_dir
from ui.bpu_column_picker import BPUColumnPicker


class TabDQEExport(ctk.CTkScrollableFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.bpu_path: Path | None = None

        ctk.CTkLabel(self, text="Analyse du BPUF cible et génération du DQE", font=("", 16, "bold")).pack(pady=(15, 5))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        self.bpu_path_var = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self.bpu_path_var, width=700).pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkButton(row, text="Choisir le gabarit BPUF (.xlsx)…", command=self.browse_bpu).pack(side="left")

        self.column_picker = BPUColumnPicker(self, state, app)
        self.column_picker.pack(fill="x", padx=20, pady=5)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(btn_row, text="Analyser la structure", command=self.analyze).pack(side="left")

        self.omit_empty_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(btn_row, text="Omettre les sections vides", variable=self.omit_empty_var).pack(side="left", padx=20)

        self.warning_label = ctk.CTkLabel(self, text="", text_color="orange")
        self.warning_label.pack(pady=5)

        self.structure_box = ctk.CTkTextbox(self, width=1100, height=230)
        self.structure_box.pack(padx=20, pady=10, fill="both", expand=True)

        self.generate_btn = ctk.CTkButton(self, text="Générer le DQE", command=self.generate, state="disabled")
        self.generate_btn.pack(pady=10)

        self.result_label = ctk.CTkLabel(self, text="", wraplength=1050, justify="left")
        self.result_label.pack(pady=5, padx=20, anchor="w")

    def browse_bpu(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.bpu_path_var.set(path)
            self.bpu_path = Path(path)
            self.state.bpu_path = self.bpu_path
            self.column_picker.set_bpu_path(path)

    def analyze(self):
        if not self.bpu_path_var.get():
            return
        self.bpu_path = Path(self.bpu_path_var.get())
        self.state.bpu_path = self.bpu_path
        overrides = self.column_picker.get_overrides()
        codes, sections, meta = parse_bpu_structure(self.bpu_path, **overrides)

        cols = meta["cols"]
        if cols.get("_defaults_used"):
            self.warning_label.configure(
                text=f"⚠️ Colonnes non détectées par mot-clé (défaut appliqué): {cols.get('_missing')} — "
                     f"utilisez le sélecteur de colonnes ci-dessus pour les préciser manuellement."
            )
        else:
            self.warning_label.configure(text="")

        nb_constates = len(set(codes) & set(self.state.consolidation)) if self.state.consolidation else 0
        nb_hors_bpu = len([c for c in self.state.consolidation if c not in codes]) if self.state.consolidation else 0
        self.structure_box.delete("1.0", "end")
        self.structure_box.insert(
            "end",
            f"Sections détectées: {meta['nb_sections']}\n"
            f"Codes prix dans le BPUF: {meta['nb_codes']}\n"
            f"Codes constatés dans l'historique consolidé: {nb_constates} / {meta['nb_codes']}\n"
            f"(Un écart important entre ces deux nombres est normal : les commandes historiques ne "
            f"couvrent jamais l'intégralité du BPUF — mode sparse.)\n"
        )
        if nb_hors_bpu:
            self.structure_box.insert(
                "end",
                f"\n⚠️ {nb_hors_bpu} code(s) consolidé(s) sans correspondance dans ce BPUF (codes conservés tels "
                f"quels à l'étape mapping) — ils apparaîtront dans une section \"HORS BPUF\" surlignée dans le "
                f"DQE généré, à vérifier/corriger directement dans Excel.\n"
            )
        if meta["nb_codes"] == 0:
            self.structure_box.insert(
                "end",
                "\n⚠️ Aucun code détecté dans ce BPUF avec les réglages actuels. Vérifiez la feuille sélectionnée, "
                "la ligne d'en-tête, les colonnes choisies dans le panneau de configuration ci-dessus, ou essayez "
                "un motif de code personnalisé si la nomenclature de ce marché est atypique.\n"
            )
        self.structure_box.insert("end", "\n")
        for s in sections:
            nb_codes_section = len([c for c in codes.values() if c.section == s.lettre])
            self.structure_box.insert("end", f"  Section {s.lettre}: {nb_codes_section} prix (lignes {s.ligne_debut}-{s.ligne_fin})\n")

        self.generate_btn.configure(state="normal")

    def generate(self):
        if not self.bpu_path or not self.state.consolidation:
            self.result_label.configure(text="Consolidation manquante — passez d'abord par l'onglet 5.")
            return

        overrides = self.column_picker.get_overrides()
        output_path = app_data_dir() / "output" / "DQE_genere.xlsx"
        report = generate_dqe_from_bpu(
            bpu_path=self.bpu_path,
            consolidation=self.state.consolidation,
            output_path=output_path,
            qte_defaut_absent=self.state.params_estimation.qte_defaut_absent if self.state.params_estimation else 0.0,
            omit_empty_sections=self.omit_empty_var.get(),
            **overrides,
        )
        anomalies = verify_formulas(output_path)

        texte = (
            f"DQE généré: {report['output_path']} | {report['nb_codes_constates']} codes constatés / "
            f"{report['nb_codes_bpu']} du BPUF | Anomalies formules: {len(anomalies)}"
        )
        if report.get("codes_hors_bpu"):
            texte += (
                f"\n⚠️ {len(report['codes_hors_bpu'])} code(s) sans correspondance BPUF ont été placés dans la "
                f"section surlignée \"HORS BPUF\" en fin de classeur : {', '.join(report['codes_hors_bpu'][:15])}"
                f"{' ...' if len(report['codes_hors_bpu']) > 15 else ''}. Vérifiez-les/corrigez-les directement "
                f"dans le fichier Excel généré."
            )
        self.result_label.configure(text=texte)

    def refresh(self):
        if not self.bpu_path_var.get() and getattr(self.state, "bpu_path", None):
            self.bpu_path = self.state.bpu_path
            self.bpu_path_var.set(str(self.state.bpu_path))
            self.column_picker.set_bpu_path(self.state.bpu_path)
