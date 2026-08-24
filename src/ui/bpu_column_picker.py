from pathlib import Path
import customtkinter as ctk
from openpyxl import load_workbook
from core.excel_builder import list_sheet_names, preview_rows, detect_columns


class BPUColumnPicker(ctk.CTkFrame):
    """Composant reutilisable (onglet mapping + onglet export) permettant de
    visualiser les premieres lignes du BPUF charge et de choisir manuellement
    la colonne Excel correspondant a chaque champ requis, ainsi qu'un motif de
    reconnaissance de code personnalise. Par defaut, tout reste sur "auto" et
    le comportement est identique a la detection automatique existante -
    ce composant est un filet de securite pour les BPUF non standards."""

    FIELDS = [("numero", "N\u00b0 de prix"), ("designation", "D\u00e9signation"), ("unite", "Unit\u00e9"), ("pu", "Prix unitaire")]

    def __init__(self, parent, state, app):
        super().__init__(parent, fg_color="transparent")
        self.state = state
        self.app = app
        self.bpu_path: Path | None = None

        ctk.CTkLabel(
            self, text="\u2699\ufe0f Configuration des colonnes (facultatif \u2014 la d\u00e9tection automatique est utilis\u00e9e par d\u00e9faut)",
            font=("", 12, "bold"), text_color="#5aa9e6",
        ).pack(anchor="w", pady=(8, 2))

        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="Feuille :", width=60, anchor="w").pack(side="left")
        self.sheet_menu = ctk.CTkOptionMenu(row1, values=["\u2014"], command=self._on_sheet_change, width=180)
        self.sheet_menu.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="Ligne d'en-t\u00eate :", width=100, anchor="w").pack(side="left", padx=(15, 0))
        self.header_row_var = ctk.StringVar(value="1")
        ctk.CTkEntry(row1, textvariable=self.header_row_var, width=45).pack(side="left", padx=5)
        ctk.CTkButton(row1, text="Charger l'aper\u00e7u", command=self.load_preview).pack(side="left", padx=10)
        ctk.CTkButton(row1, text="R\u00e9initialiser (auto)", command=self.reset_auto, fg_color="gray30", hover_color="gray20").pack(side="left", padx=5)

        self.preview_box = ctk.CTkTextbox(self, width=1040, height=120, font=("Courier New", 11))
        self.preview_box.pack(pady=5, fill="x")
        self.preview_box.insert("end", "Chargez un fichier BPUF puis cliquez sur \"Charger l'aper\u00e7u\" pour voir les colonnes disponibles ici.")
        self.preview_box.configure(state="disabled")

        cols_row = ctk.CTkFrame(self, fg_color="transparent")
        cols_row.pack(fill="x", pady=8)
        self.col_menus: dict[str, ctk.CTkOptionMenu] = {}
        for key, label in self.FIELDS:
            sub = ctk.CTkFrame(cols_row, fg_color="transparent")
            sub.pack(side="left", padx=12)
            ctk.CTkLabel(sub, text=label, font=("", 11)).pack()
            menu = ctk.CTkOptionMenu(sub, values=["auto"], width=130)
            menu.pack()
            self.col_menus[key] = menu

        pattern_row = ctk.CTkFrame(self, fg_color="transparent")
        pattern_row.pack(fill="x", pady=(10, 5))
        ctk.CTkLabel(pattern_row, text="Motif de code personnalis\u00e9 (regex avanc\u00e9, vide = auto) :").pack(side="left")
        self.pattern_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            pattern_row, textvariable=self.pattern_var, width=320,
            placeholder_text=r"ex: ^([A-Z]{1,2})(\d+)(?:-(\d+))?$",
        ).pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(self, text="Mode : d\u00e9tection automatique.", text_color="gray")
        self.status_label.pack(anchor="w", pady=5)

    def set_bpu_path(self, path: str | Path):
        self.bpu_path = Path(path)
        try:
            names = list_sheet_names(self.bpu_path)
        except Exception as exc:
            self.status_label.configure(text=f"\u26a0\ufe0f Erreur ouverture fichier : {exc}", text_color="orange")
            return
        self.sheet_menu.configure(values=names)
        self.sheet_menu.set(names[0])
        self.state.bpu_sheet_name = names[0]

    def _on_sheet_change(self, name: str):
        self.state.bpu_sheet_name = name

    def load_preview(self):
        if not self.bpu_path:
            self.status_label.configure(text="\u26a0\ufe0f Chargez d'abord un fichier BPUF.", text_color="orange")
            return
        try:
            header_row = int(self.header_row_var.get())
        except ValueError:
            header_row = 1
        self.state.bpu_header_row = header_row

        try:
            data = preview_rows(self.bpu_path, self.state.bpu_sheet_name, header_row=header_row, max_rows=6, max_cols=10)
        except Exception as exc:
            self.status_label.configure(text=f"\u26a0\ufe0f Erreur de lecture : {exc}", text_color="orange")
            return

        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        col_letters = [chr(65 + i) for i in range(data["max_cols"])]
        self.preview_box.insert("end", "      " + " | ".join(f"{c:>18}" for c in col_letters) + "\n")
        for i, row_vals in enumerate(data["rows"]):
            label = "Ent." if i == 0 else f"L{i}"
            self.preview_box.insert("end", f"{label:5s} " + " | ".join(f"{v:>18}" for v in row_vals) + "\n")
        self.preview_box.configure(state="disabled")

        try:
            wb = load_workbook(str(self.bpu_path), data_only=False)
            ws = wb[self.state.bpu_sheet_name] if self.state.bpu_sheet_name else wb.active
            auto_cols = detect_columns(ws, header_row=header_row, max_col=data["max_cols"])
            wb.close()
        except Exception:
            auto_cols = {}

        options = list(col_letters)
        for key, menu in self.col_menus.items():
            menu.configure(values=["auto"] + options)
            auto_idx = auto_cols.get(key)
            if auto_idx:
                menu.set(chr(64 + auto_idx))
            else:
                menu.set("auto")

        self.status_label.configure(
            text="Aper\u00e7u charg\u00e9 \u2014 les colonnes ci-dessus sont pr\u00e9-remplies par la d\u00e9tection automatique ; "
                 "ajustez-les si un champ semble incorrect avant d'analyser/g\u00e9n\u00e9rer.",
            text_color="white",
        )

    def reset_auto(self):
        for menu in self.col_menus.values():
            menu.configure(values=["auto"])
            menu.set("auto")
        self.pattern_var.set("")
        self.header_row_var.set("1")
        self.state.bpu_column_overrides = None
        self.state.bpu_code_pattern = None
        self.state.bpu_header_row = 1
        self.status_label.configure(text="Mode : d\u00e9tection automatique.", text_color="gray")

    def get_overrides(self) -> dict:
        """A appeler juste avant une analyse/generation : calcule et memorise
        dans le state partage les overrides actuellement selectionnes."""
        overrides = {}
        for key, menu in self.col_menus.items():
            val = menu.get()
            if val and val != "auto":
                overrides[key] = ord(val.upper()) - 64
        self.state.bpu_column_overrides = overrides if overrides else None

        pattern = self.pattern_var.get().strip()
        self.state.bpu_code_pattern = pattern if pattern else None

        try:
            self.state.bpu_header_row = int(self.header_row_var.get())
        except ValueError:
            self.state.bpu_header_row = 1

        return {
            "sheet_name": getattr(self.state, "bpu_sheet_name", None),
            "header_row": self.state.bpu_header_row,
            "column_overrides": self.state.bpu_column_overrides,
            "custom_leaf_pattern": self.state.bpu_code_pattern,
        }
