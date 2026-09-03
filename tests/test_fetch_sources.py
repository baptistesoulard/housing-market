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

import pytest

import data_manager as dmod
import fetch_new_sources as fns


class _Compteur:
    """Compte les téléchargements tentés. Une sentinelle qui LÈVE ne conviendrait pas :
    `build_dvf` attrape toute exception par fichier — un département peut légitimement
    manquer une année — donc l'exception serait avalée et ne prouverait rien."""

    def __init__(self):
        self.appels = 0

    def __call__(self, *_a, **_k):
        self.appels += 1
        raise OSError("reseau coupe pendant le test")


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
    """The parallel runner iterates BUILDERS — it must list all ten acquisition builders.

    `build_dvf` joined on 2026-09-03. It had been left out because DVF is republished
    twice a year and a weekly ~500 MB download would be absurd — with the side effect
    that it never ran automatically at all. It is now guarded by a publication-date probe
    (see `_dvf_publication`), which is what makes it cheap enough to belong here."""
    names = {b.__name__ for b in fns.BUILDERS}
    assert names == {
        "build_sitadel", "build_dvf", "build_igedd", "build_macro_core", "build_prices",
        "build_neuf_price", "build_credit_volume", "build_credit_demand_bls",
        "build_ecln", "build_renovation",
    }


# --- La garde de publication de DVF ----------------------------------------------------
# C'est elle qui décide si le job hebdomadaire télécharge un demi-giga ou rend la main en
# deux secondes. Les deux sens sont testés : sauter quand rien n'a bougé, ET redescendre
# le corpus dès qu'on n'est pas SÛR du contraire.

def _dvf_sans_reseau(monkeypatch, publiee, *, stamp, tmpdir):
    """Neutralise le réseau : années/départements figés, `Last-Modified` contrôlé."""
    monkeypatch.setattr(fns, "_dvf_annees", lambda: ["2024", "2025"])
    monkeypatch.setattr(fns, "_dvf_departements", lambda: ["01", "02"])
    monkeypatch.setattr(fns, "_last_modified", lambda _url, **_kw: publiee)
    monkeypatch.setattr(fns, "OUT_DIR", tmpdir)
    monkeypatch.setattr(fns, "DVF_STAMP", os.path.join(tmpdir, "dvf-recent.lastmod.txt"))
    open(os.path.join(tmpdir, "dvf-recent.csv"), "w").close()   # l'agrégat existe déjà
    if stamp is not None:
        with open(os.path.join(tmpdir, "dvf-recent.lastmod.txt"), "w") as f:
            f.write(stamp + "\n")


def test_dvf_saute_le_telechargement_quand_la_source_n_a_pas_bouge(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _dvf_sans_reseau(monkeypatch, "Mon, 18 May 2026 13:14:11 GMT",
                         stamp="2026-05-18T13:14:11Z", tmpdir=tmp)
        reseau = _Compteur()
        monkeypatch.setattr(fns, "_read_url", reseau)
        fns.build_dvf()
        assert reseau.appels == 0, "la garde a laisse passer un telechargement inutile"


def test_dvf_retelecharge_quand_la_source_a_ete_republiee(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        _dvf_sans_reseau(monkeypatch, "Tue, 03 Nov 2026 08:00:00 GMT",
                         stamp="2026-05-18T13:14:11Z", tmpdir=tmp)
        reseau = _Compteur()
        monkeypatch.setattr(fns, "_read_url", reseau)
        with pytest.raises(ValueError):          # le reseau est coupe : aucune vente
            fns.build_dvf()
        assert reseau.appels > 0, "une republication doit relancer le telechargement"


def test_dvf_retelecharge_quand_la_date_de_publication_est_inconnue(monkeypatch):
    """`Last-Modified` absent = « je ne sais pas », donc on descend. Ne jamais inverser :
    sauter par defaut ferait rater une publication en silence, deux fois par an."""
    with tempfile.TemporaryDirectory() as tmp:
        _dvf_sans_reseau(monkeypatch, None, stamp="2026-05-18T13:14:11Z", tmpdir=tmp)
        reseau = _Compteur()
        monkeypatch.setattr(fns, "_read_url", reseau)
        with pytest.raises(ValueError):
            fns.build_dvf()
        assert reseau.appels > 0, "sans date de publication, on doit retelecharger"


def test_les_dates_http_sont_comparees_en_chronologie_pas_en_texte(monkeypatch):
    """« Mon, 18 May 2026 » est APRÈS « Tue, 02 Jun 2025 » dans l'ordre lexicographique,
    et avant dans l'ordre du temps. Trier ces en-têtes comme du texte ferait manquer une
    republication — le défaut ne se verrait que le jour où elle arrive."""
    entetes = iter(["Tue, 02 Jun 2025 10:00:00 GMT", "Mon, 18 May 2026 13:14:11 GMT"])
    monkeypatch.setattr(fns, "_last_modified", lambda _url, **_kw: next(entetes))
    assert fns._dvf_publication(["2024", "2025"], ["01"]) == "2026-05-18T13:14:11Z"
