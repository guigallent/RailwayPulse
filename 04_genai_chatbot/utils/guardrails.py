import re
from pathlib import Path
from typing import Tuple

from utils.prompts import ALLOWED_VIEWS


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Validates generated SQL query against safety rules.
    Returns (is_valid, error_message).
    """
    cleaned_sql = sql.strip()

    # 1. Must start with SELECT or WITH (for CTEs)
    if not re.match(r"^(SELECT|WITH)\b", cleaned_sql, re.IGNORECASE):
        return False, "Query must be a SELECT or WITH statement."

    # 2. Block prohibited keywords (data modification, schema changes, system commands)
    prohibited_keywords = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
        r"\bALTER\b", r"\bCREATE\b", r"\bATTACH\b", r"\bDETACH\b",
        r"\bPRAGMA\b", r"\bVACUUM\b", r"\bEXPLAIN\b"
    ]
    for pattern in prohibited_keywords:
        if re.search(pattern, cleaned_sql, re.IGNORECASE):
            return False, f"Prohibited SQL keyword detected matching pattern: {pattern}"

    # 3. Disallow multiple statements (check for internal semicolons)
    # Strip trailing semicolon if present
    statement_body = cleaned_sql.rstrip(";").strip()
    if ";" in statement_body:
        return False, "Multiple SQL statements are not allowed."

    # 4. Enforce Table Allow-List
    # Extract table names following FROM, JOIN, or INTO keywords
    # This regex captures identifiers immediately after FROM/JOIN
    referenced_tables = set(
        match.group(1).lower()
        for match in re.finditer(
            r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", statement_body, re.IGNORECASE
        )
    )

    allowed_lower = {table.lower() for table in ALLOWED_VIEWS}
    for table in referenced_tables:
        if table not in allowed_lower:
            return False, f"Access denied to table or view '{table}'. Allowed: {ALLOWED_VIEWS}"

    return True, "Valid SQL"


if __name__ == "__main__":
    # Test suite
    test_cases = [
        ("SELECT * FROM vw_trip_stop_updates_enriched LIMIT 5;", True),
        ("SELECT * FROM sqlite_master;", False),
        ("DROP TABLE vw_trip_stop_updates_enriched;", False),
        ("SELECT * FROM vw_trip_stop_updates_enriched; DELETE FROM station_translations;", False),
        ("UPDATE station_translations SET stop_name_nl = 'X';", False),
        ("WITH cte AS (SELECT * FROM vw_latest_trip_updates) SELECT * FROM cte JOIN station_translations ON 1=1;", True),
    ]

    print("--- Guardrail Test Results ---")
    for sql_str, expected in test_cases:
        valid, msg = validate_sql(sql_str)
        status = "PASSED" if valid == expected else "FAILED"
        print(f"[{status}] Valid: {valid} | Msg: {msg}")
        print(f"  SQL: {sql_str}\n")