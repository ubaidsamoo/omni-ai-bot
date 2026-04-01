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

        # Build Gemini-format history (user/model roles)
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        # Debug: Show partial key to verify it's updated
        key_hint = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 5 else "Invalid Key"
        
        # Try Model 1, Fallback to Model 2
        models_to_try = [self.model_name, "gemini-1.5-flash", "gemini-1.5-pro"]
        last_error = ""

        for m_name in models_to_try:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=self.system_prompt
                )
                chat = model.start_chat(history=gemini_history)
                response = await chat.send_message_async(message)
                ai_response = f"{response.text}\n\n---\n*Verified with Key: {key_hint} | Model: {m_name}*"
                
                # Update history
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": ai_response})
                self.sessions[session_id] = history
                return ai_response
            except Exception as e:
                last_error = str(e)
                continue # Try next model
        
        # If all fail
        return f"❌ All models failed. Last Error: {last_error[:200]}\nKey Hint: {key_hint}"

    def clear_history(self, session_id: str = "default"):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_history(self, session_id: str = "default") -> List:
        return self.sessions.get(session_id, [])

    def get_active_sessions(self) -> List[str]:
        return list(self.sessions.keys())
