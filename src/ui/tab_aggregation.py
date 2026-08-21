import customtkinter as ctk
from core.aggregator import consolidate
from core.models import ParametresEstimation


class TabAggregation(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app

        ctk.CTkLabel(self, text="Paramètres d'estimation et consolidation sparse", font=("", 16, "bold")).pack(pady=(15, 5))

        self.precheck_label = ctk.CTkLabel(self, text="", text_color="orange", wraplength=1050, justify="left")
        self.precheck_label.pack(pady=(0, 5), padx=20, anchor="w")

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=20, pady=10, fill="x")

        self.coef_alea = self._slider_row(form, "Coefficient d'aléa", 1.0, 0.5, 2.0)
        self.coef_indexation = self._slider_row(form, "Coefficient d'indexation TP", 1.0, 0.8, 2.0)
        self.coef_marge = self._slider_row(form, "Coefficient de marge", 1.0, 0.8, 2.0)
        self.qte_defaut = self._slider_row(form, "Quantité par défaut (absent BPUF)", 0.0, 0.0, 5.0)

        ctk.CTkButton(self, text="Consolider", command=self.run_consolidation).pack(pady=15)

        self.summary = ctk.CTkLabel(self, text="Aucune consolidation.", justify="left")
        self.summary.pack(pady=5, anchor="w", padx=20)

        self.table = ctk.CTkTextbox(self, width=1100, height=380)
        self.table.pack(padx=20, pady=10, fill="both", expand=True)

    def _slider_row(self, parent, label, default, mini, maxi):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label, width=250, anchor="w").pack(side="left")
        var = ctk.DoubleVar(value=default)
        value_label = ctk.CTkLabel(row, text=f"{default:.2f}", width=50)
        slider = ctk.CTkSlider(
            row, from_=mini, to=maxi, variable=var,
            command=lambda v: value_label.configure(text=f"{float(v):.2f}"),
        )
        slider.pack(side="left", fill="x", expand=True, padx=10)
        value_label.pack(side="left")
        return var

    def run_consolidation(self):
        if not self.state.lignes_mappees:
            self.precheck_label.configure(
                text="⚠️ Aucune ligne mappée disponible. Retournez à l'onglet 3-4 et vérifiez, dans l'ordre : "
                     "① le JSON a bien été importé (compteur de commandes > 0), ② l'auto-mapping ou la saisie "
                     "manuelle a été faite, ③ le bouton \"Appliquer le mapping\" a bien été cliqué."
            )
            self.summary.configure(text="Aucune consolidation possible : 0 ligne à consolider.")
            self.table.delete("1.0", "end")
            return

        self.precheck_label.configure(text="")
        params = ParametresEstimation(
            coef_alea=self.coef_alea.get(),
            coef_indexation=self.coef_indexation.get(),
            coef_marge=self.coef_marge.get(),
            qte_defaut_absent=self.qte_defaut.get(),
        )
        self.state.params_estimation = params
        self.state.consolidation = consolidate(self.state.lignes_mappees, params)

        self.summary.configure(text=f"{len(self.state.consolidation)} code(s) prix consolidé(s) (mode sparse) à partir de {len(self.state.lignes_mappees)} ligne(s) mappée(s).")
        self.table.delete("1.0", "end")
        for code, l in sorted(self.state.consolidation.items()):
            self.table.insert(
                "end",
                f"{code:10s} | {l.designation[:40]:40s} | Qté consolidée={l.qte_consolidee:8.2f} | "
                f"PU réf={l.pu_reference:8.2f} | Qté DQE={l.qte_dqe:8.2f} | PU DQE={l.pu_dqe:8.2f}\n"
            )
        self.app.view_export.refresh()

    def refresh(self):
        if not self.state.lignes_mappees:
            self.precheck_label.configure(
                text="ℹ️ Pas encore de lignes mappées — terminez l'onglet 3-4 (import + mapping appliqué) avant de consolider."
            )
        else:
            self.precheck_label.configure(text="")
