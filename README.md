# Hotel WhatsApp Bot - MVP

Minimal FastAPI backend for a WhatsApp-first booking assistant.

## What this includes
- WhatsApp webhook endpoint (Gupshup)
- Basic slot filling (check-in, check-out, guests, room type)
- JSON-based knowledge base (kb/)
- OpenAI integration for replies
- Stripe Checkout creation and webhook handling
- File-based reservation store (reservations.json)

## Run locally
1. Create virtual env and install


2. Set env vars (use `.env` file or export)
3. Start server



4. Use ngrok for external webhook testing:



## Deploy
- Deploy to Render or Replit.
- Add environment variables in the host UI.

## Notes
- Do not commit `.env` or secrets.
- This project uses simple JSON-based retrieval. For production use pgvector or Pinecone.
