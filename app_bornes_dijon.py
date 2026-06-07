import streamlit as st
import pandas as pd
import requests
import io
import os
import re
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote_plus

# Configuration de la page
st.set_page_config(
    page_title="Bornes Electriques Carte Bancaire",
    page_icon="🗺️",
    layout="wide",
)

# --- Constantes ---
RESOURCE_URL = "https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"
DIJON_LAT = 47.3220
DIJON_LON = 5.0415

# Bases d'URL (séparées des gabarits {x}/{y}/{z} et {lat},{lon})
GOOGLE_TILES_BASE = "https://mt1.google.com/vt/lyrs="
GMAPS_SEARCH_BASE = "https://www.google.com/maps/search/?api=1&query="

CHARGEMAP_SEARCH_BASE = "https://www.google.com/search?q=chargemap+"

# --- Fonctions de traitement ---
DATA_FILE = "bornes_dijon.csv"   # fichier pré-généré et versionné avec l'app (aucun téléchargement)
CACHE_FILE = "irve_cache.csv"   # cache d'un téléchargement de la base nationale complète


def is_true(x):
    return str(x).strip().lower() in {"true", "1", "1.0", "oui", "yes"}


def clean_str(x):
    if x is None or pd.isna(x):
        return ""
    return str(x).strip()


def analyse_tarif(t):
    """Retourne (tarif_affiche, texte_a_basculer_dans_infos).

    - Si le champ ne contient qu'un lien, ou un texte sans aucun nombre,
      le tarif n'est pas exploitable : on le bascule dans les Infos et le
      tarif est marqué "Non communiqué".
    """
    t = clean_str(t)
    if not t:
        return "Non communiqué", ""
    # On retire les URL puis on vérifie s'il reste un nombre (un prix)
    sans_url = re.sub(r"(https?://\S+|www\.\S+)", "", t).strip()
    a_un_nombre = any(c.isdigit() for c in sans_url)
    if not a_un_nombre:
        return "Non communiqué", t
    return t, ""


def bloc_clampable(label, contenu, uid, seuil=130):
    """Affiche 'contenu' sous 'label', limité à 3 lignes avec un bouton
    'voir plus…' si le texte est long (astuce CSS, sans JavaScript)."""
    contenu = clean_str(contenu)
    if not contenu:
        return ""
    # Le bouton n'apparaît que si le texte dépasse ~3 lignes
    long_texte = len(contenu) > seuil or "\n" in contenu
    # Liens rendus cliquables (après calcul de la longueur visible)
    affichage = re.sub(r"(https?://\S+)", r'<a href="\1" target="_blank">\1</a>', contenu)
    en_tete = '<div style="margin-bottom: 3px;"><strong>' + label + '</strong></div>'
    if not long_texte:
        return en_tete + '<div style="font-size: 13px;">' + affichage + '</div>'
    css = (
        "<style>"
        "#" + uid + "-text{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;}"
        "#" + uid + "-cb{display:none;}"
        "#" + uid + "-cb:checked + #" + uid + "-text{-webkit-line-clamp:unset;}"
        "label[for='" + uid + "-cb'] .less{display:none;}"
        "#" + uid + "-cb:checked ~ label[for='" + uid + "-cb'] .more{display:none;}"
        "#" + uid + "-cb:checked ~ label[for='" + uid + "-cb'] .less{display:inline;}"
        "</style>"
    )
    return (
        css + en_tete
        + '<input type="checkbox" id="' + uid + '-cb">'
        + '<div id="' + uid + '-text" style="font-size: 13px;">' + affichage + '</div>'
        + '<label for="' + uid + '-cb" style="color: #1a73e8; cursor: pointer; font-size: 12px;">'
        + '<span class="more">voir plus…</span><span class="less">voir moins</span></label>'
    )


