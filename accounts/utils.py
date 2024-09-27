from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select
from accounts.models import Account


def save_new_account_to_db(account_organisation: str, session: Session):
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


def update_account_in_db(account_organisation: str, account_unique_id: int, session: Session):
    """
    Update Account in DB
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()
    
    if not account:
        return {"error": "Account not found"}
    
    account.account_organisation = account_organisation
    session.add(account)
    session.commit()
    session.refresh(account)
    
    return account