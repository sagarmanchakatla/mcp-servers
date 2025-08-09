import asyncio
from typing import Annotated, List, Optional
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair  # Updated import
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field
import asyncpg

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
DB_URL = os.environ.get("DATABASE_URL")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"
assert DB_URL is not None, "Please set DATABASE_URL in your .env file"

# --- Auth Provider (Updated to JWTVerifier) ---
class SimpleBearerAuthProvider(JWTVerifier):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: Optional[str] = None

# --- Product Models ---
class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float

# --- Initialize MCP Server ---
mcp = FastMCP(
    "Product Management Server",
    auth=SimpleBearerAuthProvider(TOKEN)  # Will be defined below
)

# --- Database Connection Pool ---
db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DB_URL)
    return db_pool

# --- Product Tool Description ---
class ProductToolDescription(RichToolDescription):
    description: str = "Retrieve product information from the database"
    use_when: str = "Use this tool to get product information by various criteria"
    side_effects: str = "Queries the database and returns product information"

# --- Product Tool ---
@mcp.tool(description=ProductToolDescription().model_dump_json())
async def get_users(
    # category: Annotated[Optional[str], Field(description="Filter products by category")] = None,
    # max_price: Annotated[Optional[float], Field(description="Maximum price filter")] = None,
    # limit: Annotated[int, Field(description="Maximum number of products to return", ge=1, le=100)] = 10
) -> List[Product]:
    pool = await get_db_pool()
    
    query = "SELECT id, name, category, price FROM products WHERE true"
    params = []
    
    if category:
        query += " AND category = $" + str(len(params) + 1)
        params.append(category)
    
    if max_price is not None:
        query += " AND price <= $" + str(len(params) + 1)
        params.append(max_price)
    
    query += f" LIMIT ${len(params) + 1}"
    params.append(limit)
    
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            logger.info(f"Fetched {len(rows)} products from the database")
            return [Product(
                id=row['id'],
                name=row['name'],
                category=row['category'],
                price=row['price']
            ) for row in rows]
    except Exception as e:
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

# --- Validate Tool (Required by Puch AI) ---
@mcp.tool
async def validate() -> str:
    """Required by Puch AI — returns your phone number for authentication."""
    return MY_NUMBER

# --- Run MCP Server ---
async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")