import os
import requests
import json

GUP_API = os.getenv("GUPSHUP_API_BASE", "https://api.gupshup.io")
GUP_KEY = os.getenv("GUPSHUP_API_KEY")
GUP_SRC = os.getenv("GUPSHUP_SANDBOX_NUMBER")  # source/sandbox number or id

def send_whatsapp_text(phone: str, text: str):
    """
    Simple Gupshup HTTP example.
    Adjust request format to match the provider (sandbox vs production).
    """
    if not GUP_KEY or not GUP_SRC:
        print("Gupshup keys missing. Would send:", phone, text)
        return

    url = f"{GUP_API}/v1/message"  # adjust to the provider docs if different
    payload = {
        "channel": "whatsapp",
        "source": GUP_SRC,
        "destination": phone,
        "message": {"type": "text", "text": text}
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": GUP_KEY
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print("Gupshup send status", resp.status_code, resp.text[:1000])
        return resp.json() if resp.ok else None
    except Exception as e:
        print("Gupshup send error", e)
        return None
