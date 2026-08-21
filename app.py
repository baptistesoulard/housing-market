import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

from data_manager import DataManager
import analysis as ana
import queries as q          # couche SQL DuckDB partagée (moteur de calcul)
import simulation as sim
import forecast as fc
import actualites as actu

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
    # A first run without a built data/ventes_ancien.csv triggers the IGEDD
    # reconstruction; show a spinner so the app isn't seen as frozen.
    if not os.path.exists(dm.paths["ventes_ancien"]):
        with st.spinner("Construction des ventes de logements anciens (IGEDD)…"):
            dm.load_or_generate_all()
    else:
        dm.load_or_generate_all()
    return dm

dm = get_data_manager()

@st.cache_resource
def get_connection():
    """Connexion DuckDB (une vue par dataset) sur les Parquet de l'entrepôt.

    `refresh=False` : get_data_manager() vient de reconstruire les CSV et les Parquet,
    inutile de le refaire. Les vues lisent les fichiers à la demande, donc la connexion
    mise en cache reste valable après une régénération — et `st.cache_resource.clear()`
    (bouton de reset) la rouvre de toute façon.
    """
    return q.open_warehouse(refresh=False)

con = get_connection()

def _data_signature():
    """Freshness key of the persisted datasets, used as the cache key below so a plain
    rerun (moving a slider) reuses the in-memory frames instead of re-reading and
    re-validating everything. `DataManager.data_signature()` keys on the file each dataset
    is actually READ from — the typed Parquet, or the CSV when the Parquet is missing or
    older — so the cache also drops when a refresh flips which of the two wins. Writing
    the warehouse happens only in get_data_manager (once per session / cache clear) or on
    an explicit rebuild button."""
    return dm.data_signature()

@st.cache_data(show_spinner=False)
def _load_frames(signature):
    # `signature` (warehouse freshness key) is the only cache key; `dm` is a stable global.
    return dm.read_frames()

# Load datasets (national-level series), cached on the source files' mtimes.
df_sitadel, df_ventes_ancien, df_macro, df_sales, df_revenue, df_ecln, df_company_sales = _load_frames(_data_signature())

# Untouched full-history macro (before the year slicer below). The affordability index
# rebases borrowing capacity to its 2015 mean from the FULL history, so the sidebar year
# slicer never moves that base.
df_macro_full = df_macro

# Les alias df_sitadel_full / df_ventes_ancien_full ont disparu avec les phases 2 et 4 :
# les cartes « Chiffres Clés » comme la série pilote de la prévision viennent maintenant de
# l'entrepôt, qui est par nature l'historique complet — donc indépendant du slicer et du
# sélecteur de segment, ce que ces copies servaient à garantir.
# Full-history macro & revenue for the forecast models (they must not depend on the slicer).
df_revenue_full = df_revenue
# Full-history ECLN for the slicer-independent headline cards (Synthèse & Marché du neuf).
df_ecln_full = df_ecln
# Full-history user-imported company sales (forecast propagation uses the untouched series).
df_company_sales_full = df_company_sales

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

def _L(fr, en):
    """Inline bilingual string for the newer tabs (Prix & Accessibilité / ECLN), which
    keep their labels local rather than expanding the big T dictionary."""
    return fr if lang_code == "FR" else en

# --- Bilingual Translations Dictionary ---
from translations import T

# Apply Translations
st.sidebar.caption(T[lang_code]["demand_planning_caption"])
st.sidebar.markdown("---")
# National-only tracking: no geographic filter or map. Every series is followed
# at the France level.

# --- Year range slicer: filters every series to the chosen period ---
_all_dates = pd.concat([df_sitadel["Date"], df_ventes_ancien["Date"], df_sales["Date"], df_macro["Date"]])
_ymin, _ymax = int(_all_dates.dt.year.min()), int(_all_dates.dt.year.max())
year_range = st.sidebar.slider(
    T[lang_code]["year_filter"], _ymin, _ymax, (_ymin, _ymax), step=1
)

def _filter_years(df):
    return df[(df["Date"].dt.year >= year_range[0]) & (df["Date"].dt.year <= year_range[1])]

df_sitadel = _filter_years(df_sitadel)
df_ventes_ancien = _filter_years(df_ventes_ancien)
df_macro = _filter_years(df_macro)
df_sales = _filter_years(df_sales)
if not df_revenue.empty:
    df_revenue = _filter_years(df_revenue)
if not df_ecln.empty:
    df_ecln = _filter_years(df_ecln)
if not df_company_sales.empty:
    df_company_sales = _filter_years(df_company_sales)

st.sidebar.info(T[lang_code]["sidebar_info"])

# --- Sidebar: PDF report generator ---
# Builds a concise "bilan" PDF (KPIs, commentary, key charts, BPCE benchmark) from the
# full-history national frames. Generated on click only (heavy imports stay lazy), then
# offered as a download. Uses the untouched full series so the report is slicer-independent.
st.sidebar.markdown("---")
st.sidebar.markdown("### 📄 " + _L("Rapport PDF", "PDF report"))
if st.sidebar.button(_L("Générer le rapport", "Generate report"), key="btn_gen_pdf"):
    with st.spinner(_L("Génération du PDF…", "Generating PDF…")):
        import report as _rep
        st.session_state["pdf_report_bytes"] = _rep.build_pdf_report(con, lang_code)
if "pdf_report_bytes" in st.session_state:
    st.sidebar.download_button(
        _L("📥 Télécharger le bilan (PDF)", "📥 Download the review (PDF)"),
        data=st.session_state["pdf_report_bytes"],
        file_name="bilan_marche_immobilier.pdf", mime="application/pdf",
        key="dl_pdf_report")

# --- Main Page Title ---
st.title(T[lang_code]["title"])

# National-only: every series is already France-level, so there is nothing to filter.
# Les alias filtered_* qui vivaient ici n'ont plus d'utilisateur depuis la phase 3 : les
# derniers `groupby` sur ces frames sont passés en SQL, où le slicer est appliqué par le
# paramètre `years=` de q.monthly plutôt qu'en amont sur une copie de DataFrame.

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

def _mom_caption(m):
    """'3 derniers mois vs n-1' momentum line for a KPI card (— if unavailable)."""
    v = m.get("last3_yoy")
    txt = "—" if v is None else (f"{v:+.1f}%".replace(".", ",") if lang_code == "FR" else f"{v:+.1f}%")
    return f"{_L('3 derniers mois vs n-1', 'Last 3 months vs prior year')} : {txt}"

def _borrow_capacity_factor(rate_pct, years):
    """Present value of a 1-unit monthly instalment over `years` at annual rate
    `rate_pct` — i.e. the principal a fixed monthly payment can service. Vectorised;
    a zero rate degenerates to n months. Used by the affordability card (Synthèse)
    and the Prix & Accessibilité section of the existing-home tab."""
    i = np.asarray(rate_pct, dtype=float) / 100.0 / 12.0
    n = years * 12
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(i > 0, (1.0 - (1.0 + i) ** (-n)) / i, float(n))

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

def add_last_value_label(fig, df, date_col, val_col, color, lang="FR", decimals=2, yshift=0):
    """Mark the last non-null point of `val_col` with a highlighted value callout
    (dot + label), like the reference chart's end-of-line figures. Values use the
    French decimal comma in FR. `yshift` (pixels) nudges the text vertically so several
    end-labels sharing near-identical values don't overlap (the dot stays on the point)."""
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
        showarrow=False, xanchor="left", xshift=8, yshift=yshift,
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

def company_series_options(df):
    """Distinct imported product-family labels ('Serie'), or [] when nothing imported."""
    if df is None or df.empty or "Serie" not in df.columns:
        return []
    return sorted(df["Serie"].dropna().astype(str).unique().tolist())

def pick_company_series(df, key, label=None, years=None):
    """Series selector + monthly [Date, Sales] aggregate for the chosen imported product
    family. Shows a selectbox only when several series were imported; returns
    (serie_name, agg_df) or (None, None) when no company sales are available.

    `df` ne sert plus qu'à lister les séries disponibles (un `unique()`, pas une
    agrégation) : la somme mensuelle est faite par DuckDB. `years` doit refléter la frame
    que l'appelant aurait passée — bornée par le slicer, ou None pour l'historique complet.
    """
    opts = company_series_options(df)
    if not opts:
        return None, None
    serie = opts[0] if len(opts) == 1 else st.selectbox(
        label or _L("Série (famille de produits)", "Series (product family)"), opts, key=key)
    agg = q.monthly(con, "company_sales", ["Sales"], windows=(), types=[serie],
                    category_col="Serie", years=years)
    return serie, agg

# Published BPCE L'Observatoire targets for 2026 (RDV Immobilier press conference,
# 2 June 2026) — external validation benchmark for our own model. Defined here (above the
# tabs) so both the Synthèse landing page and the Forecast tab can reference them.
BPCE_TX_ANCIEN_2026 = 890_000      # existing-home transactions in 2026 (−6% vs 2025)
BPCE_TX_TOTAL_2026 = 1_026_000     # total (new + existing) transactions (−5% vs 2025)
BPCE_RATE_Q4_2026 = 3.43           # credit rate at Q4 2026 (%, +34 bp YoY)
BPCE_PRICE_YOY_Q4_2026 = -0.1      # existing-home price, YoY at Q4 2026 (%)

# --- Define Streamlit Tabs ---
# First level follows the reading funnel: where does the market stand (new-build,
# existing homes) → why (macro environment, policy) → where is it going (forecast) →
# on what data (sources & imports). Each market tab owns its whole segment: the
# new-build tab covers SIT@DEL permits/starts AND ECLN commercialisation; the
# existing-home tab covers IGEDD transactions AND Notaires-INSEE prices/affordability.
#
# There is deliberately NO separate "workshop" tab. The lag exploration that used to
# live there is now folded INTO the forecast tab, next to the model whose lags it
# explains (see the two sections at the end of `with tab_forecast:`): a free-floating
# lag sandbox next to an auto-calibrated model gave two different answers to the same
# question. What survived is the part the model does NOT cover — SIT@DEL permits as an
# upstream driver of company sales.
(tab_synthese, tab_neuf, tab_ancien, tab_macro, tab_actus, tab_forecast,
 tab_donnees) = st.tabs([
    _L("🧭 Synthèse", "🧭 Overview"),
    T[lang_code]["tab_neuf"],
    T[lang_code]["tab_ancien"],
    T[lang_code]["tab_macro"],
    _L("📰 Actualités & Aides", "📰 News & Policy"),
    T[lang_code]["tab_forecast"],
    T[lang_code]["tab_donnees"]
])

