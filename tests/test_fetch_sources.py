"""Alignment tests for fetch_new_sources (no network access).

Guards the contract between the acquisition script and data_manager: every macro-core
series the script writes must land in the exact file and column data_manager reads.
A drift here would silently leave a chart NaN, so it is locked by tests.
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import data_manager as dmod
import fetch_new_sources as fns


def test_macro_core_files_match_data_manager_paths():
    expected = {
        "Insee_Confiance_Menages": dmod.INSEE_CONFIANCE_CSV,
        "Credit_Logement_Taux_Interet": dmod.TAUX_CREDIT_CSV,
        "Euribor_3M": dmod.EURIBOR_3M_CSV,
        "OAT_10ans": dmod.OAT_10ANS_CSV,
        "Intentions_Achat_Logement": dmod.INTENTIONS_LOGEMENT_CSV,
        "Taux_Chomage_BIT": dmod.CHOMAGE_BIT_CSV,
    }
    produced = {col: fname for fname, col, _kind, _code in fns.MACRO_CORE_SERIES}
    assert set(produced) == set(expected)
    for col, path in expected.items():
        assert produced[col] == os.path.basename(path), (
            f"{col}: le script écrit '{produced[col]}' mais data_manager lit "
            f"'{os.path.basename(path)}'")


def test_macro_core_columns_are_consumed_by_data_manager():
    consumed = {col for _path, col in dmod._MACRO_REQUIRED + dmod._MACRO_OPTIONAL}
    for _fname, col, _kind, _code in fns.MACRO_CORE_SERIES:
        assert col in consumed, f"colonne '{col}' produite mais jamais lue par data_manager"


def test_macro_core_series_codes_are_wellformed():
    for _fname, _col, kind, code in fns.MACRO_CORE_SERIES:
        assert kind in ("bdm", "ecb")
        if kind == "bdm":
            assert code.isdigit() and len(code) == 9, f"idbank BDM invalide : {code!r}"
        else:
            dataset, key = code.split("/", 1)
            assert dataset in ("MIR", "FM", "IRS") and key, f"clé ECB invalide : {code!r}"


def test_write_if_changed_is_hash_guarded_and_atomic():
    """An identical payload must NOT rewrite the file (mtime preserved -> app cache kept);
    a different payload rewrites atomically, leaving no .tmp behind."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "x.csv")

    assert fns._write_if_changed(p, "a,b\n1,2\n") is True          # first write
    mtime = os.path.getmtime(p)
    time.sleep(0.02)
    assert fns._write_if_changed(p, "a,b\n1,2\n") is False         # identical -> skip
    assert os.path.getmtime(p) == mtime, "un contenu identique ne doit pas toucher le mtime"
    assert fns._write_if_changed(p, "a,b\n3,4\n") is True          # changed -> rewrite
    assert not os.path.exists(p + ".tmp"), "le fichier temporaire ne doit pas subsister"
    assert fns._MANIFEST["x.csv"]["status"] == "ok"                # outcome recorded


def test_write_if_changed_handles_bytes():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "b.bin")
    assert fns._write_if_changed(p, b"\xd0\xcf\x11\xe0") is True
    assert fns._write_if_changed(p, b"\xd0\xcf\x11\xe0") is False
    with open(p, "rb") as f:
        assert f.read() == b"\xd0\xcf\x11\xe0"


def test_read_url_retries_then_succeeds(monkeypatch):
    """A couple of transient failures must be retried, not fatal (backoff neutralised)."""
    calls = {"n": 0}

    def flaky(_req, timeout=None, context=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("connection reset")

        class _Resp:
            def read(self):
                return b"OK"
        return _Resp()

    monkeypatch.setattr(fns.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(fns.time, "sleep", lambda *_a, **_k: None)
    assert fns._read_url("https://example.test", tries=3) == b"OK"
    assert calls["n"] == 3


def test_builders_registry_covers_every_source():
    """The parallel runner iterates BUILDERS — it must list all nine acquisition builders."""
    names = {b.__name__ for b in fns.BUILDERS}
    assert names == {
        "build_sitadel", "build_igedd", "build_macro_core", "build_prices",
        "build_neuf_price", "build_credit_volume", "build_credit_demand_bls",
        "build_ecln", "build_renovation",
    }
