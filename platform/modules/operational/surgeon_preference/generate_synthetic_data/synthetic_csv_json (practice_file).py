import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from faker import Faker

# Set random seed for reproducibility
random.seed(42)
fake = Faker()

# Global messiness level (adjust as needed)
MESSINESS_LEVEL = 0.2

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# -------------------------------------------------
# Domain Data Loading (from external JSON files)
# -------------------------------------------------
def load_domain_data() -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Load orthopaedic subspecialties and instruments from external JSON files.

    Returns:
        tuple: (orthopaedic_subspecialties, instruments_by_subspecialty)
    """
    try:
        import json
        with open(os.path.join(BASE_DIR, "orthopaedic_subspecialties.json")) as f:
            orthopaedic_subspecialties = json.load(f)
        with open(os.path.join(BASE_DIR, "instruments_by_subspecialty.json")) as f:
            instruments_by_subspecialty = json.load(f)
        return orthopaedic_subspecialties, instruments_by_subspecialty
    except FileNotFoundError as e:
        raise FileNotFoundError("Domain data files not found. Ensure 'orthopaedic_subspecialties.json' and 'instruments_by_subspecialty.json' exist in the script directory.") from e
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON format in domain data files.") from e

orthopaedic_subspecialties, instruments_by_subspecialty = load_domain_data()

# -------------------------------------------------
# Messiness Helpers
# -------------------------------------------------

def maybe_null(value: Any) -> Any:
    """
    Randomly set a value to None based on MESSINESS_LEVEL.

    Args:
        value: The value to potentially set to None.

    Returns:
        The original value or None.
    """
    return value if random.random() > MESSINESS_LEVEL else None

def maybe_typo(value: str) -> str:
    """
    Introduce a random typo into a string.

    Args:
        value: The string to potentially introduce a typo into.

    Returns:
        The original string or a version with a typo.
    """
    if not isinstance(value, str):
        return value
    if random.random() < MESSINESS_LEVEL:
        if len(value) > 3:
            i = random.randint(0, len(value) - 2)
            return value[:i] + random.choice("xyz") + value[i + 1:]
    return value

def maybe_case_mess(value: str) -> str:
    """
    Randomly change the case of a string.

    Args:
        value: The string to potentially change the case of.

    Returns:
        The original string or a version with changed case.
    """
    if not isinstance(value, str):
        return value
    if random.random() < MESSINESS_LEVEL:
        return random.choice([value.upper(), value.lower(), value.title()])
    return value

def maybe_extra_spaces(value: str) -> str:
    """
    Randomly add extra spaces to a string.

    Args:
        value: The string to potentially add spaces to.

    Returns:
        The original string or a version with extra spaces.
    """
    if not isinstance(value, str):
        return value
    if random.random() < MESSINESS_LEVEL:
        return f"  {value} " if random.random() < 0.5 else f"{value}   "
    return value

def messy_string(value: Optional[str]) -> Optional[str]:
    """
    Apply all string-related messiness to a value.

    Args:
        value: The string to messify.

    Returns:
        The original string or a messy version.
    """
    if value is None:
        return None
    value = maybe_typo(value)
    value = maybe_case_mess(value)
    value = maybe_extra_spaces(value)
    return value

def messy_boolean() -> Union[bool, str, int, None]:
    """
    Generate a messy boolean value.

    Returns:
        A random boolean, string, or None.
    """
    return random.choice([
        True, False, "true", "false", "TRUE", "FALSE",
        "Yes", "No", "Y", "N", 1, 0, None
    ])

def messy_timestamp() -> Union[str, None]:
    """
    Generate a messy timestamp.

    Returns:
        A timestamp in various formats or None.
    """
    if random.random() < MESSINESS_LEVEL:
        return fake.date_time().strftime("%d/%m/%Y %H:%M")  # non-ISO
    if random.random() < MESSINESS_LEVEL / 2:
        return "INVALID_DATE"
    if random.random() < MESSINESS_LEVEL / 2:
        return None
    return datetime.now().isoformat()

def messy_int() -> Union[int, str, None]:
    """
    Generate a messy integer value.

    Returns:
        A random integer, string, or None.
    """
    return random.choice([
        random.randint(1, 35),
        str(random.randint(1, 35)),
        None,
        "",
        "N/A"
    ])

def messy_id() -> Union[int, str, None]:
    """
    Generate a messy ID.

    Returns:
        A random ID, string, or None.
    """
    return random.choice([
        random.randint(1000, 9999),
        f"ID-{random.randint(1000, 9999)}",
        None,
        "",
        "UNKNOWN"
    ])

# -------------------------------------------------
# Surgeon and Preference Generators
# -------------------------------------------------

def generate_uk_surgeon_name() -> str:
    """
    Generate a messy UK surgeon name with random title and last name.

    Returns:
        A messy surgeon name (e.g., "Mr Smith", "DR JONES").
    """
    title = random.choice(["Mr", "Ms", "Miss", "Mrs", "mr", "MRS", "Dr"])
    name = fake.last_name()
    return messy_string(f"{title} {name}")

def generate_surgeons(n: int = 30) -> List[Dict[str, Any]]:
    """
    Generate a list of messy surgeon records.

    Args:
        n: Number of surgeons to generate.

    Returns:
        List of dictionaries, each representing a surgeon.
    """
    surgeons = []
    for _ in range(n):
        subspecialty = random.choice(list(orthopaedic_subspecialties.keys()))
        surgeons.append({
            "surgeon_id": messy_id(),
            "surgeon_name": messy_string(generate_uk_surgeon_name()),
            "speciality": messy_string(random.choice([
                "Orthopedis", "orthopaedick", "ORTHOPAEDICS", "Ortho", "Ortho ", "OT", None
            ])),
            "subspecialty": messy_string(subspecialty),
            "preferred_retractor_size": messy_string(random.choice([
                "Small", "Medium", "Large", "Extra Large", "XL", "S", None
            ])),
            "preferred_drill_brand": messy_string(random.choice([
                "Stryker", "Depuy Synthes", "Arthrex V300",
                "Zimmer Biomet", "Smith & Nephew", "Medtronic",
                "stryker", "STRYKER", None
            ])),
            "needs_backup_suction": messy_boolean(),
            "years_of_experience": messy_int(),
            "hospital_affiliation": messy_string(random.choice([
                fake.company(),
                fake.company().upper(),
                None,
                "",
                "NHS Trust",
                "Private Clinic"
            ]))
        })
    return surgeons

def generate_preferences(num_records: int = 1000) -> pd.DataFrame:
    """
    Generate a messy DataFrame of orthopaedic preferences.

    Args:
        num_records: Number of records to generate.

    Returns:
        A Pandas DataFrame with messy data.
    """
    surgeons = generate_surgeons()
    rows = []
    for _ in range(num_records):
        surgeon = random.choice(surgeons)
        subspecialty = surgeon["subspecialty"]

        # Ensure subspecialty is a valid key
        if not subspecialty or subspecialty.strip() not in orthopaedic_subspecialties:
            subspecialty = "Joints"  # Fallback to a valid subspecialty

        # Get the list of procedures for the subspecialty
        procedures = orthopaedic_subspecialties.get(subspecialty.strip(), [])
        if not procedures:  # If the list is empty, fallback to a default
            procedures = orthopaedic_subspecialties["Joints"]

        # Get the list of instruments for the subspecialty
        instruments = instruments_by_subspecialty.get(subspecialty.strip(), [])
        if not instruments:  # If the list is empty, fallback to a default
            instruments = instruments_by_subspecialty["Joints"]

        # Sometimes break subspecialty linkage
        if random.random() < MESSINESS_LEVEL:
            subspecialty = random.choice(list(orthopaedic_subspecialties.keys()))
            procedures = orthopaedic_subspecialties.get(subspecialty, [])
            instruments = instruments_by_subspecialty.get(subspecialty, [])

        rows.append({
            **surgeon,
            "procedure": messy_string(random.choice(procedures) if procedures else None),
            "instrument": messy_string(random.choice(instruments) if instruments else None),
            "generation_timestamp": messy_timestamp()
        })
    return pd.DataFrame(rows)
# -------------------------------------------------
# Main Execution
# -------------------------------------------------

if __name__ == "__main__":
    df = generate_preferences(1000)
    print("First 5 rows:")
    print(df.head())
    print("\nDataFrame info:")
    print(df.info())

    # Save to CSV and JSON
    csv_path = os.path.join(DATA_DIR, "orthopaedic_preferences.csv")
    json_path = os.path.join(DATA_DIR, "orthopaedic_preferences_practice.json")

    try:
        df.to_csv(csv_path, index=False)
        print(f"\nData saved to CSV: {csv_path}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

    try:
        df.to_json(json_path, orient="records", indent=2)
        print(f"Data saved to JSON: {json_path}")
    except Exception as e:
        print(f"Error saving JSON: {e}")
