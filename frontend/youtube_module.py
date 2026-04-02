import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import re
import requests
import time


class YouTubeModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.cache = {}

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _extract_video_id(self, url: str) -> str:
        patterns = [r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"❌ Invalid YouTube URL: {url}")

    def _fetch_transcript(self, video_id: str) -> str:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=['en', 'en-US', 'en-GB', 'hi', 'ur']
            )
            return " ".join(entry['text'] for entry in transcript_list)
        except (NoTranscriptFound, TranscriptsDisabled):
            pass

        try:
            transcripts_obj = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                t = transcripts_obj.find_manually_created_transcript(['en', 'hi', 'ur'])
            except Exception:
                try:
                    t = transcripts_obj.find_generated_transcript(['en', 'hi', 'ur'])
                except Exception:
                    t = list(transcripts_obj)[0]
            fetched = t.fetch()
            return " ".join(entry['text'] for entry in fetched)
        except (TranscriptsDisabled, NoTranscriptFound):
            return "TRANSCRIPT_ERROR: YouTube transcripts disabled or blocked."
        except Exception as e:
            return f"TRANSCRIPT_ERROR: {str(e)}"

    def _fetch_metadata(self, video_id: str) -> dict:
        metadata = {"title": f"Video {video_id}", "description": "", "thumbnail": ""}

        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        try:
            resp = requests.get(oembed_url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
                metadata["description"] = data.get("author_name", "")
                metadata["thumbnail"] = data.get("thumbnail_url", "")
        except Exception:
            pass

        if metadata["title"] == f"Video {video_id}":
            try:
                noembed_url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}"
                resp = requests.get(noembed_url, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    metadata["title"] = data.get("title", metadata["title"])
                    metadata["thumbnail"] = data.get("thumbnail_url", metadata["thumbnail"])
            except Exception:
                pass

        return metadata

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
        return "⚠️ Response generate nahi ho saka. Dobara koshish karein."

    def _call_gemini(self, prompt: str) -> str:
        """Central Gemini caller with retry logic."""
        model = genai.GenerativeModel(self.model_name)
        time.sleep(2)
        for attempt in range(3):
            try:
                response = model.generate_content(prompt)
                text = self._safe_gemini_response(response)
                if text and "⚠️ Response" not in text:
                    return text
            except Exception as e:
                err_msg = str(e).lower()
                if ("429" in err_msg or "exhausted" in err_msg or "quota" in err_msg) and attempt < 2:
                    time.sleep(15 + attempt * 10)
                    continue
                elif "429" in err_msg or "quota" in err_msg:
                    return "🙏 Quota limit aa gayi (429). Please 1-2 minute baad dobara koshish karein."
                else:
                    return f"⚠️ API Error: {str(e)[:120]}"
        return "⚠️ Response generate nahi ho saka. Dobara koshish karein."

    def _get_base_data(self, url: str, manual_content: str = "") -> dict:
        """
        Transcript + metadata ek baar fetch karo — sab tabs share karte hain.
        Cache mein save hota hai taake baar baar request na jaye.
        """
        video_id = self._extract_video_id(url)
        cache_key = f"raw_{video_id}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        metadata = self._fetch_metadata(video_id)

        if manual_content:
            transcript = manual_content
            transcript_note = f"📜 Manual Mode — {len(manual_content)} chars."
        else:
            transcript = self._fetch_transcript(video_id)
            if "TRANSCRIPT_ERROR" in transcript:
                transcript = f"VIDEO TITLE: {metadata['title']}\nCHANNEL: {metadata['description']}"
                transcript_note = "⚠️ Transcript nahi mila. Metadata se analyze kar raha hoon."
            else:
                transcript_note = f"✅ Transcript mila — {len(transcript)} characters"
                transcript = transcript[:7000]

        result = {
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "metadata": metadata,
            "transcript": transcript,
            "transcript_note": transcript_note,
        }
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # TAB 1 — SUMMARY
    # ─────────────────────────────────────────────

    def get_summary(self, url: str, manual_content: str = "") -> dict:
        base = self._get_base_data(url, manual_content)
        cache_key = f"summary_{base['video_id']}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Write a BILINGUAL summary of this video.

Video Title: {base['metadata']['title']}
Channel: {base['metadata']['description']}
Transcript: {base['transcript']}

Format your response EXACTLY like this:

## 📝 Summary (English)
Write a detailed 3-5 paragraph summary. Cover the main topic, key discussions, and overall message clearly.

---

## 📝 خلاصہ (Roman Urdu)
Wahi summary Roman Urdu mein likho. Natural chatting style — jaise kisi dost ko bata rahe ho. Mushkil alfaaz avoid karo.

---

## 🎬 Video Info
- **Title:** {base['metadata']['title']}
- **Channel:** {base['metadata']['description']}
"""
        analysis = self._call_gemini(prompt)
        result = {**base, "analysis": analysis, "tab": "summary"}
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # TAB 2 — KEY POINTS
    # ─────────────────────────────────────────────

    def get_keypoints(self, url: str, manual_content: str = "") -> dict:
        base = self._get_base_data(url, manual_content)
        cache_key = f"keypoints_{base['video_id']}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Extract the most important KEY POINTS from this video.

Video Title: {base['metadata']['title']}
Transcript: {base['transcript']}

Format EXACTLY like this:

## 🎯 Key Points (English)
Extract 5-8 key points. Be specific and informative.

1. **[Short Title]** — 1-2 sentence explanation of this point.
2. **[Short Title]** — Explanation...
(and so on)

---

## 🎯 اہم نکات (Roman Urdu)
Same points Roman Urdu mein — simple aur clear.

1. **[Short Title]** — Roman Urdu explanation.
2. **[Short Title]** — Explanation...
(and so on)

---

## ⭐ Sabse Zaroori Baat (One-liner)
Is poore video ka ek sabse important takeaway kya hai? Sirf ek line mein likho.
"""
        analysis = self._call_gemini(prompt)
        result = {**base, "analysis": analysis, "tab": "keypoints"}
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # TAB 3 — Q&A
    # ─────────────────────────────────────────────

    def get_answer(self, url: str, question: str, manual_content: str = "") -> dict:
        """
        Q&A tab — user koi bhi sawaal pooch sakta hai.
        Multi-turn: chat_history list pass karo conversation yaad rakhne ke liye.
        """
        base = self._get_base_data(url, manual_content)

        prompt = f"""You are a helpful YouTube Analyst Chatbot. Answer the user's question based on the video.

Video Title: {base['metadata']['title']}
Transcript: {base['transcript']}

User's Question: {question}

Format EXACTLY like this:

## 💬 Answer (English)
Give a thorough, accurate answer based only on the transcript. If the answer isn't in the video, say so honestly — don't make things up.

---

## 💬 جواب (Roman Urdu)
Wahi jawab Roman Urdu mein — jaise ek dost explain kar raha ho. Natural aur friendly tone.

---

## 📍 Context
Briefly mention which part of the video covers this topic (if identifiable).
"""
        analysis = self._call_gemini(prompt)
        return {**base, "analysis": analysis, "question": question, "tab": "qa"}

    # ─────────────────────────────────────────────
    # TAB 4 — RELATED TOPICS
    # ─────────────────────────────────────────────

    def get_related_topics(self, url: str, manual_content: str = "") -> dict:
        base = self._get_base_data(url, manual_content)
        cache_key = f"related_{base['video_id']}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Based on this video, suggest related topics and a learning path.

Video Title: {base['metadata']['title']}
Transcript: {base['transcript']}

Format EXACTLY like this:

## 🔗 Related Topics (English)
List 5-6 topics closely related to this video's content.

1. **[Topic Name]** — Why it's related and what you'd learn.
2. **[Topic Name]** — Explanation...
(and so on)

---

## 🔗 متعلقہ موضوعات (Roman Urdu)
Same topics Roman Urdu mein explain karo.

1. **[Topic Name]** — Roman Urdu explanation.
2. **[Topic Name]** — Explanation...
(and so on)

---

## 📚 Learning Path (Agle Qadam)
Is video ke baad kya sikhna chahiye? Beginner se advanced tak 4-5 steps batao — English mein.

---

## 🔍 Search Karne ke liye Keywords
Agar user is topic par aur padhna chahta hai toh kya Google/YouTube pe search kare? 6-8 keywords.
"""
        analysis = self._call_gemini(prompt)
        result = {**base, "analysis": analysis, "tab": "related"}
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # BACKWARD COMPATIBILITY
    # ─────────────────────────────────────────────

    def analyze(self, url: str, task: str = "summarize", question: str = "", manual_content: str = "") -> dict:
        """Old interface — routes to new tab methods. Purana code bhi kaam karta rahega."""
        if task == "qa" and question:
            return self.get_answer(url, question, manual_content)
        elif task == "keypoints":
            return self.get_keypoints(url, manual_content)
        elif task == "related":
            return self.get_related_topics(url, manual_content)
        else:
            return self.get_summary(url, manual_content)

    def get_transcript_only(self, url: str) -> str:
        video_id = self._extract_video_id(url)
        return self._fetch_transcript(video_id)