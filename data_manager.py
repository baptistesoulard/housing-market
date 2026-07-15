import os
import glob
import pandas as pd
import numpy as np

# Set random seed for reproducibility
np.random.seed(42)

# --- IGEDD "ventes de logements anciens" (national monthly, 12-month cumulated) ---
# Source: IGEDD (https://www.igedd.developpement-durable.gouv.fr/prix-immobilier-...).
# The .xls holds a single national series ("Ensemble de la France"), expressed as a
# 12-month rolling cumulative count in thousands. We keep the monthly part (2001+),
# convert to absolute counts (×1000) and reconstruct implied monthly flows so the
# app's usual monthly → rolling-12m pipeline reproduces the published figure exactly.
IGEDD_ANCIEN_XLS = os.path.join("data_manual_input",
                                "nombre-vente-maison-appartement-ancien.xls")
IGEDD_ANCIEN_SHEET = "Données - data"
IGEDD_ANCIEN_DATE_COL = 1   # column holding the end-of-12-month date
IGEDD_ANCIEN_VALUE_COL = 3  # column holding the count (in thousands)

# --- SIT@DEL construction data ---
SITADEL_MANUAL_CSV = os.path.join("data_manual_input",
                                  "Donnees-mensuelles-nationales-Logements.csv")

# --- Macro indicators (real, national) ---
# Household confidence: INSEE monthly synthetic confidence indicator (CVS, base 100 =
#   long-term average), BDM idbank 001587668.
# Housing-loan rate: ECB/Banque de France "cost of borrowing for households for house
#   purchase" (MIR series M.FR.B.A2C.AM.R.A.2250.EUR.N, %, new business). This is the
#   open, downloadable equivalent of the Observatoire Crédit Logement average rate.
# Both are single-series national CSVs [Date, <value>] living in data_manual_input.
INSEE_CONFIANCE_CSV = os.path.join("data_manual_input",
                                   "insee-confiance-menages.csv")
TAUX_CREDIT_CSV = os.path.join("data_manual_input",
                               "taux-credit-habitat.csv")
# Financing-market rates, both from the ECB open SDMX API (monthly):
#   Euribor 3M : FM series M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA
#   OAT 10 ans : IRS series M.FR.L.L40.CI.0000.EUR.N.Z (French long-term benchmark
#                government bond yield, i.e. the 10-year OAT).
EURIBOR_3M_CSV = os.path.join("data_manual_input", "euribor-3-mois.csv")
OAT_10ANS_CSV = os.path.join("data_manual_input", "oat-10-ans.csv")
# Two extra INSEE context series (national), both from the BDM SDMX API:
#   Housing purchase intentions : household survey (Camme), "intentions d'achats de
#     logements (dans un délai de 1 an)", response balance, seasonally adjusted (CVS),
#     idbank 001616794 (monthly). Displayed standardized ("centrées-réduites").
#   ILO unemployment rate : "taux de chômage au sens du BIT", whole population, France
#     excl. Mayotte, seasonally adjusted, idbank 001688527 (QUARTERLY). Reindexed to the
#     monthly index leaves NaN on non-quarter months (quarters land on Jan/Apr/Jul/Oct).
INTENTIONS_LOGEMENT_CSV = os.path.join("data_manual_input",
                                       "intentions-achat-logement.csv")
CHOMAGE_BIT_CSV = os.path.join("data_manual_input", "taux-chomage-bit.csv")

# --- Prix des logements anciens (real, national) ---
# House-price indices: Notaires-INSEE "indice des prix des logements anciens", France
#   métropolitaine, base 100 = moyenne annuelle 2015, série CVS, QUARTERLY. Three columns
#   in one CSV (Ensemble / Appartements / Maisons), idbanks 010567059 / 010567057 /
#   010567061 (INSEE SDMX BDM), reindexed onto the monthly master index (NaN on off-period
#   months, exactly like the quarterly ILO unemployment series above). See
#   fetch_new_sources.py for the off-runtime acquisition.
PRIX_ANCIEN_CSV = os.path.join("data_manual_input",
                               "prix-immobilier-notaires-insee.csv")
