import customtkinter as ctk
from core.aggregator import consolidate
from core.models import ParametresEstimation


class TabAggregation(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app

        ctk.CTkLabel(self, text="Param\u00e8tres d'estimation et consolidation sparse", font=("", 16, "bold")).pack(pady=(15, 5))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=20, pady=10, fill="x")

        self.coef_alea = self._slider_row(form, "Coefficient d'al\u00e9a", 1.0, 0.5, 2.0)
        self.coef_indexation = self._slider_row(form, "Coefficient d'indexation TP", 1.0, 0.8, 2.0)
        self.coef_marge = self._slider_row(form, "Coefficient de marge", 1.0, 0.8, 2.0)
        self.qte_defaut = self._slider_row(form, "Quantit\u00e9 par d\u00e9faut (absent BPUF)", 0.0, 0.0, 5.0)

        ctk.CTkButton(self, text="Consolider", command=self.run_consolidation).pack(pady=15)

        self.summary = ctk.CTkLabel(self, text="Aucune consolidation.", justify="left")
        self.summary.pack(pady=5, anchor="w", padx=20)

        self.table = ctk.CTkTextbox(self, width=1100, height=400)
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
        params = ParametresEstimation(
            coef_alea=self.coef_alea.get(),
            coef_indexation=self.coef_indexation.get(),
            coef_marge=self.coef_marge.get(),
            qte_defaut_absent=self.qte_defaut.get(),
        )
        self.state.params_estimation = params
        self.state.consolidation = consolidate(self.state.lignes_mappees, params)

        self.summary.configure(text=f"{len(self.state.consolidation)} code(s) prix consolid\u00e9(s) (mode sparse).")
        self.table.delete("1.0", "end")
        for code, l in sorted(self.state.consolidation.items()):
            self.table.insert(
                "end",
                f"{code:10s} | {l.designation[:40]:40s} | Qt\u00e9 consolid\u00e9e={l.qte_consolidee:8.2f} | "
                f"PU r\u00e9f={l.pu_reference:8.2f} | Qt\u00e9 DQE={l.qte_dqe:8.2f} | PU DQE={l.pu_dqe:8.2f}\n"
            )
        self.app.view_export.refresh()

    def refresh(self):
        pass
