import json
from pathlib import Path
from typing import List, Dict
from openai_client import get_embedding
import math

def load_kb(folder: Path):
    kb = {"rooms": [], "faqs": [], "upsells": []}
    if not folder.exists():
        return kb
    for p in folder.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            # merge known keys
            if data.get("type") == "room" or ("rooms" in p.name):
                kb["rooms"].append(data)
            elif data.get("type") == "faq" or ("faq" in p.name):
                kb["faqs"].append(data)
            elif data.get("type") == "upsell" or ("upsell" in p.name):
                kb["upsells"].append(data)
            else:
                # infer structure
                if "rooms" in data:
                    kb["rooms"].extend(data.get("rooms", []))
                if "faqs" in data:
                    kb["faqs"].extend(data.get("faqs", []))
                if "upsells" in data:
                    kb["upsells"].extend(data.get("upsells", []))
        except Exception as e:
            print("kb load error", p, e)
    return kb

def _cosine(a: List[float], b: List[float]):
    if not a or not b:
        return 0.0
    dot = sum(x*y for x,y in zip(a,b))
    norma = math.sqrt(sum(x*x for x in a))
    normb = math.sqrt(sum(x*x for x in b))
    if norma == 0 or normb == 0:
        return 0.0
    return dot / (norma * normb)

def retrieve_context(kb: Dict, query: str, top_k: int = 3):
    # Very small lightweight retrieval:
    # Match keywords against titles and faq content
    query_l = query.lower()
    matches = []
    for f in kb.get("faqs", []):
        score = 0
        title = f.get("q","") + " " + f.get("a","")
        if query_l in title.lower():
            score += 2
        # word overlap
        for w in query_l.split():
            if w in title.lower():
                score += 0.5
        if score > 0:
            matches.append((score, f.get("a","")))
    # also include room descriptions if relevant
    for r in kb.get("rooms", []):
        txt = (r.get("name","") + " " + r.get("description","")).lower()
        score = 0
        if any(w in txt for w in query_l.split()):
            score += 1
        if score > 0:
            matches.append((score, r.get("description","")))
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:top_k]]
