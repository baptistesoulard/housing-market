"""Alignment tests for fetch_new_sources (no network access).

Guards the contract between the acquisition script and data_manager: every macro-core
series the script writes must land in the exact file and column data_manager reads.
A drift here would silently leave a chart NaN, so it is locked by tests.
"""
import os
import sys

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
