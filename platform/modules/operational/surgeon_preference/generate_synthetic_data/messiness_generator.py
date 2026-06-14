# messiness_generator.py
import random
from copy import deepcopy


def introduce_typo(text: str) -> str:
    """Simulates a keyboard fat-finger typo by swapping, doubling, or omitting characters."""
    if not text or len(text) < 4:
        return text

    text_list = list(text)
    idx = random.randint(1, len(text_list) - 2)

    corruption_type = random.choice(["swap", "double", "omit"])
    if corruption_type == "swap":
        text_list[idx], text_list[idx + 1] = text_list[idx + 1], text_list[idx]
    elif corruption_type == "double":
        text_list.insert(idx, text_list[idx])
    elif corruption_type == "omit":
        text_list.pop(idx)

    return "".join(text_list)


def random_casing(text: str) -> str:
    """Randomly applies upper, lower, title, or mixed casing."""
    if not text:
        return text

    styles = [
        text.upper(),
        text.lower(),
        text.title(),
        "".join(
            c.upper() if random.random() < 0.5 else c.lower()
            for c in text
        )
    ]
    return random.choice(styles)


def apply_messiness(card_record):
    """
    Accepts a clean Pydantic card record, makes a deep copy,
    and selectively corrupts fields to simulate real-world NHS data.
    """
    messy = deepcopy(card_record)

    # ---------------------------------------------------------
    # 1. Surgeon name casing
    # ---------------------------------------------------------
    if random.random() < 0.3:
        messy.surgeon.full_name = random_casing(messy.surgeon.full_name)

    # ---------------------------------------------------------
    # 2. Procedure name whitespace + casing
    # ---------------------------------------------------------
    if random.random() < 0.25:
        messy.procedure.name = f"  {random_casing(messy.procedure.name)}   "

    # ---------------------------------------------------------
    # 3. Corrupt OPCS/ICD codes
    # ---------------------------------------------------------
    if random.random() < 0.25:
        messy.procedure.procedure_codes = [
            c.replace(".", "").replace(" ", "  ")
            for c in messy.procedure.procedure_codes
        ]

    if random.random() < 0.25:
        messy.procedure.diagnosis_codes = [
            introduce_typo(c) if random.random() < 0.3 else c
            for c in messy.procedure.diagnosis_codes
        ]

    # ---------------------------------------------------------
    # 4. Special instructions typo
    # ---------------------------------------------------------
    if messy.special_instructions and messy.special_instructions.notes:
        if random.random() < 0.4:
            messy.special_instructions.notes = introduce_typo(
                messy.special_instructions.notes
            )

    # ---------------------------------------------------------
    # 5. Randomly drop glove size
    # ---------------------------------------------------------
    if random.random() < 0.15:
        messy.surgeon.glove_size = None

    # ---------------------------------------------------------
    # 6. Corrupt instrument quantities
    # ---------------------------------------------------------
    for inst in messy.instruments:
        if random.random() < 0.1:
            inst.quantity = random.choice([None, -1, 999])

    # ---------------------------------------------------------
    # 7. Dirty whitespace on free-text fields
    # ---------------------------------------------------------
    if random.random() < 0.2:
        messy.specialty = f" {messy.specialty}  "

    return messy