# ==============================================================================
# TAB 0: SYNTHÈSE (landing page — traffic-light read of the market + auto commentary)
# ==============================================================================
with tab_synthese:
    st.header(_L("🧭 Synthèse — vue d'ensemble du marché",
                 "🧭 Market overview"))
    st.caption(_L(
        "L'état du marché immobilier en un coup d'œil : tendance par pilier, chiffres clés "
        "et implication pour la demande second œuvre. Méthode de lecture : "
        "« ℹ️ Comment lire cette page » ci-dessous.",
        "The housing market at a glance: per-pillar trend, headline figures and the "
        "implication for second-œuvre demand. Reading method: 'ℹ️ How to read this page' "
        "below."))

    # Full-history national momentum & 12m levels (slicer-independent).
    # Agrégat mensuel + cumul 12 mois en une requête par dataset (le cumul est calculé
    # par DuckDB en fonction de fenêtre, plus par un rolling pandas sur une copie).
    _sy_roll_sit = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"])
    _sy_roll_va = q.monthly(con, "ventes_ancien", ["Transactions"])
    _sy_m_permis = ana.momentum_metrics(_sy_roll_sit, "Permis")
    _sy_m_mises = ana.momentum_metrics(_sy_roll_sit, "MisesEnChantier")
    _sy_m_tx = ana.momentum_metrics(_sy_roll_va, "Transactions")
    _sy_k_permis = ana.calculate_kpis(_sy_roll_sit, "Permis")
    _sy_k_mises = ana.calculate_kpis(_sy_roll_sit, "MisesEnChantier")
    _sy_k_tx = ana.calculate_kpis(_sy_roll_va, "Transactions")

    # --- Shared card/format helpers -------------------------------------------------
    def _dot(status):
        return {"up": "🟢", "flat": "🟠", "down": "🔴"}.get(status, "⚪")

    def _status_yoy(v, hi=1.0, lo=-1.0):
        if v is None:
            return "flat"
        return "up" if v > hi else ("down" if v < lo else "flat")

    def _th(v):
        return "—" if v is None else f"{int(round(v)):,}".replace(",", " ")

    def _human(v):
        """Headline-sized number: '385 k' above 100 000, exact spaced int below —
        faster to scan; the exact figure stays in the card caption."""
        if v is None:
            return "—"
        v = float(v)
        if abs(v) >= 100_000:
            return f"{v / 1000.0:,.0f} k".replace(",", " ")
        return f"{int(round(v)):,}".replace(",", " ")

    def _pct_fr(v):
        if v is None:
            return "—"
        s = f"{v:+.1f}%"
        return s.replace(".", ",") if lang_code == "FR" else s

    def _delta3m_sub(v, exact=None):
        """Plain-language momentum caption ('+9,2 % vs un an plus tôt (3 derniers mois)'),
        with the exact 12-month total appended when the headline value is humanised."""
        txt = _pct_fr(v) + _L(" vs un an plus tôt (3 derniers mois)",
                              " vs a year earlier (last 3 months)")
        if exact is not None:
            txt += _L(" · total exact : ", " · exact total: ") + _th(exact)
        return txt

    def _render_cards(cards, per_row=3):
        """Rows of headline cards: (dot emoji, title, value, sub-caption). Title first,
        then the value — the natural reading order (what is it, then how much)."""
        for _row_start in range(0, len(cards), per_row):
            _rc = st.columns(per_row)
            for _c, (_emoji, _title, _val, _sub) in zip(_rc, cards[_row_start:_row_start + per_row]):
                with _c:
                    st.markdown(f"**{_title}**")
                    st.markdown(f"### {_emoji} {_val}")
                    if _sub:
                        st.caption(_sub)

    _mi = df_macro_full.set_index("Date").sort_index()

    def _last_prev(col, months=12):
        if col not in _mi.columns:
            return None, None
        s = _mi[col].dropna()
        if s.empty:
            return None, None
        last = float(s.iloc[-1])
        cutoff = s.index[-1] - pd.DateOffset(months=months)
        older = s[s.index <= cutoff]
        return last, (float(older.iloc[-1]) if not older.empty else None)

    # --- Global market state: one status per pillar, shown as chips before anything
    # else — the "at a glance" a sales director or GM actually needs. Derived from the
    # same momentum metrics as the cards below (no new computation).
    _neuf_l3 = [v for v in (_sy_m_permis.get("last3_yoy"), _sy_m_mises.get("last3_yoy"))
                if v is not None]
    _pill_neuf = _status_yoy(sum(_neuf_l3) / len(_neuf_l3)) if _neuf_l3 else "flat"
    _pill_ancien = _status_yoy(_sy_m_tx.get("last3_yoy"))
    _r_now, _r_yr = _last_prev("Credit_Logement_Taux_Interet")
    _dr_yr = None if (_r_now is None or _r_yr is None) else _r_now - _r_yr
    _pill_fin = ("flat" if _dr_yr is None
                 else ("down" if _dr_yr > 0.1 else ("up" if _dr_yr < -0.1 else "flat")))
    _bls_now, _ = _last_prev("Demande_Credit_Perspectives")

    _w_market = {"up": _L("en reprise", "recovering"), "flat": _L("stable", "stable"),
                 "down": _L("en repli", "declining")}
    _w_fin = {"up": _L("en amélioration", "improving"), "flat": _L("stable", "stable"),
              "down": _L("en durcissement", "tightening")}

    def _chip(status, label, word):
        _bg, _fg = {"up": ("rgba(56,142,60,0.12)", "#2E7D32"),
                    "flat": ("rgba(251,192,45,0.20)", "#7A5D00"),
                    "down": ("rgba(230,74,25,0.12)", "#B23A12")}.get(status, ("#ECECEC", "#555555"))
        return (f"<span style='background:{_bg};color:{_fg};border-radius:16px;"
                f"padding:6px 14px;margin-right:10px;font-weight:600;font-size:1.02rem;"
                f"display:inline-block;margin-bottom:6px'>{_dot(status)} {label} · {word}</span>")

    st.markdown(
        _chip(_pill_neuf, _L("Neuf", "New-build"), _w_market[_pill_neuf])
        + _chip(_pill_ancien, _L("Ancien", "Existing homes"), _w_market[_pill_ancien])
        + _chip(_pill_fin, _L("Financement", "Financing"), _w_fin[_pill_fin]),
        unsafe_allow_html=True)

    # --- Key takeaways: one bullet per pillar (one or two figures each) + the business
    # implication for second-œuvre demand — instead of a dense numbers paragraph.
    _sy_mom_ip = ana.momentum_metrics(
        q.monthly(con, "sitadel", ["MisesEnChantier"], windows=(),
                  types=ana.SITADEL_INDIVIDUEL_PUR), "MisesEnChantier")
    _lines = []
    _neuf_head = {"up": _L("la construction accélère", "construction is accelerating"),
                  "flat": _L("la construction est stable", "construction is flat"),
                  "down": _L("la construction recule", "construction is receding")}[_pill_neuf]
    _l1 = (f"{_dot(_pill_neuf)} **{_L('Neuf', 'New-build')}** — {_neuf_head} : "
           + _L(f"permis {_pct_fr(_sy_k_permis['yoy_12m_pct'])} et mises en chantier "
                f"{_pct_fr(_sy_k_mises['yoy_12m_pct'])} sur 12 mois",
                f"permits {_pct_fr(_sy_k_permis['yoy_12m_pct'])} and starts "
                f"{_pct_fr(_sy_k_mises['yoy_12m_pct'])} over 12 months"))
    if _sy_mom_ip.get("last3_yoy") is not None:
        _l1 += _L(f" (maison individuelle pure : {_pct_fr(_sy_mom_ip['last3_yoy'])} sur 3 mois).",
                  f" (detached houses: {_pct_fr(_sy_mom_ip['last3_yoy'])} over 3 months).")
    else:
        _l1 += "."
    _lines.append(_l1)

    _tx_l3 = _sy_m_tx.get("last3_yoy")
    _l2 = (f"{_dot(_pill_ancien)} **{_L('Ancien', 'Existing homes')}** — "
           + _L(f"{_human(_sy_k_tx['current_12m'])} ventes sur 12 mois "
                f"({_pct_fr(_sy_k_tx['yoy_12m_pct'])})",
                f"{_human(_sy_k_tx['current_12m'])} sales over 12 months "
                f"({_pct_fr(_sy_k_tx['yoy_12m_pct'])})"))
    if _tx_l3 is not None:
        if _pill_ancien == "down":
            _l2 += _L(f", mais la dynamique ralentit : {_pct_fr(_tx_l3)} sur les 3 derniers mois.",
                      f", but momentum is fading: {_pct_fr(_tx_l3)} over the last 3 months.")
        else:
            _l2 += _L(f" ; {_pct_fr(_tx_l3)} sur les 3 derniers mois.",
                      f"; {_pct_fr(_tx_l3)} over the last 3 months.")
    else:
        _l2 += "."
    _lines.append(_l2)

    _l3_parts = []
    if _r_now is not None:
        _r_txt = f"{_r_now:.2f} %".replace(".", ",") if lang_code == "FR" else f"{_r_now:.2f}%"
        _part = _L(f"taux de crédit à {_r_txt}", f"credit rate at {_r_txt}")
        if _dr_yr is not None:
            _part += _L(f" ({_pct_fr(_dr_yr).replace('%', ' pt')} sur un an)",
                        f" ({_pct_fr(_dr_yr).replace('%', 'pp')} over a year)")
        _l3_parts.append(_part)
    if _bls_now is not None:
        _bls_word = (_L("en hausse", "rising") if _bls_now > 0
                     else (_L("en baisse", "falling") if _bls_now < -10 else _L("stable", "flat")))
        _l3_parts.append(_L(f"les banques anticipent une demande de crédit {_bls_word}",
                            f"banks expect credit demand to be {_bls_word}"))
    if _l3_parts:
        _lines.append(f"{_dot(_pill_fin)} **{_L('Financement', 'Financing')}** — "
                      + _L(" ; ", "; ").join(_l3_parts) + ".")

    # The "so what" for the business, using the lead-times assumed across the app
    # (new-build → second-œuvre content at ~12-18 months; moves → equipment at ~2 months).
    _impl_neuf = {"up": _L("signal favorable à 12-18 mois via le neuf (fermetures & menuiseries)",
                           "favourable 12-18-month signal from new-build (closures & joinery)"),
                  "flat": _L("signal neuf neutre à 12-18 mois",
                             "neutral new-build signal at 12-18 months"),
                  "down": _L("vent contraire à 12-18 mois côté neuf",
                             "12-18-month headwind from new-build")}[_pill_neuf]
    _impl_ancien = {"up": _L("soutien à court terme (~2 mois) via les transactions "
                             "(sécurité & domotique)",
                             "short-term (~2-month) support from transactions "
                             "(security & home automation)"),
                    "flat": _L("transactions neutres à court terme",
                               "neutral short-term transactions"),
                    "down": _L("prudence à court terme (~2 mois) sur les produits liés aux "
                               "déménagements (sécurité & domotique)",
                               "short-term (~2-month) caution on move-related products "
                               "(security & home automation)")}[_pill_ancien]
    _lines.append("🎯 **" + _L("Demande second œuvre", "Second-œuvre demand")
                  + f"** — {_impl_neuf} ; {_impl_ancien}.")

    st.info(_L("**À retenir**", "**Key takeaways**") + "\n\n"
            + "\n".join(f"- {l}" for l in _lines))

    # Data freshness by source (SIT@DEL, IGEDD and ECLN can end on different
    # months/quarters), then the how-to-read methodology tucked into an expander.
    _last_sit = last_valid_month(_sy_roll_sit, "Permis")
    _last_va = last_valid_month(_sy_roll_va, "Transactions")
    _fresh = [
        f"SIT@DEL : {format_month_year(_last_sit, lang_code)}",
        f"IGEDD : {format_month_year(_last_va, lang_code)}",
    ]
    if df_ecln_full is not None and not df_ecln_full.empty:
        _e_last_d = df_ecln_full.dropna(subset=["Reservations"])["Date"].max()
        if pd.notna(_e_last_d):
            _fresh.append(f"ECLN : {_e_last_d.year}-T{(_e_last_d.month - 1) // 3 + 1}")
    st.caption("📅 " + _L("Dernières données — ", "Latest data — ") + " · ".join(_fresh))
    with st.expander("ℹ️ " + _L("Comment lire cette page", "How to read this page")):
        st.markdown(_L(
            "Chaque pastille résume la tendance des **3 derniers mois vs un an plus tôt** : "
            "🟢 vent favorable · 🟠 stable · 🔴 vent contraire. Pour les taux et "
            "l'accessibilité, 🟢 signifie des **conditions qui s'améliorent** (taux en "
            "baisse), pas une valeur qui monte. Chiffres nationaux, indépendants du filtre "
            "de période de la barre latérale ; le détail de chaque bloc est dans les "
            "onglets dédiés (liens sous chaque bloc).",
            "Each dot summarises the trend of the **last 3 months vs a year earlier**: "
            "🟢 tailwind · 🟠 flat · 🔴 headwind. For rates and affordability, 🟢 means "
            "**improving conditions** (falling rates), not a rising value. National "
            "figures, independent of the sidebar period filter; each block's detail lives "
            "in the dedicated tabs (links under each block)."))

    # --- Block 1: activity (construction, existing-home sales, new-build reservations) ---
    st.markdown("#### " + _L("Activité", "Activity"))
    _cards_act = [
        (_dot(_status_yoy(_sy_m_permis.get("last3_yoy"))),
         _L("Permis de construire", "Building permits"),
         _human(_sy_k_permis["current_12m"]) + _L(" /12 m", " /12m"),
         _delta3m_sub(_sy_m_permis.get("last3_yoy"), exact=_sy_k_permis["current_12m"])),
        (_dot(_status_yoy(_sy_m_mises.get("last3_yoy"))),
         _L("Mises en chantier", "Housing starts"),
         _human(_sy_k_mises["current_12m"]) + _L(" /12 m", " /12m"),
         _delta3m_sub(_sy_m_mises.get("last3_yoy"), exact=_sy_k_mises["current_12m"])),
        (_dot(_status_yoy(_sy_m_tx.get("last3_yoy"))),
         _L("Ventes de logements anciens", "Existing-home sales"),
         _human(_sy_k_tx["current_12m"]) + _L(" /12 m", " /12m"),
         _delta3m_sub(_sy_m_tx.get("last3_yoy"), exact=_sy_k_tx["current_12m"])),
    ]
    # New-build reservations (ECLN, quarterly): last quarter vs same quarter a year earlier.
    if df_ecln_full is not None and not df_ecln_full.empty:
        _se = df_ecln_full.dropna(subset=["Reservations"]).sort_values("Date")
        if len(_se) >= 5:
            _e_yoy = (float(_se["Reservations"].iloc[-1]) / float(_se["Reservations"].iloc[-5]) - 1) * 100
            _cards_act.append((
                _dot(_status_yoy(_e_yoy)),
                _L("Réservations particuliers neuf (ECLN)", "New-build private-buyer reservations (ECLN)"),
                _th(float(_se["Reservations"].iloc[-1])) + _L(" /trim.", " /qtr"),
                _pct_fr(_e_yoy) + _L(" vs même trimestre un an plus tôt",
                                     " vs same quarter a year earlier")))
    _render_cards(_cards_act, per_row=4 if len(_cards_act) == 4 else 3)
    st.caption(_L("→ détail : « 🏗️ Marché du neuf » · « 🏠 Marché de l'ancien »",
                  "→ detail: '🏗️ New-Build Market' · '🏠 Existing-Home Market'"))

    # --- Block 2: financing conditions ---
    st.markdown("#### " + _L("Conditions de financement", "Financing conditions"))
    _cards_fin = []
    # Credit rate direction (rising rate = headwind → down).
    _r_last, _r_prev = _last_prev("Credit_Logement_Taux_Interet")
    if _r_last is None:
        _cards_fin.append(("⚪", _L("Taux de crédit habitat", "Housing-loan rate"), "—", ""))
    else:
        _dr = None if _r_prev is None else _r_last - _r_prev
        _r_status = "flat" if _dr is None else ("down" if _dr > 0.1 else ("up" if _dr < -0.1 else "flat"))
        _r_val = (f"{_r_last:.2f} %".replace(".", ",") if lang_code == "FR" else f"{_r_last:.2f}%")
        _r_sub = _L("sur un an : ", "1-year change: ") + (_pct_fr(_dr).replace("%", " pt") if _dr is not None else "—")
        _cards_fin.append((_dot(_r_status), _L("Taux de crédit habitat", "Housing-loan rate"), _r_val, _r_sub))
    # Credit demand (BLS expectations, leading) — plain-language wording, survey named in the sub.
    _bls_last, _ = _last_prev("Demande_Credit_Perspectives")
    if _bls_last is None:
        _cards_fin.append(("⚪", _L("Demande de crédit (banques)", "Credit demand (banks)"), "—", ""))
    else:
        _bls_status = "up" if _bls_last > 0 else ("down" if _bls_last < -10 else "flat")
        _bls_word = (_L("attendue en hausse", "expected to rise") if _bls_last > 0
                     else (_L("attendue en baisse", "expected to fall") if _bls_last < -10
                           else _L("attendue stable", "expected flat")))
        _cards_fin.append((_dot(_bls_status), _L("Demande de crédit (banques)", "Credit demand (banks)"),
                           f"{_bls_last:+.0f}",
                           _bls_word + _L(" par les banques · enquête BLS, 3 prochains mois",
                                          " by banks · BLS survey, next 3 months")))
    # Affordability index (borrowing capacity ÷ prices, base 100 = 2015, 25-year loan) —
    # the same construction as the Prix & Accessibilité section of the existing-home tab.
    if "Prix_Ancien_Ensemble" in df_macro_full.columns:
        _af = df_macro_full.dropna(subset=["Credit_Logement_Taux_Interet", "Prix_Ancien_Ensemble"]).copy()
        _cap15 = _borrow_capacity_factor(
            df_macro_full.loc[(df_macro_full["Date"].dt.year == 2015)
                              & df_macro_full["Credit_Logement_Taux_Interet"].notna(),
                              "Credit_Logement_Taux_Interet"], 25).mean() if not _af.empty else None
        if _cap15 and _cap15 > 0:
            _af["_access"] = (_borrow_capacity_factor(_af["Credit_Logement_Taux_Interet"], 25)
                              / _cap15 * 100) / _af["Prix_Ancien_Ensemble"] * 100
            _acc_s = _af.set_index("Date")["_access"].dropna()
            if not _acc_s.empty:
                _a_last = float(_acc_s.iloc[-1])
                _older = _acc_s[_acc_s.index <= _acc_s.index[-1] - pd.DateOffset(months=12)]
                _da = (_a_last - float(_older.iloc[-1])) if not _older.empty else None
                _a_status = "flat" if _da is None else ("up" if _da > 1 else ("down" if _da < -1 else "flat"))
                # Say what the index MEANS (gap vs the 2015 baseline) instead of "base 100".
                _gap15 = 100.0 - _a_last
                if _gap15 > 0.5:
                    _a_txt = _L(f"logement ≈ {_gap15:.0f} % moins accessible qu'en 2015",
                                f"housing ≈ {_gap15:.0f}% less affordable than in 2015")
                elif _gap15 < -0.5:
                    _a_txt = _L(f"logement ≈ {-_gap15:.0f} % plus accessible qu'en 2015",
                                f"housing ≈ {-_gap15:.0f}% more affordable than in 2015")
                else:
                    _a_txt = _L("accessibilité au niveau de 2015", "affordability at its 2015 level")
                _a_sub = _a_txt + _L(" · sur un an : ", " · 1y: ") \
                    + (_pct_fr(_da).replace("%", " pt") if _da is not None else "—")
                _cards_fin.append((_dot(_a_status), _L("Indice d'accessibilité", "Affordability index"),
                                   f"{_a_last:.0f}", _a_sub))
    _render_cards(_cards_fin)
    st.caption(_L("→ détail : « 🏦 Environnement & Financement » · « 🏠 Marché de l'ancien »",
                  "→ detail: '🏦 Macro Environment & Financing' · '🏠 Existing-Home Market'"))

    # --- Block 3: perspective (own read vs BPCE, renovation driver, next policy step) ---
    # Gap to the published BPCE target computed first so the block header can carry
    # its one-line verdict.
    _cards_persp = []
    _sy_tx12 = q.transactions_run_rate(con).dropna()
    _sy_gap = None
    if not _sy_tx12.empty:
        _sy_last_tx = float(_sy_tx12.iloc[-1])
        _sy_gap = (_sy_last_tx - BPCE_TX_ANCIEN_2026) / BPCE_TX_ANCIEN_2026 * 100.0
    _persp_hdr = "#### " + _L("Perspective", "Outlook")
    if _sy_gap is not None:
        if _sy_gap > 3:
            _persp_hdr += _L(" — marché au-dessus de la cible BPCE 2026, infléchissement attendu",
                             " — market above the BPCE 2026 target, slowdown expected")
        elif _sy_gap >= -3:
            _persp_hdr += _L(" — marché aligné sur la cible BPCE 2026",
                             " — market in line with the BPCE 2026 target")
        else:
            _persp_hdr += _L(" — marché sous la cible BPCE 2026",
                             " — market below the BPCE 2026 target")
    st.markdown(_persp_hdr)
    if _sy_gap is None:
        _cards_persp.append(("⚪", _L("Ventes 12 m vs cible BPCE 2026", "12m sales vs BPCE 2026 target"), "—", ""))
    else:
        # Above target = market currently stronger than BPCE's end-2026 view (a slowdown is
        # implied ahead) → flag orange; near/below is closer to the published landing point.
        _f_status = "up" if _sy_gap > 3 else ("flat" if _sy_gap > -3 else "down")
        _cards_persp.append((_dot(_f_status),
                             _L("Ventes 12 m vs cible BPCE 2026", "12m sales vs BPCE 2026 target"),
                             _human(_sy_last_tx),
                             _pct_fr(_sy_gap)
                             + (_L(" au-dessus de la cible BPCE 2026 (890 k)",
                                   " above the BPCE 2026 target (890k)") if _sy_gap >= 0
                                else _L(" sous la cible BPCE 2026 (890 k)",
                                        " below the BPCE 2026 target (890k)"))))
    # Renovation activity — the stock-driven second-œuvre driver. Only shown once the
    # renovation series is populated (fetch_new_sources.build_renovation).
    if "Reno_Activite_Batiment" in df_macro_full.columns and df_macro_full["Reno_Activite_Batiment"].notna().any():
        _rn_last, _rn_prev = _last_prev("Reno_Activite_Batiment")
        if _rn_last is not None:
            _rn_d = None if _rn_prev is None else _rn_last - _rn_prev
            _rn_status = "flat" if _rn_d is None else ("up" if _rn_d > 0 else ("down" if _rn_d < 0 else "flat"))
            _rn_word = (_L("activité en baisse", "activity falling") if _rn_last < 0
                        else (_L("activité en hausse", "activity rising") if _rn_last > 0
                              else _L("activité stable", "activity flat")))
            _cards_persp.append((_dot(_rn_status),
                                 _L("Activité rénovation (second œuvre)", "Renovation activity (second-œuvre)"),
                                 f"{_rn_last:+.0f}",
                                 _L(f"solde d'opinion INSEE — {_rn_word}",
                                    f"INSEE opinion balance — {_rn_word}")))
    # Next policy milestone from the curated watchlist (Actualités & Aides).
    _sy_jalons = sorted(
        [(d, it) for it in actu.items_sorted() for d, _lbl, _typ in it.get("jalons", [])
         if d > actu.MAJ],
        key=lambda t: t[0])
    if _sy_jalons:
        _j_d, _j_it = _sy_jalons[0]
        _cards_persp.append(("🗓️", _L("Prochaine échéance aides", "Next policy deadline"),
                             pd.Timestamp(_j_d).strftime("%m/%Y"), _j_it["court"][lang_code]))
    _render_cards(_cards_persp)
    st.caption(_L("→ détail : « 📡 Prévision & Scénarios » · « 📰 Actualités & Aides »",
                  "→ detail: '📡 Forecast & Scenarios' · '📰 News & Policy'"))

    # --- Cross-market view: the new-build funnel vs existing-home sales, 12m totals.
    # This is the side-by-side read the two market tabs each show half of.
    st.markdown("---")
    st.markdown("#### " + _L("Neuf vs ancien — volumes en cumul 12 mois",
                             "New vs existing — 12-month rolling volumes"))
    st.caption(_L(
        "Lecture croisée des deux marchés que détaillent les onglets « 🏗️ Marché du neuf » "
        "et « 🏠 Marché de l'ancien », en deux angles. À gauche, les niveaux réels sur une "
        "échelle unique : le rapport de masse saute aux yeux (l'ancien pèse 2 à 3× le neuf en "
        "volume). À droite, base 100 sur la moyenne 2015 — la base des indices INSEE, donc "
        "celle de tous les indices du site : on compare les dynamiques sans distorsion "
        "d'échelle, et le repère est le même d'un graphique à l'autre.",
        "Cross-market read detailed in the '🏗️ New-Build Market' and '🏠 Existing-Home Market' "
        "tabs, from two angles. Left, real levels on a single scale: the mass ratio is obvious "
        "(existing sales are 2–3× new-build volumes). Right, rebased to 100 on the 2015 average "
        "— the INSEE base, hence every index on the site: dynamics compare without scale "
        "distortion, against the same reference throughout."))

    # Series to plot on both panels — same colour language throughout.
    _sy_series = [
        (_sy_roll_sit, "Permis_12M", T[lang_code]["permis_trace"], COLOR_BRICK, None),
        (_sy_roll_sit, "MisesEnChantier_12M", T[lang_code]["mises_trace"], COLOR_TEXT, "dash"),
        (_sy_roll_va, "Transactions_12M", T[lang_code]["transactions_trace"], COLOR_GREEN, None),
    ]

    _col_lvl, _col_idx = st.columns(2)

    # --- Left panel: real levels, single shared y-axis (in thousands). No dual axis, so
    # the vertical position of every curve is honest and directly comparable.
    with _col_lvl:
        st.markdown("**" + _L("Niveaux réels — échelle unique",
                              "Real levels — single scale") + "**")
        fig_lvl = go.Figure()
        for _df, _col, _name, _clr, _dash in _sy_series:
            fig_lvl.add_trace(go.Scatter(
                x=_df["Date"], y=_df[_col] / 1000.0, name=_name,
                line=dict(color=_clr, width=2.5, dash=_dash)))
        fig_lvl.update_layout(
            height=400, template="plotly_white",
            margin=dict(l=54, r=64, t=40, b=44),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        fig_lvl.update_yaxes(title_text=_L("Milliers /12 m", "Thousands /12m"),
                             rangemode="tozero")
        # Recent trough on the existing-home line + latest value on every curve, straight
        # on the curves so the turning points read without decoding an axis.
        _va_line = _sy_roll_va.dropna(subset=["Transactions_12M"])
        if not _va_line.empty:
            _recent = _va_line[_va_line["Date"] >= _va_line["Date"].max() - pd.DateOffset(years=4)]
            if len(_recent) > 12:
                _i_min = _recent["Transactions_12M"].idxmin()
                _d_min = _recent.loc[_i_min, "Date"]
                _v_min = _recent.loc[_i_min, "Transactions_12M"] / 1000.0
                fig_lvl.add_annotation(
                    x=_d_min, y=_v_min,
                    text=_L(f"creux : {format_month_year(_d_min, 'FR')} ({_v_min:.0f} k)",
                            f"trough: {format_month_year(_d_min, 'EN')} ({_v_min:.0f}k)"),
                    showarrow=True, arrowhead=2, arrowcolor=COLOR_GREEN, ax=0, ay=42,
                    font=dict(color=COLOR_GREEN, size=11))
        for _df, _col, _name, _clr, _dash in _sy_series:
            _sline = _df.dropna(subset=[_col])
            if not _sline.empty:
                fig_lvl.add_annotation(
                    x=_sline["Date"].iloc[-1], y=_sline[_col].iloc[-1] / 1000.0,
                    text=f"<b>{_sline[_col].iloc[-1] / 1000.0:.0f} k</b>",
                    showarrow=False, xanchor="left", xshift=6, font=dict(color=_clr, size=12))
        st.plotly_chart(fig_lvl, use_container_width=True)

    # --- Right panel: same series rebased to 100 on the 2015 annual mean — the INSEE
    # convention already used by every other index on the site (see analysis.BASE_YEAR),
    # so growth paths are compared cleanly and against a base that means something.
    # web_export.build_synthese runs the SAME computation for the web front.
    with _col_idx:
        _sy_merged = pd.merge(
            _sy_roll_sit[["Date", "Permis_12M", "MisesEnChantier_12M"]],
            _sy_roll_va[["Date", "Transactions_12M"]],
            on="Date", how="outer").sort_values("Date")
        _idx_cols = ["Permis_12M", "MisesEnChantier_12M", "Transactions_12M"]
        _base = ana.base_100(_sy_merged, _idx_cols)
        st.markdown("**" + _L(f"Base 100 = {ana.BASE_LABEL}",
                              f"Rebased to 100 = {ana.BASE_LABEL_EN}") + "**")
        fig_idx = go.Figure()
        if any(_base.values()):
            fig_idx.add_hline(y=100, line_dash="dot", line_color="#B0B7C3",
                              line_width=1)
            for _col, _name, _clr, _dash in (
                ("Permis_12M", T[lang_code]["permis_trace"], COLOR_BRICK, None),
                ("MisesEnChantier_12M", T[lang_code]["mises_trace"], COLOR_TEXT, "dash"),
                ("Transactions_12M", T[lang_code]["transactions_trace"], COLOR_GREEN, None),
            ):
                if not _base.get(_col):
                    continue          # 2015 incomplète : mieux vaut pas de courbe qu'une base fausse
                _idx = _sy_merged[["Date", _col]].dropna()
                _idx["v"] = _idx[_col] / _base[_col] * 100.0
                fig_idx.add_trace(go.Scatter(
                    x=_idx["Date"], y=_idx["v"], name=_name,
                    line=dict(color=_clr, width=2.5, dash=_dash)))
                fig_idx.add_annotation(
                    x=_idx["Date"].iloc[-1], y=_idx["v"].iloc[-1],
                    text=f"<b>{_idx['v'].iloc[-1]:.0f}</b>",
                    showarrow=False, xanchor="left", xshift=6, font=dict(color=_clr, size=12))
        fig_idx.update_layout(
            height=400, template="plotly_white",
            margin=dict(l=54, r=52, t=40, b=44),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        fig_idx.update_yaxes(title_text=_L("Indice (base 100)", "Index (base 100)"))
        st.plotly_chart(fig_idx, use_container_width=True)

    st.caption(f"{T[lang_code]['source_label']} : {T[lang_code]['source_sitadel']} · "
               f"{T[lang_code]['source_ventes_ancien']} — "
               + _L("cumul 12 mois glissant", "12-month rolling sum"))

# ==============================================================================
# TAB 1: MARCHÉ DU NEUF — permis & mises en chantier (SIT@DEL) + dynamique
# individuel vs collectif. La commercialisation ECLN est ajoutée à la suite par le
# second bloc `with tab_neuf:` (section ECLN, plus bas dans ce fichier).
# ==============================================================================
with tab_neuf:
    st.header(T[lang_code]["neuf_header"])
    st.write(T[lang_code]["neuf_desc"])

    # KPIs sit above the curves, but they depend on the SIT@DEL segment selector
    # which now lives with the SIT@DEL chart further down. Reserve the KPI position
    # with a container and fill it once the selection is known.
    kpi_container = st.container()

    # --- Charts Row ---
    st.markdown(f"### {T[lang_code]['curves_title']}")
    chart_view_opts = [T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"], T[lang_code]["chart_view_raw"]]
    chart_view = st.radio(T[lang_code]["chart_view_label"], chart_view_opts, horizontal=True,
                          key="chart_view_neuf")

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
            show_raw = st.checkbox(T[lang_code]["show_raw_label"], value=True, key="show_raw_neuf")
        with _rc2:
            show_ma12 = st.checkbox(T[lang_code]["ma_12"], key="ma12_neuf")
        with _rc3:
            show_ma6 = st.checkbox(T[lang_code]["ma_6"], key="ma6_neuf")

    # Extra settings for the SIT@DEL chart, tucked into a collapsible expander:
    #  - which indicators to show (permits only / starts only / both);
    #  - the housing-type segmentation.
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

    # Aggregate data according to the segment selection. The year-filtered aggregate
    # feeds the month-by-year comparison bars below.
    agg_sitadel = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], windows=(),
                            types=sitadel_types, years=year_range)

    # Rolling 12m + 6m sums (and the moving-average overlays) are computed on the FULL
    # history, then the DISPLAY is clipped to the selected years — so a 12m cumul / moving
    # average at Jan 2023 uses its real Feb 2022→Jan 2023 window instead of showing an empty
    # first-12-months gap after the year slicer moves the start.
    # Les deux fenêtres (12 et 6 mois) sortent de la MÊME requête ; le découpage à la
    # période choisie reste après coup, pour que le cumul de janvier garde sa vraie
    # fenêtre des 12 mois précédents.
    rolling_sitadel = _filter_years(
        q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], windows=(12, 6),
                  types=sitadel_types))

    # KPI Calculations. The "Chiffres Clés" cards always reflect the full national
    # total (all housing types, full history) for the last available month, independent
    # of the sidebar year slicer and the SIT@DEL segment selector. The charts above use
    # the filtered series; these headline figures use the untouched full series.
    rolling_sitadel_total = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"])
    kpi_permis = ana.calculate_kpis(rolling_sitadel_total, "Permis")
    kpi_mises = ana.calculate_kpis(rolling_sitadel_total, "MisesEnChantier")

    # Momentum (BPCE style): 3 derniers mois vs mêmes mois n-1, computed from the
    # monthly national series (independent of the year slicer). Surfaces inflections
    # ("coup d'arrêt") faster than the 12m rolling YoY.
    mom_permis = ana.momentum_metrics(rolling_sitadel_total, "Permis")
    mom_mises = ana.momentum_metrics(rolling_sitadel_total, "MisesEnChantier")

    # Last available month behind the headline figures.
    _kpi_sitadel_month = format_month_year(last_valid_month(rolling_sitadel_total, "Permis"), lang_code)

    # --- KPI Row (rendered into the reserved container above the charts) ---
    kpi_container.markdown(f"### {T[lang_code]['kpis_title']}")
    kpi_container.caption(_L(
        "Chiffres nationaux au dernier mois disponible — indépendants du filtre de période "
        "et de la segmentation ci-dessous.",
        "National figures at the latest available month — independent of the period filter "
        "and the segmentation below."))
    kpi_cols = kpi_container.columns(3)

    with kpi_cols[0]:
        st.metric(
            label=T[lang_code]["permis_12m"],
            value=f"{kpi_permis['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_permis['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_permis['current_val']:,} ({kpi_permis['yoy_monthly_pct']}% YoY)")
        st.caption(_mom_caption(mom_permis))
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_sitadel_month}")

    with kpi_cols[1]:
        st.metric(
            label=T[lang_code]["mises_12m"],
            value=f"{kpi_mises['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_mises['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_mises['current_val']:,} ({kpi_mises['yoy_monthly_pct']}% YoY)")
        st.caption(_mom_caption(mom_mises))
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_sitadel_month}")

    with kpi_cols[2]:
        # End of the new-build funnel: quarterly ECLN reservations (detailed in the
        # ECLN section further down this tab).
        if df_ecln_full is not None and not df_ecln_full.empty:
            _ke = df_ecln_full.dropna(subset=["Reservations"]).sort_values("Date")
            if not _ke.empty:
                _ke_yoy = ((float(_ke["Reservations"].iloc[-1]) / float(_ke["Reservations"].iloc[-5]) - 1) * 100
                           if len(_ke) >= 5 else None)
                st.metric(
                    label=_L("Réservations particuliers ECLN (trimestre)", "ECLN private-buyer reservations (quarter)"),
                    value=f"{int(_ke['Reservations'].iloc[-1]):,}".replace(",", " "),
                    delta=(f"{_ke_yoy:+.1f}% YoY" if _ke_yoy is not None else None),
                    delta_color="normal"
                )
                _ke_d = _ke["Date"].iloc[-1]
                st.caption(_L("Trimestre vs même trimestre n-1", "Quarter vs same quarter prior year"))
                st.caption(_L("Dernier trimestre disponible", "Last available quarter")
                           + f" : {_ke_d.year}-T{(_ke_d.month - 1) // 3 + 1}")

    # Charts are displayed "en milliers" (values / 1000) to match the SDES
    # presentation; the extrema labels therefore no longer divide again (text_divisor=1).
    disp_sitadel = rolling_sitadel.copy()
    for _c in ["Permis", "MisesEnChantier", "Permis_12M", "MisesEnChantier_12M", "Permis_6M", "MisesEnChantier_6M"]:
        disp_sitadel[_c] = disp_sitadel[_c] / 1000.0

    # Resolve the selected view once: rolling 12m, rolling 6m, or raw monthly.
    _is_rolling = chart_view in (T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"])
    _roll_suffix = "_12M" if chart_view == T[lang_code]["chart_view_rolling"] else "_6M"
    if chart_view == T[lang_code]["chart_view_rolling"]:
        _sub = T[lang_code]["sub_rolling"]
    elif chart_view == T[lang_code]["chart_view_rolling6"]:
        _sub = T[lang_code]["sub_rolling6"]
    else:
        _sub = T[lang_code]["sub_raw"]

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

    # Title is rendered as markdown above the chart.
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

    # --- Individual vs collective new-build dynamics --------------------------------
    # The single most important new-build signal for a second-œuvre building actor: an
    # individual house carries far more equipment content than a collective dwelling, and
    # BPCE flags the individual-pur segment as the strongest rebound (p.11-12). Isolate it
    # here with its own momentum, rather than leaving it buried in the segmentation picker.
    st.markdown("### " + _L("🏠 Dynamique Individuel vs Collectif (neuf)",
                            "🏠 Individual vs collective new-build dynamics"))
    st.caption(_L(
        "Le logement individuel — surtout l'individuel pur — porte bien plus de contenu "
        "second œuvre (fermetures, menuiseries, sécurité, domotique) qu'un logement "
        "collectif. C'est le driver de volume le plus direct pour un acteur du bâtiment.",
        "Individual housing — especially detached houses — carries far more second-œuvre "
        "content (closures, joinery, security, home automation) than collective dwellings. "
        "It is the most direct volume driver for a building-materials actor."))

    _iv_metric = st.radio(
        _L("Indicateur", "Indicator"),
        [T[lang_code]["mises_trace"], T[lang_code]["permis_trace"]],
        horizontal=True, key="indiv_collectif_metric")
    _iv_col = "MisesEnChantier" if _iv_metric == T[lang_code]["mises_trace"] else "Permis"

    # Groups: individual-pur (strongest second-œuvre content), all individual, collective.
    _iv_groups = [
        (_L("Maison individuelle pure", "Detached houses"), ana.SITADEL_INDIVIDUEL_PUR, COLOR_BRICK),
        (_L("Individuel total (pur + groupé)", "All individual (detached + terraced)"), ana.SITADEL_INDIVIDUEL, COLOR_TERRACOTTA),
        (_L("Collectif", "Collective"), ana.SITADEL_COLLECTIF, COLOR_BLUE),
    ]

    # Les trois groupes en UNE requête (fenêtres partitionnées par groupe côté SQL), là
    # où le code refaisait un agrégat + un cumul 12 mois par groupe, puis un second
    # agrégat par groupe pour le momentum — soit huit passes pandas sur l'historique.
    _iv_all = q.monthly_by_group(con, "sitadel",
                                 {lbl: types for lbl, types, _ in _iv_groups}, [_iv_col])

    iv_cols = st.columns(3)
    for _i, (_lbl, _types, _clr) in enumerate(_iv_groups):
        _full_g = _iv_all[_iv_all["Groupe"] == _lbl]
        _val12 = _full_g[f"{_iv_col}_12M"].dropna()
        _mom_g = ana.momentum_metrics(_full_g, _iv_col)
        with iv_cols[_i]:
            st.metric(
                _lbl,
                f"{int(_val12.iloc[-1]):,}".replace(",", " ") if not _val12.empty else "—",
                delta=(f"{_mom_g['roll12_yoy']:+.1f}% " + _L("sur 12 mois", "over 12 months")
                       if _mom_g["roll12_yoy"] is not None else None))
            _l3 = _mom_g.get("last3_yoy")
            _l3txt = "—" if _l3 is None else (f"{_l3:+.1f}%".replace(".", ",") if lang_code == "FR" else f"{_l3:+.1f}%")
            st.caption(f"{_L('3 derniers mois vs n-1', 'Last 3 months vs prior year')} : {_l3txt}")

    # Rolling-12m lines: individual-pur vs collective, in thousands. Computed on the full
    # history then clipped to the selected years (12m window keeps its real look-back).
    st.markdown(
        f"**{_iv_metric} — {_L('maison individuelle pure vs collectif', 'detached houses vs collective')}** "
        f"<span style='color:#6c757d;font-weight:400'>({T[lang_code]['sub_rolling']})</span>",
        unsafe_allow_html=True
    )
    fig_iv = go.Figure()
    for _lbl, _types, _clr in [_iv_groups[0], _iv_groups[2]]:
        _g = _filter_years(_iv_all[_iv_all["Groupe"] == _lbl])
        fig_iv.add_trace(go.Scatter(x=_g["Date"], y=_g[f"{_iv_col}_12M"] / 1000.0,
                                    name=_lbl, line=dict(color=_clr, width=3)))
    fig_iv.update_layout(
        xaxis_title="Date",
        yaxis_title="Thousands of dwellings" if lang_code == "EN" else "Milliers de logements",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_iv, use_container_width=True)
    st.caption(f"{T[lang_code]['source_label']} : {T[lang_code]['source_sitadel']} — "
               f"{_L('cumul 12 mois glissant', '12-month rolling sum')}")

    # --- Monthly comparison by year (grouped bars, like the IGEDD monthly chart) ---
    # Compares the selected months across the years kept by the "Période (années)"
    # filter, on the segment-filtered monthly series, "en milliers".
    st.markdown(f"### {T[lang_code]['monthly_compare_title']}")
    st.caption(T[lang_code]["monthly_compare_desc"])

    _month_names = _EN_MONTHS if lang_code == "EN" else _FR_MONTHS
    _month_labels_all = [m.capitalize() for m in _month_names]
    _label_to_num = {lbl: i + 1 for i, lbl in enumerate(_month_labels_all)}

    # Default: the 3 months ending at the last available data point (inclusive), e.g.
    # if the last point is May, default to March / April / May.
    _last_month_num = (pd.Timestamp(agg_sitadel["Date"].max()).month
                       if not agg_sitadel.empty and pd.notna(agg_sitadel["Date"].max()) else 12)
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

# ==============================================================================
# TAB 2: MARCHÉ DE L'ANCIEN — transactions IGEDD. La section Prix & Accessibilité
# est ajoutée à la suite par le second bloc `with tab_ancien:` (plus bas dans ce
# fichier).
# ==============================================================================
with tab_ancien:
    st.header(T[lang_code]["ancien_header"])
    st.write(T[lang_code]["ancien_desc"])

    # --- KPI (full national series, independent of the year slicer) ---
    rolling_ventes_ancien_total = q.monthly(con, "ventes_ancien", ["Transactions"])
    kpi_transactions = ana.calculate_kpis(rolling_ventes_ancien_total, "Transactions")
    mom_transactions = ana.momentum_metrics(rolling_ventes_ancien_total, "Transactions")
    _kpi_ventes_ancien_month = format_month_year(
        last_valid_month(rolling_ventes_ancien_total, "Transactions"), lang_code)

    st.markdown(f"### {T[lang_code]['kpis_title']}")
    st.caption(_L(
        "Chiffres nationaux au dernier mois disponible — indépendants du filtre de période.",
        "National figures at the latest available month — independent of the period filter."))
    _kpa = st.columns(3)
    with _kpa[0]:
        st.metric(
            label=T[lang_code]["transactions_12m"],
            value=f"{kpi_transactions['current_12m']:,}".replace(",", " "),
            delta=f"{kpi_transactions['yoy_12m_pct']}% YoY",
            delta_color="normal"
        )
        st.caption(f"{T[lang_code]['mensuel']} : {kpi_transactions['current_val']:,} ({kpi_transactions['yoy_monthly_pct']}% YoY)")
        st.caption(_mom_caption(mom_transactions))
        st.caption(f"{T[lang_code]['kpi_last_month']} : {_kpi_ventes_ancien_month}")

    # --- Chart controls (same three views as the new-build tab, own widget keys) ---
    st.markdown(f"### {T[lang_code]['curves_title']}")
    chart_view_a = st.radio(T[lang_code]["chart_view_label"],
                            [T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"], T[lang_code]["chart_view_raw"]],
                            horizontal=True, key="chart_view_ancien")
    show_raw_a = True
    show_ma12_a = show_ma6_a = False
    if chart_view_a == T[lang_code]["chart_view_raw"]:
        st.caption(T[lang_code]["ma_overlay_label"])
        _ra1, _ra2, _ra3, _ra_rest = st.columns([1.3, 1.3, 1.3, 1])
        with _ra1:
            show_raw_a = st.checkbox(T[lang_code]["show_raw_label"], value=True, key="show_raw_ancien")
        with _ra2:
            show_ma12_a = st.checkbox(T[lang_code]["ma_12"], key="ma12_ancien")
        with _ra3:
            show_ma6_a = st.checkbox(T[lang_code]["ma_6"], key="ma6_ancien")

    # Rolling sums computed on the FULL history, display clipped to the selected years
    # (same rationale as the new-build tab). The year-filtered monthly aggregate feeds
    # the month-by-year comparison bars below.
    agg_ventes_ancien = q.monthly(con, "ventes_ancien", ["Transactions"], windows=(),
                                  years=year_range)
    rolling_ventes_ancien = q.monthly(con, "ventes_ancien", ["Transactions"], windows=(12, 6))
    rolling_ventes_ancien = _filter_years(rolling_ventes_ancien)

    disp_ventes_ancien = rolling_ventes_ancien.copy()
    for _c in ["Transactions", "Transactions_12M", "Transactions_6M"]:
        disp_ventes_ancien[_c] = disp_ventes_ancien[_c] / 1000.0

    _is_rolling_a = chart_view_a in (T[lang_code]["chart_view_rolling"], T[lang_code]["chart_view_rolling6"])
    _roll_suffix_a = "_12M" if chart_view_a == T[lang_code]["chart_view_rolling"] else "_6M"
    if chart_view_a == T[lang_code]["chart_view_rolling"]:
        _sub_a = T[lang_code]["sub_rolling"]
    elif chart_view_a == T[lang_code]["chart_view_rolling6"]:
        _sub_a = T[lang_code]["sub_rolling6"]
    else:
        _sub_a = T[lang_code]["sub_raw"]

    st.markdown(
        f"**{T[lang_code]['chart_ventes_ancien_main']}** "
        f"<span style='color:#6c757d;font-weight:400'>({_sub_a})</span>",
        unsafe_allow_html=True
    )
    fig2 = go.Figure()
    if _is_rolling_a:
        _tcol = f"Transactions{_roll_suffix_a}"
        fig2.add_trace(go.Scatter(x=disp_ventes_ancien["Date"], y=disp_ventes_ancien[_tcol], name=T[lang_code]["transactions_trace"], line=dict(color=COLOR_GREEN, width=3)))
        find_and_add_extrema_trace(fig2, disp_ventes_ancien, "Date", _tcol, COLOR_GREEN, text_divisor=1)
        ventes_ancien_last = last_valid_month(disp_ventes_ancien, _tcol)
    else:
        _draw_raw_a = show_raw_a or not (show_ma6_a or show_ma12_a)
        if _draw_raw_a:
            # Light/translucent bars so overlaid curves (moving averages) stay readable.
            fig2.add_trace(go.Bar(x=disp_ventes_ancien["Date"], y=disp_ventes_ancien["Transactions"], name=T[lang_code]["transactions_trace"], marker_color=COLOR_GREEN_FILL))
        ventes_ancien_last = last_valid_month(disp_ventes_ancien, "Transactions")
        # Moving averages (6m and/or 12m) on the raw monthly scale, same axis.
        add_moving_average_traces(fig2, disp_ventes_ancien, "Transactions", T[lang_code]["transactions_trace"],
                                  COLOR_GREEN_DARK, show_ma12_a, show_ma6_a, T[lang_code]["ma12_suffix"], T[lang_code]["ma6_suffix"])

    fig2.update_layout(
        xaxis_title="Date",
        yaxis_title="Thousands of transactions" if lang_code == "EN" else "Milliers de transactions",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        f"{T[lang_code]['source_label']} : {T[lang_code]['source_ventes_ancien']}  \n"
        f"{T[lang_code]['last_point_label']} : {format_month_year(ventes_ancien_last, lang_code)}"
    )

    # --- Monthly comparison by year (grouped bars) ---
    st.markdown(f"### {T[lang_code]['monthly_compare_title']}")
    st.caption(T[lang_code]["monthly_compare_desc"])

    _month_names_a = _EN_MONTHS if lang_code == "EN" else _FR_MONTHS
    _month_labels_all_a = [m.capitalize() for m in _month_names_a]
    _label_to_num_a = {lbl: i + 1 for i, lbl in enumerate(_month_labels_all_a)}
    _last_month_num_a = (pd.Timestamp(agg_ventes_ancien["Date"].max()).month
                         if not agg_ventes_ancien.empty and pd.notna(agg_ventes_ancien["Date"].max()) else 12)
    _default_month_nums_a = sorted(((_last_month_num_a - k - 1) % 12) + 1 for k in range(3))

    selected_month_labels_a = st.multiselect(
        T[lang_code]["month_select_label"],
        options=_month_labels_all_a,
        default=[_month_labels_all_a[m - 1] for m in _default_month_nums_a],
        key="month_compare_ancien"
    )
    selected_month_nums_a = sorted(_label_to_num_a[l] for l in selected_month_labels_a)
    ordered_month_labels_a = [_month_labels_all_a[m - 1] for m in selected_month_nums_a]

    if not selected_month_nums_a:
        st.info(T[lang_code]["no_month_selected"])
    else:
        st.markdown(
            f"**{T[lang_code]['chart_ventes_ancien_monthly_main']}** "
            f"<span style='color:#6c757d;font-weight:400'>({T[lang_code]['sub_monthly']})</span>",
            unsafe_allow_html=True
        )
        figm2 = build_monthly_year_bars(agg_ventes_ancien, "Transactions",
                                        selected_month_nums_a, ordered_month_labels_a, (56, 142, 60))
        figm2.update_layout(yaxis_title="Thousands of transactions" if lang_code == "EN"
                            else "Milliers de transactions")
        st.plotly_chart(figm2, use_container_width=True)
        st.caption(f"{T[lang_code]['source_label']} : {T[lang_code]['source_ventes_ancien']}")

# ==============================================================================
# TAB 3: ENVIRONNEMENT MACRO & FINANCEMENT
# ==============================================================================
with tab_macro:
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

    # --- Volume de crédits : production de crédits à l'habitat (Md€) ---
    if "Production_Credits_Habitat" in df_macro.columns and df_macro["Production_Credits_Habitat"].notna().any():
        st.markdown("---")
        st.markdown("#### " + _L("Volume de crédits à l'habitat", "Housing-loan volumes"))
        # 12m cumulatives are rolled on the FULL history then clipped to the selected years
        # (a cumul at Jan of the start year keeps its real prior-12-months window).
        # Pure new loans (HORS renégociations) = the transaction-relevant part. The BCE
        # only publishes this decomposition from 2019 (NaN before) — so it drives the
        # monthly stacked bars and a cumulative overlay, while the long total stays 2003+.
        # (Testé AVANT la requête : la colonne pure ne rejoint le cumul que si elle existe.)
        _has_split = "Production_Credits_Pure" in q.macro_data_columns(con)
        _cr_roll = ["Production_Credits_Habitat"] + (["Production_Credits_Pure"] if _has_split else [])
        _cr = q.macro_rolling(con, "Production_Credits_Habitat", _cr_roll, window=12)
        _cr = _cr.rename(columns={"Production_Credits_Habitat_cum12": "_cum12",
                                  "Production_Credits_Pure_cum12": "_pure_cum12"})
        _cr = _filter_years(_cr)
        cr_cols = st.columns(2)
        with cr_cols[0]:
            macro_chart_title(_L("Production mensuelle de crédits à l'habitat", "Monthly housing-loan production"),
                              _L("crédits nouveaux vs renégociations, Md€ par mois",
                                 "new loans vs renegotiations, €bn per month") if _has_split
                              else _L("y compris renégociations, Md€ par mois",
                                      "including renegotiations, €bn per month"))
            fig_cv = go.Figure()
            if _has_split:
                # Stacked, BPCE p.24 style: purchase-related lending vs renegotiations.
                _sp = df_macro.dropna(subset=["Production_Credits_Pure"])
                fig_cv.add_trace(go.Bar(x=_sp["Date"], y=_sp["Production_Credits_Pure"],
                                        name=_L("Crédits nouveaux (hors renégo.)", "New loans (excl. reneg.)"),
                                        marker_color=COLOR_BLUE))
                fig_cv.add_trace(go.Bar(x=_sp["Date"], y=_sp["Production_Credits_Renego"],
                                        name=_L("Renégociations", "Renegotiations"),
                                        marker_color=COLOR_TERRACOTTA))
                fig_cv.update_layout(barmode="stack")
            else:
                fig_cv.add_trace(go.Bar(x=_cr["Date"], y=_cr["Production_Credits_Habitat"],
                                        name=_L("Mensuel", "Monthly"), marker_color=COLOR_BLUE, opacity=0.45))
            apply_macro_chart_layout(fig_cv, "Md€")
            st.plotly_chart(fig_cv, use_container_width=True)
            st.caption(_L(
                "Source : BCE — statistiques MIR (achat de logement, France). Les renégociations, "
                "sans lien avec une transaction ou une construction, sont isolées (décomposition "
                "BPCE p.24 ; publiée depuis 2019).",
                "Source: ECB — MIR statistics (house purchase, France). Renegotiations, unrelated to "
                "any transaction or construction, are split out (BPCE p.24 decomposition; published "
                "from 2019)."))
        with cr_cols[1]:
            macro_chart_title(_L("Production cumulée sur 12 mois", "12-month cumulative production"),
                              _L("Md€ / an", "€bn / year"))
            fig_cc = go.Figure()
            _c12 = _cr.dropna(subset=["_cum12"])
            fig_cc.add_trace(go.Scatter(x=_c12["Date"], y=_c12["_cum12"],
                                        name=_L("Total (y.c. renégo.)", "Total (incl. reneg.)"),
                                        line=dict(color=COLOR_GREEN, width=2),
                                        fill="tozeroy", fillcolor="rgba(56,142,60,0.12)"))
            add_last_value_label(fig_cc, _c12, "Date", "_cum12", COLOR_GREEN, lang_code, decimals=0)
            if _has_split:
                _p12 = _cr.dropna(subset=["_pure_cum12"])
                fig_cc.add_trace(go.Scatter(x=_p12["Date"], y=_p12["_pure_cum12"],
                                            name=_L("Hors renégociations", "Excl. renegotiations"),
                                            line=dict(color=COLOR_BRICK, width=2, dash="dot")))
                add_last_value_label(fig_cc, _p12, "Date", "_pure_cum12", COLOR_BRICK, lang_code, decimals=0)
            apply_macro_chart_layout(fig_cc, "Md€")
            st.plotly_chart(fig_cc, use_container_width=True)
            st.caption(_L(
                "Rythme annuel : total ~175 Md€ attendus en 2026 par BPCE L'Observatoire ; « hors "
                "renégociations » isole la part réellement liée aux achats.",
                "Annual run-rate: total ~€175bn expected in 2026 by BPCE L'Observatoire; 'excl. "
                "renegotiations' isolates the genuinely purchase-related part."))

    # --- Demande de crédits à l'habitat (enquête BLS, BdF/BCE) — indicateur avancé ---
    # Volume de crédits = ce qui a été distribué (réalisé) ; la demande BLS anticipe le
    # tournant AVANT la production. Le solde « perspectives à 3 mois » (BPCE p.23) est
    # passé nettement négatif fin 2025 / début 2026 → signal avancé de repli.
    if ("Demande_Credit_Perspectives" in df_macro.columns
            and df_macro["Demande_Credit_Perspectives"].notna().any()):
        st.markdown("---")
        st.markdown("#### " + _L("Demande de crédits à l'habitat (enquête BLS)",
                                 "Housing-loan demand (Bank Lending Survey)"))
        macro_chart_title(
            _L("Demande de crédits à l'habitat des ménages",
               "Household housing-loan demand"),
            _L("solde d'opinion net des banques, en % — >0 = demande en hausse",
               "net balance of banks' opinion, % — >0 = rising demand"))
        _bls = df_macro.copy()
        fig_bls = go.Figure()
        _r = _bls.dropna(subset=["Demande_Credit_Realisee"])
        fig_bls.add_trace(go.Scatter(
            x=_r["Date"], y=_r["Demande_Credit_Realisee"],
            name=_L("Réalisé (3 derniers mois)", "Realised (past 3 months)"),
            line=dict(color=COLOR_SUBTLE, width=2)))
        _f = _bls.dropna(subset=["Demande_Credit_Perspectives"])
        fig_bls.add_trace(go.Scatter(
            x=_f["Date"], y=_f["Demande_Credit_Perspectives"],
            name=_L("Perspectives (3 prochains mois)", "Expected (next 3 months)"),
            line=dict(color=COLOR_BRICK, width=2.5)))
        add_last_value_label(fig_bls, _f, "Date", "Demande_Credit_Perspectives",
                             COLOR_BRICK, lang_code, decimals=0)
        fig_bls.add_hline(y=0, line_dash="dash", line_color="grey")
        apply_macro_chart_layout(fig_bls, _L("Solde net (%)", "Net balance (%)"))
        st.plotly_chart(fig_bls, use_container_width=True)
        st.caption(_L(
            "Source : BCE / Banque de France — enquête sur la distribution du crédit bancaire "
            "(Bank Lending Survey), demande de crédits à l'habitat des ménages, France, "
            "pourcentage net. Indicateur avancé de la production de crédits (BPCE p.23).",
            "Source: ECB / Banque de France — Bank Lending Survey, demand for household "
            "house-purchase loans, France, net percentage. A leading indicator of loan "
            "production (BPCE p.23)."))

    # --- Renovation pillar — the second-œuvre demand that neither new construction nor
    # existing-home transactions capture (a large share of Somfy-type product demand comes
    # from the installed stock, not moves). Real, national; NaN until fetch_new_sources.py
    # produces the CSVs, in which case a hint replaces the charts.
    st.markdown("---")
    st.markdown("#### " + _L("Rénovation & second œuvre (pilier complémentaire)",
                             "Renovation & secondary works (complementary pillar)"))
    _reno_cols = [("Reno_Activite_Batiment",
                   _L("Activité passée — second œuvre", "Past activity — second-œuvre"),
                   _L("solde d'opinion CVS", "SA opinion balance"), COLOR_BRICK),
                  ("Reno_Activite_Prevue",
                   _L("Activité prévue — second œuvre", "Planned activity — second-œuvre"),
                   _L("solde d'opinion CVS (avancé)", "SA opinion balance (leading)"), COLOR_GREEN)]
    _reno_present = [c for c in _reno_cols
                     if c[0] in df_macro.columns and df_macro[c[0]].notna().any()]
    if not _reno_present:
        st.info(_L(
            "Pilier rénovation non encore alimenté. Lancez `python fetch_new_sources.py` "
            "(fonction `build_renovation`) pour ajouter l'activité passée et prévue du second "
            "œuvre (enquête de conjoncture bâtiment INSEE) — un troisième driver de la demande "
            "second œuvre, indépendant du neuf et des transactions.",
            "Renovation pillar not populated yet. Run `python fetch_new_sources.py` "
            "(`build_renovation`) to add past and planned second-œuvre activity (INSEE building "
            "business survey) — a third second-œuvre demand driver, independent of new-build "
            "and transactions."))
    else:
        reno_c = st.columns(len(_reno_present))
        for (_c, _title, _sub, _clr), _rc in zip(_reno_present, reno_c):
            with _rc:
                macro_chart_title(_title, _sub)
                s = df_macro.dropna(subset=[_c])
                fig_r = go.Figure()
                fig_r.add_trace(go.Scatter(x=s["Date"], y=s[_c], name=_title,
                                           line=dict(color=_clr, width=2)))
                fig_r.add_hline(y=0, line_dash="dash", line_color="grey")
                add_last_value_label(fig_r, s, "Date", _c, _clr, lang_code, decimals=0)
                apply_macro_chart_layout(fig_r, _sub)
                st.plotly_chart(fig_r, use_container_width=True)
        st.caption(_L(
            "Source : INSEE — Enquête mensuelle de conjoncture dans l'industrie du bâtiment, "
            "tendance de l'activité (passée/prévue), second œuvre, série CVS (idbanks 001586954 / "
            "001586886). Un solde négatif = plus d'entreprises signalant une baisse d'activité. La "
            "rénovation tire une part de la demande second œuvre non expliquée par le neuf ni les transactions.",
            "Source: INSEE — Monthly building-industry business survey, activity trend (past/planned), "
            "second-œuvre, SA (idbanks 001586954 / 001586886). A negative balance = more firms reporting "
            "falling activity. Renovation drives second-œuvre demand not explained by new-build or transactions."))


# ==============================================================================
# TAB: ACTUALITÉS & AIDES (veille curatée — dispositifs FR/UE et impact potentiel)
# Contenu éditorial dans actualites.py (NEWS_ITEMS) ; ici uniquement le rendu.
# ==============================================================================
with tab_actus:
    st.header(_L("📰 Actualités — aides & plans de relance logement",
                 "📰 News — housing aid & stimulus plans"))
    st.write(_L(
        "Veille sur les grands dispositifs publics français et européens qui soutiennent (ou "
        "freinent) le marché du logement : plan « Relance Logement » / dispositif Jeanbrun, "
        "MaPrimeRénov', PTZ, CEE, plan européen pour le logement abordable… Pour chaque mesure : "
        "statut, jalons, montants et **impact potentiel sur les trois piliers du modèle** "
        "(neuf, ancien, rénovation). Grille de lecture qualitative, à croiser avec l'onglet "
        "« 📡 Prévision & Scénarios ».",
        "Watchlist of the major French and EU public schemes supporting (or restraining) the "
        "housing market: 'Relance Logement' plan / Jeanbrun scheme, MaPrimeRénov', PTZ, CEE, "
        "European Affordable Housing Plan… For each measure: status, milestones, amounts and "
        "**potential impact on the model's three pillars** (new-build, existing homes, "
        "renovation). A qualitative reading grid, to cross with the 'Forecast & Scenarios' tab."))
    st.caption(_L(
        f"⚠️ Contenu éditorial mis à jour manuellement (dernière revue : {actu.MAJ}), sur la base "
        "de sources publiques citées dans chaque fiche. Les impacts sont des lectures "
        "qualitatives, pas des sorties de modèle.",
        f"⚠️ Editorial content updated manually (last review: {actu.MAJ}), based on the public "
        "sources cited in each card. Impacts are qualitative readings, not model outputs."))

    _items_all = actu.items_sorted()

    # --- KPIs ---
    _n_vigueur = sum(1 for it in _items_all if it["statut"] == "vigueur")
    _next_jalons = sorted(
        [(d, it) for it in _items_all for d, _lbl, _typ in it.get("jalons", [])
         if d > actu.MAJ],
        key=lambda t: t[0])
    ka = st.columns(4)
    ka[0].metric(_L("Dispositifs suivis", "Tracked measures"), len(_items_all))
    ka[1].metric(_L("En vigueur", "In force"), _n_vigueur)
    ka[2].metric(_L("Budget MaPrimeRénov' 2026", "MaPrimeRénov' 2026 budget"),
                 _L("3,6 Md€", "€3.6bn"))
    if _next_jalons:
        _nd, _nit = _next_jalons[0]
        ka[3].metric(_L("Prochaine échéance", "Next deadline"),
                     pd.Timestamp(_nd).strftime("%m/%Y"),
                     delta=_nit["court"][lang_code], delta_color="off")

    # --- Filtres ---
    fa = st.columns(3)
    _cat_opts = list(actu.CATEGORIES[lang_code].keys())
    _stat_opts = list(actu.STATUTS[lang_code].keys())
    _pil_opts = list(actu.PILIERS[lang_code].keys())
    with fa[0]:
        _cat_sel = st.multiselect(_L("Périmètre", "Scope"), _cat_opts, default=_cat_opts,
                                  format_func=lambda c: actu.CATEGORIES[lang_code][c],
                                  key="actu_cat")
    with fa[1]:
        _stat_sel = st.multiselect(_L("Statut", "Status"), _stat_opts, default=_stat_opts,
                                   format_func=lambda s: actu.STATUTS[lang_code][s],
                                   key="actu_statut")
    with fa[2]:
        _pil_sel = st.multiselect(
            _L("Pilier impacté", "Pillar affected"), _pil_opts, default=_pil_opts,
            format_func=lambda p: actu.PILIERS[lang_code][p], key="actu_pilier",
            help=_L("Ne garde que les mesures ayant un impact non neutre sur au moins un "
                    "des piliers sélectionnés.",
                    "Keeps only measures with a non-neutral impact on at least one selected pillar."))
    _items = [it for it in _items_all
              if it["categorie"] in _cat_sel and it["statut"] in _stat_sel
              and (not _pil_sel or any(it["impacts"][p] != 0 for p in _pil_sel)
                   or all(v == 0 for v in it["impacts"].values()))]
    if not _items:
        st.info(_L("Aucune mesure ne correspond aux filtres.", "No measure matches the filters."))

    if _items:
        # --- Matrice d'impact ---
        st.subheader(_L("🎯 Matrice d'impact par pilier du modèle",
                        "🎯 Impact matrix by model pillar"))
        st.caption(_L(
            "Lecture qualitative de la direction attendue : ⬆⬆ soutien fort · ⬆ soutien · "
            "➖ neutre/mitigé · ⬇ frein. Les piliers correspondent aux trois moteurs du modèle "
            "de ventes (permis SIT@DEL, transactions IGEDD, activité rénovation INSEE).",
            "Qualitative read of the expected direction: ⬆⬆ strong support · ⬆ support · "
            "➖ neutral/mixed · ⬇ headwind. Pillars map to the sales model's three drivers "
            "(SIT@DEL permits, IGEDD transactions, INSEE renovation activity)."))
        st.dataframe(actu.impact_matrix(_items, lang_code),
                     use_container_width=True, hide_index=True)

        # --- Échéancier ---
        st.subheader(_L("🗓️ Échéancier des mesures", "🗓️ Policy timeline"))
        _jf = actu.jalons_frame(_items, lang_code)
        fig_tl = go.Figure()
        _seen_types = set()
        for _typ, _tinfo in actu.JALON_TYPES.items():
            sub = _jf[_jf["Type"] == _typ]
            if sub.empty:
                continue
            _seen_types.add(_typ)
            fig_tl.add_trace(go.Scatter(
                x=sub["Date"], y=sub["Dispositif"], mode="markers",
                name=_tinfo[lang_code],
                marker=dict(symbol=_tinfo["symbol"], size=13,
                            color=[COLOR_BRICK if c == "FR" else COLOR_BLUE
                                   for c in sub["Categorie"]],
                            line=dict(width=1, color="white")),
                text=sub["Jalon"],
                hovertemplate="%{y} — %{x|%d/%m/%Y}<br>%{text}<extra></extra>"))
        # Ligne « aujourd'hui » (add_shape : compatible axes dates, contrairement à add_vline)
        _today = pd.Timestamp(actu.MAJ)
        fig_tl.add_shape(type="line", x0=_today, x1=_today, y0=0, y1=1, yref="paper",
                         line=dict(color=COLOR_SUBTLE, width=1, dash="dash"))
        fig_tl.add_annotation(x=_today, y=1.04, yref="paper", showarrow=False,
                              text=_L("Aujourd'hui", "Today"),
                              font=dict(color=COLOR_SUBTLE, size=11))
        apply_macro_chart_layout(fig_tl, "")
        fig_tl.update_layout(
            height=max(300, 60 + 34 * _jf["Dispositif"].nunique()),
            yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_tl, use_container_width=True)
        st.caption(_L(
            "🔴 mesures françaises · 🔵 mesures européennes. ● entrée en vigueur · ◆ jalon · "
            "✕ échéance/attendu. Ligne pointillée = date de la dernière revue.",
            "🔴 French measures · 🔵 EU measures. ● entry into force · ◆ milestone · "
            "✕ deadline/expected. Dashed line = last review date."))

        # --- Fiches détaillées ---
        st.subheader(_L("🗞️ Le détail des mesures", "🗞️ Measures in detail"))
        for it in _items:
            _hdr = (f"{actu.CATEGORIES[lang_code][it['categorie']].split(' ')[0]} "
                    f"{it['titre'][lang_code]} — {actu.STATUTS[lang_code][it['statut']]}")
            with st.expander(_hdr):
                st.markdown(it["resume"][lang_code])
                mc = st.columns(3)
                if it.get("montant"):
                    mc[0].markdown(_L("**💶 Chiffre clé** : ", "**💶 Key figure**: ")
                                   + it["montant"][lang_code])
                mc[1].markdown(_L("**⏳ Horizon de transmission** : ",
                                  "**⏳ Transmission horizon**: ") + it["horizon"][lang_code])
                _echs = [(d, lbl) for d, lbl, typ in it.get("jalons", []) if typ == "echeance"]
                if _echs:
                    mc[2].markdown(_L("**📅 Échéance** : ", "**📅 Deadline**: ")
                                   + f"{pd.Timestamp(_echs[0][0]).strftime('%d/%m/%Y')} — "
                                   + _echs[0][1][lang_code])
                ic = st.columns(3)
                for _i, _p in enumerate(("neuf", "ancien", "renovation")):
                    ic[_i].markdown(f"{actu.PILIERS[lang_code][_p]}<br>"
                                    f"**{actu.IMPACT_LABELS[lang_code][it['impacts'][_p]]}**",
                                    unsafe_allow_html=True)
                st.markdown(_L("**🎯 Impact potentiel** — ", "**🎯 Potential impact** — ")
                            + it["impact_detail"][lang_code])
                st.caption(_L("Sources : ", "Sources: ") + " · ".join(
                    f"[{lbl}]({url})" for lbl, url in it["sources"]))

        st.info(_L(
            "💡 Pour chiffrer un scénario (ex. relance de la demande via Jeanbrun/PTZ → baisse "
            "des taux effectifs ou hausse des intentions d'achat), utilisez les curseurs de "
            "l'onglet **📡 Prévision & Scénarios** : ces mesures agissent sur les mêmes canaux "
            "(taux, intentions, chômage) que le modèle de transactions.",
            "💡 To quantify a scenario (e.g. demand restart via Jeanbrun/PTZ → lower effective "
            "rates or higher purchase intentions), use the sliders in the **📡 Forecast & "
            "Scenarios** tab: these measures act on the same channels (rates, intentions, "
            "unemployment) as the transactions model."))


# ==============================================================================
# TAB 2 (suite): PRIX & ACCESSIBILITÉ — seconde moitié de l'onglet « Marché de
# l'ancien » (indices Notaires-INSEE + capacité d'emprunt / accessibilité). Ce
# second bloc `with tab_ancien:` s'affiche à la suite des transactions IGEDD.
# ==============================================================================
with tab_ancien:
    st.markdown("---")
    st.header(_L("🏷️ Prix des logements & accessibilité",
                 "🏷️ House prices & affordability"))
    st.write(_L(
        "Indices de prix des logements anciens (Notaires-INSEE, base 100 = 2015, France "
        "métropolitaine) et lecture de l'accessibilité : capacité d'emprunt à mensualité "
        "constante et indice d'accessibilité (capacité rapportée aux prix).",
        "Existing-home price indices (Notaires-INSEE, base 100 = 2015, metropolitan "
        "France) and an affordability read: constant-instalment borrowing capacity and an "
        "affordability index (capacity over prices)."))

    _labels = {"Prix_Ancien_Ensemble": _L("Ensemble", "All dwellings"),
               "Prix_Ancien_Appartements": _L("Appartements", "Apartments"),
               "Prix_Ancien_Maisons": _L("Maisons", "Houses")}
    _series_cols = [("Prix_Ancien_Ensemble", COLOR_BRICK),
                    ("Prix_Ancien_Appartements", COLOR_BLUE),
                    ("Prix_Ancien_Maisons", COLOR_GREEN)]

    if "Prix_Ancien_Ensemble" not in df_macro.columns or df_macro["Prix_Ancien_Ensemble"].dropna().empty:
        st.warning(_L(
            "Indices de prix indisponibles — lancez `python fetch_new_sources.py` pour "
            "générer les fichiers source.",
            "Price indices unavailable — run `python fetch_new_sources.py` to generate the source files."))
    else:
        # --- KPIs: dernier point + glissement annuel (4 trimestres) ---
        kcols = st.columns(3)
        for (_c, _), _kc in zip(_series_cols, kcols):
            s = df_macro.dropna(subset=[_c])
            if len(s) >= 5:
                last, prev = s[_c].iloc[-1], s[_c].iloc[-5]
                yoy = (last / prev - 1) * 100
                v = f"{last:.1f}"
                d = f"{yoy:+.1f}%"
                if lang_code == "FR":
                    v, d = v.replace(".", ","), d.replace(".", ",")
                _kc.metric(_labels[_c], v, d)
        _last_date = df_macro.dropna(subset=["Prix_Ancien_Ensemble"])["Date"].iloc[-1]
        st.caption(_L(f"Dernier point : {_last_date:%Y-%m} · base 100 = moyenne 2015 · variation en glissement annuel.",
                      f"Latest: {_last_date:%Y-%m} · base 100 = 2015 average · year-on-year change."))

        _dur = st.radio(_L("Durée d'emprunt (modèle de capacité)", "Loan term (capacity model)"),
                        [25, 20], horizontal=True,
                        format_func=lambda y: f"{y} " + _L("ans", "yrs"))

        # --- Row 1: price levels + YoY growth ---
        r1 = st.columns(2)
        with r1[0]:
            macro_chart_title(_L("Prix des logements anciens", "Existing-home prices"),
                              _L("indices Notaires-INSEE, base 100 = 2015", "Notaires-INSEE indices, base 100 = 2015"))
            fig_p = go.Figure()
            # The 3 end values sit within ~1.5 pts, so their labels collide — rank them
            # and nudge each vertically (highest up, lowest down) to keep them readable.
            _lasts = {c: df_macro.dropna(subset=[c])[c].iloc[-1] for c, _ in _series_cols}
            _order = sorted(_series_cols, key=lambda cc: _lasts[cc[0]], reverse=True)
            _ysh = {c: (1 - _order.index((c, col))) * 13 for c, col in _series_cols}
            for _c, _col in _series_cols:
                s = df_macro.dropna(subset=[_c])
                fig_p.add_trace(go.Scatter(x=s["Date"], y=s[_c], name=_labels[_c], line=dict(color=_col, width=2)))
                add_last_value_label(fig_p, s, "Date", _c, _col, lang_code, decimals=0, yshift=_ysh[_c])
            apply_macro_chart_layout(fig_p, _L("Indice (base 100)", "Index (base 100)"))
            st.plotly_chart(fig_p, use_container_width=True)
            st.caption(_L("Source : INSEE — indices Notaires-INSEE des prix des logements anciens, France métropolitaine (CVS), "
                          "idbanks 010567059 (ensemble) / 010567057 (appartements) / 010567061 (maisons).",
                          "Source: INSEE — Notaires-INSEE existing-home price indices, metropolitan France (SA), "
                          "idbanks 010567059 (all) / 010567057 (apartments) / 010567061 (houses)."))
        with r1[1]:
            macro_chart_title(_L("Évolution annuelle des prix", "Annual price growth"),
                              _L("glissement sur 1 an, %", "year-on-year, %"))
            fig_g = go.Figure()
            for _c, _col in _series_cols:
                s = df_macro.dropna(subset=[_c]).copy()
                s["_yoy"] = s[_c].pct_change(4) * 100
                s = s.dropna(subset=["_yoy"])
                fig_g.add_trace(go.Scatter(x=s["Date"], y=s["_yoy"], name=_labels[_c], line=dict(color=_col, width=2)))
            fig_g.add_hline(y=0, line_dash="dash", line_color="grey")
            apply_macro_chart_layout(fig_g, "%")
            st.plotly_chart(fig_g, use_container_width=True)
            st.caption(_L("Source : INSEE — indices Notaires-INSEE (calcul en glissement annuel). Hausse pour le 4ᵉ trimestre consécutif fin 2025 (Note de conjoncture n°71).",
                          "Source: INSEE — Notaires-INSEE indices (year-on-year calculation). 4th straight quarterly rise at end-2025 (Notaires bulletin no. 71)."))

        # --- Row 2: capacity vs price + affordability index (base 100 = 2015) ---
        # Prices are already base-2015; capacity is rebased to its 2015 mean computed on
        # the FULL history so the sidebar year slicer never moves the base.
        _full = df_macro_full.dropna(subset=["Credit_Logement_Taux_Interet"]).copy()
        _cap_2015 = _borrow_capacity_factor(
            _full.loc[_full["Date"].dt.year == 2015, "Credit_Logement_Taux_Interet"], _dur).mean()
        if not (_cap_2015 and _cap_2015 > 0):
            _cap_2015 = _borrow_capacity_factor(_full["Credit_Logement_Taux_Interet"].iloc[:1], _dur)[0]
        _acc = df_macro.dropna(subset=["Credit_Logement_Taux_Interet", "Prix_Ancien_Ensemble"]).copy()
        _acc["_capidx"] = _borrow_capacity_factor(_acc["Credit_Logement_Taux_Interet"], _dur) / _cap_2015 * 100
        _acc["_access"] = _acc["_capidx"] / _acc["Prix_Ancien_Ensemble"] * 100
        r2 = st.columns(2)
        with r2[0]:
            macro_chart_title(_L("Capacité d'emprunt vs prix", "Borrowing capacity vs prices"),
                              _L(f"base 100 = 2015 · mensualité constante, {_dur} ans",
                                 f"base 100 = 2015 · constant instalment, {_dur} yrs"))
            fig_c = go.Figure()
            fig_c.add_trace(go.Scatter(x=_acc["Date"], y=_acc["_capidx"],
                                       name=_L("Capacité d'emprunt", "Borrowing capacity"),
                                       line=dict(color=COLOR_GREEN, width=2)))
            s = df_macro.dropna(subset=["Prix_Ancien_Ensemble"])
            fig_c.add_trace(go.Scatter(x=s["Date"], y=s["Prix_Ancien_Ensemble"],
                                       name=_L("Prix (Ensemble)", "Prices (all)"),
                                       line=dict(color=COLOR_BRICK, width=2)))
            fig_c.add_hline(y=100, line_dash="dot", line_color="grey")
            apply_macro_chart_layout(fig_c, _L("Indice (base 100)", "Index (base 100)"))
            st.plotly_chart(fig_c, use_container_width=True)
            st.caption(_L("Sources : INSEE (prix Notaires-INSEE), Banque de France/BCE (taux crédit habitat) · capacité = principal finançable à mensualité constante (calcul de l'auteur).",
                          "Sources: INSEE (Notaires-INSEE prices), Banque de France/ECB (housing-loan rate) · capacity = principal a constant instalment can service (author's calc)."))
        with r2[1]:
            macro_chart_title(_L("Indice d'accessibilité", "Affordability index"),
                              _L("capacité d'emprunt ÷ prix, base 100 = 2015", "capacity ÷ prices, base 100 = 2015"))
            fig_a = go.Figure()
            fig_a.add_trace(go.Scatter(x=_acc["Date"], y=_acc["_access"],
                                       name=_L("Accessibilité", "Affordability"),
                                       line=dict(color=COLOR_BRICK, width=2),
                                       fill="tozeroy", fillcolor=COLOR_BRICK_ZONE))
            fig_a.add_hline(y=100, line_dash="dash", line_color="grey",
                            annotation_text=_L("niveau 2015", "2015 level"))
            add_last_value_label(fig_a, _acc, "Date", "_access", COLOR_BRICK, lang_code, decimals=0)
            apply_macro_chart_layout(fig_a, _L("Indice (base 100)", "Index (base 100)"))
            st.plotly_chart(fig_a, use_container_width=True)
            st.caption(_L("Sources : INSEE (prix) + Banque de France/BCE (taux) · calcul de l'auteur. Sous 100 = logement moins accessible qu'en 2015 (hausse des prix et/ou des taux).",
                          "Sources: INSEE (prices) + Banque de France/ECB (rates) · author's calc. Below 100 = housing less affordable than in 2015 (higher prices and/or rates)."))

        # --- Prix neuf vs ancien (INSEE) : niveaux + glissement annuel ---
        if "Prix_Neuf" in df_macro.columns and df_macro["Prix_Neuf"].notna().any():
            st.markdown("---")
            st.markdown("#### " + _L("Prix des logements neufs vs anciens",
                                     "New vs existing-home prices"))
            _na_defs = [("Prix_Neuf", COLOR_BLUE, _L("Neuf", "New")),
                        ("Prix_Ancien_Ensemble", COLOR_BRICK, _L("Ancien", "Existing"))]
            r3 = st.columns(2)
            with r3[0]:
                macro_chart_title(_L("Indices de prix", "Price indices"),
                                  _L("neuf & ancien, base 100 = 2015", "new & existing, base 100 = 2015"))
                fig_na = go.Figure()
                for _c, _col, _nm in _na_defs:
                    s = df_macro.dropna(subset=[_c])
                    fig_na.add_trace(go.Scatter(x=s["Date"], y=s[_c], name=_nm, line=dict(color=_col, width=2)))
                    add_last_value_label(fig_na, s, "Date", _c, _col, lang_code, decimals=0)
                apply_macro_chart_layout(fig_na, _L("Indice (base 100)", "Index (base 100)"))
                st.plotly_chart(fig_na, use_container_width=True)
                st.caption(_L("Source : INSEE — indice des prix des logements neufs (idbank 010751595) et Notaires-INSEE anciens.",
                              "Source: INSEE — new-dwelling price index (idbank 010751595) and Notaires-INSEE existing homes."))
            with r3[1]:
                macro_chart_title(_L("Croissance en glissement annuel", "Year-on-year growth"),
                                  _L("neuf & ancien, %", "new & existing, %"))
                fig_ng = go.Figure()
                for _c, _col, _nm in _na_defs:
                    s = df_macro.dropna(subset=[_c]).copy()
                    s["_yoy"] = s[_c].pct_change(4) * 100
                    s = s.dropna(subset=["_yoy"])
                    fig_ng.add_trace(go.Scatter(x=s["Date"], y=s["_yoy"], name=_nm, line=dict(color=_col, width=2)))
                fig_ng.add_hline(y=0, line_dash="dash", line_color="grey")
                apply_macro_chart_layout(fig_ng, "%")
                st.plotly_chart(fig_ng, use_container_width=True)
                st.caption(_L("Le neuf a moins corrigé que l'ancien : l'écart de prix neuf/ancien s'est creusé (BPCE L'Observatoire).",
                              "New-build prices corrected less than existing homes: the new/existing gap widened (BPCE L'Observatoire)."))


# ==============================================================================
# TAB 1 (suite): COMMERCIALISATION DES LOGEMENTS NEUFS (ECLN) — seconde moitié de
# l'onglet « Marché du neuf ». Ce second bloc `with tab_neuf:` s'affiche à la
# suite des permis / mises en chantier SIT@DEL.
# ==============================================================================
with tab_neuf:
    st.markdown("---")
    st.header(_L("🏗️ Commercialisation des logements neufs (ECLN)", "🏗️ New-build sales (ECLN)"))
    st.write(_L(
        "Commercialisation des logements neufs (SDES — ECLN, national, trimestriel CVS-CJO) : encours "
        "(stock à la vente), mises en vente, délai d'écoulement, prix au m² et réservations par catégorie "
        "d'acquéreurs (particuliers, bailleurs sociaux, investisseurs institutionnels). Le délai "
        "d'écoulement — proche de deux ans — est un signal avancé de la demande de second œuvre.",
        "New-build commercialisation (SDES — ECLN, national, quarterly SA): outstanding stock, new "
        "listings, absorption time, price per m² and reservations by buyer type (private buyers, social "
        "landlords, institutional investors). Absorption time — close to two years — leads secondary-works demand."))
    if df_ecln.empty:
        st.warning(_L("Données ECLN indisponibles — lancez `python fetch_new_sources.py`.",
                      "ECLN data unavailable — run `python fetch_new_sources.py`."))
    else:
        e = df_ecln.dropna(subset=["Reservations"]).sort_values("Date").copy()
        e["DelaiMois"] = e["DelaiEcoulement"] * 3.0  # DELAI_ECOUL is in quarters
        last = e.iloc[-1]
        _q = f"{last['Date'].year}-T{(last['Date'].month - 1) // 3 + 1}"

        def _fnum(x):
            return f"{int(x):,}".replace(",", " ")
        k = st.columns(4)
        k[0].metric(_L("Réservations particuliers (trim.)", "Private reservations (qtr)"), _fnum(last["Reservations"]))
        k[1].metric(_L("Mises en vente (trim.)", "New listings (qtr)"), _fnum(last["MisesEnVente"]))
        k[2].metric(_L("Encours à la vente", "Outstanding stock"), _fnum(last["Encours"]))
        k[3].metric(_L("Délai d'écoulement", "Absorption time"),
                    f"{last['DelaiMois']:.0f} " + _L("mois", "mo"))
        st.caption(_L(f"Dernier trimestre disponible : {_q}. Source : SDES — ECLN (CVS-CJO).",
                      f"Latest available quarter: {_q}. Source: SDES — ECLN (SA)."))

        # Row 1: encours + mises en vente (même graphique) | délai d'écoulement (à droite)
        er1 = st.columns(2)
        with er1[0]:
            macro_chart_title(_L("Encours & mises en vente", "Outstanding stock & new listings"),
                              _L("encours = stock en fin de trimestre · mises en vente = flux trimestriel",
                                 "stock = end-of-quarter level · listings = quarterly flow"))
            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(x=e["Date"], y=e["Encours"], name=_L("Encours à la vente", "Outstanding stock"),
                                       line=dict(color=COLOR_TEXT, width=2)))
            fig_s.add_trace(go.Scatter(x=e["Date"], y=e["MisesEnVente"], name=_L("Mises en vente", "New listings"),
                                       line=dict(color=COLOR_BLUE, width=2)))
            add_last_value_label(fig_s, e, "Date", "Encours", COLOR_TEXT, lang_code, decimals=0)
            add_last_value_label(fig_s, e, "Date", "MisesEnVente", COLOR_BLUE, lang_code, decimals=0)
            apply_macro_chart_layout(fig_s, _L("Nombre de logements", "Dwellings"))
            st.plotly_chart(fig_s, use_container_width=True)
            st.caption(_L("Stock élevé face à des mises en vente historiquement basses (SDES — ECLN).",
                          "High stock against historically low new listings (SDES — ECLN)."))
        with er1[1]:
            macro_chart_title(_L("Délai d'écoulement du stock", "Stock absorption time"),
                              _L("mois de commercialisation", "months of marketing"))
            fig_d = go.Figure()
            fig_d.add_trace(go.Scatter(x=e["Date"], y=e["DelaiMois"], name=_L("Délai (mois)", "Time (months)"),
                                       line=dict(color=COLOR_BRICK, width=2), fill="tozeroy", fillcolor=COLOR_BRICK_ZONE))
            fig_d.add_hline(y=24, line_dash="dash", line_color="grey",
                            annotation_text=_L("≈ 2 ans", "≈ 2 years"))
            add_last_value_label(fig_d, e, "Date", "DelaiMois", COLOR_BRICK, lang_code, decimals=0)
            apply_macro_chart_layout(fig_d, _L("Mois", "Months"))
            st.plotly_chart(fig_d, use_container_width=True)
            st.caption(_L("Près de deux fois le niveau de 2018-2022 : sortie de crise repoussée (BPCE L'Observatoire).",
                          "Nearly double the 2018-2022 level: recovery delayed (BPCE L'Observatoire)."))

        # Row 2: réservations par catégorie d'acquéreurs (barres empilées) | prix au m²
        er2 = st.columns(2)
        with er2[0]:
            macro_chart_title(_L("Réservations par catégorie d'acquéreurs", "Reservations by buyer type"),
                              _L("logements neufs, par trimestre", "new dwellings, per quarter"))
            eb = df_ecln.dropna(subset=["Resa_Sociaux"]).sort_values("Date")
            fig_cat = go.Figure()
            fig_cat.add_trace(go.Bar(x=eb["Date"], y=eb["Reservations"], name=_L("Particuliers", "Private buyers"),
                                     marker_color=COLOR_BRICK))
            fig_cat.add_trace(go.Bar(x=eb["Date"], y=eb["Resa_Sociaux"], name=_L("Bailleurs sociaux", "Social landlords"),
                                     marker_color=COLOR_BLUE))
            fig_cat.add_trace(go.Bar(x=eb["Date"], y=eb["Resa_Institutionnels"],
                                     name=_L("Investisseurs institutionnels", "Institutional investors"),
                                     marker_color=COLOR_SUNFLOWER))
            apply_macro_chart_layout(fig_cat, _L("Réservations", "Reservations"))
            fig_cat.update_layout(barmode="stack")
            st.plotly_chart(fig_cat, use_container_width=True)
            st.caption(_L("Réservations en bloc (bailleurs sociaux et institutionnels) via l'enquête ECLN « ventes aux "
                          "institutionnels » ; la part des particuliers recule (BPCE L'Observatoire). Source : SDES — ECLN.",
                          "Block sales (social landlords and institutions) from the ECLN 'sales to institutions' survey; the "
                          "private-buyer share is receding (BPCE L'Observatoire). Source: SDES — ECLN."))
        with er2[1]:
            macro_chart_title(_L("Prix des appartements neufs", "New-apartment prices"),
                              _L("prix moyen au m² (collectif)", "average price per m² (multi-family)"))
            fig_pm = go.Figure()
            _pm = e.dropna(subset=["PrixM2_Collectif"])
            fig_pm.add_trace(go.Scatter(x=_pm["Date"], y=_pm["PrixM2_Collectif"], name=_L("Prix au m²", "Price per m²"),
                                        line=dict(color=COLOR_GREEN, width=2)))
            add_last_value_label(fig_pm, _pm, "Date", "PrixM2_Collectif", COLOR_GREEN, lang_code, decimals=0)
            apply_macro_chart_layout(fig_pm, "€/m²")
            st.plotly_chart(fig_pm, use_container_width=True)
            st.caption(_L("Prix du neuf rigides malgré la faiblesse des ventes (SDES — ECLN).",
                          "New-build prices stay rigid despite weak sales (SDES — ECLN)."))


# ==============================================================================
# TAB 4: PRÉVISION & SCÉNARIOS (nowcast transactions + backtest + scénarios)
# ==============================================================================
# Train/test split for the transactions model: the lag search AND the backtest train use
# data ≤ this date, so the out-of-sample MAPE is measured on a period the lags never saw.
_FORECAST_SPLIT = "2021-12-01"

@st.cache_data(show_spinner=False)
def _forecast_bundle(macro, tx12):
    """Fit the (expensive) forecast models once and cache them, so moving the scenario
    sliders only recomputes the cheap scenario arithmetic, not the lag grid-search.

    `tx12` est passée en paramètre plutôt que dérivée ici : elle vient désormais de la
    couche SQL, et une connexion DuckDB n'est ni hachable ni sérialisable par
    `st.cache_data`. La Series, elle, est une clé de cache parfaitement valide.
    """
    rm = fc.fit_rate_model(macro)
    # Lags searched on the TRAIN window only (no leakage into the backtest period).
    lags = fc.search_tx_lags(macro, tx12, split=_FORECAST_SPLIT)
    tm = fc.fit_tx_model(macro, tx12, split=_FORECAST_SPLIT, **lags)
    return rm, lags, tm



with tab_forecast:
    st.header(_L("📡 Prévision des transactions & scénarios",
                 "📡 Transaction forecast & scenarios"))
    st.write(_L(
        "Formalisation des onglets Time-Lag / Composite en un modèle chiffré « indicateurs "
        "avancés → transactions », calibré sur les séries réelles (logique BPCE). Deux "
        "étages : (1) le taux de crédit est modélisé à partir de l'OAT 10 ans et de "
        "l'Euribor 3 mois ; (2) les ventes de logements anciens (cumul 12 mois) sont "
        "expliquées par le taux de crédit, les intentions d'achat et le chômage, chacun "
        "décalé. Un backtest hors échantillon mesure la valeur prédictive.",
        "The Time-Lag / Composite tabs formalised into a quantified 'leading indicators → "
        "transactions' model, calibrated on the real series (BPCE logic). Two stages: (1) the "
        "credit rate is modelled from the 10-year OAT and 3-month Euribor; (2) existing-home "
        "sales (12-month sum) are explained by the credit rate, purchase intentions and "
        "unemployment, each lagged. An out-of-sample backtest measures predictive value."))

    _tx12 = q.transactions_run_rate(con)
    _need = {"OAT_10ans", "Euribor_3M", "Credit_Logement_Taux_Interet",
             "Intentions_Achat_Logement", "Taux_Chomage_BIT"}
    if _tx12.dropna().empty or not _need.issubset(set(df_macro_full.columns)):
        st.warning(_L("Séries macro incomplètes — impossible de calibrer le modèle.",
                      "Incomplete macro series — cannot calibrate the model."))
    else:
        _rm, _lags, _tm = _forecast_bundle(df_macro_full, _tx12)
        _bt = _tm["backtest"]
        _b = _tm["beta"]

        # ---- 1. Credit-rate model ------------------------------------------------
        st.markdown("#### " + _L("1. Modèle de taux de crédit (OAT 10 ans + Euribor 3 mois)",
                                 "1. Credit-rate model (10-year OAT + 3-month Euribor)"))
        a1, a2 = st.columns([2, 1])
        with a1:
            fig_rm = go.Figure()
            fig_rm.add_trace(go.Scatter(x=_rm["frame"]["Date"], y=_rm["frame"]["obs"],
                                        name=_L("Taux observé", "Observed rate"), line=dict(color=COLOR_TEXT, width=2)))
            fig_rm.add_trace(go.Scatter(x=_rm["frame"]["Date"], y=_rm["frame"]["fit"],
                                        name=_L("Taux modélisé", "Modelled rate"),
                                        line=dict(color=COLOR_BRICK, width=2, dash="dot")))
            apply_macro_chart_layout(fig_rm, "%")
            st.plotly_chart(fig_rm, use_container_width=True)
        with a2:
            st.metric("R²", f"{_rm['r2']:.2f}".replace(".", ",") if lang_code == "FR" else f"{_rm['r2']:.2f}")
            _rb = _rm["beta"]
            _eq = f"{_rb[0]:.2f} + {_rb[1]:.2f}·OAT + {_rb[2]:.2f}·Euribor"
            if lang_code == "FR":
                _eq = _eq.replace(".", ",")
            st.markdown(f"**{_L('Taux', 'Rate')} ≈ {_eq}**")
            st.caption(_L(
                "+1 pt d'OAT ⇒ ~+%.2f pt de taux crédit. L'écart 2023-25 (taux sous l'OAT) reflète des banques qui retiennent leurs barèmes (BPCE)." % _rb[1],
                "+1pp OAT ⇒ ~+%.2fpp credit rate. The 2023-25 gap (rate below OAT) reflects banks holding their offers (BPCE)." % _rb[1]))
            st.caption(_L("Sources : Banque de France/BCE (taux, OAT, Euribor).",
                          "Sources: Banque de France/ECB (rate, OAT, Euribor)."))

        # ---- 2. Transactions nowcast + out-of-sample backtest --------------------
        st.markdown("#### " + _L("2. Nowcast des transactions & backtest hors échantillon",
                                 "2. Transactions nowcast & out-of-sample backtest"))
        m1, m2, m3 = st.columns(3)
        m1.metric(_L("R² (in-sample)", "R² (in-sample)"),
                  f"{_tm['r2']:.2f}".replace(".", ",") if lang_code == "FR" else f"{_tm['r2']:.2f}")
        if "mape" in _bt:
            m2.metric(_L("Erreur hors échantillon (MAPE, 2022→)", "Out-of-sample error (MAPE, 2022→)"),
                      (f"{_bt['mape']:.1f}%".replace(".", ",") if lang_code == "FR" else f"{_bt['mape']:.1f}%"))
        m3.metric(_L("Décalages (taux/intentions/chômage)", "Lags (rate/intentions/unemp.)"),
                  f"{_lags['kr']} / {_lags['ki']} / {_lags['kc']} " + _L("mois", "mo"))

        fig_tx = go.Figure()
        fig_tx.add_trace(go.Scatter(x=_tm["frame"]["Date"], y=_tm["frame"]["obs"],
                                    name=_L("Observé (IGEDD)", "Observed (IGEDD)"), line=dict(color=COLOR_TEXT, width=2.5)))
        if "frame" in _bt:
            fig_tx.add_trace(go.Scatter(x=_bt["frame"]["Date"], y=_bt["frame"]["pred"],
                                        name=_L("Prévision hors échantillon", "Out-of-sample forecast"),
                                        line=dict(color=COLOR_BRICK, width=2, dash="dot")))
            fig_tx.add_vline(x=pd.Timestamp(_bt["split"]), line_dash="dash", line_color="grey",
                             annotation_text=_L("entraînement | test", "train | test"))
        # Published BPCE L'Observatoire 2026 target (RDV Immobilier, 2 juin 2026): existing-home
        # transactions of 890 000 in 2026 (−6% after +13% in 2025). Shown as an external
        # validation reference for our own model's trajectory.
        fig_tx.add_hline(y=BPCE_TX_ANCIEN_2026, line_dash="dot", line_color=COLOR_SUNFLOWER,
                         annotation_text=_L("Cible BPCE 2026 : 890k", "BPCE 2026 target: 890k"),
                         annotation_position="bottom right")
        apply_macro_chart_layout(fig_tx, _L("Ventes sur 12 mois", "12-month sales"))
        st.plotly_chart(fig_tx, use_container_width=True)
        st.caption(_L(
            "Le modèle entraîné uniquement sur les données ≤ 2021 reproduit la contraction 2022-24 et le creux "
            "de sept-2024 puis la reprise 2025-26 — sans les avoir vues. C'est la preuve que ces indicateurs "
            "avancés « prévoient » réellement. Sources : IGEDD (ventes), INSEE + BdF/BCE (indicateurs).",
            "Trained only on ≤2021 data, the model reproduces the 2022-24 contraction, the Sept-2024 trough and "
            "the 2025-26 rebound — without having seen them. That is the proof the leading indicators genuinely "
            "'forecast'. Sources: IGEDD (sales), INSEE + BdF/ECB (indicators)."))

        # ---- 2 ter. Why THESE lags: move one, watch R² fall ----------------------
        # Folded in from the former "Atelier / Time-Lag" tab. That workshop hunted a lag by
        # maximising Pearson r on SMOOTHED LEVELS — a second, weaker answer to a question
        # this model already answers by grid-searching R² on the train window only
        # (fc.search_tx_lags). Two methods meant two numbers and no way to arbitrate, so the
        # exploration survives but is now scored with the MODEL's own criterion: refit at the
        # lag you pick and compare. Moving a lag away from the retained one must LOWER R² —
        # that is what makes the grid-search result auditable instead of asserted.
        with st.expander(_L("🔬 Vérifier les décalages retenus (en déplacer un, voir le R² bouger)",
                            "🔬 Inspect the retained lags (move one, watch R² move)")):
            _lag_specs = {
                _L("Taux de crédit", "Credit rate"):
                    ("kr", "Credit_Logement_Taux_Interet", 0, 12, _L("Taux (%)", "Rate (%)")),
                _L("Intentions d'achat", "Purchase intentions"):
                    ("ki", "Intentions_Achat_Logement", 0, 18, _L("Solde d'opinion", "Opinion balance")),
                _L("Taux de chômage", "Unemployment rate"):
                    ("kc", "Taux_Chomage_BIT", 0, 12, _L("Chômage (%)", "Unemployment (%)")),
            }
            _pc1, _pc2 = st.columns([1, 2])
            with _pc1:
                _pick = st.selectbox(_L("Prédicteur à inspecter", "Predictor to inspect"),
                                     list(_lag_specs.keys()), key="fc_lag_probe")
                _pk, _pcol, _plo, _phi, _payl = _lag_specs[_pick]
                _kman = st.slider(_L("Décalage appliqué (mois)", "Applied lag (months)"),
                                  _plo, _phi, int(_lags[_pk]), 1, key="fc_lag_probe_val",
                                  help=_L("Le curseur part sur le décalage retenu par la recherche "
                                          "en grille. Déplacez-le pour réestimer le modèle.",
                                          "The slider starts on the lag picked by the grid search. "
                                          "Move it to refit the model."))
                _trial = dict(_lags); _trial[_pk] = int(_kman)
                _tm_try = fc.fit_tx_model(df_macro_full, _tx12, split=_FORECAST_SPLIT, **_trial)
                _d_r2 = _tm_try["r2"] - _tm["r2"]
                st.metric(_L("R² au décalage choisi", "R² at the chosen lag"),
                          f"{_tm_try['r2']:.3f}".replace(".", ",") if lang_code == "FR"
                          else f"{_tm_try['r2']:.3f}",
                          (f"{_d_r2:+.3f}".replace(".", ",") if lang_code == "FR"
                           else f"{_d_r2:+.3f}") + _L(" vs retenu", " vs retained"))
                if int(_kman) == int(_lags[_pk]):
                    st.caption(_L(f"Décalage retenu par le modèle : {_lags[_pk]} mois.",
                                  f"Lag retained by the model: {_lags[_pk]} months."))
                elif _d_r2 > 0:
                    st.warning(_L(
                        f"Ce décalage fait MIEUX que celui retenu ({_lags[_pk]} mois) sur "
                        f"l'échantillon complet — normal : la grille cherche sur la fenêtre "
                        f"d'entraînement seule (≤ {_FORECAST_SPLIT[:4]}) pour ne pas contaminer "
                        f"le backtest. Un gain ici n'est donc pas une erreur du modèle.",
                        f"This lag beats the retained one ({_lags[_pk]} months) on the full sample — "
                        f"expected: the grid searches the TRAIN window only (≤ {_FORECAST_SPLIT[:4]}) "
                        f"so as not to contaminate the backtest. A gain here is not a model error."))
                else:
                    st.caption(_L(
                        f"Dégradation de {abs(_d_r2):.3f} de R² par rapport au décalage retenu "
                        f"({_lags[_pk]} mois) : la grille avait raison.".replace(".", ",", 1),
                        f"R² drops by {abs(_d_r2):.3f} versus the retained lag ({_lags[_pk]} months): "
                        f"the grid search was right."))
            with _pc2:
                _ps = df_macro_full[["Date", _pcol]].dropna().copy()
                _ps["Date"] = pd.to_datetime(_ps["Date"])
                _ps_sh = sim.shift_indicator(_ps, "Date", _pcol, int(_kman))
                _shcol = f"{_pcol}_shifted_{int(_kman)}"
                fig_probe = make_subplots(specs=[[{"secondary_y": True}]])
                fig_probe.add_trace(go.Scatter(
                    x=_tm["frame"]["Date"], y=_tm["frame"]["obs"],
                    name=_L("Transactions (cumul 12 m)", "Transactions (12-month sum)"),
                    line=dict(color=COLOR_TEXT, width=2.5)), secondary_y=False)
                fig_probe.add_trace(go.Scatter(
                    x=_ps_sh["Date"], y=_ps_sh[_shcol],
                    name=f"{_pick} " + _L(f"décalé +{int(_kman)} m", f"lagged +{int(_kman)}mo"),
                    line=dict(color=COLOR_BRICK, width=2, dash="dot")), secondary_y=True)
                apply_macro_chart_layout(fig_probe, _L("Ventes sur 12 mois", "12-month sales"))
                fig_probe.update_yaxes(title_text=_payl, secondary_y=True)
                st.plotly_chart(fig_probe, use_container_width=True)
            st.caption(_L(
                "Lecture : le prédicteur est décalé vers l'avant du nombre de mois choisi, de sorte "
                "qu'il se superpose aux transactions qu'il est censé annoncer. Le R² affiché est celui "
                "du modèle complet réestimé avec ce seul décalage modifié — les deux autres restent à "
                "leur valeur retenue. Sources : IGEDD (ventes) ; INSEE, Banque de France/BCE.",
                "Reading: the predictor is shifted forward by the chosen number of months so it overlays "
                "the transactions it is meant to lead. The R² shown is the full model refitted with this "
                "single lag changed — the other two stay at their retained values. Sources: IGEDD (sales); "
                "INSEE, Banque de France/ECB."))

        # ---- 2bis. Forward projection to horizon --------------------------------
        # Because the predictors enter with estimated lags, their ALREADY-OBSERVED values
        # pin down transactions for the coming months with no assumption on where macro
        # goes next. Sigma = out-of-sample backtest RMSE when available (else in-sample).
        _sigma = float(_bt["rmse"]) if "rmse" in _bt else float(_tm["rmse"])
        _last_tx12_pre = float(_tx12.dropna().iloc[-1])
        _fpath = fc.forecast_path(df_macro_full, _tx12, _lags, _b, _sigma, horizon=18)
        st.markdown("#### " + _L("2 bis. Projection à horizon (décalages déjà observés)",
                                 "2b. Projection to horizon (already-observed lags)"))
        if _fpath is None or _fpath.empty:
            st.info(_L(
                "Les décalages estimés ne permettent pas de projection au-delà du dernier point "
                "(un prédicteur a un décalage nul ou proche de zéro).",
                "The estimated lags allow no projection beyond the last point (a predictor has a "
                "zero / near-zero lag)."))
        else:
            _obs_line = _tm["frame"]
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Scatter(x=_obs_line["Date"], y=_obs_line["obs"],
                                        name=_L("Observé (IGEDD)", "Observed (IGEDD)"),
                                        line=dict(color=COLOR_TEXT, width=2.5)))
            # Uncertainty band (±1.28σ ≈ 80%).
            fig_fc.add_trace(go.Scatter(x=list(_fpath["Date"]) + list(_fpath["Date"][::-1]),
                                        y=list(_fpath["hi"]) + list(_fpath["lo"][::-1]),
                                        fill="toself", fillcolor="rgba(230,74,25,0.12)",
                                        line=dict(width=0), hoverinfo="skip",
                                        name=_L("Intervalle ~80 %", "~80% band")))
            fig_fc.add_trace(go.Scatter(x=_fpath["Date"], y=_fpath["pred"],
                                        name=_L("Projection", "Projection"),
                                        line=dict(color=COLOR_BRICK, width=2.5, dash="dot")))
            # Mark the boundary between the assumption-free part (all predictors observed)
            # and the carry-forward extension (predictors held flat at their last value).
            _assured = _fpath[_fpath["assured"]]
            if not _assured.empty and not _fpath["assured"].all():
                _bound = _assured["Date"].iloc[-1]
                fig_fc.add_vline(x=pd.Timestamp(_bound), line_dash="dash", line_color=COLOR_SUBTLE,
                                 annotation_text=_L("sans hypothèse | indicateurs constants",
                                                    "assumption-free | held flat"),
                                 annotation_position="top left")
            fig_fc.add_hline(y=BPCE_TX_ANCIEN_2026, line_dash="dot", line_color=COLOR_SUNFLOWER,
                             annotation_text=_L("Cible BPCE 2026 : 890k", "BPCE 2026 target: 890k"),
                             annotation_position="bottom right")
            apply_macro_chart_layout(fig_fc, _L("Ventes sur 12 mois", "12-month sales"))
            st.plotly_chart(fig_fc, use_container_width=True)

            _h_end = _fpath["Date"].iloc[-1]
            _v_end = _fpath["pred"].iloc[-1]
            _n_assured = int(_fpath["assured"].sum())
            fh1, fh2, fh3 = st.columns(3)
            fh1.metric(_L("Horizon de projection", "Projection horizon"),
                       f"{len(_fpath)} " + _L("mois", "mo"),
                       _L(f"dont {_n_assured} sans hypothèse", f"of which {_n_assured} assumption-free"),
                       delta_color="off")
            fh2.metric(_L("Fin d'horizon", "Horizon end"), f"{_h_end:%Y-%m}")
            fh3.metric(_L("Ventes 12 m projetées (fin)", "Projected 12m sales (end)"),
                       f"{_v_end:,.0f}".replace(",", " "),
                       f"{(_v_end/_last_tx12_pre-1)*100:+.1f}%".replace(".", ",") if lang_code == "FR"
                       else f"{(_v_end/_last_tx12_pre-1)*100:+.1f}%")
            st.caption(_L(
                "Jusqu'au repère, la projection n'utilise que des valeurs d'indicateurs déjà publiées "
                "(décalées de leurs délais estimés) — sans hypothèse. Au-delà, chaque indicateur manquant "
                "est maintenu à sa dernière valeur connue (report). Bande = ±1,28·RMSE (hors échantillon "
                "si disponible). Sources : IGEDD (ventes) ; INSEE, Banque de France/BCE (indicateurs).",
                "Up to the marker, the projection uses only already-published indicator values (shifted "
                "by their estimated lags) — assumption-free. Beyond it, each missing indicator is held at "
                "its last known value (carry-forward). Band = ±1.28·RMSE (out-of-sample when available). "
                "Sources: IGEDD (sales); INSEE, Banque de France/ECB (indicators)."))

        # ---- BPCE 2026 published targets (external validation benchmark) ----------
        st.markdown("**" + _L("📌 Repère : prévisions publiées BPCE L'Observatoire 2026",
                              "📌 Benchmark: BPCE L'Observatoire published 2026 forecasts") + "**")
        _last_tx12 = float(_tx12.dropna().iloc[-1])
        bp = st.columns(4)
        bp[0].metric(_L("Transactions ancien 2026", "Existing-home transactions 2026"),
                     f"{BPCE_TX_ANCIEN_2026:,.0f}".replace(",", " "),
                     _L("−6 % vs 2025", "−6% vs 2025"), delta_color="off")
        bp[1].metric(_L("Total neuf + ancien", "Total new + existing"),
                     f"{BPCE_TX_TOTAL_2026:,.0f}".replace(",", " "),
                     _L("−5 % vs 2025", "−5% vs 2025"), delta_color="off")
        bp[2].metric(_L("Taux de crédit T4 2026", "Credit rate Q4 2026"),
                     (f"{BPCE_RATE_Q4_2026:.2f} %".replace(".", ",") if lang_code == "FR" else f"{BPCE_RATE_Q4_2026:.2f}%"),
                     _L("+34 pdb sur un an", "+34bp YoY"), delta_color="off")
        bp[3].metric(_L("Prix ancien T4 2026", "Existing-home price Q4 2026"),
                     (f"{BPCE_PRICE_YOY_Q4_2026:+.1f} %".replace(".", ",") if lang_code == "FR" else f"{BPCE_PRICE_YOY_Q4_2026:+.1f}%"),
                     _L("glissement annuel", "year-on-year"), delta_color="off")
        _gap = (_last_tx12 - BPCE_TX_ANCIEN_2026) / BPCE_TX_ANCIEN_2026 * 100.0
        st.caption(_L(
            f"Dernier point réel du modèle (ventes sur 12 mois) : {_last_tx12:,.0f} — soit "
            f"{_gap:+.1f} % au-dessus de la cible annuelle BPCE 890 000 ; l'écart mesure "
            f"l'infléchissement attendu par BPCE d'ici fin 2026. Source : RDV Immobilier "
            f"BPCE L'Observatoire, 2 juin 2026.",
            f"Model's latest real point (12-month sales): {_last_tx12:,.0f} — i.e. "
            f"{_gap:+.1f}% above BPCE's 890,000 annual target; the gap measures the slowdown "
            f"BPCE expects by end-2026. Source: RDV Immobilier BPCE L'Observatoire, 2 June 2026.")
            .replace(",", " "))

        # ---- 3. Scenario panel ---------------------------------------------------
        st.markdown("#### " + _L("3. Panneau de scénarios : macro → marché → chiffre d'affaires",
                                 "3. Scenario panel: macro → market → revenue"))
        _mi = df_macro_full.set_index("Date").sort_index()
        _oat0 = float(_mi["OAT_10ans"].dropna().iloc[-1])
        _eur0 = float(_mi["Euribor_3M"].dropna().iloc[-1])
        _rate0 = float(_mi["Credit_Logement_Taux_Interet"].dropna().iloc[-1])
        _int0 = float(_mi["Intentions_Achat_Logement"].dropna().iloc[-1])
        _chom0 = float(_mi["Taux_Chomage_BIT"].dropna().iloc[-1])
        _tx0 = float(_tx12.dropna().iloc[-1])
        # Intentions are an unintuitive raw response balance; expose the lever in standard
        # deviations (like the chart's centrées-réduites view) and convert back to raw.
        _int_ser = _mi["Intentions_Achat_Logement"].dropna()
        _int_mu, _int_sd = float(_int_ser.mean()), float(_int_ser.std())
        _int0_z = (_int0 - _int_mu) / _int_sd if _int_sd > 0 else 0.0

        sc1, sc2 = st.columns([1, 2])
        with sc1:
            st.caption(_L("Hypothèses (défaut = dernières valeurs connues) :", "Assumptions (default = latest known):"))
            _oat = st.slider(_L("OAT 10 ans (%)", "10-year OAT (%)"), 0.0, 5.5, round(_oat0, 2), 0.1)
            _eur = st.slider(_L("Euribor 3 mois (%)", "3-month Euribor (%)"), -0.5, 4.5, round(_eur0, 2), 0.1)
            _chom = st.slider(_L("Taux de chômage (%)", "Unemployment rate (%)"), 6.5, 11.0, round(_chom0, 1), 0.1)
            _int_z = st.slider(_L("Intentions d'achat (écarts-types)", "Purchase intentions (std dev)"),
                               -2.5, 2.5, round(_int0_z, 1), 0.1,
                               help=_L("0 = moyenne de long terme ; +1 = un écart-type au-dessus. "
                                       "Troisième prédicteur du modèle, au même titre que le taux et le chômage.",
                                       "0 = long-term mean; +1 = one std dev above. The model's third "
                                       "predictor, alongside the rate and unemployment."))
            _int = _int_mu + _int_z * _int_sd
        _sc = fc.scenario(_rm["beta"], _b,
                          {"oat": _oat0, "euribor": _eur0, "intent": _int0, "chom": _chom0,
                           "rate_now": _rate0, "tx_now": _tx0},
                          {"oat": _oat, "euribor": _eur, "intent": _int, "chom": _chom})
        with sc2:
            r1c = st.columns(3)
            r1c[0].metric(_L("Taux de crédit implicite", "Implied credit rate"),
                          (f"{_sc['rate']:.2f}%".replace(".", ",") if lang_code == "FR" else f"{_sc['rate']:.2f}%"),
                          (f"{_sc['d_rate']:+.2f} pt".replace(".", ",") if lang_code == "FR" else f"{_sc['d_rate']:+.2f}pp"))
            r1c[1].metric(_L("Ventes projetées (12 mois)", "Projected sales (12m)"),
                          f"{_sc['tx']:,.0f}".replace(",", " "),
                          f"{_sc['d_tx']:+,.0f}".replace(",", " "))
            r1c[2].metric(_L("Impact relatif", "Relative impact"),
                          (f"{_sc['d_tx']/_tx0*100:+.1f}%".replace(".", ",") if lang_code == "FR" else f"{_sc['d_tx']/_tx0*100:+.1f}%"))
            fig_sc = go.Figure()
            fig_sc.add_trace(go.Bar(x=[_L("Actuel", "Current"), _L("Scénario", "Scenario")],
                                    y=[_tx0, _sc["tx"]], marker_color=[COLOR_SUBTLE, COLOR_BRICK],
                                    text=[f"{_tx0:,.0f}".replace(",", " "), f"{_sc['tx']:,.0f}".replace(",", " ")],
                                    textposition="outside"))
            fig_sc.update_layout(height=240, template="plotly_white", margin=dict(l=40, r=20, t=10, b=30),
                                 yaxis_title=_L("Ventes 12 mois", "12m sales"), showlegend=False)
            st.plotly_chart(fig_sc, use_container_width=True)
        st.caption(_L(
            "Lecture : effet à terme (après les décalages estimés) si ces conditions persistent, appliqué au niveau "
            "actuel réel (approche en écart, robuste au biais de niveau du modèle de taux).",
            "Reading: steady-state effect (after the estimated lags) if these conditions persist, applied to the actual "
            "current level (delta approach, robust to the rate model's level bias)."))

        # propagation to benchmarked company revenue
        if df_revenue_full is not None and not df_revenue_full.empty:
            st.markdown("**" + _L("→ Propagation au chiffre d'affaires benchmark",
                                  "→ Propagation to benchmarked revenue") + "**")
            _co = st.selectbox(_L("Entreprise", "Company"),
                               sorted(df_revenue_full["Company"].unique().tolist()))
            _caf = fc.best_tx_to_ca(df_revenue_full, _tx12, _co)
            if _caf is None:
                st.info(_L("Trop peu de points pour relier les transactions au CA de cette entreprise.",
                           "Too few points to link transactions to this company's revenue."))
            else:
                _ca_now = float(df_revenue_full[df_revenue_full["Company"] == _co]
                                .sort_values("Date")["CA_MEUR"].iloc[-1])
                _d_ca = _caf["beta"][1] * _sc["d_tx"]
                cc = st.columns(3)
                cc[0].metric(_L("CA trimestriel récent", "Recent quarterly revenue"), f"{_ca_now:,.0f} M€".replace(",", " "))
                cc[1].metric(_L("CA projeté (scénario)", "Projected revenue (scenario)"),
                             f"{_ca_now + _d_ca:,.0f} M€".replace(",", " "),
                             f"{_d_ca:+,.0f} M€".replace(",", " "))
                _rtxt = f"{_caf['r2']:.2f}"
                _rtxt = (_rtxt.replace(".", ",") + f" · {_caf['lag_q']}T") if lang_code == "FR" else (_rtxt + f" · {_caf['lag_q']}q")
                cc[2].metric(_L("Lien transactions→CA (R², décalage)", "Transactions→revenue (R², lag)"), _rtxt)
                st.caption(_L(
                    f"Élasticité estimée sur {_caf['n']} trimestres ; R²={_caf['r2']:.2f} (indicatif — séries "
                    f"d'entreprise courtes). Hexaom (neuf) et Kingfisher France (rénovation) réagissent aux "
                    f"transactions avec un décalage.",
                    f"Elasticity estimated on {_caf['n']} quarters; R²={_caf['r2']:.2f} (indicative — short company "
                    f"series). Hexaom (new-build) and Kingfisher France (renovation) respond to transactions with a lag."))

        # propagation to the user-imported MONTHLY company sales (own series). Multi-series:
        # pick the product family to propagate the transactions shock onto.
        if df_company_sales_full is not None and not df_company_sales_full.empty:
            _co_s = str(df_company_sales_full["Company"].iloc[0])

            # Recap: each product family and ITS OWN best transactions lag / R² — so the
            # planner sees at a glance which family leads/lags the market and by how much.
            _series_all = company_series_options(df_company_sales_full)
            if len(_series_all) > 1:
                _recap = []
                for _srn in _series_all:
                    _agg_srn = q.monthly(con, "company_sales", ["Sales"], windows=(),
                                         types=[_srn], category_col="Serie")
                    _fit_srn = fc.best_tx_to_monthly(_agg_srn, _tx12, "Sales")
                    _recap.append({
                        _L("Famille", "Family"): _srn,
                        _L("Décalage optimal", "Best lag"): (f"{_fit_srn['lag_m']} " + _L("mois", "mo"))
                            if _fit_srn else "—",
                        "R²": (round(_fit_srn["r2"], 2) if _fit_srn else None),
                        _L("n mois", "n months"): (_fit_srn["n"] if _fit_srn else 0),
                    })
                st.markdown("**" + _L("Décalage transactions→ventes par famille",
                                      "Transactions→sales lag per family") + "**")
                st.dataframe(pd.DataFrame(_recap), use_container_width=True, hide_index=True)

            _serie_f, _df_serie_f = pick_company_series(df_company_sales_full, key="fc_serie")
            st.markdown("**" + _L(f"→ Propagation à vos ventes importées ({_co_s} — {_serie_f})",
                                  f"→ Propagation to your imported sales ({_co_s} — {_serie_f})") + "**")
            _sf = fc.best_tx_to_monthly(_df_serie_f, _tx12, "Sales")
            if _sf is None:
                st.info(_L("Trop peu de points pour relier les transactions à vos ventes importées.",
                           "Too few points to link transactions to your imported sales."))
            else:
                _sales_now = float(_df_serie_f.sort_values("Date")["Sales"].iloc[-1])
                _d_sales = _sf["beta"][1] * _sc["d_tx"]
                sc_cols = st.columns(3)
                sc_cols[0].metric(_L("Ventes mensuelles récentes", "Recent monthly sales"),
                                  f"{_sales_now:,.0f}".replace(",", " "))
                sc_cols[1].metric(_L("Ventes projetées (scénario)", "Projected sales (scenario)"),
                                  f"{_sales_now + _d_sales:,.0f}".replace(",", " "),
                                  f"{_d_sales:+,.0f}".replace(",", " "))
                _srtxt = (f"{_sf['r2']:.2f}".replace(".", ",") + f" · {_sf['lag_m']} mois") \
                    if lang_code == "FR" else (f"{_sf['r2']:.2f} · {_sf['lag_m']}mo")
                sc_cols[2].metric(_L("Lien transactions→ventes (R², décalage)",
                                     "Transactions→sales (R², lag)"), _srtxt)
                st.caption(_L(
                    f"Élasticité estimée sur {_sf['n']} mois ; R²={_sf['r2']:.2f}. Vos ventes réagissent "
                    f"aux transactions (IGEDD, cumul 12 mois) avec ~{_sf['lag_m']} mois de décalage. "
                    f"Propagation du même choc de transactions que ci-dessus.",
                    f"Elasticity over {_sf['n']} months; R²={_sf['r2']:.2f}. Your sales respond to "
                    f"transactions (IGEDD, 12-month sum) with a ~{_sf['lag_m']}-month lag. Same "
                    f"transactions shock propagated as above."))

                # Monthly sales FORECAST: drive the imported series with the transactions
                # projection path (_fpath) through the estimated elasticity — the actual
                # demand-planning deliverable.
                _spath = fc.propagate_to_series(
                    _sf, _tx12, _fpath if (_fpath is not None) else None,
                    _df_serie_f, "Sales", sigma_tx=_sigma)
                if _spath is not None and not _spath.empty:
                    _sobs = _df_serie_f.sort_values("Date")
                    fig_sfc = go.Figure()
                    fig_sfc.add_trace(go.Scatter(x=_sobs["Date"], y=_sobs["Sales"],
                                                 name=_L("Ventes observées", "Observed sales"),
                                                 line=dict(color=COLOR_TEXT, width=2.5)))
                    fig_sfc.add_trace(go.Scatter(
                        x=list(_spath["Date"]) + list(_spath["Date"][::-1]),
                        y=list(_spath["hi"]) + list(_spath["lo"][::-1]),
                        fill="toself", fillcolor="rgba(230,74,25,0.12)", line=dict(width=0),
                        hoverinfo="skip", name=_L("Intervalle ~80 %", "~80% band")))
                    fig_sfc.add_trace(go.Scatter(x=_spath["Date"], y=_spath["pred"],
                                                 name=_L("Prévision de ventes", "Sales forecast"),
                                                 line=dict(color=COLOR_BRICK, width=2.5, dash="dot")))
                    apply_macro_chart_layout(fig_sfc, _L("Ventes mensuelles", "Monthly sales"))
                    st.plotly_chart(fig_sfc, use_container_width=True)
                    _sf_end, _sf_endval = _spath["Date"].iloc[-1], _spath["pred"].iloc[-1]
                    st.caption(_L(
                        f"Prévision de vos ventes « {_serie_f} » jusqu'à {_sf_end:%Y-%m} "
                        f"({len(_spath)} mois), obtenue en propageant la trajectoire de transactions "
                        f"projetée à travers l'élasticité estimée (décalage {_sf['lag_m']} mois).",
                        f"Forecast of your '{_serie_f}' sales through {_sf_end:%Y-%m} ({len(_spath)} "
                        f"months), by propagating the projected transactions path through the estimated "
                        f"elasticity ({_sf['lag_m']}-month lag)."))

                # Renovation as a THIRD driver: when a renovation series is available, fit a
                # two-factor model (sales ~ transactions + renovation) and compare its R² to
                # the transactions-only elasticity — renovation captures the stock-driven
                # demand that moves don't. Inactive (and silent) until the reno CSV exists.
                _reno_col = next((c for c in ("Reno_Activite_Batiment", "Reno_Activite_Prevue")
                                  if c in df_macro_full.columns
                                  and df_macro_full[c].notna().any()), None)
                if _reno_col is not None:
                    _reno_ser = df_macro_full.set_index("Date")[_reno_col]
                    _tf = fc.fit_sales_two_factor(_df_serie_f, _tx12, _reno_ser, "Sales")
                    if _tf is not None:
                        st.markdown("**" + _L("→ Rénovation comme 3ᵉ driver",
                                              "→ Renovation as a 3rd driver") + "**")
                        tf_cols = st.columns(3)
                        tf_cols[0].metric(_L("R² transactions seules", "R² transactions only"),
                                          f"{_sf['r2']:.2f}".replace(".", ",") if lang_code == "FR" else f"{_sf['r2']:.2f}")
                        tf_cols[1].metric(_L("R² transactions + rénovation", "R² transactions + renovation"),
                                          f"{_tf['r2']:.2f}".replace(".", ",") if lang_code == "FR" else f"{_tf['r2']:.2f}")
                        tf_cols[2].metric(_L("Décalages (tx / réno)", "Lags (tx / reno)"),
                                          f"{_tf['tx_lag']} / {_tf['reno_lag']} " + _L("mois", "mo"))
                        st.caption(_L(
                            "Le second facteur (rénovation) capte la demande second-œuvre tirée par le "
                            "STOCK de logements, indépendante des déménagements. Un gain de R² valide la "
                            "rénovation comme driver — et ouvre la voie au remplacement de la dernière "
                            "série synthétique.",
                            "The second factor (renovation) captures stock-driven second-œuvre demand, "
                            "independent of moves. An R² gain validates renovation as a driver — and paves "
                            "the way to replacing the last synthetic series."))


