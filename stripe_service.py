import os
import json
import stripe
from fastapi import FastAPI, responses, Request, HTTPException
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")



@app.get("/api/v1/checkout/")
async def create_checkout_session(price: int = 10):
    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "FastAPI Stripe Checkout",
                    },
                    "unit_amount": price * 100,
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_id": 3,
            "email": "abc@gmail.com",
            "request_id": 1234567890
        },
        mode="payment",
        success_url=os.getenv("BASE_URL") + "/success/",
        cancel_url=os.getenv("BASE_URL") + "/cancel/",
        customer_email="ping@fastapitutorial.com",
    )
    return responses.RedirectResponse(checkout_session.url, status_code=303)


@app.post("/api/v1/webhook/")
async def stripe_webhook(request: Request):
    payload = await request.body()
    event = None

    try:
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    print("event received is", event)
    if event["type"] == "checkout.session.completed":
        payment = event["data"]["object"]
        amount = payment["amount_total"]
        currency = payment["currency"]
        user_id = payment["metadata"]["user_id"] # get custom user id from metadata
        user_email = payment["customer_details"]["email"]
        user_name = payment["customer_details"]["name"]
        order_id = payment["id"]
        # save to db
        # send email in background task
    return {}
