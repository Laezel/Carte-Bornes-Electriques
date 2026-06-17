import streamlit as st
import pandas as pd
import requests
import io
import os
import re
import folium
import streamlit.components.v1 as components
from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote_plus

# Configuration de la page
st.set_page_config(
    page_title="Bornes Electriques Carte Bancaire",
    page_icon="🗺️",
    layout="wide",
    # "auto" : barre latérale dépliée sur ordinateur, repliée en menu hamburger sur mobile
    initial_sidebar_state="auto",
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

# ==========================================================================
# Internationalisation (i18n)
# - Interface (libellés, légende, popups, tableau) : dictionnaire fr / en / zh
# - Champs libres (tarif, observations) : colonnes pré-traduites du CSV
#   (observations_en/zh, tarification_en/zh) générées par prepare_data.py
# - Carte : libellés des tuiles Google via le paramètre hl
# ==========================================================================
LANGUAGES = {"🇫🇷 Français": "fr", "🇬🇧 English": "en", "🇨🇳 中文": "zh"}
MAP_LANGUAGES = {"Français": "fr", "English": "en", "中文": "zh-CN"}
MAP_KEYS = ["plan", "satellite", "terrain", "osm"]

TRANSLATIONS = {
    "fr": {
        "config": "🛠️ Configuration",
        "map_lang": "🗺️ Langue de la carte",
        "map_type": "Type de carte",
        "radius": "Rayon (km)",
        "power_min": "Puissance min (kW)",
        "refresh": "🔄 Forcer la mise à jour",
        "title": "Bornes de Recharge",
        "subtitle": "Dijon",
        "legend_cb": "🟢 **Carte bancaire acceptée**",
        "legend_nocb": "🟣 **Sans CB — app / badge / QR**",
        "legend_note": "*Tarifs indiqués à titre indicatif.*",
        "layer_cb": "🟢 Carte Bancaire Acceptée",
        "layer_nocb": "🟣 Sans CB (app / badge / QR)",
        "popup_power": "⚡ Puissance :",
        "popup_operator": "🏢 Opérateur :",
        "popup_address": "📍 Adresse :",
        "popup_payment": "💳 Paiement :",
        "popup_tarif": "💶 Tarif (€/kWh) :",
        "popup_info": "📝 Infos :",
        "popup_distance": "🚗 Distance :",
        "open_gmaps": "Ouvrir dans Google Maps",
        "check_chargemap": "🔎 Vérifier le prix sur Chargemap",
        "see_more": "voir plus…",
        "see_less": "voir moins",
        "not_communicated": "Non communiqué",
        "raw_tarif": "Tarif (donnée brute) : ",
        "list_title": "📋 Liste des {n} stations à proximité",
        "no_result": "Aucune borne trouvée.",
        "map_plan": "Google Maps (Plan)",
        "map_satellite": "Google Maps (Satellite)",
        "map_terrain": "Google Maps (Relief)",
        "map_osm": "OpenStreetMap",
        "val_yes": "Oui",
        "val_no": "Non",
        "val_card": "Carte bancaire",
        "val_app": "App / Badge / QR",
        "col_station": "Station",
        "col_operator": "Opérateur",
        "col_address": "Adresse",
        "col_power": "Puissance (kW)",
        "col_cb": "Paiement CB",
        "col_acte": "Paiement à l'acte",
        "col_paytype": "Type de paiement",
        "col_tarif": "Tarif (€/kWh)",
        "col_obs": "Observations",
        "col_distance": "Distance (km)",
    },
    "en": {
        "config": "🛠️ Settings",
        "map_lang": "🗺️ Map language",
        "map_type": "Map type",
        "radius": "Radius (km)",
        "power_min": "Min. power (kW)",
        "refresh": "🔄 Force update",
        "title": "Charging Stations",
        "subtitle": "Dijon",
        "legend_cb": "🟢 **Credit card accepted**",
        "legend_nocb": "🟣 **No card — app / badge / QR**",
        "legend_note": "*Prices shown for information only.*",
        "layer_cb": "🟢 Credit Card Accepted",
        "layer_nocb": "🟣 No card (app / badge / QR)",
        "popup_power": "⚡ Power:",
        "popup_operator": "🏢 Operator:",
        "popup_address": "📍 Address:",
        "popup_payment": "💳 Payment:",
        "popup_tarif": "💶 Price (€/kWh):",
        "popup_info": "📝 Info:",
        "popup_distance": "🚗 Distance:",
        "open_gmaps": "Open in Google Maps",
        "check_chargemap": "🔎 Check the price on Chargemap",
        "see_more": "see more…",
        "see_less": "see less",
        "not_communicated": "Not provided",
        "raw_tarif": "Price (raw data): ",
        "list_title": "📋 List of {n} nearby stations",
        "no_result": "No charging station found.",
        "map_plan": "Google Maps (Map)",
        "map_satellite": "Google Maps (Satellite)",
        "map_terrain": "Google Maps (Terrain)",
        "map_osm": "OpenStreetMap",
        "val_yes": "Yes",
        "val_no": "No",
        "val_card": "Credit card",
        "val_app": "App / Badge / QR",
        "col_station": "Station",
        "col_operator": "Operator",
        "col_address": "Address",
        "col_power": "Power (kW)",
        "col_cb": "Card payment",
        "col_acte": "Pay-as-you-go",
        "col_paytype": "Payment type",
        "col_tarif": "Price (€/kWh)",
        "col_obs": "Notes",
        "col_distance": "Distance (km)",
    },
    "zh": {
        "config": "🛠️ 设置",
        "map_lang": "🗺️ 地图语言",
        "map_type": "地图类型",
        "radius": "半径（公里）",
        "power_min": "最小功率（千瓦）",
        "refresh": "🔄 强制更新",
        "title": "充电站",
        "subtitle": "第戎",
        "legend_cb": "🟢 **接受银行卡**",
        "legend_nocb": "🟣 **不支持银行卡 — 应用 / 卡 / 二维码**",
        "legend_note": "*价格仅供参考。*",
        "layer_cb": "🟢 接受银行卡",
        "layer_nocb": "🟣 不支持银行卡（应用 / 卡 / 二维码）",
        "popup_power": "⚡ 功率：",
        "popup_operator": "🏢 运营商：",
        "popup_address": "📍 地址：",
        "popup_payment": "💳 支付方式：",
        "popup_tarif": "💶 价格（欧元/千瓦时）：",
        "popup_info": "📝 信息：",
        "popup_distance": "🚗 距离：",
        "open_gmaps": "在 Google 地图中打开",
        "check_chargemap": "🔎 在 Chargemap 上查看价格",
        "see_more": "查看更多…",
        "see_less": "收起",
        "not_communicated": "未提供",
        "raw_tarif": "价格（原始数据）：",
        "list_title": "📋 附近 {n} 个充电站列表",
        "no_result": "未找到充电站。",
        "map_plan": "Google 地图（地图）",
        "map_satellite": "Google 地图（卫星）",
        "map_terrain": "Google 地图（地形）",
        "map_osm": "OpenStreetMap",
        "val_yes": "是",
        "val_no": "否",
        "val_card": "银行卡",
        "val_app": "应用 / 卡 / 二维码",
        "col_station": "充电站",
        "col_operator": "运营商",
        "col_address": "地址",
        "col_power": "功率（千瓦）",
        "col_cb": "银行卡支付",
        "col_acte": "按次支付",
        "col_paytype": "支付方式",
        "col_tarif": "价格（欧元/千瓦时）",
        "col_obs": "备注",
        "col_distance": "距离（公里）",
    },
}

# Valeurs générées par le code -> clé de traduction (tableau et popups)
VALUE_KEYS = {
    "Oui": "val_yes",
    "Non": "val_no",
    "Carte bancaire": "val_card",
    "App / Badge / QR": "val_app",
    "Non communiqué": "not_communicated",
}


def t(lang, key, **kw):
    """Libellé d'interface traduit (repli sur le français puis sur la clé)."""
    s = TRANSLATIONS.get(lang, {}).get(key)
    if s is None:
        s = TRANSLATIONS["fr"].get(key, key)
    return s.format(**kw) if kw else s


def tv(lang, value):
    """Traduit une valeur générée (Oui/Non, type de paiement, Non communiqué)."""
    key = VALUE_KEYS.get(value)
    return t(lang, key) if key else value


def pick_lang(row, base, lang):
    """Champ libre dans la langue choisie si une colonne traduite existe
    (base_en / base_zh), sinon repli sur la version française."""
    if lang != "fr":
        traduit = clean_str(row.get(base + "_" + lang))
        if traduit:
            return traduit
    return clean_str(row.get(base))


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


def bloc_clampable(label, contenu, uid, lang="fr", seuil=130):
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
        + '<span class="more">' + t(lang, "see_more") + '</span><span class="less">' + t(lang, "see_less") + '</span></label>'
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
def process_data(df, rayon_km, puissance_min, lang):
    # Mis en cache : recalculé uniquement si les données, le rayon ou la puissance changent
    rows = []
    for _, row in df.iterrows():
        cb = is_true(row.get("paiement_cb"))
        # Izivia accepte la carte bancaire -> on force "Oui" même si la base indique le contraire
        if "izivia" in clean_str(row.get("nom_operateur")).lower():
            cb = True
        acte = is_true(row.get("paiement_acte"))
        obs = pick_lang(row, "observations", lang)
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
        tarif_affiche, tarif_vers_info = analyse_tarif(pick_lang(row, "tarification", lang))
        if tarif_vers_info:
            note = t(lang, "raw_tarif") + tarif_vers_info
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


@st.cache_data(show_spinner=False)
def build_map_html(data, map_type, hl, lang):
    """Construit la carte Folium et renvoie son HTML complet.

    Optimisation clé du temps de chargement : mise en cache (clé = données +
    type de carte + langues). La carte n'est bâtie qu'une seule fois, puis
    réutilisée instantanément par tous les onglets / sessions via components.html.
    """
    # Choix des tuiles Google Maps (base + gabarit séparés ; hl = langue des libellés de la carte)
    tiles_dict = {
        "plan": GOOGLE_TILES_BASE + "m&x={x}&y={y}&z={z}&hl=" + hl,
        "satellite": GOOGLE_TILES_BASE + "s&x={x}&y={y}&z={z}&hl=" + hl,
        "terrain": GOOGLE_TILES_BASE + "p&x={x}&y={y}&z={z}&hl=" + hl,
        "osm": "openstreetmap",
    }

    attr = "Google" if map_type != "osm" else "OpenStreetMap"

    # Création de la carte Folium (le fond de carte est exclu du filtre des calques)
    m = folium.Map(location=[DIJON_LAT, DIJON_LON], zoom_start=10, tiles=None)
    folium.TileLayer(tiles=tiles_dict[map_type], attr=attr, name=t(lang, "map_" + map_type), control=False).add_to(m)

    # Filtre directement sur la carte : un calque par moyen de paiement (contrôle en haut à droite)
    feature_groups = {
        "green": folium.FeatureGroup(name=t(lang, "layer_cb")),
        "purple": folium.FeatureGroup(name=t(lang, "layer_nocb"), show=True),
    }
    for grp in feature_groups.values():
        grp.add_to(m)

    # Ajout des marqueurs
    for idx, row in data.iterrows():
        if row["Paiement CB"] == "Non":
            # Sans CB (app / badge / QR) -> violet
            color = "purple"
        else:
            # Carte bancaire acceptée, quelle que soit la puissance -> vert
            color = "green"

        paiement_color = "#8e24aa" if row["Paiement CB"] == "Non" else "#188038"
        maps_url = f"{GMAPS_SEARCH_BASE}{row['lat']},{row['lon']}"

        # Tarif et Infos : repliables au-delà de 3 lignes
        if row["Tarif"] and row["Tarif"] != "Non communiqué":
            tarif_html = bloc_clampable(t(lang, "popup_tarif"), row["Tarif"], "tarif-" + str(idx), lang)
        else:
            tarif_html = '<div style="margin-bottom: 5px;"><strong>' + t(lang, "popup_tarif") + '</strong> ' + t(lang, "not_communicated") + '</div>'
        infos_html = bloc_clampable(t(lang, "popup_info"), row["Observations"], "obs-" + str(idx), lang)

        # Vérification manuelle Chargemap : proposée dès que le prix n'est pas indiqué
        prix_absent = row["Tarif"] in ("", "Non communiqué")
        chargemap_url = CHARGEMAP_SEARCH_BASE + quote_plus(f"{row['Station']} {row['Adresse']}")
        chargemap_html = (
            f'<div style="margin-top: 8px;"><a href="{chargemap_url}" target="_blank" '
            'style="display: inline-block; padding: 6px 12px; background-color: #34a853; '
            'color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">'
            + t(lang, "check_chargemap") + '</a></div>'
        ) if prix_absent else ""

        type_paiement = tv(lang, row['Type paiement'])
        html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px; border-radius: 8px;">
            <h3 style="margin: 0 0 8px 0; color: #1a73e8; font-size: 16px;">{row['Station']}</h3>
            <div style="margin-bottom: 5px;"><strong>{t(lang, 'popup_power')}</strong> {row['Puissance']} kW</div>
            <div style="margin-bottom: 5px;"><strong>{t(lang, 'popup_operator')}</strong> {row['Opérateur']}</div>
            <div style="margin-bottom: 5px;"><strong>{t(lang, 'popup_address')}</strong> {row['Adresse']}</div>
            <div style="margin-bottom: 5px;"><strong>{t(lang, 'popup_payment')}</strong> <span style="color: {paiement_color}; font-weight: bold;">{type_paiement}</span></div>
            {tarif_html}
            {infos_html}
            <div style="margin-bottom: 5px;"><strong>{t(lang, 'popup_distance')}</strong> {row['Distance']} km</div>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
            <a href="{maps_url}" target="_blank"
               style="display: inline-block; padding: 6px 12px; background-color: #1a73e8; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">
               {t(lang, 'open_gmaps')}
            </a>
            {chargemap_html}
        </div>
        """
        popup = folium.Popup(html, max_width=300)

        # Les bornes vertes (CB) passent au-dessus des violettes grâce à un z-index plus élevé
        # (sinon Leaflet empile les marqueurs selon leur latitude)
        folium.Marker(
            [row['lat'], row['lon']],
            popup=popup,
            tooltip=f"{row['Station']} ({row['Puissance']} kW) - {type_paiement}",
            icon=folium.Icon(color=color, icon="bolt", prefix="fa"),
            z_index_offset=1000 if color == "green" else 0,
        ).add_to(feature_groups[color])

    # Contrôle des calques = filtre par couleur directement sur la carte.
    # collapsed=True -> seulement une petite icône dans le coin ; la liste des filtres
    # se déploie au survol/clic au lieu d'être affichée en grand en permanence.
    folium.LayerControl(collapsed=True).add_to(m)

    # HTML complet de la carte : chaîne mise en cache et réutilisée par tous les onglets.
    return m.get_root().render()


# --- Sélecteur de langue (en haut à droite de la page, avec drapeaux) ---
# Placé avant la barre latérale car son résultat (lang) sert à traduire toute l'interface.
_, col_lang = st.columns([4, 1])
with col_lang:
    lang_label = st.selectbox("Langue", list(LANGUAGES.keys()), index=0, label_visibility="collapsed")
lang = LANGUAGES[lang_label]

# --- Interface Sidebar ---
st.sidebar.title(t(lang, "config"))
# Langue des libellés de la carte (tuiles Google)
map_lang_label = st.sidebar.selectbox(t(lang, "map_lang"), list(MAP_LANGUAGES.keys()), index=0)
hl = MAP_LANGUAGES[map_lang_label]

map_type = st.sidebar.selectbox(t(lang, "map_type"), MAP_KEYS, format_func=lambda k: t(lang, "map_" + k))
rayon = st.sidebar.slider(t(lang, "radius"), 5, 150, 80)
p_min = st.sidebar.select_slider(t(lang, "power_min"), options=[22, 50, 100, 150, 300], value=50)

st.sidebar.divider()
force_refresh = st.sidebar.button(t(lang, "refresh"))
if force_refresh:
    # On vide le cache pour forcer un vrai rechargement des données
    st.cache_data.clear()

# --- Main ---
# Optimisation mobile : mise en page responsive (marges réduites, carte dominante)
st.markdown(
    """
    <style>
    /* Petits écrans : marges réduites pour que la carte occupe tout l'espace */
    @media (max-width: 640px) {
        .block-container { padding: 0.5rem 0.5rem 2rem 0.5rem; }
        h1 { font-size: 1.4rem; line-height: 1.2; }
    }
    /* Un peu d'air en haut sur grand écran : descend le contenu (dont le sélecteur
       de langue) sous la barre d'outils horizontale de Streamlit */
    .block-container { padding-top: 4rem; }
    /* Masque les boutons « Fork » / GitHub (Community Cloud) tout en gardant le menu de réglages (thème clair / sombre / système) */
    [data-testid="stToolbarActions"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.header(t(lang, "title"))
st.subheader(t(lang, "subtitle"))
st.markdown(
    t(lang, "legend_cb") + "\n\n"
    + t(lang, "legend_nocb") + "\n\n"
    + t(lang, "legend_note")
)

data = process_data(load_data(RESOURCE_URL, force_refresh=force_refresh), rayon, p_min, lang)

if not data.empty:
    # Carte mise en cache (construite une seule fois) puis affichée en HTML pré-rendu
    # via components.html -> aucun aller-retour Python ni reconstruction à chaque onglet.
    components.html(build_map_html(data, map_type, hl, lang), height=600)

    # Tableau récapitulatif : section escamotable -> la carte reste l'élément dominant
    # (le tableau n'est rendu qu'à l'ouverture, ce qui allège l'affichage mobile)
    with st.expander(t(lang, "list_title", n=len(data)), expanded=False):
        disp = data.sort_values("Distance").drop(columns=["lat", "lon"]).copy()
        for col in ["Paiement CB", "Paiement à l'acte", "Type paiement", "Tarif"]:
            disp[col] = disp[col].map(lambda v: tv(lang, v))
        disp = disp.rename(columns={
            "Station": t(lang, "col_station"),
            "Opérateur": t(lang, "col_operator"),
            "Adresse": t(lang, "col_address"),
            "Puissance": t(lang, "col_power"),
            "Paiement CB": t(lang, "col_cb"),
            "Paiement à l'acte": t(lang, "col_acte"),
            "Type paiement": t(lang, "col_paytype"),
            "Tarif": t(lang, "col_tarif"),
            "Observations": t(lang, "col_obs"),
            "Distance": t(lang, "col_distance"),
        })
        st.dataframe(disp, use_container_width=True, hide_index=True)
else:
    st.warning(t(lang, "no_result"))
