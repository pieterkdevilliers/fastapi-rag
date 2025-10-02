from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select
from accounts.models import Account, User, StripeSubscription, AccountPrompts, WidgetConfig, WidgetAPIKey
from core.models import PasswordResetToken
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


def get_account_by_account_unique_id(account_unique_id: str, session: Session):
    """
    Retrives the Account object based on account_unique_id
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()

    return account

def create_new_user_in_db(user_email: str, user_password: str, account_unique_id: str, session: Session, receive_notifications: bool = False, is_account_owner: bool = False):
    """
    Save New User to DB
    """
    user = User(user_email=user_email, user_password=user_password, account_unique_id=account_unique_id, receive_notifications=receive_notifications, is_account_owner=is_account_owner)
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
    statement = select(User).filter(User.account_unique_id == account_unique_id)
    result = session.exec(statement)
    users = result.all()
    print('Notification Users Found: ', users)
    
    if not users:
        return {"error": "No users found"}
    
    return [user.model_dump() for user in users]


def get_users_for_account(account_unique_id: str, session: Session):
    """
    Retrieves all the users for an account
    """
    statement = select(User).filter(User.account_unique_id == account_unique_id)
    result = session.exec(statement)
    users = result.all()

    return users


def get_user_by_email(email: str, session: Session):
    """
    Retrieve user object by email_address
    """
    statement = select(User).filter(User.user_email == email)
    result = session.exec(statement)
    user = result.first()

    return user


def create_password_reset_token(user_id: int, token: str, expires_at: str, session: Session):
    """
    Create new User Token in DB
    """
    password_reset_token = PasswordResetToken(user_id=user_id, token=token, expires_at=expires_at)
    session.add(password_reset_token)
    session.commit()
    session.refresh(password_reset_token)

    return password_reset_token


def get_reset_token(token: str, session: Session):
    """
    Retrieve user object by email_address
    """
    token_record = select(PasswordResetToken).filter(PasswordResetToken.token == token)
    result = session.exec(token_record)
    token_record = result.first()

    return token_record


def update_user_password(user_id: int, password: str, session: Session):
    """
    Update user password in password reset process
    """
    user = session.get(User, user_id)
    
    if not user:
        return {"error": "User not found"}
    
    user.user_password = get_password_hash(password)
        
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


def delete_reset_token(token_record: PasswordResetToken,  session: Session):
    """
    Delete Account from DB
    """
    statement = select(PasswordResetToken).filter(PasswordResetToken.token == token_record.token)
    result = session.exec(statement)
    token_record = result.first()
    
    if not token_record:
        return {"error": "Token already expired"}
    
    session.delete(token_record)
    session.commit()
    
    return {"response": "success"}


def check_active_subscription_status(account_unique_id: str, session: Session):
    """
    Check an account for an active subscription
    """
    statement = select(StripeSubscription).filter(StripeSubscription.account_unique_id == account_unique_id, StripeSubscription.status == 'active')
    result = session.exec(statement)
    active_sub = result.first()

    if not active_sub:
        return False
    
    return True


def get_account_webhook_url(account_unique_id: str, session: Session):
    """
    Get the account's webhook_url
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    webhook_url = result.first().webhook_url

    return webhook_url


def get_opt_in_webhook_url(account_unique_id: str, session: Session):
    """
    Get the account's webhook_url
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    webhook_url = result.first().opt_in_webhook_url

    return webhook_url


def create_account_prompt(account_unique_id: str, prompt_key: str, prompt_text: str, session: Session):
    """
    Save New Account Prompt to DB
    """
    prompt = AccountPrompts(account_unique_id=account_unique_id,
                            prompt_key=prompt_key,
                            prompt_text=prompt_text)
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt


def get_account_prompts(account_unique_id: str, session: Session):
    """
    Retrieve all prompts for an account
    """
    statement = select(AccountPrompts).filter(AccountPrompts.account_unique_id == account_unique_id)
    result = session.exec(statement)
    prompts = result.all()

    return prompts


def get_most_recent_prompt(account_unique_id: str, session: Session):
    """
    Fetch the most recently created prompt for a given account.
    Returns None if no prompts exist for the account.
    """
    statement = (
        select(AccountPrompts)
        .where(AccountPrompts.account_unique_id == account_unique_id)
        .order_by(AccountPrompts.__table__.c.created_at.desc())  # Use the actual SQLAlchemy column
    )
    result = session.exec(statement).first()
    return result


def get_account_prompt_by_id(account_unique_id: str, id, session: Session):
    """
    Retrieve a specific prompt for an account by its key
    """
    statement = select(AccountPrompts).filter(AccountPrompts.account_unique_id == account_unique_id, AccountPrompts.id == id)
    result = session.exec(statement)
    prompt = result.first()

    return prompt


def delete_prompt_from_db(id, session: Session):
    """
    Delete Account Prompt from DB
    """
    statement = select(AccountPrompts).filter(AccountPrompts.id == id)
    result = session.exec(statement)
    prompt = result.first()
    
    if not prompt:
        return {"error": "Prompt not found",
                "prompt": id}
    
    session.delete(prompt)
    session.commit()
    
    return {"response": "success",
            "prompt": id}


def get_account_temperature(account_unique_id: str, session: Session):
    """
    Retrieve the temperature setting for an account
    """
    statement = select(Account).filter(Account.account_unique_id == account_unique_id)
    result = session.exec(statement)
    account = result.first()

    return account.temperature if account and account.temperature is not None else 0.2


def get_widget_configs_for_account(account_unique_id: str, session: Session):
    """
    Retrieve all the widget_config objects for an account
    """
    statement = select (WidgetConfig).filter(WidgetConfig.account_unique_id == account_unique_id)
    result = session.exec(statement)
    widget_configs = result.all()

    return widget_configs


def delete_widget_config_from_db(id, session: Session):
    """
    Delete WidgetConfig from DB
    """
    statement = select(WidgetConfig).filter(WidgetConfig.widget_id == id)
    result = session.exec(statement)
    widget_config = result.first()
    
    if not widget_config:
        return {"error": "WidgetConfig not found"}
    
    session.delete(widget_config)
    session.commit()
    
    return {"response": "success",
            "widget_config deleted": id}


def get_widget_api_keys_for_account(account_unique_id: str, session: Session):
    """
    Retrieve all the widget_api_key objects for an account
    """
    statement = select (WidgetAPIKey).filter(WidgetAPIKey.account_unique_id == account_unique_id)
    result = session.exec(statement)
    widget_api_keys = result.all()

    return widget_api_keys


def delete_widget_api_key_from_db(id, session: Session):
    """
    Delete WidgetAPIKey from DB
    """
    statement = select(WidgetAPIKey).filter(WidgetAPIKey.id == id)
    result = session.exec(statement)
    widget_api_key = result.first()
    
    if not widget_api_key:
        return {"error": "WidgetAPIKey not found"}
    
    session.delete(widget_api_key)
    session.commit()
    
    return {"response": "success",
            "widget_api_key deleted": id}
