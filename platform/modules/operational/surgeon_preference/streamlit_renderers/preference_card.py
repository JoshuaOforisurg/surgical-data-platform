import pandas as pd


def clean_value(value, default="N/A"):
    if pd.isna(value) or value == "":
        return default
    return value


def current_preference_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns the current frontline card per surgeon/procedure.

    Gold latest should already be current-state, but this keeps Streamlit safe
    when older duplicate-containing files are loaded.
    """
    if df is None or df.empty:
        return df

    working = df.copy()
    version_source = (
        working["preference_card_version"]
        if "preference_card_version" in working.columns
        else working.get("version_number", 1)
    )
    working["_sort_version"] = pd.to_numeric(version_source, errors="coerce").fillna(1)

    timestamp_source = pd.Series([pd.NaT] * len(working), index=working.index)
    for column in ("version_updated_at", "gold_created_at", "processed_at"):
        if column in working.columns:
            timestamp_source = working[column]
            break
    working["_sort_timestamp"] = pd.to_datetime(timestamp_source, errors="coerce", utc=True)
    confidence_source = (
        working["confidence"]
        if "confidence" in working.columns
        else pd.Series([0.0] * len(working), index=working.index)
    )
    working["_sort_confidence"] = pd.to_numeric(confidence_source, errors="coerce").fillna(0.0)

    surgeon_identity = "surgeon_name" if "surgeon_name" in working.columns else "surgeon_id"
    procedure_identity = "procedure_id" if "procedure_id" in working.columns else "procedure"
    if surgeon_identity not in working.columns or procedure_identity not in working.columns:
        return df

    working = working.sort_values(
        ["_sort_version", "_sort_timestamp", "_sort_confidence"],
        ascending=[False, False, False],
        na_position="last",
    )
    working = working.drop_duplicates(
        subset=[surgeon_identity, procedure_identity],
        keep="first",
    )
    return working.drop(
        columns=["_sort_version", "_sort_timestamp", "_sort_confidence"],
        errors="ignore",
    )


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

    df = current_preference_rows(df)
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
            "preference_card_version": clean_value(row.get("preference_card_version")),
            "preference_card_version_label": clean_value(row.get("preference_card_version_label")),
            "version_updated_at": clean_value(row.get("version_updated_at")),
            "data_product_version": clean_value(row.get("data_product_version")),
            "readiness_status": clean_value(row.get("readiness_status")),
            "instrument_system": clean_value(row.get("instrument_system")),
            "implant_system": clean_value(row.get("implant_system")),
            "instrument_set": clean_value(row.get("instrument_set")),
            "equipment": clean_value(row.get("equipment")),
            "draping": clean_value(row.get("draping")),
            "consumables": clean_value(row.get("consumables")),
            "disposables": clean_value(row.get("disposables")),
            "implants": clean_value(row.get("implants")),
            "sutures": clean_value(row.get("sutures")),
            "dressings": clean_value(row.get("dressings")),
            "priority_level": clean_value(row.get("priority_level")),
            "confidence": clean_value(row.get("confidence")),
            "positioning": clean_value(row.get("positioning")),
            "anaesthetic_notes": clean_value(row.get("anaesthetic_notes")),
            "skin_prep": clean_value(row.get("skin_prep")),
            "special_instructions": clean_value(row.get("special_instructions")),
        }

        card["procedures"].append(procedure_block)

    return card
