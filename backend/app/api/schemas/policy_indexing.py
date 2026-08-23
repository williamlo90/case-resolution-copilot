from pydantic import BaseModel, ConfigDict


class PolicyIndexDrainData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claimed_jobs: int
    completed_jobs: int
    failed_jobs: int
    indexed_clauses: int
    skipped_clauses: int


class PolicyIndexDrainEnvelope(BaseModel):
    data: PolicyIndexDrainData
