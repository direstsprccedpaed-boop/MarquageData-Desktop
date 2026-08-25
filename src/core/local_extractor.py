import re
import csv
import json
import hashlib
from pathlib import Path
from typing import Optional

import pdfplumber
import docx
from openpyxl import load_workbook

from core.models import CommandeExtraite, LigneCommande, DocumentIngere
from core.paths import app_data_dir

TEMPLATES_PATH = app_data_dir() / "data" / "extraction_templates.json"

# Mots-cles generiques (aucun metier code en dur) pour deviner le role de
# chaque colonne d'un tableau de lignes de commande.
LINE_KEYWORDS = {
    "code": ["code prix", "n\u00b0 prix", "n prix", "reference", "r\u00e9f\u00e9rence", "r\u00e9f.", "article", "code"],
    "designation": ["designation", "d\u00e9signation", "libelle", "libell\u00e9", "intitul\u00e9", "d\u00e9nomination"],
    "quantite": ["quantite", "quantit\u00e9", "qte", "qt\u00e9", "qty"],
    "unite": ["unite", "unit\u00e9", "un.", "u.", "unit"],
    "pu": ["prix unitaire", "p.u.", "pu ht", "prix u.", "prix unit."],
}

DATE_PATTERN = re.compile(r"(\d{2}[/\-.]\d{2}[/\-.]\d{4}|\d{4}-\d{2}-\d{2})")
NUM_COMMANDE_PATTERN = re.compile(r"(?:n\u00b0|num[e\u00e9]ro)\s*(?:de\s*)?commande\s*[:\-]?\s*([A-Za-z0-9\-\/]+)", re.IGNORECASE)
SECTEUR_PATTERN = re.compile(r"(CEI\s+[A-Z\u00c9\u00c8\u00c0][\w\-\s]{2,30}|SREX[\-\s]?\w*)", re.IGNORECASE)
NUM_VALUE_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def fingerprint_header(header: list[str]) -> str:
    normalized = "|".join(_normalize(h) for h in header)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def load_templates() -> dict:
    if not TEMPLATES_PATH.exists():
        return {}
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def save_templates(templates: dict) -> None:
    TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_PATH.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")


def confirm_template(fingerprint: str, header: list[str], mapping: dict) -> None:
    """Enregistre durablement le mapping valide par l'utilisateur pour cette
    empreinte d'en-tete : tous les documents futurs partageant la meme mise
    en page seront traites automatiquement, sans nouvelle validation."""
    templates = load_templates()
    templates[fingerprint] = {"header": header, "mapping": mapping}
    save_templates(templates)


def list_templates() -> dict:
    return load_templates()


def delete_template(fingerprint: str) -> None:
    templates = load_templates()
    templates.pop(fingerprint, None)
    save_templates(templates)


def detect_line_columns(header: list[str]) -> dict:
    detected = {"code": None, "designation": None, "quantite": None, "unite": None, "pu": None}
    for idx, cell in enumerate(header):
        norm = _normalize(cell)
        if not norm:
            continue
        for key, kws in LINE_KEYWORDS.items():
            if detected[key] is None and any(kw in norm for kw in kws):
                detected[key] = idx
    return detected


def _parse_number(raw) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace(",", ".")
    m = NUM_VALUE_PATTERN.search(text)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def extract_tables_xlsx(path: Path) -> list[list[list[str]]]:
    wb = load_workbook(str(path), data_only=True, read_only=True)
    tables = []
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    wb.close()
    return tables


def extract_tables_csv(path: Path) -> list[list[list[str]]]:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                except csv.Error:
                    dialect = csv.excel
                rows = [row for row in csv.reader(f, dialect) if any(c.strip() for c in row)]
            return [rows] if rows else []
        except (UnicodeDecodeError, LookupError):
            continue
    return []


def extract_tables_docx(path: Path) -> list[list[list[str]]]:
    document = docx.Document(str(path))
    tables = []
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        rows = [r for r in rows if any(c.strip() for c in r)]
        if rows:
            tables.append(rows)
    return tables


def extract_tables_pdf(path: Path) -> list[list[list[str]]]:
    tables = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for raw_table in page.extract_tables() or []:
                rows = [["" if c is None else str(c).strip() for c in row] for row in raw_table]
                rows = [r for r in rows if any(c.strip() for c in r)]
                if rows:
                    tables.append(rows)
    return tables


EXTRACTORS = {
    ".xlsx": extract_tables_xlsx,
    ".csv": extract_tables_csv,
    ".docx": extract_tables_docx,
    ".pdf": extract_tables_pdf,
}


def extract_metadata(texte: str) -> dict:
    date_commande = ""
    date_match = DATE_PATTERN.search(texte)
    if date_match:
        raw = date_match.group(1).replace("/", "-").replace(".", "-")
        parts = raw.split("-")
        if len(parts[0]) == 4:
            date_commande = raw
        elif len(parts) == 3 and len(parts[2]) == 4:
            date_commande = f"{parts[2]}-{parts[1]}-{parts[0]}"

    num_match = NUM_COMMANDE_PATTERN.search(texte)
    numero_commande = num_match.group(1) if num_match else ""

    secteur_match = SECTEUR_PATTERN.search(texte)
    secteur = secteur_match.group(1).strip() if secteur_match else ""

    return {"numero_commande": numero_commande, "date_commande": date_commande, "secteur": secteur}


