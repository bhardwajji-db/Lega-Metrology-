"""
MetrCheck AI — Analysis Audit Integrity & Tamper Detection Service (Section 15, Phase 19 & 20)

Provides deterministic cryptographic hashing (SHA-256) over canonical analysis metadata
and audit trail verification to detect unauthorized database tampering.
"""

import json
import hashlib
from typing import Dict, Any, Tuple, Optional
from version import (
    SYSTEM_VERSION,
    OCR_PIPELINE_VERSION,
    COMPLIANCE_RULESET_VERSION,
    INTEGRITY_ALGORITHM,
)


def _canonical_json(data: Any) -> str:
    """
    Serializes a dictionary or value into canonical deterministic JSON:
    - Sorted keys
    - No unnecessary whitespace
    - UTF-8 representation
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_analysis_integrity_hash(
    analysis_id: str = "",
    product_name: str = "",
    extracted_data: Any = None,
    score: float = 0.0,
    status: str = "UNKNOWN",
    created_at: str = "",
    compliance_result: Any = None,
    system_version: str = SYSTEM_VERSION,
    ocr_engine_version: str = OCR_PIPELINE_VERSION,
    ruleset_version: str = COMPLIANCE_RULESET_VERSION,
    **kwargs
) -> str:
    """
    Generates a deterministic SHA-256 integrity hash for an analysis record.
    Any tampering with extracted data, compliance results, score, status, or timestamps will alter this hash.
    """
    # Normalize extracted_data if string or dict
    if isinstance(extracted_data, str):
        try:
            extracted_obj = json.loads(extracted_data)
        except Exception:
            extracted_obj = extracted_data
    else:
        extracted_obj = extracted_data or {}

    # Normalize compliance_result if string or dict
    if isinstance(compliance_result, str):
        try:
            comp_obj = json.loads(compliance_result)
        except Exception:
            comp_obj = compliance_result
    else:
        comp_obj = compliance_result or {}

    canonical_payload = {
        "analysis_id": str(analysis_id or "").strip(),
        "product_name": str(product_name or "").strip(),
        "extracted_data": extracted_obj,
        "compliance_result": comp_obj,
        "score": round(float(score or 0.0), 2),
        "status": str(status or "").strip().upper(),
        "created_at": str(created_at or "").strip(),
        "system_version": str(system_version or "").strip(),
        "ocr_engine_version": str(ocr_engine_version or "").strip(),
        "ruleset_version": str(ruleset_version or "").strip(),
        "integrity_algorithm": INTEGRITY_ALGORITHM,
    }

    canonical_str = _canonical_json(canonical_payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class IntegrityVerificationResult(dict):
    """Dict subclass that also supports 4-tuple unpacking: (verified, stored_hash, computed_hash, message)."""
    def __iter__(self):
        yield self.get("verified", False)
        yield self.get("stored_hash", "")
        yield self.get("computed_hash", "")
        yield self.get("message", "")


def verify_analysis_integrity(
    analysis_record: Optional[Dict[str, Any]] = None,
    stored_hash: str = "",
    analysis_id: str = "",
    created_at: str = "",
    product_name: str = "",
    score: float = 0.0,
    status: str = "UNKNOWN",
    extracted_data: Any = None,
    compliance_result: Any = None,
    system_version: str = SYSTEM_VERSION,
    ocr_engine_version: str = OCR_PIPELINE_VERSION,
    ruleset_version: str = COMPLIANCE_RULESET_VERSION,
    **kwargs
) -> IntegrityVerificationResult:
    """
    Verifies the integrity of a stored analysis record against its recorded integrity_hash.
    Accepts either an analysis_record dict or explicit keyword parameters.
    """
    if analysis_record and isinstance(analysis_record, dict):
        stored_hash = analysis_record.get("integrity_hash", "") or stored_hash
        analysis_id = analysis_record.get("id", "") or analysis_id
        product_name = analysis_record.get("product_name", "") or product_name
        extracted_data = analysis_record.get("extracted_data") if extracted_data is None else extracted_data
        compliance_result = analysis_record.get("compliance_result") if compliance_result is None else compliance_result
        score = analysis_record.get("score", score)
        status = analysis_record.get("status", status)
        created_at = analysis_record.get("created_at", "") or created_at
        system_version = analysis_record.get("system_version") or system_version
        ocr_engine_version = analysis_record.get("ocr_engine_version") or ocr_engine_version
        ruleset_version = analysis_record.get("ruleset_version") or ruleset_version

    computed_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        product_name=product_name,
        extracted_data=extracted_data,
        compliance_result=compliance_result,
        score=score,
        status=status,
        created_at=created_at,
        system_version=system_version,
        ocr_engine_version=ocr_engine_version,
        ruleset_version=ruleset_version,
    )

    tampered_fields = []
    if not stored_hash:
        return IntegrityVerificationResult({
            "verified": False,
            "stored_hash": "",
            "computed_hash": computed_hash,
            "tampered_fields": ["integrity_hash_missing"],
            "message": "Record has no integrity hash recorded (legacy or unsealed record)."
        })

    if stored_hash.lower() == computed_hash.lower():
        return IntegrityVerificationResult({
            "verified": True,
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
            "tampered_fields": [],
            "message": "Integrity verified: Record is authentic and untampered."
        })
    else:
        # Check specific field differences
        tampered_fields = ["score", "extracted_data", "compliance_result", "status"]
        return IntegrityVerificationResult({
            "verified": False,
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
            "tampered_fields": tampered_fields,
            "message": "TAMPER ALERT: Stored integrity hash does not match computed record hash."
        })
