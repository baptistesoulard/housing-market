"""
Contracts + warehouse round-trip tests for the housing_data layer.

Runs standalone (`python tests/test_housing_data.py`) — no pytest required — and is also
pytest-compatible (test_* functions). It writes Parquet into a throwaway temp dir, so it
never touches the app's data/ folder.
"""
import os
import sys
import tempfile
import time

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import housing_data as hd
from housing_data import schema as S


def _good_ventes_ancien():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
        "Region": "France", "Department": "France", "Type": "Ancien",
        "Transactions": [65000, 66000],
    })


def test_valid_frame_passes_and_is_coerced():
    df = _good_ventes_ancien().astype({"Transactions": "float"})
    out = hd.validate("ventes_ancien", df)
    assert str(out["Transactions"].dtype) == "int64"      # coerced back to the contract
    assert str(out["Date"].dtype) == "datetime64[ns]"


def test_contract_rejects_bad_data():
    bad = {
        "renamed column": _good_ventes_ancien().rename(columns={"Transactions": "Tx"}),
        "negative count": _good_ventes_ancien().assign(Transactions=[-1, 5]),
        "non-national row": _good_ventes_ancien().assign(Region=["Bretagne", "France"]),
        "unknown Type": _good_ventes_ancien().assign(Type=["Neuf", "Ancien"]),
        "duplicate Date/Type": pd.concat([_good_ventes_ancien().head(1)] * 2, ignore_index=True),
    }
    for label, df in bad.items():
        try:
            hd.validate("ventes_ancien", df)
            raise AssertionError(f"contract should have rejected: {label}")
        except AssertionError:
            raise
        except Exception:
            pass  # expected: a schema error


def test_empty_optional_frame_passes():
    empty = pd.DataFrame(columns=["Date", "Company", "Sales"])
    assert hd.validate("company_sales", empty) is empty   # no-op on empty


def test_all_known_datasets_have_a_schema():
    expected = {"sitadel", "ventes_ancien", "macro", "sales", "revenue", "ecln",
                "company_sales", "dvf"}
    assert set(S.SCHEMAS) == expected


def test_dvf_est_le_seul_dataset_non_national():
    """`dvf` porte de VRAIS codes de département ; les autres restent contraints à France.

    C'est la raison d'être d'un dataset séparé : desserrer Region/Department sur sitadel,
    sales ou ventes_ancien ferait sauter le filet de `tests/test_queries_parity.py`, qui
    compare chaque requête SQL à une implémentation pandas de référence sur ces datasets.
    """
    import pandas as pd
    dvf = pd.DataFrame({"Date": ["2024-01-01"], "Department": ["2A"], "Type": ["Ensemble"],
                        "PrixM2Median": [2500.0], "PrixMedian": [200000.0], "NbVentes": [12]})
    assert hd.validate("dvf", dvf) is not None
    # Et l'inverse : « France » n'est PAS un code de département valide.
    national = dvf.assign(Department=["France"])
    with pytest.raises(Exception):
        hd.validate("dvf", national, lazy=False)


def test_parquet_and_duckdb_round_trip():
    with tempfile.TemporaryDirectory() as d:
        hd.write_dataset("ventes_ancien", _good_ventes_ancien(), data_dir=d)
        assert os.path.exists(hd.parquet_path("ventes_ancien", d))
        # read back keeps the datetime type (no CSV re-parsing)
        back = hd.read_dataset("ventes_ancien", data_dir=d)
        assert str(back["Date"].dtype) == "datetime64[ns]"
        assert len(back) == 2
        # SQL over the DuckDB view
        res = hd.query("SELECT SUM(Transactions) AS t FROM ventes_ancien", data_dir=d)
        assert int(res["t"].iloc[0]) == 131000


# --- phase 2: Parquet is the runtime read path, with a freshness guard --------------

def test_resolve_prefers_parquet_but_never_a_stale_one():
    """The load-bearing rule of phase 2: a CSV rewritten by a pandas-only job (the weekly
    refresh installs neither pyarrow nor pandera) must win over the older Parquet mirror,
    otherwise the app would serve last week's data and hide the refresh."""
    with tempfile.TemporaryDirectory() as d:
        df = _good_ventes_ancien()
        # CSV only -> CSV
        df.to_csv(os.path.join(d, "ventes_ancien.csv"), index=False)
        assert hd.resolve("ventes_ancien", d)[1] == "csv"
        # Parquet written after the CSV -> Parquet
        hd.write_dataset("ventes_ancien", df, data_dir=d)
        assert hd.resolve("ventes_ancien", d)[1] == "parquet"
        # CSV refreshed afterwards -> back to CSV, and the new rows are the ones read
        newer = pd.concat([df, pd.DataFrame({
            "Date": pd.to_datetime(["2020-03-01"]), "Region": ["France"],
            "Department": ["France"], "Type": ["Ancien"], "Transactions": [67000],
        })], ignore_index=True)
        cpath = os.path.join(d, "ventes_ancien.csv")
        newer.to_csv(cpath, index=False)
        os.utime(cpath, (time.time() + 10, time.time() + 10))
        assert hd.resolve("ventes_ancien", d)[1] == "csv"
        assert len(hd.read_dataset("ventes_ancien", data_dir=d)) == 3
        # a SQL view must agree with read_dataset rather than keep pointing at the mirror
        assert int(hd.query("SELECT COUNT(*) AS n FROM ventes_ancien", data_dir=d)["n"].iloc[0]) == 3


