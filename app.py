import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

from data_manager import DataManager
import analysis as ana
import simulation as sim
import export as exp

# --- Brand palette (see "Color theme.txt") ---
# Centralised so the CSS block and every Plotly trace draw from the same colours.
# Structure
COLOR_BG = "#FFFFFF"          # Fond principal (blanc éclatant)
COLOR_SURFACE = "#F5F5F5"     # Fond menu / sections (gris clair)
COLOR_TEXT = "#2D3748"        # Texte principal (gris anthracite)
# Accentuation
COLOR_BRICK = "#E64A19"       # Rouge brique — accent principal / CTA
COLOR_TERRACOTTA = "#D0A37D"  # Terre cuite — sous-titres / badges
COLOR_SUNFLOWER = "#FBC02D"   # Jaune tournesol — mise en valeur
COLOR_BLUE = "#64B5F6"        # Bleu canal / ciel — liens, séries secondaires
COLOR_GREEN = "#388E3C"       # Vert émeraude — validation / ancien
# Support (nuances dérivées pour lisibilité des courbes superposées)
COLOR_SUBTLE = "#6c757d"      # Gris sous-titres / annotations
COLOR_GRID = "#CCCCCC"        # Gris courbe de référence
COLOR_BRICK_DARK = "#B23A12"  # Rouge brique foncé (moyennes mobiles)
COLOR_TEXT_MUTED = "#5B6B7A"  # Anthracite atténué (moyennes mobiles)
COLOR_GREEN_DARK = "#2E7D32"  # Vert foncé (moyennes mobiles)
COLOR_BRICK_HOVER = "#C33A10"  # Rouge brique survol (boutons)
# Versions translucides (barres brutes / zones prévisionnelles)
COLOR_BRICK_FILL = "rgba(230,74,25,0.45)"
COLOR_TEXT_FILL = "rgba(45,55,72,0.45)"
COLOR_GREEN_FILL = "rgba(56,142,60,0.45)"
COLOR_BRICK_ZONE = "rgba(230,74,25,0.08)"

