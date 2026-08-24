"""L'archive des prévisions tient-elle ses promesses de fond ?

Ce que ce module protège n'est pas un calcul mais une **règle de preuve**. Une archive de
prévisions ne vaut que si trois choses restent vraies, et aucune des trois ne se voit à
l'écran quand elle casse :

1. **Ce qui a été publié ne bouge jamais.** Une prévision réenregistrée, arrondie
   autrement ou recalculée après coup n'est plus une prévision : c'est un commentaire.
2. **Le publié et le rétro-simulé ne se mélangent pas.** Les agréger dans un même
   « notre erreur moyenne » ferait passer une reconstitution pour une promesse tenue.
3. **La référence naïve reste comparée à armes égales.** C'est elle qui dit si le modèle
   sert à quelque chose ; la fausser flatterait le modèle sans que rien ne le signale.

Les tests n'ont besoin ni de l'entrepôt DuckDB ni du moteur : les fonctions du module sont
pures et prennent les structures déjà calculées.
"""
import numpy as np
import pandas as pd
import pytest

import forecast_archive as fa


def _projection(dates, predicted, *, sigma=50_000.0, last_observed=900_000.0,
                assured_until=1):
    """Une sortie d'`api.engine.projection()` réduite à ce que l'archive en retient."""
    return {
        "available": True,
        "sigma": sigma,
        "last_observed": last_observed,
        "series": [{"date": d, "predicted": p, "lo": p - sigma, "hi": p + sigma,
                    "assured": i < assured_until}
                   for i, (d, p) in enumerate(zip(dates, predicted))],
    }


_MODEL = {"r2": 0.91, "lags": {"kr": 10, "ki": 2, "kc": 0}, "backtest": {"mape": 4.68}}


def _rows(vintage="2026-06-01", predicted=(900_000.0, 890_000.0, 880_000.0),
          kind="archive", run_date="2026-08-20", **kwargs):
    dates = pd.date_range(pd.Timestamp(vintage) + pd.DateOffset(months=1),
                          periods=len(predicted), freq="MS").strftime("%Y-%m-%d")
    return fa.snapshot_rows(_projection(dates, predicted, **kwargs), _MODEL,
                            run_date=run_date, data_vintage=vintage, kind=kind)


# ------------------------------------------------------------------ construction
def test_une_prevision_donne_une_ligne_par_mois_vise():
    rows = _rows()
    assert list(rows.columns) == fa.COLUMNS
    assert len(rows) == 3
    assert rows["data_vintage"].unique().tolist() == ["2026-06-01"]
    assert rows["target_month"].tolist() == ["2026-07-01", "2026-08-01", "2026-09-01"]


def test_l_horizon_compte_les_mois_depuis_le_millesime():
    """C'est l'axe de lecture de toute la page : à 3 mois et à 18 mois, un modèle n'a
    aucune raison de se tromper pareil."""
    assert _rows()["horizon"].tolist() == [1, 2, 3]


def test_l_horizon_traverse_les_annees():
    rows = _rows(vintage="2025-11-01", predicted=(1.0, 2.0, 3.0))
    assert rows["horizon"].tolist() == [1, 2, 3]
    assert rows["target_month"].iloc[-1] == "2026-02-01"


def test_une_projection_indisponible_ne_produit_rien():
    """Le moteur renvoie `available: False` quand les décalages ne laissent aucun mois
    atteignable. Archiver une ligne vide vaudrait pire que rien."""
    rows = fa.snapshot_rows({"available": False, "series": []}, _MODEL,
                            run_date="2026-08-20", data_vintage="2026-06-01")
    assert rows.empty and list(rows.columns) == fa.COLUMNS


def test_les_transactions_sont_arrondies_a_l_unite():
    """Sans cet arrondi, un bruit de calcul au douzième chiffre ferait croire chaque
    semaine à une prévision nouvelle, et l'archive gonflerait de copies conformes."""
    rows = _rows(predicted=(900_000.000000001, 890_000.4, 880_000.6))
    assert rows["predicted"].tolist() == [900_000.0, 890_000.0, 880_001.0]


