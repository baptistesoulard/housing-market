"""
Off-runtime acquisition of ALL the real source files in data_manual_input/. Run
`python fetch_new_sources.py` to refresh everything in one go; the Streamlit app itself
never hits the network (it only reads the CSVs this script maintains). Each builder is
failure-isolated: one API being down skips that file and the rest still refresh.

Sources (all open / official — full per-file details in data_manual_input/Data source.txt):
  * SIT@DEL2 (SDES) — logements autorisés / commencés, mensuel national CVS-CJO, via
    l'API DiDo (même backend que le jeu data.gouv ; CSV identique au téléchargement manuel).
  * IGEDD — ventes de logements anciens, classeur .xls national (URL directe cgedd.fr) ;
    la série dérivée data/ventes_ancien.csv est invalidée pour reconstruction au prochain
    démarrage de l'app.
  * Macro « socle » (6 séries) : confiance des ménages (BDM 001587668), taux du crédit
    habitat (ECB MIR M.FR.B.A2C.AM.R.A.2250.EUR.N), Euribor 3 mois (ECB FM), OAT 10 ans
    (ECB IRS), intentions d'achat de logement (BDM 001616794), chômage BIT (BDM 001688527).
  * Prix des logements anciens — indices Notaires-INSEE, France métropolitaine, base
    100 en moyenne annuelle 2015, série CVS, trimestriels (INSEE SDMX BDM) :
        Ensemble      idbank 010567059
        Appartements  idbank 010567057
        Maisons       idbank 010567061
  * Prix des logements NEUFS — indice INSEE (France, base 100 en 2015, CVS, trimestriel,
    idbank 010751595), même base que l'ancien pour comparer neuf/ancien.
  * Production de crédits à l'habitat (crédits nouveaux, Md€, mensuel) — ECB MIR, série
    M.FR.B.A2C.A.B.A.2250.EUR.N (data-api.ecb.europa.eu).
  * Demande de crédits à l'habitat (enquête BLS) — ECB SDMX, trimestriel.
  * Commercialisation des logements neufs (ECLN) — séries nationales trimestrielles
    CVS-CJO (SDES / data.gouv) : réservations (particuliers), mises en vente, annulations,
    encours, délai d'écoulement, prix au m² (ressource « ventes aux particuliers ») +
    réservations bailleurs sociaux / investisseurs institutionnels (ressource « ventes aux
    institutionnels / ventes en bloc »).
  * Rénovation / second œuvre — activité passée & prévue (INSEE conjoncture bâtiment).

Not fetchable here: ventes-*.csv (compilations manuelles de ventes société).
"""
import os
import re
import io
import csv
import ssl
import json
import time
import hashlib
import threading
import urllib.request
from datetime import datetime, timezone
import gzip
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import dvf_clean

CTX = ssl.create_default_context()
_ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_ROOT, "data_manual_input")
DATA_DIR = os.path.join(_ROOT, "data")
MANIFEST_PATH = os.path.join(DATA_DIR, "_manifest.json")

