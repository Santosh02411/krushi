"""
chat_service.py
------------------
A real chatbot backed by the Anthropic API — not a scripted/fake response
generator. Requires ANTHROPIC_API_KEY in .env (get one at
https://console.anthropic.com). If no key is configured, the endpoint says
so plainly instead of returning a canned response pretending to be an LLM.

The system prompt gives the model real context this app already has
(recognized crops, disease-reference coverage, etc.) so answers are
grounded in what the rest of Krushi actually knows, rather than the model
inventing app-specific claims.
"""

import os

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"

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
                "error": "Chatbot isn't configured — add ANTHROPIC_API_KEY to .env (get a free key "
                         "at https://console.anthropic.com) to enable it.",
            }

        messages = []
        for turn in (history or [])[-10:]:  # keep recent context bounded
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn.get("content", "")})
        messages.append({"role": "user", "content": message})

        try:
            resp = requests.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model, "max_tokens": 600,
                    "system": SYSTEM_PROMPT, "messages": messages,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
            return {"success": True, "reply": text.strip() or "(empty response)"}
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except Exception:
                pass
            return {"success": False, "error": f"Chatbot API error: {detail or str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Chatbot request failed: {e}"}