# ------------------------------------------------------------------ ajout
def test_une_prevision_inchangee_n_est_pas_reenregistree():
    archive, added = fa.append_if_new(fa.read("/inexistant"), _rows())
    assert added and len(archive) == 3
    encore, added = fa.append_if_new(archive, _rows(run_date="2026-08-27"))
    assert not added, "le job hebdomadaire dupliquerait l'archive chaque semaine"
    assert len(encore) == 3


def test_une_prevision_qui_change_est_ajoutee():
    archive, _ = fa.append_if_new(fa.read("/inexistant"), _rows())
    archive, added = fa.append_if_new(
        archive, _rows(run_date="2026-08-27", predicted=(905_000.0, 890_000.0, 880_000.0)))
    assert added and len(archive) == 6


def test_un_nouveau_millesime_est_ajoute_meme_a_valeurs_egales():
    """Deux millésimes différents sont deux prévisions différentes, même si le modèle
    annonce par coïncidence les mêmes chiffres."""
    archive, _ = fa.append_if_new(fa.read("/inexistant"), _rows(vintage="2026-05-01"))
    archive, added = fa.append_if_new(archive, _rows(vintage="2026-06-01"))
    assert added and archive["data_vintage"].nunique() == 2


def test_les_deux_natures_ne_se_bloquent_pas_l_une_l_autre():
    """La garde de contenu compare une prévision aux prévisions DE SON TYPE : une ligne
    rétro-simulée ne doit pas empêcher d'enregistrer la prévision publiée du jour."""
    archive, _ = fa.append_if_new(fa.read("/inexistant"), _rows(kind="retro"))
    archive, added = fa.append_if_new(archive, _rows(kind="archive"))
    assert added
    assert set(archive["kind"]) == {"retro", "archive"}


# ------------------------------------------------------------------ persistance
def test_aller_retour_sur_disque(tmp_path):
    path = str(tmp_path / "archive.csv")
    fa.write(_rows(), path)
    relu = fa.read(path)
    assert relu["predicted"].tolist() == [900_000.0, 890_000.0, 880_000.0]
    assert relu["kind"].tolist() == ["archive"] * 3


def test_une_archive_absente_se_lit_comme_une_archive_vide():
    """Le premier passage du job hebdomadaire tourne sans fichier : il doit créer, pas
    échouer."""
    vide = fa.read("/inexistant/archive.csv")
    assert vide.empty and list(vide.columns) == fa.COLUMNS


def test_un_fichier_ampute_est_refuse(tmp_path):
    """Mieux vaut interrompre que publier une page d'archive silencieusement incomplète."""
    path = tmp_path / "archive.csv"
    path.write_text("run_date,kind\n2026-08-20,archive\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colonnes manquantes"):
        fa.read(str(path))


def test_le_fichier_versionne_est_trie_pour_des_diffs_lisibles(tmp_path):
    path = str(tmp_path / "archive.csv")
    melange = pd.concat([_rows(vintage="2026-06-01"), _rows(vintage="2026-05-01")],
                        ignore_index=True)
    fa.write(melange, path)
    relu = fa.read(path)
    assert relu["data_vintage"].tolist() == sorted(relu["data_vintage"].tolist())


# ------------------------------------------------------------------ évaluation
_REALISE = pd.Series({pd.Timestamp("2026-07-01"): 1_000_000.0,
                      pd.Timestamp("2026-08-01"): 800_000.0})


def test_seuls_les_mois_echus_sont_juges():
    """Trois mois prévus, deux mois réalisés : le troisième n'est pas encore arrivé et ne
    doit compter ni comme réussite ni comme échec."""
    evalue = fa.evaluate(_rows(), _REALISE)
    assert evalue["target_month"].tolist() == ["2026-07-01", "2026-08-01"]


def test_l_erreur_est_relative_et_signee_comme_il_faut():
    evalue = fa.evaluate(_rows(predicted=(900_000.0, 900_000.0, 0.0)), _REALISE)
    # 900 000 prévus contre 1 000 000 réalisés : 10 % d'erreur, sous-estimation.
    assert evalue["error"].iloc[0] == pytest.approx(-100_000.0)
    assert evalue["ape"].iloc[0] == pytest.approx(10.0)
    # 900 000 contre 800 000 : 12,5 % d'erreur, surestimation — l'erreur ABSOLUE en %.
    assert evalue["error"].iloc[1] == pytest.approx(100_000.0)
    assert evalue["ape"].iloc[1] == pytest.approx(12.5)


