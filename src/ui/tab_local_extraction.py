import customtkinter as ctk
from core.local_extractor import extract_batch_local, extract_document_local, confirm_template, load_templates
from core.importer import find_duplicates


class TabLocalExtraction(ctk.CTkScrollableFrame):
    """Alternative 100% locale au flux 'Prompts LLM -> Import JSON'. Aucune
    donnee n'est envoyee a l'exterieur : l'extraction se fait par detection
    de tableau + memoire de gabarits appris (voir core/local_extractor.py)."""

    def __init__(self, parent, state, app):
        super().__init__(parent)
        self.state = state
        self.app = app
        self.pending_templates: dict = {}
        self.pending_docs_by_fp: dict = {}

        ctk.CTkLabel(
            self, text="Extraction locale (sans LLM externe)", font=("", 16, "bold"),
        ).pack(pady=(15, 5))
        ctk.CTkLabel(
            self,
            text="Cette extraction se fait entierement sur votre poste, sans aucun envoi de donnees vers un "
                 "service externe. Elle repere les tableaux dans vos documents et memorise, une fois valide, "
                 "la correspondance des colonnes pour chaque mise en page rencontree : les documents suivants "
                 "au meme format sont ensuite traites automatiquement.",
            text_color="gray", wraplength=1050, justify="left",
        ).pack(padx=20, pady=(0, 10), anchor="w")

        ctk.CTkButton(self, text="Lancer l'extraction locale", command=self.run_extraction, height=40).pack(pady=10)

        self.summary_label = ctk.CTkLabel(self, text="Aucune extraction lancée.", justify="left", wraplength=1050)
        self.summary_label.pack(pady=5, anchor="w", padx=20)

        ctk.CTkLabel(self, text="Gabarits en attente de validation", font=("", 13, "bold")).pack(pady=(15, 5))
        self.templates_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.templates_frame.pack(padx=20, pady=5, fill="x")

        self.results_box = ctk.CTkTextbox(self, width=1050, height=280)
        self.results_box.pack(padx=20, pady=15, fill="both", expand=True)

    def run_extraction(self):
        if not self.state.documents:
            self.summary_label.configure(text="⚠️ Aucun document ingéré — lancez d'abord un scan à l'onglet 1.", text_color="orange")
            return

        commandes, rapports, gabarits_en_attente = extract_batch_local(self.state.documents)
        self.pending_templates = gabarits_en_attente

        if commandes:
            ajoutees, doublons = find_duplicates(self.state.commandes_extraites, commandes)
            self.state.commandes_extraites.extend(ajoutees)
        else:
            ajoutees, doublons = [], []

        nb_ok = len(ajoutees)
        nb_attente = sum(len(v["doc_ids"]) for v in gabarits_en_attente.values())
        nb_erreur = sum(1 for r in rapports if r.get("erreur"))

        self.summary_label.configure(
            text=f"{nb_ok} commande(s) extraite(s) et ajoutée(s) automatiquement (total cumulé: "
                 f"{len(self.state.commandes_extraites)}) | {nb_attente} document(s) en attente de validation "
                 f"de gabarit (voir ci-dessous) | {nb_erreur} document(s) sans tableau détectable | "
                 f"{len(doublons)} doublon(s) ignoré(s).",
            text_color="white",
        )

        self.results_box.delete("1.0", "end")
        for r in rapports:
            if r.get("erreur"):
                self.results_box.insert("end", f"{r['doc_id']}: ERREUR — {r['erreur']}\n")
            elif r.get("mapping_a_valider"):
                self.results_box.insert("end", f"{r['doc_id']}: en attente de validation de gabarit\n")
            else:
                self.results_box.insert(
                    "end",
                    f"{r['doc_id']}: {r['nb_lignes']} ligne(s) extraite(s), {r['nb_lignes_ignorees']} ignorée(s) "
                    f"(quantité/PU non numérique)"
                    + (" — métadonnées incomplètes, à vérifier" if r.get("metadata_incomplete") else "") + "\n",
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
            box.pack(fill="x", pady=6, padx=2)

            ctk.CTkLabel(
                box, text=f"Nouveau format détecté ({len(info['doc_ids'])} document(s) concerné(s))",
                font=("", 12, "bold"),
            ).pack(anchor="w", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                box, text="En-tête détecté : " + " | ".join(h or "(vide)" for h in info["header"][:8]),
                wraplength=1000, justify="left", text_color="gray",
            ).pack(anchor="w", padx=10)

            menus_row = ctk.CTkFrame(box, fg_color="transparent")
            menus_row.pack(fill="x", padx=10, pady=8)
            col_options = [str(i) for i in range(len(info["header"]))]
            menus = {}
            for key, label in [("code", "Code prix"), ("designation", "Désignation"), ("quantite", "Quantité"), ("unite", "Unité"), ("pu", "Prix U.")]:
                sub = ctk.CTkFrame(menus_row, fg_color="transparent")
                sub.pack(side="left", padx=8)
                ctk.CTkLabel(sub, text=label, font=("", 10)).pack()
                menu = ctk.CTkOptionMenu(sub, values=["aucune"] + col_options, width=90)
                current = info["mapping"].get(key)
                menu.set(str(current) if current is not None else "aucune")
                menu.pack()
                menus[key] = menu

            ctk.CTkButton(
                box, text="Valider ce gabarit et relancer l'extraction",
                command=lambda fp=fp, info=info, menus=menus: self._validate_template(fp, info, menus),
            ).pack(anchor="w", padx=10, pady=(0, 10))

    def _validate_template(self, fp, info, menus):
        mapping = {}
        for key, menu in menus.items():
            val = menu.get()
            mapping[key] = int(val) if val != "aucune" else None
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
                 f"(total cumulé: {len(self.state.commandes_extraites)}). Ce format sera reconnu automatiquement "
                 f"pour tous les prochains documents similaires.",
            text_color="green",
        )
        self.app.refresh_all()

    def refresh(self):
        pass
