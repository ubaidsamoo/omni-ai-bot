"""
Omni AI - Streamlit Frontend Dashboard
"""

import streamlit as st
import requests
import base64
from PIL import Image
import io
import os


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

    /* Chat bubbles */
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

    /* YouTube Q&A chat bubbles */
    .yt-user {
        background: #1a3a5c; color: #e0e0e0;
        border-radius: 18px 18px 4px 18px;
        padding: 12px 16px; margin: 8px 0 8px 60px;
    }
    .yt-bot {
        background: #1e1e2e; border: 1px solid #333;
        color: #e0e0e0; border-radius: 18px 18px 18px 4px;
        padding: 12px 16px; margin: 8px 60px 8px 0;
    }

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

    /* Transcript note */
    .transcript-note {
        background: #1e2a1e;
        border-left: 3px solid #4caf50;
        padding: 10px 14px; border-radius: 6px;
        font-size: 0.85em; color: #90ee90; margin-bottom: 12px;
    }

    /* YouTube tabs styling */
    .stTabs [data-baseweb="tab"] {
        background: #1e1e2e;
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        color: #aaa; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: #4f46e5 !important;
        color: white !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        border: none; color: white; font-weight: 700; border-radius: 12px;
        padding: 12px 28px; transition: all 0.2s;
    }
    .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(79,70,229,0.4); }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = "http://127.0.0.1:8000"

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = "user_session_1"
if "yt_module" not in st.session_state:
    # Use os.getenv to avoid FileNotFoundError from st.secrets if no secrets.toml exists
    api_key = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    st.session_state.yt_module = YouTubeModule(api_key=api_key)
if "yt_url" not in st.session_state:
    st.session_state.yt_url = ""
if "yt_results" not in st.session_state:
    st.session_state.yt_results = {}   # tab -> result
if "yt_qa_history" not in st.session_state:
    st.session_state.yt_qa_history = []

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0;'>
        <div style='font-size: 3rem;'>🤖</div>
        <h2 style='color: #667eea; margin: 8px 0;'>Omni AI</h2>
        <p style='color: #888; font-size: 0.85rem;'>Powered by Gemini 2.0 Flash</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    selected_page = st.radio("Navigate", ["💬 AI Chat", "📄 PDF Analyst", "📊 Data Analysis"], label_visibility="collapsed")
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

