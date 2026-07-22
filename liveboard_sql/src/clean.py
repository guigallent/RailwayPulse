import pandas as pd

def drop_empty_columns(df):
    empty_cols = df.columns[df.isnull().all()]
    return df.drop(columns=empty_cols)