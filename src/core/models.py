from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LigneCommande(BaseModel):
    code_prix_source: str
    designation: str
    quantite: float
    unite: str
    pu_ht: float

    @field_validator("quantite")
    @classmethod
    def qte_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("quantite negative")
        return v


class CommandeExtraite(BaseModel):
    doc_id: str
    numero_commande: str
    date_commande: str
    secteur: str
    lignes: list[LigneCommande] = Field(default_factory=list)

    @field_validator("date_commande")
    @classmethod
    def valid_date(cls, v: str) -> str:
        date.fromisoformat(v)
        return v


class MappingAlias(BaseModel):
    code_source: str
    code_cible: str
    statut: str = "mappe"


class ParametresEstimation(BaseModel):
    coef_alea: float = 1.0
    coef_indexation: float = 1.0
    coef_marge: float = 1.0
    qte_defaut_absent: float = 0.0


class LigneConsolidee(BaseModel):
    code_prix: str
    designation: str
    unite: str
    qte_consolidee: float
    pu_reference: float
    qte_dqe: float
    pu_dqe: float
    nb_documents: int
    statut: str = "constate"


class DocumentIngere(BaseModel):
    doc_id: str
    chemin: str
    type_fichier: str
    texte_brut: str
    nb_caracteres: int
    ocr_utilise: bool = False
    erreur: Optional[str] = None


class RapportAudit(BaseModel):
    total_lignes: int
    lignes_valides: int
    anomalies: list[str] = Field(default_factory=list)


class SectionBPU(BaseModel):
    lettre: str
    ligne_entete: int
    ligne_debut: int
    ligne_fin: int


class CodePrixBPU(BaseModel):
    code: str
    intitule_court: str
    unite: str
    pu_reference: float
    section: str
    ligne_source: int
