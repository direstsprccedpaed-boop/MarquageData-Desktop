from datetime import date
from collections import defaultdict
from core.models import LigneConsolidee, ParametresEstimation


def consolidate(lignes_mappees: list[dict], params: ParametresEstimation) -> dict[str, LigneConsolidee]:
    """Consolidation SPARSE : seuls les codes reellement rencontres sont retournes,
    aucune hypothese de sequence continue de codes prix n'est faite."""
    groupes: dict[str, list[dict]] = defaultdict(list)
    for ligne in lignes_mappees:
        groupes[ligne["code_prix_cible"]].append(ligne)

    resultat: dict[str, LigneConsolidee] = {}
    for code, lignes in groupes.items():
        qte_totale = sum(l["quantite"] for l in lignes)
        annees = set()
        dernier_pu = 0.0
        derniere_date = ""
        for l in lignes:
            try:
                annees.add(date.fromisoformat(l["date_commande"]).year)
            except Exception:
                pass
            if l["date_commande"] >= derniere_date:
                derniere_date = l["date_commande"]
                dernier_pu = l["pu_ht"]

        nb_annees = max(len(annees), 1)
        qte_moyenne_annee = qte_totale / nb_annees

        qte_dqe = qte_totale * params.coef_alea
        pu_dqe = dernier_pu * params.coef_indexation * params.coef_marge

        resultat[code] = LigneConsolidee(
            code_prix=code,
            designation=lignes[0]["designation"],
            unite=lignes[0]["unite"],
            qte_consolidee=qte_totale,
            pu_reference=dernier_pu,
            qte_dqe=round(qte_dqe, 3),
            pu_dqe=round(pu_dqe, 4),
            nb_documents=len({l["doc_id"] for l in lignes}),
            statut="constate",
        )
    return resultat
