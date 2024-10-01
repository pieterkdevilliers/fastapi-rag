from sqlmodel import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

DB_FILE = "source_db.db"

engine = create_engine(f'sqlite:///{DB_FILE}', echo=True)

async_engine = create_async_engine(f'sqlite+aiosqlite:///{DB_FILE}', echo=True)
