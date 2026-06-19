from typing import List, Dict, Any
from collections import defaultdict
from statistics import mean


# =========================================================
# GOLD CLINICAL ANALYTICS LAYER
# ---------------------------------------------------------
# Converts Silver-B enriched surgical data into:
# - operational insights
# - clinical patterns
# - supply chain intelligence
# - surgeon behaviour signals
# =========================================================


class ClinicalGoldAnalytics:
    def __init__(self):
        pass

    # -----------------------------------------------------
    # SURGEON LEVEL ANALYTICS
    # -----------------------------------------------------
    def surgeon_summary(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        surgeon_map = defaultdict(list)

        for r in records:
            surgeon = (
                r.get("surgeon_name")
                or r.get("surgeon", {}).get("full_name")
                or "UNKNOWN"
            )
            surgeon_map[surgeon].append(r)

        output = {}

        for surgeon, cases in surgeon_map.items():
            confidences = [
                c.get("_enrichment_meta", {}).get("confidence", 0)
                for c in cases
            ]

            procedures = [
                c.get("clinical_resolution", {}).get("procedure_id")
                for c in cases
            ]

            output[surgeon] = {
                "total_cases": len(cases),
                "avg_confidence": round(mean(confidences), 3) if confidences else 0,
                "procedure_distribution": self._distribution(procedures),
            }

        return output

    # -----------------------------------------------------
    # PROCEDURE USAGE ANALYTICS
    # -----------------------------------------------------
    def procedure_usage(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = defaultdict(int)

        for r in records:
            proc = r.get("clinical_resolution", {}).get("procedure_id")
            if proc:
                counter[proc] += 1

        return dict(counter)

    # -----------------------------------------------------
    # INSTRUMENT SYSTEM USAGE
    # -----------------------------------------------------
    def system_usage(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = defaultdict(int)

        for r in records:
            system = r.get("clinical_resolution", {}).get("system_id")
            if system:
                counter[system] += 1

        return dict(counter)

    # -----------------------------------------------------
    # MISSING ITEM ANALYTICS (VERY IMPORTANT)
    # -----------------------------------------------------
    def missing_items_analysis(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = defaultdict(int)

        for r in records:
            missing = r.get("clinical_validation", {}).get("missing_expected_items", [])

            for item in missing:
                counter[item] += 1

        return dict(counter)

    # -----------------------------------------------------
    # SYSTEM MISMATCH ANALYTICS
    # -----------------------------------------------------
    def system_mismatch_rate(self, records: List[Dict[str, Any]]) -> float:
        total = len(records)
        mismatches = 0

        for r in records:
            flags = r.get("clinical_validation", {}).get("flags", [])
            if "SYSTEM_PROCEDURE_MISMATCH" in flags:
                mismatches += 1

        return round(mismatches / total, 3) if total else 0.0

    # -----------------------------------------------------
    # CONFIDENCE DISTRIBUTION
    # -----------------------------------------------------
    def confidence_profile(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        values = [
            r.get("_enrichment_meta", {}).get("confidence", 0)
            for r in records
        ]

        if not values:
            return {"mean": 0, "min": 0, "max": 0}

        return {
            "mean": round(mean(values), 3),
            "min": min(values),
            "max": max(values),
        }

    # -----------------------------------------------------
    # GENERAL DISTRIBUTION HELPER
    # -----------------------------------------------------
    def _distribution(self, items: List[Any]) -> Dict[str, int]:
        counter = defaultdict(int)
        for i in items:
            if i:
                counter[i] += 1
        return dict(counter)

    # -----------------------------------------------------
    # FULL DASHBOARD SNAPSHOT
    # -----------------------------------------------------
    def full_report(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "source_record_count": len(records),
            "surgeon_summary": self.surgeon_summary(records),
            "procedure_usage": self.procedure_usage(records),
            "system_usage": self.system_usage(records),
            "missing_items": self.missing_items_analysis(records),
            "system_mismatch_rate": self.system_mismatch_rate(records),
            "confidence_profile": self.confidence_profile(records),
        }
