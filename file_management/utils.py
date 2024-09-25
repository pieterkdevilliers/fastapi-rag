from sqlmodel import Session
from fastapi import Depends
from file_management.source_db import SourceFileModel, engine



        

def save_file_to_db(filename: str, file_path: str, session: Session):
    """
    Save Source File to DB
    """
    db_file = SourceFileModel(file_name=filename, file_path=file_path)
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    
    return db_file
