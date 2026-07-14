from __future__ import annotations

import random

from generate_synthetic_data import shared_catalogue


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
    specialty = random.choice(shared_catalogue.SPECIALTIES)

    # ---------------------------------------------------------
    # 2. Choose a subspecialty within that specialty
    # ---------------------------------------------------------
    subspecialty = random.choice(shared_catalogue.SUBSPECIALTIES[specialty])

    # ---------------------------------------------------------
    # 3. Choose a procedure from that subspecialty
    # ---------------------------------------------------------
    procedure_list = shared_catalogue.PROCEDURES[subspecialty]
    procedure_data = random.choice(procedure_list)

    # ---------------------------------------------------------
    # 4. Validate that the procedure exists in the profiles
    # ---------------------------------------------------------
    procedure_name = procedure_data["name"]

    if procedure_name not in shared_catalogue.CLINICAL_PREFERENCE_PROFILES:
        raise ValueError(
            f"Procedure '{procedure_name}' has no matching profile in CLINICAL_PREFERENCE_PROFILES."
        )

    return specialty, subspecialty, procedure_data
