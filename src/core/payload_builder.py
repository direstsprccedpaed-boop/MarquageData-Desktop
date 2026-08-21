import json
from pathlib import Path
from core.models import DocumentIngere
from core.paths import app_data_dir

GLOBAL_PROMPT_HEADER = """Tu es un extracteur de donnees structurees pour des bons de commande / devis de signalisation routiere.

Ce message contient PLUSIEURS documents distincts, chacun delimite par un bloc "=== DOCUMENT doc_id=... ===".
Tu dois analyser CHAQUE document independamment et produire UN OBJET JSON PAR DOCUMENT.

REGLE ABSOLUE (mode SPARSE) : Chaque document ne contient QUE les lignes de prix reellement sollicitees pour cette commande. L'absence d'un code prix dans un document ne signifie PAS une quantite de zero. N'invente, ne complete et ne reconstitue JAMAIS un article absent du tableau d'un document. N'extrait QUE les lignes visiblement presentes dans chaque document source.

FORMAT DE REPONSE OBLIGATOIRE :
Reponds UNIQUEMENT par un tableau JSON (array), sans aucun texte explicatif, sans markdown, sans balises de code, contenant un objet par document dans l'ordre ou ils apparaissent, chacun conforme au schema suivant :

[
  {
    "doc_id": "reprends exactement le doc_id indique dans le bloc du document",
    "numero_commande": "string",
    "date_commande": "YYYY-MM-DD",
    "secteur": "string",
    "lignes": [
      {"code_prix_source": "string", "designation": "string", "quantite": 0.0, "unite": "string", "pu_ht": 0.0}
    ]
  }
]

Le tableau final doit contenir exactement autant d'objets que de blocs "=== DOCUMENT doc_id=... ===" ci-dessous.

DOCUMENTS A ANALYSER :
"""


def _doc_block(doc: DocumentIngere, max_chars_per_doc: int) -> str:
    return f"=== DOCUMENT doc_id={doc.doc_id} ===\n{doc.texte_brut[:max_chars_per_doc]}\n"


def build_global_prompts(
    docs: list[DocumentIngere],
    max_chars_per_batch: int = 100_000,
    max_chars_per_doc: int = 20_000,
) -> list[dict]:
    """Regroupe tous les documents ingeres en un ou plusieurs prompts globaux.

    Un seul prompt est genere si le volume total tient dans max_chars_per_batch.
    Sinon, l'app decoupe automatiquement en plusieurs lots (batches) pour ne
    jamais depasser la fenetre de contexte du LLM cible. Chaque lot reste
    autonome : une seule reponse JSON (array) par lot.

    Retourne une liste de dicts {"prompt": str, "doc_ids": list[str]}.
    """
    valid_docs = [d for d in docs if not d.erreur]
    batches: list[list[DocumentIngere]] = []
    current_batch: list[DocumentIngere] = []
    current_len = 0

    for doc in valid_docs:
        block_len = min(len(doc.texte_brut), max_chars_per_doc)
        if current_batch and (current_len + block_len > max_chars_per_batch):
            batches.append(current_batch)
            current_batch = []
            current_len = 0
        current_batch.append(doc)
        current_len += block_len

    if current_batch:
        batches.append(current_batch)

    results = []
    for batch in batches:
        body = "\n".join(_doc_block(d, max_chars_per_doc) for d in batch)
        prompt = GLOBAL_PROMPT_HEADER + body
        results.append({"prompt": prompt, "doc_ids": [d.doc_id for d in batch]})
    return results


def export_global_prompts(docs: list[DocumentIngere], max_chars_per_batch: int = 100_000) -> list[Path]:
    """Exporte chaque lot de prompt global dans un fichier .txt distinct."""
    out_dir = app_data_dir() / "data" / "prompts_globaux"
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = build_global_prompts(docs, max_chars_per_batch=max_chars_per_batch)
    paths = []
    for i, batch in enumerate(batches, start=1):
        p = out_dir / f"lot_{i:02d}_prompt_global.txt"
        p.write_text(batch["prompt"], encoding="utf-8")
        paths.append(p)
    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            [{"fichier": f"lot_{i:02d}_prompt_global.txt", "doc_ids": b["doc_ids"]} for i, b in enumerate(batches, start=1)],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return paths
