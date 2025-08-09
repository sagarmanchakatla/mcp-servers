# main.py
import os
import asyncio
import logging
import secrets
from typing import List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.types import INTERNAL_ERROR
from pydantic import BaseModel, Field

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from sqlalchemy.future import select
from sqlalchemy import func


from models import (
    init_db,
    AsyncSessionLocal,
    Owner,
    Business,
    InventoryItem,
    Order,
    OrderItem,
)
from schemas import (
    InventoryItemIn,
    InventoryItemOut,
    BusinessOut,
    PlaceOrderIn,
)

from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mcp-shop")

TOKEN = os.getenv("AUTH_TOKEN", "dev-token-please-change")
logger.info(f"Auth token: {TOKEN}")
MY_NUMBER = os.getenv("MY_NUMBER", "+0000000000")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8087))

# templates
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)

# Simple auth provider (keeps same pattern you've used)
class SimpleBearerAuthProvider(JWTVerifier):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token
        logger.info("Auth provider initialized (token presence only).")

    async def load_access_token(self, token: str):
        if token == self.token:
            from mcp.server.auth.provider import AccessToken
            return AccessToken(token=token, client_id="push-client", scopes=["*"], expires_at=None)
        return None

mcp = FastMCP("Local Shop Management", auth=SimpleBearerAuthProvider(TOKEN))

# -------------------------
# Helpers
# -------------------------
async def create_registration_token(session, owner_name: str, owner_contact: str) -> str:
    token = secrets.token_urlsafe(16)
    owner = Owner(name=owner_name, contact=owner_contact, registration_token=token)
    session.add(owner)
    await session.commit()
    await session.refresh(owner)
    logger.info("Created registration token for owner_id=%s token=%s", owner.id, token)
    return token, owner.id

async def lookup_owner_by_token(session, token: str):
    q = select(Owner).where(Owner.registration_token == token)
    result = await session.execute(q)
    return result.scalars().first()

# -------------------------
# MCP tools
# -------------------------
@mcp.tool(description="Get a registration URL for the owner (owner provides name & contact via args)")
async def register(owner_name: str, owner_contact: str) -> str:
    """
    Returns a URL the owner can open to fill registration form.
    Example: call mcp tool register("Alice", "+911234567890")
    """
    logger.info("register() tool called for owner_name=%s contact=%s", owner_name, owner_contact)
    async with AsyncSessionLocal() as session:
        token = secrets.token_urlsafe(20)
        owner = Owner(name=owner_name, contact=owner_contact, registration_token=token)
        session.add(owner)
        await session.commit()
        await session.refresh(owner)
        url = f"http://{HOST}:{PORT}/register?token={token}"
        logger.info("Registration URL created: %s", url)
        return url

@mcp.tool(description="List businesses (optional search q)")
async def list_businesses(q: Optional[str] = None) -> List[BusinessOut]:
    logger.info("list_businesses called q=%s", q)
    async with AsyncSessionLocal() as session:
        stmt = select(Business)
        if q:
            stmt = stmt.where(func.lower(Business.name).like(f"%{q.lower()}%"))
        result = await session.execute(stmt)
        rows = result.scalars().all()
        logger.info("Found %s businesses", len(rows))
        return [
            BusinessOut(
                id=b.id,
                owner_id=b.owner_id,
                name=b.name,
                business_type=b.business_type,
                description=b.description,
                address=b.address,
                city=b.city,
                delivery_available=bool(b.delivery_available),
            )
            for b in rows
        ]

@mcp.tool(description="Get details for a business")
async def get_business_info(business_id: int) -> BusinessOut:
    async with AsyncSessionLocal() as session:
        stmt = select(Business).where(Business.id == business_id)
        result = await session.execute(stmt)
        b = result.scalars().first()
        if not b:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Business {business_id} not found"))
        return BusinessOut(
            id=b.id,
            owner_id=b.owner_id,
            name=b.name,
            business_type=b.business_type,
            description=b.description,
            address=b.address,
            city=b.city,
            delivery_available=bool(b.delivery_available),
        )

