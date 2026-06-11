import pandas as pd

def build_preference_card(df: pd.DataFrame, surgeon_name: str) -> dict | None:
    """
    Converts Gold layer dataframe into a clinical preference card.
    Handles missing tabular values safely to prevent UI layout breakage.
    """
    if df is None or df.empty:
        return None

    surgeon_df = df[df["surgeon_name"] == surgeon_name]

    if surgeon_df.empty:
        return None

    base = surgeon_df.iloc[0]

    card = {
        "surgeon_name": base.get("surgeon_name") if pd.notna(base.get("surgeon_name")) else surgeon_name,
        "hospital": base.get("hospital") if pd.notna(base.get("hospital")) else "N/A",
        "specialty": base.get("specialty") if pd.notna(base.get("specialty")) else "N/A",
        "procedures": []
    }

    # Build procedure blocks safely filtering out Pandas NaN/Null values
    for _, row in surgeon_df.iterrows():
        procedure_block = {
            "procedure": row.get("procedure") if pd.notna(row.get("procedure")) else "Unknown Procedure",
            "implant_system": row.get("implant_system") if pd.notna(row.get("implant_system")) else "N/A",
            "approach": row.get("approach") if pd.notna(row.get("approach")) else "N/A",
            "instrument_set": row.get("instrument_set") if pd.notna(row.get("instrument_set")) else "N/A",
            "laterality": row.get("laterality") if pd.notna(row.get("laterality")) else "N/A",
            "priority_level": row.get("priority_level") if pd.notna(row.get("priority_level")) else "N/A",
        }

        card["procedures"].append(procedure_block)

    return card
