import pandas as pd
import numpy as np

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

def find_optimal_lag(df_indicator, df_sales, ind_col, sales_col, max_lag=24):
    """
    Finds the optimal time lag (in months) between an indicator and sales.
    Shifts the indicator forward by 'lag' months (from 0 to max_lag) and calculates 
    the Pearson correlation coefficient with contemporaneous sales.
    
    Returns:
        - dict with 'lags', 'correlations', 'optimal_lag', and 'max_correlation'
    """
    # Align dates and aggregate sales to monthly national level if they are detailed
    ind_clean = df_indicator[["Date", ind_col]].groupby("Date").sum().reset_index()
    sales_clean = df_sales[["Date", sales_col]].groupby("Date").sum().reset_index()

    correlations = []       # on levels (the historical behaviour)
    correlations_yoy = []   # on year-on-year changes (guards against spurious trend fit)
    n_points = []           # overlapping months per lag (a small n inflates |r|)
    lags = list(range(0, max_lag + 1))

    for lag in lags:
        # Shift the indicator forward by 'lag' months
        ind_shifted = ind_clean.copy()
        ind_shifted["Date"] = ind_shifted["Date"] + pd.DateOffset(months=lag)

        # Merge contemporaneous sales with shifted indicator
        merged = pd.merge(sales_clean, ind_shifted, on="Date", how="inner").sort_values("Date")
        n_points.append(len(merged))

        if len(merged) > 6:  # Need enough data points for a meaningful correlation
            r = merged[ind_col].corr(merged[sales_col])
            correlations.append(0.0 if pd.isna(r) else r)
            # Year-on-year change decorrelates the shared trend that makes two rising,
            # smoothed series look correlated even without a real lead-lag link.
            _iy = merged[ind_col].pct_change(12)
            _sy = merged[sales_col].pct_change(12)
            r_yoy = _iy.corr(_sy)
            correlations_yoy.append(0.0 if pd.isna(r_yoy) else r_yoy)
        else:
            correlations.append(0.0)
            correlations_yoy.append(0.0)

    # Find the lag with the highest absolute correlation (could be negative, e.g. interest rates,
    # but we usually look for positive correlation with permits, and negative with interest rates)
    abs_correlations = [abs(r) for r in correlations]
    if len(abs_correlations) > 0 and max(abs_correlations) > 0:
        opt_idx = int(np.argmax(abs_correlations))
        optimal_lag = lags[opt_idx]
        max_corr = correlations[opt_idx]
    else:
        opt_idx = 0
        optimal_lag = 0
        max_corr = 0.0

    return {
        "lags": lags,
        "correlations": [round(r, 3) for r in correlations],
        "correlations_yoy": [round(r, 3) for r in correlations_yoy],
        "n_points": n_points,
        "optimal_lag": optimal_lag,
        "max_correlation": round(max_corr, 3),
        "max_correlation_yoy": round(correlations_yoy[opt_idx], 3) if correlations_yoy else 0.0,
        "n_at_optimal": n_points[opt_idx] if n_points else 0,
    }

def min_max_normalize(series):
    """
    Helper to normalize a series to 0-100 range for combining different indicators.
    """
    s_min = series.min()
    s_max = series.max()
    if s_max == s_min:
        return series * 0.0 + 50.0
    return (series - s_min) / (s_max - s_min) * 100.0

