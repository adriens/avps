import pandas as pd
import requests
import io
import json
import os
import unicodedata
import re
import datetime
from glob import glob

# Configuration CPU pour marker
os.environ["TORCH_DEVICE"] = "cpu"
os.environ["INFERENCE_DEVICE"] = "cpu"


def safe_value(value, default):
    """Retourne `default` si value est None ou NaN (pandas), sinon value."""
    if value is None:
        return default
    if isinstance(value, float):
        try:
            if pd.isna(value):
                return default
        except Exception:
            pass
    return value


def safe_get(row, key, default=''):
    """Comme row.get(key, default) mais traite NaN comme une absence."""
    return safe_value(row.get(key), default)

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

def generate_jsonld_jobposting(row, numero, commune=None):
    """Génère un bloc JSON-LD JobPosting en commentaire HTML."""
    import json
    
    # Construction de l'adresse enrichie si commune détectée
    address = {
        "@type": "PostalAddress",
        "addressCountry": "NC",
        "addressRegion": "Nouvelle-Calédonie"
    }
    job_location = {
        "@type": "Place",
        "address": address
    }
    if commune:
        address["addressLocality"] = commune['name']
        address["addressRegion"] = commune['province']
        job_location["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": commune['lat'],
            "longitude": commune['lon']
        }
    
    # Données du JobPosting
    job_posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": f"{safe_get(row, 'numero', numero)} - {safe_get(row, 'libelle_poste', 'Poste disponible')}",
        "description": f"Domaine: {safe_get(row, 'libelle_domaine', 'Autres')}. Direction: {safe_get(row, 'direction_libelle', safe_get(row, 'direction_acronyme', 'DRHFPNC'))}",
        "hiringOrganization": {
            "@type": "Organization",
            "name": safe_get(row, 'direction_libelle', safe_get(row, 'direction_acronyme', 'DRHFPNC')),
            "sameAs": "https://www.gouv.nc/"
        },
        "jobLocation": job_location,
        "url": f"https://adriens.github.io/avps/{numero}/",
        "datePosted": str(safe_get(row, 'date_mis_en_ligne', pd.Timestamp.now()))[:10],
        "validThrough": str(safe_get(row, 'date_cloture', pd.Timestamp.now()))[:10],
        "employmentType": "FullTime"
    }
    
    # Convertir en JSON indentado
    jsonld_str = json.dumps(job_posting, ensure_ascii=False, indent=2)
    
    # Retourner en commentaire HTML
    return f"<!--\n<script type=\"application/ld+json\">\n{jsonld_str}\n</script>\n-->\n\n"

# Dictionnaire des abréviations courantes utilisées par la DRHFPNC
ABBREVIATIONS = {
    'DRHFPNC': "Direction des Ressources Humaines de la Fonction Publique de Nouvelle-Calédonie",
    'DPASS': "Direction Provinciale de l'Action Sanitaire et Sociale",
    'UPASS': "Unité Provinciale d'Action Sanitaire et Sociale",
    'DAFE': "Direction de l'Administration et des Finances de l'État",
    'DENC': "Direction de l'Enseignement de la Nouvelle-Calédonie",
    'DAVAR': "Direction des Affaires Vétérinaires, Alimentaires et Rurales",
    'DTSI': "Direction des Technologies et des Services de l'Information",
    'IRD': "Institut de Recherche pour le Développement",
    'IFAP': "Institut de Formation des Acteurs Publics",
    'CHT': "Centre Hospitalier Territorial",
    'CHN': "Centre Hospitalier du Nord",
    'CHS': "Centre Hospitalier Spécialisé",
    'OPT': "Office des Postes et Télécommunications",
    'CAFAT': "Caisse de Compensation des Prestations Familiales, des Accidents du Travail et de Prévoyance des Travailleurs",
    'IEOM': "Institut d'Émission d'Outre-Mer",
    'ADRAF': "Agence de Développement Rural et d'Aménagement Foncier",
    'MPRH': "Mission Politique de Ressources Humaines",
    'AVP': "Avis de Vacance de Poste",
    'PMI': "Protection Maternelle et Infantile",
    'IVG': "Interruption Volontaire de Grossesse",
    'IST': "Infections Sexuellement Transmissibles",
    'CDI': "Contrat à Durée Indéterminée",
    'CDD': "Contrat à Durée Déterminée",
    'BAFA': "Brevet d'Aptitude aux Fonctions d'Animateur",
    'BAFD': "Brevet d'Aptitude aux Fonctions de Directeur",
    'DEUST': "Diplôme d'Études Universitaires Scientifiques et Techniques",
    'DUT': "Diplôme Universitaire de Technologie",
    'BTS': "Brevet de Technicien Supérieur",
    'CAP': "Certificat d'Aptitude Professionnelle",
    'BEP': "Brevet d'Études Professionnelles",
    'DESS': "Diplôme d'Études Supérieures Spécialisées",
    'DEA': "Diplôme d'Études Approfondies",
    'NC': "Nouvelle-Calédonie",
    'PS': "Province Sud",
    'PN': "Province Nord",
    'PIL': "Province des Îles Loyauté",
    'RH': "Ressources Humaines",
    'GRH': "Gestion des Ressources Humaines",
    'GPEC': "Gestion Prévisionnelle des Emplois et des Compétences",
    'SIRH': "Système d'Information de Gestion des Ressources Humaines",
    'TIC': "Technologies de l'Information et de la Communication",
    'NTIC': "Nouvelles Technologies de l'Information et de la Communication",
    'HSE': "Hygiène, Sécurité et Environnement",
    'QSE': "Qualité, Sécurité, Environnement",
    'QHSE': "Qualité, Hygiène, Sécurité, Environnement",
}