def extract_lines_from_table(table: list[list[str]], mapping: dict) -> tuple[list[LigneCommande], int]:
    """Retourne (lignes_valides, nb_lignes_ignorees). Une ligne est ignoree si
    le code est vide ou si la quantite/le PU ne sont pas des nombres
    exploitables - jamais devinee ou inventee."""
    lignes: list[LigneCommande] = []
    nb_ignorees = 0
    for row in table[1:]:
        code_idx = mapping.get("code")
        if code_idx is None or code_idx >= len(row):
            continue
        code = row[code_idx].strip()
        if not code:
            continue

        desi_idx = mapping.get("designation")
        designation = row[desi_idx].strip() if desi_idx is not None and desi_idx < len(row) else ""

        qte_idx = mapping.get("quantite")
        qte = _parse_number(row[qte_idx]) if qte_idx is not None and qte_idx < len(row) else None

        unite_idx = mapping.get("unite")
        unite = row[unite_idx].strip() if unite_idx is not None and unite_idx < len(row) else ""

        pu_idx = mapping.get("pu")
        pu = _parse_number(row[pu_idx]) if pu_idx is not None and pu_idx < len(row) else None

        if qte is None or pu is None:
            nb_ignorees += 1
            continue
        try:
            lignes.append(LigneCommande(
                code_prix_source=code, designation=designation, quantite=qte, unite=unite, pu_ht=pu,
            ))
        except Exception:
            nb_ignorees += 1
    return lignes, nb_ignorees


def extract_document_local(doc: DocumentIngere, templates: dict | None = None) -> tuple[CommandeExtraite | None, dict]:
    """Extraction 100% locale (aucun appel LLM, aucun reseau) d'un document
    ingere, via detection de tableau + memoire de gabarits appris.

    rapport["mapping_a_valider"] est non-None si l'empreinte d'en-tete du
    tableau detecte est inconnue -> une validation humaine ponctuelle est
    necessaire avant que ce document (et tous les suivants au meme format)
    puisse etre traite automatiquement."""
    templates = templates if templates is not None else load_templates()
    path = Path(doc.chemin)
    ext = path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        return None, {"erreur": f"format non supporte pour extraction locale: {ext}"}

    try:
        tables = extractor(path)
    except Exception as exc:
        return None, {"erreur": str(exc)}

    if not tables:
        return None, {"erreur": "aucun tableau detecte dans ce document"}

    table = max(tables, key=len)
    header = table[0]
    fp = fingerprint_header(header)

    if fp in templates:
        mapping = templates[fp]["mapping"]
        mapping_a_valider = None
    else:
        mapping = detect_line_columns(header)
        mapping_a_valider = {"fingerprint": fp, "header": header, "mapping": mapping}

    essentiels_ok = mapping.get("code") is not None and mapping.get("quantite") is not None and mapping.get("pu") is not None
    lignes, nb_ignorees = extract_lines_from_table(table, mapping) if essentiels_ok else ([], 0)

    texte_meta = "\n".join(" ".join(row) for row in table[:3]) + "\n" + doc.texte_brut[:500]
    meta = extract_metadata(texte_meta)

    commande = CommandeExtraite(
        doc_id=doc.doc_id,
        numero_commande=meta["numero_commande"],
        date_commande=meta["date_commande"] or "2000-01-01",
        secteur=meta["secteur"],
        lignes=lignes,
    )

    rapport = {
        "nb_lignes": len(lignes),
        "nb_lignes_ignorees": nb_ignorees,
        "fingerprint": fp,
        "mapping_a_valider": mapping_a_valider,
        "metadata_incomplete": not (meta["numero_commande"] and meta["date_commande"] and meta["secteur"]),
    }
    return commande, rapport


def extract_batch_local(docs: list[DocumentIngere]) -> tuple[list[CommandeExtraite], list[dict], dict]:
    """Traite une liste de documents. Retourne (commandes, rapports,
    gabarits_en_attente) - gabarits_en_attente regroupe par empreinte les
    documents bloques en attente d'une validation humaine, pour ne demander
    qu'une seule confirmation meme si plusieurs documents partagent le meme
    format inconnu."""
    templates = load_templates()
    commandes: list[CommandeExtraite] = []
    rapports: list[dict] = []
    gabarits_en_attente: dict[str, dict] = {}

    for doc in docs:
        commande, rapport = extract_document_local(doc, templates=templates)
        rapport["doc_id"] = doc.doc_id
        rapports.append(rapport)
        if rapport.get("mapping_a_valider"):
            fp = rapport["mapping_a_valider"]["fingerprint"]
            entry = gabarits_en_attente.setdefault(fp, {**rapport["mapping_a_valider"], "doc_ids": []})
            entry["doc_ids"].append(doc.doc_id)
        elif commande and (commande.lignes or not rapport.get("erreur")):
            commandes.append(commande)

    return commandes, rapports, gabarits_en_attente