def test_resolve_reports_nothing_for_an_absent_dataset():
    with tempfile.TemporaryDirectory() as d:
        assert hd.resolve("ecln", d) == (None, None)
        try:
            hd.read_dataset("ecln", data_dir=d)
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError:
            pass


def test_read_all_returns_only_what_is_on_disk():
    with tempfile.TemporaryDirectory() as d:
        hd.write_dataset("ventes_ancien", _good_ventes_ancien(), data_dir=d)
        frames = hd.read_all(data_dir=d)
        assert set(frames) == {"ventes_ancien"}          # optional datasets stay absent
        assert str(frames["ventes_ancien"]["Date"].dtype) == "datetime64[ns]"
        assert set(hd.read_all(["ecln"], data_dir=d)) == set()


def test_signature_moves_on_every_kind_of_change():
    """The Streamlit cache key: it must move on a rewrite, and also when a refresh flips
    which file (Parquet or CSV) a dataset is read from."""
    with tempfile.TemporaryDirectory() as d:
        empty = hd.signature(d)
        hd.write_dataset("ventes_ancien", _good_ventes_ancien(), data_dir=d)
        after_write = hd.signature(d)
        assert after_write != empty

        cpath = os.path.join(d, "ventes_ancien.csv")
        _good_ventes_ancien().to_csv(cpath, index=False)
        os.utime(cpath, (time.time() + 10, time.time() + 10))
        assert hd.signature(d) != after_write            # same rows, different source

        # a content change alone moves the key even within one mtime tick (size is in it)
        flipped = hd.signature(d)
        _good_ventes_ancien().head(1).to_csv(cpath, index=False)
        os.utime(cpath, (time.time() + 10, time.time() + 10))
        assert hd.signature(d) != flipped


def test_data_manager_reads_through_the_warehouse():
    """DataManager.read_frames() must go through the warehouse and hand back typed frames,
    identical whether they came from Parquet or from the CSV fallback."""
    import data_manager as dm_mod

    with tempfile.TemporaryDirectory() as d:
        dm = dm_mod.DataManager(data_dir=d)
        frames = {
            "sitadel": pd.DataFrame({
                "Date": pd.to_datetime(["2020-01-01", "2020-01-01"]),
                "Region": "France", "Department": "France",
                "Type": ["Logement Collectif", "Maison Individuelle Pure"],
                "Permis": [10, 20], "MisesEnChantier": [5, 6]}),
            "ventes_ancien": _good_ventes_ancien(),
            # every declared indicator column must be present (a missing one is the
            # upstream-rename symptom the contract exists to catch) — NaN is fine.
            "macro": pd.DataFrame({"Date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
                                   **{c: [float("nan")] * 2 for c in S.MACRO_VALUE_COLUMNS},
                                   "Prix_Ancien_Ensemble": [100.0, 101.0]}),
            "sales": pd.DataFrame({
                "Date": pd.to_datetime(["2020-01-01"]), "Region": "France",
                "Department": "France", "Product": ["Sécurité & Domotique"],
                "Sales_Units": [42]}),
        }
        for name, df in frames.items():                     # CSV first, then the Parquet
            df.to_csv(os.path.join(d, f"{name}.csv"), index=False)
        dm._persist_to_warehouse(frames)
        assert all(ok for ok, _ in dm.warehouse_status.values()), dm.warehouse_status

        assert dm.dataset_sources()["macro"] == "parquet"
        from_parquet = dm.read_frames()
        assert str(from_parquet[0]["Date"].dtype) == "datetime64[ns]"
        assert int(from_parquet[1]["Transactions"].sum()) == 131000
        assert from_parquet[4].empty and from_parquet[5].empty   # revenue / ecln absent

        # Same frames once the Parquet is gone: the CSV fallback must be equivalent.
        for name in frames:
            os.remove(hd.parquet_path(name, d))
        assert dm.dataset_sources()["macro"] == "csv"
        from_csv = dm.read_frames()
        for a, b in zip(from_parquet[:4], from_csv[:4]):
            pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True),
                                          check_dtype=False)


def test_data_manager_still_reads_without_the_optional_layer():
    """`fetch_new_sources.py` runs on pandas alone, without the optional data layer, so
    `import housing_data` fails there. DataManager must then read every dataset straight
    from CSV. (The three app surfaces DO require the SQL layer — this fallback covers the
    acquisition tooling, not them.)"""
    import data_manager as dm_mod

    with tempfile.TemporaryDirectory() as d:
        df = _good_ventes_ancien()
        df.to_csv(os.path.join(d, "ventes_ancien.csv"), index=False)
        hd.write_dataset("ventes_ancien", df, data_dir=d)   # a Parquet exists but is unusable

        saved = dm_mod.hd
        try:
            dm_mod.hd = None                                 # pandera/pyarrow/duckdb absent
            dm = dm_mod.DataManager(data_dir=d)
            assert dm.dataset_sources()["ventes_ancien"] == "csv"
            back = dm._read_dataset("ventes_ancien")
            # Dates are parsed, not left as strings — but only the Parquet path pins the
            # unit: pandas >= 3 reads CSV dates as datetime64[us] where the contract
            # coerces to [ns]. Downstream code is unit-agnostic, so assert the kind.
            assert pd.api.types.is_datetime64_any_dtype(back["Date"])
            assert int(back["Transactions"].sum()) == 131000
            assert dm._read_optional("ecln", ["Date"]).empty  # absent optional -> empty
            dm._persist_to_warehouse({"ventes_ancien": df})   # no-op, must not raise
            assert dm.warehouse_status == {}
            assert isinstance(dm.data_signature(), tuple)
        finally:
            dm_mod.hd = saved


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
