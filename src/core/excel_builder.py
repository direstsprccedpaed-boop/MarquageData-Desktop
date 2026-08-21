import re
import copy
from pathlib import Path
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from core.models import CodePrixBPU, SectionBPU, LigneConsolidee

SECTION_PATTERN = re.compile(r"^\s*([A-Z]{1,2})\s*[-\u2013]\s")
CODE_PATTERN = re.compile(r"^([A-Z]{1,2})(\d+(?:\.\d+)?)$")

KEYWORDS = {
    "numero": ["n\u00b0 de prix", "n de prix", "numero de prix", "code prix", "n\u00b0prix"],
    "designation": ["designation", "d\u00e9signation", "libelle", "libell\u00e9"],
    "unite": ["unite", "unit\u00e9", "unites", "unit\u00e9s"],
    "pu": ["prix unitaire", "p.u.", "pu ht", "pu (ht)"],
}
EXCLUDE_PU = ["designation", "d\u00e9signation", "en toutes lettres"]


def _first_line(value: str) -> str:
    return (value or "").split("\n")[0].strip().lower()


def detect_columns(ws: Worksheet, header_row: int = 1, max_col: int = 30) -> dict:
    detected = {"numero": None, "designation": None, "unite": None, "pu": None}
    for col in range(1, max_col + 1):
        cell = ws.cell(row=header_row, column=col)
        raw = str(cell.value or "")
        first_line = _first_line(raw)
        if not first_line:
            continue
        for key, kws in KEYWORDS.items():
            if key == "pu" and any(ex in first_line for ex in EXCLUDE_PU):
                continue
            if detected[key] is None and any(kw in first_line for kw in kws):
                detected[key] = col
    warnings = [k for k, v in detected.items() if v is None]
    if warnings:
        detected["_defaults_used"] = True
        detected["numero"] = detected["numero"] or 1
        detected["designation"] = detected["designation"] or 2
        detected["unite"] = detected["unite"] or 3
        detected["pu"] = detected["pu"] or 4
    else:
        detected["_defaults_used"] = False
    detected["_missing"] = warnings
    return detected


def parse_bpu_structure(path: Path, sheet_name: str | None = None) -> tuple[dict[str, CodePrixBPU], list[SectionBPU], dict]:
    wb = load_workbook(str(path), data_only=False)
    ws = wb[sheet_name] if sheet_name else wb.active
    cols = detect_columns(ws)

    codes: dict[str, CodePrixBPU] = {}
    sections: list[SectionBPU] = []
    current_section: str | None = None
    section_start_row: int | None = None

    max_row = ws.max_row
    for row in range(2, max_row + 1):
        num_cell = ws.cell(row=row, column=cols["numero"]).value
        text_candidate = str(num_cell or "").strip()
        match_section = SECTION_PATTERN.match(text_candidate) or (
            SECTION_PATTERN.match(str(ws.cell(row=row, column=cols["designation"]).value or ""))
        )
        if match_section:
            if current_section is not None and section_start_row is not None:
                sections.append(SectionBPU(
                    lettre=current_section, ligne_entete=section_start_row,
                    ligne_debut=section_start_row + 1, ligne_fin=row - 1,
                ))
            current_section = match_section.group(1)
            section_start_row = row
            continue

        code_match = CODE_PATTERN.match(text_candidate)
        if code_match and current_section:
            designation_raw = str(ws.cell(row=row, column=cols["designation"]).value or "")
            intitule_court = _first_line(designation_raw).split("pu :")[0].split("l'heure")[0].strip() or designation_raw.strip()
            unite = str(ws.cell(row=row, column=cols["unite"]).value or "").strip()
            pu_val = ws.cell(row=row, column=cols["pu"]).value
            try:
                pu_ref = float(pu_val) if pu_val is not None else 0.0
            except (TypeError, ValueError):
                pu_ref = 0.0
            codes[text_candidate] = CodePrixBPU(
                code=text_candidate, intitule_court=intitule_court, unite=unite,
                pu_reference=pu_ref, section=current_section, ligne_source=row,
            )

    if current_section is not None and section_start_row is not None:
        sections.append(SectionBPU(
            lettre=current_section, ligne_entete=section_start_row,
            ligne_debut=section_start_row + 1, ligne_fin=max_row,
        ))

    meta = {"cols": cols, "nb_sections": len(sections), "nb_codes": len(codes)}
    wb.close()
    return codes, sections, meta


def _copy_style(src_cell, dst_cell) -> None:
    if src_cell.has_style:
        dst_cell.font = copy.copy(src_cell.font)
        dst_cell.border = copy.copy(src_cell.border)
        dst_cell.fill = copy.copy(src_cell.fill)
        dst_cell.number_format = copy.copy(src_cell.number_format)
        dst_cell.alignment = copy.copy(src_cell.alignment)


