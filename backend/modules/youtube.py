import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import re
import requests
import time


# ─────────────────────────────────────────────────────────────────────────────
# FREE TIER QUOTA GUIDE (gemini models — least to most expensive):
#   gemini-1.5-flash-8b  → 1500 RPD, 4M TPM  ← sabse safe, use as primary
#   gemini-1.5-flash     → 1500 RPD, 1M TPM  ← fallback #1
#   gemini-2.0-flash     → 1500 RPD, 1M TPM  ← fallback #2
# Strategy: primary model try karo, 429 aane pe next model pe jump karo.
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",   # Primary — fastest + most quota on free tier
    "gemini-2.0-flash",        # Fallback 1
    "gemini-1.5-flash",        # Fallback 2
]


class YouTubeModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-lite"):
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

    # ── TRANSCRIPT: 3-layer fallback ─────────────

    def _fetch_via_supadata(self, video_id: str) -> str:
        """
        Supadata API — working endpoint, no API key needed for basic use.
        Returns plain text transcript.
        """
        try:
            url = f"https://supadata.ai/api/youtube/transcript?videoId={video_id}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                # Try multiple response formats
                content = data.get("transcript") or data.get("content") or data.get("text") or ""
                if isinstance(content, list):
                    content = " ".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    )
                if content and len(str(content)) > 100:
                    return str(content)
        except Exception:
            pass
        return ""

    def _fetch_via_ytt_proxy(self, video_id: str) -> str:
        """
        Kiri API — free, no key, works on cloud servers.
        """
        try:
            url = f"https://yt-transcript-api.vercel.app/api?videoId={video_id}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return " ".join(item.get("text", "") for item in data)
                elif isinstance(data, dict):
                    content = data.get("transcript") or data.get("text") or ""
                    if content:
                        return content
        except Exception:
            pass

        # Second proxy attempt
        try:
            url = f"https://transcripts.youtubeapi.com/{video_id}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return " ".join(item.get("text", "") for item in data)
        except Exception:
            pass

        return ""

    def _fetch_via_library(self, video_id: str) -> str:
        """
        youtube-transcript-api direct library call.
        Local pe kaam karta hai, HF pe aksar block hoti hai — isliye 3rd try.
        """
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=['en', 'en-US', 'en-GB', 'hi', 'ur']
            )
            return " ".join(entry['text'] for entry in transcript_list)
        except (NoTranscriptFound, TranscriptsDisabled):
            pass
        except Exception:
            pass

        # Koi bhi available transcript lo
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
        """
        3-layer transcript fetching:
        1. Supadata API      (HF-friendly, free, no key)
        2. Multiple proxies  (HF-friendly, free, no key)
        3. Direct library    (local pe best, HF pe last resort)
        """
        # Layer 1: Supadata
        result = self._fetch_via_supadata(video_id)
        if result:
            return result

        # Layer 2: ytt proxy
        result = self._fetch_via_ytt_proxy(video_id)
        if result:
            return result

        # Layer 3: Direct library
        result = self._fetch_via_library(video_id)
        if result:
            return result

        return "TRANSCRIPT_ERROR: Kisi bhi method se transcript nahi mila."

    # ── METADATA ─────────────────────────────────

    def _fetch_metadata(self, video_id: str) -> dict:
        metadata = {"title": f"Video {video_id}", "description": "", "thumbnail": ""}

        # oEmbed — sabse reliable
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = requests.get(oembed_url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
                metadata["description"] = data.get("author_name", "")
                metadata["thumbnail"] = data.get("thumbnail_url", "")
                return metadata  # oEmbed kaam kar gaya, aur kuch zaroorat nahi
        except Exception:
            pass

        # noembed fallback
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

    # ── GEMINI: model fallback chain ─────────────

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

    def _call_gemini(self, prompt: str) -> str:
        """
        Smart Gemini caller:
        - Primary: gemini-1.5-flash-8b (max free quota)
        - 429 aane pe: next model pe jump karo
        - Sab models fail karein to user-friendly message
        """
        # Try to discover available models that support generateContent
        available_models = []
        try:
            for m in genai.list_models():
                try:
                    if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                        available_models.append(m.name.replace('models/', ''))
                except Exception:
                    # tolerate malformed model entries
                    continue
        except Exception:
            # If listing fails, we'll fall back to the static list below
            available_models = []

        # Build ordered list to try: user-specified, discovered, then static fallbacks
        models_to_try = []
        if self.model_name:
            models_to_try.append(self.model_name)
        for m in available_models:
            if m not in models_to_try:
                models_to_try.append(m)
        for m in FALLBACK_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = ""

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                time.sleep(1)
                response = model.generate_content(prompt)
                text = self._safe_gemini_response(response)
                if text:
                    return text
            except Exception as e:
                err_msg = str(e).lower()
                last_error = str(e)

                # If it's a quota/429 issue, try next model after a short wait
                if any(x in err_msg for x in ("429", "quota", "exhausted")):
                    time.sleep(3)
                    continue

                # If model not found / 404 for this model name, try next discovered model
                if any(x in err_msg for x in ("404", "not found", "is not found", "not supported")):
                    continue

                # For other errors, return a concise message so caller can show it
                return f"⚠️ API Error: {str(e)[:150]}"

        # If we reach here, all models failed (likely quota or unavailable models)
        return (
            "⚠️ Abhi sabhi Gemini models ki free quota use ho chuki hai ya models available nahi hain.\n\n"
            "**Kya karein:**\n"
            "- 1-2 minute wait karke dobara try karein\n"
            "- Ya naya API key use karke retry karein\n"
            "- Ya Manual Mode mein transcript paste karein\n\n"
            f"_(Last error: {last_error[:120]})_"
        )

    # ─────────────────────────────────────────────
    # BASE DATA (shared by all tabs)
    # ─────────────────────────────────────────────

    def _get_base_data(self, url: str, manual_content: str = "") -> dict:
        video_id = self._extract_video_id(url)
        cache_key = f"raw_{video_id}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        metadata = self._fetch_metadata(video_id)

        if manual_content:
            transcript = manual_content
            transcript_note = f"📜 Manual Mode — {len(manual_content)} chars"
        else:
            transcript = self._fetch_transcript(video_id)

            if "TRANSCRIPT_ERROR" in transcript:
                # Sirf metadata hai — iske saath bhi analysis ho sakti hai
                transcript = (
                    f"VIDEO TITLE: {metadata['title']}\n"
                    f"CHANNEL: {metadata['description']}\n"
                    f"NOTE: Full transcript unavailable. Analyze based on title and channel context."
                )
                transcript_note = (
                    "⚠️ Transcript fetch nahi ho saka (YouTube ne block kiya).\n"
                    "Tip: Video description copy karke Manual Mode mein paste karo — "
                    "behtar analysis milegi!"
                )
            else:
                char_count = len(transcript)
                transcript = transcript[:8000]
                transcript_note = f"✅ Transcript mila — {char_count:,} characters fetched"

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
Transcript/Content: {base['transcript']}

Format EXACTLY like this:

## 📝 Summary (English)
Write a detailed 3-5 paragraph summary. Cover the main topic, key discussions, and overall message.

---

## 📝 خلاصہ (Roman Urdu)
Wahi summary Roman Urdu mein — natural chatting style, jaise dost ko bata rahe ho. Mushkil alfaaz mat use karo.

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

        prompt = f"""You are a YouTube Analyst. Extract KEY POINTS from this video.

Video Title: {base['metadata']['title']}
Transcript/Content: {base['transcript']}

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
Transcript/Content: {base['transcript']}

User's Question: {question}

Format EXACTLY like this:

## 💬 Answer (English)
Thorough, accurate answer based on the transcript. If not in video, say so honestly.

---

## 💬 جواب (Roman Urdu)
Wahi jawab Roman Urdu mein — friendly aur natural tone.

---

## 📍 Context
Which part of the video covers this (if identifiable).
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

        prompt = f"""You are a YouTube Analyst. Suggest related topics and learning path.

Video Title: {base['metadata']['title']}
Transcript/Content: {base['transcript']}

Format EXACTLY like this:

## 🔗 Related Topics (English)
5-6 closely related topics.

1. **[Topic]** — Why related and what you'd learn.
2. **[Topic]** — Explanation...

---

## 🔗 متعلقہ موضوعات (Roman Urdu)
Same topics Roman Urdu mein.

1. **[Topic]** — Explanation.
2. **[Topic]** — Explanation...

---

## 📚 Learning Path
Beginner se advanced tak 4-5 steps — English mein.

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