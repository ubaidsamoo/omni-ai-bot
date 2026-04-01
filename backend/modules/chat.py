"""
Chat Module - Conversational AI with Persistent Memory
=======================================================
Google Gemini 1.5 Flash use karke multi-turn conversation handle karta hai.
"""

import google.generativeai as genai
from typing import Dict, List


class ChatModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.sessions: Dict[str, List] = {}
        self.system_prompt = (
            "You are Omni AI, an intelligent multimodal assistant. "
            "You are helpful, concise, and knowledgeable. Always be friendly and professional."
        )

    def _get_or_create_session(self, session_id: str) -> List:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]

    async def chat(self, message: str, session_id: str = "default") -> str:
        history = self._get_or_create_session(session_id)

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt
        )

        # Build Gemini-format history (user/model roles)
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=gemini_history)
        try:
            response = await chat.send_message_async(message)
            ai_response = response.text
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "exhausted" in err_msg or "quota" in err_msg:
                ai_response = f"🙏 Maaf kijiye limit exhaust wagera: [Detail: {str(e)[:150]}]"
            else:
                ai_response = f"⚠️ Oops! API error aagaya: {str(e)[:150]}..."

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": ai_response})
        self.sessions[session_id] = history

        return ai_response

    def clear_history(self, session_id: str = "default"):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_history(self, session_id: str = "default") -> List:
        return self.sessions.get(session_id, [])

    def get_active_sessions(self) -> List[str]:
        return list(self.sessions.keys())
