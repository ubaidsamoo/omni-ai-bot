"""
YouTube Module - Deep Dive Video Analysis
==========================================
YouTube transcript extract karke Google Gemini se analyze karta hai.
"""

import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import asyncio
import re


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
            raise ValueError(f"❌ No transcript available.\nReason: {str(e)}")

    async def get_transcript_only(self, url: str) -> str:
        video_id = self._extract_video_id(url)
        return await asyncio.to_thread(self._fetch_transcript, video_id)

    async def analyze(self, url: str, task: str = "summarize", question: str = "") -> dict:
        video_id = self._extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        transcript = await self.get_transcript_only(url)

        max_chars = 28000
        transcript_for_ai = transcript[:max_chars] + "\n\n[... truncated ...]" if len(transcript) > max_chars else transcript

        prompt = self._build_prompt(task, transcript_for_ai, question)

        model = genai.GenerativeModel(self.model_name)
        response = await model.generate_content_async(prompt)

        return {
            "video_id": video_id,
            "video_url": video_url,
            "task": task,
            "transcript_length": len(transcript),
            "transcript_preview": transcript[:500] + "..." if len(transcript) > 500 else transcript,
            "analysis": response.text,
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
