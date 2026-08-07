"""
chat_service.py
------------------
A real chatbot backed by the Google Gemini API — not a scripted/fake
response generator. Requires GEMINI_API_KEY in .env (get a free key at
https://aistudio.google.com/apikey — no credit card required to start).
Gemini's free tier has generous per-minute/per-day request limits, not a
literal unlimited quota — if you hit them, the API returns a 429 and the
chat page will say so honestly rather than hanging or faking a reply.

If no key is configured, the endpoint says so plainly instead of
returning a canned response pretending to be an LLM.

The system prompt gives the model real context this app already has
(recognized crops, disease-reference coverage, etc.) so answers are
grounded in what the rest of Krushi actually knows, rather than the model
inventing app-specific claims.
"""

import os

import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are the in-app farming assistant for Krushi, an Indian agriculture advisory \
tool. Answer farming questions (crop choice, fertilizer, pest/disease symptoms, irrigation, \
general agronomy) clearly and practically for a smallholder Indian farming context.

Krushi's own tools (mention them when relevant instead of duplicating their job):
- Crop recommendation: trained on N/P/K/pH/temperature/humidity/rainfall for 22 crops.
- Soil health tool: N/P/K/organic-carbon/pH scoring against Soil Health Card bands.
- Disease check: symptom-matching for rice, wheat, cotton, potato, maize (not image-based).
- Fertilizer plan, irrigation schedule, crop calendar, market prices (potato/tomato/wheat), \
yield prediction (11 crops) are also available as dedicated tools in the app.

If a question is about a specific numeric diagnosis (e.g. "what's my soil score"), point the \
farmer to the relevant tool instead of guessing a number. Keep answers concise and practical. \
You are not a substitute for a local agricultural extension officer for high-stakes decisions."""


class ChatService:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL

    def is_configured(self):
        return bool(self.api_key)

    def send_message(self, message, history=None):
        if not self.api_key:
            return {
                "success": False,
                "error": "Chatbot isn't configured — add GEMINI_API_KEY to .env (get a free key at "
                         "https://aistudio.google.com/apikey) to enable it.",
            }

        contents = []
        for turn in (history or [])[-10:]:  # keep recent context bounded
            role = "user" if turn.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        try:
            resp = requests.post(
                GEMINI_API_URL.format(model=self.model),
                params={"key": self.api_key},
                headers={"content-type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 600},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                block_reason = data.get("promptFeedback", {}).get("blockReason")
                if block_reason:
                    return {"success": False, "error": f"Gemini declined to answer ({block_reason})."}
                return {"success": False, "error": "Gemini returned no response."}
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            return {"success": True, "reply": text.strip() or "(empty response)"}
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except Exception:
                pass
            if resp.status_code == 429:
                return {"success": False, "error": "Gemini rate limit hit — wait a moment and try again."}
            return {"success": False, "error": f"Chatbot API error: {detail or str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Chatbot request failed: {e}"}
