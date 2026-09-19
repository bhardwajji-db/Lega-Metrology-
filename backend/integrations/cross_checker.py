import re
import difflib
import logging
from typing import Optional, List, Dict, Any, Tuple
from utils.datetime_utils import get_current_utc_iso
from models.verification_schemas import (
    CrossCheckStatus,
    CrossCheckFieldResult,
    VerificationConfidence,
    VerificationConfidenceTier,
    ApiAvailabilityStatus,
    ApiAvailabilityState,
    ExternalVerificationSummary,
    CrossCheckRequest,
)
from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus
from config import settings

logger = logging.getLogger(__name__)

# Common corporate / entity stop words to ignore during business name comparison
CORPORATE_STOP_WORDS = {
    "pvt", "ltd", "private", "limited", "llp", "inc", "corp", "corporation",
    "co", "company", "enterprises", "industries", "foods", "beverages",
    "products", "india", "mfg", "manufactured", "by", "marketed", "packed",
    "fbo", "licensee", "unit", "works", "plant", "and", "&"
}


def normalize_entity_text(text: Optional[str]) -> str:
    """
    Normalizes corporate, brand, or product names for reliable comparison.
    Strips punctuation, lowercases, and removes corporate suffixes.
    """
    if not text:
        return ""
    # Lowercase and replace non-alphanumeric chars with spaces
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text).lower())
    words = [w for w in cleaned.split() if w and w not in CORPORATE_STOP_WORDS]
    return " ".join(words)


def compute_similarity(str1: Optional[str], str2: Optional[str]) -> Tuple[float, List[str]]:
    """
    Computes hybrid similarity score between two strings using Token Jaccard + SequenceMatcher.
    Returns (similarity_score: 0.0-1.0, matched_tokens: List[str]).
    """
    if not str1 or not str2:
        return 0.0, []

    norm1 = normalize_entity_text(str1)
    norm2 = normalize_entity_text(str2)

    if not norm1 or not norm2:
        return 0.0, []

    # 1. Exact match
    if norm1 == norm2:
        tokens = list(set(norm1.split()))
        return 1.0, tokens

    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)

    jaccard = len(intersection) / float(len(union)) if union else 0.0

    # 2. Sequence matcher ratio for string alignment
    seq_ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()

    # 3. Substring containment bonus
    containment_bonus = 0.0
    if norm1 in norm2 or norm2 in norm1:
        containment_bonus = 0.20

    # Weighted hybrid score
    combined = (0.50 * jaccard) + (0.50 * seq_ratio) + containment_bonus
    final_score = min(1.0, round(combined, 3))
    matched_tokens = sorted(list(intersection))

    return final_score, matched_tokens


