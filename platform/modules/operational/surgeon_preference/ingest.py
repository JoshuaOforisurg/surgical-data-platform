"""
End‑to‑end ingestion pipeline for orthopaedic preference data.

Here is how the code works:
1. Read CSV
2. Validate each row using Pydantic schema
3. Load validated records into Postgres

This script is designed for production‑style pipelines:
- strict validation
- clear logging
- safe database insertion
"""

import pandas as pd
import psycopg2
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, List
from datetime import datetime


# ---------------------------------------------------------
# Pydantic Schema (Validation Layer)
# ---------------------------------------------------------

class OrthopaedicPreference(BaseModel):
    surgeon_id: int = Field(..., ge=1000, le=9999)
    surgeon_name: str
    speciality: Literal["Orthopaedics"]
    subspecialty: Literal[
        "Joints", "Trauma", "Spine", "Paediatric", "Foot and Ankle"
    ]
    procedure: str
    instrument: str
    preferred_retractor_size: Literal["Small", "Medium", "Large", "Extra Large"]
    preferred_drill_brand: str
    needs_backup_suction: bool
    years_of_experience: int = Field(..., ge=1, le=40)
    hospital_affiliation: str
    generation_timestamp: datetime


# ---------------------------------------------------------
# Ingestion (Extract + Validate)
# ---------------------------------------------------------

def ingest_csv(path: str) -> List[OrthopaedicPreference]:
    print(f" Reading CSV from: {path}")
    df = pd.read_csv(path)

    validated_records = []
    errors = 0

    for idx, row in df.iterrows():
        try:
            record = OrthopaedicPreference(**row.to_dict())
            validated_records.append(record)
        except ValidationError as e:
            errors += 1
            print(f" Validation error at row {idx}: {e}")

    print(f" Successfully validated {len(validated_records)} records")
    if errors > 0:
        print(f" {errors} rows failed validation and were skipped")

    return validated_records


# ---------------------------------------------------------
# Load to Postgres
# ---------------------------------------------------------

def load_to_postgres(records: List[OrthopaedicPreference], conn_string: str):
    print("Connecting to Postgres...")
    conn = conn = psycopg2.connect(
    dbname="surgical_data_platform",
    user="your_username",   #  change this to your user
    password="your_password", # Change this to your password
    host="localhost",
    port="5432"
)
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO staging.orthopaedic_preferences (
            surgeon_id, surgeon_name, speciality, subspecialty,
            procedure, instrument, preferred_retractor_size,
            preferred_drill_brand, needs_backup_suction,
            years_of_experience, hospital_affiliation,
            generation_timestamp
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    for r in records:
        cur.execute(insert_sql, (
            r.surgeon_id,
            r.surgeon_name,
            r.speciality,
            r.subspecialty,
            r.procedure,
            r.instrument,
            r.preferred_retractor_size,
            r.preferred_drill_brand,
            r.needs_backup_suction,
            r.years_of_experience,
            r.hospital_affiliation,
            r.generation_timestamp
        ))

    conn.commit()
    cur.close()
    conn.close()
    print("Data successfully loaded into Postgres")


# ---------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------

def run_pipeline():
    csv_path = "data/orthopaedic_preferences.csv"
    conn_string = "postgresql://postgres:password@localhost:5432/theatre"

    print(" Starting orthopaedic preference ingestion pipeline...")

    records = ingest_csv(csv_path)
    load_to_postgres(records, conn_string)

    print(" Pipeline completed successfully")


if __name__ == "__main__":
    run_pipeline()