# New-dwelling price index (INSEE IPLN, France, base 100 = 2015, CVS, QUARTERLY, idbank
# 010751595) — same base as the ancien indices, for a neuf/ancien comparison.
PRIX_NEUF_CSV = os.path.join("data_manual_input",
                             "prix-logements-neufs-insee.csv")
# Housing-loan production (€bn, MONTHLY) — ECB MIR, house purchase, France. Three columns:
#   Production_Credits_Habitat = new business total (...EUR.N, 2003+);
#   Production_Credits_Pure     = pure new loans, i.e. HORS renégociations (...EUR.P, 2019+);
#   Production_Credits_Renego   = renegotiations only (...EUR.R, 2019+).
# Renegotiations are split out because they trigger no transaction/construction (no second-
# œuvre demand) and are volatile (BPCE decomposes them likewise, p.24).
CREDIT_VOLUME_CSV = os.path.join("data_manual_input",
                                 "production-credits-habitat.csv")
# Housing-loan DEMAND (Bank Lending Survey, ECB) — net % of banks reporting rising demand
# for household house-purchase loans, France, QUARTERLY. Realised (past 3 months) and
# expected (next 3 months, BPCE's "perspectives à 3 mois"). A soft leading indicator.
CREDIT_DEMAND_BLS_CSV = os.path.join("data_manual_input", "credit-demand-bls.csv")
# --- Commercialisation des logements neufs (ECLN, SDES) — national quarterly CVS-CJO
# "ventes aux particuliers": réservations, mises en vente, annulations, encours, délai
# d'écoulement (en trimestres) et prix au m² du collectif. Its own dataset (data/ecln.csv).
ECLN_CSV = os.path.join("data_manual_input", "ecln-commercialisation-neuf.csv")

# --- Real "company revenue" benchmark series (quarterly, national, €) ---
# One CSV per company in data_manual_input/, named "ca-<slug>.csv", each holding
# [Date, Company, CA_MEUR] at quarterly frequency (Date = first month of the calendar
# quarter). These are REAL public figures compiled from investor-relations releases
# (see data_manual_input/ca-SOURCES.md) and are NEVER synthetic. They feed the
# "Moteur de Simulation Prospective" as an alternative sales benchmark expressed in M€.
REVENUE_GLOB = os.path.join("data_manual_input", "ca-*.csv")

# Real macro series: (manual-input file, target column). Only the first two are
# required (raise FileNotFoundError, triggering the synthetic fallback); the two
# financing rates are optional add-ons — a missing file just leaves NaN so the
# chart checkbox has nothing to draw rather than breaking data generation.
_MACRO_REQUIRED = [
    (INSEE_CONFIANCE_CSV, "Insee_Confiance_Menages"),
    (TAUX_CREDIT_CSV, "Credit_Logement_Taux_Interet"),
]
_MACRO_OPTIONAL = [
    (EURIBOR_3M_CSV, "Euribor_3M"),
    (OAT_10ANS_CSV, "OAT_10ans"),
    (INTENTIONS_LOGEMENT_CSV, "Intentions_Achat_Logement"),
    (CHOMAGE_BIT_CSV, "Taux_Chomage_BIT"),
    # House-price indices (quarterly) — reindexed onto the monthly index leaves NaN on
    # off-period months (same handling as the quarterly unemployment series).
    (PRIX_ANCIEN_CSV, "Prix_Ancien_Ensemble"),
    (PRIX_ANCIEN_CSV, "Prix_Ancien_Appartements"),
    (PRIX_ANCIEN_CSV, "Prix_Ancien_Maisons"),
    (PRIX_NEUF_CSV, "Prix_Neuf"),
    # Housing-loan production (€bn), monthly. Total ("new business", 2003+) plus the
    # BPCE-style decomposition pure-new-loans / renegotiations (2019+ only, NaN before).
    (CREDIT_VOLUME_CSV, "Production_Credits_Habitat"),
    (CREDIT_VOLUME_CSV, "Production_Credits_Pure"),
    (CREDIT_VOLUME_CSV, "Production_Credits_Renego"),
    # Housing-loan demand (BLS, net %) — quarterly, realised + expected ("perspectives").
    (CREDIT_DEMAND_BLS_CSV, "Demande_Credit_Realisee"),
    (CREDIT_DEMAND_BLS_CSV, "Demande_Credit_Perspectives"),
]


