import os
import google.generativeai as genai

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# System prompt for Gemini
_CHAT_SYSTEM = """
You are SACHETNA's AI Disaster Assistant — a professional, empathetic expert
in flood safety, disaster preparedness, and emergency response for India.

Guidelines:
- Give clear, actionable, step-by-step advice on flood and disaster safety.
- Keep responses concise: 3–6 sentences or a short numbered list. Use <br> for line breaks.
- Prioritize life-safety above all else.
- Reference Indian emergency numbers when relevant:
  NDRF 011-24363260, Police 100, Ambulance 108.
- Be calm, reassuring, and professional.
- ONLY answer questions related to flood safety, disaster preparedness,
  emergency response, monsoon safety, evacuation, and disaster first aid.
- If asked unrelated questions say:
  "I'm here to help with flood and disaster safety."
- Respond in the same language as the user (Hindi or English).
- Use simple HTML formatting (<strong>, <br>) only.
"""

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("/chat")
def chat(req: ChatRequest):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY not configured on server."
        )

    try:
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash",
            system_instruction=_CHAT_SYSTEM
        )

        history = []

        for m in req.history[-10:]:
            if m.role in ("user", "assistant") and m.content.strip():
                history.append({
                    "role": "user" if m.role == "user" else "model",
                    "parts": [m.content]
                })

        chat_session = model.start_chat(history=history)

        response = chat_session.send_message(req.message)

        reply = response.text.strip()

        return {"reply": reply}

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API error: {str(e)}"
        )
