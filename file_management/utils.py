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


def update_file_in_db(file_id: int, file_account: str, included_in_source_data: bool, session: Session):
    """
    Update Source File in DB
    """
    print(included_in_source_data)
    db_file = session.get(SourceFile, file_id)
    db_file.account_unique_id = file_account
    db_file.included_in_source_data = included_in_source_data
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    
    return db_file
