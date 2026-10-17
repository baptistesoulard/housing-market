"""Le banc d'essai (bench/tsfm_benchmark.py) : la conversion flux mensuels → cumul 12 mois.

Une erreur d'indice y a décalé d'un mois toutes les variantes « flux » et amputé leur
dernier horizon d'un mois de ventes (corrigé le 2026-10-17, journal 06). Le test fixe la
définition : le cumul à l'horizon h est la somme des mois v+h-11 à v+h.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bench"))

from tsfm_benchmark import flux_vers_tx12  # noqa: E402


def test_le_cumul_couvre_exactement_les_douze_mois_finissant_a_l_horizon():
    obs = np.arange(1, 25, dtype=float)          # mois v-23..v valent 1..24
    prev = np.arange(25, 43, dtype=float)        # mois v+1..v+18 valent 25..42
    attendu = [sum(range(13 + h, 25 + h)) for h in range(1, 19)]
    assert flux_vers_tx12(obs, prev).tolist() == attendu


def test_des_ventes_constantes_donnent_un_cumul_constant_a_tous_les_horizons():
    r = flux_vers_tx12(np.full(24, 5.0), np.full(18, 5.0))
    assert (r == 60.0).all(), r