@st.cache_data(show_spinner=False)
def load_data(url, force_refresh=False):
    # Mis en cache : ne se relance que si 'url' ou 'force_refresh' change
    # 1) Fichier pré-généré livré avec l'app -> aucun téléchargement, aucun temps de chargement
    if not force_refresh and os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE, dtype=str)

    # 2) Cache d'un précédent téléchargement de la base nationale
    if not force_refresh and os.path.exists(CACHE_FILE):
        st.info("📂 Chargement des données depuis le cache local.")
        return pd.read_csv(CACHE_FILE, dtype=str)

    # 3) Téléchargement de la base nationale (premier lancement sans fichier, ou mise à jour)
    try:
        with st.spinner("🌐 Téléchargement des données nationales (cela peut prendre un moment)..."):
            response = requests.get(url, timeout=60, verify=False)
            response.raise_for_status()
            df = pd.read_csv(io.BytesIO(response.content), sep=None, engine="python", dtype=str, on_bad_lines="skip")
            # Sauvegarder dans le cache
            df.to_csv(CACHE_FILE, index=False)
            st.success("✅ Données téléchargées et mises en cache.")
            return df
    except Exception as e:
        if os.path.exists(CACHE_FILE):
            st.warning(f"⚠️ Échec du téléchargement ({e}). Utilisation du cache existant.")
            return pd.read_csv(CACHE_FILE, dtype=str)
        else:
            st.error(f"❌ Erreur critique : Impossible de télécharger les données et aucun cache disponible. ({e})")
            # Données de secours réalistes pour la démo
            demo_data = [
                {"nom_station": "Dijon - Parking Darcy", "nom_enseigne": "EFFIA", "nom_operateur": "EFFIA", "adresse_station": "Place Darcy", "consolidated_commune": "Dijon", "puissance_nominale": "50", "paiement_cb": "oui", "paiement_acte": "oui", "tarification": "0,40 €/kWh pour les non-abonnés, 0,30 €/kWh pour les abonnés au pass de mobilité, avec une majoration de 0,05 €/min au-delà de 45 minutes de stationnement une fois la charge terminée afin de favoriser la rotation.", "observations": "Paiement sans contact disponible", "consolidated_latitude": "47.3235", "consolidated_longitude": "5.0345", "prise_type_2": "1", "prise_type_combo_ccs": "1", "prise_type_chademo": "1"},
                {"nom_station": "Dijon - Toison d'Or", "nom_enseigne": "Tesla", "nom_operateur": "Tesla", "adresse_station": "Avenue de Langres", "consolidated_commune": "Dijon", "puissance_nominale": "250", "paiement_cb": "oui", "paiement_acte": "non", "consolidated_latitude": "47.3550", "consolidated_longitude": "5.0600", "prise_type_2": "0", "prise_type_combo_ccs": "1", "prise_type_chademo": "0"},
                {"nom_station": "Quetigny - Grand Marché", "nom_enseigne": "Carrefour", "nom_operateur": "Allego", "adresse_station": "Avenue de Bourgogne", "consolidated_commune": "Quetigny", "puissance_nominale": "150", "paiement_cb": "oui", "paiement_acte": "oui", "tarification": "https://www.carrefour.fr/recharge-vehicules-electriques", "consolidated_latitude": "47.3100", "consolidated_longitude": "5.1050", "prise_type_2": "1", "prise_type_combo_ccs": "1", "prise_type_chademo": "1"},
                {"nom_station": "Chenôve - Sud", "nom_enseigne": "TotalEnergies", "nom_operateur": "TotalEnergies", "adresse_station": "Rue de Longvic", "consolidated_commune": "Chenôve", "puissance_nominale": "175", "paiement_cb": "oui", "paiement_acte": "oui", "tarification": "Tarification variable selon l'abonnement souscrit auprès de votre opérateur de mobilité ; renseignez-vous directement auprès du fournisseur pour connaître les conditions applicables à votre badge.", "consolidated_latitude": "47.2900", "consolidated_longitude": "5.0150", "prise_type_2": "1", "prise_type_combo_ccs": "1", "prise_type_chademo": "0"},
                {"nom_station": "Longvic - Zone commerciale", "nom_enseigne": "Lidl", "nom_operateur": "Izivia", "adresse_station": "Rue Jean Moulin", "consolidated_commune": "Longvic", "puissance_nominale": "120", "paiement_cb": "non", "paiement_acte": "oui", "observations": "Recharge via application mobile ou badge - QR code sur la borne", "tarification": "0,45 €/kWh à l'acte", "consolidated_latitude": "47.2850", "consolidated_longitude": "5.0550", "prise_type_2": "1", "prise_type_combo_ccs": "1", "prise_type_chademo": "0"},
            ]
            return pd.DataFrame(demo_data)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * asin(sqrt(a))


def to_float(x):
    if pd.isna(x):
        return None
    try:
        return float(str(x).strip().replace(",", "."))
    except:
        return None


