from pydantic import BaseModel, ConfigDict, Field


class AddressIn(BaseModel):
    label: str | None = Field(default=None, max_length=40)
    recipient_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=24)
    division: str = Field(min_length=1, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    city: str = Field(min_length=1, max_length=80)
    area: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=16)
    street_line1: str = Field(min_length=1, max_length=255)
    street_line2: str | None = Field(default=None, max_length=255)
    landmark: str | None = Field(default=None, max_length=255)
    is_default_shipping: bool = False
    is_default_billing: bool = False


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str | None
    recipient_name: str
    phone: str
    division: str
    district: str | None
    city: str
    area: str | None
    postal_code: str | None
    street_line1: str
    street_line2: str | None
    landmark: str | None
    is_default_shipping: bool
    is_default_billing: bool
