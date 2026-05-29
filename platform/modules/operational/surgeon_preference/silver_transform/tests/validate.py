import pandas as pd

def validate_required_columns(df: pd.DataFrame, required_cols: list) -> list:
    missing = [col for col in required_cols if col not in df.columns]
    return missing


def validate_surgeon_name(name: str) -> bool:
    if not isinstance(name, str):
        return False

    valid_titles = ["Mr", "Ms", "Mrs", "Dr", "Prof"]
    return any(name.startswith(title) for title in valid_titles)


def validate_items(items) -> bool:
    if isinstance(items, str) and items.strip():
        return True
    return False


def validate_dataframe(df: pd.DataFrame) -> dict:
    report = {"status": "PASS", "errors": []}

    required_cols = ["procedure", "surgeon", "vendor", "items", "last_updated"]
    missing = validate_required_columns(df, required_cols)

    if missing:
        report["status"] = "FAIL"
        report["errors"].append(f"Missing required columns: {missing}")

    # Row-level validation
    for idx, row in df.iterrows():

        if not validate_surgeon_name(row.get("surgeon")):
            report["status"] = "FAIL"
            report["errors"].append(f"Row {idx}: Invalid surgeon name '{row.get('surgeon')}'")

        if not validate_items(row.get("items")):
            report["status"] = "FAIL"
            report["errors"].append(f"Row {idx}: Items list is empty or invalid")

        if pd.isna(row.get("last_updated")):
            report["status"] = "FAIL"
            report["errors"].append(f"Row {idx}: Missing or invalid last_updated date")

    return report
