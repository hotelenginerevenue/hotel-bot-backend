import os
import stripe
import json

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_stripe_checkout_session(reservation: dict):
    """
    Create a Stripe Checkout Session and return session object.
    """
    line_items = [
        {
            "price_data": {
                "currency": "eur",
                "product_data": {"name": f"{reservation['room_type']} stay"},
                "unit_amount": reservation["price_cents"]
            },
            "quantity": 1
        }
    ]
    # add upsells if any
    for u in reservation.get("upsells", []):
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": u.get("id")},
                "unit_amount": u.get("price_cents")
            },
            "quantity": 1
        })
    try:
        sess = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=os.getenv("SUCCESS_URL", "https://example.com/success") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.getenv("CANCEL_URL", "https://example.com/cancel"),
            metadata={"reservation_id": reservation["id"]}
        )
        return {"id": sess.id, "url": sess.url}
    except Exception as e:
        print("Stripe create error", e)
        raise

def handle_stripe_event(payload: bytes, signature: str):
    """
    Verify webhook. Returns (event, reservation_id)
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise Exception("Missing STRIPE_WEBHOOK_SECRET")
    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=webhook_secret)
    except Exception as e:
        print("Stripe webhook verify failed", e)
        raise
    res_id = None
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        res_id = session.get("metadata", {}).get("reservation_id")
    return event, res_id
