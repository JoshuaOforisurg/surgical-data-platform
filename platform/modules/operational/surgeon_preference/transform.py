import pandas as pd
from datetime import datetime

def normalise_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )
    return df


def standardise_surgeon_name(name: str) -> str:
    if not isinstance(name, str):
        return None

    name = name.strip().title()

    # Add UK surgical title logic
    if not any(title in name for title in ["Mr", "Ms", "Mrs", "Dr", "Prof"]):
        name = f"Mr {name}"

    return name


def parse_date(date_value):
    if pd.isna(date_value):
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(date_value), fmt).date()
        except ValueError:
            continue

    return None


def standardise_vendor(vendor: str) -> str:
    if not isinstance(vendor, str):
        return None

    vendor = vendor.strip().title()

    replacements = {
        "Stryker Ltd": "Stryker",
        "Stryker UK": "Stryker",
        "J&J": "Johnson & Johnson",
        "Depuy Synthes": "Depuy Synthes",
    }

    return replacements.get(vendor, vendor)


def transform_preference_data(df: pd.DataFrame, source: str = "csv") -> pd.DataFrame:
    """
    data source = 'csv' or 'epr'
    """

    df = normalise_column_names(df)

    # Standardise surgeon names
    if "surgeon" in df.columns:
        df["surgeon"] = df["surgeon"].apply(standardise_surgeon_name)

    # Standardise vendor
    if "vendor" in df.columns:
        df["vendor"] = df["vendor"].apply(standardise_vendor)

    # Parse dates
    if "last_updated" in df.columns:
        df["last_updated"] = df["last_updated"].apply(parse_date)

    # Flatten nested items (EPR mode)
    if source == "epr" and "items" in df.columns:
        df["items"] = df["items"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

    # Fill missing fields for CSV mode
    if source == "csv":
        required_cols = ["procedure", "surgeon", "vendor", "items"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

    return df
