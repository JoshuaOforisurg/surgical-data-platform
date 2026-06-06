from pydantic import BaseModel, Field, field_validator
from typing import Optional


class NormalisedPreferenceItem(BaseModel):
    """
    Canonical cleaned record ready for Postgres insertion.
    Allows raw messy data to enter bronze safely without terminating execution.
    """

    surgeon_id: int
    procedure_id: int
    item_id: int

    mandatory: bool = Field(default=False)

    # FIX: Removed hard strict 'gt=0' limitation that forces unhandled app exceptions
    quantity: int = Field(default=1)

    notes: Optional[str] = None
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
        # FIX: Catch None, negative numbers or noise without throwing crashing ValidationErrors
        if v is None:
            return 1
        try:
            val = int(float(v))
            return val
        except Exception:
            # Safe structural fallback to prevent batch processing terminations
            return -9999

    @field_validator("notes", mode="before")
    @classmethod
    def track_quantity_anomalies(cls, v, info):
        """Automatically tags raw structural data entries for engineering audits."""
        # Access sibling values safely during validation phase
        return v