@st.cache_data(show_spinner=False)
def process_data(df, rayon_km, puissance_min):
    # Mis en cache : recalculé uniquement si les données, le rayon ou la puissance changent
    rows = []
    for _, row in df.iterrows():
        cb = is_true(row.get("paiement_cb"))
        acte = is_true(row.get("paiement_acte"))
        obs = clean_str(row.get("observations"))
        # On garde les bornes payables par CB, OU (à défaut) payables à l'acte
        if not cb and not acte:
            continue
        p_raw = to_float(row.get("puissance_nominale"))
        if p_raw is None:
            continue
        p_kw = p_raw / 1000.0 if p_raw > 1000 else p_raw
        if p_kw < puissance_min:
            continue
        lat = to_float(row.get("consolidated_latitude"))
        lon = to_float(row.get("consolidated_longitude"))
        if lat is None or lon is None:
            continue
        dist = haversine_km(DIJON_LAT, DIJON_LON, lat, lon)
        if dist > rayon_km:
            continue
        # Analyse du tarif : un lien seul ou un texte sans nombre n'est pas un vrai tarif
        tarif_affiche, tarif_vers_info = analyse_tarif(row.get("tarification"))
        if tarif_vers_info:
            note = "Tarif (donnée brute) : " + tarif_vers_info
            obs = (obs + " — " + note) if obs else note
        rows.append({
            "Station": row.get("nom_station"),
            "Opérateur": row.get("nom_operateur"),
            "Adresse": f"{row.get('adresse_station')}, {row.get('consolidated_commune')}",
            "Puissance": round(p_kw, 1),
            "Paiement CB": "Oui" if cb else "Non",
            "Paiement à l'acte": "Oui" if acte else "Non",
            "Type paiement": "Carte bancaire" if cb else "App / Badge / QR",
            "Tarif": tarif_affiche,
            "Observations": obs,
            "lat": lat,
            "lon": lon,
            "Distance": round(dist, 2),
        })
    return pd.DataFrame(rows)


# --- Interface Sidebar ---
st.sidebar.title("🛠️ Configuration")
map_type = st.sidebar.selectbox("Type de carte", ["Google Maps (Plan)", "Google Maps (Satellite)", "Google Maps (Terrain)", "OpenStreetMap"])
rayon = st.sidebar.slider("Rayon (km)", 5, 50, 15)
p_min = st.sidebar.select_slider("Puissance min (kW)", options=[22, 50, 100, 150, 300], value=50)

st.sidebar.divider()
force_refresh = st.sidebar.button("🔄 Forcer la mise à jour")
if force_refresh:
    # On vide le cache pour forcer un vrai rechargement des données
    st.cache_data.clear()
n
# --- Main ---
st.title("Bornes de Recharges Dijon")
st.markdown(
    "**Légende :** "
    "🟢 ≥ 150 kW · 🟠 ≥ 100W · 🔵 ≥ 50 kW · \n"
    "🔴 **Sans CB — paiement par App/QR uniquement**  \n"
    "*Base nationale des IRVE (Infrastructures de Recharge pour Véhicules Électriques) https://www.data.gouv.fr/datasets/base-nationale-des-irve-infrastructures-de-recharge-pour-vehicules-electriques*"
    "*La ë-C3 se recharge à la même vitesse dans toutes ces bornes : environ 1h pour une charge complete !*"
)

data = process_data(load_data(RESOURCE_URL, force_refresh=force_refresh), rayon, p_min)

