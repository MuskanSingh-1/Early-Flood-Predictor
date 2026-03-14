import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google import genai

router = APIRouter()

_CHAT_SYSTEM = """
You are SACHETNA's AI Disaster Assistant — a professional expert in flood safety in India.

Rules:
- Provide clear flood safety advice.
- Keep answers short (3–6 sentences).
- Use <br> for line breaks.
- Mention emergency numbers when useful:
  Police 100, Ambulance 108, NDRF 011-24363260.
- Only answer flood/disaster related questions.
- If unrelated say:
  "I'm here to help with flood and disaster safety."
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
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY missing")

    try:

        client = genai.Client(api_key=api_key)

        prompt = _CHAT_SYSTEM + "\n\nUser: " + req.message

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        reply = response.text.strip()

        return {"reply": reply}

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API error: {str(e)}"
        )