# ==============================================================================
# TAB 4 (suite): PERMIS -> VENTES SOCIETE — le seul driver amont que le modele
# n'utilise pas. Ce bloc est le rescape de l'ex-onglet « Atelier exploratoire » :
# tout le reste de cet atelier (recherche de decalage par r de Pearson, branche
# macro, benchmark sur ventes synthetiques, indicateur composite pondere a la main)
# a ete retire comme redondant ou non verifiable — voir le commentaire au-dessus de
# `st.tabs`. Ce second bloc `with tab_forecast:` s'affiche a la suite des scenarios.
# ==============================================================================
with tab_forecast:
    st.markdown("---")
    st.markdown("#### " + _L("4. Permis de construire → vos ventes (driver amont hors modèle)",
                             "4. Building permits → your sales (upstream driver outside the model)"))
    st.write(_L(
        "L'étage 2 du modèle explique les transactions par le taux, les intentions d'achat et "
        "le chômage — SIT@DEL n'y figure pas. Or, pour une activité de second-œuvre, un permis "
        "déposé aujourd'hui EST une commande dans quelques mois : un lien que le modèle ne peut "
        "pas voir. Il est mesuré ici avec le MÊME estimateur que l'élasticité transactions→ventes "
        "ci-dessus, donc les deux drivers sont directement comparables.",
        "Stage 2 of the model explains transactions with the rate, purchase intentions and "
        "unemployment — SIT@DEL is not in it. Yet for a second-œuvre business a permit filed today "
        "IS an order a few months out: a link the model cannot see. It is measured here with the "
        "SAME estimator as the transactions→sales elasticity above, so the two drivers are "
        "directly comparable."))

    if df_company_sales_full is None or df_company_sales_full.empty:
        st.info(_L(
            "Importez vos ventes société (onglet « ⚙️ Données & Sources ») pour mesurer le "
            "décalage entre les permis de construire et votre activité.",
            "Import your company sales (『⚙️ Data & Sources』 tab) to measure the lag between "
            "building permits and your own activity."))
    else:
        _pv1, _pv2 = st.columns([1, 2])
        with _pv1:
            _pm_type = st.selectbox(T[lang_code]["housing_type"],
                                    df_sitadel["Type"].unique().tolist(), key="permis_type")
            _pm_metric = st.selectbox(T[lang_code]["metric_sitadel"],
                                      ["Permis", "MisesEnChantier"], key="permis_metric")
            _serie_p, _agg_p = pick_company_series(df_company_sales_full, key="permis_serie")

            # Driver: 12-month rolling permits, so it sits on the same footing as the
            # 12-month transactions run-rate the other elasticity uses.
            _pm_df = q.monthly(con, "sitadel", [_pm_metric], windows=(12,), types=[_pm_type])
            _pm_col = f"{_pm_metric}_12M"
            _pm_ser = (_pm_df.dropna(subset=[_pm_col])
                       .assign(Date=lambda d: pd.to_datetime(d["Date"]))
                       .set_index("Date")[_pm_col].sort_index())

            _fit_p = fc.best_tx_to_monthly(_agg_p, _pm_ser, "Sales")
            _fit_t = fc.best_tx_to_monthly(_agg_p, _tx12, "Sales")

        if _fit_p is None:
            with _pv1:
                st.info(_L("Trop peu de mois communs entre les permis et vos ventes.",
                           "Too few overlapping months between permits and your sales."))
        else:
            with _pv1:
                st.metric(_L("Décalage permis → ventes", "Permits → sales lag"),
                          f"{_fit_p['lag_m']} " + _L("mois", "months"),
                          "R² = " + (f"{_fit_p['r2']:.2f}".replace(".", ",")
                                          if lang_code == "FR" else f"{_fit_p['r2']:.2f}"),
                          delta_color="off")
                if _fit_t is not None:
                    _better = (_L("les permis", "permits") if _fit_p["r2"] >= _fit_t["r2"]
                               else _L("les transactions", "transactions"))
                    st.caption(_L(
                        f"Comparé sur la même série : transactions R²={_fit_t['r2']:.2f} "
                        f"(décalage {_fit_t['lag_m']} mois) contre permis R²={_fit_p['r2']:.2f} "
                        f"(décalage {_fit_p['lag_m']} mois). Le meilleur driver amont de "
                        f"« {_serie_p} » est ici : {_better}.",
                        f"Same series, both drivers: transactions R²={_fit_t['r2']:.2f} "
                        f"({_fit_t['lag_m']}-month lag) versus permits R²={_fit_p['r2']:.2f} "
                        f"({_fit_p['lag_m']}-month lag). The better upstream driver of "
                        f"'{_serie_p}' here is: {_better}."))
                st.caption(_L(f"Élasticité estimée sur {_fit_p['n']} mois communs.",
                              f"Elasticity estimated over {_fit_p['n']} overlapping months."))

            with _pv2:
                _lag_p = int(_fit_p["lag_m"])
                _pm_plot = _pm_ser.rename("Val").reset_index()
                _pm_sh = sim.shift_indicator(_pm_plot, "Date", "Val", _lag_p)
                _shc = f"Val_shifted_{_lag_p}"
                _sales_obs = _agg_p.sort_values("Date")

                fig_pm = make_subplots(specs=[[{"secondary_y": True}]])
                fig_pm.add_trace(go.Scatter(
                    x=_pm_sh["Date"], y=_pm_sh[_shc],
                    name=f"{_pm_metric} — {_pm_type} "
                         + _L(f"(cumul 12 m, décalé +{_lag_p} m)",
                              f"(12-month sum, lagged +{_lag_p}mo)"),
                    line=dict(color=COLOR_BRICK, width=2.5)), secondary_y=False)
                fig_pm.add_trace(go.Scatter(
                    x=_sales_obs["Date"], y=_sales_obs["Sales"],
                    name=_L(f"Ventes — {_serie_p}", f"Sales — {_serie_p}"),
                    line=dict(color=COLOR_TEXT, width=2.5)), secondary_y=True)

                # The payoff of the shift: permits already FILED reach beyond the last
                # observed sale, so the shaded zone is activity already in the pipeline.
                _last_sale = _sales_obs["Date"].max()
                _last_shift = _pm_sh["Date"].max()
                if pd.notna(_last_sale) and pd.notna(_last_shift) and _last_shift > _last_sale:
                    fig_pm.add_vrect(x0=_last_sale, x1=_last_shift,
                                     fillcolor=COLOR_BRICK_ZONE, opacity=0.5, layer="below",
                                     line_width=0, annotation_text=T[lang_code]["zone_prev"],
                                     annotation_position="top left")
                apply_macro_chart_layout(fig_pm, _L("Permis (cumul 12 mois)", "Permits (12-month sum)"))
                fig_pm.update_yaxes(title_text=_L("Ventes mensuelles", "Monthly sales"),
                                    secondary_y=True)
                st.plotly_chart(fig_pm, use_container_width=True)
                st.caption(_L(
                    "Zone ombrée : les permis y sont DÉJÀ déposés, mais les ventes correspondantes "
                    "ne sont pas encore réalisées — c'est l'activité déjà engagée en amont. "
                    "Sources : SDES — SIT@DEL (permis) ; vos ventes importées.",
                    "Shaded zone: permits there are ALREADY filed but the matching sales have not "
                    "happened yet — activity already in the pipeline. Sources: SDES — SIT@DEL "
                    "(permits); your imported sales."))


