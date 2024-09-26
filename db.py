from sqlmodel import create_engine

DB_FILE = "source_db.db"
engine = create_engine(f'sqlite:///{DB_FILE}', echo=True)