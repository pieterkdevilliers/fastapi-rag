from sqlalchemy import create_engine
from sqlmodel import Session
from db import engine


def get_session():
    """
    Get Session
    """
    with Session(engine) as session:
        yield session