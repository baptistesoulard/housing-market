"""
housing_data — reusable, engine-light data layer for the HousingMarket datasets.

Two independent pieces, usable together or apart:
  * schema : typed pandera contracts + validate() — robustness / tests, no storage tie-in.
  * warehouse : Parquet persistence + an embedded DuckDB SQL surface over the files.

Typical uses:
    from housing_data import validate, write_all, read_dataset, connect, query
    write_all({"macro": df_macro, "sitadel": df_sitadel})      # validate -> Parquet
    df = read_dataset("macro")                                  # Parquet (CSV fallback)
    df = query("SELECT Date, Reservations FROM ecln ORDER BY Date")   # SQL, no server

The layer is deliberately decoupled from Streamlit so an API, a notebook or an HTML/CSS
front can consume the exact same warehouse.
"""
from .schema import SCHEMAS, MACRO_VALUE_COLUMNS, validate
from .warehouse import (
    DEFAULT_DATA_DIR,
    connect,
    parquet_path,
    query,
    read_dataset,
    write_all,
    write_dataset,
)

__all__ = [
    "SCHEMAS",
    "MACRO_VALUE_COLUMNS",
    "validate",
    "DEFAULT_DATA_DIR",
    "connect",
    "parquet_path",
    "query",
    "read_dataset",
    "write_all",
    "write_dataset",
]
