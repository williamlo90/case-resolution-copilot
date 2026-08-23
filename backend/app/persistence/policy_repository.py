from app.persistence.policies.authoring import PolicyAuthoringRepository
from app.persistence.policies.evidence import PolicyEvidenceRepository
from app.persistence.policies.legacy import LegacyPolicyRepository
from app.persistence.policies.lifecycle import PolicyLifecycleRepository
from app.persistence.policies.queries import PolicyQueryRepository
from app.persistence.policies.retrieval_v2 import PolicyRetrievalV2Repository


class PolicyRepository(
    PolicyQueryRepository,
    PolicyAuthoringRepository,
    LegacyPolicyRepository,
    PolicyLifecycleRepository,
    PolicyEvidenceRepository,
    PolicyRetrievalV2Repository,
):
    """Facade preserving the public governed-policy persistence contract."""