# --- Provenance manifest, filled as builders write. Thread-safe so builders can run in
# parallel (see refresh_all): every write records what changed, its last observation and a
# content hash, so freshness is inspectable without re-reading every CSV. ---
_MANIFEST = {}          # basename -> {status, changed, rows, last_obs, sha256, fetched_at}
_FAILURES = []          # [{"source": str, "error": str}]
_LOCK = threading.Lock()


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_url(url, accept="application/xml", *, tries=3, backoff=2.0, timeout=120):
    """HTTP GET with retry + exponential backoff. The INSEE/BCE/DiDo APIs return the odd
    transient 5xx / reset; a couple of retries turn those into a success instead of a
    skipped source. Raises the last error only if every attempt fails.

    `timeout` is the per-attempt socket timeout: keep it generous (120 s) for the usually-
    reliable SDMX/DiDo APIs, but lower it for a host that *intermittently hangs* (cgedd.fr —
    see build_igedd) so a dead attempt fails fast and a retry gets a fresh connection while
    the host is responsive, instead of burning the whole attempt on a stalled socket."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": accept})
    last = None
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=CTX).read()
        except Exception as e:                       # retry ANY transient network error
            last = e
            if attempt < tries - 1:
                time.sleep(backoff ** attempt)       # 1s, 2s, 4s, ...
    raise last


def _get(url, **kw):
    return _read_url(url, "application/xml", **kw)


def _write_if_changed(path, content, *, rows=None, last=None, label=None):
    """Atomic, hash-guarded write. `content` is str or bytes. The file is only rewritten
    when its bytes actually differ, so an unchanged source never bumps the mtime the app's
    load cache keys on (no needless Parquet rebuild, no noisy git diff). The write goes
    through a temp file + os.replace so a mid-write crash can't leave a truncated CSV.
    Records the outcome in the manifest and returns True iff the file was (re)written."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    old = None
    if os.path.exists(path):
        with open(path, "rb") as f:
            old = f.read()
    changed = old != data
    if changed:
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)                        # atomic swap
    base = os.path.basename(path)
    with _LOCK:
        _MANIFEST[base] = {
            "status": "ok", "changed": changed, "rows": rows, "last_obs": last,
            "sha256": hashlib.sha256(data).hexdigest()[:16], "fetched_at": _now_iso(),
        }
    # ASCII-only console output: the Windows default code page (cp1252) can't encode e.g.
    # '->' arrows, and a print crash here would wrongly mark a successful write as failed.
    extra = f" ({rows} pts, last={last})" if rows is not None else ""
    print(f"{label or base} -> {base} [{'MAJ' if changed else 'inchange'}]{extra}")
    return changed


def _record_failure(source, err):
    """Log a per-source failure into the manifest (the previous CSV stays in place)."""
    with _LOCK:
        _FAILURES.append({"source": source, "error": f"{err.__class__.__name__}: {err}"})
    print(f"  {source} -> SKIPPED ({err.__class__.__name__}: {err})")


def _period_to_date(p):
    """INSEE TIME_PERIOD -> first day of the period. Handles monthly ('2026-06'), quarterly
    ('2025-Q4' -> 2025-10-01) and annual ('2021' -> 2021-01-01)."""
    m = re.match(r"^(\d{4})-(\d{2})$", p)            # monthly
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(r"^(\d{4})-Q([1-4])$", p)           # quarterly
    if m:
        return pd.Timestamp(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)
    m = re.match(r"^(\d{4})$", p)                     # annual
    if m:
        return pd.Timestamp(int(m.group(1)), 1, 1)
    return pd.NaT


def _fetch_bdm(idbank):
    xml = _read_url("https://www.bdm.insee.fr/series/sdmx/data/SERIES_BDM/" + idbank).decode("utf-8", "replace")
    obs = re.findall(r'TIME_PERIOD="([^"]+)"\s+OBS_VALUE="([^"]+)"', xml)
    s = pd.Series({_period_to_date(p): float(v) for p, v in obs})
    return s.sort_index()


def _fetch_ecb(dataset, key):
    """Monthly ECB SDMX series (open API, no key) -> Series indexed by first-of-month.
    TIME_PERIOD is 'YYYY-MM'; values are returned as-is (caller handles unit scaling).
    Uses a CSV Accept header (the ECB honours Accept and would otherwise return XML)."""
    url = f"https://data-api.ecb.europa.eu/service/data/{dataset}/{key}?format=csvdata"
    raw = _read_url(url, "text/csv").decode("utf-8-sig", "replace")
    out = {}
    for r in csv.DictReader(io.StringIO(raw)):
        p = r["TIME_PERIOD"]
        out[pd.Timestamp(int(p[:4]), int(p[5:7]), 1)] = float(r["OBS_VALUE"])
    return pd.Series(out).sort_index()


def build_sitadel():
    """SIT@DEL2 monthly national series (logements autorisés / commencés) via the DiDo
    API — same backend as the data.gouv dataset documented in Data source.txt; /csv
    serves the latest millésime. The payload is identical to the manual download
    (';'-separated, ANNEE/MOIS/TYPE_LGT/NAT_SERIES/LOG_AUT/LOG_COM/...), so the header
    is sanity-checked before overwriting the file data_manager parses."""
    url = ("https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/"
           "datafiles/175486a6-76a3-4c6c-a34b-aeb96758910b/csv")
    raw = _get(url).decode("utf-8", "replace")
    header = raw.splitlines()[0] if raw else ""
    for col in ("ANNEE", "MOIS", "TYPE_LGT", "NAT_SERIES", "LOG_AUT", "LOG_COM"):
        if col not in header:
            raise ValueError(f"en-tête DiDo inattendu (colonne '{col}' absente) : {header!r}")
    path = os.path.join(OUT_DIR, "Donnees-mensuelles-nationales-Logements.csv")
    _write_if_changed(path, raw, rows=raw.count(chr(10)), label="sitadel")


