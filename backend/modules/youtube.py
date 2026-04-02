"""
YouTube Module - Deep Dive Video Analysis
==========================================
YouTube transcript extract karke Google Gemini se analyze karta hai.

# ── YouTube ─────────────────────────────────────────────────────────────────
# youtube-transcript-api==0.6.3
# beautifulsoup4==4.12.3
# requests==2.32.3
# lxml==5.3.0
"""

import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import asyncio
import re
import requests
from bs4 import BeautifulSoup


class YouTubeModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.cache = {} # Simple URL-based cache to save Quota

    def _extract_video_id(self, url: str) -> str:
        patterns = [r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"❌ Invalid YouTube URL: {url}")

    def _fetch_transcript(self, video_id: str) -> str:
        """Sync transcript fetch - asyncio.to_thread mein run hoga"""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=['en', 'en-US', 'en-GB', 'hi', 'ur']
            )
            return " ".join(entry['text'] for entry in transcript_list)
        except NoTranscriptFound:
            pass
        except TranscriptsDisabled:
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
        """Fetch Title/Description using oEmbed (Reliable) and HTML Scraping (Fallback)"""
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        metadata = {"title": f"Video {video_id}", "description": ""}
        
        # 1. Try oEmbed for Title (Very reliable)
        try:
            resp = requests.get(oembed_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                metadata["title"] = data.get("title", metadata["title"])
        except Exception:
            pass

        # 2. Try Scrape for Description (Tricky, YouTube blocks simple requests)
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if "consent.youtube.com" in r.url:
                # Redirected to consent page, try again with a cookie or just skip
                pass
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Try meta description first
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag:
                desc = desc_tag.get("content", "")
                if "Enjoy the videos and music you love" not in desc:
                    metadata["description"] = desc

            # If description still generic, try scraping 'ytInitialData' JSON
            if not metadata["description"] or "Enjoy the videos" in metadata["description"]:
                match = re.search(r'shortDescription":"(.*?)"', r.text)
                if match:
                    metadata["description"] = match.group(1).encode().decode('unicode_escape')

            # Final Title Fallback
            if metadata["title"] == f"Video {video_id}":
                title_tag = soup.find("title")
                if title_tag:
                    metadata["title"] = title_tag.text.replace(" - YouTube", "")

        except Exception as e:
            metadata["description"] = f"Metadata fetch failed: {str(e)}"
            
        return metadata

    async def get_transcript_only(self, url: str) -> str:
        video_id = self._extract_video_id(url)
        return await asyncio.to_thread(self._fetch_transcript, video_id)

    async def analyze(self, url: str, task: str = "summarize", question: str = "") -> dict:
        video_id = self._extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 0. Quota Protection: Check Cache
        cache_key = f"{video_id}_{task}_{question}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        transcript = await self.get_transcript_only(url)
        
        if "TRANSCRIPT_ERROR" in transcript:
            metadata = await asyncio.to_thread(self._fetch_metadata, video_id)
            source_content = f"VIDEO TITLE: {metadata['title']}\nVIDEO DESCRIPTION: {metadata['description']}"
            transcript_preview = f"⚠️ Note: Transcripts were blocked/disabled. Analyzing based on Metadata.\n\nDescription: {metadata['description'][:500]}"
            transcript_len = 0
            
            # Stronger fallback prompt
            prompt = f"The transcript for this video is blocked or unavailable. I need you to perform a DEEP DIVE analysis based ONLY on the Title and Description below. Follow the NoteGPT format strictly.\n\n{source_content}\n\nTask: {task}. {question}"
        else:
            transcript_len = len(transcript)
            transcript_preview = transcript[:500] + "..." if len(transcript) > 500 else transcript
            max_chars = 28000
            transcript_for_ai = transcript[:max_chars]
            prompt = self._build_prompt(task, transcript_for_ai, question)

        model = genai.GenerativeModel(self.model_name)
        try:
            response = await model.generate_content_async(prompt)
            analysis_text = response.text
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "exhausted" in err_msg or "quota" in err_msg:
                analysis_text = "🙏 Maaf kijiye, abhi AI service thori busy hai ya limit poori ho gayi hai (429 Quota). Kuch dair baad try karein ya nai API key laga kar check karein."
            else:
                analysis_text = f"⚠️ Oops! API error aagaya: {str(e)[:50]}..."

        result = {
            "video_id": video_id,
            "video_url": video_url,
            "task": task,
            "transcript_length": transcript_len,
            "transcript_preview": transcript_preview,
            "analysis": analysis_text,
            "question": question if task == "qa" else None
        }
        
        # Save to cache if successful
        if "Maaf kijiye" not in analysis_text:
            self.cache[cache_key] = result
            
        return result

    def _build_prompt(self, task: str, transcript: str, question: str = "") -> str:
        base = f"You are a YouTube Analyst (NoteGPT Style). Analyze the transcript and provide a HIGH-QUALITY BILINGUAL DEEP DIVE (English & Roman Urdu).\n\nTranscript: {transcript[:25000]}\n\n"

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
