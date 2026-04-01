"""
Omni AI - Streamlit Frontend Dashboard
"""

import streamlit as st
import requests
import base64
from PIL import Image
import io

st.set_page_config(page_title="Omni AI", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%); color: #e0e0e0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%); border-right: 1px solid #2d2d5e; }
    .main-header { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; margin-bottom: 20px; text-align: center; box-shadow: 0 8px 32px rgba(102,126,234,0.3); }
    .main-header h1 { color: white; font-size: 2.5rem; margin: 0; }
    .main-header p { color: rgba(255,255,255,0.85); font-size: 1rem; margin: 8px 0 0 0; }
    .feature-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; margin: 10px 0; }
    .chat-user { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 12px 16px; border-radius: 18px 18px 4px 18px; margin: 8px 0; max-width: 80%; margin-left: auto; }
    .chat-ai { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #e0e0e0; padding: 12px 16px; border-radius: 18px 18px 18px 4px; margin: 8px 0; max-width: 80%; }
    .stButton > button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; padding: 10px 24px; font-weight: 600; }
    hr { border-color: rgba(255,255,255,0.1); }
    [data-testid="stMetric"] { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .metric-card { background: rgba(255,255,255,0.05); border-top: 4px solid #667eea; padding: 15px; border-radius: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# FIX: 127.0.0.1 instead of localhost
BACKEND_URL = "http://127.0.0.1:8000"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = "user_session_1"
if "uploaded_doc_id" not in st.session_state:
    st.session_state.uploaded_doc_id = None
if "uploaded_doc_name" not in st.session_state:
    st.session_state.uploaded_doc_name = None

with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0;'>
        <div style='font-size: 3rem;'>🤖</div>
        <h2 style='color: #667eea; margin: 8px 0;'>Omni AI</h2>
        <p style='color: #888; font-size: 0.85rem;'>Powered by Gemini 1.5 Flash</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    selected_page = st.radio("Navigate", ["💬 AI Chat", "🎥 YouTube Deep Dive", "📊 Data Analysis"], label_visibility="collapsed")
    st.divider()
    st.markdown("**🔗 Backend Status**")
    try:
        resp = requests.get(f"{BACKEND_URL}/", timeout=2)
        if resp.status_code == 200:
            st.success("✅ Connected")
        else:
            st.error("❌ Backend Error")
    except Exception:
        st.error("❌ Backend Offline")
        st.info("💡 Run: `uvicorn main:app --reload` in backend/ folder")
    st.divider()
    st.markdown("<p style='color:#666; font-size:0.75rem; text-align:center;'>Omni AI v2.0 | Built with ❤️</p>", unsafe_allow_html=True)

st.markdown("""
<div class='main-header'>
    <h1>🤖 Omni AI</h1>
    <p>Multimodal Intelligence • Chat • YouTube • Data</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
if selected_page == "💬 AI Chat":
    st.markdown("## 💬 Conversational AI")
    st.markdown("Talk with Roman Urdu Omni Ai")

    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown("""
            <div style='text-align:center; padding:40px; color:#666;'>
                <div style='font-size:3rem;'>👋</div>
                <p>Hello! Ask Anything!</p>
            </div>
            """, unsafe_allow_html=True)

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f"<div class='chat-user'><strong>You:</strong><br>{msg['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-ai'><strong>🤖 Omni AI:</strong><br>{msg['content']}</div>", unsafe_allow_html=True)

    st.divider()

    # FIX: st.chat_input - Enter se send, no send_btn
    col1, col2 = st.columns([6, 1])
    with col1:
        user_input = st.chat_input("What Your Today Goal... (Enter to send)")
    with col2:
        st.write("")
        clear_btn = st.button("Clear 🗑️", use_container_width=True)

    # FIX: sirf user_input check karo, send_btn nahi
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("🤔 Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/chat/message",
                    data={"message": user_input, "session_id": st.session_state.session_id}
                )
                if response.status_code == 200:
                    ai_response = response.json()["response"]
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                else:
                    st.error(f"Backend error: {response.text}")
                    st.session_state.chat_history.pop()
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.session_state.chat_history.pop()
        st.rerun()

    if clear_btn:
        st.session_state.chat_history = []
        try:
            requests.post(f"{BACKEND_URL}/chat/clear", data={"session_id": st.session_state.session_id})
        except Exception:
            pass
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: YOUTUBE DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════
elif selected_page == "🎥 YouTube Deep Dive":
    st.markdown("## 🎥 YouTube Deep Dive")
    st.markdown("Kisi bhi YouTube video ka transcript extract karo aur AI se deep analysis karo!")

    yt_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

    col1, col2 = st.columns(2)
    with col1:
        analysis_type = st.selectbox(
            "📋 Analysis Type",
            options=["summarize", "key_points", "chapters", "sentiment", "qa"],
            format_func=lambda x: {
                "summarize": "📝 Complete Summary",
                "key_points": "🎯 Key Points & Takeaways",
                "chapters": "📑 Chapter Breakdown",
                "sentiment": "😊 Sentiment Analysis",
                "qa": "❓ Question & Answer"
            }[x]
        )
    with col2:
        user_question = ""
        if analysis_type == "qa":
            user_question = st.text_input("Your Question", placeholder="Video ke baare mein kya jaanna chahte ho?")
        else:
            st.info("💡 Analysis type select karo - AI automatic kaam karega!")

    analyze_btn = st.button("🔍 Analyze Video", use_container_width=True)

    if analyze_btn and yt_url:
        with st.spinner("📥 Transcript extract ho raha hai... phir AI analyze karega..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/youtube/analyze",
                    data={"url": yt_url, "task": analysis_type, "question": user_question},
                    timeout=120
                )
                if response.status_code == 200:
                    data = response.json()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🎥 Video ID", data.get("video_id", "N/A"))
                    with col2:
                        transcript_len = data.get("transcript_length", 0)
                        st.metric("📝 Transcript Length", f"{transcript_len:,} chars")
                    with col3:
                        st.metric("📖 Approx. Words", f"~{transcript_len // 5:,}")
                    
                    st.divider()
                    
                    if is_fallback:
                        st.warning("📡 YouTube Transcripts are currently blocked/disabled by the server. Switching to AI Analysis based on Video Metadata (Title/Description).")
                    
                    st.markdown("### 🤖 AI Analysis")
                    st.markdown(data.get("analysis", "No analysis available"))
                    with st.expander("📜 View Transcript Preview"):
                        st.text_area("Transcript (Preview)", value=data.get("transcript_preview", ""), height=200, disabled=True)
                    st.markdown(f"🔗 [Video Link]({data.get('video_url', yt_url)})")
                else:
                    st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
            except requests.Timeout:
                st.error("⏱️ Timeout! Video bahut lamba ho sakta hai.")
            except Exception as e:
                st.error(f"❌ Connection Error: {e}")
    elif analyze_btn and not yt_url:
        st.warning("⚠️ Pehle YouTube URL enter karo!")

    with st.expander("💡 Tips & Tricks"):
        st.markdown("""
        - English captions wali videos best kaam karti hain
        - Auto-generated captions bhi work karti hain
        - Long videos ke liye "Key Points" option use karo
        - Private videos supported nahi hain
        """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: DATA ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif selected_page == "📊 Data Analysis":
    st.markdown("## 📊 AI-Powered Data Analysis")
    st.markdown("CSV file upload karo - AI statistical insights aur automated charts banayega!")

    csv_file = st.file_uploader("📎 CSV File Upload karo", type=["csv"])

    if csv_file:
        analysis_question = st.text_area(
            "🤔 Analysis Question (Optional)",
            value="Give me a complete statistical summary and the most important insights from this dataset.",
            height=80
        )
        analyze_data_btn = st.button("📊 Run Analysis", use_container_width=True)

        if analyze_data_btn:
            with st.spinner("🔄 Data analyze ho raha hai aur charts ban rahe hain..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/data/analyze",
                        files={"csv_file": (csv_file.name, csv_file.read(), "text/csv")},
                        data={"question": analysis_question},
                        timeout=120
                    )
                    if response.status_code == 200:
                        data = response.json()
                        shape = data.get("shape", {})
                        
                        # --- POWER BI DASHBOARD LAYOUT ---
                        st.markdown("### 📈 Data Analytics Dashboard")
                        
                        # KPI Metrics Row
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown("<div class='metric-card'><strong>Total Rows</strong><br><h2>{:,}</h2></div>".format(shape.get('rows', 0)), unsafe_allow_html=True)
                        with m2:
                            st.markdown("<div class='metric-card'><strong>Columns</strong><br><h2>{}</h2></div>".format(shape.get('columns', 0)), unsafe_allow_html=True)
                        with m3:
                            null_total = sum(data.get("null_counts", {}).values())
                            st.markdown("<div class='metric-card'><strong>Missing Vals</strong><br><h2>{}</h2></div>".format(null_total), unsafe_allow_html=True)
                        with m4:
                            st.markdown("<div class='metric-card'><strong>Status</strong><br><h2 style='color:#4CAF50;'>Ready</h2></div>", unsafe_allow_html=True)
                        
                        st.write("")
                        st.divider()

                        # Grid Layout: Charts and Insights
                        col_chart, col_insights = st.columns([1.3, 1])
                        
                        with col_chart:
                            if data.get("chart_base64"):
                                st.markdown("#### 📊 Visual Distribution")
                                chart_bytes = base64.b64decode(data["chart_base64"])
                                chart_image = Image.open(io.BytesIO(chart_bytes))
                                try:
                                    st.image(chart_image, use_column_width=True)
                                except:
                                    st.image(chart_image) # Fallback if even col_width fails
                        
                        with col_insights:
                            st.markdown("#### 💡 AI Strategic Insights")
                            st.markdown(f"""
                            <div style='background: rgba(102,126,234,0.1); border-left: 5px solid #667eea; padding: 20px; border-radius: 10px; min-height: 400px;'>
                                {data.get('ai_insights', 'No insights available').replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)

                        if data.get("sample_data"):
                            with st.expander("👀 View Raw Sample Data"):
                                import pandas as pd
                                df_sample = pd.DataFrame(data["sample_data"])
                                st.dataframe(df_sample, use_container_width=True)
                    else:
                        st.error(f"❌ {response.json().get('detail', 'Analysis failed')}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")


# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style='text-align:center; color:#555; font-size:0.8rem; padding:10px 0;'>
    🤖 <strong>Omni AI</strong> — Powered by Google Gemini 1.5 Flash |
    Built with FastAPI + Streamlit + LangChain
</div>
""", unsafe_allow_html=True)