def build_igedd():
    """IGEDD existing-home sales workbook — stable direct URL on cgedd.fr (the IGEDD
    page 'prix-immobilier-evolution-a-long-terme-a1048' links to it). Saved as-is; the
    derived data/ventes_ancien.csv is then deleted so data_manager.ensure_ventes_ancien
    rebuilds the monthly flows from the fresh workbook on the next app start (or via the
    in-app « Reconstruire » button).

    cgedd.fr (the legacy CGEDD domain, no gouv.fr mirror for this file) *intermittently
    hangs* from datacenter IPs — the recurring cause of red CI runs (fine on 08-03, stalled
    on 08-10 / 08-12). Since it works some minutes and not others, we fail each stalled
    attempt fast (45 s) and retry more times: better odds of catching a responsive moment,
    and a total hang wastes ~3 min instead of ~6. A persistent failure is still isolated to
    a ::warning:: by refresh_all — the previous workbook stays in place (it changes yearly)."""
    url = "https://www.cgedd.fr/nombre-vente-maison-appartement-ancien.xls"
    raw = _get(url, tries=5, timeout=45)
    if not raw.startswith(b"\xd0\xcf\x11\xe0"):     # OLE2 magic: it must be a real .xls
        raise ValueError("le fichier téléchargé n'est pas un classeur .xls (page d'erreur ?)")
    path = os.path.join(OUT_DIR, "nombre-vente-maison-appartement-ancien.xls")
    _write_if_changed(path, raw, rows=len(raw) // 1024, label="igedd")
    # No manual invalidation needed: the workbook is only (re)written when it actually
    # changed, so its mtime now leads data/ventes_ancien.csv — and DataManager.ensure_
    # ventes_ancien is mtime-aware, rebuilding the derived monthly series on the next app
    # start (or in CI, see refresh_ventes_ancien). Avoids committing a spurious deletion.


# The six "socle" macro series (the forecast model's predictors), each a single
# [Date, <column>] CSV. (fichier, colonne data_manager, source, code série) — kept as
# data so tests can check the filenames/columns stay aligned with data_manager.
MACRO_CORE_SERIES = [
    ("insee-confiance-menages.csv", "Insee_Confiance_Menages", "bdm", "001587668"),
    ("taux-credit-habitat.csv", "Credit_Logement_Taux_Interet", "ecb", "MIR/M.FR.B.A2C.AM.R.A.2250.EUR.N"),
    ("euribor-3-mois.csv", "Euribor_3M", "ecb", "FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"),
    ("oat-10-ans.csv", "OAT_10ans", "ecb", "IRS/M.FR.L.L40.CI.0000.EUR.N.Z"),
    ("intentions-achat-logement.csv", "Intentions_Achat_Logement", "bdm", "001616794"),
    ("taux-chomage-bit.csv", "Taux_Chomage_BIT", "bdm", "001688527"),
]


def build_macro_core():
    """The six first-wave macro CSVs (confiance, taux crédit, Euribor, OAT, intentions,
    chômage BIT) — historically downloaded by hand from the very same SDMX endpoints the
    other builders use. Each series is fetched independently so one outage only skips
    that file. Quarterly series (chômage) keep one row per quarter, first month of the
    quarter, exactly like the manual files."""
    for filename, column, kind, code in MACRO_CORE_SERIES:
        try:
            s = _fetch_bdm(code) if kind == "bdm" else _fetch_ecb(*code.split("/", 1))
            _write_single_series(s, column, filename, column)
        except Exception as e:
            _record_failure(column, e)


def build_prices():
    cols = {
        "Prix_Ancien_Ensemble": "010567059",
        "Prix_Ancien_Appartements": "010567057",
        "Prix_Ancien_Maisons": "010567061",
    }
    df = pd.DataFrame({c: _fetch_bdm(idb) for c, idb in cols.items()})
    df.index.name = "Date"
    df = df.reset_index().sort_values("Date")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError("indices prix ancien vides")
    path = os.path.join(OUT_DIR, "prix-immobilier-notaires-insee.csv")
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label="prix")


