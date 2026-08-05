from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class CustomerSnapshotRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    customer_id: str
    name: str
    tier: str
    locale: str
    contact: EmailStr
    captured_at: datetime


class BookingSnapshotRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    reference: str
    service_date_label: str
    status: str
    provider: str
    itinerary: str
    passengers: int
    paid_amount: Decimal
    currency: str
    captured_at: datetime
