# messiness_generator.py
import random
from copy import deepcopy


def introduce_typo(text: str) -> str:
    """Simulates a keyboard fat-finger typo by swapping or doubling characters."""
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


def apply_messiness(card_record):
    """
    Accepts a clean Pydantic card record, makes a deep copy,
    and selectively corrupts fields to simulate real-world legacy hospital data.
    """
    # Create a deep copy so we don't accidentally ruin our clean object data in memory
    messy_card = deepcopy(card_record)

    # 1. Simulate inconsistent casing in names (e.g., MR. JAMES GATE or mr. james gate)
    if random.random() < 0.3:
        messy_card.surgeon.full_name = random.choice([
            messy_card.surgeon.full_name.upper(),
            messy_card.surgeon.full_name.lower()
        ])

    # 2. Introduce formatting typos into OPCS-4 codes (e.g., "W20.1 Z58.2" -> "W201. Z582")
    if random.random() < 0.25:
        # Strip decimal points or jumble spaces
        code = messy_card.procedure.code
        messy_card.procedure.code = code.replace(".", "").replace(" ", "  ")

    # 3. Simulate human typos in free-text fields
    if messy_card.special_instructions and messy_card.special_instructions.notes:
        if random.random() < 0.4:
            messy_card.special_instructions.notes = introduce_typo(messy_card.special_instructions.notes)

    # 4. Introduce structural truncation or missing optional values (Simulating form dropouts)
    if random.random() < 0.15:
        messy_card.surgeon.glove_size = None  # Randomly dropped out attribute

    # 5. Add dirty whitespace padding to string fields
    if random.random() < 0.3:
        messy_card.procedure.name = f"   {messy_card.procedure.name}  "

    # 6. Corrupt instrument quantities (e.g., negative numbers or massive numbers due to typos)
    if messy_card.instruments:
        for inst in messy_card.instruments:
            if random.random() < 0.1:
                inst.quantity = random.choice([-1, 999, None])
                if inst.notes is None:
                    inst.notes = "QTY UNKNOWN - VERIFY"

    return messy_card