def build_neuf_price():
    """INSEE 'Indice des prix des logements neufs' (France, base 100 = moyenne annuelle
    2015, série CVS), trimestriel, idbank 010751595 — même base que les indices anciens,
    pour comparer neuf et ancien."""
    s = _fetch_bdm("010751595").rename("Prix_Neuf")
    df = s.reset_index().rename(columns={"index": "Date"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError("indice prix neuf vide")
    path = os.path.join(OUT_DIR, "prix-logements-neufs-insee.csv")
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label="neuf")


def build_credit_volume():
    """Production de crédits à l'habitat aux ménages (en Md€), mensuel, DÉCOMPOSÉE comme
    BPCE p.24 — ECB MIR (MFI Interest Rate statistics), achat de logement, France :
      * pure new loans (hors renégociations), série ...2250.EUR.**P** ;
      * renégociations seules,                série ...2250.EUR.**R**.
    Le total « new business » (...EUR.N) = P + R ; on le recalcule pour garder le rythme
    de production comparable au chiffre publié BPCE (~175 Md€). Les renégociations sont
    isolées car décorrélées des transactions/constructions (aucune activité second œuvre).
    """
    tot = _fetch_ecb("MIR", "M.FR.B.A2C.A.B.A.2250.EUR.N") / 1000.0   # M€ -> Md€ (2003+)
    pur = _fetch_ecb("MIR", "M.FR.B.A2C.A.B.A.2250.EUR.P") / 1000.0   # pure new loans (2019+)
    ren = _fetch_ecb("MIR", "M.FR.B.A2C.A.B.A.2250.EUR.R") / 1000.0   # renégociations (2019+)
    # Total = N (long history, 2003+, authoritative — matches BPCE's ~175 Md€ headline);
    # Pure + Renego decompose it from 2019 only (N ≈ P + R over the overlap).
    df = pd.DataFrame({"Production_Credits_Habitat": tot,
                       "Production_Credits_Pure": pur,
                       "Production_Credits_Renego": ren})
    df.index.name = "Date"
    df = df.reset_index().sort_values("Date")
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError("production de crédits vide")
    path = os.path.join(OUT_DIR, "production-credits-habitat.csv")
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label="credit")


def build_credit_demand_bls():
    """Enquête sur la distribution du crédit bancaire (Bank Lending Survey, BLS) — demande
    de crédits à l'habitat des ménages en France, en pourcentage net (net percentage of
    banks reporting an increase). Deux horizons (comme BPCE p.23, « perspectives à 3 mois ») :
      * réalisé sur les 3 derniers mois (TIME_HORIZON=B3) ;
      * attendu sur les 3 prochains mois (TIME_HORIZON=F3) — le « perspectives ».
    ECB SDMX dataset BLS, ménages (H) / achat de logement (H), item Z (demande globale),
    pourcentage net (FNET). Trimestriel, 2003-Q1→. """
    keys = {
        "Demande_Credit_Realisee": "Q.FR.ALL.Z.H.H.B3.ZZ.D.FNET",
        "Demande_Credit_Perspectives": "Q.FR.ALL.Z.H.H.F3.ZZ.D.FNET",
    }

    def _fetch_bls_q(key):
        url = f"https://data-api.ecb.europa.eu/service/data/BLS/{key}?format=csvdata"
        raw = _read_url(url, "text/csv").decode("utf-8-sig", "replace")
        out = {}
        for r in csv.DictReader(io.StringIO(raw)):
            y, q = r["TIME_PERIOD"].split("-Q")
            out[pd.Timestamp(int(y), (int(q) - 1) * 3 + 1, 1)] = float(r["OBS_VALUE"])
        return pd.Series(out).sort_index()

    df = pd.DataFrame({c: _fetch_bls_q(k) for c, k in keys.items()})
    df.index.name = "Date"
    df = df.reset_index().sort_values("Date")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError("demande de crédits (BLS) vide")
    path = os.path.join(OUT_DIR, "credit-demand-bls.csv")
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label="bls")