# Owner tools
@mcp.tool(description="View inventory for an owner/business")
async def view_inventory(owner_id: int) -> List[InventoryItemIn]:
    logger.info("view_inventory called owner_id=%s", owner_id)
    async with AsyncSessionLocal() as session:
        stmt = select(InventoryItem).join(Business).where(Business.owner_id == owner_id)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            InventoryItemIn(
                name=r.name,
                sku=r.sku,
                category=r.category,
                price=float(r.price),
                qty=int(r.qty),
                unit=r.unit,
            )
            for r in rows
        ]

@mcp.tool(description="Add an item to inventory")
async def add_item(
    owner_id: int,
    business_id: int,
    name: str,
    sku: Optional[str] = None,
    category: Optional[str] = None,
    price: float = 0.0,
    qty: int = 0,
    unit: Optional[str] = None
) -> str:
    logger.info("add_item owner_id=%s business_id=%s name=%s qty=%s", owner_id, business_id, name, qty)
    async with AsyncSessionLocal() as session:
        stmt = select(Business).where(Business.id == business_id, Business.owner_id == owner_id)
        res = await session.execute(stmt)
        b = res.scalars().first()
        if not b:
            return f"Business {business_id} not found or not owned by {owner_id}"
        item = InventoryItem(
            business_id=business_id,
            name=name,
            sku=sku,
            category=category,
            price=price,
            qty=qty,
            unit=unit,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return f"Item {item.id} added."

@mcp.tool(description="Update inventory item")
async def update_item(
    owner_id: int,
    item_id: int,
    name: Optional[str] = None,
    price: Optional[float] = None,
    qty: Optional[int] = None,
    category: Optional[str] = None
) -> str:
    logger.info("update_item owner_id=%s item_id=%s", owner_id, item_id)
    async with AsyncSessionLocal() as session:
        # find item and ensure owner
        stmt = select(InventoryItem).where(InventoryItem.id == item_id).join(Business).where(Business.owner_id == owner_id)
        res = await session.execute(stmt)
        item = res.scalars().first()
        if not item:
            return "Item not found or not authorized."
        if name is not None:
            item.name = name
        if price is not None:
            item.price = price
        if qty is not None:
            item.qty = qty
        if category is not None:
            item.category = category
        await session.commit()
        return "Item updated."

@mcp.tool(description="Delete inventory item")
async def delete_item(owner_id: int, item_id: int) -> str:
    logger.info("delete_item owner_id=%s item_id=%s", owner_id, item_id)
    async with AsyncSessionLocal() as session:
        stmt = select(InventoryItem).where(InventoryItem.id == item_id).join(Business).where(Business.owner_id == owner_id)
        res = await session.execute(stmt)
        item = res.scalars().first()
        if not item:
            return "Item not found or not authorized."
        await session.delete(item)
        await session.commit()
        return "Item deleted."

@mcp.tool(description="List orders for an owner")
async def list_orders(owner_id: int) -> List[dict]:
    logger.info("list_orders owner_id=%s", owner_id)
    async with AsyncSessionLocal() as session:
        stmt = select(Order).join(Business).where(Business.owner_id == owner_id).order_by(Order.created_at.desc())
        res = await session.execute(stmt)
        orders = res.scalars().all()
        out = []
        for o in orders:
            out.append({
                "id": o.id,
                "customer_name": o.customer_name,
                "customer_contact": o.customer_contact,
                "status": o.status,
                "total_amount": float(o.total_amount),
                "created_at": str(o.created_at),
            })
        return out

@mcp.tool(description="Mark order shipped")
async def mark_order_shipped(owner_id: int, order_id: int) -> str:
    logger.info("mark_order_shipped owner_id=%s order_id=%s", owner_id, order_id)
    async with AsyncSessionLocal() as session:
        stmt = select(Order).where(Order.id == order_id).join(Business).where(Business.owner_id == owner_id)
        res = await session.execute(stmt)
        order = res.scalars().first()
        if not order:
            return "Order not found or not authorized."
        order.status = "shipped"
        await session.commit()
        return "Order marked shipped."

# Customer tools
@mcp.tool(description="Place order at a business (simple order)")
async def place_order(business_id: int, customer_name: str, customer_contact: str, items: List[dict]) -> str:
    """
    items: list of dicts like [{"item_id": 1, "qty": 2}, ...]
    """
    logger.info("place_order business_id=%s customer=%s items=%s", business_id, customer_name, items)
    async with AsyncSessionLocal() as session:
        # fetch items and compute total
        total = 0.0
        order_items = []
        for it in items:
            item_id = int(it.get("item_id"))
            qty = int(it.get("qty", 1))
            stmt = select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.business_id == business_id)
            res = await session.execute(stmt)
            db_item = res.scalars().first()
            if not db_item:
                return f"Item {item_id} not found for business {business_id}"
            if db_item.qty < qty:
                return f"Not enough stock for item {db_item.name}"
            line_total = float(db_item.price) * qty
            total += line_total
            order_items.append((db_item, qty, float(db_item.price), line_total))

        # create order
        order = Order(business_id=business_id, customer_name=customer_name, customer_contact=customer_contact, status="pending", total_amount=total)
        session.add(order)
        await session.commit()
        await session.refresh(order)

        # create order items and update inventory
        for db_item, qty, unit_price, line_total in order_items:
            oi = OrderItem(order_id=order.id, inventory_item_id=db_item.id, name=db_item.name, qty=qty, unit_price=unit_price, total_price=line_total)
            session.add(oi)
            db_item.qty = db_item.qty - qty
        await session.commit()
        return f"Order placed: {order.id} total={total:.2f}"

