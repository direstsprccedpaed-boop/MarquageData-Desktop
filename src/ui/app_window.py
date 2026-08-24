import customtkinter as ctk
from ui.tab_ingest import TabIngest
from ui.tab_llm import TabLLM
from ui.tab_mapping import TabMapping
from ui.tab_aggregation import TabAggregation
from ui.tab_dqe_export import TabDQEExport

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AppState:
    def __init__(self):
        self.documents = []
        self.commandes_extraites = []
        self.mapping = {}
        self.lignes_mappees = []
        self.a_qualifier = []
        self.consolidation = {}
        self.params_estimation = None
        self.bpu_path = None            # partage le BPUF cible entre l'onglet mapping et l'onglet export
        self.bpu_sheet_name = None      # feuille selectionnee dans le classeur BPUF
        self.bpu_header_row = 1         # ligne d'en-tete (par defaut 1)
        self.bpu_column_overrides = None  # dict optionnel {"numero":idx, "designation":idx, "unite":idx, "pu":idx}
        self.bpu_code_pattern = None    # regex optionnelle personnalisee pour la detection des codes prix


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MarquageData-Desktop — Pipeline DQE")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # IMPORTANT : ne jamais nommer cet attribut "self.state" sur une
        # sous-classe de ctk.CTk / tkinter.Tk. Tk expose une methode native
        # self.state() (gestion normal/zoomed/iconic) que CustomTkinter
        # appelle en interne (ex: _windows_set_titlebar_color). L'ecraser
        # avec un objet non appelable provoque un TypeError au mainloop().
        self.app_state = AppState()

        self.tabview = ctk.CTkTabview(self, width=1180, height=770)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_ingest = self.tabview.add("1. Ingestion")
        self.tab_llm = self.tabview.add("2. Prompts LLM")
        self.tab_mapping = self.tabview.add("3-4. Import & Mapping")
        self.tab_aggregation = self.tabview.add("5. Consolidation")
        self.tab_export = self.tabview.add("6. Export DQE")

        self.view_ingest = TabIngest(self.tab_ingest, self.app_state, self)
        self.view_ingest.pack(fill="both", expand=True)

        self.view_llm = TabLLM(self.tab_llm, self.app_state, self)
        self.view_llm.pack(fill="both", expand=True)

        self.view_mapping = TabMapping(self.tab_mapping, self.app_state, self)
        self.view_mapping.pack(fill="both", expand=True)

        self.view_aggregation = TabAggregation(self.tab_aggregation, self.app_state, self)
        self.view_aggregation.pack(fill="both", expand=True)

        self.view_export = TabDQEExport(self.tab_export, self.app_state, self)
        self.view_export.pack(fill="both", expand=True)

    def refresh_all(self):
        self.view_llm.refresh()
        self.view_mapping.refresh()
        self.view_aggregation.refresh()
        self.view_export.refresh()
