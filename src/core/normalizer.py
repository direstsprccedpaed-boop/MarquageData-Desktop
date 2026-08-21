import json
from pathlib import Path
from core.models import MappingAlias, CommandeExtraite
from core.paths import app_data_dir

CONFIG_PATH = app_data_dir() / "data" / "mapping_config.json"


def load_mapping() -> dict[str, MappingAlias]:
    if not CONFIG_PATH.exists():
        return {}
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {k: MappingAlias.model_validate(v) for k, v in raw.items()}


def save_mapping(mapping: dict[str, MappingAlias]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {k: v.model_dump() for k, v in mapping.items()}
    CONFIG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_source_codes(commandes: list[CommandeExtraite]) -> set[str]:
    codes = set()
    for c in commandes:
        for ligne in c.lignes:
            codes.add(ligne.code_prix_source.strip())
    return codes


def apply_mapping(
    commandes: list[CommandeExtraite], mapping: dict[str, MappingAlias]
) -> tuple[list[dict], list[str]]:
    """Applique le mapping et retourne les lignes enrichies + la liste des codes a qualifier."""
    lignes_mappees = []
    a_qualifier: set[str] = set()
    for c in commandes:
        for ligne in c.lignes:
            code_src = ligne.code_prix_source.strip()
            alias = mapping.get(code_src)
            if alias and alias.statut == "mappe":
                code_cible = alias.code_cible
            else:
                code_cible = code_src
                a_qualifier.add(code_src)
            lignes_mappees.append({
                "doc_id": c.doc_id,
                "numero_commande": c.numero_commande,
                "date_commande": c.date_commande,
                "code_prix_source": code_src,
                "code_prix_cible": code_cible,
                "designation": ligne.designation,
                "quantite": ligne.quantite,
                "unite": ligne.unite,
                "pu_ht": ligne.pu_ht,
            })
    return lignes_mappees, sorted(a_qualifier)


def upsert_alias(mapping: dict[str, MappingAlias], code_source: str, code_cible: str) -> dict[str, MappingAlias]:
    mapping[code_source] = MappingAlias(code_source=code_source, code_cible=code_cible, statut="mappe")
    return mapping