# Header (Chat page pe nahi)
if selected_page != "💬 AI Chat":
    st.markdown("""
    <div class='main-header'>
        <h1>🤖 Omni AI</h1>
        <p>Multimodal Intelligence • Chat • PDF • Data</p>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
if selected_page == "💬 AI Chat":
    chat_container = st.container(height=600, border=False)
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown("""
            <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;
                        height: 100%; text-align: center; margin-top: 100px;'>
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
    user_input = st.chat_input("What is your goal today? (Enter to send)")

    if st.button("Clear Chat 🗑️"):
        st.session_state.chat_history = []
        try:
            requests.post(f"{BACKEND_URL}/chat/clear", data={"session_id": st.session_state.session_id})
        except Exception:
            pass
        st.rerun()

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
# PAGE 2: PDF ANALYST — UPLOAD DOC AND CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif selected_page == "📄 PDF Analyst":
    st.markdown("## 📄 PDF Analyst Chatbot")
    st.markdown("##### Upload any PDF to get summaries, key points, and ask questions! (Max ~50,000 characters)")

    # ── Upload Input ──────────────────────────────
    col_upload, col_btn = st.columns([5, 1])
    with col_upload:
        pdf_file = st.file_uploader("Upload PDF File", type=["pdf"])
    with col_btn:
        st.write("") # spacing
        st.write("") 
        pdf_analyze_btn = st.button("🚀 Analyze", use_container_width=True)

    if pdf_file and pdf_file.name != st.session_state.get("pdf_name"):
        st.session_state.pdf_name = pdf_file.name
        st.session_state.pdf_results = {}
        st.session_state.pdf_qa_history = []
        
    if "pdf_results" not in st.session_state:
        st.session_state.pdf_results = {}
    if "pdf_qa_history" not in st.session_state:
        st.session_state.pdf_qa_history = []

    # Analyze button dabane pe sab tabs ke liye fetch karo
    if pdf_analyze_btn and pdf_file:
        with st.spinner("🔍 PDF analyze ho rahi hai — thoda sabr karo..."):
            try:
                pdf_bytes = pdf_file.getvalue()
                response = requests.post(
                    f"{BACKEND_URL}/document/analyze",
                    files={"pdf_file": (pdf_file.name, pdf_bytes, "application/pdf")},
                    data={"task": "summarize"},
                    timeout=120
                )
                if response.status_code == 200:
                    data = response.json()
                    if "error" in data:
                        st.error(data["error"])
                    else:
                        st.session_state.pdf_results["summary"] = data
                else:
                    st.error(f"❌ Backend Error: {response.text}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    elif pdf_analyze_btn and not pdf_file:
        st.warning("⚠️ Pehle PDF upload karo!")

    # ── TABS ──────────────────────────────────
    tab_summary, tab_qa = st.tabs([
        "📝 Summary & Key Points",
        "💬 Q&A Chat"
    ])

    # ── TAB 1: SUMMARY ────────────────────────
    with tab_summary:
        if "summary" in st.session_state.pdf_results:
            r = st.session_state.pdf_results["summary"]
            
            topic = r.get("topic", "Unknown")
            st.markdown(f"### 🏷️ Topic: {topic}")
            st.divider()
            
            st.markdown(r.get("analysis", ""))
        else:
            st.info("👆 Upar PDF upload karo aur **Analyze** button dabao!")

    # ── TAB 2: Q&A CHAT ───────────────────────
    with tab_qa:
        if not st.session_state.get("pdf_name"):
            st.info("👆 Pehle PDF upload karo aur Analyze dabao — phir yahan document ke baaray mein poochho!")
        else:
            topic = st.session_state.pdf_results.get("summary", {}).get("topic", "")
            st.markdown(f"##### 💬 Is document ({topic}) ke baare mein kuch bhi poochho!")
            st.divider()

            # Chat history dikhao
            for msg in st.session_state.pdf_qa_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="yt-user">🧑 {msg["text"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="yt-bot">🤖 {msg["text"]}</div>', unsafe_allow_html=True)

            # Input row
            q_col, btn_col = st.columns([5, 1])
            with q_col:
                user_q = st.text_input(
                    "Sawaal",
                    placeholder="Apna sawaal yahan likho...",
                    label_visibility="collapsed",
                    key="pdf_qa_input"
                )
            with btn_col:
                ask_btn = st.button("📨 Poochho", use_container_width=True, key="pdf_ask")

            if ask_btn and user_q and pdf_file:
                st.session_state.pdf_qa_history.append({"role": "user", "text": user_q})
                with st.spinner("🤔 Soch raha hoon..."):
                    try:
                        pdf_bytes = pdf_file.getvalue()
                        response = requests.post(
                            f"{BACKEND_URL}/document/analyze",
                            files={"pdf_file": (pdf_file.name, pdf_bytes, "application/pdf")},
                            data={"task": "qa", "question": user_q},
                            timeout=60
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if "error" in data:
                                answer = data["error"]
                            else:
                                answer = data.get("analysis", "⚠️ Jawab nahi mila.")
                            st.session_state.pdf_qa_history.append({"role": "bot", "text": answer})
                        else:
                            st.error(f"Backend error: {response.text}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

            if st.session_state.pdf_qa_history:
                if st.button("🗑️ Chat saaf karo", key="pdf_clear_chat"):
                    st.session_state.pdf_qa_history = []
                    st.rerun()

    # Tips
    with st.expander("💡 Tips & Tricks"):
        st.markdown('''
        - **Bilingual Focus:** Sawaal dono languages (Roman Urdu/English) mein pooche ja sakte hain.
        - **PDF Limit:** Boht bari books (>100 pages) model ke limit exceed kr skti hain, unhain compress karein.
        - **General Mode:** Agar apka sawal exactly document mein nahi hai, system apko uski General Knowledge dega aur clearly mention karega!
        ''')


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: DATA ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif selected_page == "📊 Data Analysis":
    st.markdown("### 💡 Try an Example Dataset")
    examples = {
        "None (Upload your own)": None,
        "🥗 Tips Analysis (Small)": "data/tips.csv",
        "🎓 Student Performance (Small)": "data/student.csv",
        "🏥 Insurance Costs (Bigger)": "data/insurance.csv"
    }
    selected_example = st.selectbox("Select a dataset to quickly test AI accuracy:", list(examples.keys()))

    csv_file = st.file_uploader("📎 OR CSV File Upload karo", type=["csv"])

    final_csv_data = None
    final_csv_name = None

    if csv_file:
        final_csv_data = csv_file.read()
        final_csv_name = csv_file.name
    elif selected_example != "None (Upload your own)":
        example_path = examples[selected_example]
        try:
            with open(example_path, "rb") as f:
                final_csv_data = f.read()
                final_csv_name = example_path.split("/")[-1]
            st.success(f"✅ Example Loaded: {selected_example}")
        except Exception as e:
            st.error(f"❌ Could not load example: {e}")

    if final_csv_data:
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
                        files={"csv_file": (final_csv_name, final_csv_data, "text/csv")},
                        data={"question": analysis_question},
                        timeout=120
                    )
                    if response.status_code == 200:
                        data = response.json()
                        shape = data.get("shape", {})

                        st.markdown("### 📈 Data Analytics Dashboard")

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
    🤖 <strong>Omni AI</strong> — Powered by Google Gemini 2.0 Flash |
    Built with FastAPI + Streamlit + LangChain
</div>
""", unsafe_allow_html=True)