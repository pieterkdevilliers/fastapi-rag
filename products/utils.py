from secrets import token_hex
from sqlmodel import Session
from sqlmodel.sql.expression import select
from products.models import UserProduct


def create_new_user_product_in_db(account_unique_id: str, payload, session: Session):
    """
    Save New UserProduct to DB
    """
    user_product = UserProduct(
        account_unique_id=account_unique_id,
        product_title=payload.product_title,
        product_description=payload.product_description,
        product_sale_url=payload.product_sale_url,
        who_is_this_for=payload.who_is_this_for,
        is_active=payload.is_active,
        )
    session.add(user_product)
    session.commit()
    session.refresh(user_product)
    
    return user_product


def get_user_product_by_product_title(account_unique_id: str, product_title: str, session: Session):
    """
    Retrieves the UserProduct object based on product_title
    """
    statement = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id, UserProduct.product_title == product_title)
    result = session.exec(statement)
    user_product = result.first()

    return user_product


def get_user_products_for_account(account_unique_id: str, session: Session):
    """
    Retrieves the UserProduct objects based on account_unique_id
    """
    statement = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id)
    result = session.exec(statement)
    user_products = result.all()

    return user_products


def get_active_user_products_for_account(account_unique_id: str, session: Session):
    """
    Retrieves the active UserProduct objects based on account_unique_id
    """
    statement = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id, UserProduct.is_active == True)
    result = session.exec(statement)
    active_user_products = result.all()

    return active_user_products


def get_user_product_by_id(account_unique_id: str, product_id: int, session: Session):
    """
    Retrieves the UserProduct object based on id
    """
    statement = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id, UserProduct.id == product_id)
    result = session.exec(statement)
    user_product = result.first()

    return user_product


def update_user_product(account_unique_id: str, product_id: int, payload, session: Session):
    """
    Update UserProduct
    """
    user_product = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id, UserProduct.id == product_id)
    
    if not user_product:
        return {"error": "UserProduct not found"}
    
    user_product.product_title = payload.product_title
    user_product.product_description = payload.product_description
    user_product.product_sale_url = payload.product_sale_url
    user_product.who_is_this_for = payload.who_is_this_for
    user_product.is_active = payload.is_active
        
    session.add(user_product)
    session.commit()
    session.refresh(user_product)
    
    return user_product


def delete_user_product_from_db(account_unique_id: str, product_id: int,  session: Session):
    """
    Delete UserProduct from DB
    """
    statement = select(UserProduct).filter(UserProduct.account_unique_id == account_unique_id, UserProduct.id == product_id)
    result = session.exec(statement)
    user_product = result.first()
    
    if not user_product:
        return {"error": "UserProduct not found"}
    
    session.delete(user_product)
    session.commit()
    
    return {"response": "success"}


def format_user_products_for_prompt(user_products: list) -> str:
    """
    Convert UserProduct model objects into a clean, LLM-friendly text format.
    """
    lines = ["Available Products:\n"]
    for i, product in enumerate(user_products, start=1):
        lines.append(f"{i}. {product.product_title}")
        lines.append(f"   - Description: {product.product_description}")
        lines.append(f"   - For: {product.who_is_this_for}")
        lines.append(f"   - URL: {product.product_sale_url}\n")
    return "\n".join(lines)

