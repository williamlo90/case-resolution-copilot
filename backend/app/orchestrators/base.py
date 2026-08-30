from dataclasses import dataclass
from typing import Literal, Protocol

from app.analysis.deterministic_decision_engine import DecisionEngine

OrchestratorKind = Literal["production", "utility", "prototype"]


@dataclass(frozen=True, slots=True)
class OrchestratorDescriptor:
    name: str
    framework: str
    kind: OrchestratorKind
    default_runtime: bool
    purpose: str


class DecisionOrchestrator(DecisionEngine, Protocol):
    descriptor: OrchestratorDescriptor
