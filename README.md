# MarquageData-Desktop

Application de bureau native Windows (CustomTkinter) pour le pipeline de consolidation
de commandes historiques de signalisation routiere et la generation de DQE Excel.

## Aucun serveur, aucun navigateur
Application 100% GUI native - aucun port TCP local, compatible pare-feu strict.

## Build local
```bash
pip install -r requirements.txt
python src/main.py
```

## Compilation en .exe
```bash
pyinstaller build_config.spec --clean --noconfirm
```
L'executable est produit dans `dist/MarquageData-Desktop.exe`.

## Build automatise (CI/CD)
Un push sur `main` ou un tag `v*` declenche `.github/workflows/build-windows-exe.yml`
qui compile sur `windows-latest` et publie l'executable en artefact (et en Release sur tag).

## Donnees locales
Les fichiers de travail (textes bruts, mapping, DQE generes) sont stockes dans
`%APPDATA%/MarquageDataApp/`.

## Workflow metier
1. Ingestion du dossier source (thread d'arriere-plan, OCR auto si < 50 caracteres/page).
2. Generation des prompts LLM sparse (copie manuelle vers un LLM externe).
3. Import et validation des reponses JSON.
4. Mapping des alias de codes prix (PN -> BPUF).
5. Consolidation statistique sparse avec coefficients d'alea/indexation/marge.
6. Analyse du BPUF cible et generation du DQE (.xlsx) avec formules et totaux de section.
