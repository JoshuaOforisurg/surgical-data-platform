import pandas as pd

def clean_value(value, default="N/A"):
    if pd.isna(value) or value == "":
        return default
    return value


def build_preference_card(
    df: pd.DataFrame,
    surgeon_name: str,
    procedure: str | None = None,
) -> dict | None:
    """
    Converts Gold layer dataframe into a clinical preference card.
    Handles missing tabular values safely to prevent UI layout breakage.
    """
    if df is None or df.empty:
        return None

    surgeon_df = df[df["surgeon_name"] == surgeon_name]
    if procedure and "procedure" in surgeon_df.columns:
        surgeon_df = surgeon_df[surgeon_df["procedure"] == procedure]

    if surgeon_df.empty:
        return None

    base = surgeon_df.iloc[0]

    card = {
        "surgeon_name": clean_value(base.get("surgeon_name"), surgeon_name),
        "hospital": clean_value(base.get("hospital")),
        "specialty": clean_value(base.get("specialty")),
        "procedures": []
    }

    # Build procedure blocks safely filtering out Pandas NaN/Null values
    for _, row in surgeon_df.iterrows():
        procedure_block = {
            "procedure": clean_value(row.get("procedure"), "Unknown Procedure"),
            "procedure_id": clean_value(row.get("procedure_id")),
            "opcs_code": clean_value(row.get("opcs_code")),
            "readiness_status": clean_value(row.get("readiness_status")),
            "instrument_system": clean_value(row.get("instrument_system")),
            "implant_system": clean_value(row.get("implant_system")),
            "instrument_set": clean_value(row.get("instrument_set")),
            "priority_level": clean_value(row.get("priority_level")),
            "confidence": clean_value(row.get("confidence")),
            "positioning": clean_value(row.get("positioning")),
            "anaesthetic_notes": clean_value(row.get("anaesthetic_notes")),
            "skin_prep": clean_value(row.get("skin_prep")),
            "special_instructions": clean_value(row.get("special_instructions")),
        }

        card["procedures"].append(procedure_block)

    return card
