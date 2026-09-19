from typing import Dict, List, Any, Optional
from compliance.rules.models import RuleDefinition, RuleDomain
from compliance.rules.legal_metrology import LEGAL_METROLOGY_RULES
from compliance.rules.fssai import FSSAI_RULES

class RuleRegistry:
    """
    Centralized, versioned registry of statutory packaging compliance rules.
    Maintains clean separation between Legal Metrology and FSSAI domains.
    """

    def __init__(self):
        self._rules: Dict[str, RuleDefinition] = {}
        # Register Legal Metrology rules
        for r_id, r_def in LEGAL_METROLOGY_RULES.items():
            self._rules[r_id] = r_def
        # Register FSSAI rules
        for r_id, r_def in FSSAI_RULES.items():
            self._rules[r_id] = r_def

    def get_rule(self, rule_id: str) -> Optional[RuleDefinition]:
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[RuleDefinition]:
        return list(self._rules.values())

    def get_rules_by_domain(self, domain: RuleDomain) -> List[RuleDefinition]:
        return [r for r in self._rules.values() if r.domain == domain]

    def get_rules_by_category(self, category: Any) -> List[RuleDefinition]:
        cat_str = category.value if hasattr(category, 'value') else str(category)
        cat_upper = cat_str.upper()
        if cat_upper in ("ALL", ""):
            return list(self._rules.values())
        return [
            r for r in self._rules.values()
            if "ALL" in getattr(r, 'category_applicability', ['ALL']) or cat_upper in getattr(r, 'category_applicability', [])
        ]

    def get_rules_by_version(self, version: str) -> List[RuleDefinition]:
        return [r for r in self._rules.values() if getattr(r, 'rule_version', r.version) == version]

    def count(self) -> int:
        return len(self._rules)

registry = RuleRegistry()

