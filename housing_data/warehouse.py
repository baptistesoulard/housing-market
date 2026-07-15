"""
Typed, columnar storage + embedded query layer for the HousingMarket datasets.

This is the reusable data layer: it takes the app's already-built pandas frames,
validates them against their contracts (see schema.py), and persists them as **Parquet**
— a typed, compressed, self-describing format any other app (Python, R, DuckDB-WASM in a
browser) can read back with zero parsing code. On top of the Parquet files it exposes a
zero-server **DuckDB** connection so the frames can be queried and joined in plain SQL,
without ever standing up a database server.

Design choices, on purpose:
  * No server. DuckDB is embedded (one process, one file / a folder of Parquet), like
    SQLite but columnar/analytical. Nothing to administer or back up beyond the files.
  * Parquet lives alongside the existing CSVs, it does not replace them yet — the
    migration is incremental and non-breaking (the Streamlit app keeps reading CSV until
    it is switched over).
  * The query surface is standard SQL over one view per dataset, so the same warehouse is
    reusable by an API (FastAPI), a notebook, or an HTML/CSS front (static Parquet export
    / DuckDB-WASM) — not just this Streamlit app.

Public API:
    write_dataset(name, df, data_dir)      validate -> Parquet (returns path)
    write_all(frames, data_dir)            bulk write of the app's frame dict
    read_dataset(name, data_dir)           Parquet -> DataFrame (CSV fallback)
    connect(data_dir, datasets=None)       DuckDB connection with a view per dataset
    query(sql, data_dir)                   run SQL over those views, return a DataFrame
    parquet_path(name, data_dir)
"""
from __future__ import annotations

import os
from typing import Iterable, Mapping

import pandas as pd

from . import schema as _schema

DEFAULT_DATA_DIR = "data"


def parquet_path(name: str, data_dir: str = DEFAULT_DATA_DIR) -> str:
    return os.path.join(data_dir, f"{name}.parquet")


def _csv_path(name: str, data_dir: str) -> str:
    return os.path.join(data_dir, f"{name}.csv")


def write_dataset(name: str, df: pd.DataFrame, data_dir: str = DEFAULT_DATA_DIR,
                  validate: bool = True) -> str:
    """Validate `df` against its contract and write it to Parquet. Returns the path.

    Validation is on by default: a frame that breaches its schema never reaches disk.
    Pass validate=False only for a deliberate, already-trusted write.
    """
    if name not in _schema.SCHEMAS:
        raise KeyError(f"Unknown dataset {name!r} (known: {sorted(_schema.SCHEMAS)})")
    os.makedirs(data_dir, exist_ok=True)
    out = _schema.validate(name, df) if validate else df
    path = parquet_path(name, data_dir)
    # pyarrow engine (already a project dependency); index is never meaningful here.
    out.to_parquet(path, index=False)
    return path


def write_all(frames: Mapping[str, pd.DataFrame], data_dir: str = DEFAULT_DATA_DIR,
              validate: bool = True) -> dict[str, str]:
    """Write every {name: frame} pair whose name is a known dataset. Unknown names are
    skipped (so callers can pass their whole frame dict). Returns {name: path}."""
    written = {}
    for name, df in frames.items():
        if name in _schema.SCHEMAS and df is not None:
            written[name] = write_dataset(name, df, data_dir, validate=validate)
    return written


def read_dataset(name: str, data_dir: str = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Read a dataset back as a DataFrame. Prefers Parquet (typed, no date re-parsing);
    falls back to the CSV during the migration window when Parquet is not present yet."""
    ppath = parquet_path(name, data_dir)
    if os.path.exists(ppath):
        return pd.read_parquet(ppath)
    cpath = _csv_path(name, data_dir)
    if os.path.exists(cpath):
        return pd.read_csv(cpath, parse_dates=["Date"])
    raise FileNotFoundError(f"No Parquet or CSV for dataset {name!r} in {data_dir!r}")


def _available_sources(data_dir: str) -> dict[str, str]:
    """{name: file path} for every known dataset that has a Parquet (preferred) or CSV
    on disk, so connect() only registers views that can actually resolve."""
    sources = {}
    for name in _schema.SCHEMAS:
        ppath = parquet_path(name, data_dir)
        cpath = _csv_path(name, data_dir)
        if os.path.exists(ppath):
            sources[name] = ppath
        elif os.path.exists(cpath):
            sources[name] = cpath
    return sources


def connect(data_dir: str = DEFAULT_DATA_DIR, datasets: Iterable[str] | None = None):
    """Return an in-memory DuckDB connection exposing one SQL view per available dataset.

    Views read the Parquet (or CSV) files directly and lazily — nothing is copied into
    the database, so this is cheap to open and always reflects the files on disk. Query
    them by name, e.g. `connect().sql("SELECT * FROM macro WHERE Date >= '2020-01-01'")`.
    """
    import duckdb  # local import: keep duckdb optional for pure-CSV consumers

    con = duckdb.connect(database=":memory:")
    sources = _available_sources(data_dir)
    wanted = set(datasets) if datasets is not None else set(sources)
    for name, path in sources.items():
        if name not in wanted:
            continue
        reader = "read_parquet" if path.endswith(".parquet") else "read_csv_auto"
        # DuckDB can't bind a prepared parameter inside CREATE VIEW (DDL). The path is
        # internal (never user input); inline it with single quotes doubled to be safe.
        lit = "'" + path.replace("\\", "/").replace("'", "''") + "'"
        con.execute(f'CREATE VIEW "{name}" AS SELECT * FROM {reader}({lit})')
    return con


def query(sql: str, data_dir: str = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Run a SQL query over the dataset views and return the result as a DataFrame."""
    con = connect(data_dir)
    try:
        return con.sql(sql).df()
    finally:
        con.close()
