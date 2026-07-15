"""
Contracts + warehouse round-trip tests for the housing_data layer.

Runs standalone (`python tests/test_housing_data.py`) — no pytest required — and is also
pytest-compatible (test_* functions). It writes Parquet into a throwaway temp dir, so it
never touches the app's data/ folder.
"""
import os
import sys
import tempfile

import pandas as pd

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
    expected = {"sitadel", "ventes_ancien", "macro", "sales", "revenue", "ecln", "company_sales"}
    assert set(S.SCHEMAS) == expected


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
