import pandas as pd
import requests
import io
import json
import os
import unicodedata
import re
from glob import glob

# Configuration CPU pour marker
os.environ["TORCH_DEVICE"] = "cpu"
os.environ["INFERENCE_DEVICE"] = "cpu"

def extract_pdf_url(val):
    """Extrait l'URL du PDF depuis l'objet JSON présent dans la colonne url_pdf."""
    if not val:
        return None
    try:
        if isinstance(val, dict):
            return f"https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/files/{val.get('id')}/download/"
        
        data = json.loads(val)
        if isinstance(data, list):
            data = data[0]
        
        file_id = data.get('id')
        if file_id:
            return f"https://data.gouv.nc/explore/dataset/avis-de-vacances-de-poste-avp-drhfpnc/files/{file_id}/download/"
    except Exception:
        pass
    return val

def process_pdfs_to_markdown(df, data_dir="docs"):
    """Télécharge les PDFs et les convertit en Markdown avec marker-pdf (SANS IMAGES)."""
    print("Début de la conversion des PDFs en Markdown (Images désactivées)...")
    
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import save_output
        
        print("  Chargement des modèles d'IA...")
        model_dict = create_model_dict()
        # Désactivation de l'extraction d'images
        converter = PdfConverter(
            artifact_dict=model_dict,
            config={
                "disable_ocr": True,
                "disable_image_extraction": True
            }
        )
    except Exception as e:
        print(f"  Erreur lors de l'initialisation de marker: {e}")
        return

    os.makedirs(data_dir, exist_ok=True)
    
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        numero = str(row['numero']).replace("/", "_")
        url_pdf = row['url_pdf']
        final_md_path = os.path.join(data_dir, f"{numero}.md")
        
        if not url_pdf or not url_pdf.startswith("http"):
            continue
            
        # On évite de retraiter ce qui existe déjà
        if os.path.exists(final_md_path):
            print(f"  [{i}/{total}] {numero} déjà traité.")
            continue

        try:
            print(f"  [{i}/{total}] Traitement de {numero}...")
            pdf_response = requests.get(url_pdf)
            pdf_response.raise_for_status()
            
            temp_pdf = f"temp_{numero}.pdf"
            with open(temp_pdf, "wb") as f:
                f.write(pdf_response.content)
            
            rendered = converter(temp_pdf)
            save_output(rendered, output_dir=data_dir, fname_base=numero)
            
            # Ajout du titre H1 pour corriger la navigation et lien PDF
            if os.path.exists(final_md_path):
                with open(final_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                libelle_poste = row.get('libelle_poste', 'Poste disponible')
                # Frontmatter pour cacher la navigation latérale sur les pages d'annonces
                header = f'---\nhide:\n  - navigation\n---\n\n'
                header += f'# {numero} - {libelle_poste}\n\n'
                header += f'<div style="text-align: right; margin-bottom: 1em;"><a href="{url_pdf}" target="_blank" style="display: inline-block; padding: 8px 16px; background-color: #3f51b5; color: white; text-decoration: none; border-radius: 4px;">📄 Télécharger le PDF original</a></div>\n\n'
                
                with open(final_md_path, 'w', encoding='utf-8') as f:
                    f.write(header + content)
            
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
                
        except Exception as e:
            print(f"    Erreur pour {numero}: {e}")
            if 'temp_pdf' in locals() and os.path.exists(temp_pdf):
                os.remove(temp_pdf)

    # Nettoyage des métadonnées
    all_json_files = glob(os.path.join(data_dir, "*_meta.json"))
    for json_file in all_json_files:
        os.remove(json_file)

def main():
    url = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/avis-de-vacances-de-poste-avp-drhfpnc/exports/parquet?lang=fr&timezone=Pacific%2FNoumea"
    
    print(f"Téléchargement des données depuis {url}...")
    response = requests.get(url)
    response.raise_for_status()
    
    df = pd.read_parquet(io.BytesIO(response.content))
    col_pdf = 'url_pdf'
    df_all = df[df[col_pdf].notna()].copy()
    
    total = len(df_all)
    print(f"Nombre d'AVPs à traiter : {total}")

    df_all['url_pdf'] = df_all['url_pdf'].apply(extract_pdf_url)

    renames = {
        'numeroavp': 'numero',
        'datepublicationavp': 'date_publication_avp',
        'libelleposte': 'libelle_poste',
        'libelleemploirome': 'libelle_emploi_rome',
        'codeemploirome': 'code_emploi_rome',
        'datemiseenligne': 'date_mis_en_ligne',
        'libellecollectivite': 'libelle_collectivite',
        'libellecorpsgrade': 'libelle_corps_grade',
        'libellecorpsgrade2': 'libelle_corps_grade_2',
        'libelledomaine': 'libelle_domaine',
        'libelledomaine2': 'libelle_domaine_2',
        'dureeresidenceexigee': 'duree_residence_exigee',
        'dateapourvoir': 'date_a_pourvoir',
        'libelleposteapourvoir': 'date_a_pourvoir_libelle',
        'libelledirection': 'direction_libelle',
        'acronymedirection': 'direction_acronyme',
        'libelleservice': 'service_libelle',
        'lieutravail': 'lieu_travail',
        'datecreation': 'date_creation',
        'datecloture': 'date_cloture',
        'emploiresp': 'emploi_resp',
        'activitesprincipales': 'activites_principales',
        'activitessecondaires': 'activites_secondaires',
        'conditionsparticulieres': 'conditions_particulieres',
        'savoirfaire': 'savoir_faire',
        'commentairerepublication': 'commentaire_republication',
        'contacttelephone': 'contact_telephone',
        'contactemail': 'contact_email',
        'contactsecondaire': 'contact_secondaire',
        'contactsecondairetelephone': 'contact_secondaire_telephone',
        'contactsecondaireemail': 'contact_secondaire_email',
        'nbposteapourvoir': 'nb_postes_a_pourvoir',
        'apourvoirautre': 'a_pourvoir_autre',
        'collectivitenomrh': 'collectivite_nom_rh',
        'collectiviteadressedepot': 'collectivite_adresse_depot',
        'collectiviteadressepostale': 'collectivite_adresse_postale',
        'collectiviteemail': 'collectivite_email'
    }
    
    df_all.rename(columns={k: v for k, v in renames.items() if k in df_all.columns}, inplace=True)
    
    # On génère le CSV et l'index AVANT le traitement long des PDFs
    os.makedirs("docs", exist_ok=True)
    print("Enregistrement de docs/all_avps.csv...")
    df_all.to_csv("docs/all_avps.csv", index=False, encoding='utf-8')
    
    generate_index_md(df_all)
    generate_zensical_config()
    
    # Nettoyage des fichiers MD qui ne sont plus dans le CSV
    clean_orphaned_markdowns(df_all, data_dir="docs")
    
    # Traitement des PDFs (plus long)
    process_pdfs_to_markdown(df_all)
    
    print(f"Terminé. {len(df_all)} lignes traitées.")

def get_icon(domaine):
    icons = {"Informatique": "💻", "Numérique": "🌐", "Santé": "🏥", "Infirmier": "💉", "Équipement": "🏗️", "Environnement": "🌱", "Administration": "📁", "Enseignement": "🎓", "Rural": "🌾", "Météo": "☁️", "Social": "🤝"}
    dom_str = str(domaine).lower()
    for key, icon in icons.items():
        if key.lower() in dom_str: return icon
    return "📋"

def slugify(text):
    """Génère un slug propre pour les ancres Markdown."""
    text = unicodedata.normalize('NFD', str(text))
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn']) # Supprime les accents
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text)

