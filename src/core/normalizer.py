import json
import difflib
from pathlib import Path
from core.models import MappingAlias, CommandeExtraite, CodePrixBPU
from core.paths import app_data_dir

CONFIG_PATH = app_data_dir() / "data" / "mapping_config.json"

# Statuts possibles pour un MappingAlias :
#   "mappe"       -> correspondance exacte ou validee vers un code du BPUF cible
#   "conserve"    -> code source conserve tel quel (pas de correspondance BPUF garantie),
#                    a corriger si besoin directement dans le DQE Excel genere
#   "a_qualifier" -> aucune decision prise, ligne exclue de la consolidation


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


def collect_source_designations(commandes: list[CommandeExtraite]) -> dict[str, str]:
    """Retourne, pour chaque code source rencontre, la premiere designation associee
    (utilisee comme base pour la suggestion par similarite de texte)."""
    result: dict[str, str] = {}
    for c in commandes:
        for ligne in c.lignes:
            code = ligne.code_prix_source.strip()
            if code not in result:
                result[code] = ligne.designation
    return result


def auto_map_from_bpu(
    commandes: list[CommandeExtraite],
    codes_bpu: dict[str, CodePrixBPU],
    existing_mapping: dict[str, MappingAlias],
    fuzzy_threshold: float = 0.55,
) -> tuple[dict[str, MappingAlias], dict[str, str], list[str]]:
    """Auto-mapping en 2 passes, exploitant le fait que les commandes historiques
    sont generalement passees sur la base d'un DQE reprenant deja la nomenclature BPUF.

    Passe 1 (identite) : si un code_prix_source correspond exactement a un code du
    BPUF cible, il est mappe automatiquement vers lui-meme -> aucune saisie requise.

    Passe 2 (suggestion) : pour les codes restants, une suggestion est calculee par
    similarite textuelle entre la designation de la commande et l'intitule court de
    chaque prix du BPUF. La suggestion reste modifiable/validable par l'utilisateur -
    elle n'est jamais appliquee automatiquement sans confirmation. L'utilisateur peut
    aussi choisir de conserver le code source tel quel (voir keep_source_code) plutot
    que de forcer une correspondance BPUF, quitte a corriger directement dans le DQE
    Excel genere.

    Retourne (mapping_mis_a_jour_avec_les_identites, suggestions, codes_sans_suggestion).
    """
    source_designations = collect_source_designations(commandes)
    mapping = dict(existing_mapping)
    suggestions: dict[str, str] = {}
    sans_suggestion: list[str] = []

    bpu_designations = {code: info.intitule_court for code, info in codes_bpu.items()}

    for code, designation in source_designations.items():
        if code in mapping:
            continue

        if code in codes_bpu:
            mapping[code] = MappingAlias(code_source=code, code_cible=code, statut="mappe")
            continue

        best_code, best_score = None, 0.0
        for bpu_code, bpu_desig in bpu_designations.items():
            score = difflib.SequenceMatcher(None, designation.lower().strip(), bpu_desig.lower().strip()).ratio()
            if score > best_score:
                best_score, best_code = score, bpu_code

        if best_code and best_score >= fuzzy_threshold:
            suggestions[code] = best_code
        else:
            sans_suggestion.append(code)

    return mapping, suggestions, sans_suggestion


def apply_mapping(
    commandes: list[CommandeExtraite], mapping: dict[str, MappingAlias]
) -> tuple[list[dict], list[str]]:
    """Applique le mapping et retourne les lignes enrichies + la liste des codes a qualifier.
    Les statuts "mappe" et "conserve" sont tous deux consideres comme resolus."""
    lignes_mappees = []
    a_qualifier: set[str] = set()
    for c in commandes:
        for ligne in c.lignes:
            code_src = ligne.code_prix_source.strip()
            alias = mapping.get(code_src)
            if alias and alias.statut in ("mappe", "conserve"):
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


def keep_source_code(mapping: dict[str, MappingAlias], code_source: str) -> dict[str, MappingAlias]:
    """Conserve le code source tel quel comme code cible, sans exiger de correspondance
    BPUF verifiee. Utile quand une correction finale directement dans le DQE Excel est
    plus rapide/pertinente qu'un mapping precis a la saisie."""
    mapping[code_source] = MappingAlias(code_source=code_source, code_cible=code_source, statut="conserve")
    return mapping


def keep_all_remaining_as_source(
    commandes: list[CommandeExtraite], mapping: dict[str, MappingAlias]
) -> dict[str, MappingAlias]:
    """Applique keep_source_code() a tous les codes source encore non resolus."""
    codes = collect_source_codes(commandes)
    for code in codes:
        if code not in mapping:
            mapping = keep_source_code(mapping, code)
    return mapping
