import os
import asyncio
import logging
from typing import Annotated, List, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.types import INTERNAL_ERROR
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient  # MongoDB async client

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -------------------- Load environment --------------------
load_dotenv()
TOKEN = os.getenv("AUTH_TOKEN")
MY_NUMBER = os.getenv("MY_NUMBER")
MONGO_URL = os.getenv("MONGO_URL")  # mongodb:// or mongodb+srv://

assert TOKEN, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER, "Please set MY_NUMBER in your .env file"
assert MONGO_URL, "Please set MONGO_URL in your .env file"

# -------------------- Auth --------------------
class SimpleBearerAuthProvider(JWTVerifier):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str):
        if token == self.token:
            from mcp.server.auth.provider import AccessToken
            return AccessToken(token=token, client_id="push-client", scopes=["*"], expires_at=None)
        return None

# -------------------- Models --------------------
class Product(BaseModel):
    id: int
    name: str
    description: str
    price: int

# -------------------- MCP Init --------------------
mcp = FastMCP("Product Management Server", auth=SimpleBearerAuthProvider(TOKEN))
mongo_client = None

async def get_db():
    """Connect to MongoDB and return the correct DB."""
    global mongo_client
    if mongo_client is None:
        logger.info("Connecting to MongoDB...")
        mongo_client = AsyncIOMotorClient(MONGO_URL)
    return mongo_client["productsDB"]  # ✅ correct name

# -------------------- Tools --------------------
# -------------------- Tools --------------------
@mcp.tool(description="Retrieve product information from MongoDB")
async def get_products(
    category: Annotated[Optional[str], Field(description="Filter products by category")] = None,
    max_price: Annotated[Optional[int], Field(description="Maximum price filter (integer)")] = None,
    limit: Annotated[int, Field(description="Max number of products to return", ge=1, le=100)] = 10
) -> List[Product]:
    """Fetch products from MongoDB with optional filters."""
    try:
        db = await get_db()
        query = {}
        if category:
            query["category"] = category
        if max_price is not None:
            query["price"] = {"$lte": max_price}

        logger.info(f"MongoDB Query: {query} | Limit: {limit}")
        cursor = db["products"].find(query).limit(limit)

        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                results.append(Product(**doc))
            except Exception as e:
                logger.warning(f"Skipping invalid document: {doc} | Error: {e}")

        logger.info(f"Fetched {len(results)} products")
        return results

    except Exception as e:
        logger.exception("MongoDB query failed")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"MongoDB error: {e}"))


@mcp.tool(description="Insert a new product into MongoDB")
async def insert_product(
    id: Annotated[int, Field(description="Unique integer ID for the product")],
    name: Annotated[str, Field(description="Name of the product")],
    description: Annotated[str, Field(description="Product description")],
    price: Annotated[int, Field(description="Product price in ₹")],
    category: Annotated[Optional[str], Field(description="Optional category of the product")] = None
) -> str:
    """Insert a new product into MongoDB."""
    try:
        db = await get_db()
        existing = await db["products"].find_one({"id": id})
        if existing:
            return f"❌ Product with id {id} already exists."

        product_data = {
            "id": id,
            "name": name,
            "description": description,
            "price": price,
        }
        if category:
            product_data["category"] = category

        await db["products"].insert_one(product_data)
        return f"✅ Product '{name}' inserted successfully."

    except Exception as e:
        logger.exception("Insert failed")
        return f"❌ Failed to insert product: {e}"


@mcp.tool(description="Update an existing product in MongoDB")
async def update_product(
    id: Annotated[int, Field(description="ID of the product to update")],
    name: Annotated[Optional[str], Field(description="Updated name of the product")] = None,
    description: Annotated[Optional[str], Field(description="Updated description of the product")] = None,
    price: Annotated[Optional[int], Field(description="Updated price in ₹")] = None,
    category: Annotated[Optional[str], Field(description="Updated category of the product")] = None
) -> str:
    """Update product details by ID."""
    try:
        db = await get_db()
        update_fields = {}
        if name is not None:
            update_fields["name"] = name
        if description is not None:
            update_fields["description"] = description
        if price is not None:
            update_fields["price"] = price
        if category is not None:
            update_fields["category"] = category

        if not update_fields:
            return "❌ No fields to update."

        result = await db["products"].update_one({"id": id}, {"$set": update_fields})
        if result.matched_count == 0:
            return f"❌ Product with id {id} not found."

        return f"✅ Product {id} updated successfully."

    except Exception as e:
        logger.exception("Update failed")
        return f"❌ Failed to update product: {e}"


@mcp.tool(description="Delete a product from MongoDB by ID")
async def delete_product(
    id: Annotated[int, Field(description="ID of the product to delete")]
) -> str:
    """Delete a product by ID."""
    try:
        db = await get_db()
        result = await db["products"].delete_one({"id": id})
        if result.deleted_count == 0:
            return f"❌ Product with id {id} not found."
        return f"✅ Product {id} deleted successfully."

    except Exception as e:
        logger.exception("Delete failed")
        return f"❌ Failed to delete product: {e}"

@mcp.tool
async def validate() -> str:
    """Required by PushAI — returns your phone number for authentication."""
    return MY_NUMBER

# -------------------- Run Server --------------------
async def main():
    logger.info("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
