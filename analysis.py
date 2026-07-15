import pandas as pd
import numpy as np

def filter_by_geography(df, level, regions=None, departments=None):
    """
    Filters a dataframe based on the selected geographic level (National, Régional, Départemental)
    and specific selection parameters.
    """
    if level == "National":
        return df.copy()
    elif level == "Régional" and regions:
        return df[df["Region"].isin(regions)].copy()
    elif level == "Départemental" and departments:
        return df[df["Department"].isin(departments)].copy()
    return df.copy()

def aggregate_sitadel(df_sitadel, types=None):
    """
    Aggregates SIT@DEL data by Date.
    If 'types' is provided, filters for those housing types.
    """
    df = df_sitadel.copy()
    if types:
        df = df[df["Type"].isin(types)]
        
    df_agg = df.groupby("Date")[["Permis", "MisesEnChantier"]].sum().reset_index()
    df_agg = df_agg.sort_values("Date")
    return df_agg

def aggregate_dvf(df_dvf, types=None):
    """
    Aggregates DVF data by Date.
    If 'types' is provided, filters for those property types.
    """
    df = df_dvf.copy()
    if types:
        df = df[df["Type"].isin(types)]
        
    df_agg = df.groupby("Date")[["Transactions"]].sum().reset_index()
    df_agg = df_agg.sort_values("Date")
    return df_agg

def aggregate_sales(df_sales, products=None):
    """
    Aggregates Sales data by Date.
    If 'products' is provided, filters for those products.
    """
    df = df_sales.copy()
    if products:
        df = df[df["Product"].isin(products)]
        
    df_agg = df.groupby("Date")[["Sales_Units"]].sum().reset_index()
    df_agg = df_agg.sort_values("Date")
    return df_agg

def calculate_rolling_12m(df, value_cols):
    """
    Calculates the 12-month rolling sum (cumul glissant sur 12 mois) for the given column names.
    Appends columns with suffix '_12m'.
    Assumes df is ordered chronologically by 'Date' (at monthly interval).
    """
    df_rolling = df.copy()
    for col in value_cols:
        # Since frequency is monthly, window=12 calculates the 12-month rolling sum
        # min_periods=12 ensures we don't display incomplete rolling sums at the start, or min_periods=1 to show what's available
        df_rolling[f"{col}_12M"] = df_rolling[col].rolling(window=12, min_periods=12).sum()
    return df_rolling

def calculate_rolling(df, value_cols, window):
    """
    Calculates the N-month rolling sum for the given columns, appending columns with
    suffix '_{window}M' (e.g. '_6M', '_12M'). Assumes monthly-ordered 'Date'.
    """
    df_rolling = df.copy()
    for col in value_cols:
        df_rolling[f"{col}_{window}M"] = df_rolling[col].rolling(window=window, min_periods=window).sum()
    return df_rolling

# --- SIT@DEL housing-type groupings (individual vs collective) ---
# A single individual house carries far more "second-œuvre" content (fermetures,
# menuiseries, sécurité, domotique) than a collective dwelling, so these groupings
# isolate the individual-housing signal that drives building-materials demand.
SITADEL_INDIVIDUEL_PUR = ["Maison Individuelle Pure"]
SITADEL_INDIVIDUEL = ["Maison Individuelle Pure", "Maison Individuelle Groupée"]
SITADEL_COLLECTIF = ["Logement Collectif", "Logement en Résidence"]


def momentum_metrics(df, value_col, date_col="Date"):
    """Momentum ratios in the BPCE style, from a monthly series of `value_col`:
      - roll12_yoy: latest 12-month sum vs the previous 12-month sum ("+X % sur 12 mois
        par rapport aux 12 mois précédents");
      - last3_yoy: sum of the last 3 months vs the same 3 calendar months a year earlier
        ("+X % sur les 3 derniers mois par rapport aux mêmes mois n-1") — the metric BPCE
        uses to flag an acceleration or a "coup d'arrêt".
    Returns {"roll12_yoy": float|None, "last3_yoy": float|None}. Assumes a monthly series.
    """
    s = df.dropna(subset=[value_col]).sort_values(date_col)
    vals = s[value_col].values
    out = {"roll12_yoy": None, "last3_yoy": None}
    if len(vals) >= 24:
        last12, prev12 = vals[-12:].sum(), vals[-24:-12].sum()
        if prev12 > 0:
            out["roll12_yoy"] = round((last12 - prev12) / prev12 * 100.0, 1)
    if len(vals) >= 15:
        last3, prev3 = vals[-3:].sum(), vals[-15:-12].sum()
        if prev3 > 0:
            out["last3_yoy"] = round((last3 - prev3) / prev3 * 100.0, 1)
    return out


def calculate_kpis(df, value_col, date_col="Date"):
    """
    Calculates key metrics for indicator summary cards:
    - Current Value
    - Current 12M Cumulative Value
    - Year-over-Year (YoY) Change for 12M Cumulative Value (comparing latest month to same month last year)
    - Year-over-Year (YoY) Change for monthly value
    """
    df_sorted = df.sort_values(date_col).copy()
    if len(df_sorted) < 13:
        return {
            "current_val": 0,
            "current_12m": 0,
            "yoy_12m_pct": 0.0,
            "yoy_monthly_pct": 0.0,
            "trend": "Stable"
        }
        
    latest_row = df_sorted.iloc[-1]
    latest_date = latest_row[date_col]
    
    # 12-month rolling column
    col_12m = f"{value_col}_12M"
    if col_12m not in df_sorted.columns:
        df_sorted = calculate_rolling_12m(df_sorted, [value_col])
        latest_row = df_sorted.iloc[-1]
        
    current_val = latest_row[value_col]
    current_12m = latest_row[col_12m]
    
    # Look for 12 months ago row
    date_1y_ago = latest_date - pd.DateOffset(years=1)
    # Find matching row closest to date_1y_ago
    row_1y_ago_candidates = df_sorted[df_sorted[date_col] == date_1y_ago]
    
    if len(row_1y_ago_candidates) > 0:
        row_1y_ago = row_1y_ago_candidates.iloc[0]
        val_1y_ago = row_1y_ago[value_col]
        val_12m_1y_ago = row_1y_ago[col_12m]
        
        yoy_monthly_pct = ((current_val - val_1y_ago) / val_1y_ago * 100.0) if val_1y_ago > 0 else 0.0
        yoy_12m_pct = ((current_12m - val_12m_1y_ago) / val_12m_1y_ago * 100.0) if pd.notna(val_12m_1y_ago) and val_12m_1y_ago > 0 else 0.0
    else:
        yoy_monthly_pct = 0.0
        yoy_12m_pct = 0.0
        
    # Determine general trend
    if yoy_12m_pct > 2.0:
        trend = "Haussier"
    elif yoy_12m_pct < -2.0:
        trend = "Baissier"
    else:
        trend = "Stable"
        
    return {
        "current_val": int(current_val) if not pd.isna(current_val) else 0,
        "current_12m": int(current_12m) if not pd.isna(current_12m) else 0,
        "yoy_12m_pct": round(yoy_12m_pct, 1),
        "yoy_monthly_pct": round(yoy_monthly_pct, 1),
        "trend": trend
    }