# ==============================================================================
# TAB 5: DONNÉES & SOURCES — consultation des sources et import des ventes
# société. L'export SAP IBP qui partageait cet onglet a été retiré (besoin
# suspendu) ; le formateur `export.py` reste en place, non câblé, pour pouvoir
# le rebrancher sans le réécrire.
# ==============================================================================
with tab_donnees:
    st.caption(T[lang_code]["donnees_caption"])
    # Single-purpose tab. The source-data browser, the per-dataset CSV overwrite, the
    # "réinitialisation générale" and the IGEDD rebuild button all lived here and were
    # removed: acquisition is fully scripted (fetch_new_sources.py + the weekly GitHub
    # Actions workflow), so an in-app overwrite path was a second, unversioned way to
    # mutate the same files. The typed-warehouse validation panel went with them — see
    # the note in CLAUDE.md about the diagnostics this costs.
    st.header(_L("🏢 Ventes mensuelles de votre société",
                 "🏢 Your company's monthly sales"))
    st.write(_L(
        "Importez les ventes mensuelles de votre société (CSV) pour les utiliser comme cible "
        "dans « 📡 Prévision & Scénarios » : propagation du scénario à vos ventes, décalage "
        "transactions→ventes par famille, et comparaison au driver permis. Une seule société "
        "à la fois — chaque import remplace le précédent.",
        "Import your company's monthly sales (CSV) to use as a target in '📡 Forecast & "
        "Scenarios': scenario propagation to your sales, transactions→sales lag per family, and "
        "comparison against the permits driver. One company at a time — each import replaces "
        "the previous one."))
    st.caption(_L(
        "Les jeux de données sources (SIT@DEL, IGEDD, macro, ECLN…) ne se chargent plus "
        "depuis l'application : ils sont rafraîchis par `python fetch_new_sources.py`, que le "
        "workflow hebdomadaire GitHub Actions exécute déjà.",
        "The source datasets (SIT@DEL, IGEDD, macro, ECLN…) are no longer loaded from the app: "
        "they are refreshed by `python fetch_new_sources.py`, which the weekly GitHub Actions "
        "workflow already runs."))
    st.info(_L(
        "**Format attendu :** un CSV avec une colonne **`Date`** (mensuelle, ex. `2023-01-01` ou "
        "`2023-01`) et une colonne de ventes nommée **`Sales`** (ou `Ventes`). Colonnes `Company` "
        "et **`Serie`** (famille de produits — plusieurs familles dans un même fichier) facultatives.",
        "**Expected format:** a CSV with a **`Date`** column (monthly, e.g. `2023-01-01` or "
        "`2023-01`) and a sales column named **`Sales`** (or `Ventes`). Optional `Company` and "
        "**`Serie`** columns (product family — several families in one file)."))
    st.caption(_L(
        "💡 Alternative versionnée : déposez un fichier par famille nommé "
        "`data_manual_input/ventes-<famille>.csv` (comme les `ca-*.csv`). Ils sont ingérés "
        "automatiquement quand aucun import ad-hoc n'est présent — traçable via git.",
        "💡 Versioned alternative: drop one file per family named "
        "`data_manual_input/ventes-<family>.csv` (like the `ca-*.csv`). They are ingested "
        "automatically when no ad-hoc upload is present — git-traceable."))

    if df_company_sales_full is not None and not df_company_sales_full.empty:
        _cs_name = str(df_company_sales_full["Company"].iloc[0])
        _cs_min = df_company_sales_full["Date"].min().strftime("%Y-%m")
        _cs_max = df_company_sales_full["Date"].max().strftime("%Y-%m")
        st.success(_L(
            f"Série active : « {_cs_name} » — {len(df_company_sales_full)} mois ({_cs_min} → {_cs_max}). "
            f"Sélectionnable comme benchmark dans l'Atelier exploratoire (Time-Lag / Composite) "
            f"et dans « 📡 Prévision & Scénarios ».",
            f"Active series: '{_cs_name}' — {len(df_company_sales_full)} months ({_cs_min} → {_cs_max}). "
            f"Selectable as a benchmark in the Exploratory Workshop (Time-Lag / Composite) "
            f"and in '📡 Forecast & Scenarios'."))
        st.dataframe(df_company_sales_full.tail(12), use_container_width=True)

    _cs_col1, _cs_col2 = st.columns([2, 1])
    with _cs_col1:
        _cs_file = st.file_uploader(_L("Choisir un CSV de ventes mensuelles", "Choose a monthly-sales CSV"),
                                    type="csv", key="company_sales_upload")
        _cs_template = pd.DataFrame(
            {"Date": ["2023-01-01", "2023-02-01", "2023-03-01"], "Sales": [1200, 1350, 1280]}
        ).to_csv(index=False).encode("utf-8")
        st.download_button(_L("📥 Modèle CSV (Date, Sales)", "📥 CSV template (Date, Sales)"),
                           data=_cs_template, file_name="company_sales_template.csv",
                           mime="text/csv", key="dl_company_sales_template")
    with _cs_col2:
        _cs_company = st.text_input(_L("Nom de la société", "Company name"),
                                    value=_L("Ma société", "My company"), key="company_sales_name")
        if _cs_file is not None and st.button(_L("Importer les ventes", "Import sales"),
                                              key="btn_company_sales_import"):
            ok, msg = dm.import_company_sales(_cs_file, _cs_company)
            if ok:
                st.success(msg)
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)
        if df_company_sales_full is not None and not df_company_sales_full.empty:
            if st.button(_L("🗑️ Retirer les ventes importées", "🗑️ Remove imported sales"),
                         key="btn_company_sales_del"):
                if os.path.exists(dm.paths["company_sales"]):
                    os.remove(dm.paths["company_sales"])
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
