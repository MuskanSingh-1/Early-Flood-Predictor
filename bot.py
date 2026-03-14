import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google import genai

router = APIRouter()

_CHAT_SYSTEM = """
You are SACHETNA's AI Assistant inside the SACHETNA flood awareness app.

Your main purpose is to help users with:
- flood safety
- disaster preparedness
- emergency response
- monsoon safety
- evacuation guidance

However, you can also answer general questions helpfully when users ask them.

Guidelines:
- Prefer safety-focused responses when relevant.
- If a user asks about hospitals, emergency numbers, weather, travel safety, etc., answer helpfully.
- If the question is unrelated to disasters (general knowledge, directions, etc.), still provide a useful answer.
- Keep responses concise (3–6 sentences).
- Use simple HTML formatting when helpful (<br>, <strong>).

Emergency numbers in India:
Police: 100
Ambulance: 108
NDRF: 011-24363260

Always stay calm, helpful, and informative.
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
