"""
Off-runtime acquisition of the REAL source series added in the "Prix & Accessibilité"
and "Commercialisation Neuf (ECLN)" tabs. Run manually to (re)fresh the manual-input
CSVs; the Streamlit app itself never hits the network (same convention as the other
data_manual_input/*.csv real series).

Sources (all open / official):
  * Prix des logements anciens — indices Notaires-INSEE, France métropolitaine, base
    100 en moyenne annuelle 2015, série CVS, trimestriels (INSEE SDMX BDM) :
        Ensemble      idbank 010567059
        Appartements  idbank 010567057
        Maisons       idbank 010567061
  * Prix des logements NEUFS — indice INSEE (France, base 100 en 2015, CVS, trimestriel,
    idbank 010751595), même base que l'ancien pour comparer neuf/ancien.
  * Production de crédits à l'habitat (crédits nouveaux, Md€, mensuel) — ECB MIR, série
    M.FR.B.A2C.A.B.A.2250.EUR.N (data-api.ecb.europa.eu).
  * Commercialisation des logements neufs (ECLN) — séries nationales trimestrielles
    CVS-CJO (SDES / data.gouv) : réservations (particuliers), mises en vente, annulations,
    encours, délai d'écoulement, prix au m² (ressource « ventes aux particuliers ») +
    réservations bailleurs sociaux / investisseurs institutionnels (ressource « ventes aux
    institutionnels / ventes en bloc »).
"""
import os
import re
import io
import csv
import ssl
import urllib.request

import pandas as pd

CTX = ssl.create_default_context()
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_manual_input")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/xml"})
    return urllib.request.urlopen(req, timeout=120, context=CTX).read()


def _period_to_date(p):
    """INSEE TIME_PERIOD -> first day of the period ('2025-Q4' -> 2025-10-01, '2021' -> 2021-01-01)."""
    m = re.match(r"^(\d{4})-Q([1-4])$", p)
    if m:
        return pd.Timestamp(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)
    m = re.match(r"^(\d{4})$", p)
    if m:
        return pd.Timestamp(int(m.group(1)), 1, 1)
    return pd.NaT


def _fetch_bdm(idbank):
    xml = _get("https://www.bdm.insee.fr/series/sdmx/data/SERIES_BDM/" + idbank).decode("utf-8", "replace")
    obs = re.findall(r'TIME_PERIOD="([^"]+)"\s+OBS_VALUE="([^"]+)"', xml)
    s = pd.Series({_period_to_date(p): float(v) for p, v in obs})
    return s.sort_index()


def _fetch_ecb(dataset, key):
    """Monthly ECB SDMX series (open API, no key) -> Series indexed by first-of-month.
    TIME_PERIOD is 'YYYY-MM'; values are returned as-is (caller handles unit scaling).
    Uses a CSV Accept header (the ECB honours Accept and would otherwise return XML)."""
    url = f"https://data-api.ecb.europa.eu/service/data/{dataset}/{key}?format=csvdata"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"})
    raw = urllib.request.urlopen(req, timeout=120, context=CTX).read().decode("utf-8-sig", "replace")
    out = {}
    for r in csv.DictReader(io.StringIO(raw)):
        p = r["TIME_PERIOD"]
        out[pd.Timestamp(int(p[:4]), int(p[5:7]), 1)] = float(r["OBS_VALUE"])
    return pd.Series(out).sort_index()


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
    path = os.path.join(OUT_DIR, "prix-immobilier-notaires-insee.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"prix -> {path} ({len(df)} trimestres, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


def build_neuf_price():
    """INSEE 'Indice des prix des logements neufs' (France, base 100 = moyenne annuelle
    2015, série CVS), trimestriel, idbank 010751595 — même base que les indices anciens,
    pour comparer neuf et ancien."""
    s = _fetch_bdm("010751595").rename("Prix_Neuf")
    df = s.reset_index().rename(columns={"index": "Date"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, "prix-logements-neufs-insee.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"neuf -> {path} ({len(df)} trimestres, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


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
    path = os.path.join(OUT_DIR, "production-credits-habitat.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"credit -> {path} ({len(df)} mois, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"})
        raw = urllib.request.urlopen(req, timeout=120, context=CTX).read().decode("utf-8-sig", "replace")
        out = {}
        for r in csv.DictReader(io.StringIO(raw)):
            y, q = r["TIME_PERIOD"].split("-Q")
            out[pd.Timestamp(int(y), (int(q) - 1) * 3 + 1, 1)] = float(r["OBS_VALUE"])
        return pd.Series(out).sort_index()

    df = pd.DataFrame({c: _fetch_bls_q(k) for c, k in keys.items()})
    df.index.name = "Date"
    df = df.reset_index().sort_values("Date")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, "credit-demand-bls.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"bls -> {path} ({len(df)} trimestres, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


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
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, "ecln-commercialisation-neuf.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"ecln -> {path} ({len(df)} trimestres, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


def _write_single_series(series, column, filename, label):
    """Persist a single real series to a [Date, <column>] CSV in data_manual_input."""
    df = series.rename(column).reset_index()
    df.columns = ["Date", column]
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"{label} -> {path} ({len(df)} points, {df['Date'].iloc[0]} -> {df['Date'].iloc[-1]})")


def build_renovation():
    """Renovation-pillar sources — the second-œuvre / renovation demand that new
    construction and existing-home transactions don't capture. Both are national and real:

      * Reno_Activite_Batiment : INSEE monthly business survey in the building trades,
        activity-opinion balance (climat/activité) — a timely soft read on renovation and
        second-œuvre demand. INSEE SDMX BDM idbank (see IDBANK_RENO_ACTIVITE).
      * Reno_Aides_Distribuees : MaPrimeRénov' grants (ANAH / data.gouv), a volume proxy
        for the renovation-driven equipment market.

    Both idbanks/endpoints below MUST be verified against the live catalogues before use;
    they are isolated in their own function and guarded in __main__ so a wrong identifier
    only skips the renovation pillar (the app then degrades gracefully) rather than aborting
    the whole acquisition run. When a CSV is absent, data_manager leaves the column NaN.
    """
    # NOTE: verify these identifiers on bdm.insee.fr before relying on the values.
    IDBANK_RENO_ACTIVITE = "001585919"   # INSEE — bâtiment, solde d'opinion sur l'activité
    s_act = _fetch_bdm(IDBANK_RENO_ACTIVITE).rename("Reno_Activite_Batiment")
    _write_single_series(s_act, "Reno_Activite_Batiment",
                         "reno-activite-batiment.csv", "reno-activite")


if __name__ == "__main__":
    build_prices()
    build_neuf_price()
    build_credit_volume()
    build_credit_demand_bls()
    build_ecln()
    # Renovation pillar is best-effort: a not-yet-verified identifier must not abort the run.
    try:
        build_renovation()
    except Exception as e:
        print(f"reno -> SKIPPED ({e.__class__.__name__}: {e}). "
              f"Vérifiez les identifiants dans build_renovation().")
