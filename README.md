---
title: Omni Ai Bot
emoji: 🤖
colorFrom: blue
colorTo: pink
sdk: docker
pinned: false
---

![Omni AI Dashboard](omni_ai.PNG)

# 🤖 Omni AI Bot - Multi-Functional Generative AI Workspace

Omni AI is a powerful, versatile, and high-performance AI assistant built to streamline your productivity using Google's state-of-the-art **Gemini API**. Whether you need a smart conversationalist, deep-dive analysis of your PDF documents, or sophisticated data insights, Omni AI has you covered.

---

## 🚀 Experience Omni AI
![Omni AI Features](omni_ai_3.PNG)

---

## ✨ Core Features

*   **💬 Pro-Grade AI Chat**: Minimalist, clean, and highly responsive chat interface powered by Gemini 2.0 Flash. Features conversational memory and intelligent formatting.
*   **📄 PDF Analyst**: Upload any PDF document to instantly extract summaries, key points, and interact with the content through a smart, bilingual Q&A chat (English & Roman Urdu). Includes a smart fallback to General Knowledge if the answer isn't in the PDF.
*   **📊 Data Analysis Engine**: Upload documents or datasets for instant AI-powered analysis and visualization.
*   **👁️ Vision Capabilities**: Process and understand visual information with multi-modal AI reasoning.
*   **🛠️ Robust Backend**: Powered by FastAPI with high-performance asynchronous request handling.

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Modern, minimalist UI)
- **Backend**: FastAPI (Python)
- **AI Engine**: Google Gemini API (2.0 Flash)
- **Deployment**: Docker & HuggingFace Spaces

---

## 🔧 Installation & Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/ubaidsamoo/omni-ai-bot.git
    cd omni-ai-bot
    ```

2.  **Configuration**:
    Create a `.env` file in the `backend/` directory and add your Google API Key:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    ```

3.  **Run with Docker (Recommended)**:
    ```bash
    docker-compose up --build
    ```

4.  **Local Development**:
    *   **Backend**: 
        ```bash
        cd backend
        python -m venv .venv
        pip install -r requirements.txt
        uvicorn main:app --reload
        ```
    *   **Frontend**:
        ```bash
        cd frontend
        streamlit run app.py
        ```

---

## 📝 About the Project
Omni AI is designed to provide a premium AI experience with a focus on speed, reliability, and modern aesthetics. Perfectly suited for educational, research, and personal productivity.

---

Built with ❤️ by [Ubaid Samoo](https://github.com/ubaidsamoo)
