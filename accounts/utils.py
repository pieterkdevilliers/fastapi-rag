from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select
from accounts.models import Account, User, StripeSubscription
from authentication import get_password_hash


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
    account = session.exec(select(Account).where(Account.account_unique_id == account_unique_id)).first()
    
    if not account:
        return {"error": "Account not found"}
    
    updated_account_dict = updated_account.model_dump(exclude_unset=True, exclude={"id"})
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


def create_new_user_in_db(user_email: str, user_password: str, account_unique_id: str, session: Session, receive_notifications: bool = False):
    """
    Save New User to DB
    """
    user = User(user_email=user_email, user_password=user_password, account_unique_id=account_unique_id, receive_notifications=receive_notifications)
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
        if key == "user_password":
            hashed_password = get_password_hash(value)
            value = hashed_password
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


def get_notification_users(account_unique_id: str, session: Session):
    """
    Get Users who should receive notifications
    """
    statement = select(User).filter(User.account_unique_id == account_unique_id, User.receive_notifications == True)
    result = session.exec(statement)
    users = result.all()
    
    if not users:
        return {"error": "No users found"}
    
    return [user.model_dump() for user in users]


def create_stripe_subscription_in_db(account_unique_id: str, subscription_data: dict, session: Session):
    """
    Create a new subscription for an account
    """
    
    statement = StripeSubscription(account_unique_id=account_unique_id, **subscription_data)
    session.add(statement   )
    session.commit()
    session.refresh(statement)

    return statement


def update_stripe_subscription_in_db(account_unique_id: str, subscription_id: str, updated_data: dict, session: Session):
    """
    Update an existing subscription for an account
    """
    
    statement = session.exec(select(StripeSubscription).where(
        StripeSubscription.account_unique_id == account_unique_id,
        StripeSubscription.subscription_id == subscription_id
    )).first()
    
    if not statement:
        return {"error": "Subscription not found"}
    
    updated_data_dict = {k: v for k, v in updated_data.items() if v is not None}
    for key, value in updated_data_dict.items():
        setattr(statement, key, value)
        
    session.add(statement)
    session.commit()
    session.refresh(statement)
    
    return statement