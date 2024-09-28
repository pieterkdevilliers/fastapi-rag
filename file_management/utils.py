from sqlmodel import Session
from file_management.models import SourceFile
        

def save_file_to_db(filename: str, file_path: str, file_account: str, session: Session):
    """
    Save Source File to DB
    """
    db_file = SourceFile(file_name=filename, file_path=file_path, account_unique_id=file_account)
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    
    return db_file
