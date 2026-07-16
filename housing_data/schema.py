"""
Data contracts for the HousingMarket datasets (pandera).

Each dataset the app persists has an explicit, typed schema here. Validating a frame
against its schema *before* it is written to the warehouse turns a silent breakage
(a source column renamed upstream, a stray NaN, a non-national row) into a loud,
testable error. This is the robustness layer the storage engine itself does not give
you — it is deliberately independent of DuckDB/Parquet so it can guard a CSV, a
pandas frame or a Parquet write identically, and be reused by any other app that
consumes these series.

Public API:
    SCHEMAS          mapping {dataset_name: DataFrameSchema}
    validate(name, df, lazy=True) -> validated (coerced) DataFrame
    MACRO_VALUE_COLUMNS  the ordered macro indicator columns (excl. Date)
"""
from __future__ import annotations

# pandera split its pandas API into `pandera.pandas` (>=0.20). Fall back to the flat
# import so this keeps working on older pins.
try:  # pragma: no cover - import shim
    import pandera.pandas as pa
    from pandera.pandas import Column, Check, DataFrameSchema
except ImportError:  # pragma: no cover
    import pandera as pa
    from pandera import Column, Check, DataFrameSchema

# --- shared building blocks -------------------------------------------------
_DATE = Column("datetime64[ns]", nullable=False, coerce=True,
               title="First day of the observation month/quarter")
# National-only invariant: every persisted row is tagged France/France.
_FRANCE = Column(str, Check.isin(["France"]), nullable=False, coerce=True)

# Canonical category vocabularies (a value outside the set is a contract breach).
SITADEL_TYPES = [
    "Logement Collectif",
    "Maison Individuelle Groupée",
    "Maison Individuelle Pure",
    "Logement en Résidence",
]
SALES_PRODUCTS = [
    "Fermetures & Menuiseries",
    "Équipements Extérieurs",
    "Sécurité & Domotique",
]

# Every macro indicator column (all optional/nullable: a source that starts late or is
# absent leaves a real NaN gap rather than an invented value — see data_manager).
MACRO_VALUE_COLUMNS = [
    "Insee_Confiance_Menages",
    "Credit_Logement_Taux_Interet",
    "Euribor_3M",
    "OAT_10ans",
    "Intentions_Achat_Logement",
    "Taux_Chomage_BIT",
    "Prix_Ancien_Ensemble",
    "Prix_Ancien_Appartements",
    "Prix_Ancien_Maisons",
    "Prix_Neuf",
    "Production_Credits_Habitat",
    "Production_Credits_Pure",
    "Production_Credits_Renego",
    "Demande_Credit_Realisee",
    "Demande_Credit_Perspectives",
    # Renovation pillar (real INSEE building-industry survey — NaN until fetch runs):
    #   Reno_Activite_Batiment  = "activité passée — second œuvre" opinion balance, CVS
    #                             (idbank 001586954) — current second-œuvre demand.
    #   Reno_Activite_Prevue    = "activité prévue — second œuvre" opinion balance, CVS
    #                             (idbank 001586886) — a leading signal (planned activity).
    "Reno_Activite_Batiment",
    "Reno_Activite_Prevue",
]

_COUNT = lambda title: Column(int, Check.ge(0), nullable=False, coerce=True, title=title)


# --- dataset schemas --------------------------------------------------------
# strict=False everywhere: an unexpected *extra* column is tolerated, but a *missing*
# declared column (the usual symptom of an upstream rename) fails loudly. coerce=True so
# validation also normalises dtypes (CSV strings -> datetime/int/float).

SITADEL = DataFrameSchema(
    {
        "Date": _DATE,
        "Region": _FRANCE,
        "Department": _FRANCE,
        "Type": Column(str, Check.isin(SITADEL_TYPES), nullable=False, coerce=True),
        "Permis": _COUNT("Building permits (LOG_AUT)"),
        "MisesEnChantier": _COUNT("Housing starts (LOG_COM)"),
    },
    strict=False, coerce=True, name="sitadel",
    unique=["Date", "Type"],
)