def test_la_naive_est_jugee_sur_les_memes_mois_que_le_modele():
    """Sinon la comparaison qui décide de l'utilité du modèle serait truquée."""
    evalue = fa.evaluate(_rows(last_observed=1_000_000.0), _REALISE)
    assert evalue["naive_ape"].iloc[0] == pytest.approx(0.0)     # naïve parfaite ce mois-là
    assert evalue["naive_ape"].iloc[1] == pytest.approx(25.0)
    assert evalue["ape"].notna().all()


def test_une_archive_sans_mois_echu_ne_plante_pas():
    """L'état du jour de la mise en service : des prévisions, aucun verdict."""
    evalue = fa.evaluate(_rows(vintage="2030-01-01"), _REALISE)
    assert evalue.empty
    assert fa.by_horizon(evalue).empty


def test_evaluer_une_archive_vide_ne_plante_pas():
    assert fa.evaluate(fa.read("/inexistant"), _REALISE).empty


# ------------------------------------------------------------------ score par horizon
def test_le_score_par_horizon_compare_modele_et_naive():
    # 900 000 prévus aux deux horizons, contre 1 000 000 puis 800 000 réalisés ;
    # la naïve annonce 1 000 000 partout : parfaite au mois 1, à 25 % au mois 2.
    evalue = fa.evaluate(_rows(predicted=(900_000.0, 900_000.0, 0.0),
                               last_observed=1_000_000.0), _REALISE)
    table = fa.by_horizon(evalue)
    assert table["horizon"].tolist() == [1, 2]
    ligne = table[table["horizon"] == 2].iloc[0]
    assert ligne["mape"] == pytest.approx(12.5)
    assert ligne["naive_mape"] == pytest.approx(25.0)
    assert ligne["skill"] == pytest.approx(0.5)          # moitié de l'erreur évitée


def test_un_modele_moins_bon_que_la_naive_affiche_un_score_negatif():
    """Le cas qui compte, et celui que les données réelles produisent à court terme : le
    modèle PERD contre « demain ressemblera à aujourd'hui ». Un score négatif doit
    apparaître, au lieu d'être noyé dans une moyenne tous horizons confondus."""
    evalue = fa.evaluate(_rows(predicted=(500_000.0, 500_000.0, 0.0),
                               last_observed=820_000.0), _REALISE)
    ligne = fa.by_horizon(evalue).iloc[1]                # horizon 2
    assert ligne["mape"] == pytest.approx(37.5)
    assert ligne["naive_mape"] == pytest.approx(2.5)
    assert ligne["skill"] < 0


def test_une_naive_parfaite_ne_produit_pas_de_score():
    """Diviser par une erreur naïve nulle donnerait un infini qui s'afficherait comme un
    exploit. Mieux vaut « pas de score » qu'une division par zéro déguisée."""
    evalue = fa.evaluate(_rows(last_observed=1_000_000.0), _REALISE)
    ligne = fa.by_horizon(evalue).iloc[0]                # horizon 1 : naïve exacte
    assert ligne["naive_mape"] == pytest.approx(0.0)
    assert pd.isna(ligne["skill"])


def test_le_score_reste_calculable_quand_la_naive_se_trompe_plus():
    evalue = fa.evaluate(_rows(predicted=(1_100_000.0, 1_000_000.0, 0.0),
                               last_observed=1_400_000.0), _REALISE)
    table = fa.by_horizon(evalue)
    assert (table["skill"] < 1).all() and table["skill"].notna().all()


# ------------------------------------------------------------------ millésimes
def test_les_millesimes_suivent_le_rythme_de_la_serie():
    serie = pd.Series(range(6),
                      index=pd.date_range("2026-01-01", periods=6, freq="MS"))
    vintages = fa.monthly_vintages(serie, "2026-03-01")
    assert [v.strftime("%Y-%m") for v in vintages] == ["2026-03", "2026-04", "2026-05", "2026-06"]


def test_les_millesimes_s_arretent_ou_on_le_demande():
    serie = pd.Series(range(6),
                      index=pd.date_range("2026-01-01", periods=6, freq="MS"))
    vintages = fa.monthly_vintages(serie, "2026-01-01", until="2026-02-01")
    assert len(vintages) == 2