def generate_index_md(df):
    print("Génération de index.md...")
    df['libelle_domaine'] = df['libelle_domaine'].fillna('Autres filières')
    df_sorted = df.sort_values(['libelle_domaine', 'date_mis_en_ligne'], ascending=[True, False])
    
    md_content = "---\nhide:\n  - toc\n---\n\n"
    md_content += "# 📢 Avis de Vacances de Poste (DRHFPNC)\n\n"
    md_content += f"Dernière mise à jour : **{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}**\n\n"

    md_content += "## 📂 Sommaire par domaines\n\n"
    for domaine in sorted(df['libelle_domaine'].unique()):
        icon = get_icon(domaine)
        count = len(df[df['libelle_domaine'] == domaine])
        anchor = slugify(domaine)
        md_content += f"* [{icon} {domaine} ({count})](#{anchor})\n"
    md_content += "\n---\n\n"

    for domaine, group in df_sorted.groupby('libelle_domaine'):
        icon = get_icon(domaine)
        anchor = slugify(domaine)
        # On force l'ID du titre pour que l'ancre corresponde exactement
        md_content += f"## {icon} {domaine} ({len(group)}) {{: #{anchor} }}\n\n"
        md_content += "| Référence | Poste | Direction | Date Limite |\n"
        md_content += "| --- | --- | --- | --- |\n"
        for _, row in group.iterrows():
            numero = str(row.get('numero', '')).replace("/", "_")
            libelle = row.get('libelle_poste', 'Poste sans titre')
            direction = row.get('direction_acronyme', row.get('direction_libelle', '-'))
            date_cloture_str = str(row.get('date_cloture', '-'))
            
            # Calcul des badges
            badges = ""
            now = pd.Timestamp.now()
            
            # Badge Nouveau (moins de 3 jours)
            try:
                date_pub = pd.to_datetime(row.get('date_mis_en_ligne'))
                if (now - date_pub).days <= 3:
                    badges += ' <span style="background-color: #43a047; color: white; padding: 2px 9px; border-radius: 12px; font-size: 0.7em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 8px; vertical-align: middle; white-space: nowrap;">✨ Nouveau</span>'
            except: pass

            # Badge Urgence / Délai (3 niveaux)
            try:
                date_limite = pd.to_datetime(row.get('date_cloture'))
                days_left = (date_limite - now).days
                
                if 0 <= days_left <= 2:
                    color = "#e53935" # Rouge
                    label = "🔥 Urgent"
                elif 3 <= days_left <= 7:
                    color = "#fb8c00" # Orange
                    label = "⏳ Cette semaine"
                else:
                    color = "#1e88e5" # Bleu
                    label = "📋 En cours"
                
                badges += f' <span style="background-color: {color}; color: white; padding: 2px 9px; border-radius: 12px; font-size: 0.7em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 8px; vertical-align: middle; white-space: nowrap;">{label}</span>'
            except: pass

            md_content += f"| {numero} | [{libelle}]({numero}/){badges} | {direction} | {date_cloture_str} |\n"
        md_content += "\n"
    
    with open("docs/index.md", "w", encoding="utf-8") as f:
        f.write(md_content)