# ---------------------------------------------------------------------------
# Normalisation des dates au format ISO 8601 (YYYY-MM-DD)
# ---------------------------------------------------------------------------

MONTHS_FR = {
    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'aout': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11,
    'décembre': 12, 'decembre': 12,
}

# 1) Dates textuelles : "15 mai 2026", "1er juin 2026"
PATTERN_DATE_TEXT = re.compile(
    r'\b(\d{1,2})(?:er)?\s+'
    r'(janvier|février|fevrier|mars|avril|mai|juin|juillet|'
    r'août|aout|septembre|octobre|novembre|décembre|decembre)\s+'
    r'(\d{4})\b',
    re.IGNORECASE,
)

# 2) Dates numériques : 15/05/2026, 15.05.2026, 15-05-2026
#    Backreference \2 force le même séparateur ; année à 4 chiffres obligatoire
PATTERN_DATE_NUMERIC = re.compile(
    r'(?<![\d\w/.\-])'
    r'(\d{1,2})([/.\-])(\d{1,2})\2(\d{4})'
    r'(?![\d\w/.\-])'
)

# 3) Placeholder pour protéger les dates déjà au format ISO
PATTERN_ISO = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')


def _to_iso(year, month, day):
    """Tente de construire une date valide. Retourne None si invalide."""
    try:
        return datetime.date(int(year), int(month), int(day)).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def _replace_text_date(match):
    day, month_name, year = match.group(1), match.group(2).lower(), match.group(3)
    month = MONTHS_FR.get(month_name)
    if month is None:
        return match.group(0)
    iso = _to_iso(year, month, day)
    return iso if iso else match.group(0)


def _replace_numeric_date(match):
    day, _sep, month, year = match.group(1), match.group(2), match.group(3), match.group(4)
    iso = _to_iso(year, month, day)
    return iso if iso else match.group(0)


def normalize_dates(content):
    """Convertit toutes les dates détectées en YYYY-MM-DD (ISO 8601).

    Stratégie :
      0. Protège les dates déjà ISO (idempotence).
      1. Convertit les dates textuelles (« 15 mai 2026 »).
      2. Convertit les dates numériques avec séparateurs identiques.
      3. Restaure les placeholders.
      Chaque conversion valide la date via datetime.date ; en cas d'invalidité
      le texte original est conservé.
    """
    placeholders = []

    def _save_iso(m):
        placeholders.append(m.group(0))
        return f'__ISODATE_{len(placeholders) - 1}__'

    content = PATTERN_ISO.sub(_save_iso, content)
    content = PATTERN_DATE_TEXT.sub(_replace_text_date, content)
    content = PATTERN_DATE_NUMERIC.sub(_replace_numeric_date, content)

    for i, original in enumerate(placeholders):
        content = content.replace(f'__ISODATE_{i}__', original)

    return content


def add_abbreviations(content):
    """Détecte les abréviations présentes et ajoute leurs définitions en bas du markdown.

    Material/Zensical convertit ces définitions en tooltips <abbr> au survol.
    """
    abbr_section = []
    for abbr, definition in ABBREVIATIONS.items():
        if re.search(rf'\b{re.escape(abbr)}\b', content):
            abbr_section.append(f"*[{abbr}]: {definition}")

    if abbr_section:
        content = content.rstrip() + "\n\n" + "\n".join(abbr_section) + "\n"

    return content


