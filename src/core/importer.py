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
    """Conserve pour compatibilite : parse une reponse JSON representant UNE seule commande."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, [f"JSON invalide: {exc}"]
    try:
        commande = CommandeExtraite.model_validate(data)
    except ValidationError as exc:
        return None, [str(e) for e in exc.errors()]
    return commande, _detect_anomalies(commande)


def parse_json_array(raw_text: str) -> tuple[list[CommandeExtraite], list[str]]:
    """Parse une reponse JSON globale : soit un tableau [ {...}, {...} ],
    soit un objet unique {...} (retro-compatibilite avec l'ancien flux par document).
    Chaque element est valide independamment ; un element invalide n'empeche pas
    le traitement des autres."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return [], [f"JSON invalide: {exc}"]

    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return [], ["Le JSON doit etre un objet ou un tableau d'objets"]

    valides: list[CommandeExtraite] = []
    anomalies: list[str] = []

    for idx, item in enumerate(items):
        doc_ref = item.get("doc_id", f"element_{idx}") if isinstance(item, dict) else f"element_{idx}"
        try:
            commande = CommandeExtraite.model_validate(item)
        except ValidationError as exc:
            for err in exc.errors():
                anomalies.append(f"{doc_ref}: {err.get('msg', err)} (champ: {'.'.join(str(p) for p in err.get('loc', []))})")
            continue
        valides.append(commande)
        anomalies.extend(_detect_anomalies(commande))

    return valides, anomalies


def import_json_files(paths: list[Path]) -> tuple[list[CommandeExtraite], RapportAudit]:
    """Importe un ou plusieurs fichiers JSON. Chaque fichier peut contenir
    un tableau de plusieurs commandes (reponse globale) ou une commande unique."""
    valides: list[CommandeExtraite] = []
    toutes_anomalies: list[str] = []
    total_lignes = 0
    for p in paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception as exc:
            toutes_anomalies.append(f"{p.name}: erreur lecture ({exc})")
            continue
        commandes, anomalies = parse_json_array(raw)
        valides.extend(commandes)
        total_lignes += sum(len(c.lignes) for c in commandes)
        toutes_anomalies.extend(f"{p.name} -> {a}" for a in anomalies)

    rapport = RapportAudit(
        total_lignes=total_lignes,
        lignes_valides=total_lignes - len([a for a in toutes_anomalies if "negative" in a or "nul" in a]),
        anomalies=toutes_anomalies,
    )
    return valides, rapport


def import_json_text_global(raw_text: str) -> tuple[list[CommandeExtraite], RapportAudit]:
    """Importe directement un texte JSON colle (tableau global ou objet unique)."""
    commandes, anomalies = parse_json_array(raw_text)
    total_lignes = sum(len(c.lignes) for c in commandes)
    rapport = RapportAudit(
        total_lignes=total_lignes,
        lignes_valides=total_lignes - len([a for a in anomalies if "negative" in a or "nul" in a]),
        anomalies=anomalies,
    )
    return commandes, rapport