def build_ecln():
    # (2) ventes aux particuliers CVS-CJO ; (8) ventes aux institutionnels (ventes en
    # bloc) CVS-CJO — cette dernière ventile les réservations SOCIAL (bailleurs sociaux)
    # / NONSOCIAL (investisseurs institutionnels). Réservations « Particuliers » = fichier
    # (2) ; les trois catégories alimentent le graphique par acquéreur (cf. BPCE p.13).
    url_part = ("https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/"
                "datafiles/7e002311-3413-4046-9248-b6e761803fd0/csv")
    url_inst = ("https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/"
                "datafiles/174038f5-67ce-464f-b359-4c3c4034e77c/csv")
    rows = list(csv.DictReader(io.StringIO(_get(url_part).decode("utf-8", "replace")), delimiter=";"))
    rows_inst = list(csv.DictReader(io.StringIO(_get(url_inst).decode("utf-8", "replace")), delimiter=";"))

    def q_to_date(t):
        y, q = t.split("-T")
        return pd.Timestamp(int(y), (int(q) - 1) * 3 + 1, 1)

    def num(x):
        x = (x or "").strip().replace(",", ".")
        return float(x) if x else None

    recs = {}
    for r in rows:
        if r["NATURE_PROJET"] != "Toutes constructions":
            continue
        d = q_to_date(r["TRIMESTRE"])
        rec = recs.setdefault(d, {"Date": d})
        if r["TYPE_LGT"] == "Tous logements":
            rec["Reservations"] = num(r["RESA"])          # réservations des PARTICULIERS
            rec["MisesEnVente"] = num(r["MEV"])
            rec["Annulations"] = num(r["ANNUL"])
            rec["Encours"] = num(r["STOCK"])
            rec["DelaiEcoulement"] = num(r["DELAI_ECOUL"])
        if r["TYPE_LGT"] == "Collectif":
            rec["PrixM2_Collectif"] = num(r["PRIX_M2"])

    # ventes en bloc : réservations bailleurs sociaux / investisseurs institutionnels
    for r in rows_inst:
        d = q_to_date(r["TRIMESTRE"])
        rec = recs.setdefault(d, {"Date": d})
        rec["Resa_Sociaux"] = num(r.get("RESA_SOCIAL"))
        rec["Resa_Institutionnels"] = num(r.get("RESA_NONSOCIAL"))

    cols = ["Date", "Reservations", "MisesEnVente", "Annulations", "Encours",
            "DelaiEcoulement", "PrixM2_Collectif", "Resa_Sociaux", "Resa_Institutionnels"]
    df = pd.DataFrame(sorted(recs.values(), key=lambda x: x["Date"]))
    df = df.reindex(columns=cols)
    if df.empty:
        raise ValueError("commercialisation neuf (ECLN) vide")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, "ecln-commercialisation-neuf.csv")
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label="ecln")


def _write_single_series(series, column, filename, label):
    """Persist a single real series to a [Date, <column>] CSV in data_manual_input."""
    df = series.rename(column).reset_index()
    df.columns = ["Date", column]
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    if df.empty:
        raise ValueError(f"série vide ({column})")
    path = os.path.join(OUT_DIR, filename)
    _write_if_changed(path, df.to_csv(index=False), rows=len(df),
                      last=df["Date"].iloc[-1], label=label)


def build_renovation():
    """Renovation-pillar sources — the SECOND-ŒUVRE / renovation demand that new construction
    and existing-home transactions don't capture (a large share of Somfy-type product demand
    comes from the installed stock, not moves). Two real, national, monthly INSEE series from
    the building-industry business survey (Enquête mensuelle de conjoncture dans l'industrie
    du bâtiment), CVS, both verified on bdm.insee.fr:

      * Reno_Activite_Batiment : "Tendance de l'activité passée — Second œuvre" (opinion
        balance, idbank 001586954) — the current state of second-œuvre demand.
      * Reno_Activite_Prevue   : "Tendance de l'activité prévue — Second œuvre" (opinion
        balance, idbank 001586886) — a LEADING signal (planned activity).

    Each source is fetched independently so a single failure only skips that series (the app
    then leaves the macro column NaN and degrades gracefully).
    """
    # (1) Second-œuvre PAST activity (CVS, monthly 1975+). idbank verified on bdm.insee.fr.
    try:
        s_act = _fetch_bdm("001586954").rename("Reno_Activite_Batiment")
        _write_single_series(s_act, "Reno_Activite_Batiment",
                             "reno-activite-batiment.csv", "reno-activite")
    except Exception as e:
        _record_failure("reno-activite", e)

    # (2) Second-œuvre PLANNED activity (CVS, monthly 1975+) — leading indicator.
    try:
        s_prev = _fetch_bdm("001586886").rename("Reno_Activite_Prevue")
        _write_single_series(s_prev, "Reno_Activite_Prevue",
                             "reno-activite-prevue.csv", "reno-prevue")
    except Exception as e:
        _record_failure("reno-prevue", e)

    # Possible future enrichment (volume): MaPrimeRénov' / éco-PTZ (ANAH, data.gouv/DiDo).
    # A clean national monthly time series is not straightforward via API — deferred.


