from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import pandas as pd

from bronze_Ingestion.catalog import (
    DEFAULT_ORGANISATION_ID,
    DEFAULT_ORGANISATION_NAME,
    BronzeCatalogRepository,
)
from config.settings import PostgresSettings


CURRENT_CARD_STATUS = "active"
APPROVED_DRAFT_STATUS = "approved_pending_publish"


@dataclass(frozen=True)
class PreferenceCardImportSummary:
    enabled: bool
    imported: int = 0
    organisation_id: str = DEFAULT_ORGANISATION_ID
    source_gold_key: str = ""
    message: str = ""


@dataclass(frozen=True)
class PreferenceCardPublishSummary:
    enabled: bool
    published: bool = False
    card_id: str = ""
    version_id: str = ""
    version_number: int = 0
    organisation_id: str = DEFAULT_ORGANISATION_ID
    message: str = ""


@dataclass(frozen=True)
class PreferenceCardRollbackSummary:
    enabled: bool
    rolled_back: bool = False
    card_id: str = ""
    rollback_version_id: str = ""
    source_version_id: str = ""
    from_version_number: int = 0
    to_version_number: int = 0
    organisation_id: str = DEFAULT_ORGANISATION_ID
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


def current_card_rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert operational Postgres current-card rows back into the dataframe shape
    used by the Streamlit preference-card renderer.
    """
    flattened_rows: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("card_payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        version_number = row.get("current_version_number") or payload.get("version_number")
        flattened = {
            **payload,
            "card_id": str(row.get("card_id") or ""),
            "card_key": row.get("card_key") or payload.get("card_key", ""),
            "surgeon_id": row.get("surgeon_id") or payload.get("surgeon_id", ""),
            "surgeon_name": row.get("surgeon_name") or payload.get("surgeon_name", ""),
            "procedure_id": row.get("procedure_id") or payload.get("procedure_id", ""),
            "procedure": row.get("procedure_name") or payload.get("procedure", ""),
            "procedure_name": row.get("procedure_name") or payload.get("procedure_name", ""),
            "specialty": row.get("specialty") or payload.get("specialty", ""),
            "subspecialty": row.get("subspecialty") or payload.get("subspecialty", ""),
            "preference_card_version": version_number,
            "preference_card_version_label": payload.get("preference_card_version_label")
            or f"v{version_number or 1}",
            "version_number": version_number,
            "version_updated_by": row.get("published_by") or payload.get("version_updated_by", ""),
            "version_updated_at": row.get("published_at") or payload.get("version_updated_at", ""),
            "source_gold_key": row.get("source_gold_key") or payload.get("source_gold_key", ""),
            "operational_source": "postgres",
        }
        flattened_rows.append(flattened)

    return pd.DataFrame(flattened_rows)


def build_published_card_payload(
    current_payload: dict[str, Any],
    draft: dict[str, Any],
    publisher: str,
    editable_fields: list[str],
    published_at: str,
) -> dict[str, Any]:
    if draft.get("status") != APPROVED_DRAFT_STATUS:
        raise ValueError("Only approved_pending_publish drafts can be published.")

    proposed = draft.get("proposed") or {}
    payload = dict(current_payload or {})

    if draft.get("draft_type") == "create":
        payload.update(
            {
                "surgeon_id": draft.get("surgeon_id", ""),
                "surgeon_name": draft.get("surgeon_name", ""),
                "specialty": draft.get("specialty", ""),
                "subspecialty": draft.get("subspecialty", ""),
                "procedure": draft.get("procedure", ""),
                "procedure_id": draft.get("procedure_id", ""),
                "version_number": 1,
                "preference_card_version": 1,
                "preference_card_version_label": "v1",
                "is_current": True,
            }
        )
    elif not payload:
        raise ValueError("Approved edit draft does not match an operational preference card.")

    next_version = (
        1
        if draft.get("draft_type") == "create"
        else _safe_version_number(payload.get("preference_card_version") or payload.get("version_number")) + 1
    )

    for field in editable_fields:
        if field in proposed:
            payload[field] = proposed[field]

    payload.update(
        {
            "version_number": next_version,
            "preference_card_version": next_version,
            "preference_card_version_label": f"v{next_version}",
            "version_updated_by": publisher,
            "version_updated_at": published_at,
            "is_current": True,
        }
    )
    return normalise_gold_card_row(payload)


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
                        change_type="pipeline_import",
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

    def list_card_history(
        self,
        surgeon_name: str,
        procedure_name: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        surgeon_name = _clean_text(surgeon_name)
        procedure_name = _clean_text(procedure_name)
        if not surgeon_name or not procedure_name:
            return []

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        cards.card_id,
                        cards.organisation_id,
                        cards.card_key,
                        cards.surgeon_name,
                        cards.procedure_name,
                        versions.version_id,
                        versions.version_number,
                        versions.version_label,
                        versions.source_gold_key,
                        versions.published_by,
                        versions.published_at,
                        versions.change_type,
                        versions.source_version_id,
                        versions.change_reason,
                        versions.is_current,
                        versions.created_at
                    FROM app_workflow.preference_cards cards
                    JOIN app_workflow.preference_card_versions versions
                        ON cards.card_id = versions.card_id
                    WHERE cards.organisation_id = %s
                      AND cards.surgeon_name = %s
                      AND cards.procedure_name = %s
                    ORDER BY versions.version_number DESC, versions.created_at DESC
                    LIMIT %s
                    """,
                    (organisation_id, surgeon_name, procedure_name, limit),
                )
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def publish_approved_draft(
        self,
        draft: dict[str, Any],
        publisher: str,
        editable_fields: list[str],
        source_gold_key: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        published_at: str | None = None,
    ) -> PreferenceCardPublishSummary:
        if not self.enabled:
            return PreferenceCardPublishSummary(
                enabled=False,
                organisation_id=organisation_id,
                message="Postgres settings are not configured.",
            )

        published_at = published_at or datetime.now(UTC).isoformat()
        lookup_payload = {
            "surgeon_id": draft.get("surgeon_id"),
            "surgeon_name": draft.get("surgeon_name"),
            "procedure_id": draft.get("procedure_id"),
            "procedure": draft.get("procedure"),
            "procedure_name": draft.get("procedure"),
        }
        card_key = card_key_for_row(lookup_payload)

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                current_card = self._load_current_card_for_update(
                    cur,
                    organisation_id=organisation_id,
                    card_key=card_key,
                )
                current_payload = (
                    dict(current_card["card_payload"])
                    if current_card and isinstance(current_card.get("card_payload"), dict)
                    else {}
                )
                published_payload = build_published_card_payload(
                    current_payload=current_payload,
                    draft=draft,
                    publisher=publisher,
                    editable_fields=editable_fields,
                    published_at=published_at,
                )
                self._upsert_current_card(
                    cur=cur,
                    row=published_payload,
                    organisation_id=organisation_id,
                    source_gold_key=source_gold_key,
                    imported_by=publisher,
                    imported_at=published_at,
                    change_type="draft_publish",
                )
                published_card = self._load_current_card_for_update(
                    cur,
                    organisation_id=organisation_id,
                    card_key=published_payload["card_key"],
                )
            conn.commit()

        return PreferenceCardPublishSummary(
            enabled=True,
            published=True,
            card_id=str(published_card.get("card_id") or "") if published_card else "",
            version_id=str(published_card.get("version_id") or "") if published_card else "",
            version_number=int(published_payload["version_number"]),
            organisation_id=organisation_id,
            message=f"Published operational card version v{published_payload['version_number']}.",
        )

    def rollback_to_version(
        self,
        card_id: str,
        source_version_id: str,
        actor_email: str,
        actor_name: str,
        actor_roles: list[str],
        reason: str,
        source_gold_key: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        rolled_back_at: str | None = None,
    ) -> PreferenceCardRollbackSummary:
        if not self.enabled:
            return PreferenceCardRollbackSummary(
                enabled=False,
                organisation_id=organisation_id,
                message="Postgres settings are not configured.",
            )

        reason = _clean_text(reason)
        if not reason:
            raise ValueError("Rollback reason is required.")

        rolled_back_at = rolled_back_at or datetime.now(UTC).isoformat()
        rollback_version_id = str(uuid.uuid4())

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                current = self._load_current_card_by_id_for_update(
                    cur,
                    organisation_id=organisation_id,
                    card_id=card_id,
                )
                if not current:
                    raise ValueError("Current preference card was not found.")
                if str(current["version_id"]) == str(source_version_id):
                    raise ValueError("Cannot rollback to the current version.")

                source = self._load_version_for_card(
                    cur,
                    organisation_id=organisation_id,
                    card_id=card_id,
                    version_id=source_version_id,
                )
                if not source:
                    raise ValueError("Rollback source version was not found.")

                from_version_number = int(current["current_version_number"])
                to_version_number = from_version_number + 1
                source_payload = dict(source["card_payload"])
                rollback_payload = {
                    **source_payload,
                    "version_number": to_version_number,
                    "preference_card_version": to_version_number,
                    "preference_card_version_label": f"v{to_version_number}",
                    "version_updated_by": actor_email or actor_name,
                    "version_updated_at": rolled_back_at,
                    "is_current": True,
                }
                rollback_payload = normalise_gold_card_row(rollback_payload)

                cur.execute(
                    """
                    UPDATE app_workflow.preference_card_versions
                    SET is_current = false
                    WHERE card_id = %s
                    """,
                    (card_id,),
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
                        change_type,
                        source_version_id,
                        change_reason,
                        is_current
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'rollback', %s, %s, true)
                    """,
                    (
                        rollback_version_id,
                        card_id,
                        organisation_id,
                        to_version_number,
                        f"v{to_version_number}",
                        Json(rollback_payload),
                        source_gold_key,
                        actor_email or actor_name,
                        rolled_back_at,
                        source_version_id,
                        reason,
                    ),
                )
                cur.execute(
                    """
                    UPDATE app_workflow.preference_cards
                    SET current_version_id = %s,
                        current_version_number = %s,
                        source_gold_key = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE card_id = %s
                      AND organisation_id = %s
                    """,
                    (
                        rollback_version_id,
                        to_version_number,
                        source_gold_key,
                        card_id,
                        organisation_id,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "preference_card_rollback_published",
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        "preference_card",
                        card_id,
                        Json(
                            {
                                "card_id": card_id,
                                "rollback_version_id": rollback_version_id,
                                "source_version_id": source_version_id,
                                "from_version_number": from_version_number,
                                "to_version_number": to_version_number,
                                "rollback_reason": reason,
                                "surgeon_name": current.get("surgeon_name"),
                                "procedure_name": current.get("procedure_name"),
                                "organisation_id": organisation_id,
                            }
                        ),
                    ),
                )
            conn.commit()

        return PreferenceCardRollbackSummary(
            enabled=True,
            rolled_back=True,
            card_id=card_id,
            rollback_version_id=rollback_version_id,
            source_version_id=source_version_id,
            from_version_number=from_version_number,
            to_version_number=to_version_number,
            organisation_id=organisation_id,
            message=f"Created rollback version v{to_version_number} from version {source.get('version_label')}.",
        )

    @staticmethod
    def _load_current_card_for_update(cur, organisation_id: str, card_key: str) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT
                cards.card_id,
                cards.card_key,
                cards.current_version_number,
                versions.version_id,
                versions.card_payload
            FROM app_workflow.preference_cards cards
            JOIN app_workflow.preference_card_versions versions
                ON cards.current_version_id = versions.version_id
            WHERE cards.organisation_id = %s
              AND cards.card_key = %s
              AND cards.status = %s
            FOR UPDATE OF cards
            """,
            (organisation_id, card_key, CURRENT_CARD_STATUS),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def _load_current_card_by_id_for_update(
        cur,
        organisation_id: str,
        card_id: str,
    ) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT
                cards.card_id,
                cards.organisation_id,
                cards.surgeon_name,
                cards.procedure_name,
                cards.current_version_number,
                versions.version_id,
                versions.card_payload
            FROM app_workflow.preference_cards cards
            JOIN app_workflow.preference_card_versions versions
                ON cards.current_version_id = versions.version_id
            WHERE cards.organisation_id = %s
              AND cards.card_id = %s
              AND cards.status = %s
            FOR UPDATE OF cards
            """,
            (organisation_id, card_id, CURRENT_CARD_STATUS),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def _load_version_for_card(
        cur,
        organisation_id: str,
        card_id: str,
        version_id: str,
    ) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT
                version_id,
                card_id,
                organisation_id,
                version_number,
                version_label,
                card_payload,
                is_current
            FROM app_workflow.preference_card_versions
            WHERE organisation_id = %s
              AND card_id = %s
              AND version_id = %s
            """,
            (organisation_id, card_id, version_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None

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
        change_type: str,
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
                change_type,
                is_current
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (card_id, version_number)
            DO UPDATE SET version_label = EXCLUDED.version_label,
                          card_payload = EXCLUDED.card_payload,
                          source_gold_key = EXCLUDED.source_gold_key,
                          published_by = EXCLUDED.published_by,
                          published_at = EXCLUDED.published_at,
                          change_type = EXCLUDED.change_type,
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
                change_type,
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