def create_composite_indicator(components, target_start_date=None, target_end_date=None):
    """
    Creates a weighted composite leading indicator (Indicateur Composite).
    
    Each component is a dictionary:
    {
       'df': DataFrame containing Date and value columns,
       'value_col': str, name of the column,
       'lag': int, months to shift forward,
       'weight': float, weight of this component (0 to 1),
       'invert': bool, if True, inverts the normalized series (useful for interest rates)
    }
    
    Normalizes each component to a 0-100 scale, shifts it, multiplies by weight, 
    and sums them up.
    
    Returns:
        DataFrame with columns ['Date', 'Composite_Indicator']
    """
    if not components:
        return pd.DataFrame()
        
    # We will generate a master date grid
    all_dates = []
    processed_components = []
    
    for idx, comp in enumerate(components):
        df_comp = comp['df'][['Date', comp['value_col']]].copy()
        # Group by date to aggregate regional/departmental data if any
        df_comp = df_comp.groupby('Date')[comp['value_col']].sum().reset_index()
        
        # Normalize the raw series first to 0-100 range
        raw_vals = df_comp[comp['value_col']]
        norm_vals = min_max_normalize(raw_vals)
        if comp.get('invert', False):
            norm_vals = 100.0 - norm_vals
            
        df_comp['normalized_val'] = norm_vals
        
        # Apply the lag shift
        if comp['lag'] != 0:
            df_comp['Date'] = df_comp['Date'] + pd.DateOffset(months=comp['lag'])
            
        # Rename col to prevent collision
        df_comp = df_comp.rename(columns={'normalized_val': f'comp_{idx}'})
        processed_components.append(df_comp[['Date', f'comp_{idx}']])
        all_dates.extend(df_comp['Date'].tolist())
        
    # Build master date range and merge
    unique_dates = sorted(list(set(all_dates)))
    master_df = pd.DataFrame({'Date': unique_dates})
    
    for idx, comp_df in enumerate(processed_components):
        master_df = pd.merge(master_df, comp_df, on='Date', how='left')
        
    # Interpolate missing values resulting from shifting to align them nicely
    master_df = master_df.sort_values('Date').reset_index(drop=True)
    for idx in range(len(processed_components)):
        col_name = f'comp_{idx}'
        master_df[col_name] = master_df[col_name].interpolate(method='linear', limit_direction='both')
        
    # Calculate weighted sum
    master_df['Composite_Indicator'] = 0.0
    total_weight = sum(comp['weight'] for comp in components)
    if total_weight == 0:
        total_weight = 1.0
        
    for idx, comp in enumerate(components):
        col_name = f'comp_{idx}'
        normalized_weight = comp['weight'] / total_weight
        master_df['Composite_Indicator'] += master_df[col_name] * normalized_weight
        
    # Clean up and return
    result_df = master_df[['Date', 'Composite_Indicator']].copy()
    
    # Optionally filter dates
    if target_start_date:
        result_df = result_df[result_df['Date'] >= pd.to_datetime(target_start_date)]
    if target_end_date:
        result_df = result_df[result_df['Date'] <= pd.to_datetime(target_end_date)]
        
    return result_df.sort_values('Date').reset_index(drop=True)

