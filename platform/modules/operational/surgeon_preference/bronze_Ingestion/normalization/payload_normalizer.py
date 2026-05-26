from pydantic import BaseModel, Field, field_validator
from typing import Optional


class NormalisedPreferenceItem(BaseModel):
    """
    Canonical cleaned record ready for Postgres insertion.
    """

    surgeon_id: int
    procedure_id: int
    item_id: int

    mandatory: bool = Field(default=False)
    quantity: int = Field(gt=0)

    notes: Optional[str] = None

    # Optional but highly useful for surgical preference systems
    category: Optional[str] = None
    sequence: Optional[int] = None

    @field_validator("mandatory", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"true", "1", "yes", "y"}
        return bool(v)

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_quantity(cls, v):
        if v is None:
            return 1
        try:
            return int(float(v))
        except Exception:
            raise ValueError(f"Invalid quantity value: {v}")