VENTES_ANCIEN = DataFrameSchema(
    {
        "Date": _DATE,
        "Region": _FRANCE,
        "Department": _FRANCE,
        "Type": Column(str, Check.isin(["Ancien"]), nullable=False, coerce=True),
        "Transactions": _COUNT("Existing-home sales (reconstructed monthly flow)"),
    },
    strict=False, coerce=True, name="ventes_ancien",
    unique=["Date", "Type"],
)

MACRO = DataFrameSchema(
    {
        "Date": _DATE,
        **{c: Column(float, nullable=True, coerce=True) for c in MACRO_VALUE_COLUMNS},
    },
    strict=False, coerce=True, name="macro",
    unique=["Date"],
)

SALES = DataFrameSchema(
    {
        "Date": _DATE,
        "Region": _FRANCE,
        "Department": _FRANCE,
        "Product": Column(str, Check.isin(SALES_PRODUCTS), nullable=False, coerce=True),
        "Sales_Units": _COUNT("Synthetic second-œuvre units"),
    },
    strict=False, coerce=True, name="sales",
    unique=["Date", "Product"],
)

REVENUE = DataFrameSchema(
    {
        "Date": _DATE,
        "Company": Column(str, nullable=False, coerce=True),
        "CA_MEUR": Column(float, Check.ge(0), nullable=False, coerce=True,
                          title="Quarterly revenue (M€)"),
    },
    strict=False, coerce=True, name="revenue",
    unique=["Date", "Company"],
)

ECLN = DataFrameSchema(
    {
        "Date": _DATE,
        "Reservations": Column(float, nullable=True, coerce=True),
        "MisesEnVente": Column(float, nullable=True, coerce=True),
        "Annulations": Column(float, nullable=True, coerce=True),
        "Encours": Column(float, nullable=True, coerce=True),
        "DelaiEcoulement": Column(float, Check.ge(0), nullable=True, coerce=True),
        "PrixM2_Collectif": Column(float, Check.ge(0), nullable=True, coerce=True),
        "Resa_Sociaux": Column(float, nullable=True, coerce=True),
        "Resa_Institutionnels": Column(float, nullable=True, coerce=True),
    },
    strict=False, coerce=True, name="ecln",
    unique=["Date"],
)

# Optional user-imported monthly company sales (present only after an import). Multi-series:
# one company, one or more product families ("Serie"), monthly. A single-series import gets
# Serie = Company so the shape is uniform whether the source file split by product or not.
COMPANY_SALES = DataFrameSchema(
    {
        "Date": _DATE,
        "Company": Column(str, nullable=False, coerce=True),
        "Serie": Column(str, nullable=False, coerce=True,
                        title="Product family / imported series label"),
        "Sales": Column(float, nullable=False, coerce=True,
                        title="Imported monthly sales"),
    },
    strict=False, coerce=True, name="company_sales",
    unique=["Date", "Serie"],
)

SCHEMAS: dict[str, DataFrameSchema] = {
    "sitadel": SITADEL,
    "ventes_ancien": VENTES_ANCIEN,
    "macro": MACRO,
    "sales": SALES,
    "revenue": REVENUE,
    "ecln": ECLN,
    "company_sales": COMPANY_SALES,
}


def validate(name: str, df, lazy: bool = True):
    """Validate `df` against the named dataset schema and return the coerced frame.

    Raises KeyError for an unknown dataset name and pandera.errors.SchemaError(s) when
    the frame violates its contract (with lazy=True, all failures are collected and
    reported together). An empty frame is passed through untouched — a not-yet-populated
    optional dataset (revenue/ecln/company_sales absent) is not a contract breach.
    """
    schema = SCHEMAS[name]
    if df is None or len(df) == 0:
        return df
    return schema.validate(df, lazy=lazy)