# ---------------------------------------------------------------------------
# Détection des communes de Nouvelle-Calédonie (gazetteer)
# ---------------------------------------------------------------------------
# Liste officielle des 33 communes avec province, coordonnées GPS et variantes
# orthographiques courantes (sans accents, alternatives).
COMMUNES_NC = {
    # --- Province Sud (14 communes) ---
    'Nouméa':       {'province': 'Province Sud', 'lat': -22.2758, 'lon': 166.4580, 'aliases': ['Noumea']},
    'Mont-Dore':    {'province': 'Province Sud', 'lat': -22.2333, 'lon': 166.5833, 'aliases': ['Mont Dore', 'le Mont-Dore']},
    'Dumbéa':       {'province': 'Province Sud', 'lat': -22.1500, 'lon': 166.4500, 'aliases': ['Dumbea']},
    'Païta':        {'province': 'Province Sud', 'lat': -22.1333, 'lon': 166.3500, 'aliases': ['Paita']},
    'Bourail':      {'province': 'Province Sud', 'lat': -21.5667, 'lon': 165.5000, 'aliases': []},
    'Boulouparis':  {'province': 'Province Sud', 'lat': -21.8667, 'lon': 166.0500, 'aliases': []},
    'Farino':       {'province': 'Province Sud', 'lat': -21.6667, 'lon': 165.7833, 'aliases': []},
    'La Foa':       {'province': 'Province Sud', 'lat': -21.7167, 'lon': 165.8333, 'aliases': ['Foa']},
    'Moindou':      {'province': 'Province Sud', 'lat': -21.6833, 'lon': 165.6833, 'aliases': []},
    'Sarraméa':     {'province': 'Province Sud', 'lat': -21.6333, 'lon': 165.8500, 'aliases': ['Sarramea']},
    'Thio':         {'province': 'Province Sud', 'lat': -21.6167, 'lon': 166.2167, 'aliases': []},
    'Yaté':         {'province': 'Province Sud', 'lat': -22.1500, 'lon': 166.9500, 'aliases': ['Yate']},
    'Île-des-Pins': {'province': 'Province Sud', 'lat': -22.6167, 'lon': 167.4833, 'aliases': ['Ile des Pins', 'Île des Pins', 'Vao']},
    'Poya':         {'province': 'Province Sud', 'lat': -21.3500, 'lon': 165.1333, 'aliases': []},

    # --- Province Nord (17 communes) ---
    'Koné':         {'province': 'Province Nord', 'lat': -21.0667, 'lon': 164.8500, 'aliases': ['Kone']},
    'Koumac':       {'province': 'Province Nord', 'lat': -20.5667, 'lon': 164.2833, 'aliases': []},
    'Pouembout':    {'province': 'Province Nord', 'lat': -21.1333, 'lon': 164.8833, 'aliases': []},
    'Voh':          {'province': 'Province Nord', 'lat': -20.9500, 'lon': 164.6833, 'aliases': []},
    'Kaala-Gomen':  {'province': 'Province Nord', 'lat': -20.6167, 'lon': 164.4000, 'aliases': ['Kaala Gomen']},
    'Ouégoa':       {'province': 'Province Nord', 'lat': -20.3500, 'lon': 164.4333, 'aliases': ['Ouegoa']},
    'Pouébo':       {'province': 'Province Nord', 'lat': -20.4000, 'lon': 164.5833, 'aliases': ['Pouebo']},
    'Hienghène':    {'province': 'Province Nord', 'lat': -20.6833, 'lon': 164.9333, 'aliases': ['Hienghene']},
    'Touho':        {'province': 'Province Nord', 'lat': -20.7833, 'lon': 165.2333, 'aliases': []},
    'Poindimié':    {'province': 'Province Nord', 'lat': -20.9333, 'lon': 165.3333, 'aliases': ['Poindimie']},
    'Ponérihouen':  {'province': 'Province Nord', 'lat': -21.0833, 'lon': 165.4167, 'aliases': ['Ponerihouen']},
    'Houaïlou':     {'province': 'Province Nord', 'lat': -21.2833, 'lon': 165.6333, 'aliases': ['Houailou']},
    'Kouaoua':      {'province': 'Province Nord', 'lat': -21.4000, 'lon': 165.8333, 'aliases': []},
    'Canala':       {'province': 'Province Nord', 'lat': -21.5333, 'lon': 165.9667, 'aliases': []},
    'Belep':        {'province': 'Province Nord', 'lat': -19.7167, 'lon': 163.6500, 'aliases': []},
    'Poum':         {'province': 'Province Nord', 'lat': -20.2333, 'lon': 164.0167, 'aliases': []},
    'Ouaco':        {'province': 'Province Nord', 'lat': -20.8333, 'lon': 164.5167, 'aliases': []},

    # --- Province des Îles Loyauté (3 communes) ---
    'Lifou':        {'province': 'Province des Îles Loyauté', 'lat': -20.9000, 'lon': 167.2500, 'aliases': ['Wé', 'We']},
    'Maré':         {'province': 'Province des Îles Loyauté', 'lat': -21.5000, 'lon': 168.0333, 'aliases': ['Mare', 'Tadine']},
    'Ouvéa':        {'province': 'Province des Îles Loyauté', 'lat': -20.5500, 'lon': 166.5833, 'aliases': ['Ouvea', 'Fayaoué', 'Fayaoue']},
}

# Patterns de contexte qui boostent la confiance ("lieu de travail : ...")
LOCATION_CONTEXT_PATTERN = re.compile(
    r'(?i)(?:lieu de travail|affectation|résidence administrative|'
    r'r[ée]sidence|bas[ée]\s+à|situ[ée]\s+à|poste\s+bas[ée]\s+à)\s*:?\s*([^\n]{0,200})'
)


