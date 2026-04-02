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

    def _extract_video_id(self, url: str) -> str:
        patterns = [r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"❌ Invalid YouTube URL: {url}")

    def _fetch_transcript(self, video_id: str) -> str:
        """Sync transcript fetch - no asyncio needed."""
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
        """Fetch Title using oEmbed (most reliable on cloud servers)."""
        metadata = {"title": f"Video {video_id}", "description": ""}

        # oEmbed: Most reliable, works even on HuggingFace cloud IPs
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        try:
            resp = requests.get(oembed_url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
                metadata["description"] = data.get("author_name", "")
        except Exception:
            pass

        # Fallback: noembed (alternative oembed provider)
        if metadata["title"] == f"Video {video_id}":
            try:
                noembed_url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}"
                resp = requests.get(noembed_url, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    metadata["title"] = data.get("title", metadata["title"])
            except Exception:
                pass

        return metadata

    def _safe_gemini_response(self, response) -> str:
        """Safely extract text from Gemini response - prevents blank output."""
        try:
            # Method 1: Direct .text
            if hasattr(response, 'text') and response.text:
                return response.text
        except Exception:
            pass

        try:
            # Method 2: candidates -> parts
            if response.candidates:
                parts = response.candidates[0].content.parts
                return " ".join(p.text for p in parts if hasattr(p, 'text'))
        except Exception:
            pass

        return "⚠️ Response generate nahi ho saka. Dobara koshish karein."

    def analyze(self, url: str, task: str = "summarize", question: str = "", manual_content: str = "") -> dict:
        """
        SYNC version - Streamlit ke saath perfectly kaam karta hai.
        asyncio.to_thread ya await bilkul use nahi kiya.
        """
        video_id = self._extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Cache check
        cache_key = f"{video_id}_{task}_{question}_{len(manual_content)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        transcript_len = 0
        transcript_preview = ""

        # Manual mode
        if manual_content:
            transcript = manual_content
            transcript_len = len(transcript)
            transcript_preview = f"📜 Manual Mode. Content Length: {transcript_len} chars."
        else:
            # Auto mode - sync call
            transcript = self._fetch_transcript(video_id)

            if "TRANSCRIPT_ERROR" in transcript:
                metadata = self._fetch_metadata(video_id)
                transcript = f"VIDEO TITLE: {metadata['title']}\nCHANNEL: {metadata['description']}"
                transcript_preview = f"⚠️ Transcript nahi mila. Metadata se analyze kar raha hoon.\n\nTitle: {metadata['title']}"
                transcript_len = 0
            else:
                transcript_len = len(transcript)
                transcript_preview = transcript[:500] + "..." if len(transcript) > 500 else transcript
                transcript = transcript[:7000]  # ~2k tokens, safe for free tier

        # Small delay for quota safety
        time.sleep(2)

        model = genai.GenerativeModel(self.model_name)
        prompt = self._build_prompt(task, transcript, question)

        # Retry loop
        analysis_text = ""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)  # SYNC - no await
                analysis_text = self._safe_gemini_response(response)
                if analysis_text and "⚠️ Response" not in analysis_text:
                    break
            except Exception as e:
                err_msg = str(e).lower()
                if ("429" in err_msg or "exhausted" in err_msg or "quota" in err_msg) and attempt < max_retries - 1:
                    wait_time = 15 + (attempt * 10)
                    time.sleep(wait_time)
                    continue
                elif "429" in err_msg or "quota" in err_msg:
                    analysis_text = "🙏 Quota limit aa gayi (429). Please 1-2 minute baad dobara koshish karein ya Manual Mode use karein."
                else:
                    analysis_text = f"⚠️ API Error: {str(e)[:100]}"
                break

        result = {
            "video_id": video_id,
            "video_url": video_url,
            "task": task,
            "transcript_length": transcript_len,
            "transcript_preview": transcript_preview,
            "analysis": analysis_text,
            "question": question if task == "qa" else None
        }

        if "Quota" not in analysis_text and "⚠️" not in analysis_text:
            self.cache[cache_key] = result

        return result

    def get_transcript_only(self, url: str) -> str:
        """Sync version - Streamlit ke liye."""
        video_id = self._extract_video_id(url)
        return self._fetch_transcript(video_id)

    def _build_prompt(self, task: str, transcript: str, question: str = "") -> str:
        base = (
            "You are a YouTube Analyst (NoteGPT Style). "
            "Analyze the transcript and provide a HIGH-QUALITY BILINGUAL DEEP DIVE (English & Roman Urdu).\n\n"
            f"Transcript: {transcript[:25000]}\n\n"
        )

        if task == "qa":
            return base + f"Answer this question in English and Roman Urdu: {question}"

        return base + """Provide a deep dive in exactly this format:

## 📊 1. COMPREHENSIVE REPORT
[English: Write a high-quality summary explaining the video content in detail.]
---
[Roman Urdu: Write the same summary in natural, fluid Roman Urdu. 'Is video mein hamen...']

## 🎯 2. KEY TAKEAWAYS
* [English: Core point 1]
* [Roman Urdu: Point 1 ka Roman Urdu tarjuma]
* [English: Core point 2]
* [Roman Urdu: Point 2 ka Roman Urdu tarjuma]

---
💡 Ensure the Roman Urdu is readable and natural. Don't use difficult Urdu words, use the language as people chat (Roman Urdu style)."""
