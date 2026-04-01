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
            raise ValueError("❌ Transcripts are disabled for this video.")

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
        except Exception as e:
            return f"TRANSCRIPT_ERROR: {str(e)}"

    def _fetch_metadata(self, video_id: str) -> dict:
        """Fetch Title/Description from YouTube HTML as a fallback"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}, timeout=10)
            soup = BeautifulSoup(r.text, 'lxml')
            title = soup.find("title").text.replace(" - YouTube", "") if soup.find("title") else f"Video {video_id}"
            description = ""
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag:
                description = desc_tag.get("content", "")
            return {"title": title, "description": description}
        except Exception as e:
            return {"title": f"Video {video_id}", "description": f"Metadata fetch failed: {str(e)}"}

    async def get_transcript_only(self, url: str) -> str:
        video_id = self._extract_video_id(url)
        return await asyncio.to_thread(self._fetch_transcript, video_id)

    async def analyze(self, url: str, task: str = "summarize", question: str = "") -> dict:
        video_id = self._extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        transcript = await self.get_transcript_only(url)
        
        is_fallback = False
        if "TRANSCRIPT_ERROR" in transcript:
            is_fallback = True
            metadata = await asyncio.to_thread(self._fetch_metadata, video_id)
            source_content = f"VIDEO TITLE: {metadata['title']}\nVIDEO DESCRIPTION: {metadata['description']}"
            transcript_preview = f"⚠️ Note: Transcripts were blocked/disabled. Analyzing based on Metadata.\n\nDescription: {metadata['description'][:500]}"
            transcript_len = 0
            prompt = f"The transcript for this video is unavailable. Analyze this video based on its title and description.\n\n{source_content}\n\nTask: {task}. {question}"
        else:
            is_fallback = False
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
                analysis_text = "🙏 Maaf kijiye, abhi AI service thori busy hai ya limit poori ho gayi hai. Kuch dair baad try karein ya nai API key laga kar check karein."
            else:
                analysis_text = f"⚠️ Oops! API error aagaya: {str(e)[:50]}..."

        return {
            "video_id": video_id,
            "video_url": video_url,
            "task": task,
            "transcript_length": transcript_len,
            "transcript_preview": transcript_preview,
            "analysis": analysis_text,
            "question": question if task == "qa" else None
        }

    def _build_prompt(self, task: str, transcript: str, question: str = "") -> str:
        base = f"You are analyzing a YouTube video transcript.\n\n---TRANSCRIPT---\n{transcript}\n---END---\n\n"

        prompts = {
            "summarize": base + """Provide a comprehensive summary:

## 📋 Video Summary
### Overview
### Main Topics Covered
### Detailed Summary
### Key Takeaways (5-7 points)
### Who Should Watch This?""",

            "qa": base + f"""Answer this question based on the video:

**Question**: {question}

Be specific, reference transcript parts when helpful.""",

            "key_points": base + """Extract key points:

## 🎯 Key Points
### Critical Insights (3-5)
### Supporting Points (5-10)
### Practical Applications
### Notable Quotes
### One-Sentence Summary""",

            "sentiment": base + """Analyze sentiment:

## 😊 Sentiment Analysis
### Overall Tone
### Emotional Journey
### Speaker's Attitude
### Positive vs Negative Balance
### Final Verdict""",

            "chapters": base + """Break into chapters:

## 📑 Video Chapters
For each chapter: **Title**, **Summary** (2-3 sentences), **Key Points** (2-3 bullets)
End with **Complete Overview**."""
        }

        return prompts.get(task, prompts["summarize"])