def detect_communes(content):
    """Détecte les communes NC mentionnées dans le markdown.

    Stratégie en deux passes :
      1. Recherche dans les sections de contexte (lieu de travail, affectation)
         pour identifier la commune principale avec haute confiance.
      2. Recherche globale pour collecter toutes les communes mentionnées.

    Retourne (commune_principale, liste_communes_mentionnées).
    Chaque entrée est un dict avec name, province, lat, lon.
    """
    # Construit la liste de tous les libellés à chercher (canonique + aliases)
    candidates = []
    for canonical, info in COMMUNES_NC.items():
        for label in [canonical] + info['aliases']:
            candidates.append((label, canonical))
    # Tri par longueur décroissante : matche les variantes longues en premier
    # (ex: "Mont-Dore" avant "Mont")
    candidates.sort(key=lambda x: -len(x[0]))

    def _find_in(text):
        found = []
        for label, canonical in candidates:
            m = re.search(rf'\b{re.escape(label)}\b', text)
            if m and canonical not in [f['name'] for f in found]:
                info = COMMUNES_NC[canonical]
                found.append({
                    'name': canonical,
                    'province': info['province'],
                    'lat': info['lat'],
                    'lon': info['lon'],
                    '_pos': m.start(),
                })
        # Tri par position d'apparition dans le texte
        found.sort(key=lambda x: x['_pos'])
        for f in found:
            f.pop('_pos', None)
        return found

    # Passe 1 : commune principale via contexte
    primary = None
    for ctx_match in LOCATION_CONTEXT_PATTERN.finditer(content):
        ctx_text = ctx_match.group(1)
        ctx_communes = _find_in(ctx_text)
        if ctx_communes:
            primary = ctx_communes[0]
            break

    # Passe 2 : toutes les communes mentionnées
    all_communes = _find_in(content)

    # Si pas de primaire trouvée par contexte, prendre la première mentionnée
    if primary is None and all_communes:
        primary = all_communes[0]

    return primary, all_communes



def format_contacts(content):
    """Détecte emails et numéros de téléphone et les rend cliquables."""
    
    # Système de placeholders pour protéger les liens déjà créés
    placeholders = []
    
    def save_link(match):
        placeholders.append(match.group(0))
        return f'__LINK_PLACEHOLDER_{len(placeholders)-1}__'
    
    # 0. Sauvegarder les liens markdown existants pour ne pas les re-matcher
    content = re.sub(r'\[[^\]]+\]\([^\)]+\)', save_link, content)
    
    # 1. Emails : détection et transformation en lien mailto:
    content = re.sub(
        r'\b([\w\.\-]+@[\w\.\-]+\.\w{2,})\b',
        r'[✉️ \1](mailto:\1)',
        content
    )
    # Sauvegarder les nouveaux liens email
    content = re.sub(r'\[✉️[^\]]+\]\([^\)]+\)', save_link, content)
    
    # 2. Téléphones - fonction de formatage
    def format_phone(match):
        phone = match.group(1)
        # Nettoyer pour le lien tel: (garder + et chiffres)
        digits = re.sub(r'[^\d+]', '', phone)
        return f'[📞 {phone}](tel:{digits})'
    
    # 2a. +687 NC international (en premier pour éviter conflits)
    content = re.sub(
        r'(\+687[\s\.\-]?\d{2}[\s\.\-]?\d{2}[\s\.\-]?\d{2})',
        format_phone,
        content
    )
    # Sauvegarder ces nouveaux liens
    content = re.sub(r'\[📞[^\]]+\]\([^\)]+\)', save_link, content)
    
    # 2b. France 10 chiffres (0X.XX.XX.XX.XX) - avant NC pour éviter conflits
    content = re.sub(
        r'\b(0\d[\.\s\-]\d{2}[\.\s\-]\d{2}[\.\s\-]\d{2}[\.\s\-]\d{2})\b',
        format_phone,
        content
    )
    content = re.sub(r'\[📞[^\]]+\]\([^\)]+\)', save_link, content)
    
    # 2c. NC 6 chiffres avec séparateurs (XX.XX.XX, XX XX XX)
    # Lookahead/lookbehind pour éviter les dates et références
    content = re.sub(
        r'(?<![\d\.\-])\b(\d{2}[\.\s\-]\d{2}[\.\s\-]\d{2})\b(?![\.\d\-])',
        format_phone,
        content
    )
    
    # 3. Restaurer tous les placeholders
    for i, link in enumerate(placeholders):
        content = content.replace(f'__LINK_PLACEHOLDER_{i}__', link)
    
    return content

