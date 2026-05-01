import os
import glob
import re

def generate_catalog():
    docs_dir = "docs"
    # Dossier d'export pour ne pas polluer le site Zensical
    output_dir = "exports"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "avp_catalog.md")
    
    # On récupère tous les AVP (fichiers commençant par 25- ou 26-)
    avp_files = sorted(glob.glob(os.path.join(docs_dir, "[0-9][0-9]-*.md")))
    
    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write("# 📚 Catalogue Complet des Avis de Vacances de Poste (AVP)\n\n")
        outfile.write(f"Ce document regroupe {len(avp_files)} offres extraites de la DRHFPNC.\n\n")
        
        for filepath in avp_files:
            with open(filepath, "r", encoding="utf-8") as infile:
                content = infile.read()
                
                # Suppression du frontmatter YAML (tout ce qui est entre les premiers ---)
                clean_content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
                
                outfile.write(clean_content)
                outfile.write("\n\n---\n\n") # Séparateur horizontal entre les offres
                
    print(f"✅ Catalogue généré dans : {output_file} ({len(avp_files)} offres)")

if __name__ == "__main__":
    generate_catalog()
