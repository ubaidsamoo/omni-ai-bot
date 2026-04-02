import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import re
import requests
import time


# ─────────────────────────────────────────────────────────────────────────────
# FREE TIER QUOTA (March 2026 — verified from Google docs):
#   gemini-2.5-flash-lite → 15 RPM, 1000 RPD  ← sabse zyada quota, PRIMARY
#   gemini-2.5-flash      → 10 RPM,  250 RPD  ← fallback #1
#   gemini-2.5-pro        →  5 RPM,  100 RPD  ← fallback #2 (last resort)
# NOTE: gemini-2.0-flash March 2026 mein retire ho gaya — use mat karo!
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_MODELS = [
    "gemini-2.5-flash-lite-preview-06-17",  # Primary — max free quota
    "gemini-2.5-flash",                      # Fallback 1
    "gemini-2.5-pro",                        # Fallback 2 (last resort)
]


class YouTubeModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash-lite-preview-06-17"):
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
        Supadata — reliable third-party transcript API, HF pe kaam karta hai.
        No API key needed for basic use.
        """
        try:
            # Format 1: REST endpoint
            url = f"https://api.supadata.ai/v1/youtube/transcript"
            params = {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "text"}
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content") or data.get("transcript") or data.get("text") or ""
                if isinstance(content, list):
                    content = " ".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in content
                    )
                if content and len(str(content)) > 100:
                    return str(content)
        except Exception:
            pass

        try:
            # Format 2: alternate endpoint
            url = f"https://api.supadata.ai/v1/youtube/transcript?videoId={video_id}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content") or data.get("transcript") or data.get("text") or ""
                if content and len(str(content)) > 100:
                    return str(content)
        except Exception:
            pass

        return ""

    def _fetch_via_ytt_proxy(self, video_id: str) -> str:
        """
        Multiple free proxy endpoints — HF cloud IPs pe kaam karte hain.
        """
        proxies = [
            # Proxy 1: tactiq
            {
                "url": f"https://tactiq-apps-prod.tactiq.io/transcript",
                "method": "POST",
                "json": {"videoUrl": f"https://www.youtube.com/watch?v={video_id}", "langCode": "en"},
                "parser": lambda d: " ".join(s.get("text", "") for s in d.get("captions", []))
            },
            # Proxy 2: kome
            {
                "url": f"https://kome.ai/api/tools/youtube-transcript",
                "method": "POST",
                "json": {"video_id": video_id},
                "parser": lambda d: d.get("transcript", "")
            },
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        for proxy in proxies:
            try:
                if proxy["method"] == "POST":
                    resp = requests.post(
                        proxy["url"],
                        json=proxy["json"],
                        headers=headers,
                        timeout=15
                    )
                else:
                    resp = requests.get(proxy["url"], headers=headers, timeout=15)

                if resp.status_code == 200:
                    data = resp.json()
                    result = proxy["parser"](data)
                    if result and len(str(result)) > 100:
                        return str(result)
            except Exception:
                continue

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
        models_to_try = FALLBACK_MODELS.copy()
        # Agar user ne custom model set kiya hai toh pehle woh try karo
        if self.model_name not in models_to_try:
            models_to_try.insert(0, self.model_name)

        last_error = ""

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                time.sleep(1)  # Minimal delay — zyada nahi
                response = model.generate_content(prompt)
                text = self._safe_gemini_response(response)
                if text:
                    return text
            except Exception as e:
                err_msg = str(e).lower()
                last_error = str(e)

                if "429" in err_msg or "quota" in err_msg or "exhausted" in err_msg:
                    # Is model ki quota khatam — next model try karo
                    time.sleep(3)
                    continue
                else:
                    # Quota nahi, koi aur error hai — same model retry mat karo
                    return f"⚠️ API Error: {str(e)[:150]}"

        # Sab models fail
        return (
            "⚠️ Abhi sabhi Gemini models ki free quota use ho chuki hai.\n\n"
            "**Kya karein:**\n"
            "- 1-2 minute wait karke dobara try karein\n"
            "- Ya kal aayein — daily limit reset ho jaati hai\n"
            "- Ya Manual Mode mein transcript paste karein\n\n"
            f"_(Last error: {last_error[:100]})_"
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