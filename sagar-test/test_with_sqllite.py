import os
import asyncio
import logging
from typing import Annotated, List

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.types import INTERNAL_ERROR
from pydantic import BaseModel, Field

from sqlalchemy import Integer, String, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy.future import select

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# -------------------- Load environment --------------------
load_dotenv()
TOKEN = os.getenv("AUTH_TOKEN")
MY_NUMBER = os.getenv("MY_NUMBER")

# SQLite database file
DB_FILE = "notes.db"
PG_URL = f"sqlite+aiosqlite:///{DB_FILE}"

assert TOKEN, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER, "Please set MY_NUMBER in your .env file"

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

# -------------------- SQLAlchemy Setup --------------------
Base = declarative_base()
engine = create_async_engine(PG_URL, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# -------------------- Models --------------------
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

class NoteModel(BaseModel):
    id: int
    user_id: str
    content: str

# -------------------- MCP Init --------------------
mcp = FastMCP("Notes Management Server", auth=SimpleBearerAuthProvider(TOKEN))

# -------------------- Tools --------------------
@mcp.tool(description="Retrieve notes for a specific user")
async def get_notes(
    user_id: Annotated[str, Field(description="User ID to retrieve notes for")],
    limit: Annotated[int, Field(description="Max number of notes to return", ge=1, le=100)] = 10
) -> List[NoteModel]:
    try:
        async with AsyncSessionLocal() as db:
            # Add filter for user_id and proper ordering
            stmt = select(Note).where(Note.user_id == user_id).order_by(Note.id.desc()).limit(limit)
            result = await db.execute(stmt)
            notes = result.scalars().all()
            
            if not notes:
                return []
                
            return [NoteModel(id=n.id, user_id=n.user_id, content=n.content) for n in notes]
    except Exception as e:
        logger.exception("Failed to fetch notes")
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"Failed to fetch notes: {str(e)}"
        ))

@mcp.tool(description="Insert a new note into SQLite")
async def add_note(
    user_id: Annotated[str, Field(description="User ID for the note")],
    content: Annotated[str, Field(description="Note content")]
) -> str:
    try:
        async for db in get_db():
            note = Note(user_id=user_id, content=content)
            db.add(note)
            await db.commit()
            await db.refresh(note)
            return f"✅ Note {note.id} added for user {user_id}"
    except Exception as e:
        logger.exception("Insert failed")
        return f"❌ Failed to insert note: {e}"

@mcp.tool(description="Update an existing note in SQLite")
async def update_note(
    id: Annotated[int, Field(description="ID of the note to update")],
    content: Annotated[str, Field(description="Updated content of the note")]
) -> str:
    try:
        async for db in get_db():
            stmt = select(Note).where(Note.id == id)
            result = await db.execute(stmt)
            note = result.scalars().first()
            if not note:
                return f"❌ Note with id {id} not found."
            note.content = content
            await db.commit()
            return f"✅ Note {id} updated."
    except Exception as e:
        logger.exception("Update failed")
        return f"❌ Failed to update note: {e}"

@mcp.tool(description="Delete a note from SQLite by ID")
async def delete_note(
    id: Annotated[int, Field(description="ID of the note to delete")]
) -> str:
    try:
        async for db in get_db():
            stmt = select(Note).where(Note.id == id)
            result = await db.execute(stmt)
            note = result.scalars().first()
            if not note:
                return f"❌ Note with id {id} not found."
            await db.delete(note)
            await db.commit()
            return f"✅ Note {id} deleted."
    except Exception as e:
        logger.exception("Delete failed")
        return f"❌ Failed to delete note: {e}"

@mcp.tool
async def validate() -> str:
    """Required by PushAI — returns your phone number for authentication."""
    return MY_NUMBER

@mcp.tool
async def ping() -> str:
    return "pong"

# -------------------- Run Server --------------------
async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await init_models()
    logger.info("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
