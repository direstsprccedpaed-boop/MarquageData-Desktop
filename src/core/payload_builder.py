import json
from pathlib import Path
from core.models import DocumentIngere
from core.paths import app_data_dir

PROMPT_TEMPLATE = """Tu es un extracteur de donnees structurees pour des bons de commande / devis de signalisation routiere.

REGLE ABSOLUE (mode SPARSE) : Ce document ne contient QUE les lignes de prix reellement sollicitees pour cette commande. L'absence d'un code prix dans ce texte ne signifie PAS une quantite de zero. N'invente, ne complete et ne reconstitue JAMAIS un article absent du tableau. N'extrait QUE les lignes visiblement presentes dans le texte source.

Retourne UNIQUEMENT un JSON valide strictement conforme au schema suivant, sans texte explicatif, sans markdown, sans balises de code :

{{
  "doc_id": "{doc_id}",
  "numero_commande": "string",
  "date_commande": "YYYY-MM-DD",
  "secteur": "string",
  "lignes": [
    {{"code_prix_source": "string", "designation": "string", "quantite": 0.0, "unite": "string", "pu_ht": 0.0}}
  ]
}}

TEXTE SOURCE DU DOCUMENT (doc_id={doc_id}) :
---
{texte}
---
"""


def build_prompt(doc: DocumentIngere) -> str:
    return PROMPT_TEMPLATE.format(doc_id=doc.doc_id, texte=doc.texte_brut[:20000])


def export_batch(docs: list[DocumentIngere]) -> Path:
    batch = [{"doc_id": d.doc_id, "prompt": build_prompt(d)} for d in docs if not d.erreur]
    out_path = app_data_dir() / "data" / "llm_batch_queue.json"
    out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def export_individual(docs: list[DocumentIngere]) -> list[Path]:
    out_dir = app_data_dir() / "data" / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for d in docs:
        if d.erreur:
            continue
        p = out_dir / f"{d.doc_id}_prompt.txt"
        p.write_text(build_prompt(d), encoding="utf-8")
        paths.append(p)
    return paths
