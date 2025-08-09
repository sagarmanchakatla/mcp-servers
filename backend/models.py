# models.py
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    JSON,
)
import datetime
import os

Base = declarative_base()

# Owner who registers, can manage one or more businesses
class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=False)  # phone or email
    registration_token = Column(String, nullable=True, unique=True)  # temporary

    businesses = relationship("Business", back_populates="owner")


class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    name = Column(String, nullable=False)
    business_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    delivery_available = Column(Boolean, default=False)
    delivery_radius_km = Column(Float, nullable=True)
    payment_modes = Column(String, nullable=True)  # comma-separated for v1
    working_hours = Column(String, nullable=True)
    # metadata = Column(JSON, nullable=True)  # arbitrary data
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("Owner", back_populates="businesses")
    items = relationship("InventoryItem", back_populates="business")


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True)
    price = Column(Float, nullable=False, default=0.0)
    qty = Column(Integer, nullable=False, default=0)
    unit = Column(String, nullable=True)  # e.g., pcs, kg, bottle
    # metadata = Column(JSON, nullable=True)

    business = relationship("Business", back_populates="items")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    customer_name = Column(String, nullable=False)
    customer_contact = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending/accepted/shipped/completed/cancelled
    total_amount = Column(Float, nullable=False, default=0.0)
    delivery_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    # metadata = Column(JSON, nullable=True)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=True)
    name = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)

    order = relationship("Order", back_populates="items")


# DB bootstrap / session
def get_sqlite_url(dbfile: str = "shop.db"):
    return f"sqlite+aiosqlite:///{dbfile}"

# For Neon/Postgres later you can replace with env var
# DATABASE_URL = os.getenv("DATABASE_URL", 'postgresql+asyncpg://neondb_owner:npg_gWVqFNe8jxZ2@ep-polished-union-ad75q6hu-pooler.c-2.us-east-1.aws.neon.tech/neondb')

DATABASE_URL = get_sqlite_url()

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# helper to get a session
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
