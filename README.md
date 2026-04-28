# AVPS DRHFPNC Processing

Ce projet permet de récupérer les Avis de Vacances de Poste (AVP) de la DRHFPNC depuis `data.gouv.nc`, de les convertir en Markdown et de générer un fichier CSV global.

Il est basé sur la logique de `opt-nc/avps` mais sans filtrage par direction (tous les AVPs sont inclus).

## Pré-requis

- [uv](https://github.com/astral-sh/uv) installé.

## Installation

```bash
uv sync
```

## Utilisation

Pour lancer la récupération et la conversion :

```bash
uv run src/process_avps.py
```

Les résultats seront générés dans le dossier `data/` :
- `all_avps.csv` : Le fichier CSV contenant toutes les métadonnées.
- `*.md` : Les fichiers Markdown convertis à partir des PDFs originaux.

## Fonctionnement

1. Téléchargement des données au format Parquet depuis l'API de `data.gouv.nc`.
2. Extraction des URLs de téléchargement des PDFs.
3. Utilisation de `marker-pdf` pour une conversion haute qualité des PDFs en Markdown (avec extraction d'images).
4. Sauvegarde du CSV final.
