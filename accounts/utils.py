from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select
from accounts.models import Account, User


def create_new_account_in_db(account_organisation: str, session: Session):
    """
    Save New Account to DB
    """
    account_unique_id = token_hex(8)
    account = Account(account_organisation=account_organisation,
                      account_unique_id=account_unique_id)
    session.add(account)
    session.commit()
    session.refresh(account)
    
    return account


def update_account_in_db(account_unique_id: str, updated_account: Account, session: Session):
    """
    Update Account in DB
    """
    account = session.get(Account, account_unique_id == account_unique_id)
    
    if not account:
        return {"error": "Account not found"}
    
    updated_account_dict = updated_account.model_dump(exclude_unset=True)
    for key, value in updated_account_dict.items():
        setattr(account, key, value)
    session.add(account)
    session.commit()
    session.refresh(account)
    
    return account


def delete_account_from_db(account_unique_id: str, session: Session):
    """
    Delete Account from DB
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()
    
    if not account:
        return {"error": "Account not found"}
    
    session.delete(account)
    session.commit()
    
    return {"response": "success",
            "account_unique_id": account_unique_id}


def create_new_user_in_db(user_email: str, user_password: str, account_unique_id: str, session: Session):
    """
    Save New User to DB
    """
    user = User(user_email=user_email, user_password=user_password, account_unique_id=account_unique_id)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


def update_user_in_db(account_unique_id: str, user_id: int, updated_user: User, session: Session):
    """
    Update Account in DB
    """
    user = session.get(User, user_id)
    
    if not user:
        return {"error": "User not found"}
    
    updated_user_dict = updated_user.model_dump(exclude_unset=True)
    for key, value in updated_user_dict.items():
        setattr(user, key, value)
        
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


def delete_user_from_db(account_unique_id: str, user_id: int,  session: Session):
    """
    Delete Account from DB
    """
    statement = select(User).filter(User.account_unique_id == account_unique_id, User.id == user_id)
    result = session.exec(statement)
    user = result.first()
    
    if not user:
        return {"error": "User not found"}
    
    session.delete(user)
    session.commit()
    
    return {"response": "success",
            "user_id": user_id}