def generate_dqe_from_bpu(
    bpu_path: Path,
    consolidation: dict[str, LigneConsolidee],
    output_path: Path,
    qte_defaut_absent: float = 0.0,
    omit_empty_sections: bool = False,
    sheet_name: str | None = None,
) -> dict:
    codes_bpu, sections, meta = parse_bpu_structure(bpu_path, sheet_name)
    src_wb = load_workbook(str(bpu_path), data_only=False)
    src_ws = src_wb[sheet_name] if sheet_name else src_wb.active
    cols = meta["cols"]

    dqe_wb = Workbook()
    dqe_ws = dqe_wb.active
    dqe_ws.title = "DQE"

    headers = ["N\u00b0 Prix", "Intitul\u00e9 court", "Unit\u00e9", "Prix Unitaire", "Quantit\u00e9", "Total"]
    for c, h in enumerate(headers, start=1):
        dqe_ws.cell(row=1, column=c, value=h)

    current_row = 2
    section_totals: list[tuple[str, int]] = []
    not_found_in_history = []

    for section in sections:
        codes_section = [c for c, v in codes_bpu.items() if v.section == section.lettre]
        if not codes_section:
            continue
        if omit_empty_sections and not any(c in consolidation for c in codes_section):
            continue

        src_header_cell = src_ws.cell(row=section.ligne_entete, column=cols["numero"])
        header_row_idx = current_row
        dqe_ws.cell(row=current_row, column=1, value=src_header_cell.value)
        _copy_style(src_header_cell, dqe_ws.cell(row=current_row, column=1))
        current_row += 1
        section_start = current_row

        for code in sorted(codes_section):
            bpu_info = codes_bpu[code]
            consolide = consolidation.get(code)
            statut_constate = consolide is not None
            if not statut_constate:
                not_found_in_history.append(code)

            pu = consolide.pu_dqe if consolide else bpu_info.pu_reference
            qte = consolide.qte_dqe if consolide else qte_defaut_absent

            dqe_ws.cell(row=current_row, column=1, value=code)
            dqe_ws.cell(row=current_row, column=2, value=bpu_info.intitule_court)
            dqe_ws.cell(row=current_row, column=3, value=bpu_info.unite)
            pu_cell = dqe_ws.cell(row=current_row, column=4, value=round(pu, 4))
            qte_cell = dqe_ws.cell(row=current_row, column=5, value=round(qte, 3))
            total_cell = dqe_ws.cell(row=current_row, column=6, value=f"=D{current_row}*E{current_row}")

            pu_cell.number_format = "#,##0.00 \u20ac"
            total_cell.number_format = "#,##0.00 \u20ac"

            if not statut_constate:
                for col_idx in range(1, 7):
                    cell = dqe_ws.cell(row=current_row, column=col_idx)
                    cell.font = cell.font.copy(italic=True, color="808080")

            current_row += 1

        section_end = current_row - 1
        if section_end >= section_start:
            dqe_ws.cell(row=current_row, column=2, value=f"TOTAL SECTION {section.lettre}")
            total_section_cell = dqe_ws.cell(row=current_row, column=6, value=f"=SUM(F{section_start}:F{section_end})")
            total_section_cell.number_format = "#,##0.00 \u20ac"
            section_totals.append((section.lettre, current_row))
            current_row += 1
        current_row += 1

    if section_totals:
        formula = "=" + "+".join(f"F{row}" for _, row in section_totals)
        dqe_ws.cell(row=current_row, column=2, value="TOTAL GENERAL HT")
        total_general_cell = dqe_ws.cell(row=current_row, column=6, value=formula)
        total_general_cell.number_format = "#,##0.00 \u20ac"

    for col_idx, width in enumerate([12, 45, 10, 15, 12, 15], start=1):
        dqe_ws.column_dimensions[get_column_letter(col_idx)].width = width

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dqe_wb.save(str(output_path))
    src_wb.close()

    return {
        "nb_sections": len(sections),
        "nb_codes_bpu": len(codes_bpu),
        "nb_codes_constates": len(consolidation),
        "codes_absents_historique": not_found_in_history,
        "colonnes_detectees": cols,
        "output_path": str(output_path),
    }


def verify_formulas(output_path: Path) -> list[str]:
    wb = load_workbook(str(output_path), data_only=False)
    ws = wb.active
    anomalies = []
    for row in range(2, ws.max_row + 1):
        d_val = ws.cell(row=row, column=4).value
        e_val = ws.cell(row=row, column=5).value
        f_val = ws.cell(row=row, column=6).value
        if isinstance(d_val, (int, float)) and isinstance(e_val, (int, float)):
            if not (isinstance(f_val, str) and f_val.startswith("=")):
                anomalies.append(f"Ligne {row}: formule totale manquante")
    wb.close()
    return anomalies
