import os
from dotenv import load_dotenv
from sqlmodel import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

if os.environ.get('ENVIRONMENT') == 'development':

    DB_FILE = "source_db.db"

    engine = create_engine(f'sqlite:///{DB_FILE}', echo=True)

    async_engine = create_async_engine(f'sqlite+aiosqlite:///{DB_FILE}', echo=True)

else:

    DATABASE_URL = os.environ.get('DATABASE_URL')
    print(f"DATABASE_URL: {DATABASE_URL}")

    # Synchronous engine for PostgreSQL
    engine = create_engine(DATABASE_URL.replace('postgres://', 'postgresql://'), echo=True)

    # Asynchronous engine for PostgreSQL
    async_engine = create_async_engine(DATABASE_URL.replace('postgres://', 'postgresql+asyncpg://'), echo=True)
