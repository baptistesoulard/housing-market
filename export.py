import pandas as pd
import numpy as np

def format_for_sap_ibp(df_indicator, indicator_name, date_col="Date", value_col="Value", 
                       loc_col=None, location_val="FR", time_granularity="Monthly", 
                       date_format="YYYY-MM-DD", delimiter=";", 
                       custom_headers=None):
    """
    Formats a shifted indicator series into a flat table matching SAP IBP Key Figure import requirements.
    
    Parameters:
        df_indicator (DataFrame): Input data containing date and value.
        indicator_name (str): ID of the Key Figure / Indicator (e.g., 'KF_SITADEL_PERMIS_LAG14').
        date_col (str): Column containing dates.
        value_col (str): Column containing the values.
        loc_col (str): If None, use static 'location_val' for all rows. If provided, maps locations.
        location_val (str): Default location code if no location column is in df_indicator (e.g. "FR" or "NATIONAL").
        time_granularity (str): "Monthly" or "Weekly" (resamples or interpolates to weeks).
        date_format (str): "YYYY-MM-DD", "YYYYMM", or "DD/MM/YYYY".
        delimiter (str): ";", ",", or "\t".
        custom_headers (dict): Dict mapping default headers ('PERIOD', 'LOCATION', 'INDICATOR', 'VALUE') 
                              to SAP IBP target fields.
                              
    Returns:
        tuple (csv_string, DataFrame): Flat formatted DataFrame and its raw CSV string representation.
    """
    df = df_indicator.copy()
    df = df.sort_values(date_col)
    
    # 1. Handle Time Granularity
    if time_granularity == "Weekly":
        # Convert to weekly frequency (W-MON)
        # We can set the date as index, resample weekly, and interpolate the values
        df_temp = df.set_index(date_col)
        # Weekly resampling, linear interpolation of the values
        df_weekly = df_temp[[value_col]].resample('W-MON').interpolate(method='linear')
        
        # If there are locations, we would need to do this per location
        if loc_col and loc_col in df.columns:
            weekly_rows = []
            for loc in df[loc_col].unique():
                df_loc = df[df[loc_col] == loc].set_index(date_col)
                df_loc_w = df_loc[[value_col]].resample('W-MON').interpolate(method='linear')
                df_loc_w[loc_col] = loc
                weekly_rows.append(df_loc_w.reset_index())
            df = pd.concat(weekly_rows, ignore_index=True)
        else:
            df = df_weekly.reset_index()
    else:
        # Standard monthly (ensuring it is grouped properly if locations exist)
        if loc_col and loc_col in df.columns:
            df = df.groupby([date_col, loc_col])[value_col].sum().reset_index()
        else:
            df = df.groupby(date_col)[value_col].sum().reset_index()
            
    # 2. Build Standard Flat Table Columns
    flat_rows = []
    
    # If location column is not present or selected, create a static location column
    if not loc_col or loc_col not in df.columns:
        df["LOC_ID"] = location_val
        loc_field = "LOC_ID"
    else:
        loc_field = loc_col
        
    df["IND_ID"] = indicator_name
    
    # 3. Apply Date Formatting
    def format_date(dt):
        if date_format == "YYYYMM":
            return dt.strftime("%Y%m")
        elif date_format == "DD/MM/YYYY":
            return dt.strftime("%d/%m/%Y")
        else: # YYYY-MM-DD
            return dt.strftime("%Y-%m-%d")
            
    df["PERIOD"] = df[date_col].apply(format_date)
    
    # 4. Standard SAP Schema Column Mapping
    default_headers = {
        'PERIOD': 'PERIODID0',
        'LOCATION': 'LOCID',
        'INDICATOR': 'PRDID',
        'VALUE': 'KEYFIGUREVALUE'
    }
    
    if custom_headers:
        # Merge or override defaults with user settings
        default_headers.update(custom_headers)
        
    # Build final DataFrame with requested column names
    export_df = pd.DataFrame({
        default_headers['PERIOD']: df["PERIOD"],
        default_headers['LOCATION']: df[loc_field],
        default_headers['INDICATOR']: df["IND_ID"],
        default_headers['VALUE']: df[value_col].round(2)
    })
    
    # Clean up NaN values (convert to empty strings or 0.0)
    export_df = export_df.fillna(0.0)
    
    # Generate CSV string
    csv_string = export_df.to_csv(index=False, sep=delimiter, encoding="utf-8")
    
    return csv_string, export_df
