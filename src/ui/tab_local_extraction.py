import customtkinter as ctk
from core.local_extractor import extract_batch_local, extract_document_local, confirm_template, load_templates
from core.importer import find_duplicates


class TabLocalExtraction(ctk.CTkScrollableFrame):
    """Alternative 100% locale au flux 'Prompts LLM -> Import JSON'. Aucune
    donnee n'est envoyee a l'exterieur. Un systeme de score ecarte
    automatiquement les tableaux de page de garde (MOA, dates, duree, marche)
    qui n'ont pas de colonnes numeriques coherentes - seuls les tableaux
    ayant un minimum de vraisemblance sont soumis a validation humaine, avec
    un apercu des vraies donnees (pas juste des numeros de colonne)."""

    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.pending_templates: dict = {}
        self.ignored_fingerprints: set[str] = set()

        ctk.CTkLabel(self, text="Extraction locale (sans LLM externe)", font=("", 16, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(
            self,
            text="Cette extraction se fait entièrement sur votre poste, sans aucun envoi de données vers un "
                 "service externe. L'application repère automatiquement le tableau qui ressemble le plus à une "
                 "liste de prix (et ignore les pages de garde administratives type MOA/dates/durée). Si aucun "
                 "tableau fiable n'est trouvé pour un document, il est signalé — utilisez alors le flux LLM "
                 "classique (onglet 2) pour celui-ci uniquement.",
            text_color="gray", wraplength=1050, justify="left",
        ).pack(padx=20, pady=(0, 10), anchor="w")

        ctk.CTkButton(self, text="Lancer l'extraction locale", command=self.run_extraction, height=40).pack(pady=10)

        self.summary_label = ctk.CTkLabel(self, text="Aucune extraction lancée.", justify="left", wraplength=1050)
        self.summary_label.pack(pady=5, anchor="w", padx=20)

        ctk.CTkLabel(
            self, text="Gabarits en attente de validation",
            font=("", 13, "bold"),
        ).pack(pady=(15, 2))
        ctk.CTkLabel(
            self,
            text="Pour chaque format inconnu ci-dessous : regardez les vraies valeurs affichées dans l'aperçu, "
                 "puis indiquez sous chaque colonne à quoi elle correspond. Si l'aperçu ne ressemble à rien "
                 "d'exploitable (page de garde, tableau vide), cliquez directement sur \"Ignorer\" — ces "
                 "documents pourront être traités via le flux LLM à la place.",
            text_color="gray", wraplength=1050, justify="left",
        ).pack(padx=20, pady=(0, 5), anchor="w")

        self.templates_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.templates_frame.pack(padx=20, pady=5, fill="x")

        self.results_box = ctk.CTkTextbox(self, width=1050, height=260)
        self.results_box.pack(padx=20, pady=15, fill="both", expand=True)

    def run_extraction(self):
        if not self.state.documents:
            self.summary_label.configure(text="⚠️ Aucun document ingéré — lancez d'abord un scan à l'onglet 1.", text_color="orange")
            return

        commandes, rapports, gabarits_en_attente = extract_batch_local(self.state.documents)
        self.pending_templates = {fp: v for fp, v in gabarits_en_attente.items() if fp not in self.ignored_fingerprints}

        if commandes:
            ajoutees, doublons = find_duplicates(self.state.commandes_extraites, commandes)
            self.state.commandes_extraites.extend(ajoutees)
        else:
            ajoutees, doublons = [], []

        nb_ok = len(ajoutees)
        nb_attente = sum(len(v["doc_ids"]) for v in self.pending_templates.values())
        nb_erreur = sum(1 for r in rapports if r.get("erreur"))

        self.summary_label.configure(
            text=f"{nb_ok} commande(s) extraite(s) et ajoutée(s) automatiquement (total cumulé : "
                 f"{len(self.state.commandes_extraites)}) | {nb_attente} document(s) en attente de validation "
                 f"de gabarit (ci-dessous) | {nb_erreur} document(s) sans table fiable (à traiter via le LLM) | "
                 f"{len(doublons)} doublon(s) ignoré(s).",
            text_color="white",
        )

        self.results_box.delete("1.0", "end")
        for r in rapports:
            if r.get("erreur"):
                self.results_box.insert("end", f"{r['doc_id']} : {r['erreur']}\n")
            elif r.get("mapping_a_valider"):
                self.results_box.insert("end", f"{r['doc_id']} : en attente de validation de gabarit\n")
            else:
                extra = " — métadonnées incomplètes, à vérifier" if r.get("metadata_incomplete") else ""
                self.results_box.insert(
                    "end",
                    f"{r['doc_id']} : {r['nb_lignes']} ligne(s) extraite(s), {r['nb_lignes_ignorees']} "
                    f"ignorée(s) (quantité/PU non numérique){extra}\n",
                )

        self._render_pending_templates()
        self.app.refresh_all()

    def _render_pending_templates(self):
        for w in self.templates_frame.winfo_children():
            w.destroy()

        if not self.pending_templates:
            ctk.CTkLabel(self.templates_frame, text="Aucun gabarit en attente.", text_color="gray").pack(anchor="w")
            return

        for fp, info in self.pending_templates.items():
            box = ctk.CTkFrame(self.templates_frame, fg_color=("gray85", "gray20"))
            box.pack(fill="x", pady=8, padx=2)

            top_row = ctk.CTkFrame(box, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(10, 4))
            ctk.CTkLabel(
                top_row, text=f"Nouveau format détecté ({len(info['doc_ids'])} document(s) concerné(s))",
                font=("", 12, "bold"),
            ).pack(side="left")
            ctk.CTkButton(
                top_row, text="Ignorer ce format (traiter via le LLM)", fg_color="gray30", hover_color="gray20",
                width=200, command=lambda fp=fp: self._ignore_template(fp),
            ).pack(side="right")

            preview_box = ctk.CTkTextbox(box, width=1000, height=90, font=("Courier New", 11))
            preview_box.pack(padx=10, pady=4, fill="x")
            nb_cols = max(len(info["header"]), *(len(r) for r in info["preview_rows"])) if info["preview_rows"] else len(info["header"])
            col_indices = "      " + " | ".join(f"col.{i:<8}" for i in range(nb_cols)) + "\n"
            header_line = "Ent.  " + " | ".join(f"{(info['header'][i] if i < len(info['header']) else ''):<10}" for i in range(nb_cols)) + "\n"
            preview_box.insert("end", col_indices)
            preview_box.insert("end", header_line)
            for j, row in enumerate(info["preview_rows"], start=1):
                line = f"L{j}    " + " | ".join(f"{(row[i] if i < len(row) else ''):<10}" for i in range(nb_cols)) + "\n"
                preview_box.insert("end", line)
            preview_box.configure(state="disabled")

            menus_row = ctk.CTkFrame(box, fg_color="transparent")
            menus_row.pack(fill="x", padx=10, pady=8)
            col_options = [f"col.{i}" for i in range(nb_cols)]
            menus = {}
            for key, label in [("code", "Code prix"), ("designation", "Désignation"), ("quantite", "Quantité"), ("unite", "Unité"), ("pu", "Prix U.")]:
                sub = ctk.CTkFrame(menus_row, fg_color="transparent")
                sub.pack(side="left", padx=8)
                ctk.CTkLabel(sub, text=label, font=("", 10)).pack()
                menu = ctk.CTkOptionMenu(sub, values=["aucune"] + col_options, width=100)
                current = info["mapping"].get(key)
                menu.set(f"col.{current}" if current is not None else "aucune")
                menu.pack()
                menus[key] = menu

            ctk.CTkButton(
                box, text="Valider ce gabarit et relancer l'extraction",
                command=lambda fp=fp, info=info, menus=menus: self._validate_template(fp, info, menus),
            ).pack(anchor="w", padx=10, pady=(0, 10))

    def _ignore_template(self, fp: str):
        self.ignored_fingerprints.add(fp)
        self.pending_templates.pop(fp, None)
        self._render_pending_templates()
        self.summary_label.configure(
            text=self.summary_label.cget("text") + " (Un format a été marqué comme ignoré — utilisez le flux "
                 "LLM pour les documents concernés.)",
        )

    def _validate_template(self, fp, info, menus):
        mapping = {}
        for key, menu in menus.items():
            val = menu.get()
            mapping[key] = int(val.replace("col.", "")) if val != "aucune" else None
        confirm_template(fp, info["header"], mapping)

        docs_a_relancer = [d for d in self.state.documents if d.doc_id in info["doc_ids"]]
        templates = load_templates()
        nouvelles_commandes = []
        for d in docs_a_relancer:
            commande, _ = extract_document_local(d, templates=templates)
            if commande and commande.lignes:
                nouvelles_commandes.append(commande)

        ajoutees, doublons = find_duplicates(self.state.commandes_extraites, nouvelles_commandes)
        self.state.commandes_extraites.extend(ajoutees)

        self.pending_templates.pop(fp, None)
        self._render_pending_templates()
        self.summary_label.configure(
            text=f"Gabarit validé — {len(ajoutees)} commande(s) supplémentaire(s) extraite(s) automatiquement "
                 f"(total cumulé : {len(self.state.commandes_extraites)}). Ce format sera reconnu automatiquement "
                 f"pour tous les prochains documents similaires.",
            text_color="green",
        )
        self.app.refresh_all()

    def refresh(self):
        pass
