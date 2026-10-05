from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from bronze_Ingestion.catalog import (
    DEFAULT_ORGANISATION_ID,
    DEFAULT_ORGANISATION_NAME,
    BronzeCatalogRepository,
)
from config.settings import PostgresSettings


CURRENT_CARD_STATUS = "active"


@dataclass(frozen=True)
class PreferenceCardImportSummary:
    enabled: bool
    imported: int = 0
    organisation_id: str = DEFAULT_ORGANISATION_ID
    source_gold_key: str = ""
    message: str = ""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_version_number(value: Any) -> int:
    try:
        version = int(float(value))
    except (TypeError, ValueError):
        return 1
    return max(version, 1)


def card_key_for_row(row: dict[str, Any]) -> str:
    """
    Stable product key for a current card.

    Prefer source IDs when present. Fall back to names so imported synthetic or
    legacy cards without IDs can still be versioned deterministically.
    """
    surgeon = _clean_text(row.get("surgeon_id")) or _clean_text(row.get("surgeon_name")).lower()
    procedure = (
        _clean_text(row.get("procedure_id"))
        or _clean_text(row.get("procedure"))
        or _clean_text(row.get("procedure_name"))
    ).lower()
    digest = hashlib.sha256(f"{surgeon}|{procedure}".encode("utf-8")).hexdigest()[:16]
    return f"card_{digest}"


def normalise_gold_card_row(row: dict[str, Any]) -> dict[str, Any]:
    surgeon_name = _clean_text(row.get("surgeon_name"))
    procedure_name = _clean_text(row.get("procedure")) or _clean_text(row.get("procedure_name"))
    if not surgeon_name:
        raise ValueError("surgeon_name is required.")
    if not procedure_name:
        raise ValueError("procedure/procedure_name is required.")

    version_number = _safe_version_number(
        row.get("preference_card_version") or row.get("version_number")
    )
    normalised = {
        **row,
        "card_key": card_key_for_row(row),
        "surgeon_id": _clean_text(row.get("surgeon_id")),
        "surgeon_name": surgeon_name,
        "procedure_id": _clean_text(row.get("procedure_id")),
        "procedure_name": procedure_name,
        "specialty": _clean_text(row.get("specialty")),
        "subspecialty": _clean_text(row.get("subspecialty")),
        "version_number": version_number,
        "version_label": _clean_text(row.get("preference_card_version_label")) or f"v{version_number}",
    }
    return normalised