def build_macro_from_files(date_range):
    """
    Build the national macro dataframe [Date, Insee_Confiance_Menages,
    Credit_Logement_Taux_Interet, Euribor_3M, OAT_10ans] from the real manual-input
    CSVs, aligned on the app's monthly `date_range`. Months not covered by a source
    series are left as NaN (e.g. the housing-loan rate only starts in 2003), so charts
    show a real gap rather than an invented value. Raises FileNotFoundError when a
    REQUIRED source file (confidence, housing-loan rate) is missing (callers fall back
    to synthetic data); optional financing rates simply stay NaN when absent.
    """
    idx = pd.DatetimeIndex(date_range)

    def _load(path, col):
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"])
        s = df.set_index("Date")[col]
        # Align to the master monthly index (NaN where the source has no data).
        return s.reindex(idx)

    out = {"Date": idx}
    for path, col in _MACRO_REQUIRED:
        out[col] = _load(path, col).to_numpy()   # missing file -> FileNotFoundError
    for path, col in _MACRO_OPTIONAL:
        try:
            out[col] = _load(path, col).to_numpy()
        except FileNotFoundError:
            out[col] = np.nan
    return pd.DataFrame(out)

def _synthetic_insee(year, month):
    """SYNTHETIC household-confidence fallback (only when the real INSEE CSV is missing).
    Long-term average ~100; year-specific regimes (pre-2018 approximated)."""
    if year <= 2007:
        return 104.0 + np.sin(month / 2.0)               # pre-crisis optimism
    elif year in (2008, 2009):
        return 86.0 - (6.0 if month in (9, 10, 11) else 0.0)  # financial crisis
    elif year in (2010, 2011):
        return 96.0 + np.cos(month / 3.0) * 2
    elif 2012 <= year <= 2015:
        return 90.0 + np.sin(month / 3.0) * 2             # eurozone doldrums
    elif year in (2016, 2017):
        return 100.0 + np.sin(month / 2.0)
    elif year == 2018:
        return 101.0 + np.sin(month / 2.0)
    elif year == 2019:
        return 103.0 + np.cos(month / 2.0)
    elif year == 2020:
        return 92.0 - (10.0 if month in (4, 5, 11) else 2.0)  # COVID drop
    elif year == 2021:
        return 98.0 + np.sin(month / 3.0) * 3
    elif year == 2022:
        return 88.0 - (month / 2.0)
    elif year in (2023, 2024):
        return 82.0 + np.random.normal(0, 1.5)
    elif year == 2025:
        return 86.0 + (month / 3.0)
    else:  # 2026+
        return 90.0 + np.random.normal(0, 1.0)


def _synthetic_rate(year, month):
    """SYNTHETIC mortgage-rate fallback (%) — only when the real BdF/BCE CSV is missing."""
    if year <= 2017:
        # Long decline from ~5.0% (2001) to ~1.5% (2017), with a 2008 bump.
        base = 5.0 - (year - 2001) * (5.0 - 1.5) / 16.0
        if year == 2008:
            base += 0.6
        return base + np.random.normal(0, 0.03)
    elif year == 2018:
        return 1.45 + (month * 0.01)
    elif year == 2019:
        return 1.30 - (month * 0.015)
    elif year == 2020:
        return 1.15 + np.random.normal(0, 0.02)
    elif year == 2021:
        return 1.10 + (month * 0.005)
    elif year == 2022:
        return 1.12 + (month * 0.12)                      # quick hike
    elif year == 2023:
        return 2.60 + (month * 0.14)
    elif year == 2024:
        return 4.20 - (month * 0.04)
    elif year == 2025:
        return 3.70 - (month * 0.03)
    else:  # 2026+
        return 3.34 + np.random.normal(0, 0.03)


