import asyncio
import asyncpg
import ssl
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        conn = await asyncpg.connect(
            dsn=os.getenv("DATABASE_URL"),
            ssl=ssl_context
        )
        print("✅ Successfully connected to database!")
        
        # Test a simple query
        result = await conn.fetch("SELECT 1")
        print("✅ Simple query test passed:", result)
        
        # Test users table query
        users = await conn.fetch('SELECT * FROM products')
        print("✅ Users query test passed. Found users:", len(users))
        
        await conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")

asyncio.run(test_connection())