# ------------------------------------------------------------------ sens et bande
def test_le_taux_de_bon_sens_compare_les_directions_pas_les_niveaux():
    """« Le marché monte-t-il ou baisse-t-il ? » est la question du lecteur.

    Une MAPE demande de savoir ce qu'est une erreur relative moyenne ; un taux de bon sens
    se lit tel quel, et c'est sur lui qu'une décision d'achat ou un plan de charge se
    prennent. Le sens s'apprécie par rapport au dernier chiffre CONNU au moment de la
    prévision — la même référence que la naïve, sans quoi les deux ne se compareraient pas.
    """
    rows = _rows(predicted=(950_000.0, 850_000.0), last_observed=900_000.0)
    realise = pd.Series([960_000.0, 890_000.0],
                        index=pd.to_datetime(["2026-07-01", "2026-08-01"]))
    table = fa.by_horizon(fa.evaluate(rows, realise))
    # h1 : prévu au-dessus de 900k, réalisé au-dessus  -> bon sens
    # h2 : prévu en dessous, réalisé en dessous        -> bon sens
    assert table["direction"].tolist() == [1.0, 1.0]

    rows = _rows(predicted=(950_000.0,), last_observed=900_000.0)
    realise = pd.Series([880_000.0], index=pd.to_datetime(["2026-07-01"]))
    assert fa.by_horizon(fa.evaluate(rows, realise))["direction"].iloc[0] == 0.0


def test_la_couverture_dit_ce_que_la_bande_vaut_vraiment():
    """Une bande annoncée à 80 % qui en couvre 57 % n'est pas une bande, c'est un décor."""
    rows = _rows(predicted=(900_000.0, 900_000.0), sigma=10_000.0)
    realise = pd.Series([905_000.0, 950_000.0],           # dedans, puis dehors
                        index=pd.to_datetime(["2026-07-01", "2026-08-01"]))
    assert fa.by_horizon(fa.evaluate(rows, realise))["coverage"].tolist() == [1.0, 0.0]


def test_la_bande_calibree_suit_les_quantiles_de_l_erreur_signee():
    """`band_table` étalonne la bande sur les erreurs passées, par horizon.

    L'erreur retenue est SIGNÉE : le modèle surestime de façon croissante avec l'horizon,
    et une bande symétrique autour d'une prévision biaisée rate d'un côté plus que de
    l'autre. Les bornes sont donc inversées — surestimer de 30 000 dans 90 % des cas veut
    dire que le réalisé est au moins 30 000 SOUS la prévision aussi souvent.
    """
    ev = pd.DataFrame({"horizon": [1] * 40,
                       "predicted": np.linspace(900_000.0, 940_000.0, 40),
                       "realized": 900_000.0})
    table = fa.band_table(ev, lo_q=0.10, hi_q=0.90, min_obs=20)
    assert table["horizon"].tolist() == [1] and table["n"].iloc[0] == 40
    erreurs = ev["predicted"] - ev["realized"]
    assert abs(table["lo_off"].iloc[0] + erreurs.quantile(0.90)) < 1e-6
    assert abs(table["hi_off"].iloc[0] + erreurs.quantile(0.10)) < 1e-6
    assert table["lo_off"].iloc[0] < table["hi_off"].iloc[0]


def test_un_horizon_trop_peu_observe_n_est_pas_calibre():
    """Mieux vaut la bande constante qu'un quantile tiré de cinq points."""
    ev = pd.DataFrame({"horizon": [1] * 30 + [2] * 5,
                       "predicted": 910_000.0, "realized": 900_000.0})
    assert fa.band_table(ev, min_obs=20)["horizon"].tolist() == [1]
    assert fa.band_table(pd.DataFrame()).empty


def test_la_bande_fait_un_aller_retour_par_le_disque(tmp_path):
    chemin = str(tmp_path / "forecast_band.csv")
    assert fa.read_band(chemin) is None                   # absente -> repli, pas d'erreur
    band = pd.DataFrame({"horizon": [2, 1], "n": [30, 30],
                         "lo_off": [-40_000.0, -10_000.0], "hi_off": [30_000.0, 5_000.0]})
    fa.write_band(band, chemin)
    relue = fa.read_band(chemin)
    assert relue["horizon"].tolist() == [1, 2]            # triée, pour un diff lisible
    assert relue["lo_off"].tolist() == [-10_000.0, -40_000.0]
