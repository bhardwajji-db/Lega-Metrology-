"""
MetrCheck AI — Claim Rule Registry & Regulatory Configuration Engine
Loads and validates external statutory claim rules from JSON configurations.
Enforces the principle: "Never invent regulatory requirements. If a rule cannot be verified
from configured regulatory knowledge: rule_status = NOT_VERIFIED, assessment = REVIEW_REQUIRED."
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from claims.models import ClaimCategory

logger = logging.getLogger(__name__)


class RegulatoryRule:
    def __init__(self, data: Dict[str, Any]):
        self.rule_id: str = data.get("rule_id", "CLAIM-RULE-GENERIC")
        self.claim_type: str = data.get("claim_type", "OTHER")
        category_raw = data.get("category", "OTHER")
        try:
            self.category: ClaimCategory = ClaimCategory(category_raw)
        except ValueError:
            self.category = ClaimCategory.OTHER
        self.jurisdiction: str = data.get("jurisdiction", "IN")
        self.source: str = data.get("source", "Configured Regulatory Source")
        self.source_reference: str = data.get("source_reference", "")
        self.source_url: str = data.get("source_url", "")
        self.version: str = data.get("version", "1.0")
        self.enabled: bool = data.get("enabled", True)
        self.description: str = data.get("description", "")
        self.patterns: List[str] = [p.lower().strip() for p in data.get("patterns", [])]
        self.contradiction_ingredients: List[str] = [
            i.lower().strip() for i in data.get("contradiction_ingredients", [])
        ]
        self.supporting_nutrients: List[str] = [
            n.lower().strip() for n in data.get("supporting_nutrients", [])
        ]
        self.required_markings: List[str] = [
            m.lower().strip() for m in data.get("required_markings", [])
        ]
        self.expected_origin: Optional[str] = data.get("expected_origin")
        self.min_protein_g_per_100g_solid: Optional[float] = data.get("min_protein_g_per_100g_solid")
        self.min_protein_g_per_100ml_liquid: Optional[float] = data.get("min_protein_g_per_100ml_liquid")
        self.max_fat_g_per_100g_solid: Optional[float] = data.get("max_fat_g_per_100g_solid")
        self.max_fat_g_per_100ml_liquid: Optional[float] = data.get("max_fat_g_per_100ml_liquid")
        self.max_sugar_g_per_100g: Optional[float] = data.get("max_sugar_g_per_100g")
        self.max_cholesterol_mg_per_100g: Optional[float] = data.get("max_cholesterol_mg_per_100g")
        self.requires_nutrition_panel: bool = data.get("requires_nutrition_panel", False)
        self.contradiction_if_multi_ingredient: bool = data.get("contradiction_if_multi_ingredient", False)
        self.is_absolute: bool = data.get("is_absolute", False)
        self.is_comparative: bool = data.get("is_comparative", False)
        self.is_high_risk: bool = data.get("is_high_risk", False)
        self.risk_level: str = data.get("risk_level", "MEDIUM")
        self.default_status: Optional[str] = data.get("default_status")
        self.requires_human_review: bool = data.get("requires_human_review", False)
        self.raw_data: Dict[str, Any] = data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "claim_type": self.claim_type,
            "category": self.category.value,
            "jurisdiction": self.jurisdiction,
            "source": self.source,
            "source_reference": self.source_reference,
            "source_url": self.source_url,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "is_absolute": self.is_absolute,
            "is_comparative": self.is_comparative,
            "is_high_risk": self.is_high_risk,
            "risk_level": self.risk_level,
            "requires_human_review": self.requires_human_review,
        }


class ClaimRuleRegistry:
    _instance = None

    def __init__(self):
        self._rules: Dict[str, RegulatoryRule] = {}
        self._load_all_rules()

    @classmethod
    def get_instance(cls) -> "ClaimRuleRegistry":
        if cls._instance is None:
            cls._instance = ClaimRuleRegistry()
        return cls._instance

    def _load_all_rules(self):
        rules_dir = os.path.join(os.path.dirname(__file__), "claim_rules")
        if not os.path.exists(rules_dir):
            logger.warning(f"[ClaimRuleRegistry] Rules directory not found: {rules_dir}")
            return

        rule_files = [f for f in os.listdir(rules_dir) if f.endswith(".json")]
        total_loaded = 0
        for fname in sorted(rule_files):
            fpath = os.path.join(rules_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("enabled", True):
                                rule = RegulatoryRule(item)
                                self._rules[rule.rule_id] = rule
                                total_loaded += 1
            except Exception as e:
                logger.error(f"[ClaimRuleRegistry] Failed to load {fname}: {e}")
        logger.info(f"[ClaimRuleRegistry] Successfully loaded {total_loaded} active regulatory rules.")

    def get_rule_by_id(self, rule_id: str) -> Optional[RegulatoryRule]:
        return self._rules.get(rule_id)

    def get_rules_by_category(self, category: ClaimCategory) -> List[RegulatoryRule]:
        return [r for r in self._rules.values() if r.category == category and r.enabled]

    def get_all_rules(self) -> List[RegulatoryRule]:
        return list(self._rules.values())

    def find_matching_rule(self, normalized_claim_text: str) -> Optional[RegulatoryRule]:
        """Match claim text against patterns in loaded rules."""
        text = normalized_claim_text.lower().strip()
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            for pattern in rule.patterns:
                if pattern in text or text in pattern:
                    return rule
        return None


# Global registry singleton
claim_rule_registry = ClaimRuleRegistry.get_instance()
