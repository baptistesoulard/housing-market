"""
PDF report generator — a concise "bilan" of the residential real-estate market for the
Demand Planning team. Renders the app's key figures, an auto-generated commentary, a few
brand-styled charts and the published BPCE 2026 benchmark into a self-contained PDF.

Charts are drawn with matplotlib (rendered to in-memory PNG); the document is laid out
with reportlab (Platypus). Both are pure-Python, pip-installable and headless-friendly, so
the app never needs a browser or a static-export engine. Called from the app's sidebar
"Rapport PDF" button — see build_pdf_report().
"""
import io
from datetime import date

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend (no display needed)
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image)

import analysis as ana

# --- Brand palette (mirrors app.py) ---
BRICK = "#E64A19"
TEXT = "#2D3748"
BLUE = "#64B5F6"
GREEN = "#388E3C"
TERRA = "#D0A37D"
SUBTLE = "#6c757d"

# Published BPCE L'Observatoire 2026 targets (RDV Immobilier, 2 June 2026) — external
# benchmark, kept in sync with app.py.
BPCE_TX_ANCIEN_2026 = 890_000
BPCE_TX_TOTAL_2026 = 1_026_000
BPCE_RATE_Q4_2026 = 3.43
BPCE_PRICE_YOY_Q4_2026 = -0.1

_FR_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
              "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _L(fr, en, lang):
    return fr if lang == "FR" else en


def _month_year(ts, lang):
    ts = pd.Timestamp(ts)
    months = _FR_MONTHS if lang == "FR" else _EN_MONTHS
    return f"{months[ts.month - 1]} {ts.year}"


def _num(v, lang):
    """Thousands-separated integer with a French thin space."""
    return f"{int(round(v)):,}".replace(",", " ")


def _pct(v, lang):
    if v is None:
        return "—"
    s = f"{v:+.1f}%"
    return s.replace(".", ",") if lang == "FR" else s


