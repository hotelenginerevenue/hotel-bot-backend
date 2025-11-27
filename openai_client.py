import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = (
    "You are a concise hotel booking assistant. Use only the provided hotel facts. "
    "Answer in the user's language. Keep replies short. If user asks to book, collect check-in, check-out, guests, and room type."
)

def ask_openai(user_text: str, context_texts: list):
    # build prompt with retrieved context
    context = "\n\n".join([f"- {c}" for c in (context_texts or [])])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context:\n{context}"},
        {"role": "user", "content": user_text}
    ]
    try:
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini") if os.getenv("OPENAI_MODEL") else "gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=200
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return text
    except Exception as e:
        print("OpenAI error:", e)
        # fallback simple reply
        return "Sorry, I cannot answer that right now. Please try again."

# Optional embedding function (not used directly, kept for later)
def get_embedding(text: str):
    try:
        r = openai.Embeddings.create(model="text-embedding-3-small", input=text)
        return r["data"][0]["embedding"]
    except Exception as e:
        print("Embedding error", e)
        return None