def generate_sitadel_and_macro():
    """Build the REAL national SIT@DEL construction series (from the manual-input CSV) and
    the REAL macro dataframe (build_macro_from_files, with a synthetic fallback). No DVF,
    no sales here: DVF is the real IGEDD series (ensure_dvf_ancien) and second-œuvre sales
    are derived from real SIT@DEL + real DVF in build_sales().

    Coverage is DYNAMIC — no hardcoded end. SIT@DEL comes straight from its CSV (its own
    real extent). The macro monthly index spans 2001 to SIT@DEL's last month plus a short
    buffer (faster financial series such as confidence/Euribor can lead construction data
    by a month or two), then trailing months with no real value in any column are trimmed
    so the frame ends exactly on the latest real observation — never a phantom NaN month.
    National-only: one row per Date × Type, tagged Region/Department = "France".
    """
    # --- SIT@DEL construction (REAL) ---
    raw_sitadel = pd.read_csv(SITADEL_MANUAL_CSV, sep=";")
    raw_sitadel["Date"] = pd.to_datetime(raw_sitadel["ANNEE"].astype(str) + "-" + raw_sitadel["MOIS"].astype(str).str.zfill(2) + "-01")
    cvs_cjo_sitadel = raw_sitadel[raw_sitadel["NAT_SERIES"] == "CVS-CJO"].copy()
    type_map = {
        "Collectif": "Logement Collectif",
        "Individuel groupe": "Maison Individuelle Groupée",
        "Individuel pur": "Maison Individuelle Pure",
        "Residence": "Logement en Résidence"
    }
    cvs_cjo_sitadel = cvs_cjo_sitadel[cvs_cjo_sitadel["TYPE_LGT"].isin(type_map.keys())].copy()
    cvs_cjo_sitadel["Type"] = cvs_cjo_sitadel["TYPE_LGT"].map(type_map)
    cvs_cjo_sitadel["Region"] = "France"
    cvs_cjo_sitadel["Department"] = "France"
    cvs_cjo_sitadel = cvs_cjo_sitadel.rename(columns={"LOG_AUT": "Permis", "LOG_COM": "MisesEnChantier"})
    df_sitadel = cvs_cjo_sitadel[["Date", "Region", "Department", "Type", "Permis", "MisesEnChantier"]].sort_values(["Date", "Type"]).reset_index(drop=True)
    sit_max = df_sitadel["Date"].max()

    # --- Macro (REAL, synthetic fallback) — dynamic range, trailing-NaN trimmed ---
    try:
        probe_range = pd.date_range("2001-01-01", sit_max + pd.DateOffset(months=6), freq="MS")
        df_macro = build_macro_from_files(probe_range)
        val_cols = [c for c in df_macro.columns if c != "Date"]
        has_value = df_macro[val_cols].notna().any(axis=1)
        if has_value.any():
            df_macro = df_macro.loc[:has_value[has_value].index.max()].reset_index(drop=True)
    except FileNotFoundError:
        # Fallback bounded to SIT@DEL's real extent (no lead months / no invented tail).
        date_range = pd.date_range("2001-01-01", sit_max, freq="MS")
        df_macro = pd.DataFrame({
            "Date": date_range,
            "Insee_Confiance_Menages": [_synthetic_insee(d.year, d.month) for d in date_range],
            "Credit_Logement_Taux_Interet": [max(0.3, _synthetic_rate(d.year, d.month)) for d in date_range],
            "Euribor_3M": np.nan,
            "OAT_10ans": np.nan,
        })
    return df_sitadel, df_macro


