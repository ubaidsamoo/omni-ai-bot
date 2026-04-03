import google.generativeai as genai
import PyPDF2
import io
import time
import json

class DocumentModule:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.cache = {}
        
        self.error_messages = {
            "no_pdf": "⚠️ Pehle PDF upload karo!",
            "empty_pdf": "⚠️ PDF mein koi text nahi mila. Scanned image PDF ho sakta hai.",
            "no_question": "⚠️ Koi sawaal poochho!",
            "quota_error": "⚠️ API quota limit. 1-2 minute baad dobara try karo.",
            "off_topic": "❌ Ye sawaal PDF ke topic se bilkul alag hai."
        }

    def _extract_text(self, pdf_bytes: bytes) -> str:
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"❌ PDF parse nahi ho saki: {e}")

    def _safe_gemini_response(self, response) -> str:
        try:
            if hasattr(response, 'text') and response.text:
                return response.text
        except Exception:
            pass
        try:
            if response.candidates:
                parts = response.candidates[0].content.parts
                return " ".join(p.text for p in parts if hasattr(p, 'text'))
        except Exception:
            pass
        return ""

    def _call_gemini(self, prompt: str, system_prompt: str = None) -> str:
        fallback_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.0-pro"]
        models_to_try = [self.model_name] + [m for m in fallback_models if m != self.model_name]

        last_error = ""
        for m_name in models_to_try:
            try:
                if system_prompt:
                    model = genai.GenerativeModel(model_name=m_name, system_instruction=system_prompt)
                else:
                    model = genai.GenerativeModel(model_name=m_name)
                    
                time.sleep(1)
                response = model.generate_content(prompt)
                text = self._safe_gemini_response(response)
                if text:
                    return text
            except Exception as e:
                err_msg = str(e).lower()
                last_error = str(e)
                if any(x in err_msg for x in ("429", "quota", "exhausted")):
                    time.sleep(3)
                    continue
                if any(x in err_msg for x in ("404", "not found", "is not found", "not supported", "v1beta")):
                    continue
                return f"⚠️ API Error: {str(e)[:150]}"

        return self.error_messages["quota_error"]

    def _get_topic(self, text: str) -> str:
        prompt = f"Read this PDF content and reply with ONLY the main topic in 3-5 words. Nothing else.\n\nPDF Content: {text[:15000]}"
        topic = self._call_gemini(prompt)
        return topic.replace("\n", "").strip()

    def process_pdf(self, pdf_bytes: bytes, file_id: str) -> dict:
        if file_id in self.cache:
            return self.cache[file_id]

        text = self._extract_text(pdf_bytes)
        if not text or len(text) < 10:
            return {"error": self.error_messages["empty_pdf"]}

        # Limit to 50000 chars roughly to avoid massive token limits
        text = text[:50000]
        topic = self._get_topic(text)
        
        result = {"text": text, "topic": topic}
        self.cache[file_id] = result
        return result

    def get_summary(self, pdf_bytes: bytes, file_id: str) -> dict:
        base = self.process_pdf(pdf_bytes, file_id)
        if "error" in base:
            return base

        summary_cache_key = f"summary_{file_id}"
        if summary_cache_key in self.cache:
            return self.cache[summary_cache_key]

        prompt = f"""PDF Content:
{base['text']}

---

Provide a complete analysis in this EXACT format:

## 📄 PDF Summary (English)
[3-5 paragraph detailed summary]

---

## 📄 خلاصہ (Roman Urdu)
[Same summary in Roman Urdu]

---

## 🎯 Key Points
1. **[Point]** — Explanation
2. **[Point]** — Explanation
(5-8 points total)

---

## ❓ Suggested Questions
- [Question 1 from PDF content]
- [Question 2 from PDF content]
- [Question 3 — topic-related general question]
- [Question 4]
- [Question 5]"""

        analysis = self._call_gemini(prompt)
        res = {"topic": base["topic"], "analysis": analysis}
        self.cache[summary_cache_key] = res
        return res

    def get_answer(self, pdf_bytes: bytes, file_id: str, question: str) -> dict:
        base = self.process_pdf(pdf_bytes, file_id)
        if "error" in base:
            return base

        system_prompt = """You are an expert PDF Analyst Chatbot called 'Omni AI'. You have TWO modes:

**MODE 1 — PDF Mode:** If the question can be answered from the PDF content, answer from it.
**MODE 2 — General Mode:** If the question is related to the PDF's topic but not directly in the PDF, answer from your own knowledge — but clearly mention it.

Rules:
1. First check if answer is in PDF
2. If yes → answer from PDF and mention '📄 PDF se'
3. If not in PDF but topic-related → answer from knowledge and mention '🧠 General Knowledge se'
4. If completely unrelated to PDF topic → politely refuse (use ❌)
5. Always answer BILINGUAL — English + Roman Urdu
6. Never make up PDF content"""

        prompt = f"""PDF Topic: {base['topic']}
PDF Content:
{base['text']}

---

User Question: {question}

First decide which mode to use:
- If answer is IN the PDF → use PDF Mode
- If answer is topic-related but NOT in PDF → use General Mode  
- If completely off-topic → refuse politely

Answer in this EXACT format:

## 💬 Answer (English)
[Your answer]

---

## 💬 جواب (Roman Urdu)
[Same answer in Roman Urdu — natural chatting style]

---

## 📍 Source
**📄 PDF se** — [page/section] 
OR
**🧠 General Knowledge** — [brief reason why not in PDF]"""

        analysis = self._call_gemini(prompt, system_prompt=system_prompt)
        return {"topic": base["topic"], "analysis": analysis, "question": question}