# --- Page Configuration ---
st.set_page_config(
    page_title="Market Intelligence Immobilier",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Brand Styling (CSS Injection) ---
st.markdown("""
<style>
    /* Main Theme Colors (see "Color theme.txt") */
    :root {
        --brand-brick: #E64A19;       /* Rouge brique — accent principal / CTA */
        --brand-terracotta: #D0A37D;  /* Terre cuite */
        --brand-sunflower: #FBC02D;   /* Jaune tournesol */
        --brand-blue: #64B5F6;        /* Bleu canal / ciel */
        --brand-green: #388E3C;       /* Vert émeraude */
        --brand-text: #2D3748;        /* Texte anthracite */
        --brand-surface: #F5F5F5;     /* Gris clair (structure) */
    }

    /* Aired-out white background */
    .stApp {
        background-color: #FFFFFF;
    }

    /* Title and headers */
    h1 {
        color: #2D3748 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 700 !important;
        border-bottom: 2px solid #E64A19;
        padding-bottom: 8px;
    }
    h2, h3 {
        color: #2D3748 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 600 !important;
    }

    /* Sidebar styling (light grey structure surface) */
    section[data-testid="stSidebar"] {
        background-color: #F5F5F5 !important;
    }

    /* Hyperlinks — bleu canal */
    a, a:visited {
        color: #1E88E5 !important;
    }

    /* KPI Card styling */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 700;
        color: #2D3748;
    }

    /* Styled container */
    .kpi-card {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #E64A19;
    }

    /* Custom button styles */
    .stButton>button {
        background-color: #E64A19 !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        font-weight: bold !important;
    }
    .stButton>button:hover {
        background-color: #C33A10 !important;
        color: white !important;
    }

    /* Multiselect chips (e.g. "Segmentation Neuf"): show the full category label
       instead of the default ellipsis truncation. */
    div[data-baseweb="select"] span[data-baseweb="tag"] {
        max-width: none !important;
    }
    div[data-baseweb="select"] span[data-baseweb="tag"] span {
        max-width: none !important;
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: normal !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Initialize Data Manager ---
@st.cache_resource
def get_data_manager():
    dm = DataManager()
    # A first run without a built data/dvf.csv triggers the (multi-minute)
    # geolocated DVF ingestion; show a spinner so the app isn't seen as frozen.
    if not os.path.exists(dm.paths["dvf"]):
        with st.spinner("Construction de la base DVF réelle (géolocalisées, 2014→2025)… quelques minutes."):
            dm.load_or_generate_all()
    else:
        dm.load_or_generate_all()
    return dm

dm = get_data_manager()

# Load initial datasets (national-level series)
df_sitadel, df_dvf, df_macro, df_sales = dm.load_or_generate_all()

# Keep untouched references to the full national series. The "Chiffres Clés" cards
# use these so the headline figures stay independent of the sidebar year slicer and
# the on-chart segment selector (which reassign / filter the working dataframes below).
df_sitadel_full, df_dvf_full = df_sitadel, df_dvf

# --- Handle parameter application from state (placed before any widget render) ---
if "opt_applied" in st.session_state and st.session_state["opt_applied"]:
    st.session_state["c1_lag"] = int(st.session_state["opt_c1_lag"])
    st.session_state["c1_w"] = float(st.session_state["opt_c1_w"])
    st.session_state["c2_lag"] = int(st.session_state["opt_c2_lag"])
    st.session_state["c2_w"] = float(st.session_state["opt_c2_w"])
    st.session_state["c3_lag"] = int(st.session_state["opt_c3_lag"])
    st.session_state["c3_w"] = float(st.session_state["opt_c3_w"])
    st.session_state["opt_applied"] = False

# --- Sidebar Controls ---
st.sidebar.title("🏠 Market Intelligence")

# 🌐 Language Selector
language = st.sidebar.selectbox("🌐 Langue / Language", ["Français", "English"])
lang_code = "FR" if language == "Français" else "EN"

# --- Bilingual Translations Dictionary ---
T = {
    "FR": {
        "title": "🏠 Outil de Market Intelligence Immobilier & Aide à la Prévision",
        "demand_planning_caption": "Département Demand Planning",
        "year_filter": "📅 Période (années)",
        "geo_filter": "🌍 Filtre Géographique",
        "geo_granularity": "Niveau de granularité",
        "regions_label": "Sélectionnez les Régions",
        "regions_all_placeholder": "all — toutes les régions",
        "depts_label": "Sélectionnez les Départements",
        "depts_all_placeholder": "all — tous les départements",
        "filter_region_label": "Filtrer par Région",
        "sidebar_info": "💡 **Aide à la décision :** Les permis de construire et mises en chantier de SIT@DEL ainsi que les ventes de logements anciens (IGEDD) prédisent l'activité des industries du second œuvre du bâtiment avec un décalage temporel (Time Lag) propre à chaque segment de logement.",
        "tab_lookback": "📊 Conjoncture rétrospective",
        "tab_macro": "🏦 Contexte Macro & Financement",
        "tab_timelag": "🔮 Simulation Time Lag",
        "tab_composite": "🧪 Modèle Composite",
        "tab_export": "💾 Export SAP IBP",
        "tab_source": "📂 Données Source",
        
        # Tab 1
        "lookback_header": "📈 Visualisation Conjoncturelle des Marchés",
        "lookback_desc": "Analyse rétrospective des indicateurs de construction neuve (SIT@DEL) et des ventes de logements anciens (IGEDD), au niveau national.",
        "seg_neuf": "Segmentation Neuf (SIT@DEL)",
        "seg_ancien": "Segmentation Ancien (DVF)",
        "kpis_title": "🔑 Chiffres Clés",
        "kpi_last_month": "Dernier mois disponible",
        "permis_12m": "Permis de Construire (Cumul 12m glissant)",
        "mises_12m": "Mises en Chantier (Cumul 12m glissant)",
        "transactions_12m": "Ventes anciennes IGEDD (Cumul 12m glissant)",
        "mensuel": "Mensuel",
        "curves_title": "📊 Courbes d'évolution du marché",
        "chart_view_label": "Type de visualisation",
        "chart_view_rolling": "Cumul Glissant 12 Mois (Lissé)",
        "chart_view_rolling6": "Cumul Glissant 6 Mois",
        "chart_view_raw": "Données Brutes Mensuelles",
        "ma_overlay_label": "Séries à afficher (données brutes et/ou moyennes mobiles) :",
        "show_raw_label": "Données brutes mensuelles",
        "ma_12": "Moyenne mobile 12 mois",
        "ma_6": "Moyenne mobile 6 mois",
        "ma_axis_title": "Moyenne mobile (milliers/mois)",
        "ma12_suffix": "MM 12m",
        "ma6_suffix": "MM 6m",
        "chart_sitadel_main": "Logements autorisés et commencés",
        "chart_sitadel_permis": "Logements autorisés",
        "chart_sitadel_mises": "Logements commencés",
        "chart_dvf_main": "Transactions de logements anciens",
        "extra_params_title": "⚙️ Paramètres supplémentaires (neuf)",
        "neuf_metric_label": "Indicateurs neuf à afficher",
        "neuf_metric_both": "Les deux",
        "neuf_metric_permis": "Permis de construire",
        "neuf_metric_mises": "Logements commencés",
        "sub_rolling": "cumul sur 12 mois, en milliers",
        "sub_rolling6": "cumul sur 6 mois, en milliers",
        "sub_raw": "données mensuelles brutes, en milliers",
        "source_label": "Source",
        "source_sitadel": "SIT@DEL (SDES)",
        "source_dvf": "IGEDD",
        "last_point_label": "Dernier point",
        "monthly_compare_title": "📅 Comparaison Mensuelle par Année",
        "monthly_compare_desc": "Sélectionnez un ou plusieurs mois pour comparer leurs valeurs d'une année à l'autre. Les années affichées correspondent au filtre « Période (années) » de la barre latérale.",
        "month_select_label": "Mois à comparer",
        "monthly_metric_label": "Indicateur neuf (SIT@DEL)",
        "chart_sitadel_monthly_permis": "Permis de construire mensuels",
        "chart_sitadel_monthly_mises": "Mises en chantier mensuelles",
        "chart_dvf_monthly_main": "Transactions mensuelles de logements anciens",
        "sub_monthly": "en milliers",
        "no_month_selected": "Sélectionnez au moins un mois pour afficher la comparaison.",
        "macro_context": "🏦 Contexte Macroéconomique et Financement",
        "macro_desc": "Indicateurs de contexte macroéconomique et de conditions de financement : indice de confiance des ménages (INSEE), taux nominaux moyens du crédit habitat (Banque de France / BCE), Euribor 3 mois et OAT 10 ans (BCE), ainsi que les intentions d'achats de logements des ménages et le taux de chômage au sens du BIT (INSEE).",
        "source_insee_full": "Source : INSEE — Enquête mensuelle de conjoncture auprès des ménages, indicateur synthétique de confiance (CVS, base 100 = moyenne de longue période), idbank 001587668.",
        "source_rate_full": "Source : Banque de France / BCE — Coût du crédit à l'habitat des particuliers (crédits nouveaux, statistiques MIR, série M.FR.B.A2C.AM.R.A.2250.EUR.N). Équivalent ouvert et téléchargeable de l'Observatoire Crédit Logement.",
        "chart_insee_title": "Indice de Confiance des Ménages (INSEE)",
        "chart_insee_avg": "Moyenne de long terme (100)",
        "chart_rates_title": "Taux d'intérêt et conditions de financement",
        "rate_series_label": "Séries à afficher :",
        "euribor_trace": "Euribor 3 mois",
        "oat_trace": "OAT 10 ans",
        "source_euribor_full": "Source : BCE — Euribor 3 mois (moyenne mensuelle, série FM M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA).",
        "source_oat_full": "Source : BCE / AFT — OAT 10 ans, taux de référence des emprunts d'État français à 10 ans (série IRS M.FR.L.L40.CI.0000.EUR.N.Z).",
        "permis_trace": "Permis de Construire",
        "mises_trace": "Mises en Chantier",
        "transactions_trace": "Transactions Ancien",
        "insee_trace": "Indice de Confiance",
        "credit_trace": "Taux Crédit Habitat",
        "chart_insee_sub": "indice base 100",
        "chart_rates_sub": "en %",
        "intentions_trace": "Intentions d'achat de logement",
        "chomage_trace": "Taux de chômage BIT",
        "chart_intentions_title": "Intentions d'achats de logements dans un délai de 1 an",
        "chart_intentions_sub": "solde des réponses, données CVS centrées-réduites",
        "chart_chomage_title": "Taux de chômage au sens du BIT en France",
        "chart_chomage_sub": "en %",
        "source_intentions_full": "Source : INSEE — Enquête mensuelle de conjoncture auprès des ménages (Camme), intentions d'achats de logements (dans un délai de 1 an), solde des réponses, données CVS (idbank 001616794). Série affichée centrée-réduite (écart à la moyenne, en écarts-types).",
        "source_chomage_full": "Source : INSEE — Taux de chômage au sens du BIT, ensemble, France hors Mayotte, données CVS trimestrielles (idbank 001688527).",

        # Tab 2
        "timelag_header": "🔮 Moteur de Simulation Prospective (Time Lag)",
        "timelag_desc": "Décaler les indicateurs macroéconomiques ou de construction immobilière dans le futur pour modéliser des indicateurs avancés et estimer la demande future.",
        "sim_params": "### 🎛️ Paramètres de Simulation",
        "src_indicator": "1. Source d'Indicateur",
        "housing_type": "Type de logement",
        "property_type": "Type de bien",
        "metric_sitadel": "Métrique",
        "indicator_label": "Indicateur",
        "smooth_ind": "Lisser l'indicateur (Cumul 12M glissant)",
        "time_lag_label": "2. Décalage Temporel (Time Lag en mois)",
        "time_lag_help": "Décale la courbe de l'indicateur vers le futur (valeur positive). Un lag de 14 signifie que l'indicateur d'aujourd'hui prédira les ventes dans 14 mois.",
        "sales_compare": "3. Comparer avec les ventes de",
        "optimal_lag_search": "🎯 Recherche de Décalage Optimal",
        "optimal_lag_desc": "Calculer automatiquement le décalage qui maximise la corrélation avec vos ventes.",
        "btn_calc_optimal": "Calculer le Lag Optimal",
        "optimal_found": "Lag Optimal trouvé",
        "max_corr": "Corrélation Maximale (Pearson)",
        "btn_apply_lag": "Appliquer le Lag de {lag} mois",
        "comp_view": "📈 Visualisation Comparée",
        "alignment_title": "Alignement : {ind} (décalé de {lag} mois) vs Ventes",
        "scale_ind": "Échelle Indicateur",
        "scale_sales": "Ventes (Unités)",
        "zone_prev": "🔮 ZONE PRÉVISIONNELLE",
        "corr_dist_title": "📊 Distribution des coefficients de corrélation par mois de décalage",
        "best_align_title": "Meilleur alignement : {lag} mois avec r = {r}",
        
        # Tab 3
        "composite_header": "🧪 Créateur d'Indicateur Avancé Composite",
        "composite_desc": "Combinez plusieurs indicateurs (permis, taux, confiance) avec des décalages temporels et des pondérations personnalisés pour créer un signal d'activité composite robuste.",
        "composite_config": "🛠️ Sélectionnez les composantes et configurez leurs poids et lags",
        "comp1_title": "Component 1: SIT@DEL",
        "comp2_title": "Component 2: INSEE",
        "comp3_title": "Component 3: Financement",
        "comp_lag": "Lag (mois)",
        "comp_weight": "Poids de l'Indicateur",
        "comp_invert": "Inverser l'indicateur",
        "comp_invert_help": "Recommandé : des taux élevés freinent l'immobilier, inverser permet de créer un signal d'activité positif corrélé aux ventes.",
        "bench_product": "Sélectionnez le produit pour évaluer le modèle composite",
        "composite_plot_title": "Indicateur Avancé Composite (Normalisé 0-100) vs Ventes Réelles",
        "composite_axis": "Indice Composite (0-100)",
        "sales_axis": "Volume des Ventes (Unités)",
        "composite_perf": "💡 **Performance de l'indicateur composite :** Corrélation linéaire avec les ventes de {product} : **r = {r:.3f}**.",
        
        # Tab 4
        "export_header": "💾 Export et Formatage pour SAP IBP",
        "export_desc": "Formatez, prévisualisez et exportez la série temporelle de l'Indicateur Avancé calculé pour l'intégrer directement comme Key Figure Exogène dans SAP IBP.",
        "export_source_label": "Indicateur à exporter",
        "src_simple_lag": "Indicateur Simple Décalé (Défini dans l'onglet 'Simulation')",
        "src_composite": "Indicateur Composite (Défini dans l'onglet 'Modèle Composite')",
        "no_simple_lag": "⚠️ Aucun indicateur décalé n'a été calculé. Rendez-vous sur l'onglet 'Simulation Time Lag' pour en générer un.",
        "no_composite": "⚠️ Aucun indicateur composite n'a été créé. Rendez-vous sur l'onglet 'Modèle Composite' pour en configurer un.",
        "export_ready": "✅ Source prête à l'export contenant {count} mois de données.",
        "export_params": "### ⚙️ Paramètres d'Exportation SAP",
        "kf_name_label": "ID de la Key Figure dans SAP IBP",
        "granularity_label": "Granularité temporelle",
        "date_format_label": "Format de date / période",
        "delimiter_label": "Délimiteur de colonnes CSV",
        "locid_default": "Code de localisation par défaut (LOCID)",
        "header_mapping": "#### 🛠️ Personnalisation des En-têtes (Headers Mapping)",
        "header_period": "Période (Time)",
        "header_loc": "Localisation (Location)",
        "header_ind": "Indicateur / Produit",
        "header_val": "Valeur (Value)",
        "export_preview_title": "👀 Prévisualisation du fichier d'intégration (.csv)",
        "export_rows_desc": "Aperçu des 10 premières lignes (total : {count} lignes) :",
        "btn_download_csv": "📥 Télécharger le fichier CSV pour SAP IBP",
        "sap_instructions": "#### 📋 Instructions de chargement SAP IBP:\n1. Connectez-vous à la console SAP IBP Cloud.\n2. Ouvrez l'application **\"Data Integration Jobs\"**.\n3. Sélectionnez le job de chargement des **Key Figures** de type exogène.\n4. Déposez ce fichier CSV. L'alignement automatique avec la Key Figure `KEYFIGUREVALUE` et la période `PERIODID0` se fera d'après vos en-têtes configurés.",
        
        # Tab 5
        "source_header": "📂 Gestion des Données Ingestion & Open Data",
        "source_desc": "Ce module gère le stockage local et permet d'ingérer de nouvelles données en téléversant des fichiers CSV personnalisés pour écraser les données historiques.",
        "source_status": "📊 Données Actuelles du Système",
        "select_db_view": "Sélectionnez la base à visualiser / mettre à jour",
        "db_preview_label": "Aperçu de la base **{name}** ({count} lignes) :",
        "btn_download_template": "📥 Télécharger le modèle CSV ({name}.csv)",
        "upload_new_data": "📤 Téléverser de Nouvelles Données",
        "upload_desc": "Mettez à jour la table **{name}** avec vos propres données locales ou des extractions directes SAP / Ministères.",
        "required_cols": "Colonnes requises :",
        "file_uploader_label": "Choisir un fichier CSV pour {name}",
        "btn_import_overwrite": "Importer et Écraser {name}",
        "reset_title": "⚠️ Réinitialisation Générale",
        "reset_desc": "Rétablir toutes les bases de données par défaut de l'application (données historiques 2018-2026).",
        "btn_reset_all": "Réinitialiser toutes les bases",
        "reset_spinner": "Rétablissement des données en cours...",
        "reset_success": "Toutes les bases ont été réinitialisées aux données d'origine !",
        "synthetic_note": "⚠️ Données synthétiques, en attente de source officielle.",
        "map_caption": "🗺️ Transactions DVF 2025 par département (foncé = plus de transactions). Cliquez un département pour filtrer.",
        "map_caption_region": "🗺️ Transactions DVF 2025 par région (foncé = plus de transactions). Cliquez une région pour filtrer.",
        "map_hover_tx": "Transactions 2025",
        "igedd_header": "🏛️ Ventes dans l'ancien (source IGEDD)",
        "igedd_desc": "La série des ventes de logements anciens provient du fichier national IGEDD « data_manual_input/nombre-vente-maison-appartement-ancien.xls » (cumul 12 mois glissant, national). Cliquez pour la reconstruire si vous avez mis à jour le fichier.",
        "igedd_btn": "🔄 Reconstruire les ventes anciennes (IGEDD)",
        "igedd_spinner": "Lecture du fichier IGEDD et reconstruction de la série...",
    },
    "EN": {
        "title": "🏠 Real Estate Market Intelligence & Forecasting Tool",
        "demand_planning_caption": "Demand Planning Department",
        "year_filter": "📅 Period (years)",
        "geo_filter": "🌍 Geographic Filter",
        "geo_granularity": "Granularity level",
        "regions_label": "Select Regions",
        "regions_all_placeholder": "all — every region",
        "depts_label": "Select Departments",
        "depts_all_placeholder": "all — every department",
        "filter_region_label": "Filter by Region",
        "sidebar_info": "💡 **Decision support:** SIT@DEL building permits & construction starts as well as IGEDD existing-home sales predict activity in the building secondary-works (second-œuvre) industries with a specific Time Lag proper to each housing segment.",
        "tab_lookback": "📊 Look-back Analysis",
        "tab_macro": "🏦 Macro & Financing Context",
        "tab_timelag": "🔮 Time Lag Simulation",
        "tab_composite": "🧪 Composite Model",
        "tab_export": "💾 Export SAP IBP",
        "tab_source": "📂 Source Data",
        
        # Tab 1
        "lookback_header": "📈 Market Economic Visualization",
        "lookback_desc": "Retrospective analysis of new construction metrics (SIT@DEL) and existing-home sales volumes (IGEDD), at the national level.",
        "seg_neuf": "New Construction Segment (SIT@DEL)",
        "seg_ancien": "Existing Housing Segment (DVF)",
        "kpis_title": "🔑 Key Performance Indicators",
        "kpi_last_month": "Last available month",
        "permis_12m": "Building Permits (12M Rolling Cumulative)",
        "mises_12m": "Construction Starts (12M Rolling Cumulative)",
        "transactions_12m": "IGEDD existing-home sales (12M Rolling Cumulative)",
        "mensuel": "Monthly",
        "curves_title": "📊 Market evolution curves",
        "chart_view_label": "Visualization Type",
        "chart_view_rolling": "12-Month Rolling Cumulative (Smoothed)",
        "chart_view_rolling6": "6-Month Rolling Cumulative",
        "chart_view_raw": "Raw Monthly Data",
        "ma_overlay_label": "Series to display (raw data and/or moving averages):",
        "show_raw_label": "Raw monthly data",
        "ma_12": "12-month moving average",
        "ma_6": "6-month moving average",
        "ma_axis_title": "Moving average (thousands/month)",
        "ma12_suffix": "12m MA",
        "ma6_suffix": "6m MA",
        "chart_sitadel_main": "Housing permits and starts",
        "chart_sitadel_permis": "Housing permits",
        "chart_sitadel_mises": "Housing starts",
        "chart_dvf_main": "Existing-home sales",
        "extra_params_title": "⚙️ Additional settings (new-build)",
        "neuf_metric_label": "New-build indicators to display",
        "neuf_metric_both": "Both",
        "neuf_metric_permis": "Building permits",
        "neuf_metric_mises": "Housing starts",
        "sub_rolling": "12-month rolling sum, in thousands",
        "sub_rolling6": "6-month rolling sum, in thousands",
        "sub_raw": "raw monthly data, in thousands",
        "source_label": "Source",
        "source_sitadel": "SIT@DEL (SDES)",
        "source_dvf": "IGEDD",
        "last_point_label": "Last data point",
        "monthly_compare_title": "📅 Monthly Comparison by Year",
        "monthly_compare_desc": "Select one or more months to compare their values year over year. The years shown follow the “Période (années)” filter in the sidebar.",
        "month_select_label": "Months to compare",
        "monthly_metric_label": "New-build indicator (SIT@DEL)",
        "chart_sitadel_monthly_permis": "Monthly building permits",
        "chart_sitadel_monthly_mises": "Monthly construction starts",
        "chart_dvf_monthly_main": "Monthly existing-home sales",
        "sub_monthly": "in thousands",
        "no_month_selected": "Select at least one month to display the comparison.",
        "macro_context": "🏦 Macroeconomics and Financing Context",
        "macro_desc": "Macroeconomic context and financing-condition indicators: household confidence index (INSEE), average nominal housing-loan rates (Banque de France / ECB), 3-month Euribor and 10-year OAT (ECB), together with household housing-purchase intentions and the ILO unemployment rate (INSEE).",
        "source_insee_full": "Source: INSEE — Monthly household confidence survey, synthetic confidence indicator (SA, base 100 = long-term average), idbank 001587668.",
        "source_rate_full": "Source: Banque de France / ECB — Cost of borrowing for house purchase (new business, MIR statistics, series M.FR.B.A2C.AM.R.A.2250.EUR.N). Open, downloadable equivalent of the Crédit Logement Observatory rate.",
        "chart_insee_title": "Household Confidence Index (INSEE)",
        "chart_insee_avg": "Long-term Average (100)",
        "chart_rates_title": "Interest rates and financing conditions",
        "rate_series_label": "Series to display:",
        "euribor_trace": "3-month Euribor",
        "oat_trace": "10-year OAT",
        "source_euribor_full": "Source: ECB — 3-month Euribor (monthly average, FM series M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA).",
        "source_oat_full": "Source: ECB / AFT — 10-year OAT, benchmark yield of French 10-year government bonds (IRS series M.FR.L.L40.CI.0000.EUR.N.Z).",
        "permis_trace": "Building Permits",
        "mises_trace": "Construction Starts",
        "transactions_trace": "Transactions",
        "insee_trace": "Confidence Index",
        "credit_trace": "Housing Loan Rate",
        "chart_insee_sub": "index, base 100",
        "chart_rates_sub": "in %",
        "intentions_trace": "Housing purchase intentions",
        "chomage_trace": "ILO unemployment rate",
        "chart_intentions_title": "Housing purchase intentions within 1 year",
        "chart_intentions_sub": "response balance, seasonally adjusted, standardized",
        "chart_chomage_title": "ILO unemployment rate in France",
        "chart_chomage_sub": "in %",
        "source_intentions_full": "Source: INSEE — Monthly household confidence survey (Camme), intentions to purchase housing (within 1 year), response balance, seasonally adjusted (idbank 001616794). Series shown standardized (deviation from mean, in standard deviations).",
        "source_chomage_full": "Source: INSEE — ILO unemployment rate, whole population, France excl. Mayotte, seasonally adjusted quarterly data (idbank 001688527).",

        # Tab 2
        "timelag_header": "🔮 Forward-Looking Simulation Engine (Time Lag)",
        "timelag_desc": "Shift macroeconomic or construction indicators forward in time to model leading indicators and project future sales demand.",
        "sim_params": "### 🎛️ Simulation Parameters",
        "src_indicator": "1. Indicator Source",
        "housing_type": "Housing type",
        "property_type": "Property type",
        "metric_sitadel": "Metric",
        "indicator_label": "Indicator",
        "smooth_ind": "Smooth indicator (12M rolling cumulative)",
        "time_lag_label": "2. Time Lag (months)",
        "time_lag_help": "Shifts the indicator curve forward in time (positive lag). A lag of 14 means today's permits will predict sales 14 months into the future.",
        "sales_compare": "3. Compare with sales of",
        "optimal_lag_search": "🎯 Optimal Lag Search",
        "optimal_lag_desc": "Automatically calculate the time lag that maximizes Pearson correlation with your sales.",
        "btn_calc_optimal": "Calculate Optimal Lag",
        "optimal_found": "Optimal Lag found",
        "max_corr": "Maximum Correlation (Pearson)",
        "btn_apply_lag": "Apply Lag of {lag} months",
        "comp_view": "📈 Comparative Visualization",
        "alignment_title": "Alignment: {ind} (shifted by {lag} months) vs Sales",
        "scale_ind": "Indicator Scale",
        "scale_sales": "Sales (Units)",
        "zone_prev": "🔮 FORECAST ZONE",
        "corr_dist_title": "📊 Correlation coefficient distribution by month lag",
        "best_align_title": "Best alignment: {lag} months with r = {r}",
        
        # Tab 3
        "composite_header": "🧪 Weighted Composite Leading Indicator",
        "composite_desc": "Combine multiple indicators (permis, rates, confidence) with custom time lags and weights to create a single robust demand signal.",
        "composite_config": "🛠️ Select components and configure weights and lags",
        "comp1_title": "Component 1: SIT@DEL",
        "comp2_title": "Component 2: INSEE",
        "comp3_title": "Component 3: Financing",
        "comp_lag": "Lag (months)",
        "comp_weight": "Indicator Weight",
        "comp_invert": "Invert indicator",
        "comp_invert_help": "Recommended: High interest rates slow down housing. Inverting creates a positive activity signal correlated with sales.",
        "bench_product": "Select product to benchmark the composite model",
        "composite_plot_title": "Composite Leading Indicator (Normalized 0-100) vs Actual Sales",
        "composite_axis": "Composite Index (0-100)",
        "sales_axis": "Sales Volume (Units)",
        "composite_perf": "💡 **Composite indicator performance:** Linear correlation with sales of {product}: **r = {r:.3f}**.",
        
        # Tab 4
        "export_header": "💾 SAP IBP Formatting & Export",
        "export_desc": "Format, preview and export the calculated Leading Indicator series to import it directly as an Exogenous Key Figure in SAP IBP.",
        "export_source_label": "Indicator to export",
        "src_simple_lag": "Shifted Simple Indicator (Defined in 'Simulation' tab)",
        "src_composite": "Composite Indicator (Defined in 'Composite Model' tab)",
        "no_simple_lag": "⚠️ No shifted simple indicator calculated. Go to the 'Simulation Time Lag' tab to generate one.",
        "no_composite": "⚠️ No composite indicator created. Go to the 'Composite Model' tab to configure one.",
        "export_ready": "✅ Export source ready with {count} months of data.",
        "export_params": "### ⚙️ SAP Export Settings",
        "kf_name_label": "Key Figure ID in SAP IBP",
        "granularity_label": "Temporal granularity",
        "date_format_label": "Date / period format",
        "delimiter_label": "CSV Column Delimiter",
        "locid_default": "Default location code (LOCID)",
        "header_mapping": "#### 🛠️ Column Headers Mapping",
        "header_period": "Period (Time)",
        "header_loc": "Location (Location)",
        "header_ind": "Indicator / Product",
        "header_val": "Value (Value)",
        "export_preview_title": "👀 Integration File Preview (.csv)",
        "export_rows_desc": "Showing the first 10 rows (total: {count} rows):",
        "btn_download_csv": "📥 Download CSV file for SAP IBP",
        "sap_instructions": "#### 📋 SAP IBP Loading Instructions:\n1. Log in to your SAP IBP Cloud console.\n2. Open the **\"Data Integration Jobs\"** app.\n3. Select the job to load exogenous **Key Figures**.\n4. Upload this CSV file. Automatic alignment with Key Figure `KEYFIGUREVALUE` and period `PERIODID0` will be done based on your configured headers.",
        
        # Tab 5
        "source_header": "📂 Source Data & Open Data Management",
        "source_desc": "This module manages local storage and enables data ingestion by uploading custom CSV files to overwrite historical data.",
        "source_status": "📊 Current System Databases",
        "select_db_view": "Select database to view / update",
        "db_preview_label": "Database preview for **{name}** ({count} rows):",
        "btn_download_template": "📥 Download CSV template ({name}.csv)",
        "upload_new_data": "📤 Upload New Data",
        "upload_desc": "Update the **{name}** table with your own local data or direct extractions from SAP / Ministries.",
        "required_cols": "Required columns:",
        "file_uploader_label": "Choose CSV file for {name}",
        "btn_import_overwrite": "Import & Overwrite {name}",
        "reset_title": "⚠️ System General Reset",
        "reset_desc": "Restore all databases to application default values (historical data 2018-2026).",
        "btn_reset_all": "Reset all databases",
        "reset_spinner": "Restoring data, please wait...",
        "reset_success": "All databases have been successfully restored to factory defaults!",
        "synthetic_note": "⚠️ Synthetic data, pending an official source.",
        "map_caption": "🗺️ 2025 DVF transactions by department (darker = more transactions). Click a department to filter.",
        "map_caption_region": "🗺️ 2025 DVF transactions by region (darker = more transactions). Click a region to filter.",
        "map_hover_tx": "2025 transactions",
        "igedd_header": "🏛️ Existing-home sales (IGEDD source)",
        "igedd_desc": "The existing-home sales series comes from the IGEDD national file 'data_manual_input/nombre-vente-maison-appartement-ancien.xls' (12-month rolling total, national). Click to rebuild it if you have updated the file.",
        "igedd_btn": "🔄 Rebuild existing-home sales (IGEDD)",
        "igedd_spinner": "Reading the IGEDD file and rebuilding the series...",
    }
}

# Apply Translations
st.sidebar.caption(T[lang_code]["demand_planning_caption"])
st.sidebar.markdown("---")
# National-only tracking: no geographic filter or map. Every series is followed
# at the France level, so downstream filtering is a no-op.
internal_geo_level = "National"
selected_regions = []
selected_departments = []

# --- Year range slicer: filters every series to the chosen period ---
_all_dates = pd.concat([df_sitadel["Date"], df_dvf["Date"], df_sales["Date"], df_macro["Date"]])
_ymin, _ymax = int(_all_dates.dt.year.min()), int(_all_dates.dt.year.max())
year_range = st.sidebar.slider(
    T[lang_code]["year_filter"], _ymin, _ymax, (_ymin, _ymax), step=1
)

def _filter_years(df):
    return df[(df["Date"].dt.year >= year_range[0]) & (df["Date"].dt.year <= year_range[1])]

df_sitadel = _filter_years(df_sitadel)
df_dvf = _filter_years(df_dvf)
df_macro = _filter_years(df_macro)
df_sales = _filter_years(df_sales)

st.sidebar.info(T[lang_code]["sidebar_info"])

# --- Main Page Title ---
st.title(T[lang_code]["title"])

# Filter dataframes according to geographical choices
filtered_sitadel = ana.filter_by_geography(df_sitadel, internal_geo_level, selected_regions, selected_departments)
filtered_dvf = ana.filter_by_geography(df_dvf, internal_geo_level, selected_regions, selected_departments)
filtered_sales = ana.filter_by_geography(df_sales, internal_geo_level, selected_regions, selected_departments)

_FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_EN_MONTHS = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

def format_month_year(date, lang="FR"):
    """Format a timestamp as 'mars 2026' (FR) / 'March 2026' (EN)."""
    if pd.isna(date):
        return "—"
    date = pd.Timestamp(date)
    months = _EN_MONTHS if lang == "EN" else _FR_MONTHS
    return f"{months[date.month - 1]} {date.year}"

def last_valid_month(df, value_col, date_col="Date"):
    """Return the most recent date for which value_col is non-null."""
    valid = df.dropna(subset=[value_col])
    return valid[date_col].max() if not valid.empty else pd.NaT

def add_moving_average_traces(fig, disp_df, base_col, name, color, show_ma12, show_ma6,
                              ma12_lbl, ma6_lbl, date_col="Date"):
    """Overlay 6m/12m moving-average lines (per-month mean = rolling sum / window) for
    `base_col` on the primary y-axis, alongside the raw monthly data (same scale).
    `disp_df` already holds the rolling-sum columns '<base>_12M'/'<base>_6M' scaled to
    thousands."""
    if show_ma12 and f"{base_col}_12M" in disp_df:
        fig.add_trace(go.Scatter(x=disp_df[date_col], y=disp_df[f"{base_col}_12M"] / 12.0,
                                 name=f"{name} · {ma12_lbl}",
                                 line=dict(color=color, width=2.4, dash="solid")))
    if show_ma6 and f"{base_col}_6M" in disp_df:
        fig.add_trace(go.Scatter(x=disp_df[date_col], y=disp_df[f"{base_col}_6M"] / 6.0,
                                 name=f"{name} · {ma6_lbl}",
                                 line=dict(color=color, width=2.4, dash="dot")))

def _year_shade(base_rgb, t):
    """Blend a base RGB colour with white. t=0 -> light tint (older years),
    t=1 -> full base colour (most recent year), like the IGEDD purple gradient."""
    r, g, b = base_rgb
    mix = 0.80 * (1.0 - t)  # fraction of white mixed in
    return f"rgb({int(r + (255 - r) * mix)},{int(g + (255 - g) * mix)},{int(b + (255 - b) * mix)})"

def build_monthly_year_bars(agg_df, value_col, month_nums, month_labels, base_rgb,
                            date_col="Date", divisor=1000.0):
    """Grouped bar chart comparing the selected months across years.

    x-axis = selected months; one bar group per year (barmode='group'); values are the
    monthly `value_col` divided by `divisor` ("en milliers"). Years come from `agg_df`,
    which is already restricted to the sidebar "Période (années)" filter.
    """
    d = agg_df.copy()
    d["_Year"] = d[date_col].dt.year
    d["_Month"] = d[date_col].dt.month
    years = sorted(d["_Year"].unique())
    n = len(years)
    fig = go.Figure()
    for i, y in enumerate(years):
        t = 1.0 if n <= 1 else i / (n - 1)
        yvals = []
        for m in month_nums:
            row = d[(d["_Year"] == y) & (d["_Month"] == m)]
            yvals.append(round(row[value_col].sum() / divisor, 1) if not row.empty else None)
        fig.add_trace(go.Bar(name=str(y), x=month_labels, y=yvals,
                             marker_color=_year_shade(base_rgb, t)))
    fig.update_layout(
        barmode="group",
        xaxis_title="",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def find_and_add_extrema_trace(fig, df, date_col, val_col, color, window=24, edge_buffer=12, text_divisor=1000):
    df_clean = df.dropna(subset=[val_col]).reset_index(drop=True)
    if len(df_clean) < 3:
        return
    
    vals = df_clean[val_col].values
    dates = df_clean[date_col].values
    n = len(vals)
    
    extrema_x = []
    extrema_y = []
    extrema_text = []
    extrema_pos = []
    
    # 1. Start point
    extrema_x.append(dates[0])
    extrema_y.append(vals[0])
    extrema_text.append(f"<b>{int(round(vals[0] / text_divisor)):,}</b>")
    extrema_pos.append("top right")
    
    # 2. Local extrema (only if not too close to the edges)
    for i in range(1, n - 1):
        if i < edge_buffer or (n - 1 - i) < edge_buffer:
            continue
            
        start_idx = max(0, i - window)
        end_idx = min(n, i + window + 1)
        local_window = vals[start_idx:end_idx]
        
        is_max = (vals[i] == np.max(local_window)) and (i == start_idx + np.argmax(local_window))
        is_min = (vals[i] == np.min(local_window)) and (i == start_idx + np.argmin(local_window))
        
        if is_max:
            extrema_x.append(dates[i])
            extrema_y.append(vals[i])
            extrema_text.append(f"<b>{int(round(vals[i] / text_divisor)):,}</b>")
            extrema_pos.append("top center")
        elif is_min:
            extrema_x.append(dates[i])
            extrema_y.append(vals[i])
            extrema_text.append(f"<b>{int(round(vals[i] / text_divisor)):,}</b>")
            extrema_pos.append("bottom center")
            
    # 3. End point
    if dates[-1] not in extrema_x:
        extrema_x.append(dates[-1])
        extrema_y.append(vals[-1])
        extrema_text.append(f"<b>{int(round(vals[-1] / text_divisor)):,}</b>")
        extrema_pos.append("top right")
        
    fig.add_trace(go.Scatter(
        x=extrema_x,
        y=extrema_y,
        mode="text",
        text=extrema_text,
        textposition=extrema_pos,
        showlegend=False,
        textfont=dict(size=11, color=color, family="Arial Black"),
        hoverinfo="skip"
    ))

def add_last_value_label(fig, df, date_col, val_col, color, lang="FR", decimals=2):
    """Mark the last non-null point of `val_col` with a highlighted value callout
    (dot + label), like the reference chart's end-of-line figures. Values use the
    French decimal comma in FR."""
    valid = df.dropna(subset=[val_col])
    if valid.empty:
        return
    row = valid.iloc[-1]
    x, y = row[date_col], float(row[val_col])
    txt = f"{y:.{decimals}f}"
    if lang != "EN":
        txt = txt.replace(".", ",")
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode="markers",
        marker=dict(color=color, size=7),
        showlegend=False, hoverinfo="skip"
    ))
    fig.add_annotation(
        x=x, y=y, text=f"<b>{txt}</b>",
        showarrow=False, xanchor="left", xshift=8,
        font=dict(color=color, size=12)
    )

def apply_macro_chart_layout(fig, yaxis_title):
    """Uniform look for the four "Contexte Macro & Financement" charts: identical
    height and margins (so every chart is the same size) and a horizontal legend
    anchored just above the plot area, top-left (uniform legend placement). Titles are
    rendered as markdown above each chart, so no in-figure title is set here."""
    fig.update_layout(
        height=380,
        xaxis_title="Date",
        yaxis_title=yaxis_title,
        template="plotly_white",
        margin=dict(l=60, r=70, t=54, b=44),  # r: room for end-of-line callouts; t: top legend
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        showlegend=True,
    )

def macro_chart_title(title, subtitle):
    """Bold markdown title + grey inline subtitle, shared by the four macro charts."""
    st.markdown(
        f"**{title}** "
        f"<span style='color:#6c757d;font-weight:400'>({subtitle})</span>",
        unsafe_allow_html=True
    )

# --- Define Streamlit Tabs ---
tabs = st.tabs([
    T[lang_code]["tab_lookback"],
    T[lang_code]["tab_macro"],
    T[lang_code]["tab_timelag"],
    T[lang_code]["tab_composite"],
    T[lang_code]["tab_export"],
    T[lang_code]["tab_source"]
])

# ==============================================================================
# TAB 1: CONJONCTURE LOOK-BACK
# ==============================================================================
with tabs[0]:
    st.header(T[lang_code]["lookback_header"])
    st.write(T[lang_code]["lookback_desc"])
    
    # KPIs sit above the curves, but they depend on the SIT@DEL segment selector
    # which now lives with the SIT@DEL chart further down. Reserve the KPI position
    # with a container and fill it once the selection is known.
    kpi_container = st.container()

    # --- Charts Row ---
    st.markdown(f"### {T[lang_code]['curves_title']}")
    chart_view_opts = [T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"], T[lang_code]["chart_view_raw"]]
    chart_view = st.radio(T[lang_code]["chart_view_label"], chart_view_opts, horizontal=True)

    # Moving averages apply to the raw monthly data only (same scale) — never to the
    # rolling cumulative views. In that view the raw bars, the 6m MA and the 12m MA are
    # three independent toggles, so the averages can be shown together and with or without
    # the raw data. Offered only when "Données Brutes Mensuelles" is selected.
    show_raw = True
    show_ma12 = show_ma6 = False
    if chart_view == T[lang_code]["chart_view_raw"]:
        st.caption(T[lang_code]["ma_overlay_label"])
        _rc1, _rc2, _rc3, _rc_rest = st.columns([1.3, 1.3, 1.3, 1])
        with _rc1:
            show_raw = st.checkbox(T[lang_code]["show_raw_label"], value=True, key="show_raw")
        with _rc2:
            show_ma12 = st.checkbox(T[lang_code]["ma_12"], key="ma12")
        with _rc3:
            show_ma6 = st.checkbox(T[lang_code]["ma_6"], key="ma6")

    # Extra settings for the neuf/SIT@DEL chart, tucked into a collapsible expander:
    #  - which indicators to show (permits only / starts only / both);
    #  - the housing-type segmentation. Both apply to the neuf chart only (the IGEDD
    #    "ancien" series is a single national aggregate with no housing-type split).
    with st.expander(T[lang_code]["extra_params_title"]):
        neuf_metric = st.radio(
            T[lang_code]["neuf_metric_label"],
            [T[lang_code]["neuf_metric_both"], T[lang_code]["neuf_metric_permis"], T[lang_code]["neuf_metric_mises"]],
            horizontal=True, key="neuf_metric_evo"
        )
        sitadel_types = st.multiselect(
            T[lang_code]["seg_neuf"],
            options=df_sitadel["Type"].unique().tolist(),
            default=df_sitadel["Type"].unique().tolist(),
            key="seg_sitadel"
        )
    show_permis = neuf_metric in (T[lang_code]["neuf_metric_both"], T[lang_code]["neuf_metric_permis"])
    show_mises = neuf_metric in (T[lang_code]["neuf_metric_both"], T[lang_code]["neuf_metric_mises"])

    c_col1, c_col2 = st.columns(2)

    # Aggregate data according to segment selections
    agg_sitadel = ana.aggregate_sitadel(filtered_sitadel, sitadel_types)
    agg_dvf = ana.aggregate_dvf(filtered_dvf)

    # Calculate rolling 12m + 6m sums for the smoothed visualizations
    rolling_sitadel = ana.calculate_rolling_12m(agg_sitadel, ["Permis", "MisesEnChantier"])
    rolling_sitadel = ana.calculate_rolling(rolling_sitadel, ["Permis", "MisesEnChantier"], 6)
    rolling_dvf = ana.calculate_rolling_12m(agg_dvf, ["Transactions"])
    rolling_dvf = ana.calculate_rolling(rolling_dvf, ["Transactions"], 6)

    # KPI Calculations. The "Chiffres Clés" cards always reflect the full national
    # total (all housing types, full history) for the last available month, independent
    # of the sidebar year slicer and the SIT@DEL segment selector. The charts above use
    # the filtered series; these headline figures use the untouched full series.
    rolling_sitadel_total = ana.calculate_rolling_12m(
        ana.aggregate_sitadel(df_sitadel_full), ["Permis", "MisesEnChantier"]
    )
    rolling_dvf_total = ana.calculate_rolling_12m(
        ana.aggregate_dvf(df_dvf_full), ["Transactions"]
    )
    kpi_permis = ana.calculate_kpis(rolling_sitadel_total, "Permis")
    kpi_mises = ana.calculate_kpis(rolling_sitadel_total, "MisesEnChantier")
    kpi_transactions = ana.calculate_kpis(rolling_dvf_total, "Transactions")

    # Last available month behind each headline figure (SIT@DEL vs IGEDD can differ).
    _kpi_sitadel_month = format_month_year(last_valid_month(rolling_sitadel_total, "Permis"), lang_code)
    _kpi_dvf_month = format_month_year(last_valid_month(rolling_dvf_total, "Transactions"), lang_code)

    # --- KPI Row (rendered into the reserved container above the charts) ---
    kpi_container.markdown(f"### {T[lang_code]['kpis_title']}")
    kpi_cols = kpi_container.columns(3)

    with kpi_cols[0]:
        st.metric(
            label=T[lang_code]["permis_12m"],
            value=f"{kpi_permis['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_permis['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_permis['current_val']:,} ({kpi_permis['yoy_monthly_pct']}% YoY)")
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_sitadel_month}")

    with kpi_cols[1]:
        st.metric(
            label=T[lang_code]["mises_12m"],
            value=f"{kpi_mises['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_mises['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_mises['current_val']:,} ({kpi_mises['yoy_monthly_pct']}% YoY)")
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_sitadel_month}")

    with kpi_cols[2]:
        st.metric(
            label=T[lang_code]["transactions_12m"],
            value=f"{kpi_transactions['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_transactions['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_transactions['current_val']:,} ({kpi_transactions['yoy_monthly_pct']}% YoY)")
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_dvf_month}")

    # Charts are displayed "en milliers" (values / 1000) to match the IGEDD/SDES
    # presentation; the extrema labels therefore no longer divide again (text_divisor=1).
    disp_sitadel = rolling_sitadel.copy()
    for _c in ["Permis", "MisesEnChantier", "Permis_12M", "MisesEnChantier_12M", "Permis_6M", "MisesEnChantier_6M"]:
        disp_sitadel[_c] = disp_sitadel[_c] / 1000.0
    disp_dvf = rolling_dvf.copy()
    for _c in ["Transactions", "Transactions_12M", "Transactions_6M"]:
        disp_dvf[_c] = disp_dvf[_c] / 1000.0

    # Resolve the selected view once: rolling 12m, rolling 6m, or raw monthly.
    _is_rolling = chart_view in (T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"])
    _roll_suffix = "_12M" if chart_view == T[lang_code]["chart_view_rolling"] else "_6M"
    if chart_view == T[lang_code]["chart_view_rolling"]:
        _sub = T[lang_code]["sub_rolling"]
    elif chart_view == T[lang_code]["chart_view_rolling6"]:
        _sub = T[lang_code]["sub_rolling6"]
    else:
        _sub = T[lang_code]["sub_raw"]

    with c_col1:
        # Title adapts to the selected indicators (permits only / starts only / both).
        if show_permis and show_mises:
            _sitadel_title = T[lang_code]["chart_sitadel_main"]
        elif show_permis:
            _sitadel_title = T[lang_code]["chart_sitadel_permis"]
        else:
            _sitadel_title = T[lang_code]["chart_sitadel_mises"]
        st.markdown(
            f"**{_sitadel_title}** "
            f"<span style='color:#6c757d;font-weight:400'>({_sub})</span>",
            unsafe_allow_html=True
        )
        fig1 = go.Figure()
        if _is_rolling:
            _pcol, _mcol = f"Permis{_roll_suffix}", f"MisesEnChantier{_roll_suffix}"
            if show_permis:
                fig1.add_trace(go.Scatter(x=disp_sitadel["Date"], y=disp_sitadel[_pcol], name=T[lang_code]["permis_trace"], line=dict(color=COLOR_BRICK, width=3)))
                find_and_add_extrema_trace(fig1, disp_sitadel, "Date", _pcol, COLOR_BRICK, text_divisor=1)
            if show_mises:
                fig1.add_trace(go.Scatter(x=disp_sitadel["Date"], y=disp_sitadel[_mcol], name=T[lang_code]["mises_trace"], line=dict(color=COLOR_TEXT, width=3, dash='dash')))
                find_and_add_extrema_trace(fig1, disp_sitadel, "Date", _mcol, COLOR_TEXT, text_divisor=1)
            sitadel_last = last_valid_month(disp_sitadel, _pcol if show_permis else _mcol)
        else:
            # Draw raw bars/line unless the user hid them; if nothing at all is selected,
            # keep the raw data so the chart is never empty.
            _draw_raw = show_raw or not (show_ma6 or show_ma12)
            if _draw_raw:
                # Light/translucent bars so overlaid curves (moving averages) stay readable.
                if show_permis:
                    fig1.add_trace(go.Bar(x=disp_sitadel["Date"], y=disp_sitadel["Permis"], name=T[lang_code]["permis_trace"], marker_color=COLOR_BRICK_FILL))
                if show_mises:
                    if show_permis:
                        # Both shown: keep Mises as a line so it reads against the Permis bars.
                        fig1.add_trace(go.Scatter(x=disp_sitadel["Date"], y=disp_sitadel["MisesEnChantier"], name=T[lang_code]["mises_trace"], line=dict(color=COLOR_TEXT, width=2)))
                    else:
                        # Mises alone: display as bars, like the Permis series.
                        fig1.add_trace(go.Bar(x=disp_sitadel["Date"], y=disp_sitadel["MisesEnChantier"], name=T[lang_code]["mises_trace"], marker_color=COLOR_TEXT_FILL))
            sitadel_last = last_valid_month(disp_sitadel, "Permis" if show_permis else "MisesEnChantier")
            # Moving averages (6m and/or 12m) on the raw monthly scale, same axis.
            if show_permis:
                add_moving_average_traces(fig1, disp_sitadel, "Permis", T[lang_code]["permis_trace"],
                                          COLOR_BRICK_DARK, show_ma12, show_ma6, T[lang_code]["ma12_suffix"], T[lang_code]["ma6_suffix"])
            if show_mises:
                add_moving_average_traces(fig1, disp_sitadel, "MisesEnChantier", T[lang_code]["mises_trace"],
                                          COLOR_TEXT_MUTED, show_ma12, show_ma6, T[lang_code]["ma12_suffix"], T[lang_code]["ma6_suffix"])

        # Title is rendered as markdown at the top of this column (above).
        fig1.update_layout(
            xaxis_title="Date",
            yaxis_title="Thousands of dwellings" if lang_code == "EN" else "Milliers de logements",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.caption(
            f"{T[lang_code]['source_label']} : {T[lang_code]['source_sitadel']}  \n"
            f"{T[lang_code]['last_point_label']} : {format_month_year(sitadel_last, lang_code)}"
        )

    with c_col2:
        st.markdown(
            f"**{T[lang_code]['chart_dvf_main']}** "
            f"<span style='color:#6c757d;font-weight:400'>({_sub})</span>",
            unsafe_allow_html=True
        )
        fig2 = go.Figure()
        if _is_rolling:
            _tcol = f"Transactions{_roll_suffix}"
            fig2.add_trace(go.Scatter(x=disp_dvf["Date"], y=disp_dvf[_tcol], name=T[lang_code]["transactions_trace"], line=dict(color=COLOR_GREEN, width=3)))
            find_and_add_extrema_trace(fig2, disp_dvf, "Date", _tcol, COLOR_GREEN, text_divisor=1)
            dvf_last = last_valid_month(disp_dvf, _tcol)
        else:
            _draw_raw = show_raw or not (show_ma6 or show_ma12)
            if _draw_raw:
                # Light/translucent bars so overlaid curves (moving averages) stay readable.
                fig2.add_trace(go.Bar(x=disp_dvf["Date"], y=disp_dvf["Transactions"], name=T[lang_code]["transactions_trace"], marker_color=COLOR_GREEN_FILL))
            dvf_last = last_valid_month(disp_dvf, "Transactions")
            # Moving averages (6m and/or 12m) on the raw monthly scale, same axis.
            add_moving_average_traces(fig2, disp_dvf, "Transactions", T[lang_code]["transactions_trace"],
                                      COLOR_GREEN_DARK, show_ma12, show_ma6, T[lang_code]["ma12_suffix"], T[lang_code]["ma6_suffix"])

        fig2.update_layout(
            xaxis_title="Date",
            yaxis_title="Thousands of transactions" if lang_code == "EN" else "Milliers de transactions",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            f"{T[lang_code]['source_label']} : {T[lang_code]['source_dvf']}  \n"
            f"{T[lang_code]['last_point_label']} : {format_month_year(dvf_last, lang_code)}"
        )

    # --- Monthly comparison by year (grouped bars, like the IGEDD monthly chart) ---
    # Compares the selected months across the years kept by the "Période (années)"
    # filter. Neuf uses the segment-filtered monthly Permis; ancien uses monthly
    # Transactions. Both are shown "en milliers" to match the top charts.
    st.markdown(f"### {T[lang_code]['monthly_compare_title']}")
    st.caption(T[lang_code]["monthly_compare_desc"])

    _month_names = _EN_MONTHS if lang_code == "EN" else _FR_MONTHS
    _month_labels_all = [m.capitalize() for m in _month_names]
    _label_to_num = {lbl: i + 1 for i, lbl in enumerate(_month_labels_all)}

    # Default: the 3 months ending at the last available data point (inclusive), e.g.
    # if the last point is May, default to March / April / May.
    _last_dates = [d for d in [agg_sitadel["Date"].max() if not agg_sitadel.empty else None,
                               agg_dvf["Date"].max() if not agg_dvf.empty else None] if pd.notna(d)]
    _last_month_num = pd.Timestamp(max(_last_dates)).month if _last_dates else 12
    _default_month_nums = sorted(((_last_month_num - k - 1) % 12) + 1 for k in range(3))
    _default_month_labels = [_month_labels_all[m - 1] for m in _default_month_nums]

    selected_month_labels = st.multiselect(
        T[lang_code]["month_select_label"],
        options=_month_labels_all,
        default=_default_month_labels,   # 3 months up to and including the last data point
        key="month_compare"
    )
    selected_month_nums = sorted(_label_to_num[l] for l in selected_month_labels)
    ordered_month_labels = [_month_labels_all[m - 1] for m in selected_month_nums]

    # Neuf metric choice (applies to the left chart only). Its own left-half row keeps
    # the two monthly charts below vertically aligned.
    mt_col1, _mt_col2 = st.columns(2)
    with mt_col1:
        _monthly_metric = st.radio(
            T[lang_code]["monthly_metric_label"],
            [T[lang_code]["permis_trace"], T[lang_code]["mises_trace"]],
            horizontal=True, key="monthly_metric"
        )
    if _monthly_metric == T[lang_code]["mises_trace"]:
        _neuf_col, _neuf_title = "MisesEnChantier", T[lang_code]["chart_sitadel_monthly_mises"]
    else:
        _neuf_col, _neuf_title = "Permis", T[lang_code]["chart_sitadel_monthly_permis"]

    if not selected_month_nums:
        st.info(T[lang_code]["no_month_selected"])
    else:
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(
                f"**{_neuf_title}** "
                f"<span style='color:#6c757d;font-weight:400'>({T[lang_code]['sub_monthly']})</span>",
                unsafe_allow_html=True
            )
            figm1 = build_monthly_year_bars(agg_sitadel, _neuf_col,
                                            selected_month_nums, ordered_month_labels, (230, 74, 25))
            figm1.update_layout(yaxis_title="Thousands of dwellings" if lang_code == "EN"
                                else "Milliers de logements")
            st.plotly_chart(figm1, use_container_width=True)
            st.caption(f"{T[lang_code]['source_label']} : {T[lang_code]['source_sitadel']}")
        with m_col2:
            st.markdown(
                f"**{T[lang_code]['chart_dvf_monthly_main']}** "
                f"<span style='color:#6c757d;font-weight:400'>({T[lang_code]['sub_monthly']})</span>",
                unsafe_allow_html=True
            )
            figm2 = build_monthly_year_bars(agg_dvf, "Transactions",
                                            selected_month_nums, ordered_month_labels, (56, 142, 60))
            figm2.update_layout(yaxis_title="Thousands of transactions" if lang_code == "EN"
                                else "Milliers de transactions")
            st.plotly_chart(figm2, use_container_width=True)
            st.caption(f"{T[lang_code]['source_label']} : {T[lang_code]['source_dvf']}")

# ==============================================================================
# TAB 2: CONTEXTE MACRO ÉCONOMIQUE ET FINANCEMENT
# ==============================================================================
with tabs[1]:
    st.header(T[lang_code]["macro_context"])
    st.write(T[lang_code]["macro_desc"])

    # --- Macro Indicators Row (INSEE household confidence + Credit Logement rates) ---
    # Rate-series selector lives in its own row ABOVE the two charts so that both
    # chart titles line up. It sits in the right half, above the rates chart it controls.
    _sel_left, _sel_right = st.columns(2)
    with _sel_right:
        # Three financing-rate series on one chart, each toggled by a checkbox:
        # housing-loan rate (BdF/BCE), 3-month Euribor and 10-year OAT (both ECB).
        st.caption(T[lang_code]["rate_series_label"])
        _rk1, _rk2, _rk3 = st.columns(3)
        with _rk1:
            show_credit_rate = st.checkbox(T[lang_code]["credit_trace"], value=True, key="rate_credit")
        with _rk2:
            show_euribor = st.checkbox(T[lang_code]["euribor_trace"], value=True, key="rate_euribor")
        with _rk3:
            show_oat = st.checkbox(T[lang_code]["oat_trace"], value=True, key="rate_oat")

    macro_cols = st.columns(2)

    with macro_cols[0]:
        macro_chart_title(T[lang_code]["chart_insee_title"], T[lang_code]["chart_insee_sub"])
        fig_insee = go.Figure()
        fig_insee.add_trace(go.Scatter(x=df_macro["Date"], y=df_macro["Insee_Confiance_Menages"], name=T[lang_code]["insee_trace"], line=dict(color=COLOR_BRICK, width=2)))
        fig_insee.add_hline(y=100, line_dash="dash", line_color="grey", annotation_text=T[lang_code]["chart_insee_avg"])
        add_last_value_label(fig_insee, df_macro, "Date", "Insee_Confiance_Menages", COLOR_BRICK, lang_code, decimals=0)
        apply_macro_chart_layout(fig_insee, "Indice (base 100)" if lang_code == "FR" else "Index (base 100)")
        st.plotly_chart(fig_insee, use_container_width=True)
        st.caption(T[lang_code]["source_insee_full"])

    with macro_cols[1]:
        macro_chart_title(T[lang_code]["chart_rates_title"], T[lang_code]["chart_rates_sub"])
        fig_rates = go.Figure()
        _rate_srcs = []
        if show_credit_rate:
            fig_rates.add_trace(go.Scatter(x=df_macro["Date"], y=df_macro["Credit_Logement_Taux_Interet"],
                                           name=T[lang_code]["credit_trace"], line=dict(color=COLOR_TEXT, width=2)))
            add_last_value_label(fig_rates, df_macro, "Date", "Credit_Logement_Taux_Interet", COLOR_TEXT, lang_code)
            _rate_srcs.append(T[lang_code]["source_rate_full"])
        if show_euribor and "Euribor_3M" in df_macro.columns:
            fig_rates.add_trace(go.Scatter(x=df_macro["Date"], y=df_macro["Euribor_3M"],
                                           name=T[lang_code]["euribor_trace"], line=dict(color=COLOR_BLUE, width=2)))
            add_last_value_label(fig_rates, df_macro, "Date", "Euribor_3M", COLOR_BLUE, lang_code)
            _rate_srcs.append(T[lang_code]["source_euribor_full"])
        if show_oat and "OAT_10ans" in df_macro.columns:
            fig_rates.add_trace(go.Scatter(x=df_macro["Date"], y=df_macro["OAT_10ans"],
                                           name=T[lang_code]["oat_trace"], line=dict(color=COLOR_GREEN, width=2)))
            add_last_value_label(fig_rates, df_macro, "Date", "OAT_10ans", COLOR_GREEN, lang_code)
            _rate_srcs.append(T[lang_code]["source_oat_full"])
        apply_macro_chart_layout(fig_rates, "%" if lang_code == "EN" else "Taux d'intérêt (%)")
        st.plotly_chart(fig_rates, use_container_width=True)
        if _rate_srcs:
            st.caption("  \n".join(_rate_srcs))

    # --- Bottom row: two extra INSEE context charts ------------------------------
    #  Left : household housing-purchase intentions (Camme survey). Shown standardized
    #         ("centrées-réduites": deviation from mean divided by std) to match the
    #         INSEE presentation, with a 0 reference line.
    #  Right: ILO unemployment rate. The source series is QUARTERLY, so we drop the NaN
    #         off-quarter months and plot the quarter points connected into a line.
    st.markdown("---")
    ctx_cols = st.columns(2)

    with ctx_cols[0]:
        macro_chart_title(T[lang_code]["chart_intentions_title"], T[lang_code]["chart_intentions_sub"])
        fig_int = go.Figure()
        if "Intentions_Achat_Logement" in df_macro.columns:
            _int = df_macro.dropna(subset=["Intentions_Achat_Logement"]).copy()
            _mu = _int["Intentions_Achat_Logement"].mean()
            _sd = _int["Intentions_Achat_Logement"].std()
            if pd.notna(_sd) and _sd > 0:
                _int["_z"] = (_int["Intentions_Achat_Logement"] - _mu) / _sd
                fig_int.add_trace(go.Scatter(
                    x=_int["Date"], y=_int["_z"],
                    name=T[lang_code]["intentions_trace"],
                    line=dict(color=COLOR_BLUE, width=2)))
                fig_int.add_hline(y=0, line_dash="dash", line_color="grey")
        apply_macro_chart_layout(fig_int, "Écarts-types" if lang_code == "FR" else "Standard deviations")
        st.plotly_chart(fig_int, use_container_width=True)
        st.caption(T[lang_code]["source_intentions_full"])

    with ctx_cols[1]:
        macro_chart_title(T[lang_code]["chart_chomage_title"], T[lang_code]["chart_chomage_sub"])
        fig_cho = go.Figure()
        if "Taux_Chomage_BIT" in df_macro.columns:
            _cho = df_macro.dropna(subset=["Taux_Chomage_BIT"]).copy()
            fig_cho.add_trace(go.Scatter(
                x=_cho["Date"], y=_cho["Taux_Chomage_BIT"],
                name=T[lang_code]["chomage_trace"],
                line=dict(color=COLOR_BRICK, width=2)))
            add_last_value_label(fig_cho, _cho, "Date", "Taux_Chomage_BIT",
                                 COLOR_BRICK, lang_code, decimals=1)
        apply_macro_chart_layout(fig_cho, "%")
        st.plotly_chart(fig_cho, use_container_width=True)
        st.caption(T[lang_code]["source_chomage_full"])


# ==============================================================================
# TAB 3: SIMULATION TIME LAG
# ==============================================================================
with tabs[2]:
    st.header(T[lang_code]["timelag_header"])
    st.write(T[lang_code]["timelag_desc"])
    
    col_sim1, col_sim2 = st.columns([1, 2])
    
    with col_sim1:
        st.markdown(T[lang_code]["sim_params"])
        
        # 1. Choose indicator to lag
        indicator_category = st.selectbox(
            T[lang_code]["src_indicator"],
            ["Construction (SIT@DEL)", "Transactions (DVF)", "Indicateur Macro"] if lang_code == "FR" else ["Construction (SIT@DEL)", "Transactions (DVF)", "Macro Indicator"]
        )
        
        internal_category = "Construction (SIT@DEL)"
        if indicator_category in ["Transactions (DVF)"]:
            internal_category = "Transactions (DVF)"
        elif indicator_category in ["Indicateur Macro", "Macro Indicator"]:
            internal_category = "Indicateur Macro"
            
        if internal_category == "Construction (SIT@DEL)":
            ind_sub_type = st.selectbox(T[lang_code]["housing_type"], df_sitadel["Type"].unique().tolist())
            ind_metric = st.selectbox(T[lang_code]["metric_sitadel"], ["Permis", "MisesEnChantier"] if lang_code == "FR" else ["Permis", "MisesEnChantier"])
            
            raw_ind_df = filtered_sitadel[filtered_sitadel["Type"] == ind_sub_type]
            raw_ind_df = raw_ind_df.groupby("Date")[ind_metric].sum().reset_index()
            raw_ind_df = raw_ind_df.rename(columns={ind_metric: "Val"})
            ind_label = f"{ind_metric} - {ind_sub_type}"
            
        elif internal_category == "Transactions (DVF)":
            # Single national IGEDD "ventes anciennes" series — no sub-type choice.
            raw_ind_df = filtered_dvf.groupby("Date")["Transactions"].sum().reset_index()
            raw_ind_df = raw_ind_df.rename(columns={"Transactions": "Val"})
            ind_label = "Ventes anciennes (IGEDD)"
            
        else: # Macro
            # Friendly label -> df_macro column. Only columns actually present are
            # offered (Euribor/OAT are optional and may be absent from an uploaded CSV).
            _macro_options = {
                T[lang_code]["insee_trace"]: "Insee_Confiance_Menages",
                T[lang_code]["credit_trace"]: "Credit_Logement_Taux_Interet",
                T[lang_code]["euribor_trace"]: "Euribor_3M",
                T[lang_code]["oat_trace"]: "OAT_10ans",
            }
            _macro_options = {lbl: col for lbl, col in _macro_options.items() if col in df_macro.columns}
            _macro_choice = st.selectbox(T[lang_code]["indicator_label"], list(_macro_options.keys()))
            ind_metric = _macro_options[_macro_choice]

            # Drop months the source doesn't cover (e.g. rate before 2003) so NaN don't
            # pollute the rolling sum / correlation downstream.
            raw_ind_df = df_macro[["Date", ind_metric]].dropna(subset=[ind_metric]).copy()
            raw_ind_df = raw_ind_df.rename(columns={ind_metric: "Val"})
            ind_label = _macro_choice
            
        # Smooth indicator with 12M rolling
        smooth_ind = st.checkbox(T[lang_code]["smooth_ind"], value=True)
        if smooth_ind:
            raw_ind_df["Val_Raw"] = raw_ind_df["Val"]
            raw_ind_df["Val"] = raw_ind_df["Val_Raw"].rolling(window=12, min_periods=1).sum()
            ind_label += " (12M)" if lang_code == "EN" else " (Cumul 12M)"
            
        # 2. Time Lag Slider
        time_lag = st.slider(
            T[lang_code]["time_lag_label"],
            min_value=-24,
            max_value=24,
            value=14,
            help=T[lang_code]["time_lag_help"]
        )
        
        # 3. Choose product sales to compare with
        selected_product = st.selectbox(
            T[lang_code]["sales_compare"],
            df_sales["Product"].unique().tolist()
        )
        
        # Aggregate local Sales
        agg_sales = filtered_sales[filtered_sales["Product"] == selected_product]
        agg_sales = agg_sales.groupby("Date")["Sales_Units"].sum().reset_index()
        
        st.markdown("---")
        # 4. Auto-correlation analysis trigger
        st.subheader(T[lang_code]["optimal_lag_search"])
        st.write(T[lang_code]["optimal_lag_desc"])
        
        if st.button(T[lang_code]["btn_calc_optimal"], key="btn_corr"):
            with st.spinner("Analyse..." if lang_code == "FR" else "Analyzing..."):
                corr_res = sim.find_optimal_lag(raw_ind_df, agg_sales, "Val", "Sales_Units")
                
                st.session_state["corr_results"] = corr_res
                st.session_state["optimal_lag"] = corr_res["optimal_lag"]
                st.session_state["max_correlation"] = corr_res["max_correlation"]
                
        # Display optimal correlation result if computed
        if "corr_results" in st.session_state:
            opt_lag = st.session_state["optimal_lag"]
            max_r = st.session_state["max_correlation"]
            st.success(f"**{T[lang_code]['optimal_found']} : {opt_lag} {'mois' if lang_code == 'FR' else 'months'}**")
            st.metric(T[lang_code]["max_corr"], f"r = {max_r}")
            
            # Option to apply the optimal lag
            if st.button(T[lang_code]["btn_apply_lag"].format(lag=opt_lag)):
                time_lag = opt_lag
                
    with col_sim2:
        st.markdown(f"### {T[lang_code]['comp_view']}")
        
        # Create shifted indicator
        shifted_ind_df = sim.shift_indicator(raw_ind_df, "Date", "Val", time_lag)
        col_shifted_val = f"Val_shifted_{time_lag}"
        
        fig_sim = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Trace 1: Original Indicator (Historical)
        fig_sim.add_trace(
            go.Scatter(
                x=raw_ind_df["Date"], 
                y=raw_ind_df["Val"], 
                name=f"{ind_label} (Original)",
                line=dict(color=COLOR_GRID, width=2)
            ),
            secondary_y=False
        )
        
        # Trace 2: Shifted Indicator (Leading Indicator)
        fig_sim.add_trace(
            go.Scatter(
                x=shifted_ind_df["Date"], 
                y=shifted_ind_df[col_shifted_val], 
                name=f"{ind_label} (Shifted +{time_lag}m)",
                line=dict(color=COLOR_BRICK, width=3)
            ),
            secondary_y=False
        )
        
        # Trace 3: Sales (Actual)
        fig_sim.add_trace(
            go.Scatter(
                x=agg_sales["Date"], 
                y=agg_sales["Sales_Units"], 
                name=f"Sales - {selected_product}",
                line=dict(color=COLOR_TEXT, width=3)
            ),
            secondary_y=True
        )
        
        fig_sim.update_layout(
            title=T[lang_code]["alignment_title"].format(ind=ind_label, lag=time_lag),
            xaxis_title="Date" if lang_code == "EN" else "Temps",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        fig_sim.update_yaxes(title_text=T[lang_code]["scale_ind"], secondary_y=False)
        fig_sim.update_yaxes(title_text=T[lang_code]["scale_sales"], secondary_y=True)
        
        # Highlight Future Forecasting Zone
        max_sales_date = agg_sales["Date"].max()
        fig_sim.add_vrect(
            x0=max_sales_date, x1=shifted_ind_df["Date"].max(),
            fillcolor=COLOR_BRICK_ZONE, opacity=0.5,
            layer="below", line_width=0,
            annotation_text=T[lang_code]["zone_prev"], annotation_position="top left"
        )
        
        st.plotly_chart(fig_sim, use_container_width=True)
        # Sales are always synthetic; the compared indicator may be real (DVF) or synthetic.
        st.caption(T[lang_code]["synthetic_note"])

        # Save shifted data in session state for export later
        st.session_state["shifted_export_df"] = shifted_ind_df
        st.session_state["shifted_export_col"] = col_shifted_val
        st.session_state["shifted_export_name"] = f"KF_SITADEL_{ind_label.replace(' ', '_').upper()}_LAG{time_lag}"
        # All three indicator sources are now real: SIT@DEL construction (manual CSV),
        # DVF/IGEDD transactions, and macro (INSEE confidence + Banque de France rate).
        # The exported shifted indicator is therefore never synthetic.
        st.session_state["shifted_export_synthetic"] = False
        
        # Correlation distribution bar chart if computed
        if "corr_results" in st.session_state:
            st.markdown(f"### {T[lang_code]['corr_dist_title']}")
            results = st.session_state["corr_results"]
            
            fig_bar = go.Figure()
            colors = [COLOR_GRID] * len(results["lags"])
            opt_idx = results["lags"].index(results["optimal_lag"])
            colors[opt_idx] = COLOR_BRICK
            
            fig_bar.add_trace(
                go.Bar(
                    x=results["lags"],
                    y=results["correlations"],
                    marker_color=colors,
                    name="Correlation"
                )
            )
            fig_bar.update_layout(
                xaxis_title="Lags (months)" if lang_code == "EN" else "Décalage (Lags en mois)",
                yaxis_title="Pearson Correlation (r)" if lang_code == "EN" else "Coefficient de corrélation de Pearson (r)",
                template="plotly_white",
                title=T[lang_code]["best_align_title"].format(lag=results["optimal_lag"], r=results["max_correlation"])
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption(T[lang_code]["synthetic_note"])


# ==============================================================================
# TAB 4: MODÈLE COMPOSITE
# ==============================================================================
with tabs[3]:
    st.header(T[lang_code]["composite_header"])
    st.write(T[lang_code]["composite_desc"])
    
    st.markdown(f"#### {T[lang_code]['composite_config']}")
    
    comp_cols = st.columns(3)
    
    with comp_cols[0]:
        st.subheader(T[lang_code]["comp1_title"])
        comp1_type = st.selectbox("1. Type", df_sitadel["Type"].unique().tolist(), index=0)
        comp1_metric = st.selectbox("1. Metric", ["Permis", "MisesEnChantier"], index=0)
        comp1_lag = st.number_input(T[lang_code]["comp_lag"], min_value=0, max_value=24, value=12, key="c1_lag")
        comp1_weight = st.slider(T[lang_code]["comp_weight"], 0.0, 1.0, 0.6, key="c1_w")
        
        df_c1 = filtered_sitadel[filtered_sitadel["Type"] == comp1_type].groupby("Date")[comp1_metric].sum().reset_index()
        
    with comp_cols[1]:
        st.subheader(T[lang_code]["comp2_title"])
        comp2_metric = "Insee_Confiance_Menages"
        st.info("INSEE Consumer Confidence" if lang_code == "EN" else "Moral des ménages (Confiance)")
        comp2_lag = st.number_input(T[lang_code]["comp_lag"], min_value=0, max_value=24, value=4, key="c2_lag")
        comp2_weight = st.slider(T[lang_code]["comp_weight"], 0.0, 1.0, 0.2, key="c2_w")
        
        df_c2 = df_macro[["Date", comp2_metric]].copy()
        
    with comp_cols[2]:
        st.subheader(T[lang_code]["comp3_title"])
        comp3_metric = "Credit_Logement_Taux_Interet"
        st.info("Housing Loan Nominal Interest Rates" if lang_code == "EN" else "Taux d'intérêt moyen du crédit")
        comp3_lag = st.number_input(T[lang_code]["comp_lag"], min_value=0, max_value=24, value=6, key="c3_lag")
        comp3_weight = st.slider(T[lang_code]["comp_weight"], 0.0, 1.0, 0.2, key="c3_w")
        comp3_invert = st.checkbox(T[lang_code]["comp_invert"], value=True, help=T[lang_code]["comp_invert_help"])
        
        df_c3 = df_macro[["Date", comp3_metric]].copy()
        
    components = [
        {
            'df': df_c1,
            'value_col': comp1_metric,
            'lag': comp1_lag,
            'weight': comp1_weight,
            'invert': False
        },
        {
            'df': df_c2,
            'value_col': comp2_metric,
            'lag': comp2_lag,
            'weight': comp2_weight,
            'invert': False
        },
        {
            'df': df_c3,
            'value_col': comp3_metric,
            'lag': comp3_lag,
            'weight': comp3_weight,
            'invert': comp3_invert
        }
    ]
    
    df_composite = sim.create_composite_indicator(components)
    
    bench_product = st.selectbox(
        T[lang_code]["bench_product"],
        df_sales["Product"].unique().tolist(),
        key="comp_bench_product"
    )
    df_sales_bench = filtered_sales[filtered_sales["Product"] == bench_product].groupby("Date")["Sales_Units"].sum().reset_index()
    
    # --- AUTOMATED PARAMETER OPTIMIZATION ---
    st.markdown("---")
    st.subheader("🎯 Optimisation Automatique des Paramètres" if lang_code == "FR" else "🎯 Automated Parameter Optimization")
    st.write(
        "Lancer un algorithme de recherche pour trouver la combinaison parfaite de coefficients (Poids et Lags) "
        "qui maximise la corrélation linéaire de Pearson avec vos ventes." 
        if lang_code == "FR" else 
        "Run an algorithm to find the perfect combination of coefficients (Weights and Lags) "
        "that maximizes Pearson correlation with your sales."
    )
    
    if st.button("Trouver les meilleurs coefficients (Lag, Poids...)" if lang_code == "FR" else "Find Best Coefficients (Lag, Weight...)", key="btn_optimize_composite"):
        with st.spinner("Recherche de la meilleure combinaison parmi 9504 configurations..." if lang_code == "FR" else "Searching best combination among 9504 configurations..."):
            opt_res = sim.optimize_composite_parameters(
                df_c1=df_c1, col_c1=comp1_metric,
                df_c2=df_c2, col_c2=comp2_metric,
                df_c3=df_c3, col_c3=comp3_metric,
                df_sales=df_sales_bench,
                invert_c3=comp3_invert
            )
            st.session_state["opt_composite_res"] = opt_res
            
    if "opt_composite_res" in st.session_state:
        res = st.session_state["opt_composite_res"]
        st.success(
            f"**Meilleure configuration trouvée !** Corrélation maximale : **r = {res['max_correlation']:.3f}**"
            if lang_code == "FR" else
            f"**Best configuration found!** Maximum correlation: **r = {res['max_correlation']:.3f}**"
        )
        
        c_opt1, c_opt2, c_opt3 = st.columns(3)
        with c_opt1:
            st.markdown(f"**SIT@DEL (Comp. 1) :**")
            st.write(f"Lag : **{res['best_lags'][0]}** mois")
            st.write(f"Poids / Weight : **{res['best_weights'][0]}**")
        with c_opt2:
            st.markdown(f"**INSEE (Comp. 2) :**")
            st.write(f"Lag : **{res['best_lags'][1]}** mois")
            st.write(f"Poids / Weight : **{res['best_weights'][1]}**")
        with c_opt3:
            st.markdown(f"**Taux / Rates (Comp. 3) :**")
            st.write(f"Lag : **{res['best_lags'][2]}** mois")
            st.write(f"Poids / Weight : **{res['best_weights'][2]}**")
            
        col_app1, col_app2 = st.columns([1, 2])
        with col_app1:
            if st.button("🚀 Appliquer ces coefficients" if lang_code == "FR" else "🚀 Apply these coefficients", key="btn_apply_opt_params"):
                st.session_state["opt_c1_lag"] = int(res["best_lags"][0])
                st.session_state["opt_c1_w"] = float(res["best_weights"][0])
                st.session_state["opt_c2_lag"] = int(res["best_lags"][1])
                st.session_state["opt_c2_w"] = float(res["best_weights"][1])
                st.session_state["opt_c3_lag"] = int(res["best_lags"][2])
                st.session_state["opt_c3_w"] = float(res["best_weights"][2])
                st.session_state["opt_applied"] = True
                st.rerun()
        with col_app2:
            st.info(
                "💡 **Note :** Cliquez sur le bouton pour appliquer automatiquement ces coefficients aux curseurs ci-dessus."
                if lang_code == "FR" else
                "💡 **Note :** Click the button to automatically apply these coefficients to the sliders above."
            )
    
    # Create master plot
    fig_comp = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 1. Composite Indicator
    fig_comp.add_trace(
        go.Scatter(
            x=df_composite["Date"],
            y=df_composite["Composite_Indicator"],
            name="🧪 Composite Indicator" if lang_code == "EN" else "🧪 Indicateur Composite",
            line=dict(color=COLOR_BRICK, width=4)
        ),
        secondary_y=False
    )
    
    # 2. Benchmark Sales
    fig_comp.add_trace(
        go.Scatter(
            x=df_sales_bench["Date"],
            y=df_sales_bench["Sales_Units"],
            name=f"Sales - {bench_product}",
            line=dict(color=COLOR_TEXT, width=3)
        ),
        secondary_y=True
    )
    
    fig_comp.update_layout(
        title=T[lang_code]["composite_plot_title"],
        xaxis_title="Date",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig_comp.update_yaxes(title_text=T[lang_code]["composite_axis"], secondary_y=False)
    fig_comp.update_yaxes(title_text=T[lang_code]["sales_axis"], secondary_y=True)
    
    # Shaded forecast area
    max_sales_bench_date = df_sales_bench["Date"].max()
    fig_comp.add_vrect(
        x0=max_sales_bench_date, x1=df_composite["Date"].max(),
        fillcolor=COLOR_BRICK_ZONE, opacity=0.5,
        layer="below", line_width=0,
        annotation_text=T[lang_code]["zone_prev"], annotation_position="top left"
    )
    
    st.plotly_chart(fig_comp, use_container_width=True)
    st.caption(T[lang_code]["synthetic_note"])

    # Measure correlation between composite indicator and historical sales
    merged_comp_sales = pd.merge(df_sales_bench, df_composite, on="Date", how="inner")
    if len(merged_comp_sales) > 5:
        r_composite = merged_comp_sales["Composite_Indicator"].corr(merged_comp_sales["Sales_Units"])
        st.info(T[lang_code]["composite_perf"].format(product=bench_product, r=r_composite))
    
    # Save composite data in session state for export
    st.session_state["composite_export_df"] = df_composite
    st.session_state["composite_export_col"] = "Composite_Indicator"
    st.session_state["composite_export_name"] = f"KF_COMPOSITE_{bench_product.replace(' ', '_').upper()}"
    # The composite blends synthetic indicators (SIT@DEL / sales / macro), so it is synthetic.
    st.session_state["composite_export_synthetic"] = True


# ==============================================================================
# TAB 5: EXPORT SAP IBP
# ==============================================================================
with tabs[4]:
    st.header(T[lang_code]["export_header"])
    st.write(T[lang_code]["export_desc"])
    
    export_source = st.radio(
        T[lang_code]["export_source_label"],
        [T[lang_code]["src_simple_lag"], T[lang_code]["src_composite"]],
        horizontal=True
    )
    
    source_available = False
    
    if export_source == T[lang_code]["src_simple_lag"]:
        if "shifted_export_df" in st.session_state:
            export_raw_df = st.session_state["shifted_export_df"]
            val_col_name = st.session_state["shifted_export_col"]
            default_kf_name = st.session_state["shifted_export_name"]
            export_is_synthetic = st.session_state.get("shifted_export_synthetic", True)
            source_available = True
        else:
            st.warning(T[lang_code]["no_simple_lag"])
    else:
        if "composite_export_df" in st.session_state:
            export_raw_df = st.session_state["composite_export_df"]
            val_col_name = st.session_state["composite_export_col"]
            default_kf_name = st.session_state["composite_export_name"]
            export_is_synthetic = st.session_state.get("composite_export_synthetic", True)
            source_available = True
        else:
            st.warning(T[lang_code]["no_composite"])
            
    if source_available:
        st.success(T[lang_code]["export_ready"].format(count=len(export_raw_df)))
        
        col_exp1, col_exp2 = st.columns([1, 2])
        
        with col_exp1:
            st.markdown(T[lang_code]["export_params"])
            
            kf_name = st.text_input(T[lang_code]["kf_name_label"], value=default_kf_name)
            
            granularity = st.selectbox(T[lang_code]["granularity_label"], ["Monthly", "Weekly"] if lang_code == "FR" else ["Monthly", "Weekly"])
            
            # Convert internal granularity name
            internal_granularity = "Monthly"
            if granularity in ["Weekly", "Hebdomadaire"]:
                internal_granularity = "Weekly"
                
            date_format = st.selectbox(
                T[lang_code]["date_format_label"],
                ["YYYY-MM-DD", "YYYYMM", "DD/MM/YYYY"]
            )
            
            delimiter = st.selectbox(
                T[lang_code]["delimiter_label"],
                ["; (Standard Europe)", ", (Standard US)", "Onglet (Tabulation)"] if lang_code == "FR" else ["; (Standard Europe)", ", (Standard US)", "Tab (Tabulation)"],
                index=0
            )
            delim_char = ";" if ";" in delimiter else ("," if "," in delimiter else "\t")
            
            location_val = st.text_input(T[lang_code]["locid_default"], value="FR_DEFAULT")
            
            st.markdown(T[lang_code]["header_mapping"])
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                header_period = st.text_input(T[lang_code]["header_period"], value="PERIODID0")
                header_loc = st.text_input(T[lang_code]["header_loc"], value="LOCID")
            with col_h2:
                header_ind = st.text_input(T[lang_code]["header_ind"], value="PRDID")
                header_val = st.text_input(T[lang_code]["header_val"], value="KEYFIGUREVALUE")
                
            custom_headers = {
                'PERIOD': header_period,
                'LOCATION': header_loc,
                'INDICATOR': header_ind,
                'VALUE': header_val
            }
            
        with col_exp2:
            st.markdown(f"### {T[lang_code]['export_preview_title']}")
            
            csv_str, export_df = exp.format_for_sap_ibp(
                df_indicator=export_raw_df,
                indicator_name=kf_name,
                date_col="Date",
                value_col=val_col_name,
                location_val=location_val,
                time_granularity=internal_granularity,
                date_format=date_format,
                delimiter=delim_char,
                custom_headers=custom_headers
            )
            
            st.write(T[lang_code]["export_rows_desc"].format(count=len(export_df)))
            st.dataframe(export_df.head(10), use_container_width=True)
            if export_is_synthetic:
                st.caption(T[lang_code]["synthetic_note"])
            
            st.markdown("---")
            st.download_button(
                label=T[lang_code]["btn_download_csv"],
                data=csv_str,
                file_name=f"{kf_name.lower()}_export.csv",
                mime="text/csv"
            )
            
            st.markdown(T[lang_code]["sap_instructions"])


# ==============================================================================
# TAB 6: DONNÉES SOURCE
# ==============================================================================
with tabs[5]:
    st.header(T[lang_code]["source_header"])
    st.write(T[lang_code]["source_desc"])
    
    st.markdown(f"### {T[lang_code]['source_status']}")
    
    db_cat_opts = ["SIT@DEL (Construction neuve)", "DVF (Transactions immobilières)", "Indicateurs Macro", "Ventes réelles"] if lang_code == "FR" else ["SIT@DEL (New Construction)", "DVF (Real Estate Transactions)", "Macro Indicators", "Actual Sales"]
    db_cat = st.selectbox(
        T[lang_code]["select_db_view"],
        db_cat_opts
    )
    
    internal_cat = "sitadel"
    if db_cat in ["DVF (Transactions immobilières)", "DVF (Real Estate Transactions)"]:
        internal_cat = "dvf"
    elif db_cat in ["Indicateurs Macro", "Macro Indicators"]:
        internal_cat = "macro"
    elif db_cat in ["Ventes réelles", "Actual Sales"]:
        internal_cat = "sales"
        
    if internal_cat == "sitadel":
        display_df = df_sitadel
        req_cols = ["Date", "Region", "Department", "Type", "Permis", "MisesEnChantier"]
    elif internal_cat == "dvf":
        display_df = df_dvf
        req_cols = ["Date", "Region", "Department", "Type", "Transactions"]
    elif internal_cat == "macro":
        display_df = df_macro
        req_cols = ["Date", "Insee_Confiance_Menages", "Credit_Logement_Taux_Interet"]
    else:
        display_df = df_sales
        req_cols = ["Date", "Region", "Department", "Product", "Sales_Units"]
        
    col_db1, col_db2 = st.columns([2, 1])
    
    with col_db1:
        st.write(T[lang_code]["db_preview_label"].format(name=internal_cat.upper(), count=len(display_df)))
        st.dataframe(display_df.head(100), use_container_width=True)
        if internal_cat not in ("dvf", "sitadel", "macro"):
            st.caption(T[lang_code]["synthetic_note"])
        
        csv_template = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=T[lang_code]["btn_download_template"].format(name=internal_cat),
            data=csv_template,
            file_name=f"{internal_cat}_template.csv",
            mime="text/csv"
        )
        
    with col_db2:
        st.markdown(f"### {T[lang_code]['upload_new_data']}")
        st.write(T[lang_code]["upload_desc"].format(name=internal_cat.upper()))
        st.info(f"**{T[lang_code]['required_cols']}** {', '.join(req_cols)}")
        
        uploaded_file = st.file_uploader(T[lang_code]["file_uploader_label"].format(name=internal_cat.upper()), type="csv")
        
        if uploaded_file is not None:
            if st.button(T[lang_code]["btn_import_overwrite"].format(name=internal_cat.upper()), key=f"btn_up_{internal_cat}"):
                success, msg = dm.update_with_custom_csv(internal_cat, uploaded_file)
                if success:
                    st.success(msg)
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.error(msg)
                    
        st.markdown("---")
        st.subheader(T[lang_code]["reset_title"])
        st.write(T[lang_code]["reset_desc"])
        if st.button(T[lang_code]["btn_reset_all"], key="btn_reset_all"):
            with st.spinner(T[lang_code]["reset_spinner"]):
                dm.load_or_generate_all(force_regenerate=True)
                st.cache_resource.clear()
                st.success(T[lang_code]["reset_success"])
                st.rerun()

    # --- Section: rebuild "ventes dans l'ancien" from the IGEDD national file ---
    st.markdown("---")
    st.header(T[lang_code]["igedd_header"])
    st.write(T[lang_code]["igedd_desc"])

    if st.button(T[lang_code]["igedd_btn"], key="btn_igedd_import"):
        with st.spinner(T[lang_code]["igedd_spinner"]):
            success, msg = dm.ensure_dvf_ancien(force_rebuild=True)
            if success:
                st.success(msg)
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error(msg)
