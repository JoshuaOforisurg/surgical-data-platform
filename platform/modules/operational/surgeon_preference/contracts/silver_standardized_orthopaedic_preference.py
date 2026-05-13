import pandas as pd
import numpy as np
from datetime import datetime
from silver_orthopaedic_preference import OrthopaedicPreference


def clean_silver(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # -----------------------------------------
    # 1. Replace "Nan", "NaN", "", " " → proper NaN
    # -----------------------------------------
    df = df.replace(["Nan", "NaN", "", " "], np.nan)

    # -----------------------------------------
    # 2. Fix surgeon_id (generate synthetic if missing)
    # -----------------------------------------
    if "surgeon_id" not in df.columns:
        df["surgeon_id"] = np.nan

    df["surgeon_id"] = df["surgeon_id"].fillna(
        pd.Series(range(5000, 5000 + len(df)))
    ).astype(int)

    # -----------------------------------------
    # 3. Fix speciality
    # -----------------------------------------
    df["speciality"] = "Orthopaedics"

    # -----------------------------------------
    # 4. Fix subspeciality (fallback to Joints)
    # -----------------------------------------
    if "subspeciality" not in df.columns:
        df["subspeciality"] = "Joints"
    else:
        df["subspeciality"] = df["subspeciality"].fillna("Joints")

    # -----------------------------------------
    # 5. Fix preferred_retractor_size
    # -----------------------------------------
    if "preferred_retractor_size" not in df.columns:
        df["preferred_retractor_size"] = "Medium"
    else:
        df["preferred_retractor_size"] = df["preferred_retractor_size"].fillna("Medium")

    # -----------------------------------------
    # 6. Fix years_of_experience
    # -----------------------------------------
    if "years_of_experience" not in df.columns:
        df["years_of_experience"] = 5
    else:
        df["years_of_experience"] = (
            df["years_of_experience"]
            .fillna(5)
            .astype(float)
            .clip(lower=1, upper=40)
        )

    # -----------------------------------------
    # 7. Fix hospital_affiliation
    # -----------------------------------------
    if "hospital_affiliation" not in df.columns:
        df["hospital_affiliation"] = "Unknown"
    else:
        df["hospital_affiliation"] = df["hospital_affiliation"].fillna("Unknown")

    # -----------------------------------------
    # 8. Fix generation_timestamp
    # -----------------------------------------
    def fix_timestamp(x):
        if pd.isna(x):
            return datetime.utcnow()
        try:
            ts = pd.to_datetime(x)
            if ts.year < 2020:
                return datetime(2020, 1, 1)
            return ts
        except:
            return datetime.utcnow()

    if "generation_timestamp" not in df.columns:
        df["generation_timestamp"] = datetime.utcnow()
    else:
        df["generation_timestamp"] = df["generation_timestamp"].apply(fix_timestamp)

    return df
