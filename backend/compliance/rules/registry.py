from typing import Dict, List, Any
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

    def get_rule(self, rule_id: str) -> RuleDefinition:
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[RuleDefinition]:
        return list(self._rules.values())

    def get_rules_by_domain(self, domain: RuleDomain) -> List[RuleDefinition]:
        return [r for r in self._rules.values() if r.domain == domain]

    def count(self) -> int:
        return len(self._rules)

registry = RuleRegistry()
