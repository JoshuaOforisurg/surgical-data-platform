# models/normalised.py
from pydantic import BaseModel

class NormalisedPreferenceItem(BaseModel):
    """
    Represents the clean relational record ready for direct Postgres insertion.
    """
    surgeon_id: int
    procedure_id: int
    item_id: int
    mandatory: bool
    quantity: int
    notes: str | None = None
