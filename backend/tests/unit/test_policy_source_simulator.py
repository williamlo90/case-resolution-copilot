from app.integrations.policy_source_simulator import DeterministicPolicySourceSimulator
from app.retrieval.policy_parser import parse_policy_source


def test_policy_simulator_covers_each_generic_case_category() -> None:
    policies = DeterministicPolicySourceSimulator().fetch_policies()
    covered = {category for policy in policies for category in policy.applicability.case_categories}

    assert {
        "billing_dispute",
        "refund_request",
        "account_access",
        "service_exception",
    } <= covered
    assert all(parse_policy_source(policy.source_text, policy.applicability) for policy in policies)


def test_policy_simulator_has_distinct_decision_scopes() -> None:
    policies = DeterministicPolicySourceSimulator().fetch_policies()

    assert len({policy.applicability.decision_scope for policy in policies}) == len(policies)
