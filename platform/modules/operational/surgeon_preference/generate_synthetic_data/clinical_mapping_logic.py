# clinical_mapping_logic.py
# Fully aligned with mock_data.py

import random
from generate_synthetic_data import mock_data


def generate_clinical_mapping():
    """
    Returns:
        specialty (str)
        subspecialty (str)
        procedure_data (dict)  # includes name + codes
    """

    # ---------------------------------------------------------
    # 1. Choose a specialty
    # ---------------------------------------------------------
    specialty = random.choice(mock_data.SPECIALTIES)

    # ---------------------------------------------------------
    # 2. Choose a subspecialty within that specialty
    # ---------------------------------------------------------
    subspecialty = random.choice(mock_data.SUBSPECIALTIES[specialty])

    # ---------------------------------------------------------
    # 3. Choose a procedure from that subspecialty
    # ---------------------------------------------------------
    procedure_list = mock_data.PROCEDURES[subspecialty]
    procedure_data = random.choice(procedure_list)

    # ---------------------------------------------------------
    # 4. Validate that the procedure exists in the profiles
    # ---------------------------------------------------------
    procedure_name = procedure_data["name"]

    if procedure_name not in mock_data.CLINICAL_PREFERENCE_PROFILES:
        raise ValueError(
            f"Procedure '{procedure_name}' has no matching profile in CLINICAL_PREFERENCE_PROFILES."
        )

    return specialty, subspecialty, procedure_data