# Every real source file, one builder each. Failure-isolated: an API being down skips
# that source (the app keeps serving the previous CSV) and the rest refresh.
# --- DVF : prix au m2 par departement (fenetre glissante officielle) -----------------
GEO_DVF = "https://files.data.gouv.fr/geo-dvf/latest/csv"


def _dvf_departements():
    """Les 97 departements couverts par DVF, dans l'ordre des codes INSEE.

    Les quatre absents (Alsace-Moselle, sous regime du Livre foncier, et Mayotte) sont
    exclus ici plutot que decouverts par des 404 en boucle : leur non-couverture est un
    fait etabli, pas un incident reseau. Voir dvf_clean.DEPARTEMENTS_SANS_DVF.
    """
    codes = [f"{i:02d}" for i in range(1, 20)] + ["2A", "2B"]         + [f"{i:02d}" for i in range(21, 96)] + ["971", "972", "973", "974", "976"]
    return [c for c in codes if c not in dvf_clean.DEPARTEMENTS_SANS_DVF]


def _dvf_annees():
    """Les annees reellement publiees par le millesime courant, lues sur la source.

    Ne pas coder la fenetre en dur : elle glisse a chaque publication semestrielle, et
    une annee ecrite en dur deviendrait un 404 silencieux six mois plus tard.
    """
    html = _read_url(f"{GEO_DVF}/", "text/html").decode("utf-8", "replace")
    return sorted(set(re.findall(r'href="[^"]*/([0-9]{4})/"', html)))


def build_dvf():
    """Agrege DVF en medianes trimestrielles par departement, sur la fenetre officielle.

    485 fichiers (97 departements x 5 annees, ~500 Mo) telecharges puis JETES : seul
    l'agregat, quelques centaines de Ko, est ecrit. Ne jamais commiter les fichiers bruts.

    Le nettoyage vit dans `dvf_clean` (filtre documente, teste sur cas fabriques) ; ce
    builder ne fait que de la collecte. L'historique anterieur a la fenetre glissante est
    produit separement par `dvf_backfill.py` et commite — voir son en-tete.
    """
    annees = _dvf_annees()
    deps = _dvf_departements()
    morceaux = []

    def un_fichier(args):
        annee, dep = args
        url = f"{GEO_DVF}/{annee}/departements/{dep}.csv.gz"
        try:
            brut = gzip.decompress(_read_url(url, "text/csv"))
        except Exception as e:                       # un departement absent une annee
            print(f"dvf {annee}/{dep} indisponible ({e})")
            return None
        df = pd.read_csv(io.BytesIO(brut), dtype=str, low_memory=False,
                         usecols=["id_mutation", "date_mutation", "nature_mutation",
                                  "valeur_fonciere", "code_departement", "type_local",
                                  "surface_reelle_bati"])
        return dvf_clean.clean(dvf_clean.from_geo_dvf(df))

    taches = [(a, d) for a in annees for d in deps]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for propre in ex.map(un_fichier, taches):
            if propre is not None and not propre.empty:
                morceaux.append(propre)

    if not morceaux:
        raise ValueError("DVF : aucune vente retenue")
    agg = dvf_clean.aggregate(pd.concat(morceaux, ignore_index=True))
    agg["Date"] = agg["Date"].dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, "dvf-recent.csv")
    _write_if_changed(path, agg.to_csv(index=False), rows=len(agg),
                      last=agg["Date"].iloc[-1], label="dvf")