def build_sales(df_sitadel, df_dvf):
    """Synthetic national sales of second-œuvre building products, driven by the REAL
    leading indicators the app actually displays: individual-house & collective permits
    (SIT@DEL) and existing-home transactions (IGEDD). Three generic building-trade
    families, each with its own lead-time: closures/joinery ~12m after housing permits;
    outdoor equipment with individual houses; security/home-automation ~2m after
    existing-home sales.

    The series is bounded to the real market extent — min of the SIT@DEL and IGEDD last
    months — so it never fabricates a month with no underlying real data. Values are the
    only remaining synthetic dataset, pending a real second-œuvre source.
    """
    np.random.seed(42)  # reproducible synthetic noise, independent of prior RNG use
    end = min(df_sitadel["Date"].max(), df_dvf["Date"].max())
    date_range = pd.date_range("2001-01-01", end, freq="MS")

    permits_house = df_sitadel[df_sitadel["Type"] == "Maison Individuelle Pure"].groupby("Date")["Permis"].sum()
    permits_coll = df_sitadel[df_sitadel["Type"] == "Logement Collectif"].groupby("Date")["Permis"].sum()
    # REAL IGEDD monthly transaction flows (the exact series shown to the user), not a
    # discarded synthetic proxy.
    tx_total = df_dvf.groupby("Date")["Transactions"].sum()

    sales_data = []
    for date in date_range:
        ph = permits_house.get(date - pd.DateOffset(months=12), permits_house.iloc[0])
        pc = permits_coll.get(date - pd.DateOffset(months=18), permits_coll.iloc[0])
        tx = tx_total.get(date - pd.DateOffset(months=2), tx_total.iloc[0])

        fermetures = int(ph * 4.8 + pc * 1.5 + np.random.normal(3000, 400))
        exterieur = int(ph * 0.95 + np.random.normal(600, 100))
        securite = int(tx * 0.12 + np.random.normal(1000, 200))

        for product, units in (("Fermetures & Menuiseries", fermetures),
                               ("Équipements Extérieurs", exterieur),
                               ("Sécurité & Domotique", securite)):
            sales_data.append({
                "Date": date, "Region": "France", "Department": "France",
                "Product": product, "Sales_Units": max(0, units),
            })

    return pd.DataFrame(sales_data)

