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


def update_file_in_db(file_id: int, updated_file: SourceFile, session: Session):
    """
    Update Source File in DB
    """
    file = session.get(SourceFile, file_id)
    
    if not file:
        return {"error": "File not found"}
    
    updated_file_dict = updated_file.model_dump(exclude_unset=True)
    print('updated_file_dict:', updated_file_dict)
    for key, value in updated_file_dict.items():
        setattr(file, key, value)
    session.add(file)
    session.commit()
    session.refresh(file)
    
    return file
