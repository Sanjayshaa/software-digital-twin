"""
Phase 4 — Centralized Relationship Impact Rules Registry.
Defines explicit propagation directions, impact semantics, and confidence behaviors
for every typed relationship in the Digital Twin.
"""

from typing import Dict, Optional, List
from app.services.impact.models import (
    RelationshipImpactRule,
    ImpactPropagationRule,
    PropagationDirection,
    ImpactClassification,
    ChangeKind,
)


class RelationshipRuleRegistry:
    """
    Centralized registry of relationship propagation rules.
    Determines whether and how a relationship type propagates change impact.
    Formalized in Phase 8.9 for reproducible and inspectable research evaluation.
    """

    # Backward-compatible relationship rules
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

    # Canonical Phase 8.9 Formally Specified Propagation Rules
    CANONICAL_PROPAGATION_RULES: Dict[str, ImpactPropagationRule] = {
        "CALLS": ImpactPropagationRule(
            rule_id="RULE_CALLS_CALLER_IMPACT",
            relationship_type="CALLS",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["AST_CALL_EXPRESSION", "QUALIFIED_SYMBOL_MATCH"],
            confidence_factor=1.0,
            max_depth_applicability=5,
            rationale="Caller invoking modified callee may break due to signature, return value, or behavioral changes.",
            category="COMPONENT",
        ),
        "IMPORTS": ImpactPropagationRule(
            rule_id="RULE_IMPORTS_IMPORTER_IMPACT",
            relationship_type="IMPORTS",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["IMPORT_STATEMENT", "MODULE_RESOLUTION"],
            confidence_factor=0.95,
            max_depth_applicability=5,
            rationale="Importing module depends on module namespace or exported interface of the imported target.",
            category="COMPONENT",
        ),
        "DEPENDS_ON": ImpactPropagationRule(
            rule_id="RULE_DEPENDS_ON_DEPENDENT_IMPACT",
            relationship_type="DEPENDS_ON",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["PACKAGE_SPECIFICATION", "CONFIGURATION_REFERENCE"],
            confidence_factor=0.95,
            max_depth_applicability=5,
            rationale="Dependent component relies on service contract and runtime availability of target.",
            category="COMPONENT",
        ),
        "CONSUMES": ImpactPropagationRule(
            rule_id="RULE_CONSUMES_CLIENT_IMPACT",
            relationship_type="CONSUMES",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["HTTP_CLIENT_CALL", "RPC_INVOCATION"],
            confidence_factor=0.90,
            max_depth_applicability=5,
            rationale="Consumer client contract may fail if provider API schema or payload semantics change.",
            category="COMPONENT",
        ),
        "EXTENDS": ImpactPropagationRule(
            rule_id="RULE_EXTENDS_SUBCLASS_IMPACT",
            relationship_type="EXTENDS",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["CLASS_DECLARATION", "INHERITANCE_SPECIFICATION"],
            confidence_factor=1.0,
            max_depth_applicability=5,
            rationale="Derived subclass inherits methods, fields, and constructors from the modified base class.",
            category="COMPONENT",
        ),
        "IMPLEMENTS": ImpactPropagationRule(
            rule_id="RULE_IMPLEMENTS_IMPL_IMPACT",
            relationship_type="IMPLEMENTS",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["INTERFACE_IMPLEMENTATION", "TYPE_DECLARATION"],
            confidence_factor=1.0,
            max_depth_applicability=5,
            rationale="Implementing class must satisfy the modified interface contract and abstract methods.",
            category="COMPONENT",
        ),
        "PERSISTS_TO": ImpactPropagationRule(
            rule_id="RULE_PERSISTS_TO_DATA_IMPACT",
            relationship_type="PERSISTS_TO",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["ORM_MAPPING", "SQL_STATEMENT"],
            confidence_factor=0.90,
            max_depth_applicability=5,
            rationale="Data access entities and ORM mappings are affected by alterations to table schema.",
            category="DATABASE",
        ),
        "EXPOSES": ImpactPropagationRule(
            rule_id="RULE_EXPOSES_API_IMPACT",
            relationship_type="EXPOSES",
            change_kind="ANY",
            direction=PropagationDirection.FORWARD,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["ROUTE_DECORATOR", "ENDPOINT_REGISTRATION"],
            confidence_factor=0.95,
            max_depth_applicability=5,
            rationale="Handler or controller implementation changes directly affect the behavior of the exposed HTTP route.",
            category="API",
        ),
        "TESTS": ImpactPropagationRule(
            rule_id="RULE_TESTS_TEST_IMPACT",
            relationship_type="TESTS",
            change_kind="ANY",
            direction=PropagationDirection.REVERSE,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["TEST_RUNNER_TARGET", "ASSERTION_SURFACE"],
            confidence_factor=1.0,
            max_depth_applicability=5,
            rationale="Test assertion surface targets changed component; test must be executed to verify regression.",
            category="TEST",
        ),
        "PARTICIPATES_IN": ImpactPropagationRule(
            rule_id="RULE_PARTICIPATES_PROCESS_IMPACT",
            relationship_type="PARTICIPATES_IN",
            change_kind="ANY",
            direction=PropagationDirection.FORWARD,
            impact_classification=ImpactClassification.DIRECT,
            evidence_requirements=["WORKFLOW_STEP_MAPPING"],
            confidence_factor=0.85,
            max_depth_applicability=5,
            rationale="Workflow or business process execution step involves the modified component logic.",
            category="PROCESS",
        ),
        "TRANSITIONS_TO": ImpactPropagationRule(
            rule_id="RULE_TRANSITIONS_STATE_IMPACT",
            relationship_type="TRANSITIONS_TO",
            change_kind="ANY",
            direction=PropagationDirection.FORWARD,
            impact_classification=ImpactClassification.PROVEN_TRANSITIVE,
            evidence_requirements=["STATE_TRANSITION_EDGE"],
            confidence_factor=0.85,
            max_depth_applicability=5,
            rationale="Downstream workflow state may be influenced by logic in prior transition steps.",
            category="PROCESS",
        ),
    }

    def __init__(
        self,
        custom_rules: Optional[Dict[str, RelationshipImpactRule]] = None,
        custom_canonical_rules: Optional[Dict[str, ImpactPropagationRule]] = None,
    ):
        self._rules = dict(self.DEFAULT_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

        self._canonical_rules = dict(self.CANONICAL_PROPAGATION_RULES)
        if custom_canonical_rules:
            self._canonical_rules.update(custom_canonical_rules)

    def get_rule(self, relationship_type: str) -> Optional[RelationshipImpactRule]:
        """Returns the propagation rule for a relationship type if enabled."""
        norm_type = (relationship_type or "").upper()
        rule = self._rules.get(norm_type)
        if rule and rule.enabled:
            return rule
        return None

    def get_canonical_rule(self, relationship_type: str, change_kind: str = "ANY") -> Optional[ImpactPropagationRule]:
        """
        Returns the formal ImpactPropagationRule for the given relationship type and change kind.
        """
        norm_type = (relationship_type or "").upper()
        rule = self._canonical_rules.get(norm_type)
        if rule and rule.enabled:
            return rule
        return None

    def is_propagating(self, relationship_type: str) -> bool:
        """Checks if a relationship type propagates change impact."""
        return self.get_rule(relationship_type) is not None

    def all_rules(self) -> List[RelationshipImpactRule]:
        """Returns all configured legacy rules."""
        return list(self._rules.values())

    def all_canonical_rules(self) -> List[ImpactPropagationRule]:
        """Returns all formally specified canonical propagation rules."""
        return list(self._canonical_rules.values())


# Global default rule registry instance
relationship_rule_registry = RelationshipRuleRegistry()