def post_process_markdown(content, row, numero):
    """Post-traitement du markdown : ajoute blocs rapides et nettoie le contenu."""
    import html
    
    # 1. Nettoyer les caractères spéciaux (HTML entities)
    content = html.unescape(content)
    # Supprimer les &nbsp; restants
    content = content.replace('&nbsp;', ' ')
    
    # 2. AMÉLIORATION 1 : Nettoyer les sauts de ligne excessifs
    # Remplacer 4+ sauts de ligne par 2 sauts de ligne
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    # 2.5. Détecter et formatter les contacts (emails et téléphones)
    content = format_contacts(content)

    # 2.6. Normaliser toutes les dates au format ISO 8601 (YYYY-MM-DD)
    content = normalize_dates(content)
    
    # 3. AMÉLIORATION 4 : Détecter et formatter les sections clés
    # Patterns courants dans les annonces (case-insensitive)
    sections_patterns = [
        (r'(?i)^(\*{0,3}\s*)?missions?\s*:', '## 🎯 Missions'),
        (r'(?i)^(\*{0,3}\s*)?activit[ée]s?\s*:', '## 📋 Activités'),
        (r'(?i)^(\*{0,3}\s*)?qualifications?\s*:', '## 🎓 Qualifications'),
        (r'(?i)^(\*{0,3}\s*)?comp[ée]tences?\s*:', '## 💼 Compétences'),
        (r'(?i)^(\*{0,3}\s*)?profil\s*:', '## 👤 Profil'),
        (r'(?i)^(\*{0,3}\s*)?savoir[- ]faire\s*:', '## 🛠️ Savoir-faire'),
        (r'(?i)^(\*{0,3}\s*)?exp[ée]rience?\s*:', '## 📚 Expérience'),
        (r'(?i)^(\*{0,3}\s*)?contact\s*:', '## 📞 Contact'),
        (r'(?i)^(\*{0,3}\s*)?employeur\s*:', '## 🏢 Employeur'),
        (r'(?i)^(\*{0,3}\s*)?lieu\s*:', '## 📍 Lieu'),
        (r'(?i)^(\*{0,3}\s*)?dur[ée]e?\s*:', '## ⏱️ Durée'),
        (r'(?i)^(\*{0,3}\s*)?r[ée]mun[ée]ration\s*:', '## 💰 Rémunération'),
    ]
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        matched = False
        for pattern, replacement in sections_patterns:
            if re.match(pattern, line):
                # Retirer le texte original et utiliser le replacement avec emoji
                new_lines.append(replacement)
                matched = True
                break
        
        if not matched:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)

    # 3.5 Nettoyer les titres de section
    # Supprimer les ** (le niveau de section suffit pour l'emphasis)
    content = re.sub(r'^(#{1,6}\s+)\*\*(.*)\*\*', r'\1\2', content, flags=re.MULTILINE)
    # Supprimer le dernier ':' en fin de ligne
    content = re.sub(r'^(#{1,6}\s+.+?):\s*$', r'\1', content, flags=re.MULTILINE)
    
    # 4. Extraire le contenu après le titre principal
    lines = content.split('\n')
    title_index = -1
    for i, line in enumerate(lines):
        if line.startswith('# ') or line.startswith('## '):
            title_index = i
            break
    
    # Construire le bloc "Candidature rapide"
    date_cloture = safe_get(row, 'date_cloture', '-')
    direction = safe_get(row, 'direction_acronyme', safe_get(row, 'direction_libelle', 'DRHFPNC'))
    domaine = safe_get(row, 'libelle_domaine', 'Autres')
    
    # Calcul du badge urgence
    urgence_badge = ""
    try:
        date_limite = pd.to_datetime(date_cloture)
        now = pd.Timestamp.now()
        days_left = (date_limite - now).days
        
        if 0 <= days_left <= 2:
            urgence_badge = "🔥 **Urgent** (≤2 jours)"
        elif 3 <= days_left <= 7:
            urgence_badge = "⏳ **Cette semaine** (≤7 jours)"
        else:
            urgence_badge = "📋 En cours"
    except:
        urgence_badge = "📋 En cours"
    
    candidature_bloc = f"""
!!! success "📋 Candidature rapide"
    **Date limite :** {date_cloture}  
    **Direction :** {direction}  
    **Domaine :** {domaine}  
    **Statut :** {urgence_badge}

"""
    
    # 5. Insérer le bloc après le titre
    if title_index >= 0:
        # Insérer après le titre (à l'index title_index + 1)
        lines.insert(title_index + 1, "")
        lines.insert(title_index + 2, candidature_bloc)
        content = '\n'.join(lines)
    
    # 6. Ajouter le bloc "Actions rapides" à la fin
    pdf_url = safe_get(row, 'url_pdf_original', '#')
    actions_bloc = f"""
---

## 🎯 Actions rapides

- 📄 [Télécharger le PDF original]({pdf_url})
- ← [Retour à l'index](./)
- 💼 [Autres offres en {domaine}](../#{ slugify(domaine)})
- 🏢 [Toutes les offres DRHFPNC](./?direction={direction.lower()})
"""
    content += actions_bloc

    # 6. Ajouter les définitions d'abréviations (tooltips Material/Zensical)
    content = add_abbreviations(content)

    return content

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
    
    # Nettoyer les MD qui n'ont plus d'URL PDF valide
    valid_numeros = set()
    for _, row in df.iterrows():
        url_pdf = safe_get(row, 'url_pdf', '')
        if url_pdf and url_pdf.startswith("http"):
            numero = str(row['numero']).replace("/", "_")
            valid_numeros.add(numero)
    
    # Supprimer les MD des offers qui n'ont plus d'URL PDF
    for existing_md in glob.glob(os.path.join(data_dir, "*.md")):
        if existing_md == os.path.join(data_dir, "index.md"):
            continue  # Garder index.md
        basename = os.path.basename(existing_md).replace(".md", "")
        if basename not in valid_numeros:
            print(f"  Suppression de {basename}.md (pas d'URL PDF valide)")
            os.remove(existing_md)
    
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        numero = str(row['numero']).replace("/", "_")
        url_pdf = safe_get(row, 'url_pdf', '')
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
            
            # Enrichissement du frontmatter et ajout du contenu
            if os.path.exists(final_md_path):
                with open(final_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Calcul du statut
                try:
                    date_cloture = pd.to_datetime(row.get('date_cloture'))
                    now = pd.Timestamp.now()
                    status = "fermé" if date_cloture < now else "ouvert"
                except:
                    status = "ouvert"
                
                # Post-traitement du contenu (blocs rapides + nettoyage)
                processed_content = post_process_markdown(content, row, numero)

                # Détection de la commune NC dans le contenu post-traité
                primary_commune, all_communes = detect_communes(processed_content)

                # Frontmatter enrichi YAML
                libelle_poste = safe_get(row, 'libelle_poste', 'Poste disponible')
                domaine = safe_get(row, 'libelle_domaine', 'Autres filières')
                direction = safe_get(row, 'direction_acronyme', safe_get(row, 'direction_libelle', '-'))
                date_cloture = safe_get(row, 'date_cloture', '-')
                date_publication = safe_get(row, 'date_mis_en_ligne', '-')

                header = f'---\n'
                header += f'numero: "{row["numero"]}"\n'
                header += f'domaine: "{domaine}"\n'
                header += f'direction: "{direction}"\n'
                header += f'date_cloture: "{date_cloture}"\n'
                header += f'date_publication: "{date_publication}"\n'
                header += f'status: "{status}"\n'
                header += f'url_pdf_original: "{url_pdf}"\n'
                if primary_commune:
                    header += f'ville: "{primary_commune["name"]}"\n'
                    header += f'province: "{primary_commune["province"]}"\n'
                    header += f'geo:\n'
                    header += f'  latitude: {primary_commune["lat"]}\n'
                    header += f'  longitude: {primary_commune["lon"]}\n'
                header += f'search:\n'
                header += f'  boost: 1.5\n'
                # OpenGraph + Twitter Cards
                header += f'og_title: "{row["numero"]} - {libelle_poste} | AVPS DRHFPNC"\n'
                header += f'og_description: "Direction: {direction} | Domaine: {domaine} | Clôture: {date_cloture}"\n'
                header += f'og_type: "article"\n'
                header += f'og_url: "https://adriens.github.io/avps/{numero}/"\n'
                header += f'twitter_card: "summary_large_image"\n'
                header += f'twitter_title: "{row["numero"]} - {libelle_poste}"\n'
                header += f'twitter_description: "AVPS DRHFPNC | {domaine} | {direction} | Clôture: {date_cloture}"\n'
                header += f'---\n\n'
                header += f'# {numero} - {libelle_poste}\n\n'
                header += f'<div style="text-align: right; margin-bottom: 1em;"><a href="{url_pdf}" target="_blank" style="display: inline-block; padding: 8px 16px; background-color: #3f51b5; color: white; text-decoration: none; border-radius: 4px;">📄 Télécharger le PDF original</a></div>\n\n'

                with open(final_md_path, 'w', encoding='utf-8') as f:
                    f.write(header + generate_jsonld_jobposting(row, numero, primary_commune) + processed_content)
            
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
    generate_rss_feed(df_all)
    generate_sitemap(df_all)
    generate_robots_txt()
    
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
    
    # Conversion en datetime pour un tri fiable
    df['date_cloture_dt'] = pd.to_datetime(df['date_cloture'], errors='coerce')
    df['date_mis_en_ligne_dt'] = pd.to_datetime(df['date_mis_en_ligne'], errors='coerce')
    
    # Tri : Domaine (A-Z), puis Clôture (Bientôt -> Loin), puis Publication (Récent -> Vieux)
    df_sorted = df.sort_values(
        ['libelle_domaine', 'date_cloture_dt', 'date_mis_en_ligne_dt'], 
        ascending=[True, True, False]
    )
    
    now = pd.Timestamp.now()
    total_count = len(df)
    urgent_count = len(df[pd.to_datetime(df['date_cloture'], errors='coerce') - now <= pd.Timedelta(days=2)])
    this_week_count = len(df[(pd.to_datetime(df['date_cloture'], errors='coerce') - now > pd.Timedelta(days=2)) & (pd.to_datetime(df['date_cloture'], errors='coerce') - now <= pd.Timedelta(days=7))])
    
    # Frontmatter YAML
    md_content = "---\n"
    md_content += 'description: "Catalogue complet et à jour des Avis de Vacances de Poste publiés par la DRHFPNC"\n'
    md_content += 'og_title: "Avis de Vacances de Poste DRHFPNC"\n'
    md_content += 'og_description: "Catalogue complet et à jour de toutes les offres d\'emploi publiées par la DRHFPNC. Nouvelle Calédonie."\n'
    md_content += 'og_type: "website"\n'
    md_content += 'og_url: "https://adriens.github.io/avps/"\n'
    md_content += 'twitter_card: "summary"\n'
    md_content += 'twitter_title: "AVPS DRHFPNC - Offres d\'emploi Nouvelle Calédonie"\n'
    md_content += 'twitter_description: "Découvrez les Avis de Vacances de Poste en cours de la DRHFPNC"\n'
    md_content += 'search:\n'
    md_content += '  boost: 1\n'
    md_content += '---\n\n'
    
    md_content += "# 📢 Avis de Vacances de Poste (DRHFPNC)\n\n"
    md_content += f"Dernière mise à jour : **{now.strftime('%d/%m/%Y %H:%M')}** (Nouvelle Calédonie)\n\n"

    # Blocs informatifs avec extension Material
    md_content += "!!! info \"Statistiques\"\n"
    md_content += f"    **{total_count}** offres disponibles — "
    md_content += f"**{urgent_count}** urgent (≤2j) — "
    md_content += f"**{this_week_count}** cette semaine\n\n"

    md_content += "## Sommaire par domaines\n\n"
    for domaine in sorted(df['libelle_domaine'].unique()):
        icon = get_icon(domaine)
        count = len(df[df['libelle_domaine'] == domaine])
        anchor = slugify(domaine)
        md_content += f"- [{icon} {domaine} ({count})](#{anchor})\n"
    md_content += "\n---\n\n"

    for domaine, group in df_sorted.groupby('libelle_domaine'):
        icon = get_icon(domaine)
        anchor = slugify(domaine)
        # Anchor compatible Zensical
        md_content += f"## {icon} {domaine} {{: #{anchor} }}\n\n"
        md_content += f"__{len(group)} offre{'s' if len(group) > 1 else ''}__\n\n"
        
        for _, row in group.iterrows():
            numero = str(row.get('numero', '')).replace("/", "_")
            libelle = safe_get(row, 'libelle_poste', 'Poste sans titre')
            direction = safe_get(row, 'direction_acronyme', safe_get(row, 'direction_libelle', '-'))
            date_cloture_str = str(safe_get(row, 'date_cloture', '-'))
            
            # Calcul du badge d'urgence (compact, épuré)
            urgence_badge = "🟢 EN COURS"
            try:
                date_limite = pd.to_datetime(row.get('date_cloture'))
                days_left = (date_limite - now).days
                
                if 0 <= days_left <= 2:
                    urgence_badge = "🔴 URGENT"
                elif 3 <= days_left <= 7:
                    urgence_badge = "🟠 CETTE SEMAINE"
            except:
                pass
            
            # Format : Numéro BADGE — Poste | Direction | Clôture
            md_content += f"- **{numero}** `{urgence_badge}` — [{libelle}]({numero}/) | {direction} | Clôture: {date_cloture_str}\n"
        
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
site_description = "Catalogue complet et à jour des Avis de Vacances de Poste publiés par la DRHFPNC"
site_url = "https://adriens.github.io/avps/"
repo_url = "https://github.com/adriens/avps"
repo_name = "adriens/avps"
docs_dir = "docs"
site_dir = "site"
nav = [
  { title = "Accueil", path = "index.md" }
]

[project.theme]
name = "material"
language = "fr"
features = [
  "navigation.top",
  "navigation.tracking", 
  "navigation.footer",
  "navigation.sections",
  "navigation.expand",
  "search.suggest",
  "search.highlight",
  "search.share",
  "content.code.copy",
  "content.tabs.link"
]
icon.repo = "material/github"

[project.theme.font]
text = "Roboto"
code = "Roboto Mono"

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

# Extensions Markdown pour Material/Zensical
[project.markdown]
extensions = [
  "tables",
  "toc",
  "abbr",
  "pymdownx.superfences",
  "pymdownx.tabbed",
  "pymdownx.emoji",
  "pymdownx.blocks.admonition",
  "pymdownx.blocks.details",
  "attr_list"
]

[project.markdown.extension_configs]
pymdownx.emoji = { emoji_index = "pymdownx.emoji.twemoji", emoji_generator = "pymdownx.emoji.to_svg" }
pymdownx.superfences = { preserve_tabs = true }
toc = { permalink = true }

[[project.extra.social]]
icon = "material/github"
link = "https://github.com/adriens/avps"
name = "Code source sur GitHub"

[[project.extra.social]]
icon = "material/rss"
link = "feed.xml"
name = "Flux RSS des offres"

[project.extra]
copyright = \"\"\"
Copyright &copy; 2026 adriens<br>
<small>Propulsé par <a href='https://github.com/opt-nc/zensical' target='_blank'>Zensical</a> • <a href='https://github.com/adriens/avps' target='_blank'>Source</a></small>
\"\"\"
"""
    with open("zensical.toml", "w", encoding="utf-8") as f:
        f.write(config)

def generate_rss_feed(df):
    """Génère un flux RSS valide pour les AVPs."""
    import datetime
    print("Génération de docs/feed.xml...")
    
    now = datetime.datetime.now()
    rfc822_time = now.strftime("%a, %d %b %Y %H:%M:%S +1100")
    
    rss = '<?xml version="1.0" encoding="UTF-8"?>\n'
    rss += '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
    rss += '<channel>\n'
    rss += '  <title>DRHFPNC - Avis de Vacances de Poste</title>\n'
    rss += '  <link>https://adriens.github.io/avps/</link>\n'
    rss += '  <description>Avis de vacances de poste en cours et publiés par la DRHFPNC (Nouvelle Calédonie)</description>\n'
    rss += '  <language>fr</language>\n'
    rss += '  <managingEditor>contact@example.com</managingEditor>\n'
    rss += f'  <lastBuildDate>{rfc822_time}</lastBuildDate>\n'
    rss += '  <atom:link href="https://adriens.github.io/avps/feed.xml" rel="self" type="application/rss+xml"/>\n'
    rss += '  <image>\n'
    rss += '    <url>https://adriens.github.io/avps/assets/favicon.png</url>\n'
    rss += '    <title>DRHFPNC - AVPs</title>\n'
    rss += '    <link>https://adriens.github.io/avps/</link>\n'
    rss += '  </image>\n'
    
    # Trier par date de mise en ligne décroissante et limiter à 30 récentes
    df['date_mis_en_ligne_dt'] = pd.to_datetime(df['date_mis_en_ligne'], errors='coerce')
    df_sorted = df.sort_values('date_mis_en_ligne_dt', ascending=False).head(30)
    
    for _, row in df_sorted.iterrows():
        numero = str(safe_get(row, 'numero', '')).replace("/", "_")
        libelle_poste = safe_get(row, 'libelle_poste', 'Poste disponible')
        direction = safe_get(row, 'direction_acronyme', safe_get(row, 'direction_libelle', '-'))
        date_cloture = safe_get(row, 'date_cloture', '-')
        date_publication = safe_get(row, 'date_mis_en_ligne', '')
        libelle_domaine = safe_get(row, 'libelle_domaine', 'Autres')
        url_pdf = safe_get(row, 'url_pdf', '')
        
        item_link = f"https://adriens.github.io/avps/{numero}/"
        
        # Description enrichie avec métadonnées
        description = f"<strong>Direction :</strong> {direction}<br/>"
        description += f"<strong>Domaine :</strong> {libelle_domaine}<br/>"
        description += f"<strong>Clôture :</strong> {date_cloture}"
        
        rss += '  <item>\n'
        rss += f'    <title>{numero} - {libelle_poste}</title>\n'
        rss += f'    <link>{item_link}</link>\n'
        rss += f'    <guid isPermaLink="true">{item_link}</guid>\n'
        rss += f'    <description>{description}</description>\n'
        rss += f'    <content:encoded><![CDATA[{description}]]></content:encoded>\n'
        rss += f'    <category>{libelle_domaine}</category>\n'
        
        if url_pdf:
            rss += f'    <enclosure url="{url_pdf}" length="0" type="application/pdf"/>\n'
        
        try:
            pub_date = pd.to_datetime(date_publication)
            rss += f'    <pubDate>{pub_date.strftime("%a, %d %b %Y %H:%M:%S +1100")}</pubDate>\n'
        except:
            rss += f'    <pubDate>{rfc822_time}</pubDate>\n'
            
        rss += '  </item>\n'
    
    rss += '</channel>\n'
    rss += '</rss>'
    
    with open("docs/feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)

def generate_sitemap(df, data_dir="docs"):
    """Génère un sitemap.xml pour les moteurs de recherche."""
    print("Génération de docs/sitemap.xml...")
    
    now = pd.Timestamp.now().strftime("%Y-%m-%d")
    base_url = "https://adriens.github.io/avps"
    
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # Index principal
    sitemap += '  <url>\n'
    sitemap += f'    <loc>{base_url}/</loc>\n'
    sitemap += f'    <lastmod>{now}</lastmod>\n'
    sitemap += '    <changefreq>daily</changefreq>\n'
    sitemap += '    <priority>1.0</priority>\n'
    sitemap += '  </url>\n'
    
    # Feed RSS
    sitemap += '  <url>\n'
    sitemap += f'    <loc>{base_url}/feed.xml</loc>\n'
    sitemap += f'    <lastmod>{now}</lastmod>\n'
    sitemap += '    <changefreq>daily</changefreq>\n'
    sitemap += '    <priority>0.8</priority>\n'
    sitemap += '  </url>\n'
    
    # Toutes les offres
    for _, row in df.iterrows():
        numero = str(row['numero']).replace("/", "_")
        page_path = f"{base_url}/{numero}/"
        
        try:
            date_mod = pd.to_datetime(row.get('date_mis_en_ligne', now))
            lastmod = date_mod.strftime("%Y-%m-%d")
        except:
            lastmod = now
        
        try:
            date_cloture = pd.to_datetime(row.get('date_cloture'))
            priority = "0.9" if date_cloture > pd.Timestamp.now() else "0.5"
            changefreq = "weekly" if date_cloture > pd.Timestamp.now() else "never"
        except:
            priority = "0.7"
            changefreq = "weekly"
        
        sitemap += '  <url>\n'
        sitemap += f'    <loc>{page_path}</loc>\n'
        sitemap += f'    <lastmod>{lastmod}</lastmod>\n'
        sitemap += f'    <changefreq>{changefreq}</changefreq>\n'
        sitemap += f'    <priority>{priority}</priority>\n'
        sitemap += '  </url>\n'
    
    sitemap += '</urlset>'
    
    with open(os.path.join(data_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)

def generate_robots_txt(data_dir="docs"):
    """Génère un robots.txt pour indiquer aux crawlers comment explorer le site."""
    print("Génération de docs/robots.txt...")
    
    robots = """# Robots.txt pour AVPS DRHFPNC
User-agent: *
Allow: /

# Interdire l'accès aux dossiers temporaires/privés (s'il y en avait)
Disallow: /temp/
Disallow: /.git/

# Vitesse de crawl
Crawl-delay: 1

# Sitemap
Sitemap: https://adriens.github.io/avps/sitemap.xml
Sitemap: https://adriens.github.io/avps/feed.xml
"""
    
    with open(os.path.join(data_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

if __name__ == "__main__":
    main()
