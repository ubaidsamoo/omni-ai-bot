"""
Chat Module - Conversational AI with Persistent Memory
=======================================================
Google Gemini 1.5 Flash use karke multi-turn conversation handle karta hai.
"""

import google.generativeai as genai
from typing import Dict, List


class ChatModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key
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
        
        # Step 1: Get available models from Google to see what this key can access
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name.replace('models/', ''))
        except Exception as e:
            return f"❌ API Key Error: Google se models ki list nahi mil saki. [Error: {str(e)[:100]}]\nKey Hint: {key_hint}"

        if not available_models:
            return f"❌ No Models Found: Is API key par koi bhi Gemini model enabled nahi hai.\nKey Hint: {key_hint}"

        # Step 2: Try preferred models first, then fallback to ANY available model
        preferred = [self.model_name, "gemini-2.0-flash", "gemini-2.0-pro", "gemini-2.0-flash-lite"]
        
        # Merge lists (preferred first, then others)
        to_try = []
        for p in preferred:
            if p in available_models: to_try.append(p)
        for a in available_models:
            if a not in to_try: to_try.append(a)

        last_error = ""
        for m_name in to_try:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=self.system_prompt
                )
                chat = model.start_chat(history=gemini_history)
                response = await chat.send_message_async(message)
                ai_response = response.text
                
                # Update history
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": ai_response})
                self.sessions[session_id] = history
                return ai_response
            except Exception as e:
                last_error = str(e)
                continue 

        return "🙏 Maaf kijiye, abhi AI service thori busy hai ya limit poori ho gayi hai. Kuch dair baad try karein ya nai API key laga kar check karein."

    def clear_history(self, session_id: str = "default"):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_history(self, session_id: str = "default") -> List:
        return self.sessions.get(session_id, [])

    def get_active_sessions(self) -> List[str]:
        return list(self.sessions.keys())
