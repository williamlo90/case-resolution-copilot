from app.persistence.case_persistence.commands import CaseCommandRepository
from app.persistence.case_persistence.queries import CaseQueryRepository
from app.persistence.case_persistence.seeding import CaseSeedRepository


class CaseRepository(CaseQueryRepository, CaseCommandRepository, CaseSeedRepository):
    """Facade preserving the public case persistence contract."""
