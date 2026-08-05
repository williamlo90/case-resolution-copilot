import json
from datetime import date
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from app.persistence.database import Database
from app.persistence.models import PolicyChunkModel, PolicyDocumentVersionModel
from app.retrieval.embeddings import EMBEDDING_VERSION, embed

CORPUS_VERSION = "support-policy-corpus-v1"
CHUNKING_VERSION = "clause-v1"
INDEX_VERSION = "policy-index-v1"


class PolicyClause(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clause: str = Field(min_length=1)
    text: str = Field(min_length=20)


class PolicySource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    version: int = Field(gt=0)
    title: str
    case_category: str
    plan: str
    jurisdiction: str
    customer_tier: str
    effective_from: date
    effective_to: date | None
    clauses: list[PolicyClause] = Field(min_length=1)


def ingest_policy(database: Database, path: Path) -> None:
    raw = path.read_bytes()
    source = PolicySource.model_validate(json.loads(raw))
    content_hash = sha256(raw).hexdigest()
    with database.session() as session:
        existing = session.scalar(
            select(PolicyDocumentVersionModel).where(
                PolicyDocumentVersionModel.source_id == source.source_id,
                PolicyDocumentVersionModel.version == source.version,
            )
        )
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ValueError("A published policy version cannot be replaced.")
            return
        document = PolicyDocumentVersionModel(
            source_id=source.source_id,
            version=source.version,
            title=source.title,
            case_category=source.case_category,
            plan=source.plan,
            jurisdiction=source.jurisdiction,
            customer_tier=source.customer_tier,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
            lifecycle_status="active",
            content_hash=content_hash,
            corpus_version=CORPUS_VERSION,
        )
        session.add(document)
        session.flush()
        session.execute(
            delete(PolicyChunkModel).where(PolicyChunkModel.policy_version_id == document.id)
        )
        for clause in source.clauses:
            session.add(
                PolicyChunkModel(
                    policy_version_id=document.id,
                    clause=clause.clause,
                    text=clause.text,
                    content_hash=sha256(clause.text.encode()).hexdigest(),
                    chunking_version=CHUNKING_VERSION,
                    embedding_version=EMBEDDING_VERSION,
                    index_version=INDEX_VERSION,
                    embedding=embed(clause.text),
                )
            )
