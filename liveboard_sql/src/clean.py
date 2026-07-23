import pandas as pd

def drop_empty_columns(df):
    empty_cols = df.columns[df.isnull().all()]
    if len(empty_cols) > 0:
        print(f"  -> Removing empty columns: {list(empty_cols)}")
    else:
        print("  -> No empty columns found")
    return df.drop(columns=empty_cols)