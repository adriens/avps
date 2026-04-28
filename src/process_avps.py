import pandas as pd
import requests
import io
import json
import os
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

def process_pdfs_to_markdown(df, data_dir="data"):
    """Télécharge les PDFs et les convertit en Markdown avec marker-pdf."""
    print("Début de la conversion des PDFs en Markdown avec marker-pdf...")
    
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import save_output
        
        print("  Chargement des modèles d'IA...")
        model_dict = create_model_dict()
        converter = PdfConverter(
            artifact_dict=model_dict,
            config={
                "disable_ocr": True,
                "disable_image_extraction": False
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
            
        # On évite de retraiter ce qui existe déjà pour gagner du temps
        if os.path.exists(final_md_path):
            print(f"  [{i}/{total}] {numero} déjà traité, on passe.")
            continue

        try:
            print(f"  [{i}/{total}] Traitement de {numero}...")
            # 1. Téléchargement du PDF
            pdf_response = requests.get(url_pdf)
            pdf_response.raise_for_status()
            
            temp_pdf = f"temp_{numero}.pdf"
            with open(temp_pdf, "wb") as f:
                f.write(pdf_response.content)
            
            # 2. Conversion avec marker
            rendered = converter(temp_pdf)
            
            # 3. Sauvegarde
            save_output(rendered, output_dir=data_dir, fname_base=numero)
            
            # 4. Ajout du lien PDF original
            if os.path.exists(final_md_path):
                with open(final_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pdf_header = f'<div style="text-align: right; margin-bottom: 1em;"><a href="{url_pdf}" target="_blank" style="display: inline-block; padding: 8px 16px; background-color: #3f51b5; color: white; text-decoration: none; border-radius: 4px;">📄 Télécharger le PDF original</a></div>\n\n'
                with open(final_md_path, 'w', encoding='utf-8') as f:
                    f.write(pdf_header + content)
            
            # Nettoyage
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            print(f"    Généré : {final_md_path}")
                
        except Exception as e:
            print(f"    Erreur pour {numero}: {e}")
            if 'temp_pdf' in locals() and os.path.exists(temp_pdf):
                os.remove(temp_pdf)

    # Nettoyage des fichiers JSON de métadonnées générés par marker
    all_json_files = glob(os.path.join(data_dir, "*_meta.json"))
    for json_file in all_json_files:
        os.remove(json_file)

def main():
    url = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/avis-de-vacances-de-poste-avp-drhfpnc/exports/parquet?lang=fr&timezone=Pacific%2FNoumea"
    
    print(f"Téléchargement des données depuis {url}...")
    response = requests.get(url)
    response.raise_for_status()
    
    df = pd.read_parquet(io.BytesIO(response.content))
    
    # On ne filtre QUE sur la présence d'un PDF
    col_pdf = 'url_pdf'
    df_all = df[df[col_pdf].notna()].copy()
    
    # LIMITATION POUR TEST : On ne prend que les 5 premières lignes
    print("⚠️ MODE TEST : Limitation aux 5 premières annonces.")
    df_all = df_all.head(5)

    total = len(df_all)
    print(f"Nombre d'AVPs à traiter : {total}")

    # Extraction des URLs PDF
    df_all['url_pdf'] = df_all['url_pdf'].apply(extract_pdf_url)

    # Renommage des colonnes (même mapping que l'original pour la cohérence)
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
    
    # Conversion PDF -> Markdown
    process_pdfs_to_markdown(df_all)
    
    # Sauvegarde du CSV global
    os.makedirs("data", exist_ok=True)
    output_path = "data/all_avps.csv"
    df_all.to_csv(output_path, index=False, encoding='utf-8')
    
    # Génération de l'index.md par domaine
    generate_index_md(df_all)
    
    # Génération de la config Zensical
    generate_zensical_config()
    
    print(f"Terminé. {len(df_all)} lignes enregistrées dans {output_path}.")

def get_icon(domaine):
    """Retourne une icône selon le domaine."""
    icons = {
        "Informatique": "💻",
        "Numérique": "🌐",
        "Santé": "🏥",
        "Infirmier": "💉",
        "Équipement": "🏗️",
        "Environnement": "🌱",
        "Administration": "📁",
        "Enseignement": "🎓",
        "Rural": "🌾",
        "Météo": "☁️",
        "Social": "🤝"
    }
    dom_str = str(domaine).lower()
    for key, icon in icons.items():
        if key.lower() in dom_str:
            return icon
    return "📋"

def generate_index_md(df):
    """Génère un fichier index.md classé par domaine avec des tableaux dédiés."""
    print("Génération de index.md par domaine...")
    
    # Remplissage des domaines vides
    df['libelle_domaine'] = df['libelle_domaine'].fillna('Autres filières')
    
    # Tri par domaine puis par date de mise en ligne
    df_sorted = df.sort_values(['libelle_domaine', 'date_mis_en_ligne'], ascending=[True, False])
    
    md_content = "# 📢 Avis de Vacances de Poste (DRHFPNC)\n\n"
    md_content += "Bienvenue sur le catalogue complet des AVPs. Ce site est mis à jour quotidiennement.\n\n"
    md_content += f"Dernière mise à jour : **{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}**  \n"
    md_content += f"Nombre de postes ouverts : **{len(df)}**\n\n"

    # Navigation rapide (Sommaire)
    md_content += "## 📂 Sommaire par domaines\n\n"
    for domaine in sorted(df['libelle_domaine'].unique()):
        icon = get_icon(domaine)
        count = len(df[df['libelle_domaine'] == domaine])
        anchor = str(domaine).lower().replace(" ", "-").replace("é", "e").replace("è", "e")
        md_content += f"* [{icon} {domaine} ({count})](#{anchor})\n"
    md_content += "\n---\n\n"

    # Groupement par domaine
    for domaine, group in df_sorted.groupby('libelle_domaine'):
        icon = get_icon(domaine)
        anchor = str(domaine).lower().replace(" ", "-").replace("é", "e").replace("è", "e")
        md_content += f"## {icon} {domaine} ({len(group)})\n\n"
        md_content += "| Référence | Poste | Direction | Date Limite |\n"
        md_content += "| --- | --- | --- | --- |\n"
        
        for _, row in group.iterrows():
            numero = str(row.get('numero', '')).replace("/", "_")
            libelle = row.get('libelle_poste', 'Poste sans titre')
            direction = row.get('direction_acronyme', row.get('direction_libelle', '-'))
            date_cloture = row.get('date_cloture', '-')
            
            try:
                if pd.notna(date_cloture):
                    date_cloture = pd.to_datetime(date_cloture).strftime('%d/%m/%Y')
            except:
                pass

            md_content += f"| {numero} | [{libelle}]({numero}.md) | {direction} | {date_cloture} |\n"
        md_content += "\n"
    
    with open("data/index.md", "w", encoding="utf-8") as f:
        f.write(md_content)

def generate_zensical_config():
    """Génère un fichier zensical.toml avec le mode sombre par défaut."""
    config = """# Configuration Zensical
title = "AVPS DRHFPNC"
description = "Catalogue complet des AVPs de la DRHFPNC"
source_dir = "data"
output_dir = "site"

[theme]
name = "material"
default_mode = "dark"
primary_color = "#3f51b5"
accent_color = "#ff4081"

[navigation]
show_reading_time = false
show_last_updated = true
"""
    with open("zensical.toml", "w", encoding="utf-8") as f:
        f.write(config)
    print("✅ Configuration Zensical (Dark Mode) générée.")

if __name__ == "__main__":
    main()
