import csv

def read_csv_file(filepath):
    """Reads a GTFS .txt/.csv file into a list of dicts (all values as strings).
    """
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [dict(row) for row in reader]
    return rows


def drop_empty_columns(rows):
    """Removes columns that are empty (None or '') across every row.
    """
    if not rows:
        print("  -> No rows to inspect, skipping")
        return rows

    fieldnames = rows[0].keys()
    empty_cols = {
        col for col in fieldnames
        if all(row.get(col) is None or row.get(col) == "" for row in rows)
    }

    if empty_cols:
        print(f"  -> Removing empty columns: {list(empty_cols)}")
    else:
        print("  -> No empty columns found")

    return [
        {k: v for k, v in row.items() if k not in empty_cols}
        for row in rows
    ]


def cast_value(value, col_type):
    """Casts a single string value to the target SQL type.

    Empty strings become None so they are inserted as SQL NULL, which
    matters for nullable/foreign-key columns like parent_station.
    """
    if value is None or value == "":
        return None
    if col_type == "int":
        return int(value)
    if col_type == "float":
        return float(value)
    return value  # "str" / TEXT columns pass through unchanged


def prepare_rows(rows, column_types):
    """Projects rows down to the columns a table actually has, in schema
    order, and casts each value to its SQL type.

    column_types: an ordered dict/list of (column_name, "int"|"float"|"str")
    describing the destination table, e.g. from build.py's schema.
    """
    prepared = []
    for row in rows:
        prepared.append({
            col: cast_value(row.get(col), col_type)
            for col, col_type in column_types
        })
    return prepared