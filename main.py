import os
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from kb import load_kb, retrieve_context
from storage import load_reservations, save_reservations
from gupshup import send_whatsapp_text
from stripe_integration import create_stripe_checkout_session, handle_stripe_event
from openai_client import ask_openai

# Config
RES_FILE = Path("reservations.json")
KB_FOLDER = Path("kb")

app = FastAPI(title="Hotel WhatsApp Bot - MVP")

# Load KB at startup
KB = load_kb(KB_FOLDER)

@app.get("/")
async def root():
    return {"status": "running", "time": datetime.utcnow().isoformat()}

# Simple health check for reservations file
@app.get("/admin/reservations")
async def admin_reservations():
    data = load_reservations(RES_FILE)
    return {"count": len(data), "reservations": data}

# Webhook entry for WhatsApp (Gupshup)
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(req: Request):
    payload = await req.json()
    # Gupshup payload structure may vary. We handle common shapes.
    # Log payload for debugging
    print("INBOUND WHATSAPP:", json.dumps(payload)[:2000])

    # Try multiple known fields
    phone = None
    text = None
    if "payload" in payload and isinstance(payload["payload"], dict):
        # Gupshup sample: payload -> message -> text -> ...
        msg = payload["payload"].get("message", {}) or {}
        phone = payload["payload"].get("sender", {}).get("phone")
        text = msg.get("text") or msg.get("payload") or payload["payload"].get("message", {}).get("data")
    # fallback
    phone = phone or payload.get("from") or payload.get("sender")
    text = text or payload.get("text") or payload.get("message")

    if not phone:
        return JSONResponse({"ok": False, "error": "no sender phone"}, status_code=400)

    phone = phone.strip()
    text = (text or "").strip()

    # Very small session-state: store draft reservation keyed by phone
    sessions = load_reservations(RES_FILE)
    session = sessions.get(phone, {"state": "collecting", "slots": {}, "created_at": datetime.utcnow().isoformat()})

    # Basic slot collection logic
    slots = session.get("slots", {})
    if not slots.get("check_in"):
        # look for a simple date pattern, else ask
        if text:
            slots["check_in"] = text  # simple UX: accept first message as check-in
            session["state"] = "collecting_checkout"
            session["slots"] = slots
            sessions[phone] = session
            save_reservations(sessions, RES_FILE)
            await send_whatsapp_text(phone, "Thanks. Now send check-out date (YYYY-MM-DD).")
            return {"ok": True}
        else:
            await send_whatsapp_text(phone, "Welcome. Send check-in date (YYYY-MM-DD).")
            return {"ok": True}

    if session["state"] == "collecting_checkout" and not slots.get("check_out"):
        slots["check_out"] = text or slots.get("check_out")
        session["state"] = "collecting_guests"
        session["slots"] = slots
        sessions[phone] = session
        save_reservations(sessions, RES_FILE)
        await send_whatsapp_text(phone, "How many guests?")
        return {"ok": True}

    if session["state"] == "collecting_guests" and not slots.get("guests"):
        # expect an integer
        try:
            guests = int(text.strip())
        except Exception:
            await send_whatsapp_text(phone, "Please send number of guests as a digit, e.g., 2")
            return {"ok": True}
        slots["guests"] = guests
        session["state"] = "asking_room_type"
        session["slots"] = slots
        sessions[phone] = session
        save_reservations(sessions, RES_FILE)

        # show available rooms from KB (simple)
        room_names = [r["name"] for r in KB.get("rooms", [])]
        msg = "Choose room type: " + ", ".join(room_names)
        await send_whatsapp_text(phone, msg)
        return {"ok": True}

    if session["state"] == "asking_room_type" and not slots.get("room_type"):
        # find matching room by name or id
        chosen = text.lower()
        match = None
        for r in KB.get("rooms", []):
            if chosen in r["id"].lower() or chosen in r["name"].lower():
                match = r
                break
        if not match:
            await send_whatsapp_text(phone, "Room type not found. Please send exact room name from the list.")
            return {"ok": True}
        slots["room_type"] = match["id"]
        session["slots"] = slots
        session["state"] = "quote_ready"
        sessions[phone] = session
        save_reservations(sessions, RES_FILE)

        # generate quote and offer checkout
        nights = 1
        try:
            # naive nights calc if iso dates
            check_in = datetime.fromisoformat(slots["check_in"])
            check_out = datetime.fromisoformat(slots["check_out"])
            nights = max(1, (check_out.date() - check_in.date()).days)
        except Exception:
            nights = 1
        # find price
        room = next((r for r in KB.get("rooms", []) if r["id"] == match["id"]), None)
        base_price = room.get("price", 0) if room else 0
        price_cents = int(base_price * 100 * nights)
        upsell = KB.get("upsells", [])[:1]  # suggest first upsell
        upsell_text = ""
        if upsell:
            upsell_text = f"Upsell suggestion: {upsell[0]['name']} €{upsell[0]['price']}"
        quote_msg = f"Quote: {room['name']} for {nights} night(s). Total €{price_cents/100:.2f}. {upsell_text}\nSend YES to get a payment link."
        await send_whatsapp_text(phone, quote_msg)
        return {"ok": True}

    # If user confirms payment
    if session["state"] == "quote_ready" and text.lower() in ("yes", "pay", "ok"):
        # Build reservation object
        rid = "res_" + uuid4().hex[:8]
        slots = session["slots"]
        room = next((r for r in KB.get("rooms", []) if r["id"] == slots["room_type"]), {})
        # recompute price
        nights = 1
        try:
            check_in = datetime.fromisoformat(slots["check_in"])
            check_out = datetime.fromisoformat(slots["check_out"])
            nights = max(1, (check_out.date() - check_in.date()).days)
        except Exception:
            nights = 1
        total_cents = int(room.get("price", 0) * 100 * nights)
        reservation = {
            "id": rid,
            "phone": phone,
            "name": session.get("name") or "",
            "room_type": slots["room_type"],
            "check_in": slots["check_in"],
            "check_out": slots["check_out"],
            "nights": nights,
            "price_cents": int(room.get("price", 0) * 100),
            "upsells": [],
            "total_cents": total_cents,
            "payment_status": "PENDING",
            "stripe_session_id": None,
            "created_at": datetime.utcnow().isoformat()
        }
        saved = load_reservations(RES_FILE)
        saved[rid] = reservation
        save_reservations(saved, RES_FILE)

        # Create Stripe Checkout
        checkout = create_stripe_checkout_session(reservation)
        # update reservation with session id
        saved = load_reservations(RES_FILE)
        saved[rid]["stripe_session_id"] = checkout.get("id")
        save_reservations(saved, RES_FILE)

        # Send checkout URL via WhatsApp
        await send_whatsapp_text(phone, f"Open this link to pay: {checkout.get('url')}")
        return {"ok": True}

    # Otherwise fallback to AI reply using KB retrieval
    context = retrieve_context(KB, text, top_k=3)
    ai_resp = ask_openai(text, context)
    await send_whatsapp_text(phone, ai_resp)
    return {"ok": True}

# Stripe webhook
@app.post("/webhook/stripe")
async def stripe_webhook(req: Request, stripe_signature: str = Header(None)):
    payload = await req.body()
    sig = stripe_signature or req.headers.get("stripe-signature")
    try:
        event, res_id = handle_stripe_event(payload, sig)
    except Exception as e:
        print("Stripe webhook error:", str(e))
        raise HTTPException(status_code=400, detail="invalid webhook")

    # On checkout.session.completed mark PAID
    if event and event["type"] == "checkout.session.completed" and res_id:
        data = load_reservations(RES_FILE)
        if res_id in data:
            data[res_id]["payment_status"] = "PAID"
            save_reservations(data, RES_FILE)
            # send confirmation
            await send_whatsapp_text(data[res_id]["phone"],
                                     f"Booking {res_id} confirmed for {data[res_id]['check_in']} to {data[res_id]['check_out']}. Total €{data[res_id]['total_cents']/100:.2f}")
            return JSONResponse({"ok": True})
    return JSONResponse({"ok": True})
