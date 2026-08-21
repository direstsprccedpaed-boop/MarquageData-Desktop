import json
from pathlib import Path
from pydantic import ValidationError
from core.models import CommandeExtraite, RapportAudit


def _detect_anomalies(commande: CommandeExtraite) -> list[str]:
    anomalies = []
    for ligne in commande.lignes:
        if ligne.quantite < 0:
            anomalies.append(f"{commande.doc_id}: quantite negative sur {ligne.code_prix_source}")
        if ligne.pu_ht <= 0:
            anomalies.append(f"{commande.doc_id}: PU manquant/nul sur {ligne.code_prix_source}")
        if not ligne.code_prix_source.strip():
            anomalies.append(f"{commande.doc_id}: code prix vide")
    return anomalies


def parse_json_text(raw_text: str) -> tuple[CommandeExtraite | None, list[str]]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, [f"JSON invalide: {exc}"]
    try:
        commande = CommandeExtraite.model_validate(data)
    except ValidationError as exc:
        return None, [str(e) for e in exc.errors()]
    return commande, _detect_anomalies(commande)


def import_json_files(paths: list[Path]) -> tuple[list[CommandeExtraite], RapportAudit]:
    valides: list[CommandeExtraite] = []
    toutes_anomalies: list[str] = []
    total_lignes = 0
    for p in paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception as exc:
            toutes_anomalies.append(f"{p.name}: erreur lecture ({exc})")
            continue
        commande, anomalies = parse_json_text(raw)
        if commande:
            valides.append(commande)
            total_lignes += len(commande.lignes)
        toutes_anomalies.extend(anomalies)

    rapport = RapportAudit(
        total_lignes=total_lignes,
        lignes_valides=total_lignes - len([a for a in toutes_anomalies if "negative" in a or "nul" in a]),
        anomalies=toutes_anomalies,
    )
    return valides, rapport