class PreferenceCardRepository:
    def __init__(self, settings: PostgresSettings | None):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings is not None

    def initialise(self) -> None:
        BronzeCatalogRepository(self.settings).initialise()

    def import_gold_rows(
        self,
        rows: Iterable[dict[str, Any]],
        source_gold_key: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        organisation_name: str = DEFAULT_ORGANISATION_NAME,
        imported_by: str = "pipeline",
        imported_at: str | None = None,
    ) -> PreferenceCardImportSummary:
        if not self.enabled:
            return PreferenceCardImportSummary(
                enabled=False,
                organisation_id=organisation_id,
                source_gold_key=source_gold_key,
                message="Postgres settings are not configured.",
            )

        normalised_rows = [normalise_gold_card_row(dict(row)) for row in rows]
        imported_at = imported_at or datetime.now(UTC).isoformat()

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                self._ensure_organisation(cur, organisation_id, organisation_name)
                for row in normalised_rows:
                    self._upsert_current_card(
                        cur=cur,
                        row=row,
                        organisation_id=organisation_id,
                        source_gold_key=source_gold_key,
                        imported_by=imported_by,
                        imported_at=imported_at,
                    )
            conn.commit()

        return PreferenceCardImportSummary(
            enabled=True,
            imported=len(normalised_rows),
            organisation_id=organisation_id,
            source_gold_key=source_gold_key,
            message=f"Imported {len(normalised_rows)} current preference cards.",
        )

    def list_current_cards(
        self,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        cards.card_id,
                        cards.organisation_id,
                        cards.card_key,
                        cards.surgeon_id,
                        cards.surgeon_name,
                        cards.procedure_id,
                        cards.procedure_name,
                        cards.specialty,
                        cards.subspecialty,
                        cards.current_version_number,
                        cards.status,
                        versions.version_id,
                        versions.card_payload,
                        versions.source_gold_key,
                        versions.published_by,
                        versions.published_at,
                        cards.updated_at
                    FROM app_workflow.preference_cards cards
                    JOIN app_workflow.preference_card_versions versions
                        ON cards.current_version_id = versions.version_id
                    WHERE cards.organisation_id = %s
                      AND cards.status = %s
                      AND versions.is_current = true
                    ORDER BY cards.surgeon_name, cards.procedure_name
                    LIMIT %s
                    """,
                    (organisation_id, CURRENT_CARD_STATUS, limit),
                )
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _ensure_organisation(cur, organisation_id: str, organisation_name: str) -> None:
        cur.execute(
            """
            INSERT INTO app_workflow.organisations (
                organisation_id,
                organisation_name,
                status
            )
            VALUES (%s, %s, 'active')
            ON CONFLICT (organisation_id)
            DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (organisation_id, organisation_name),
        )

    @staticmethod
    def _upsert_current_card(
        cur,
        row: dict[str, Any],
        organisation_id: str,
        source_gold_key: str,
        imported_by: str,
        imported_at: str,
    ) -> None:
        card_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        version_number = row["version_number"]

        cur.execute(
            """
            INSERT INTO app_workflow.preference_cards (
                card_id,
                organisation_id,
                card_key,
                surgeon_id,
                surgeon_name,
                procedure_id,
                procedure_name,
                specialty,
                subspecialty,
                current_version_number,
                status,
                source_gold_key
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (organisation_id, card_key)
            DO UPDATE SET surgeon_id = EXCLUDED.surgeon_id,
                          surgeon_name = EXCLUDED.surgeon_name,
                          procedure_id = EXCLUDED.procedure_id,
                          procedure_name = EXCLUDED.procedure_name,
                          specialty = EXCLUDED.specialty,
                          subspecialty = EXCLUDED.subspecialty,
                          current_version_number = EXCLUDED.current_version_number,
                          status = EXCLUDED.status,
                          source_gold_key = EXCLUDED.source_gold_key,
                          updated_at = CURRENT_TIMESTAMP
            RETURNING card_id
            """,
            (
                card_id,
                organisation_id,
                row["card_key"],
                row["surgeon_id"],
                row["surgeon_name"],
                row["procedure_id"],
                row["procedure_name"],
                row["specialty"],
                row["subspecialty"],
                version_number,
                CURRENT_CARD_STATUS,
                source_gold_key,
            ),
        )
        persisted_card_id = str(cur.fetchone()["card_id"])

        cur.execute(
            """
            UPDATE app_workflow.preference_card_versions
            SET is_current = false
            WHERE card_id = %s
            """,
            (persisted_card_id,),
        )
        cur.execute(
            """
            INSERT INTO app_workflow.preference_card_versions (
                version_id,
                card_id,
                organisation_id,
                version_number,
                version_label,
                card_payload,
                source_gold_key,
                published_by,
                published_at,
                is_current
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (card_id, version_number)
            DO UPDATE SET version_label = EXCLUDED.version_label,
                          card_payload = EXCLUDED.card_payload,
                          source_gold_key = EXCLUDED.source_gold_key,
                          published_by = EXCLUDED.published_by,
                          published_at = EXCLUDED.published_at,
                          is_current = true
            RETURNING version_id
            """,
            (
                version_id,
                persisted_card_id,
                organisation_id,
                version_number,
                row["version_label"],
                Json(row),
                source_gold_key,
                imported_by,
                imported_at,
            ),
        )
        persisted_version_id = str(cur.fetchone()["version_id"])
        cur.execute(
            """
            UPDATE app_workflow.preference_cards
            SET current_version_id = %s,
                current_version_number = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE card_id = %s
            """,
            (persisted_version_id, version_number, persisted_card_id),
        )