BUILDERS = [
    build_sitadel,          # SIT@DEL2 (SDES, API DiDo)
    build_igedd,            # ventes anciennes IGEDD (.xls cgedd.fr)
    build_macro_core,       # confiance, taux crédit, Euribor, OAT, intentions, chômage
    build_prices,           # indices Notaires-INSEE (ancien)
    build_neuf_price,       # indice prix logements neufs
    build_credit_volume,    # production de crédits à l'habitat (MIR)
    build_credit_demand_bls,  # demande de crédits (BLS)
    build_ecln,             # commercialisation des logements neufs
    build_renovation,       # activité second œuvre passée / prévue
]


def _write_manifest():
    """Persist the provenance manifest (data/_manifest.json) — per file: changed?, last
    observation, short content hash, fetch timestamp; plus any per-source failures. Lets
    the app show data freshness without re-reading every CSV, and flags a stale source."""
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest = {"generated_at": _now_iso(),
                "files": dict(sorted(_MANIFEST.items())),
                "failures": _FAILURES}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"manifeste -> {MANIFEST_PATH}")


def refresh_ventes_ancien():
    """Rebuild data/ventes_ancien.csv from the freshly fetched IGEDD workbook. The app does
    this lazily on start (ensure_ventes_ancien is mtime-aware), but CI has no app run, so it
    calls this to keep the committed derived series consistent with the committed .xls.
    Imported lazily so a plain `fetch_new_sources` run needs no pandas-heavy data_manager."""
    try:
        from data_manager import DataManager
        df = DataManager.build_ventes_ancien_from_igedd()
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(os.path.join(DATA_DIR, "ventes_ancien.csv"), index=False, encoding="utf-8")
        print(f"ventes_ancien -> reconstruit ({len(df)} mois)")
    except Exception as e:
        _record_failure("ventes_ancien (rebuild)", e)


def _emit_ci_annotations(total_failure):
    """Under GitHub Actions, turn per-source failures into workflow annotations so each skip
    shows up in the run's 'Annotations' column (and the notification email) WITHOUT the whole
    job going red on a single flaky or IP-blocked API. A total wipe-out is escalated to an
    error. No-op off CI (detected via the GITHUB_ACTIONS env var GitHub always sets)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    level = "error" if total_failure else "warning"
    for f in _FAILURES:                              # ::warning::/::error:: -> annotations
        print(f"::{level} title=Source non rafraichie::{f['source']} - {f['error']}")
    if total_failure:
        print("::error title=Refresh data sources::Toutes les sources ont echoue "
              "(panne reseau ou regression) - aucun fichier ecrit.")


def refresh_all(parallel=True, max_workers=4, rebuild_derived=True):
    """Run every builder (failure-isolated), rebuild the derived IGEDD series, and write the
    manifest. Builders are independent network I/O, so parallel execution turns the wall
    time from the sum into the max; pass parallel=False to debug one source at a time.

    Returns True unless it was a TOTAL failure (no file written at all). A partial failure —
    the common case: one API timing out or blocking the CI runner's IP — returns True so the
    caller exits 0 and CI still commits the sources that DID refresh."""
    def _run(b):
        try:
            b()
        except Exception as e:
            _record_failure(b.__name__, e)

    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(_run, BUILDERS))
    else:
        for b in BUILDERS:
            _run(b)

    if rebuild_derived:
        refresh_ventes_ancien()
    _write_manifest()

    changed = sorted(f for f, m in _MANIFEST.items() if m.get("changed"))
    total_failure = not _MANIFEST and bool(_FAILURES)   # nothing written AND something failed
    _emit_ci_annotations(total_failure)
    if _FAILURES:
        print(f"\nTerminé avec échec(s) : {', '.join(x['source'] for x in _FAILURES)} "
              f"— les CSV précédents restent en place.")
    print(f"Sources modifiées : {len(changed)}/{len(_MANIFEST)}"
          + (f" ({', '.join(changed)})" if changed else " — rien de neuf."))
    return not total_failure


if __name__ == "__main__":
    import sys
    ok = refresh_all(parallel="--sequential" not in sys.argv)
    # Exit non-zero ONLY on a total failure (every source down). A single flaky/blocked API
    # must not fail the run — its skip is already surfaced as a manifest failure + CI warning.
    sys.exit(0 if ok else 1)
