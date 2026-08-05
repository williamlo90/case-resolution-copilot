from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.proposals import IntentClassification


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_message: str = Field(min_length=1, max_length=4000)


class ModelGatewayError(RuntimeError):
    pass


class ModelGatewayTimeout(ModelGatewayError):
    pass


class ModelGatewayUnavailable(ModelGatewayError):
    pass


class ModelGateway(Protocol):
    provider_name: str
    model_version: str

    def classify(self, request: ClassificationRequest) -> IntentClassification: ...
