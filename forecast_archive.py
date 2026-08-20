"""Archive des prévisions — ce que le modèle annonçait, face à ce qui s'est passé.

Une prévision publiée sans trace de ses prévisions passées est une opinion : rien ne
permet au lecteur de savoir si l'exercice réussit. Ce module donne au projet la seule
chose qui transforme l'une en l'autre — une mémoire, tenue automatiquement.

## Deux natures de lignes, à ne jamais confondre

La colonne `kind` sépare deux choses qui se ressemblent dans un tableau et n'ont pas la
même valeur de preuve :

| `kind` | Ce que c'est | Ce que ça prouve |
|---|---|---|
| `archive` | Une prévision **réellement publiée** ce jour-là, enregistrée par le job hebdomadaire avant que la suite ne soit connue. | Beaucoup : personne ne peut la retoucher après coup. |
| `retro` | Une prévision **recalculée après coup**, en tronquant les données au millésime visé. | Moins : elle montre que la MÉTHODE tenait, pas que nous l'avions publiée. |

Les lignes `retro` existent pour que la page ne soit pas vide au lancement — sans elles,
il faudrait attendre un an avant d'avoir quoi que ce soit à montrer. Elles doivent rester
étiquetées comme telles partout où elles sont affichées. Les mélanger dans un même chiffre
« notre erreur moyenne » serait une tromperie.

**Limite des lignes `retro`, à énoncer sur la page** : elles sont calculées sur les séries
d'AUJOURD'HUI tronquées à la date du millésime, pas sur les valeurs telles qu'elles
étaient publiées à l'époque. Or les transactions dans l'ancien sont révisées. Une
rétro-simulation voit donc des données légèrement meilleures que celles dont on disposait
réellement — il n'existe pas d'archive de millésimes qui permettrait de faire autrement.
Pour ne pas ajouter un second avantage à ce premier, la troncature s'applique AUSSI aux
séries macro, alors qu'elles sont publiées plus vite que les transactions : la
rétro-simulation travaille donc avec un mois de macro de moins que la réalité.

## Ce qui n'est pas stocké, et pourquoi

Le **réalisé** n'est pas dans le fichier. Il est rejoint à la lecture, depuis la série
courante (`evaluate`). C'est délibéré : la source révise ses chiffres, et une valeur
réalisée figée à l'enregistrement vieillirait mal — on comparerait alors une prévision à
un réalisé périmé. Ce qui est figé, c'est ce qui ne doit jamais bouger : la prévision.

La **référence naïve** (`naive`), elle, est stockée : c'est le dernier cumul 12 mois
observé au moment de la prévision, donc une information qui n'existe plus telle quelle une
fois la série révisée. Elle sert d'étalon — un modèle qui ne bat pas « demain ressemblera
à aujourd'hui » ne mérite pas d'être publié, et le montrer vaut mieux que de l'espérer.

## Utilisation

    python forecast_archive.py --record       # enregistre la prévision du jour (hebdo)
    python forecast_archive.py --backfill     # (re)calcule les millésimes rétro-simulés
    python forecast_archive.py --report       # erreur par horizon, modèle contre naïve

Le module lui-même ne dépend ni de DuckDB ni du moteur : ses fonctions prennent des
structures déjà calculées. Seul `main()` fait le câblage, par des imports tardifs — ce qui
permet aux tests de tourner sans entrepôt.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

ARCHIVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "forecast_archive.csv")

#: Fenêtre d'entraînement du backtest — même valeur que `api.engine.FORECAST_SPLIT` et
#: `app.py:_FORECAST_SPLIT`, recopiée plutôt qu'importée pour la même raison qu'eux : ce
#: module ne doit dépendre ni de l'app Streamlit ni de l'API.
FORECAST_SPLIT = "2021-12-01"

COLUMNS = [
    "run_date",         # jour de l'enregistrement (UTC)
    "kind",             # "archive" (publiée) ou "retro" (recalculée après coup)
    "data_vintage",     # dernier mois de transactions CONNU à ce moment-là
    "target_month",     # le mois prévu
    "horizon",          # mois d'écart entre data_vintage et target_month (1..18)
    "predicted",        # cumul 12 mois de transactions prévu
    "lo", "hi",         # bande à ~80 % (± 1,2816 sigma)
    "assured",          # True : aucun prédicteur n'a eu besoin d'être prolongé
    "naive",            # référence : dernier cumul 12 mois observé (marche aléatoire)
    "sigma",            # écart-type retenu pour la bande
    "r2",               # R² du modèle au moment de la prévision
    "backtest_mape",    # MAPE hors échantillon connue à ce moment-là
    "lag_rate", "lag_intentions", "lag_unemployment",  # décalages retenus
]

# Les transactions sont des comptages : les arrondir à l'unité évite qu'un bruit de calcul
# au douzième chiffre après la virgule fasse croire à un changement de prévision et
# déclenche une ligne d'archive de plus chaque semaine.
_UNIT_COLS = ("predicted", "lo", "hi", "naive", "sigma")
_RATIO_COLS = ("r2", "backtest_mape")


# --------------------------------------------------------------------- construction
def snapshot_rows(projection: dict, model: dict, *, run_date, data_vintage,
                  kind: str = "archive") -> pd.DataFrame:
    """Les lignes d'archive correspondant à UNE prévision.

    `projection` et `model` sont les sorties de `api.engine.projection()` et
    `api.engine.transactions_model()` — c'est-à-dire exactement ce que le site publie.
    Reconstruire ici un calcul équivalent créerait une seconde vérité ; on archive donc la
    sortie publiée, pas une copie qui pourrait en diverger.
    """
    if not projection.get("available"):
        return pd.DataFrame(columns=COLUMNS)

    vintage = pd.Timestamp(data_vintage)
    lags = model.get("lags", {})
    backtest = model.get("backtest", {})
    rows = []
    for point in projection["series"]:
        target = pd.Timestamp(point["date"])
        rows.append({
            "run_date": pd.Timestamp(run_date).strftime("%Y-%m-%d"),
            "kind": kind,
            "data_vintage": vintage.strftime("%Y-%m-%d"),
            "target_month": target.strftime("%Y-%m-%d"),
            "horizon": _months_between(vintage, target),
            "predicted": point["predicted"],
            "lo": point["lo"],
            "hi": point["hi"],
            "assured": bool(point["assured"]),
            "naive": projection.get("last_observed"),
            "sigma": projection.get("sigma"),
            "r2": model.get("r2"),
            "backtest_mape": backtest.get("mape"),
            "lag_rate": lags.get("kr"),
            "lag_intentions": lags.get("ki"),
            "lag_unemployment": lags.get("kc"),
        })
    return _round(pd.DataFrame(rows, columns=COLUMNS))


def _months_between(start, end) -> int:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    return (end.year - start.year) * 12 + (end.month - start.month)


def _round(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in _UNIT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(0)
    for col in _RATIO_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(6)
    return df


# --------------------------------------------------------------------- lecture/écriture
def read(path: str = ARCHIVE_PATH) -> pd.DataFrame:
    """L'archive, ou une frame vide et correctement typée s'il n'y en a pas encore."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} : colonnes manquantes {missing}")
    return df[COLUMNS]


