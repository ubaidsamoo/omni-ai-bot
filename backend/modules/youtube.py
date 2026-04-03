import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import re
import requests
import time

# ─────────────────────────────────────────────────────────────────────────────
# VERIFIED WORKING MODELS — April 2026
# gemini-1.5-*  → DEAD (404)
# gemini-2.0-*  → Still alive but retiring June 2026
# gemini-2.5-flash      → STABLE, FREE, BEST CHOICE
# gemini-2.5-flash-lite → STABLE, FREE, MAX QUOTA
# gemini-2.5-pro        → STABLE, FREE (5 RPM only)
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_MODELS = [
    "gemini-2.0-flash",       # Standard choice for April 2026
    "gemini-2.0-flash-lite",  # Fast, free, high quota
    "gemini-2.0-pro",         # Fallback for complex reasoning
]


class YouTubeModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash-lite"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.cache = {}

    # ─────────────────────────────────────────────
    # VIDEO ID EXTRACT
    # ─────────────────────────────────────────────

    def _extract_video_id(self, url: str) -> str:
        patterns = [r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"❌ Invalid YouTube URL: {url}")

    # ─────────────────────────────────────────────
    # TRANSCRIPT: 3-layer fallback
    # ─────────────────────────────────────────────

    def _fetch_via_tactiq(self, video_id: str) -> str:
        """Tactiq proxy — works on cloud IPs, no API key needed."""
        try:
            resp = requests.post(
                "https://tactiq-apps-prod.tactiq.io/transcript",
                json={"videoUrl": f"https://www.youtube.com/watch?v={video_id}", "langCode": "en"},
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                captions = data.get("captions", [])
                if captions:
                    text = " ".join(c.get("text", "") for c in captions)
                    if len(text) > 100:
                        return text
        except Exception:
            pass
        return ""

    def _fetch_via_kome(self, video_id: str) -> str:
        """Kome.ai proxy — free, no key, cloud-friendly."""
        try:
            resp = requests.post(
                "https://kome.ai/api/tools/youtube-transcript",
                json={"video_id": video_id},
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("transcript", "") or data.get("text", "")
                if text and len(str(text)) > 100:
                    return str(text)
        except Exception:
            pass
        return ""

    def _fetch_via_library(self, video_id: str) -> str:
        """Direct youtube-transcript-api — best on local, sometimes works on HF too."""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=['en', 'en-US', 'en-GB', 'hi', 'ur']
            )
            return " ".join(entry['text'] for entry in transcript_list)
        except (NoTranscriptFound, TranscriptsDisabled):
            pass
        except Exception:
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
        except Exception:
            pass
        return ""

    def _fetch_transcript(self, video_id: str) -> str:
        """Try all 3 methods in order. Return TRANSCRIPT_ERROR only if ALL fail."""

        # Layer 1: Tactiq (most reliable on cloud)
        result = self._fetch_via_tactiq(video_id)
        if result:
            return result

        # Layer 2: Kome.ai
        result = self._fetch_via_kome(video_id)
        if result:
            return result

        # Layer 3: Direct library
        result = self._fetch_via_library(video_id)
        if result:
            return result

        return "TRANSCRIPT_ERROR"

    # ─────────────────────────────────────────────
    # METADATA
    # ─────────────────────────────────────────────

    def _fetch_metadata(self, video_id: str) -> dict:
        metadata = {"title": f"Video {video_id}", "description": "", "thumbnail": ""}
        try:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
                metadata["description"] = data.get("author_name", "")
                metadata["thumbnail"] = data.get("thumbnail_url", "")
                return metadata
        except Exception:
            pass
        try:
            url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
                metadata["thumbnail"] = data.get("thumbnail_url", metadata["thumbnail"])
        except Exception:
            pass
        return metadata

    # ─────────────────────────────────────────────
    # GEMINI CALLER — model fallback chain
    # ─────────────────────────────────────────────

    def _safe_response_text(self, response) -> str:
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

    def _call_gemini(self, prompt: str) -> str:
        """
        Try FALLBACK_MODELS in order.
        On 429 → wait briefly and try next model.
        On other errors → return error message immediately.
        """
        # Try self.model_name first, then fallbacks
        to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        
        for i, model_name in enumerate(to_try):
            try:
                model = genai.GenerativeModel(model_name)
                time.sleep(1)
                response = model.generate_content(prompt)
                text = self._safe_response_text(response)
                if text:
                    return text
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "quota" in err or "exhausted" in err:
                    # Rate limited — try next model after short wait
                    if i < len(FALLBACK_MODELS) - 1:
                        time.sleep(5)
                        continue
                    else:
                        return (
                            "⚠️ **Quota khatam ho gayi** — teeno Gemini models temporarily limited hain.\n\n"
                            "**Kya karein:** 2-3 minute wait karke dobara try karo. "
                            "Free tier ki daily limit midnight Pacific Time pe reset hoti hai."
                        )
                elif any(x in err for x in ("404", "not found", "is not found", "not supported", "v1beta")):
                    # Model deprecated — try next immediately
                    continue
                else:
                    return f"⚠️ API Error: {str(e)[:150]}"

        return "⚠️ Koi bhi model kaam nahi kar raha. Dobara koshish karein."

    # ─────────────────────────────────────────────
    # BASE DATA (shared by all tabs — cached)
    # ─────────────────────────────────────────────

    def _get_base_data(self, url: str, manual_content: str = "") -> dict:
        video_id = self._extract_video_id(url)
        cache_key = f"raw_{video_id}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        metadata = self._fetch_metadata(video_id)

        if manual_content:
            transcript = manual_content
            transcript_note = f"📜 Manual Mode — {len(manual_content):,} characters"
        else:
            raw = self._fetch_transcript(video_id)
            if raw == "TRANSCRIPT_ERROR":
                transcript = (
                    f"VIDEO TITLE: {metadata['title']}\n"
                    f"CHANNEL: {metadata['description']}\n"
                    "NOTE: Full transcript unavailable. Analyze based on title and channel only."
                )
                transcript_note = (
                    "⚠️ Auto-transcript nahi mila.\n"
                    "💡 **Tip:** Video ki description ya captions copy karke "
                    "**Manual Mode** mein paste karo — behtar analysis milegi!"
                )
            else:
                char_count = len(raw)
                transcript = raw[:8000]
                transcript_note = f"✅ Transcript mila — {char_count:,} characters"

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
        cache_key = f"summary_{base['video_id']}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Write a BILINGUAL summary of this video.

Video Title: {base['metadata']['title']}
Channel: {base['metadata']['description']}
Content: {base['transcript']}

Format EXACTLY like this:

## 📝 Summary (English)
Write a detailed 3-5 paragraph summary. Cover the main topic, key discussions, and overall message.

---

## 📝 خلاصہ (Roman Urdu)
Wahi summary Roman Urdu mein — natural chatting style, jaise dost ko bata rahe ho.

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
        cache_key = f"keypoints_{base['video_id']}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Extract KEY POINTS from this video.

Video Title: {base['metadata']['title']}
Content: {base['transcript']}

Format EXACTLY like this:

## 🎯 Key Points (English)
Extract 5-8 key points. Be specific and informative.

1. **[Short Title]** — 1-2 sentence explanation.
2. **[Short Title]** — Explanation...

---

## 🎯 اہم نکات (Roman Urdu)
Same points Roman Urdu mein — simple aur clear.

1. **[Short Title]** — Roman Urdu explanation.
2. **[Short Title]** — Explanation...

---

## ⭐ Sabse Zaroori Baat
Is video ka ek sabse important takeaway — sirf ek line mein.
"""
        analysis = self._call_gemini(prompt)
        result = {**base, "analysis": analysis, "tab": "keypoints"}
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # TAB 3 — Q&A
    # ─────────────────────────────────────────────

    def get_answer(self, url: str, question: str, manual_content: str = "") -> dict:
        base = self._get_base_data(url, manual_content)

        prompt = f"""You are a helpful YouTube Analyst Chatbot.

Video Title: {base['metadata']['title']}
Content: {base['transcript']}

User's Question: {question}

Format EXACTLY like this:

## 💬 Answer (English)
Thorough, accurate answer based on the content. If not covered, say so honestly.

---

## 💬 جواب (Roman Urdu)
Same jawab Roman Urdu mein — friendly aur natural tone.

---

## 📍 Context
Which part of the video this comes from (if identifiable).
"""
        analysis = self._call_gemini(prompt)
        return {**base, "analysis": analysis, "question": question, "tab": "qa"}

    # ─────────────────────────────────────────────
    # TAB 4 — RELATED TOPICS
    # ─────────────────────────────────────────────

    def get_related_topics(self, url: str, manual_content: str = "") -> dict:
        base = self._get_base_data(url, manual_content)
        cache_key = f"related_{base['video_id']}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"""You are a YouTube Analyst. Suggest related topics and learning path.

Video Title: {base['metadata']['title']}
Content: {base['transcript']}

Format EXACTLY like this:

## 🔗 Related Topics (English)
5-6 closely related topics.

1. **[Topic]** — Why related and what you'd learn.
2. **[Topic]** — Explanation...

---

## 🔗 متعلقہ موضوعات (Roman Urdu)
Same topics Roman Urdu mein.

1. **[Topic]** — Explanation.

---

## 📚 Learning Path
Beginner se advanced tak 4-5 steps.

---

## 🔍 Search Keywords
6-8 keywords jo user Google/YouTube pe search kare.
"""
        analysis = self._call_gemini(prompt)
        result = {**base, "analysis": analysis, "tab": "related"}
        self.cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────
    # BACKWARD COMPATIBILITY
    # ─────────────────────────────────────────────

    def analyze(self, url: str, task: str = "summarize", question: str = "", manual_content: str = "") -> dict:
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