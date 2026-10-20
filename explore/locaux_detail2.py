"""Suite : le dictionnaire des codes, et la rupture de 2026 mois par mois."""
import io
import urllib.request

import pandas as pd

UA = {"User-Agent": "barometre-logement exploration"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


dico = get("https://data.statistiques.developpement-durable.gouv.fr/dido/api/files/"
           "38ca96c1-c8af-42db-bba1-13cd4bc713f3")
open("dico.xls", "wb").write(dico)
try:
    feuilles = pd.read_excel(io.BytesIO(dico), sheet_name=None, header=None)
except Exception as e:  # noqa: BLE001
    feuilles = {}
    print("lecture xls impossible :", e)
for nom, f in feuilles.items():
    f = f.fillna("").astype(str)
    print(f"\n=== feuille {nom} : {len(f)} lignes ===")
    print("variables :", ", ".join(v for v in f.iloc[:, 0].tolist() if v))
    for i in range(len(f)):
        ligne = " | ".join(v for v in f.iloc[i].tolist() if v)
        if any(k in ligne.upper() for k in ("SERV", "ENSEIGN", "SANT", "SPORT", "CULTURE")):
            print(">>", ligne)

raw = get("https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/"
          "f8f0700f-806c-40a7-83b1-f21cf507e7c4/csv")
open("locaux.csv", "wb").write(raw)
df = pd.read_csv("locaux.csv", sep=";", dtype=str,
                 usecols=["DPC_AUT", "DATE_REELLE_AUTORISATION", "TYPE_SERVICE_PUBLIC",
                          "SURF_PUB_CREEE", "DESTINATION_PRINCIPALE", "DPC_DOC", "DATE_REELLE_DOC"])
df["SURF_PUB_CREEE"] = pd.to_numeric(df["SURF_PUB_CREEE"], errors="coerce")
pub = df[df["SURF_PUB_CREEE"] > 0]
print("\n=== m² publics autorisés par MOIS DE PRISE EN COMPTE (DPC_AUT), 2024-2026, milliers ===")
t = pub[pub["DPC_AUT"] >= "2024-01"].pivot_table(index="DPC_AUT", columns="TYPE_SERVICE_PUBLIC",
                                                  values="SURF_PUB_CREEE", aggfunc="sum", fill_value=0)
print((t / 1000).round(0).to_string())
print("\n=== part du code 7 dans les m² publics, par mois de prise en compte ===")
print((t.get("7", 0) / t.sum(axis=1) * 100).round(0).to_string())
print("\n=== DESTINATION_PRINCIPALE (toutes lignes) ===")
print(df["DESTINATION_PRINCIPALE"].value_counts(dropna=False).to_string())
print("\n=== m² publics commencés par année de DOC (DATE_REELLE_DOC), milliers ===")
pub2 = pub.dropna(subset=["DATE_REELLE_DOC"]).copy()
pub2["a"] = pub2["DATE_REELLE_DOC"].str[:4]
print((pub2.pivot_table(index="a", columns="TYPE_SERVICE_PUBLIC", values="SURF_PUB_CREEE",
                        aggfunc="sum", fill_value=0) / 1000).round(0).to_string())