def write(df: pd.DataFrame, path: str = ARCHIVE_PATH) -> None:
    """Écrit l'archive, triée pour que le fichier versionné produise des diffs lisibles."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ordered = df.sort_values(["kind", "data_vintage", "target_month", "run_date"])
    ordered.to_csv(path, index=False)


def append_if_new(archive: pd.DataFrame, rows: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Ajoute `rows` à `archive`, sauf si la dernière prévision du même type est identique.

    Le job hebdomadaire tourne même les semaines où aucune source n'a bougé. Sans cette
    garde, l'archive gonflerait d'une copie conforme par semaine et le fichier versionné
    produirait un diff à chaque passage — exactement ce que l'acquisition des sources
    évite déjà de son côté.
    """
    if rows.empty:
        return archive, False
    same_kind = archive[archive["kind"] == rows["kind"].iloc[0]] if len(archive) else archive
    if len(same_kind):
        last_run = same_kind["run_date"].max()
        previous = same_kind[same_kind["run_date"] == last_run].drop(columns=["run_date"])
        candidate = rows.drop(columns=["run_date"])
        if _same_forecast(previous, candidate):
            return archive, False
    return pd.concat([archive, rows], ignore_index=True), True


def _same_forecast(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    key = ["data_vintage", "target_month"]
    a = a.sort_values(key).reset_index(drop=True)
    b = b.sort_values(key).reset_index(drop=True)
    if a.shape != b.shape:
        return False
    return a.astype(str).equals(b.astype(str))


# --------------------------------------------------------------------- évaluation
def evaluate(archive: pd.DataFrame, realized: pd.Series) -> pd.DataFrame:
    """Joint le réalisé et calcule l'erreur — pour les mois qui sont arrivés.

    `realized` : la série courante du cumul 12 mois, indexée par mois. Elle est relue à
    chaque appel plutôt que stockée, pour que l'archive suive les révisions de la source
    (voir l'en-tête du module).
    """
    if archive.empty:
        return archive.assign(realized=[], error=[], ape=[], naive_ape=[])
    obs = pd.Series(realized).dropna()
    obs.index = pd.to_datetime(obs.index)

    out = archive.copy()
    out["realized"] = pd.to_datetime(out["target_month"]).map(obs)
    out = out[out["realized"].notna()].copy()
    if out.empty:
        return out.assign(error=[], ape=[], naive_ape=[])
    out["error"] = out["predicted"] - out["realized"]
    out["ape"] = (out["error"].abs() / out["realized"]) * 100
    out["naive_ape"] = ((out["naive"] - out["realized"]).abs() / out["realized"]) * 100
    return out


def by_horizon(evaluated: pd.DataFrame) -> pd.DataFrame:
    """Erreur moyenne par horizon, modèle contre référence naïve.

    Un score unique ne dit rien d'utile : l'erreur à trois mois et celle à dix-huit n'ont
    aucune raison de se ressembler, et c'est l'horizon qui intéresse le lecteur. La colonne
    `skill` est la part d'erreur évitée par rapport à la naïve — négative, elle dit que le
    modèle fait moins bien que « demain ressemblera à aujourd'hui », ce qui doit se voir.
    """
    if evaluated.empty:
        return pd.DataFrame(columns=["horizon", "n", "mape", "naive_mape", "skill"])
    grouped = evaluated.groupby("horizon").agg(
        n=("ape", "size"), mape=("ape", "mean"), naive_mape=("naive_ape", "mean"),
    ).reset_index()
    grouped["skill"] = 1 - grouped["mape"] / grouped["naive_mape"].where(
        grouped["naive_mape"] > 0)
    return grouped


# --------------------------------------------------------------------- câblage
def _engine_snapshot(kind: str = "archive", run_date=None) -> pd.DataFrame:
    """La prévision du jour, telle que le site la publie."""
    from api import engine  # tardif : le module reste importable sans entrepôt

    engine.reset()
    projection = engine.projection()
    model = engine.transactions_model()
    vintage = engine.health()["transactions_last_month"]
    return snapshot_rows(projection, model, kind=kind,
                         run_date=run_date or pd.Timestamp.now("UTC").normalize(),
                         data_vintage=vintage)


def retro_rows(macro: pd.DataFrame, tx12: pd.Series, vintages, *,
               split: str = FORECAST_SPLIT, horizon: int = 18) -> pd.DataFrame:
    """Rétro-simule le modèle à chaque millésime : entrées tronquées, modèle réajusté.

    La troncature est la seule chose qui rende l'exercice honnête — elle porte sur la macro
    ET sur les transactions (voir l'en-tête : c'est le choix conservateur). Les décalages
    sont recherchés à chaque millésime, comme ils le seraient en vrai ; la fenêtre
    d'entraînement du backtest ne bouge pas, elle est antérieure à tous les millésimes.
    """
    import forecast as fc

    macro_dates = pd.to_datetime(macro["Date"])
    frames = []
    for vintage in vintages:
        vintage = pd.Timestamp(vintage)
        m = macro[macro_dates <= vintage]
        t = tx12[tx12.index <= vintage].dropna()
        if t.empty or len(m) < 60:
            continue
        lags = fc.search_tx_lags(m, t, split=split)
        model = fc.fit_tx_model(m, t, split=split, **lags)
        backtest = model["backtest"]
        sigma = float(backtest.get("rmse", model["rmse"]))
        path = fc.forecast_path(m, t, lags, model["beta"], sigma, horizon=horizon)
        if path is None or path.empty:
            continue
        projection = {
            "available": True,
            "sigma": sigma,
            "last_observed": float(t.iloc[-1]),
            "series": [{"date": row.Date, "predicted": row.pred, "lo": row.lo,
                        "hi": row.hi, "assured": row.assured}
                       for row in path.itertuples()],
        }
        published = {"r2": model["r2"], "lags": lags,
                     "backtest": {"mape": backtest.get("mape")}}
        # `run_date` = le millésime lui-même : ces lignes n'ont pas été produites un jour
        # donné, prétendre le contraire brouillerait la distinction avec `archive`.
        frames.append(snapshot_rows(projection, published, kind="retro",
                                    run_date=vintage, data_vintage=vintage))
    return (pd.concat(frames, ignore_index=True) if frames
            else pd.DataFrame(columns=COLUMNS))


def monthly_vintages(tx12: pd.Series, start: str, *, until=None) -> list[pd.Timestamp]:
    """Un millésime par mois observé : la série est mensuelle, donc c'est le rythme réel
    auquel une prévision aurait été republiée."""
    index = pd.to_datetime(tx12.dropna().index)
    end = pd.Timestamp(until) if until is not None else index.max()
    return [d for d in index if pd.Timestamp(start) <= d <= end]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true",
                        help="enregistre la prévision du jour (job hebdomadaire)")
    parser.add_argument("--backfill", metavar="DEPUIS", nargs="?", const="2022-07-01",
                        help="recalcule les millésimes rétro-simulés depuis cette date")
    parser.add_argument("--report", action="store_true",
                        help="affiche l'erreur par horizon, modèle contre naïve")
    parser.add_argument("--path", default=ARCHIVE_PATH)
    args = parser.parse_args(argv)
    if not (args.record or args.backfill or args.report):
        parser.error("choisir --record, --backfill ou --report")

    archive = read(args.path)

    if args.backfill:
        import queries as q
        from data_manager import DataManager

        con = q.open_warehouse()
        macro = DataManager().read_frames()[2]
        tx12 = q.transactions_run_rate(con)
        vintages = monthly_vintages(tx12, args.backfill)
        print(f"[archive] rétro-simulation de {len(vintages)} millésime(s)…")
        rows = retro_rows(macro, tx12, vintages)
        # La rétro-simulation est REJOUÉE en entier : elle est déterministe, et la garder
        # incrémentale mélangerait des lignes calculées avec des versions différentes du
        # modèle. Les lignes `archive`, elles, ne sont jamais réécrites.
        archive = pd.concat([archive[archive["kind"] != "retro"], rows], ignore_index=True)
        print(f"[archive] {len(rows)} ligne(s) rétro-simulée(s)")

    if args.record:
        try:
            rows = _engine_snapshot()
        except Exception as error:                      # noqa: BLE001
            # Ce script tourne dans le job hebdomadaire, AVANT l'export du front. Un modèle
            # que les séries du jour ne permettent pas de calibrer ne doit pas faire échouer
            # la publication des données : on perd une ligne d'archive, pas un rafraîchis-
            # sement. L'échec reste visible dans le journal du job.
            print(f"[archive] prévision non enregistrée — {type(error).__name__}: {error}")
            return 0
        archive, added = append_if_new(archive, rows)
        if added:
            print(f"[archive] prévision du {rows['run_date'].iloc[0]} enregistrée "
                  f"({len(rows)} points, millésime {rows['data_vintage'].iloc[0]})")
        else:
            print("[archive] prévision inchangée depuis le dernier enregistrement — rien à ajouter.")

    if args.record or args.backfill:
        write(archive, args.path)
        print(f"[archive] {len(archive)} ligne(s) au total dans {args.path}")

    if args.report:
        import queries as q

        realized = q.transactions_run_rate(q.open_warehouse())
        for kind in ("archive", "retro"):
            subset = archive[archive["kind"] == kind]
            table = by_horizon(evaluate(subset, realized))
            print(f"\n=== {kind} — {len(subset)} ligne(s) ===")
            print(table.to_string(index=False) if len(table) else "aucun mois échu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