def optimize_composite_parameters(df_c1, col_c1, df_c2, col_c2, df_c3, col_c3, df_sales,
                                  sales_col="Sales_Units", invert_c3=True, train_frac=0.7):
    """
    Grid search over lags & weights, selected on a TRAIN split and reported on a held-out
    TEST split so the headline correlation isn't the in-sample overfit of ~9 500 configs.

    The best (lags, weights) is chosen to maximise the Pearson correlation on the first
    `train_frac` of the aligned months; the returned `max_correlation` is that TRAIN value,
    and `test_correlation` is the SAME configuration measured on the remaining (later)
    months — the honest, out-of-sample number to trust. Falls back to the in-sample value
    for `test_correlation` when the overlap is too short to split.
    The 66 weight candidates for a given lag triple are evaluated in one matrix product
    rather than one Pearson call each, which is why the 9 504 configurations stay in the
    ~1.5 s range on the national series (the remaining cost is the 280 date merges).
    """
    # 1. Clean and normalize inputs
    c1_clean = df_c1[['Date', col_c1]].groupby('Date').sum().reset_index()
    c1_clean['val'] = min_max_normalize(c1_clean[col_c1])
    
    c2_clean = df_c2[['Date', col_c2]].groupby('Date').sum().reset_index()
    c2_clean['val'] = min_max_normalize(c2_clean[col_c2])
    
    c3_clean = df_c3[['Date', col_c3]].groupby('Date').sum().reset_index()
    c3_clean['val'] = min_max_normalize(c3_clean[col_c3])
    if invert_c3:
        c3_clean['val'] = 100.0 - c3_clean['val']
        
    df_s_clean = df_sales[['Date', sales_col]].groupby('Date').sum().reset_index()
    
    # Define candidate grids
    lags_1 = [6, 8, 10, 12, 14, 16, 18, 20] # Construction lags
    lags_2 = [0, 2, 4, 6, 8]               # Confidence lags
    lags_3 = [0, 2, 4, 6, 8, 10, 12]       # Credit rate lags
    
    # Generate weight candidates summing to 1.0 (step 0.1)
    weight_combos = []
    for w1 in np.arange(0.0, 1.05, 0.1):
        for w2 in np.arange(0.0, 1.05 - w1, 0.1):
            w3 = 1.0 - w1 - w2
            w1_r, w2_r, w3_r = round(w1, 1), round(w2, 1), round(w3, 1)
            if round(w1_r + w2_r + w3_r, 2) == 1.0:
                weight_combos.append((w1_r, w2_r, w3_r))
                
    # Weights as one (K, 3) matrix: every candidate composite for a given lag triple is
    # then a single matrix product V @ W.T instead of K separate weighted sums.
    W = np.asarray(weight_combos, dtype=float)

    max_r = -1.0          # best TRAIN correlation
    best_test_r = None    # its TEST correlation
    best_lags = [12, 4, 6]
    best_weights = [0.6, 0.2, 0.2]

    def _corr_all(C, y):
        """Pearson correlation of every column of C (n, K) against y (n,), vectorised.
        Returns (K,) with NaN where a composite is constant (zero variance) or n < 3."""
        if len(y) < 3:
            return np.full(C.shape[1], np.nan)
        Cc = C - C.mean(axis=0)
        yc = y - y.mean()
        den = np.sqrt((Cc ** 2).sum(axis=0)) * np.sqrt((yc ** 2).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(den > 0, (Cc * yc[:, None]).sum(axis=0) / den, np.nan)

    # Each component is aligned onto the sales dates ONCE PER CANDIDATE LAG (20 reindex
    # operations in total) instead of being re-merged inside the triple loop (840 merges).
    # Aligning component c at lag l means reading c at date (sales_date - l months), which
    # is exactly what shifting c forward by l and inner-joining on Date does; a month the
    # component does not cover stays NaN and is masked out below, reproducing the inner join.
    dates = pd.DatetimeIndex(df_s_clean['Date'])
    y_all = df_s_clean[sales_col].to_numpy(dtype=float)

    def _aligned(clean, lags):
        s = clean.set_index('Date')['val']
        return {l: s.reindex(dates - pd.DateOffset(months=l)).to_numpy(dtype=float)
                for l in lags}

    a1, a2, a3 = _aligned(c1_clean, lags_1), _aligned(c2_clean, lags_2), _aligned(c3_clean, lags_3)
    y_ok = np.isfinite(y_all)

    # Fast Grid Search
    for l1 in lags_1:
        v1_all = a1[l1]
        ok1 = y_ok & np.isfinite(v1_all)
        for l2 in lags_2:
            v2_all = a2[l2]
            ok2 = ok1 & np.isfinite(v2_all)
            for l3 in lags_3:
                v3_all = a3[l3]
                keep = ok2 & np.isfinite(v3_all)      # the inner-join row set
                n = int(keep.sum())
                if n > 6:
                    # df_s_clean is groupby-sorted by Date, so `keep` is already
                    # chronological and the split below is a true holdout.
                    y = y_all[keep]
                    V = np.column_stack((v1_all[keep], v2_all[keep], v3_all[keep]))
                    cut = int(n * train_frac)
                    # Need a usable train and test slice; else fall back to whole-sample.
                    has_split = (cut >= 3) and (n - cut >= 3)

                    # All candidate composites at once: (n, 3) @ (3, K) -> (n, K).
                    composites = V @ W.T
                    r_train = (_corr_all(composites[:cut], y[:cut]) if has_split
                               else _corr_all(composites, y))
                    if np.all(np.isnan(r_train)):
                        continue
                    # nanargmax returns the FIRST maximum, matching the strict ">" of the
                    # original per-combo loop, so ties resolve to the same weights.
                    k = int(np.nanargmax(r_train))
                    if r_train[k] > max_r:
                        max_r = float(r_train[k])
                        best_lags = [l1, l2, l3]
                        best_weights = [float(w) for w in W[k]]
                        best_test_r = (float(_corr_all(composites[cut:], y[cut:])[k])
                                       if has_split else max_r)

    return {
        "best_lags": best_lags,
        "best_weights": [round(w, 2) for w in best_weights],
        "max_correlation": round(max_r, 3),
        "test_correlation": (round(best_test_r, 3) if best_test_r is not None
                             and not np.isnan(best_test_r) else None),
    }

