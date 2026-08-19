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
  * Parquet is the **runtime read path**: the app loads typed columnar files instead of
    re-parsing CSV on every cold start. The CSVs stay next to them as the versioned,
    human-diffable interchange format — and as the fallback whenever the Parquet is absent
    (fresh clone: Parquet is gitignored) or STALE (CSVs pulled from git while the local
    Parquet still dates from an earlier session).
  * That freshness rule is the load-bearing part: `resolve()` never returns a Parquet file
    older than its own CSV, so a CSV-only refresh can not be masked by a stale mirror.
  * The query surface is standard SQL over one view per dataset, so the same warehouse is
    reusable by an API (FastAPI), a notebook, or an HTML/CSS front (static Parquet export
    / DuckDB-WASM) — not just this Streamlit app.

Public API:
    write_dataset(name, df, data_dir)      validate -> Parquet (returns path)
    write_all(frames, data_dir)            bulk write of the app's frame dict
    read_dataset(name, data_dir)           Parquet (when fresh) -> DataFrame, CSV fallback
    read_all(names, data_dir)              {name: DataFrame} for several datasets at once
    resolve(name, data_dir)                (path, kind) actually used to read a dataset
    signature(data_dir)                    hashable freshness key (cache invalidation)
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


def _mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def resolve(name: str, data_dir: str = DEFAULT_DATA_DIR) -> tuple[str | None, str | None]:
    """Return `(path, kind)` for the file a read of `name` would actually use.

    kind is "parquet", "csv", or None when the dataset is on disk in neither form.

    Parquet wins only when it is at least as recent as its sibling CSV. That guard is
    what makes a Parquet-first runtime safe. The CSVs are the versioned artefacts and the
    Parquet are gitignored, so the two go out of step in the ordinary case: a `git pull`
    brings in CSVs refreshed by the weekly job while the local Parquet still dates from
    the previous session. Without this rule the app would serve that stale mirror and hide
    the very refresh it just pulled.
    """
    ppath, cpath = parquet_path(name, data_dir), _csv_path(name, data_dir)
    pm, cm = _mtime(ppath), _mtime(cpath)
    if pm is not None and (cm is None or pm >= cm):
        return ppath, "parquet"
    if cm is not None:
        return cpath, "csv"
    return None, None


def read_dataset(name: str, data_dir: str = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Read a dataset back as a DataFrame.

    Prefers the Parquet (typed: no date re-parsing, no dtype guessing) and falls back to
    the CSV when the Parquet is missing or older than it — see `resolve`.
    """
    path, kind = resolve(name, data_dir)
    if kind == "parquet":
        return pd.read_parquet(path)
    if kind == "csv":
        return pd.read_csv(path, parse_dates=["Date"])
    raise FileNotFoundError(f"No Parquet or CSV for dataset {name!r} in {data_dir!r}")


def read_all(names: Iterable[str] | None = None,
             data_dir: str = DEFAULT_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Read several datasets at once: `{name: DataFrame}`.

    `names` defaults to every known dataset. A dataset present in neither form is simply
    absent from the result (optional datasets — revenue/ecln/company_sales — legitimately
    have no file until they are first built), so callers can supply their own empty shape.
    """
    wanted = list(_schema.SCHEMAS) if names is None else list(names)
    out: dict[str, pd.DataFrame] = {}
    for name in wanted:
        if resolve(name, data_dir)[1] is not None:
            out[name] = read_dataset(name, data_dir)
    return out


def signature(data_dir: str = DEFAULT_DATA_DIR) -> tuple:
    """A hashable freshness key over the whole warehouse, for cache invalidation.

    One entry per known dataset: `(name, kind, mtime, size)` of the file that would be
    read — so the key moves when a CSV is refreshed, when a Parquet is rewritten, and
    when a rewrite flips which of the two wins. Size is in there because two writes
    inside the same filesystem mtime tick are otherwise indistinguishable.
    """
    entries = []
    for name in sorted(_schema.SCHEMAS):
        path, kind = resolve(name, data_dir)
        if kind is None:
            entries.append((name, None, 0.0, 0))
            continue
        try:
            info = os.stat(path)
            entries.append((name, kind, info.st_mtime, info.st_size))
        except OSError:  # raced with a rewrite — treat as "changed"
            entries.append((name, kind, 0.0, 0))
    return tuple(entries)


def _available_sources(data_dir: str) -> dict[str, str]:
    """{name: file path} for every known dataset readable on disk, applying the same
    Parquet-freshness rule as read_dataset — so a SQL view never disagrees with what
    `read_dataset` would hand back for the same dataset."""
    sources = {}
    for name in _schema.SCHEMAS:
        path, kind = resolve(name, data_dir)
        if kind is not None:
            sources[name] = path
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