if not data.empty:
    # Choix des tuiles Google Maps (base + gabarit séparés)
    tiles_dict = {
        "Google Maps (Plan)": GOOGLE_TILES_BASE + "m&x={x}&y={y}&z={z}",
        "Google Maps (Satellite)": GOOGLE_TILES_BASE + "s&x={x}&y={y}&z={z}",
        "Google Maps (Terrain)": GOOGLE_TILES_BASE + "p&x={x}&y={y}&z={z}",
        "OpenStreetMap": "openstreetmap",
    }

    attr = "Google" if "Google" in map_type else "OpenStreetMap"

    # Création de la carte Folium (le fond de carte est exclu du filtre des calques)
    m = folium.Map(location=[DIJON_LAT, DIJON_LON], zoom_start=13, tiles=None)
    folium.TileLayer(tiles=tiles_dict[map_type], attr=attr, name=map_type, control=False).add_to(m)

    # Filtre directement sur la carte : un calque par couleur (contrôle en haut à droite)
    feature_groups = {
        "green": folium.FeatureGroup(name="🟢 ≥ 150 kW (CB)"),
        "orange": folium.FeatureGroup(name="🟠 ≥ 100 kW (CB)"),
        "blue": folium.FeatureGroup(name="🔵 ≥ 50 kW (CB)"),
        "red": folium.FeatureGroup(name="🔴 Sans CB (app / badge / QR)", show=False),
    }
    for grp in feature_groups.values():
        grp.add_to(m)

    # Ajout des marqueurs
    for idx, row in data.iterrows():
        if row["Paiement CB"] == "Non":
            # Sans CB mais paiement à l'acte -> rouge
            color = "red"
        else:
            color = "green" if row["Puissance"] >= 150 else ("orange" if row["Puissance"] >= 100 else "blue")

        paiement_color = "#d93025" if row["Paiement CB"] == "Non" else "#188038"
        maps_url = f"{GMAPS_SEARCH_BASE}{row['lat']},{row['lon']}"

        # Tarif et Infos : repliables au-delà de 3 lignes
        if row["Tarif"] and row["Tarif"] != "Non communiqué":
            tarif_html = bloc_clampable("💶 Tarif (€/kWh) :", row["Tarif"], "tarif-" + str(idx))
        else:
            tarif_html = '<div style="margin-bottom: 5px;"><strong>💶 Tarif (€/kWh) :</strong> Non communiqué</div>'
        infos_html = bloc_clampable("📝 Infos :", row["Observations"], "obs-" + str(idx))

        # Vérification manuelle Chargemap : proposée dès que le prix n'est pas indiqué
        prix_absent = row["Tarif"] in ("", "Non communiqué")
        chargemap_url = CHARGEMAP_SEARCH_BASE + quote_plus(f"{row['Station']} {row['Adresse']}")
        chargemap_html = (
            f'<div style="margin-top: 8px;"><a href="{chargemap_url}" target="_blank" '
            'style="display: inline-block; padding: 6px 12px; background-color: #34a853; '
            'color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">'
            '🔎 Vérifier le prix sur Chargemap</a></div>'
        ) if prix_absent else ""

        html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px; border-radius: 8px;">
            <h3 style="margin: 0 0 8px 0; color: #1a73e8; font-size: 16px;">{row['Station']}</h3>
            <div style="margin-bottom: 5px;"><strong>⚡ Puissance :</strong> {row['Puissance']} kW</div>
            <div style="margin-bottom: 5px;"><strong>🏢 Opérateur :</strong> {row['Opérateur']}</div>
            <div style="margin-bottom: 5px;"><strong>📍 Adresse :</strong> {row['Adresse']}</div>
            <div style="margin-bottom: 5px;"><strong>💳 Paiement :</strong> <span style="color: {paiement_color}; font-weight: bold;">{row['Type paiement']}</span></div>
            {tarif_html}
            {infos_html}
            <div style="margin-bottom: 5px;"><strong>🚗 Distance :</strong> {row['Distance']} km</div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
            <a href="{maps_url}" target="_blank"
               style="display: inline-block; padding: 6px 12px; background-color: #1a73e8; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">
               Ouvrir dans Google Maps
            </a>
            {chargemap_html}
        </div>
        """
        popup = folium.Popup(html, max_width=300)

        folium.Marker(
            [row['lat'], row['lon']],
            popup=popup,
            tooltip=f"{row['Station']} ({row['Puissance']} kW) - {row['Type paiement']}",
            icon=folium.Icon(color=color, icon="bolt", prefix="fa"),
        ).add_to(feature_groups[color])

    # Contrôle des calques = filtre par couleur directement sur la carte
    folium.LayerControl(collapsed=True).add_to(m)

    # Affichage de la carte.
    # returned_objects=[] -> st_folium ne renvoie aucune interaction à Python :
    # cliquer sur un point ou déplacer/zoomer la carte ne déclenche plus de re-run inutile.
    # (Les détails restent visibles dans les bulles directement sur la carte.)
    st_folium(m, width="100%", height=600, returned_objects=[])

    # Tableau récapitulatif
    st.subheader("📋 Liste des stations à proximité")
    st.dataframe(data.sort_values("Distance"), use_container_width=True, hide_index=True)
else:
    st.warning("Aucune borne trouvée.")