def _png(fig):
    """Render a matplotlib figure to a rewound PNG BytesIO and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _style_ax(ax):
    ax.grid(True, alpha=0.25, linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(labelsize=8)


# --- Charts -----------------------------------------------------------------------------

def _chart_construction(df_sitadel, lang):
    agg = ana.calculate_rolling_12m(ana.aggregate_sitadel(df_sitadel),
                                    ["Permis", "MisesEnChantier"]).dropna(subset=["Permis_12M"])
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    ax.plot(agg["Date"], agg["Permis_12M"] / 1000, color=BRICK, lw=2,
            label=_L("Permis de construire", "Building permits", lang))
    ax.plot(agg["Date"], agg["MisesEnChantier_12M"] / 1000, color=TEXT, lw=2, ls="--",
            label=_L("Mises en chantier", "Housing starts", lang))
    ax.set_ylabel(_L("Milliers", "Thousands", lang), fontsize=8)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    _style_ax(ax)
    return _png(fig)


def _chart_transactions(df_ventes_ancien, lang):
    agg = ana.calculate_rolling_12m(ana.aggregate_ventes_ancien(df_ventes_ancien),
                                    ["Transactions"]).dropna(subset=["Transactions_12M"])
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    ax.plot(agg["Date"], agg["Transactions_12M"] / 1000, color=GREEN, lw=2,
            label=_L("Ventes anciennes (IGEDD)", "Existing-home sales (IGEDD)", lang))
    ax.axhline(BPCE_TX_ANCIEN_2026 / 1000, color=TERRA, lw=1.2, ls=":",
               label=_L("Cible BPCE 2026 (890k)", "BPCE 2026 target (890k)", lang))
    ax.set_ylabel(_L("Milliers", "Thousands", lang), fontsize=8)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    _style_ax(ax)
    return _png(fig)


def _chart_indiv_collectif(df_sitadel, lang):
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    groups = [(_L("Maison individuelle pure", "Detached houses", lang), ana.SITADEL_INDIVIDUEL_PUR, BRICK),
              (_L("Collectif", "Collective", lang), ana.SITADEL_COLLECTIF, BLUE)]
    for lbl, types, clr in groups:
        g = ana.calculate_rolling_12m(ana.aggregate_sitadel(df_sitadel, types),
                                      ["MisesEnChantier"]).dropna(subset=["MisesEnChantier_12M"])
        ax.plot(g["Date"], g["MisesEnChantier_12M"] / 1000, color=clr, lw=2, label=lbl)
    ax.set_ylabel(_L("Milliers (mises en chantier)", "Thousands (starts)", lang), fontsize=8)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    _style_ax(ax)
    return _png(fig)


def _chart_rates(df_macro, lang):
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    series = [("Credit_Logement_Taux_Interet", BRICK, _L("Taux crédit habitat", "Housing loan rate", lang)),
              ("OAT_10ans", GREEN, _L("OAT 10 ans", "10-year OAT", lang)),
              ("Euribor_3M", BLUE, _L("Euribor 3 mois", "3-month Euribor", lang))]
    drawn = False
    for col, clr, lbl in series:
        if col in df_macro.columns and df_macro[col].notna().any():
            d = df_macro.dropna(subset=[col])
            ax.plot(d["Date"], d[col], color=clr, lw=1.8, label=lbl)
            drawn = True
    ax.set_ylabel("%", fontsize=8)
    if drawn:
        ax.legend(loc="upper left", fontsize=8, frameon=False)
    _style_ax(ax)
    return _png(fig)


def _img(png_buf, width_mm=170.0, fig_ratio=2.7 / 7.4):
    """reportlab Image sized to a target width (mm), height from the figure aspect ratio."""
    w = width_mm * mm
    return Image(png_buf, width=w, height=w * fig_ratio)


# --- Document ---------------------------------------------------------------------------

def build_pdf_report(df_sitadel, df_ventes_ancien, df_macro, lang="FR"):
    """Build the market 'bilan' PDF and return it as bytes. Inputs are the FULL-history
    national frames (df_*_full in the app). Everything is derived from the numbers so the
    report matches the dashboard."""
    # --- Headline figures (full national history, 12m rolling) ---
    roll_sit = ana.calculate_rolling_12m(ana.aggregate_sitadel(df_sitadel),
                                         ["Permis", "MisesEnChantier"])
    roll_ventes_ancien = ana.calculate_rolling_12m(ana.aggregate_ventes_ancien(df_ventes_ancien), ["Transactions"])
    kpi_p = ana.calculate_kpis(roll_sit, "Permis")
    kpi_m = ana.calculate_kpis(roll_sit, "MisesEnChantier")
    kpi_t = ana.calculate_kpis(roll_ventes_ancien, "Transactions")
    mom_p = ana.momentum_metrics(ana.aggregate_sitadel(df_sitadel), "Permis")
    mom_m = ana.momentum_metrics(ana.aggregate_sitadel(df_sitadel), "MisesEnChantier")
    mom_t = ana.momentum_metrics(ana.aggregate_ventes_ancien(df_ventes_ancien), "Transactions")
    mom_ip = ana.momentum_metrics(
        ana.aggregate_sitadel(df_sitadel, ana.SITADEL_INDIVIDUEL_PUR), "MisesEnChantier")
    commentary = ana.build_market_commentary(kpi_p, kpi_m, kpi_t, mom_p, mom_m, mom_t, mom_ip, lang)

    last_sit = ana.aggregate_sitadel(df_sitadel)["Date"].max()
    last_ventes_ancien = ana.aggregate_ventes_ancien(df_ventes_ancien)["Date"].max()
    last_tx12 = float(roll_ventes_ancien.dropna(subset=["Transactions_12M"])["Transactions_12M"].iloc[-1])
    gap = (last_tx12 - BPCE_TX_ANCIEN_2026) / BPCE_TX_ANCIEN_2026 * 100.0

    # --- Styles ---
    styles = getSampleStyleSheet()
    brick = colors.HexColor(BRICK)
    ink = colors.HexColor(TEXT)
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=ink, fontSize=22, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor(SUBTLE), fontSize=10, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=brick, fontSize=13, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], textColor=ink, fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=styles["Normal"], textColor=colors.HexColor(SUBTLE), fontSize=8, leading=11)

    story = []

    # --- Header ---
    story.append(Paragraph(_L("Bilan du marché immobilier résidentiel",
                              "Residential real-estate market review", lang), h1))
    story.append(Paragraph(_L("Market Intelligence — Département Demand Planning",
                              "Market Intelligence — Demand Planning Department", lang), sub))
    _gen = _L(f"Généré le {date.today().strftime('%d/%m/%Y')}",
              f"Generated {date.today().strftime('%Y-%m-%d')}", lang)
    _cov = _L(f"Données jusqu'à {_month_year(max(last_sit, last_ventes_ancien), lang)}",
              f"Data through {_month_year(max(last_sit, last_ventes_ancien), lang)}", lang)
    story.append(Paragraph(f"{_gen} · {_cov}", small))
    story.append(Spacer(1, 8))

    # --- KPI table ---
    story.append(Paragraph(_L("Chiffres clés", "Key figures", lang), h2))
    hdr = [_L("Indicateur", "Indicator", lang), _L("Cumul 12 mois", "12-month total", lang),
           _L("Sur 12 mois", "Over 12 months", lang), _L("3 mois vs n-1", "3 months vs prior year", lang)]
    rows = [
        [_L("Permis de construire", "Building permits", lang), _num(kpi_p["current_12m"], lang),
         _pct(kpi_p["yoy_12m_pct"], lang), _pct(mom_p.get("last3_yoy"), lang)],
        [_L("Mises en chantier", "Housing starts", lang), _num(kpi_m["current_12m"], lang),
         _pct(kpi_m["yoy_12m_pct"], lang), _pct(mom_m.get("last3_yoy"), lang)],
        [_L("Ventes anciennes (IGEDD)", "Existing-home sales (IGEDD)", lang), _num(kpi_t["current_12m"], lang),
         _pct(kpi_t["yoy_12m_pct"], lang), _pct(mom_t.get("last3_yoy"), lang)],
    ]
    tbl = Table([hdr] + rows, colWidths=[62 * mm, 36 * mm, 32 * mm, 40 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brick),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # --- Commentary ---
    story.append(Paragraph(_L("À retenir", "At a glance", lang), h2))
    story.append(Paragraph(commentary, body))

    # --- Charts ---
    story.append(Paragraph(_L("Construction neuve (cumul 12 mois, en milliers)",
                              "New construction (12-month total, thousands)", lang), h2))
    story.append(_img(_chart_construction(df_sitadel, lang)))
    story.append(Paragraph(_L("Ventes de logements anciens (cumul 12 mois, en milliers)",
                              "Existing-home sales (12-month total, thousands)", lang), h2))
    story.append(_img(_chart_transactions(df_ventes_ancien, lang)))
    story.append(Paragraph(_L("Individuel pur vs collectif (mises en chantier, cumul 12 mois)",
                              "Detached vs collective (starts, 12-month total)", lang), h2))
    story.append(_img(_chart_indiv_collectif(df_sitadel, lang)))
    story.append(Paragraph(_L("Taux d'intérêt et conditions de financement (%)",
                              "Interest rates and financing conditions (%)", lang), h2))
    story.append(_img(_chart_rates(df_macro, lang)))

    # --- BPCE benchmark ---
    story.append(Paragraph(_L("Repère : prévisions BPCE L'Observatoire 2026",
                              "Benchmark: BPCE L'Observatoire 2026 forecasts", lang), h2))
    bhdr = [_L("Transactions ancien", "Existing-home transactions", lang),
            _L("Total neuf + ancien", "Total new + existing", lang),
            _L("Taux crédit T4", "Credit rate Q4", lang),
            _L("Prix ancien T4", "Existing price Q4", lang)]
    brow = [f"{_num(BPCE_TX_ANCIEN_2026, lang)} (-6%)", f"{_num(BPCE_TX_TOTAL_2026, lang)} (-5%)",
            (f"{BPCE_RATE_Q4_2026:.2f} %".replace(".", ",") if lang == "FR" else f"{BPCE_RATE_Q4_2026:.2f}%"),
            _pct(BPCE_PRICE_YOY_Q4_2026, lang)]
    btbl = Table([bhdr, brow], colWidths=[42.5 * mm] * 4)
    btbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(btbl)
    story.append(Spacer(1, 4))
    story.append(Paragraph(_L(
        f"Dernier point réel du modèle : {_num(last_tx12, lang)} ventes sur 12 mois, soit "
        f"{_pct(gap, lang)} au-dessus de la cible annuelle BPCE de 890 000 — l'écart mesure "
        f"l'infléchissement attendu d'ici fin 2026. Sources : SIT@DEL (SDES), IGEDD, INSEE, "
        f"Banque de France / BCE, BPCE L'Observatoire.",
        f"Model's latest real point: {_num(last_tx12, lang)} 12-month sales, i.e. {_pct(gap, lang)} "
        f"above BPCE's 890,000 annual target — the gap measures the expected slowdown by end-2026. "
        f"Sources: SIT@DEL (SDES), IGEDD, INSEE, Banque de France / ECB, BPCE L'Observatoire.", lang), small))

    # --- Build ---
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=_L("Bilan marché immobilier", "Real-estate market review", lang))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
