from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .io import read_events
from .models import EventType
from .rules import evaluate_lifecycle, group_events


SOURCE_FILES = ("requests.csv", "suppliers.csv", "kits.csv", "items.csv", "events.csv")
REQUIRED_COLUMNS = {
    "requests": {"kit_request_id", "case_id", "procedure_name", "surgeon_id", "requested_at", "required_by", "priority", "approval_status"},
    "suppliers": {"supplier_id", "supplier_name", "approved", "specialty", "contact_channel"},
    "kits": {"kit_id", "kit_request_id", "supplier_id", "kit_name", "expected_tray_count", "received_tray_count", "current_location", "return_due_at"},
    "items": {"item_id", "kit_id", "item_name", "category", "catalogue_number", "serial_or_lot_number", "expected_quantity", "received_quantity", "used_quantity", "returned_quantity", "expiry_date", "status"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed


def parse_non_negative(row: dict[str, Any], field: str, table: str) -> int:
    try:
        value = int(row[field])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"{table} row {row.get('_source_row')}: invalid {field}") from exc
    if value < 0:
        raise ValueError(f"{table} row {row.get('_source_row')}: {field} cannot be negative")
    return value


class LoanKitMedallionPipeline:
    """Deterministic, synthetic-first Landing/Bronze/Silver/Gold pipeline."""

    def run(self, source_dir: Path, output_dir: Path, as_of: datetime) -> dict[str, Any]:
        source_dir, output_dir = Path(source_dir), Path(output_dir)
        if as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        missing = [name for name in SOURCE_FILES if not (source_dir / name).is_file()]
        if missing:
            raise ValueError(f"missing source files: {', '.join(missing)}")
        landing, bronze, silver, gold = (output_dir / name for name in ("landing", "bronze", "silver", "gold"))
        for directory in (landing, bronze, silver, gold):
            directory.mkdir(parents=True, exist_ok=True)

        landing_manifest = self.land(source_dir, landing)
        bronze_tables = self.bronze(landing, bronze)
        silver_tables, findings = self.silver(bronze_tables, landing, silver)
        gold_counts, workflow_findings = self.gold(silver_tables, landing, gold, as_of)
        all_findings = findings + workflow_findings
        manifest = {
            "pipeline_version": __version__,
            "as_of": as_of.isoformat(),
            "quality_status": "failed" if any(row["severity"] == "error" for row in all_findings) else "passed",
            "quality_findings": len(all_findings),
            "stages": {
                "landing": landing_manifest,
                "bronze": {name: len(rows) for name, rows in bronze_tables.items()},
                "silver": {name: len(rows) for name, rows in silver_tables.items()},
                "gold": gold_counts,
            },
        }
        stable = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        manifest["run_id"] = hashlib.sha256(stable.encode()).hexdigest()[:16]
        write_json(output_dir / "pipeline_manifest.json", manifest)
        write_json(gold / "quality_report.json", {
            "status": manifest["quality_status"],
            "error_count": sum(row["severity"] == "error" for row in all_findings),
            "warning_count": sum(row["severity"] == "warning" for row in all_findings),
            "findings": all_findings,
        })
        return manifest

    def land(self, source_dir: Path, landing: Path) -> dict[str, Any]:
        files = []
        for name in SOURCE_FILES:
            target = landing / name
            shutil.copyfile(source_dir / name, target)
            files.append({"file": name, "sha256": sha256(target), "bytes": target.stat().st_size})
        result = {"file_count": len(files), "files": files}
        write_json(landing / "manifest.json", result)
        return result

    def bronze(self, landing: Path, bronze: Path) -> dict[str, list[dict[str, Any]]]:
        tables = {}
        for filename in SOURCE_FILES:
            name = filename.removesuffix(".csv")
            rows = read_csv(landing / filename)
            if name != "events":
                missing = REQUIRED_COLUMNS[name] - set(rows[0] if rows else [])
                if missing:
                    raise ValueError(f"{filename} missing columns: {', '.join(sorted(missing))}")
            enriched = [{**row, "_source_file": filename, "_source_row": line} for line, row in enumerate(rows, 2)]
            tables[name] = enriched
            with (bronze / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
                for row in enriched:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
        return tables

    def silver(self, bronze: dict[str, list[dict[str, Any]]], landing: Path, silver: Path) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
        requests = [self.normalise_request(row) for row in bronze["requests"]]
        suppliers = [self.normalise_supplier(row) for row in bronze["suppliers"]]
        kits = [self.normalise_kit(row) for row in bronze["kits"]]
        items = [self.normalise_item(row) for row in bronze["items"]]
        events = []
        for event in read_events(landing / "events.csv"):
            row = asdict(event)
            row.update(event_type=event.event_type.value, occurred_at=event.occurred_at.isoformat(), required_by=event.required_by.isoformat() if event.required_by else "")
            events.append(row)
        tables = {"requests": requests, "suppliers": suppliers, "kits": kits, "items": items, "events": events}
        findings = self.relationship_findings(tables)
        for name, rows in tables.items():
            write_json(silver / f"{name}.json", rows)
        write_json(silver / "quality_findings.json", findings)
        return tables, findings

    def normalise_request(self, row: dict[str, Any]) -> dict[str, Any]:
        result = {key: row[key].strip() for key in REQUIRED_COLUMNS["requests"]}
        result.update(requested_at=parse_datetime(row["requested_at"]).isoformat(), required_by=parse_datetime(row["required_by"]).isoformat(), _source_file=row["_source_file"], _source_row=row["_source_row"])
        return result

    def normalise_supplier(self, row: dict[str, Any]) -> dict[str, Any]:
        approved = row["approved"].strip().lower()
        if approved not in {"true", "false"}:
            raise ValueError(f"suppliers row {row['_source_row']}: approved must be true or false")
        result = {key: row[key].strip() for key in REQUIRED_COLUMNS["suppliers"]}
        result.update(approved=approved == "true", _source_file=row["_source_file"], _source_row=row["_source_row"])
        return result

    def normalise_kit(self, row: dict[str, Any]) -> dict[str, Any]:
        result = {key: row[key].strip() for key in REQUIRED_COLUMNS["kits"]}
        result.update(expected_tray_count=parse_non_negative(row, "expected_tray_count", "kits"), received_tray_count=parse_non_negative(row, "received_tray_count", "kits"), _source_file=row["_source_file"], _source_row=row["_source_row"])
        if result["return_due_at"]:
            result["return_due_at"] = parse_datetime(result["return_due_at"]).isoformat()
        return result

    def normalise_item(self, row: dict[str, Any]) -> dict[str, Any]:
        categories = {"instrument", "implant", "consumable"}
        statuses = {"expected", "received", "missing", "damaged", "used", "implanted", "wasted", "returned"}
        result = {key: row[key].strip() for key in REQUIRED_COLUMNS["items"]}
        result["category"], result["status"] = result["category"].lower(), result["status"].lower()
        if result["category"] not in categories or result["status"] not in statuses:
            raise ValueError(f"items row {row['_source_row']}: unsupported category or status")
        for field in ("expected_quantity", "received_quantity", "used_quantity", "returned_quantity"):
            result[field] = parse_non_negative(row, field, "items")
        result.update(_source_file=row["_source_file"], _source_row=row["_source_row"])
        return result

    def relationship_findings(self, tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
        requests = {row["kit_request_id"] for row in tables["requests"]}
        suppliers = {row["supplier_id"] for row in tables["suppliers"]}
        kits = {row["kit_id"] for row in tables["kits"]}
        findings = []
        for kit in tables["kits"]:
            if kit["kit_request_id"] not in requests:
                findings.append(self.finding("ORPHAN_KIT", kit["kit_id"], "Kit has no matching request."))
            if kit["supplier_id"] not in suppliers:
                findings.append(self.finding("UNKNOWN_SUPPLIER", kit["kit_id"], "Kit has no matching supplier."))
            if kit["received_tray_count"] != kit["expected_tray_count"]:
                findings.append(self.finding("TRAY_COUNT_MISMATCH", kit["kit_id"], "Received tray count differs from expected."))
        for item in tables["items"]:
            if item["kit_id"] not in kits:
                findings.append(self.finding("ORPHAN_ITEM", item["item_id"], "Item has no matching kit."))
            if item["received_quantity"] < item["expected_quantity"]:
                findings.append(self.finding("ITEM_SHORTAGE", item["item_id"], "Received quantity is below expected."))
            if item["status"] in {"missing", "damaged", "wasted"}:
                findings.append(self.finding("ITEM_EXCEPTION", item["item_id"], f"Item status is {item['status']}."))
        return findings

    @staticmethod
    def finding(code: str, entity: str, message: str, severity: str = "error") -> dict[str, str]:
        return {"code": code, "severity": severity, "entity_id": entity, "message": message}

    def gold(self, tables: dict[str, list[dict[str, Any]]], landing: Path, gold: Path, as_of: datetime) -> tuple[dict[str, int], list[dict[str, Any]]]:
        request_map = {row["kit_request_id"]: row for row in tables["requests"]}
        supplier_map = {row["supplier_id"]: row for row in tables["suppliers"]}
        kits_by_request: dict[str, list[dict[str, Any]]] = {}
        items_by_kit: dict[str, list[dict[str, Any]]] = {}
        for kit in tables["kits"]:
            kits_by_request.setdefault(kit["kit_request_id"], []).append(kit)
        for item in tables["items"]:
            items_by_kit.setdefault(item["kit_id"], []).append(item)

        groups = group_events(read_events(landing / "events.csv"))
        lifecycle, workflow_findings = {}, []
        for request_id, events in sorted(groups.items()):
            summary, findings = evaluate_lifecycle(events)
            lifecycle[request_id] = asdict(summary)
            workflow_findings.extend(asdict(row) for row in findings)

        worklist, risks, discrepancies, ssd, readiness, returns = [], [], [], [], [], []
        supplier_stats: dict[str, dict[str, Any]] = {}
        completed = {"theatre_check_completed", "kit_used", "usage_reconciled", "return_prepared", "supplier_collected", "workflow_closed"}
        for request_id, request in sorted(request_map.items()):
            kits = kits_by_request.get(request_id, [])
            items = [item for kit in kits for item in items_by_kit.get(kit["kit_id"], [])]
            life = lifecycle.get(request_id, {})
            hours = int((parse_datetime(request["required_by"]) - as_of).total_seconds() // 3600)
            status = str(life.get("current_status", "request_submitted"))
            item_errors = sum(item["status"] in {"missing", "damaged", "wasted"} or item["received_quantity"] < item["expected_quantity"] for item in items)
            reasons = []
            if request["approval_status"] != "approved": reasons.append("approval_not_complete")
            if hours < 48 and status not in completed: reasons.append("not_ready_within_48_hours")
            if int(life.get("error_count", 0)) or item_errors: reasons.append("open_errors")
            base = {"kit_request_id": request_id, "case_id": request["case_id"], "procedure_name": request["procedure_name"], "required_by": request["required_by"], "hours_until_required": hours, "current_status": status, "next_owner": self.next_owner(status)}
            worklist.append(base)
            if reasons: risks.append({**base, "risk_reasons": "|".join(reasons)})
            readiness.append({**base, "theatre_ready": bool(life.get("theatre_ready")) and not item_errors, "workflow_errors": int(life.get("error_count", 0)), "item_errors": item_errors})
            for kit in kits:
                problem_items = [i for i in items_by_kit.get(kit["kit_id"], []) if i["received_quantity"] != i["expected_quantity"] or i["status"] in {"missing", "damaged"}]
                has_problem = kit["received_tray_count"] != kit["expected_tray_count"] or bool(problem_items)
                if has_problem: discrepancies.append({"kit_request_id": request_id, "kit_id": kit["kit_id"], "supplier_id": kit["supplier_id"], "expected_trays": kit["expected_tray_count"], "received_trays": kit["received_tray_count"], "item_discrepancies": len(problem_items)})
                events = groups.get(request_id, [])
                ssd.append({"kit_request_id": request_id, "kit_id": kit["kit_id"], "current_location": kit["current_location"], "ssd_handover_recorded": any(e.event_type == EventType.SSD_HANDOVER for e in events), "ssd_release_recorded": any(e.event_type == EventType.SSD_RELEASED for e in events)})
                if kit["return_due_at"] and status not in {"supplier_collected", "workflow_closed"}:
                    returns.append({"kit_request_id": request_id, "kit_id": kit["kit_id"], "supplier_id": kit["supplier_id"], "return_due_at": kit["return_due_at"], "overdue": parse_datetime(kit["return_due_at"]) < as_of, "current_location": kit["current_location"]})
                stat = supplier_stats.setdefault(kit["supplier_id"], {"requests": set(), "kits": 0, "problems": 0})
                stat["requests"].add(request_id); stat["kits"] += 1; stat["problems"] += has_problem
        supplier_performance = [{"supplier_id": sid, "supplier_name": supplier_map.get(sid, {}).get("supplier_name", ""), "approved": supplier_map.get(sid, {}).get("approved", False), "request_count": len(stat["requests"]), "kit_count": stat["kits"], "kits_with_discrepancy": stat["problems"]} for sid, stat in sorted(supplier_stats.items())]
        outputs = {
            "upcoming_worklist": worklist,
            "at_risk_cases": risks,
            "receipt_discrepancies": discrepancies,
            "ssd_status": ssd,
            "theatre_readiness": readiness,
            "outstanding_returns": returns,
            "supplier_performance": supplier_performance,
        }
        default_fields = {
            "receipt_discrepancies": ["kit_request_id", "kit_id", "supplier_id", "expected_trays", "received_trays", "item_discrepancies"],
            "outstanding_returns": ["kit_request_id", "kit_id", "supplier_id", "return_due_at", "overdue", "current_location"],
        }
        for name, rows in outputs.items():
            write_csv(gold / f"{name}.csv", rows, list(rows[0]) if rows else default_fields.get(name, []))
        return {name: len(rows) for name, rows in outputs.items()}, workflow_findings

    @staticmethod
    def next_owner(status: str) -> str:
        return {"request_submitted": "theatre_team_leader", "request_approved": "instrument_coordinator", "supplier_confirmed": "supplier", "delivery_received": "theatre_reception", "receipt_check_completed": "sterile_services", "ssd_handover": "sterile_services", "ssd_released": "theatre_team", "theatre_check_completed": "theatre_team", "kit_used": "theatre_team", "usage_reconciled": "theatre_team", "return_prepared": "supplier", "supplier_collected": "instrument_coordinator", "workflow_closed": "none"}.get(status, "instrument_coordinator")