# validation tool
@mcp.tool
async def validate() -> str:
    return MY_NUMBER

# -------------------------
# HTTP registration endpoints
# -------------------------
@mcp.custom_route("/register", methods=["GET"])
async def serve_register(request: Request):
    token = request.query_params.get("token")
    if not token:
        return PlainTextResponse("Missing token", status_code=400)
    template = env.get_template("register_form.html")
    html = template.render(token=token)
    return HTMLResponse(html)

@mcp.custom_route("/register/submit", methods=["POST"])
async def submit_register(request: Request):
    form = await request.form()
    token = form.get("token")
    owner_name = form.get("owner_name")
    owner_contact = form.get("owner_contact")
    business_name = form.get("business_name")
    business_type = form.get("business_type")
    description = form.get("description")
    address = form.get("address")
    city = form.get("city")
    postal_code = form.get("postal_code")
    delivery_available = bool(form.get("delivery_available"))
    delivery_radius = form.get("delivery_radius") or None
    payment_modes = form.get("payment_modes") or None

    item_name = form.get("item_name")
    item_sku = form.get("item_sku")
    item_category = form.get("item_category")
    item_price = form.get("item_price") or None
    item_qty = form.get("item_qty") or None
    item_unit = form.get("item_unit") or None

    async with AsyncSessionLocal() as session:
        owner = await lookup_owner_by_token(session, token)
        if not owner:
            return PlainTextResponse("Invalid token", status_code=400)

        # update owner details
        owner.name = owner_name or owner.name
        owner.contact = owner_contact or owner.contact
        # clear token to prevent reuse
        owner.registration_token = None
        session.add(owner)
        await session.commit()
        await session.refresh(owner)

        # create business
        b = Business(
            owner_id=owner.id,
            name=business_name,
            business_type=business_type,
            description=description,
            address=address,
            city=city,
            postal_code=postal_code,
            delivery_available=delivery_available,
            delivery_radius_km=float(delivery_radius) if delivery_radius else None,
            payment_modes=payment_modes,
        )
        session.add(b)
        await session.commit()
        await session.refresh(b)

        # optional initial item
        if item_name:
            try:
                price_v = float(item_price) if item_price else 0.0
            except Exception:
                price_v = 0.0
            try:
                qty_v = int(item_qty) if item_qty else 0
            except Exception:
                qty_v = 0
            it = InventoryItem(business_id=b.id, name=item_name, sku=item_sku, category=item_category, price=price_v, qty=qty_v, unit=item_unit)
            session.add(it)
            await session.commit()

    template = env.get_template("register_success.html")
    return HTMLResponse(template.render(owner_id=owner.id, business_id=b.id))

# -------------------------
# Startup
# -------------------------
async def startup():
    logger.info("Initializing DB...")
    await init_db()
    logger.info("DB initialized.")

if __name__ == "__main__":
    asyncio.run(startup())
    logger.info("Starting MCP server...")
    asyncio.run(mcp.run_async("streamable-http", host=HOST, port=PORT))