class DataManager:
    """
    Manages loading, updating, and saving of housing and macroeconomic indicators.
    Provides standard schemas and holds data in session states or files.
    """
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.paths = {
            "sitadel": os.path.join(self.data_dir, "sitadel.csv"),
            "dvf": os.path.join(self.data_dir, "dvf.csv"),
            "macro": os.path.join(self.data_dir, "macro.csv"),
            "sales": os.path.join(self.data_dir, "sales.csv"),
            "revenue": os.path.join(self.data_dir, "revenue.csv"),
            "ecln": os.path.join(self.data_dir, "ecln.csv")
        }
        
    def load_or_generate_all(self, force_regenerate=False):
        """
        Loads the datasets. SIT@DEL is real (manual-input CSV), macro is real
        (build_macro_from_files) and the "ventes dans l'ancien" series (df_dvf) is the real
        IGEDD national series (ensure_dvf_ancien) — none are synthetic. Only the
        second-œuvre `sales` remain synthetic, and they are now DERIVED FROM the real
        SIT@DEL permits and the real IGEDD transactions (build_sales), so the modelled
        series is consistent with the data the app shows.
        """
        # 1. Real IGEDD "ventes dans l'ancien" first — it anchors both the display and the
        #    transaction-linked synthetic sales, so it must exist before sales are built.
        self.ensure_dvf_ancien(force_rebuild=force_regenerate)
        df_dvf = pd.read_csv(self.paths["dvf"], parse_dates=["Date"])

        # 2. Real SIT@DEL + macro, generated & cached together.
        if not (os.path.exists(self.paths["sitadel"]) and os.path.exists(self.paths["macro"])) \
                or force_regenerate:
            df_sitadel, df_macro = generate_sitadel_and_macro()
            df_sitadel.to_csv(self.paths["sitadel"], index=False, encoding="utf-8")
            df_macro.to_csv(self.paths["macro"], index=False, encoding="utf-8")
        else:
            df_sitadel = pd.read_csv(self.paths["sitadel"], parse_dates=["Date"])
            df_macro = pd.read_csv(self.paths["macro"], parse_dates=["Date"])

        # 3. Synthetic second-œuvre sales, DERIVED FROM real SIT@DEL permits + real IGEDD
        #    transactions. Rebuild when forced, missing, or when a driver (dvf/sitadel) is
        #    newer than the cache (so a data refresh propagates).
        _sales_stale = (force_regenerate or not os.path.exists(self.paths["sales"])
                        or os.path.getmtime(self.paths["sales"]) < max(
                            os.path.getmtime(self.paths["dvf"]),
                            os.path.getmtime(self.paths["sitadel"])))
        if _sales_stale:
            df_sales = build_sales(df_sitadel, df_dvf)
            df_sales.to_csv(self.paths["sales"], index=False, encoding="utf-8")
        else:
            df_sales = pd.read_csv(self.paths["sales"], parse_dates=["Date"])

        # Real company-revenue benchmark (quarterly, €). Rebuilt from the ca-*.csv
        # manual-input files; empty frame when none are present.
        self.ensure_revenue(force_rebuild=force_regenerate)
        if os.path.exists(self.paths["revenue"]):
            df_revenue = pd.read_csv(self.paths["revenue"], parse_dates=["Date"])
        else:
            df_revenue = pd.DataFrame(columns=["Date", "Company", "CA_MEUR"])

        # Real ECLN commercialisation-of-new-dwellings series (quarterly). Rebuilt from
        # the SDES manual-input CSV; empty frame when the source file is absent.
        self.ensure_ecln(force_rebuild=force_regenerate)
        if os.path.exists(self.paths["ecln"]):
            df_ecln = pd.read_csv(self.paths["ecln"], parse_dates=["Date"])
        else:
            df_ecln = pd.DataFrame(columns=[
                "Date", "Reservations", "MisesEnVente", "Annulations",
                "Encours", "DelaiEcoulement", "PrixM2_Collectif",
                "Resa_Sociaux", "Resa_Institutionnels"])

        return df_sitadel, df_dvf, df_macro, df_sales, df_revenue, df_ecln

    @staticmethod
    def build_revenue_from_manual_inputs(pattern=REVENUE_GLOB):
        """
        Reads every data_manual_input/ca-*.csv file (one per company) and returns a
        single tidy dataframe [Date, Company, CA_MEUR] at quarterly frequency, sorted
        by company then date. Each source file must expose those three columns; the
        Company label falls back to the file slug when the column is absent. Returns an
        empty (correctly-typed) frame when no source file matches.
        """
        cols = ["Date", "Company", "CA_MEUR"]
        frames = []
        for path in sorted(glob.glob(pattern)):
            df = pd.read_csv(path)
            df["Date"] = pd.to_datetime(df["Date"])
            if "Company" not in df.columns:
                slug = os.path.splitext(os.path.basename(path))[0].replace("ca-", "")
                df["Company"] = slug
            df["CA_MEUR"] = pd.to_numeric(df["CA_MEUR"], errors="coerce")
            frames.append(df[cols])
        if not frames:
            return pd.DataFrame(columns=cols)
        out = pd.concat(frames, ignore_index=True).dropna(subset=["CA_MEUR"])
        return out.sort_values(["Company", "Date"]).reset_index(drop=True)

    def ensure_revenue(self, force_rebuild=False):
        """
        Guarantees data/revenue.csv holds the real company-revenue benchmark compiled
        from the ca-*.csv manual-input files. (Re)builds it when the cache is missing or
        force_rebuild is set. Never writes synthetic data. Returns (success, message);
        success is True with an explanatory message even when no source file exists (the
        benchmark is simply unavailable, not an error).
        """
        # Rebuild when forced, when the cache is missing, or when any source ca-*.csv is
        # newer than the cache (so editing/adding a company refreshes automatically).
        if os.path.exists(self.paths["revenue"]) and not force_rebuild:
            cache_mtime = os.path.getmtime(self.paths["revenue"])
            sources = glob.glob(REVENUE_GLOB)
            if not sources or all(os.path.getmtime(s) <= cache_mtime for s in sources):
                return True, "CA entreprise (benchmark réel) déjà présent."
        df = self.build_revenue_from_manual_inputs()
        if df.empty:
            return True, ("Aucun fichier data_manual_input/ca-*.csv : "
                          "benchmark CA entreprise indisponible.")
        df.to_csv(self.paths["revenue"], index=False, encoding="utf-8")
        companies = ", ".join(sorted(df["Company"].unique()))
        return True, (f"CA entreprise importé : {len(df)} points trimestriels "
                      f"({companies}).")

    @staticmethod
    def build_ecln_from_manual_input(path=ECLN_CSV):
        """
        Reads the national ECLN commercialisation series (SDES, quarterly CVS-CJO) from
        its manual-input CSV and returns a tidy, date-sorted dataframe [Date,
        Reservations, MisesEnVente, Annulations, Encours, DelaiEcoulement,
        PrixM2_Collectif]. The file is already in the app's target shape (see
        fetch_new_sources.py); this just parses dates and enforces numeric columns.
        """
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"])
        for c in ["Reservations", "MisesEnVente", "Annulations", "Encours",
                  "DelaiEcoulement", "PrixM2_Collectif",
                  "Resa_Sociaux", "Resa_Institutionnels"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values("Date").reset_index(drop=True)

    def ensure_ecln(self, force_rebuild=False):
        """
        Guarantees data/ecln.csv holds the real ECLN commercialisation series, (re)built
        from the SDES manual-input CSV when the cache is missing / older than the source
        / force_rebuild is set. Never writes synthetic data. Returns (success, message);
        a missing source file is not an error (the ECLN charts are simply unavailable).
        """
        if os.path.exists(self.paths["ecln"]) and not force_rebuild:
            if not os.path.exists(ECLN_CSV) or \
                    os.path.getmtime(ECLN_CSV) <= os.path.getmtime(self.paths["ecln"]):
                return True, "Commercialisation neuf (ECLN) déjà présente."
        if not os.path.exists(ECLN_CSV):
            return True, (f"Fichier ECLN introuvable (« {ECLN_CSV} ») : "
                          "commercialisation neuf indisponible.")
        df = self.build_ecln_from_manual_input()
        df.to_csv(self.paths["ecln"], index=False, encoding="utf-8")
        dmin, dmax = df["Date"].min().strftime("%Y-%m"), df["Date"].max().strftime("%Y-%m")
        return True, (f"Commercialisation neuf (ECLN) importée : {len(df)} trimestres "
                      f"({dmin} → {dmax}).")

    @staticmethod
    def build_dvf_ancien_from_igedd(xls_path=IGEDD_ANCIEN_XLS):
        """
        Reads the IGEDD national "ventes de logements anciens" .xls and returns a
        national, app-shaped dataframe [Date, Region, Department, Type, Transactions]
        at monthly frequency.

        The published series is a 12-month rolling cumulative count (in thousands).
        We keep the monthly section (from 2001), convert to absolute counts, and
        reconstruct the implied monthly flow f so that a trailing-12-month sum of f
        reproduces the published cumulative C exactly:
            f[m] = C[m] - C[m-1] + f[m-12],  seeded flat over the first 12 months.
        """
        raw = pd.read_excel(xls_path, sheet_name=IGEDD_ANCIEN_SHEET, header=None)
        s = raw.iloc[:, [IGEDD_ANCIEN_DATE_COL, IGEDD_ANCIEN_VALUE_COL]].copy()
        s.columns = ["date", "val"]
        s["date"] = pd.to_datetime(s["date"], errors="coerce")
        s["val"] = pd.to_numeric(s["val"].astype(str).str.replace(",", ".", regex=False),
                                 errors="coerce")
        s = s.dropna(subset=["date", "val"]).sort_values("date")
        # Keep the monthly part only (annual points before 2001 break rolling-12m).
        s = s[s["date"] >= "2001-01-01"]
        if len(s) < 13:
            raise ValueError("Série IGEDD trop courte / colonnes inattendues.")

        dates = s["date"].dt.to_period("M").dt.to_timestamp()   # first of month
        C = s["val"].to_numpy(dtype=float) * 1000.0             # thousands → counts
        n = len(C)
        f = np.empty(n)
        f[:12] = C[11] / 12.0                                   # flat seed (first year)
        for m in range(12, n):
            f[m] = C[m] - C[m - 1] + f[m - 12]

        return pd.DataFrame({
            "Date": dates.values,
            "Region": "France",
            "Department": "France",
            "Type": "Ancien",
            "Transactions": np.rint(f).astype(int),
        })

    def ensure_dvf_ancien(self, force_rebuild=False):
        """
        Guarantees data/dvf.csv holds the real IGEDD "ventes dans l'ancien" series
        (national, monthly flows reconstructed from the 12-month cumulative). Builds
        it from the IGEDD .xls when data/dvf.csv is missing or force_rebuild is set.
        Returns (success, message). Never writes synthetic DVF.
        """
        if os.path.exists(self.paths["dvf"]) and not force_rebuild:
            return True, "Ventes ancien (IGEDD) déjà présentes."
        try:
            df = self.build_dvf_ancien_from_igedd()
        except FileNotFoundError:
            return False, (f"Fichier IGEDD introuvable : « {IGEDD_ANCIEN_XLS} ».")
        except ImportError:
            return False, ("Lecture .xls impossible : installez « xlrd>=2.0.1 » "
                           "(pip install xlrd).")
        except Exception as e:
            return False, f"Erreur lecture IGEDD : {e}"

        df.to_csv(self.paths["dvf"], index=False, encoding="utf-8")
        dmin, dmax = df["Date"].min().strftime("%Y-%m"), df["Date"].max().strftime("%Y-%m")
        return True, (f"Ventes ancien (IGEDD) importées : {len(df)} mois "
                      f"({dmin} → {dmax}).")

    def update_with_custom_csv(self, category, uploaded_file):
        """
        Updates a specific dataset category using a user-uploaded CSV file.
        Performs basic validation of required columns.
        """
        try:
            df = pd.read_csv(uploaded_file)
            
            # Validation based on category
            if category == "sitadel":
                required = {"Date", "Region", "Department", "Type", "Permis", "MisesEnChantier"}
            elif category == "dvf":
                required = {"Date", "Region", "Department", "Type", "Transactions"}
            elif category == "macro":
                required = {"Date", "Insee_Confiance_Menages", "Credit_Logement_Taux_Interet"}
            elif category == "sales":
                required = {"Date", "Region", "Department", "Product", "Sales_Units"}
            else:
                return False, "Catégorie inconnue"
                
            missing = required - set(df.columns)
            if missing:
                return False, f"Colonnes manquantes: {', '.join(missing)}"
            
            # Ensure proper Date formatting
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")
            
            # Save the updated file
            df.to_csv(self.paths[category], index=False, encoding="utf-8")
            return True, f"Fichier {category}.csv mis à jour avec succès !"
            
        except Exception as e:
            return False, f"Erreur lors du traitement du fichier: {str(e)}"
            
    def get_geography_hierarchy(self, df):
        """Region -> sorted departments, derived from the data (national: France)."""
        return {r: sorted(df[df["Region"] == r]["Department"].unique().tolist())
                for r in df["Region"].unique()}
