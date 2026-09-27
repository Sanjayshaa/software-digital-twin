"""
Phase 4 — Centralized Relationship Impact Rules Registry.
Defines explicit propagation directions, impact semantics, and confidence behaviors
for every typed relationship in the Digital Twin.
"""

from typing import Dict, Optional, List
from app.services.impact.models import RelationshipImpactRule, PropagationDirection


class RelationshipRuleRegistry:
    """
    Centralized registry of relationship propagation rules.
    Determines whether and how a relationship type propagates change impact.
    """

    DEFAULT_RULES: Dict[str, RelationshipImpactRule] = {
        # 1. Calls: When B calls A, if A changes then B is directly impacted!
        "CALLS": RelationshipImpactRule(
            relationship_type="CALLS",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Caller may be broken or affected by modifications to the callee signature or behavior",
            confidence_factor=1.0,
            category="COMPONENT",
        ),
        # 2. Imports: When B imports A, if A changes then B is impacted
        "IMPORTS": RelationshipImpactRule(
            relationship_type="IMPORTS",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Importing module or file depends on symbols or interface of imported module",
            confidence_factor=0.95,
            category="COMPONENT",
        ),
        # 3. Depends On: When B depends on A, if A changes B is impacted
        "DEPENDS_ON": RelationshipImpactRule(
            relationship_type="DEPENDS_ON",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Dependent component relies on target entity availability and contract",
            confidence_factor=0.95,
            category="COMPONENT",
        ),
        # 4. Consumes: When Consumer consumes Service/Endpoint, if Endpoint changes Consumer is impacted
        "CONSUMES": RelationshipImpactRule(
            relationship_type="CONSUMES",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Consumer client contract may break if provider API schema changes",
            confidence_factor=0.90,
            category="COMPONENT",
        ),
        # 5. Extends: When Derived extends Base, if Base changes Derived is impacted
        "EXTENDS": RelationshipImpactRule(
            relationship_type="EXTENDS",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Derived subclass inherits methods and state from modified base class",
            confidence_factor=1.0,
            category="COMPONENT",
        ),
        # 6. Implements: When Impl implements Interface, if Interface changes Impl is impacted
        "IMPLEMENTS": RelationshipImpactRule(
            relationship_type="IMPLEMENTS",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Implementation must satisfy updated interface contracts",
            confidence_factor=1.0,
            category="COMPONENT",
        ),
        # 7. Persists To: When Repository/Model persists to Database Table
        "PERSISTS_TO": RelationshipImpactRule(
            relationship_type="PERSISTS_TO",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Data access entity affected by alterations to database table schema",
            confidence_factor=0.90,
            category="DATABASE",
        ),
        # 8. Exposes: When Service/Handler exposes API endpoint, changes to handler affect the exposed API
        "EXPOSES": RelationshipImpactRule(
            relationship_type="EXPOSES",
            enabled=True,
            direction=PropagationDirection.FORWARD,
            impact_semantics="Handler changes directly affect exposed public HTTP route behavior",
            confidence_factor=0.95,
            category="API",
        ),
        # 9. Tests: In Digital Twin, TestTestCase --[TESTS]--> TargetFunction.
        # When TargetFunction changes, TestTestCase is impacted!
        "TESTS": RelationshipImpactRule(
            relationship_type="TESTS",
            enabled=True,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Test assertion surface targets changed component; test must be re-run",
            confidence_factor=1.0,
            category="TEST",
        ),
        # 10. Process Participation / Transitions:
        "PARTICIPATES_IN": RelationshipImpactRule(
            relationship_type="PARTICIPATES_IN",
            enabled=True,
            direction=PropagationDirection.FORWARD,
            impact_semantics="Workflow execution step involves modified business logic",
            confidence_factor=0.85,
            category="PROCESS",
        ),
        "TRANSITIONS_TO": RelationshipImpactRule(
            relationship_type="TRANSITIONS_TO",
            enabled=True,
            direction=PropagationDirection.FORWARD,
            impact_semantics="Downstream workflow state may be influenced by prior transition logic",
            confidence_factor=0.85,
            category="PROCESS",
        ),
        # 11. Contains: Structural hierarchy navigation only (disabled by default for dependency propagation)
        "CONTAINS": RelationshipImpactRule(
            relationship_type="CONTAINS",
            enabled=False,
            direction=PropagationDirection.REVERSE,
            impact_semantics="Structural container; not a functional dependency impact by default",
            confidence_factor=0.70,
            category="COMPONENT",
        ),
        "PART_OF": RelationshipImpactRule(
            relationship_type="PART_OF",
            enabled=False,
            direction=PropagationDirection.FORWARD,
            impact_semantics="Structural hierarchy; not a functional dependency impact by default",
            confidence_factor=0.70,
            category="COMPONENT",
        ),
    }

    def __init__(self, custom_rules: Optional[Dict[str, RelationshipImpactRule]] = None):
        self._rules = dict(self.DEFAULT_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

    def get_rule(self, relationship_type: str) -> Optional[RelationshipImpactRule]:
        """Returns the propagation rule for a relationship type if enabled."""
        norm_type = (relationship_type or "").upper()
        rule = self._rules.get(norm_type)
        if rule and rule.enabled:
            return rule
        return None

    def is_propagating(self, relationship_type: str) -> bool:
        """Checks if a relationship type propagates change impact."""
        return self.get_rule(relationship_type) is not None

    def all_rules(self) -> List[RelationshipImpactRule]:
        """Returns all configured rules."""
        return list(self._rules.values())


# Global default rule registry instance
relationship_rule_registry = RelationshipRuleRegistry()
