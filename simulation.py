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
    
    correlations = []
    lags = list(range(0, max_lag + 1))
    
    for lag in lags:
        # Shift the indicator forward by 'lag' months
        ind_shifted = ind_clean.copy()
        ind_shifted["Date"] = ind_shifted["Date"] + pd.DateOffset(months=lag)
        
        # Merge contemporaneous sales with shifted indicator
        merged = pd.merge(sales_clean, ind_shifted, on="Date", how="inner")
        
        if len(merged) > 6: # Need enough data points for a meaningful correlation
            # Calculate correlation
            r = merged[ind_col].corr(merged[sales_col])
            if pd.isna(r):
                r = 0.0
            correlations.append(r)
        else:
            correlations.append(0.0)
            
    # Find the lag with the highest absolute correlation (could be negative, e.g. interest rates,
    # but we usually look for positive correlation with permits, and negative with interest rates)
    abs_correlations = [abs(r) for r in correlations]
    if len(abs_correlations) > 0 and max(abs_correlations) > 0:
        opt_idx = np.argmax(abs_correlations)
        optimal_lag = lags[opt_idx]
        max_corr = correlations[opt_idx]
    else:
        optimal_lag = 0
        max_corr = 0.0
        
    return {
        "lags": lags,
        "correlations": [round(r, 3) for r in correlations],
        "optimal_lag": optimal_lag,
        "max_correlation": round(max_corr, 3)
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

def optimize_composite_parameters(df_c1, col_c1, df_c2, col_c2, df_c3, col_c3, df_sales, sales_col="Sales_Units", invert_c3=True):
    """
    Grid search to find the optimal lags and weights that maximize Pearson correlation 
    with benchmark sales.
    Executes in under 0.5s by using aligned NumPy vectors.
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
                
    max_r = -1.0
    best_lags = [12, 4, 6]
    best_weights = [0.6, 0.2, 0.2]
    
    # Fast Grid Search
    for l1 in lags_1:
        # Pre-shift component 1
        df_shift1 = c1_clean.copy()
        df_shift1['Date'] = df_shift1['Date'] + pd.DateOffset(months=l1)
        df_shift1 = df_shift1.rename(columns={'val': 'v1'})
        
        for l2 in lags_2:
            # Pre-shift component 2
            df_shift2 = c2_clean.copy()
            df_shift2['Date'] = df_shift2['Date'] + pd.DateOffset(months=l2)
            df_shift2 = df_shift2.rename(columns={'val': 'v2'})
            
            for l3 in lags_3:
                # Pre-shift component 3
                df_shift3 = c3_clean.copy()
                df_shift3['Date'] = df_shift3['Date'] + pd.DateOffset(months=l3)
                df_shift3 = df_shift3.rename(columns={'val': 'v3'})
                
                # Merge aligned
                merged = df_s_clean.copy()
                merged = pd.merge(merged, df_shift1[['Date', 'v1']], on='Date', how='inner')
                merged = pd.merge(merged, df_shift2[['Date', 'v2']], on='Date', how='inner')
                merged = pd.merge(merged, df_shift3[['Date', 'v3']], on='Date', how='inner')
                
                if len(merged) > 6:
                    y = merged[sales_col].values
                    v1 = merged['v1'].values
                    v2 = merged['v2'].values
                    v3 = merged['v3'].values
                    
                    for w1, w2, w3 in weight_combos:
                        composite = w1 * v1 + w2 * v2 + w3 * v3
                        # Calculate Pearson correlation
                        r_matrix = np.corrcoef(composite, y)
                        if r_matrix.shape[0] > 1:
                            r = r_matrix[0, 1]
                            if not np.isnan(r) and r > max_r:
                                max_r = r
                                best_lags = [l1, l2, l3]
                                best_weights = [w1, w2, w3]
                                
    return {
        "best_lags": best_lags,
        "best_weights": [round(w, 2) for w in best_weights],
        "max_correlation": round(max_r, 3)
    }

