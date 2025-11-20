from fastapi import FastAPI, Request
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "running"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(req: Request):
    body = await req.json()
    # placeholder: we will replace this with actual handling later
    print("Inbound webhook:", body)
    return {"ok": True}
