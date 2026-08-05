from app.persistence.policies.authoring import PolicyAuthoringRepository
from app.persistence.policies.evidence import PolicyEvidenceRepository
from app.persistence.policies.legacy import LegacyPolicyRepository
from app.persistence.policies.lifecycle import PolicyLifecycleRepository
from app.persistence.policies.queries import PolicyQueryRepository


class PolicyRepository(
    PolicyQueryRepository,
    PolicyAuthoringRepository,
    LegacyPolicyRepository,
    PolicyLifecycleRepository,
    PolicyEvidenceRepository,
):
    """Facade preserving the public governed-policy persistence contract."""
