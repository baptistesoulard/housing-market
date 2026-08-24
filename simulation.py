"""Décalage temporel d'un indicateur, pour l'aligner sur une série cible.

Ce module portait aussi la recherche de décalage par maximisation du r de Pearson et
tout l'indicateur composite pondéré à la main. Les deux sont partis avec l'onglet
« Atelier exploratoire » (voir CLAUDE.md, « Onglets retirés ») : la recherche de
décalage est faite par « Prévision & Scénarios », en grille sur le R² du modèle
lui-même et sur la seule fenêtre d'entraînement ; le composite, lui, n'avait ni
backtest ni score, donc rien pour l'arbitrer.

Ne reste que le décalage, qui est de la mise en forme et non une méthode rivale.
"""
import pandas as pd

def shift_indicator(df, date_col, value_col, lag_months):
    """
    Shifts the date of an indicator forward (lag > 0) or backward (lag < 0) by a given number of months.
    This creates the "Indicateur Avancé".
    For example, if lag_months = 14:
    A value on 2024-01-01 is shifted to 2025-03-01. This represents how today's permits 
    predict sales 14 months in the future.
    """
    df_shifted = df[[date_col, value_col]].copy()
    if lag_months == 0:
        return df_shifted.rename(columns={value_col: f"{value_col}_shifted_0"})
        
    df_shifted[date_col] = df_shifted[date_col] + pd.DateOffset(months=lag_months)
    return df_shifted.rename(columns={value_col: f"{value_col}_shifted_{lag_months}"})
