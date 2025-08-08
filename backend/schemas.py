# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class InventoryItemIn(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    price: float = Field(..., ge=0)
    qty: int = Field(..., ge=0)
    unit: Optional[str] = None

class InventoryItemOut(InventoryItemIn):
    id: int

class BusinessOut(BaseModel):
    id: int
    owner_id: int
    name: str
    business_type: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    delivery_available: Optional[bool] = False

class PlaceOrderItem(BaseModel):
    item_id: int
    qty: int = Field(..., ge=1)

class PlaceOrderIn(BaseModel):
    customer_name: str
    customer_contact: str
    delivery_address: Optional[str] = None
    items: List[PlaceOrderItem]