def clean_orphaned_markdowns(df, data_dir="docs"):
    """Supprime les fichiers .md dans docs/ qui ne sont pas dans le DataFrame (sauf index.md)."""
    print("Nettoyage des fichiers Markdown orphelins...")
    valid_numbers = set(str(n).replace("/", "_") for n in df['numero'].unique())
    
    for file_path in glob(os.path.join(data_dir, "*.md")):
        base_name = os.path.basename(file_path).replace(".md", "")
        if base_name != "index" and base_name not in valid_numbers:
            print(f"  Suppression de {file_path} (non référencé)")
            os.remove(file_path)

def generate_zensical_config():
    config = """[project]
site_name = "AVPS DRHFPNC"
site_description = "Catalogue complet des AVPs de la DRHFPNC"
site_url = "https://adriens.github.io/avps/"
repo_url = "https://github.com/adriens/avps"
repo_name = "adriens/avps"
docs_dir = "docs"
site_dir = "site"

[project.theme]
name = "material"
language = "fr"
features = ["navigation.top", "navigation.tracking", "navigation.footer", "navigation.sections", "search.suggest", "search.highlight"]

# Mode sombre par défaut (Slate en premier)
[[project.theme.palette]]
scheme = "slate"
primary = "indigo"
accent = "indigo"
toggle.icon = "material/brightness-4"
toggle.name = "Passer au mode clair"

[[project.theme.palette]]
scheme = "default"
primary = "indigo"
accent = "indigo"
toggle.icon = "material/brightness-7"
toggle.name = "Passer au mode sombre"

[project.extra]
copyright = \"\"\"
Copyright &copy; 2026 adriens<br>
<small>Propulsé par <a href='https://github.com/opt-nc/zensical' target='_blank'>Zensical</a></small>
\"\"\"
"""
    with open("zensical.toml", "w", encoding="utf-8") as f:
        f.write(config)

if __name__ == "__main__":
    main()
