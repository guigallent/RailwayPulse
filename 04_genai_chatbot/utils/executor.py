import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "railpulse_snapshot.db"

# Columns that contain raw delay values in seconds needing conversion to minutes
DELAY_COLUMNS = {"arrival_delay", "departure_delay", "delay_seconds", "avg_delay", "max_delay"}


def convert_delays_to_minutes(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Scans row dictionaries and converts delay values from seconds to minutes (rounded to 1 decimal).
    Leaves non-delay fields untouched.
    """
    formatted_rows = []
    for row in rows:
        formatted_row = {}
        for key, val in row.items():
            if key.lower() in DELAY_COLUMNS and val is not None and isinstance(val, (int, float)):
                # Convert seconds to minutes
                formatted_row[f"{key}_min"] = round(val / 60.0, 1)
            else:
                formatted_row[key] = val
        formatted_rows.append(formatted_row)
    return formatted_rows


def execute_query(sql: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Executes validated SQL against railpulse_snapshot.db in read-only mode.
    Returns (formatted_results_list, column_names).
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database snapshot not found at: {DB_PATH}")

    # Open SQLite in read-only mode URI
    db_uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row  # Enables access by column name
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        raw_rows = cursor.fetchall()
        
        if not raw_rows:
            return [], []

        columns = [description[0] for description in cursor.description]
        dict_rows = [dict(row) for row in raw_rows]
        
        # Convert delays from seconds -> minutes
        formatted_rows = convert_delays_to_minutes(dict_rows)
        
        return formatted_rows, columns
    finally:
        conn.close()


if __name__ == "__main__":
    from utils.sql_chain import generate_sql

    test_questions = [
        "Which station had the most delays today?",
        "What percentage of trips at Gent-Sint-Pieters were tracked for delay?",
        "Combien de trains ont eu du retard à Bruxelles-Midi?",
    ]

    print("--- Testing SQL Generation + Execution Pipeline ---\n")
    for q in test_questions:
        print(f"Q: {q}")
        try:
            sql = generate_sql(q)
            results, cols = execute_query(sql)
            print(f"SQL: {sql}")
            print(f"Results ({len(results)} rows): {results}\n")
        except Exception as e:
            print(f"Execution Error: {e}\n")
        print("-" * 50)