class CrossCheckEngine:
    """
    Statutory External Verification & Cross-Checking Intelligence Engine.
    Performs deterministic and fuzzy verification between OCR-extracted package data
    and authoritative registry / cache records (FoSCoS, GS1 DataKart, QR payloads).
    """

    def check_fssai_manufacturer_consistency(
        self,
        fssai_record: Optional[FSSAIVerificationRecord],
        extracted_manufacturer: Optional[str],
        extracted_address: Optional[str] = None
    ) -> CrossCheckFieldResult:
        """
        Cross-checks FoSCoS FBO business name against extracted manufacturer name.
        """
        field = "manufacturer_name"
        if not fssai_record or fssai_record.status == FSSAIVerificationStatus.NOT_APPLICABLE:
            return CrossCheckFieldResult(
                check_type="FSSAI_MANUFACTURER_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_manufacturer,
                registry_value=None,
                status=CrossCheckStatus.NOT_APPLICABLE,
                similarity_score=0.0,
                discrepancy_details="No FSSAI licence present on package for cross-referencing."
            )

        if fssai_record.status in (FSSAIVerificationStatus.INVALID_FORMAT, FSSAIVerificationStatus.NOT_FOUND):
            return CrossCheckFieldResult(
                check_type="FSSAI_MANUFACTURER_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_manufacturer,
                registry_value=None,
                status=CrossCheckStatus.NOT_FOUND if fssai_record.status == FSSAIVerificationStatus.NOT_FOUND else CrossCheckStatus.MISMATCH,
                similarity_score=0.0,
                discrepancy_details=f"FSSAI licence {fssai_record.licence_number} could not be validated in registry ({fssai_record.status.value}).",
                is_critical_mismatch=True
            )

        if fssai_record.status == FSSAIVerificationStatus.NOT_VERIFIED:
            return CrossCheckFieldResult(
                check_type="FSSAI_MANUFACTURER_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_manufacturer,
                registry_value=None,
                status=CrossCheckStatus.UNVERIFIED,
                similarity_score=0.0,
                discrepancy_details="FSSAI 14-digit format valid. Live FoSCoS business name lookup unconfigured or offline."
            )

        registry_name = fssai_record.business_name or ""
        if not registry_name:
            return CrossCheckFieldResult(
                check_type="FSSAI_MANUFACTURER_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_manufacturer,
                registry_value=None,
                status=CrossCheckStatus.UNVERIFIED,
                similarity_score=0.0,
                discrepancy_details="FSSAI record verified but business name missing from registry payload."
            )

        combined_extracted = f"{extracted_manufacturer or ''} {extracted_address or ''}".strip()
        sim_score, matched_tokens = compute_similarity(combined_extracted, registry_name)

        if sim_score >= 0.70:
            status = CrossCheckStatus.MATCH
            details = f"Extracted manufacturer aligns with FoSCoS registered business '{registry_name}' (Match: {int(sim_score*100)}%)."
            is_critical = False
        elif sim_score >= 0.40:
            status = CrossCheckStatus.PARTIAL_MATCH
            details = f"Partial name overlap with FoSCoS registered entity '{registry_name}' (Similarity: {int(sim_score*100)}%). Review recommended."
            is_critical = False
        else:
            status = CrossCheckStatus.MISMATCH
            details = f"Discrepancy: Extracted manufacturer '{extracted_manufacturer}' differs from FoSCoS registered licensee '{registry_name}'."
            is_critical = True

        return CrossCheckFieldResult(
            check_type="FSSAI_MANUFACTURER_CONSISTENCY",
            field_name=field,
            extracted_value=extracted_manufacturer,
            registry_value=registry_name,
            status=status,
            similarity_score=sim_score,
            matched_tokens=matched_tokens,
            discrepancy_details=details,
            is_critical_mismatch=is_critical
        )

    def check_gs1_product_consistency(
        self,
        gs1_record: Optional[GS1VerificationRecord],
        extracted_product_name: Optional[str],
        extracted_brand_name: Optional[str] = None
    ) -> CrossCheckFieldResult:
        """
        Cross-checks GS1 DataKart Brand / Product Description against extracted product declarations.
        """
        field = "product_name"
        if not gs1_record or gs1_record.status == GS1VerificationStatus.NOT_APPLICABLE:
            return CrossCheckFieldResult(
                check_type="GS1_PRODUCT_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_product_name,
                registry_value=None,
                status=CrossCheckStatus.NOT_APPLICABLE,
                similarity_score=0.0,
                discrepancy_details="No GTIN barcode present on package for GS1 cross-referencing."
            )

        if gs1_record.status == GS1VerificationStatus.INVALID_FORMAT:
            return CrossCheckFieldResult(
                check_type="GS1_PRODUCT_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_product_name,
                registry_value=None,
                status=CrossCheckStatus.MISMATCH,
                similarity_score=0.0,
                discrepancy_details=f"Barcode {gs1_record.gtin} failed standard GS1 Modulo-10 checksum.",
                is_critical_mismatch=True
            )

        if gs1_record.status == GS1VerificationStatus.NOT_FOUND:
            return CrossCheckFieldResult(
                check_type="GS1_PRODUCT_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_product_name,
                registry_value=None,
                status=CrossCheckStatus.NOT_FOUND,
                similarity_score=0.0,
                discrepancy_details=f"GTIN {gs1_record.gtin} not found in GS1 DataKart / Verified by GS1 registry.",
                is_critical_mismatch=False
            )

        if gs1_record.status == GS1VerificationStatus.NOT_VERIFIED:
            return CrossCheckFieldResult(
                check_type="GS1_PRODUCT_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_product_name,
                registry_value=None,
                status=CrossCheckStatus.UNVERIFIED,
                similarity_score=0.0,
                discrepancy_details="GS1 Modulo-10 checksum valid. Live DataKart registry lookup unconfigured or offline."
            )

        registry_desc = f"{gs1_record.brand_name or ''} {gs1_record.product_description or ''}".strip()
        if not registry_desc:
            return CrossCheckFieldResult(
                check_type="GS1_PRODUCT_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_product_name,
                registry_value=None,
                status=CrossCheckStatus.UNVERIFIED,
                similarity_score=0.0,
                discrepancy_details="GS1 GTIN verified but product description missing from registry payload."
            )

        combined_extracted = f"{extracted_brand_name or ''} {extracted_product_name or ''}".strip()
        sim_score, matched_tokens = compute_similarity(combined_extracted, registry_desc)

        if sim_score >= 0.65:
            status = CrossCheckStatus.MATCH
            details = f"Extracted product declarations match GS1 DataKart catalog entry '{registry_desc}' ({int(sim_score*100)}%)."
            is_critical = False
        elif sim_score >= 0.35:
            status = CrossCheckStatus.PARTIAL_MATCH
            details = f"Partial product match with GS1 DataKart entry '{registry_desc}' (Similarity: {int(sim_score*100)}%)."
            is_critical = False
        else:
            status = CrossCheckStatus.MISMATCH
            details = f"Discrepancy: Extracted product '{extracted_product_name}' differs from GS1 registered product '{registry_desc}'."
            is_critical = True

        return CrossCheckFieldResult(
            check_type="GS1_PRODUCT_CONSISTENCY",
            field_name=field,
            extracted_value=extracted_product_name,
            registry_value=registry_desc,
            status=status,
            similarity_score=sim_score,
            matched_tokens=matched_tokens,
            discrepancy_details=details,
            is_critical_mismatch=is_critical
        )

    def check_gs1_manufacturer_consistency(
        self,
        gs1_record: Optional[GS1VerificationRecord],
        extracted_manufacturer: Optional[str]
    ) -> CrossCheckFieldResult:
        """
        Cross-checks GS1 DataKart registered company name against extracted manufacturer.
        """
        field = "manufacturer_name"
        if not gs1_record or not gs1_record.company_name or gs1_record.status != GS1VerificationStatus.VERIFIED:
            return CrossCheckFieldResult(
                check_type="GS1_MANUFACTURER_CONSISTENCY",
                field_name=field,
                extracted_value=extracted_manufacturer,
                registry_value=getattr(gs1_record, 'company_name', None),
                status=CrossCheckStatus.NOT_APPLICABLE if not gs1_record else CrossCheckStatus.UNVERIFIED,
                similarity_score=0.0,
                discrepancy_details="GS1 manufacturer company details not available."
            )

        sim_score, matched_tokens = compute_similarity(extracted_manufacturer, gs1_record.company_name)
        if sim_score >= 0.70:
            status = CrossCheckStatus.MATCH
            details = f"Extracted manufacturer matches GS1 company owner '{gs1_record.company_name}' ({int(sim_score*100)}%)."
            is_critical = False
        elif sim_score >= 0.40:
            status = CrossCheckStatus.PARTIAL_MATCH
            details = f"Partial match with GS1 company owner '{gs1_record.company_name}' ({int(sim_score*100)}%)."
            is_critical = False
        else:
            status = CrossCheckStatus.MISMATCH
            details = f"Discrepancy: Extracted manufacturer '{extracted_manufacturer}' differs from GS1 company owner '{gs1_record.company_name}'."
            is_critical = True

        return CrossCheckFieldResult(
            check_type="GS1_MANUFACTURER_CONSISTENCY",
            field_name=field,
            extracted_value=extracted_manufacturer,
            registry_value=gs1_record.company_name,
            status=status,
            similarity_score=sim_score,
            matched_tokens=matched_tokens,
            discrepancy_details=details,
            is_critical_mismatch=is_critical
        )

    def check_qr_statutory_consistency(
        self,
        qr_payload: Optional[str],
        extracted_declarations: Dict[str, Any]
    ) -> List[CrossCheckFieldResult]:
        """
        Parses QR payload safely and cross-checks contained key-value statutory declarations
        against OCR-extracted statutory declarations (e.g. MRP, Net Quantity, Batch, FSSAI).
        """
        results: List[CrossCheckFieldResult] = []
        if not qr_payload or not qr_payload.strip():
            return results

        payload = qr_payload.strip()

        # 1. Check if QR payload contains FSSAI 14-digit number
        fssai_match = re.search(r'\b([12]\d{13})\b', payload)
        if fssai_match:
            qr_fssai = fssai_match.group(1)
            ext_fssai = extracted_declarations.get("fssai_license") or ""
            clean_ext = re.sub(r'\D', '', str(ext_fssai))
            is_match = (qr_fssai == clean_ext) if clean_ext else False
            results.append(CrossCheckFieldResult(
                check_type="QR_STATUTORY_CONSISTENCY",
                field_name="fssai_license",
                extracted_value=ext_fssai or None,
                registry_value=qr_fssai,
                status=CrossCheckStatus.MATCH if is_match else (CrossCheckStatus.MISMATCH if ext_fssai else CrossCheckStatus.REVIEW_REQUIRED),
                similarity_score=1.0 if is_match else 0.0,
                matched_tokens=[qr_fssai] if is_match else [],
                discrepancy_details=f"QR code embeds FSSAI licence {qr_fssai}." + (" Matches label." if is_match else " Differs from label declaration."),
                is_critical_mismatch=not is_match and bool(ext_fssai)
            ))

        # 2. Check if QR payload contains Net Quantity or MRP declarations
        # e.g., "MRP 250", "Rs. 250", "250.00", "500g", "1kg"
        mrp_ext = str(extracted_declarations.get("mrp") or "")
        if mrp_ext:
            clean_mrp = re.sub(r'[^\d.]', '', mrp_ext)
            if clean_mrp and clean_mrp in payload:
                results.append(CrossCheckFieldResult(
                    check_type="QR_STATUTORY_CONSISTENCY",
                    field_name="mrp",
                    extracted_value=mrp_ext,
                    registry_value=clean_mrp,
                    status=CrossCheckStatus.MATCH,
                    similarity_score=1.0,
                    matched_tokens=[clean_mrp],
                    discrepancy_details=f"QR code payload confirms MRP ₹{clean_mrp}."
                ))

        return results

    def compute_verification_confidence(
        self,
        fssai_record: Optional[FSSAIVerificationRecord],
        gs1_record: Optional[GS1VerificationRecord],
        cross_checks: List[CrossCheckFieldResult],
        is_offline: bool = False
    ) -> VerificationConfidence:
        """
        Computes deterministic verification confidence score and tier.
        """
        factors: Dict[str, Any] = {}
        score = 0.0

        # Factor 1: Structural Format & Checksum validation (up to +0.30)
        checksum_passed = False
        fssai_format_valid = fssai_record and fssai_record.status not in (FSSAIVerificationStatus.INVALID_FORMAT, FSSAIVerificationStatus.NOT_APPLICABLE)
        gs1_checksum_valid = gs1_record and gs1_record.status not in (GS1VerificationStatus.INVALID_FORMAT, GS1VerificationStatus.NOT_APPLICABLE)

        if fssai_format_valid:
            score += 0.15
            factors["fssai_format_valid"] = True
        if gs1_checksum_valid:
            score += 0.15
            factors["gs1_checksum_valid"] = True
        if fssai_format_valid or gs1_checksum_valid:
            checksum_passed = True

        # Factor 2: External Registry Confirmation (up to +0.35)
        registry_confirmed = False
        if fssai_record and fssai_record.status == FSSAIVerificationStatus.VERIFIED:
            score += 0.20
            factors["fssai_registry_verified"] = True
            registry_confirmed = True
        if gs1_record and gs1_record.status == GS1VerificationStatus.VERIFIED:
            score += 0.15
            factors["gs1_registry_verified"] = True
            registry_confirmed = True

        # Factor 3: Cross-Field Consistency Agreement Rate (up to +0.35)
        evaluable_checks = [c for c in cross_checks if c.status not in (CrossCheckStatus.NOT_APPLICABLE, CrossCheckStatus.UNVERIFIED)]
        field_agreement_rate = 0.0
        if evaluable_checks:
            matches = sum(1.0 for c in evaluable_checks if c.status == CrossCheckStatus.MATCH)
            partial = sum(0.5 for c in evaluable_checks if c.status == CrossCheckStatus.PARTIAL_MATCH)
            field_agreement_rate = round((matches + partial) / len(evaluable_checks), 2)
            score += round(0.35 * field_agreement_rate, 3)
            factors["field_agreement_rate"] = field_agreement_rate

        # Factor 4: Critical Mismatch Penalties
        critical_mismatches = [c for c in cross_checks if c.is_critical_mismatch]
        if critical_mismatches:
            penalty = len(critical_mismatches) * 0.35
            score = max(0.0, score - penalty)
            factors["critical_mismatches_count"] = len(critical_mismatches)

        # Cap score between 0.0 and 1.0
        final_score = min(1.0, max(0.0, round(score, 2)))

        # Assign confidence tier
        if final_score >= 0.75:
            tier = VerificationConfidenceTier.HIGH
            verdict = "Authoritative external verification & high field consistency confirmed."
        elif final_score >= 0.45:
            tier = VerificationConfidenceTier.MEDIUM
            verdict = "Structural conformity confirmed; partial or local verification records available."
        elif final_score > 0.0:
            tier = VerificationConfidenceTier.LOW
            verdict = "Low confidence: External verification records unconfirmed or discrepancies found."
        else:
            tier = VerificationConfidenceTier.ZERO
            verdict = "Unverified: No statutory identifiers present or verification failed."

        return VerificationConfidence(
            score=final_score,
            tier=tier,
            checksum_passed=checksum_passed,
            registry_confirmed=registry_confirmed,
            field_agreement_rate=field_agreement_rate,
            factors=factors,
            verdict=verdict
        )

    def evaluate_all(
        self,
        extracted_data: Dict[str, Any],
        fssai_record: Optional[FSSAIVerificationRecord] = None,
        gs1_record: Optional[GS1VerificationRecord] = None,
        qr_payload: Optional[str] = None,
        barcode_detected: Optional[str] = None,
        offline_mode: bool = False
    ) -> ExternalVerificationSummary:
        """
        Executes comprehensive cross-field consistency evaluation across all sources.
        """
        now_ts = get_current_utc_iso()
        cross_checks: List[CrossCheckFieldResult] = []
        sources: List[str] = []

        # 1. FSSAI ↔ Manufacturer Cross-Check
        ext_mfg = extracted_data.get("manufacturer") or extracted_data.get("manufacturer_name") or ""
        ext_addr = extracted_data.get("manufacturer_address") or ""
        fssai_check = self.check_fssai_manufacturer_consistency(fssai_record, ext_mfg, ext_addr)
        cross_checks.append(fssai_check)
        if fssai_record and fssai_record.provider:
            sources.append(fssai_record.provider)

        # 2. GS1 ↔ Product Cross-Check
        ext_prod = extracted_data.get("product_name") or ""
        ext_brand = extracted_data.get("brand_name") or extracted_data.get("brand") or ""
        gs1_prod_check = self.check_gs1_product_consistency(gs1_record, ext_prod, ext_brand)
        cross_checks.append(gs1_prod_check)
        if gs1_record and gs1_record.provider:
            sources.append(gs1_record.provider)

        # 3. GS1 ↔ Manufacturer Cross-Check
        if gs1_record and gs1_record.company_name:
            gs1_mfg_check = self.check_gs1_manufacturer_consistency(gs1_record, ext_mfg)
            cross_checks.append(gs1_mfg_check)

        # 4. QR ↔ Statutory Declarations Cross-Check
        if qr_payload:
            qr_checks = self.check_qr_statutory_consistency(qr_payload, extracted_data)
            cross_checks.extend(qr_checks)
            sources.append("OPENCV_SAFE_QR_DETECTOR")

        # 5. Determine Overall Consistency Status
        statuses = [c.status for c in cross_checks if c.status != CrossCheckStatus.NOT_APPLICABLE]
        discrepancies = [c.discrepancy_details for c in cross_checks if c.discrepancy_details and c.status in (CrossCheckStatus.MISMATCH, CrossCheckStatus.NOT_FOUND)]

        if any(s == CrossCheckStatus.MISMATCH for s in statuses):
            overall_status = CrossCheckStatus.MISMATCH
        elif any(s == CrossCheckStatus.PARTIAL_MATCH for s in statuses):
            overall_status = CrossCheckStatus.PARTIAL_MATCH
        elif any(s == CrossCheckStatus.MATCH for s in statuses):
            overall_status = CrossCheckStatus.MATCH
        elif any(s == CrossCheckStatus.UNVERIFIED for s in statuses):
            overall_status = CrossCheckStatus.UNVERIFIED
        else:
            overall_status = CrossCheckStatus.NOT_APPLICABLE

        # 6. Compute Confidence
        confidence = self.compute_verification_confidence(
            fssai_record=fssai_record,
            gs1_record=gs1_record,
            cross_checks=cross_checks,
            is_offline=offline_mode
        )

        # 7. Check API Availability Status
        api_availability = {
            "foscos": ApiAvailabilityStatus(
                service_name="FoSCoS Official Registry API",
                state=ApiAvailabilityState.ONLINE if (fssai_record and fssai_record.is_live) else (
                    ApiAvailabilityState.UNCONFIGURED if not settings.FSSAI_API_URL else ApiAvailabilityState.OFFLINE
                ),
                endpoint=settings.FSSAI_API_URL or "UNCONFIGURED",
                last_checked=now_ts,
                message="FoSCoS live registry online." if (fssai_record and fssai_record.is_live) else "Operating in local validation mode."
            ),
            "gs1_datakart": ApiAvailabilityStatus(
                service_name="GS1 India DataKart API",
                state=ApiAvailabilityState.ONLINE if (gs1_record and gs1_record.is_live) else (
                    ApiAvailabilityState.UNCONFIGURED if not settings.GS1_API_URL else ApiAvailabilityState.OFFLINE
                ),
                endpoint=settings.GS1_API_URL or "UNCONFIGURED",
                last_checked=now_ts,
                message="GS1 DataKart live registry online." if (gs1_record and gs1_record.is_live) else "Operating in local validation mode."
            )
        }

        # Summary verdict text
        if overall_status == CrossCheckStatus.MATCH:
            verdict = "All external identifiers and statutory declarations are fully consistent across official registries."
        elif overall_status == CrossCheckStatus.PARTIAL_MATCH:
            verdict = "External identifiers are structurally valid with partial entity name consistency. Review recommended."
        elif overall_status == CrossCheckStatus.MISMATCH:
            verdict = f"Critical discrepancy detected across external registries: {len(discrepancies)} mismatch(es) found."
        elif overall_status == CrossCheckStatus.UNVERIFIED:
            verdict = "Structural format and Modulo-10 checksum verified locally. Remote registry unconfigured or offline."
        else:
            verdict = "No statutory external identifiers available for cross-referencing."

        return ExternalVerificationSummary(
            fssai_verification=fssai_record,
            gs1_verification=gs1_record,
            qr_payload=qr_payload,
            barcode_detected=barcode_detected,
            cross_checks=cross_checks,
            overall_consistency_status=overall_status,
            confidence=confidence,
            api_availability=api_availability,
            offline_mode=offline_mode,
            verification_timestamp=now_ts,
            verification_sources=list(set(sources)),
            discrepancies=discrepancies,
            summary_verdict=verdict
        )


# Global singleton instance
cross_check_engine = CrossCheckEngine()
