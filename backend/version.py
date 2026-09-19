"""
MetrCheck AI — Central Version & Pipeline Tracking (Section 15 & 22)

Defines authoritative version constants for the system, OCR engines,
structured extraction models, compliance rulesets, and integrity algorithms.
"""

SYSTEM_VERSION = "2.4.0"
OCR_PIPELINE_VERSION = "PaddleOCR-v4-OneDNN"
EXTRACTION_ENGINE_VERSION = "LLM-Rule-Extractor-v2.1"
COMPLIANCE_RULESET_VERSION = "LegalMetrology-Rules2011-Rev2024"
FSSAI_REGULATION_VERSION = "FSSAI-Labelling2020-Rev2023"
INTEGRITY_ALGORITHM = "SHA-256/CANONICAL-JSON-v1"
AUDIT_CHAIN_ALGORITHM = "SHA-256/BLOCK-CHAIN-v1"


def get_system_version_manifest() -> dict:
    """Returns full version manifest of the running MetrCheck AI instance."""
    return {
        "system_version": SYSTEM_VERSION,
        "ocr_pipeline_version": OCR_PIPELINE_VERSION,
        "extraction_engine_version": EXTRACTION_ENGINE_VERSION,
        "compliance_ruleset_version": COMPLIANCE_RULESET_VERSION,
        "fssai_regulation_version": FSSAI_REGULATION_VERSION,
        "integrity_algorithm": INTEGRITY_ALGORITHM,
        "audit_chain_algorithm": AUDIT_CHAIN_ALGORITHM,
    }


get_version_metadata = get_system_version_manifest

