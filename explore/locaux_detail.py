"""Exploration ponctuelle (branche explore/**, jamais fusionnée) : le fichier détaillé des
permis créant des locaux permet-il de séparer enseignement, santé, action sociale… dans les
équipements publics ? On lit l'en-tête, puis la répartition des surfaces de service public
par « type de service public », année par année."""
import json
import re
import sys
import urllib.request

import pandas as pd

UA = {"User-Agent": "barometre-logement exploration"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def candidats():
    """(titre, url csv) des fichiers « locaux » : DiDo d'abord, data.gouv en repli."""
    out = []
    try:
        ds = json.loads(get("https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/"
                            "datasets/6513f0189d7d312c80ec5b5b"))
        print("DiDo, clés du jeu :", sorted(ds)[:30])
        for f in ds.get("datafiles", []):
            print("  DiDo datafile :", f.get("rid"), "|", f.get("title"))
            if re.search(r"local|locaux", f.get("title", ""), re.I):
                out.append((f["title"], "https://data.statistiques.developpement-durable.gouv.fr/"
                            f"dido/api/v1/datafiles/{f['rid']}/csv"))
    except Exception as e:  # noqa: BLE001
        print("DiDo indisponible :", e)
    try:
        dg = json.loads(get("https://www.data.gouv.fr/api/1/datasets/689c42fa521ccf80ce954f83/"))
        for r in dg.get("resources", []):
            print("  data.gouv :", r.get("format"), "|", r.get("title"), "|", r.get("url"))
            if re.search(r"local|locaux", r.get("title", ""), re.I) and r.get("format") == "csv":
                out.append((r["title"], r["url"]))
    except Exception as e:  # noqa: BLE001
        print("data.gouv indisponible :", e)
    return out


def main():
    cands = candidats()
    if not cands:
        sys.exit("aucun fichier « locaux » trouvé")
    titre, url = cands[0]
    print("\n=== Fichier retenu :", titre, url)
    raw = get(url, binary=True)
    print(f"taille : {len(raw) / 1e6:.0f} Mo")
    open("locaux.csv", "wb").write(raw)
    sep = ";" if raw[:2000].count(b";") > raw[:2000].count(b",") else ","
    head = pd.read_csv("locaux.csv", sep=sep, nrows=5, dtype=str)
    print("\n=== Colonnes (", len(head.columns), ") ===")
    for c in head.columns:
        print("  ", c, "|", head[c].iloc[0])
    cols = list(head.columns)
    pick = lambda pat: [c for c in cols if re.search(pat, c, re.I)]  # noqa: E731
    c_type = pick(r"SERVICE_PUB")
    c_surf = pick(r"SURF.*CREE|CREE.*SURF|SDP")
    c_date = pick(r"DATE_REELLE_AUTORISATION|DATE.*AUTOR")
    c_doc = pick(r"DATE_REELLE_DOC|DATE.*OUVERT|DATE.*DOC")
    c_detail = pick(r"ENSEIGN|SANTE|SPORT|SPECTACLE|CULTE|ADMIN|SOUS_DEST|SSDEST")
    print("\ntype service public :", c_type)
    print("surfaces créées :", c_surf)
    print("dates :", c_date, c_doc)
    print("colonnes de sous-destination détaillée :", c_detail)
    use = sorted(set(c_type + c_surf + c_date + c_doc + c_detail))
    df = pd.read_csv("locaux.csv", sep=sep, dtype=str, usecols=use)
    print("lignes :", len(df))
    for c in c_surf + c_detail:
        if c not in c_type:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if c_date:
        df["annee"] = df[c_date[0]].str[:4]
    if c_type:
        t = c_type[0]
        print("\n=== Codes de", t, "(toutes lignes) ===")
        print(df[t].value_counts(dropna=False).head(20).to_string())
        pub = [c for c in c_surf if re.search(r"PUB", c, re.I)]
        print("surface « service public » :", pub)
        if pub and c_date:
            p = pub[0]
            sub = df[df[p] > 0]
            print(f"\npermis avec {p} > 0 : {len(sub)}")
            tab = sub.pivot_table(index="annee", columns=t, values=p, aggfunc="sum",
                                  fill_value=0, dropna=False)
            print("\n=== m² de service public autorisés, par année et type (milliers) ===")
            print((tab / 1000).round(0).to_string())
            nb = sub.pivot_table(index="annee", columns=t, values=p, aggfunc="count",
                                 fill_value=0, dropna=False)
            print("\n=== nombre de permis, par année et type ===")
            print(nb.to_string())
            manquant = sub[t].isna() | (sub[t].astype(str).str.strip() == "")
            print("\npart des m² sans type, par année :")
            print((sub[manquant].groupby("annee")[p].sum()
                   / sub.groupby("annee")[p].sum() * 100).round(1).to_string())
    for c in c_detail:
        if c_date and pd.api.types.is_numeric_dtype(df[c]):
            print(f"\n=== {c} par année (milliers de m²) ===")
            print((df.groupby("annee")[c].sum() / 1000).round(0).to_string())


main()
