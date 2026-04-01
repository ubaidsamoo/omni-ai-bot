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
    .stApp { background: #0f1116; color: #ffffff; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background: #161922; border-right: 1px solid #2d333b; }
    
    /* Premium Header */
    .main-header { 
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); 
        padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center;
        box-shadow: 0 10px 30px rgba(79,70,229,0.3); border: 1px solid rgba(255,255,255,0.1);
    }
    .main-header h1 { color: white; font-size: 2.2rem; font-weight: 800; margin: 0; }
    .chat-user { 
        background: #2563eb; color: white; padding: 12px 18px; 
        border-radius: 20px 20px 2px 20px; margin: 10px 0; 
        max-width: 85%; margin-left: auto; box-shadow: 0 4px 10px rgba(37,99,235,0.2);
    }
    .chat-ai { 
        background: #1e293b; border: 1px solid #334155; color: #f1f5f9; 
        padding: 12px 18px; border-radius: 20px 20px 20px 2px; margin: 10px 0; 
        max-width: 85%; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    .stChatInput { position: fixed; bottom: 20px; }

    /* Glassmorphism Cards */
    .dashboard-card {
        background: rgba(255,255,255,0.03); 
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px; padding: 24px; 
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        min-height: 140px;
    }
    .dashboard-card:hover { 
        transform: translateY(-8px); 
        background: rgba(255,255,255,0.06);
        border-color: #4f46e5;
        box-shadow: 0 12px 30px rgba(79,70,229,0.25);
    }
    
    .kpi-title { color: #94a3b8; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 1px; }
    .kpi-value { font-size: 2.5rem; font-weight: 800; color: #ffffff; margin: 0; }
    .kpi-trend { font-size: 0.8rem; font-weight: 500; margin-top: 8px; padding: 2px 8px; border-radius: 20px; background: rgba(76,175,80,0.1); color: #4ade80; }
    
    /* Smart Insight Box */
    .insight-box {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.05);
        border-left: 6px solid #4f46e5;
        padding: 30px; border-radius: 16px;
        font-size: 1.05rem; line-height: 1.7; color: #cbd5e1;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }

    .stButton > button { 
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); 
        border: none; color: white; font-weight: 700; border-radius: 12px;
        padding: 12px 28px; transition: all 0.2s;
    }
    .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(79,70,229,0.4); }
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

# Header - Show on all pages EXCEPT Chat page for that "Gemini/ChatGPT" look
if selected_page != "💬 AI Chat":
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
    # No extra titles here for that clean look
    chat_container = st.container(height=600, border=False)
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown("""
            <div style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; margin-top: 100px;'>
                <h1 style='font-size: 3.5rem; margin-bottom: 0;'>🤖 How can I help?</h1>
                <p style='color: #888; font-size: 1.2rem;'>Ask Omni AI anything in Roman Urdu or English.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"<div class='chat-user'>👤 <strong>You:</strong><br>{msg['content']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='chat-ai'>🤖 <strong>Omni AI:</strong><br>{msg['content']}</div>", unsafe_allow_html=True)

    st.divider()

    # FIX: st.chat_input - Enter se send, no send_btn
    # Fixed Input Box
    user_input = st.chat_input("What is your goal today? (Enter to send)")
    
    # Optional Clear button in a separate small row
    if st.button("Clear Chat 🗑️"):
        st.session_state.chat_history = []
        try:
            requests.post(f"{BACKEND_URL}/chat/clear", data={"session_id": st.session_state.session_id})
        except Exception:
            pass
        st.rerun()

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


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: YOUTUBE DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════
elif selected_page == "🎥 YouTube Deep Dive":
    st.markdown("## 🎥 YouTube Summarizer")

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
                            st.markdown(f"<div class='dashboard-card'><div class='kpi-title'>Total Rows</div><div class='kpi-value'>{shape.get('rows', 0):,}</div><div class='kpi-trend'>Stable</div></div>", unsafe_allow_html=True)
                        with m2:
                            st.markdown(f"<div class='dashboard-card'><div class='kpi-title'>Attributes</div><div class='kpi-value'>{shape.get('columns', 0)}</div><div class='kpi-trend'>Valid</div></div>", unsafe_allow_html=True)
                        with m3:
                            null_total = sum(data.get("null_counts", {}).values())
                            st.markdown(f"<div class='dashboard-card'><div class='kpi-title'>Missing</div><div class='kpi-value'>{null_total}</div><div class='kpi-trend' style='color:#ff4b4b;'>{round((null_total/max(1, shape.get('rows',1)))*100, 1)}%</div></div>", unsafe_allow_html=True)
                        with m4:
                            st.markdown("<div class='dashboard-card'><div class='kpi-title'>System</div><div class='kpi-value'>AI</div><div class='kpi-trend' style='color:#667eea;'>Optimized</div></div>", unsafe_allow_html=True)
                        
                        st.write("")
                        st.divider()

                        # Grid Layout: Charts and Insights
                        col_chart, col_insights = st.columns([1.2, 1])
                        
                        with col_chart:
                            if data.get("chart_base64"):
                                st.markdown("#### 📊 Analysis Snapshot")
                                chart_bytes = base64.b64decode(data["chart_base64"])
                                chart_image = Image.open(io.BytesIO(chart_bytes))
                                st.image(chart_image, use_column_width=True)
                        
                        with col_insights:
                            st.markdown("#### 🚀 Smart Strategy Insights")
                            st.markdown(f"<div class='insight-box'>{data.get('ai_insights', 'No insights available').replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

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