import json
import re
import requests
import streamlit as st

st.set_page_config(page_title="Exegesis AI Enterprise", page_icon="🎓", layout="wide")

# --- Secure Secrets Fetching ---
if "OPENROUTER_API_KEY" in st.secrets:
    FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    st.error("🔒 API Key Missing! Please add 'OPENROUTER_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- System Prompt Engineering Blocks ---
HINT_GENERATOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. Use a scaffolding method: guide the student step by step instead of giving the answer straight away.\n\n"
    "Rules:\n"
    "- Use simple words and short sentences. Add a small everyday example where it helps.\n"
    "- HINT1 is a gentle nudge that points to the key idea. It must NOT contain the answer.\n"
    "- HINT2 is more direct and names the method, rule or concept to use. It must NOT contain the final answer.\n"
    "- HINT3 is almost the full path (for example the first steps of the working) but still leaves the last step to the student.\n"
    "- EXPLANATION gives the complete answer with clear step-by-step reasoning, then one short line to remember.\n"
    "- Write plain text only. No markdown, no bullet points, no bold, and no extra headings.\n"
    "Return your response in EXACTLY this format:\nHINT1: <text>\n\nHINT2: <text>\n\nHINT3: <text>\n\nEXPLANATION: <text>"
)

TUTOR_CHAT_PROMPT = "You are Exegesis AI, a friendly tutor for school students. Answer clearly in simple words, in a few short sentences."
FRIEND_CHAT_PROMPT = "You are Exegesis AI, acting as a warm, comforting friend. Speak like a kind peer or trusted friend to a student who feels sad."
DYNAMIC_SAFETY_PROMPT = "You are a compassionate safety responder. Provide a unique, highly specific empathetic response urging a student to connect with a trusted adult."

# --- Mock Cloud Database & User Registry ---
if "mock_db_initialized" not in st.session_state:
    st.session_state["school_ai_enabled"] = True
    st.session_state["assigned_school_tasks"] = [
        "Complete Quadratic Formula practice sheet",
        "Read Chapter 3 on plant cell structures"
    ]
    # Stores username: {"password": str, "messages": [], "account_type": str, "gender": str}
    st.session_state["users_db"] = {
        "Aarav": {"password": "123", "messages": [], "account_type": "Student Portal", "gender": "Male"}
    }
    st.session_state["mock_db_initialized"] = True

# Persistent Chat State Controls
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "account_type" not in st.session_state: st.session_state["account_type"] = ""
if "user_gender" not in st.session_state: st.session_state["user_gender"] = "Not Disclosed"
if "current_topic" not in st.session_state: st.session_state["current_topic"] = None
if "hints" not in st.session_state: st.session_state["hints"] = {}
if "explanation" not in st.session_state: st.session_state["explanation"] = ""
if "attempt" not in st.session_state: st.session_state["attempt"] = 1
if "show_explanation" not in st.session_state: st.session_state["show_explanation"] = False
if "messages" not in st.session_state: st.session_state["messages"] = []
if "is_sad_mode" not in st.session_state: st.session_state["is_sad_mode"] = False

# --- Onboarding Login & Signup Screen ---
if not st.session_state["logged_in"]:
    st.title("=== Welcome to Exegesis AI ===")
    
    auth_mode = st.radio("Choose Action", ["Log In", "Create Account"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entered_name = st.text_input("Your Name", placeholder="e.g. Alex")
        entered_pass = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if auth_mode == "Create Account":
            acc_choice = st.radio("Access Portal Role", ["Student Portal", "Teacher Portal", "Principal Control Panel", "Personal Account"])
            gender_choice = st.radio("Select Gender", ["Male", "Female", "Other"])
            
            if st.button("Register Account", use_container_width=True):
                clean_name = entered_name.strip()
                if clean_name == "" or entered_pass == "":
                    st.error("Name and password cannot be empty.")
                elif clean_name in st.session_state["users_db"]:
                    st.error("Username already exists. Please log in.")
                else:
                    st.session_state["users_db"][clean_name] = {
                        "password": entered_pass,
                        "messages": [],
                        "account_type": acc_choice,
                        "gender": gender_choice
                    }
                    st.success("Account created successfully! Switch to 'Log In' to enter.")
        else:
            if st.button("Log In to Workspace", use_container_width=True):
                clean_name = entered_name.strip()
                if clean_name in st.session_state["users_db"] and st.session_state["users_db"][clean_name]["password"] == entered_pass:
                    user_data = st.session_state["users_db"][clean_name]
                    st.session_state["user_name"] = clean_name
                    st.session_state["account_type"] = user_data["account_type"]
                    st.session_state["user_gender"] = user_data["gender"]
                    st.session_state["messages"] = user_data["messages"]
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    st.stop()

user_name = st.session_state["user_name"]
account_label = st.session_state["account_type"]

# Helper to save messages back to the mock database dictionary
def save_user_session():
    if user_name in st.session_state["users_db"]:
        st.session_state["users_db"][user_name]["messages"] = st.session_state["messages"]

# --- Navigation Sidebar Interface Engine ---
with st.sidebar:
    st.title("📂 Workspace Settings")
    st.write(f"👤 **Active User:** {user_name}")
    st.write(f"🏫 **Access:** {account_label}")
    
    if st.button("Log out System Session", use_container_width=True):
        save_user_session()
        st.session_state["logged_in"] = False
        st.rerun()
        
    st.markdown("---")
    st.subheader("📋 Assigned School Tasks")
    
    if account_label == "Student Portal":
        if st.session_state["assigned_school_tasks"]:
            for task in st.session_state["assigned_school_tasks"]:
                st.checkbox(task, key=f"check_{task[:15]}")
        else:
            st.caption("No homework assignments active right now.")
            
    elif account_label in ["Teacher Portal", "Principal Control Panel"]:
        for i, task in enumerate(st.session_state["assigned_school_tasks"]):
            col_t, col_b = st.columns([4, 1])
            with col_t:
                st.caption(f"{i+1}. {task}")
            with col_b:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state["assigned_school_tasks"].pop(i)
                    st.rerun()
                    
        st.markdown("---")
        new_task_input = st.text_input("Push New Assignment Topic", key="new_task_field", placeholder="e.g. Read Physics Chapter 2")
        if st.button("➕ Assign Task to Class", use_container_width=True):
            if new_task_input.strip() != "":
                st.session_state["assigned_school_tasks"].append(new_task_input.strip())
                st.rerun()

    st.markdown("---")
    if account_label == "Student Portal":
        if st.button("New Chat / Topic", use_container_width=True):
            st.session_state["current_topic"] = None
            st.session_state["hints"] = {}
            st.session_state["explanation"] = ""
            st.session_state["attempt"] = 1
            st.session_state["show_explanation"] = False
            st.session_state["messages"] = []
            st.session_state["is_sad_mode"] = False
            save_user_session()
            st.rerun()

# --- Security & Keyword Core Engines ---
def detect_harmful_keywords(text):
    harmful_keywords = ["kill", "suicide", "harm", "hurt", "violence", "weapon", "gun", "die", "unalive"]
    cleaned_text = text.lower()
    for word in harmful_keywords:
        if re.search(r'\b' + re.escape(word) + r'\b', cleaned_text): return True
    return False

def generate_dynamic_safety_response(violation_text):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"},
            json={"model": "openrouter/free", "messages": [{"role": "system", "content": DYNAMIC_SAFETY_PROMPT}, {"role": "user", "content": violation_text}]},
            timeout=15,
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return "Please connect with a counselor, family member, or teacher right away to keep you safe."

def check_sadness(text):
    sad_keywords = ["sad", "lonely", "down", "upset", "cry", "crying", "depressed"]
    return any(word in text.lower() for word in sad_keywords)

# =====================================================================
# INTERFACE PANEL 1: PRINCIPAL CONTROL PANEL
# =====================================================================
if account_label == "Principal Control Panel":
    st.title("🛡️ Institutional Admin Console")
    st.write("Manage systemic artificial intelligence guardrails.")
    
    if st.session_state["school_ai_enabled"]:
        st.success("🟢 Exegesis AI Scaffolding Engines are currently **ACTIVE**.")
        if st.button("🔴 Turn Off School AI Access", use_container_width=True):
            st.session_state["school_ai_enabled"] = False
            st.rerun()
    else:
        st.error("🔴 Exegesis AI Scaffolding Engines are currently **DISABLED**.")
        if st.button("🟢 Turn On School AI Access", use_container_width=True):
            st.session_state["school_ai_enabled"] = True
            st.rerun()

# =====================================================================
# INTERFACE PANEL 2: TEACHER PORTAL
# =====================================================================
elif account_label == "Teacher Portal":
    st.title("📋 Teacher Monitoring Dashboard")
    st.write("Track student activity and accounts.")
    st.write(f"Registered Users in Database: {list(st.session_state['users_db'].keys())}")

# =====================================================================
# INTERFACE PANEL 3: STUDENT & PERSONAL TUTOR PORTAL
# =====================================================================
else:
    if not st.session_state["school_ai_enabled"] and account_label == "Student Portal":
        st.error("🔒 Access Suspended by administration.")
        st.stop()

    st.title("🎓 Exegesis Learning Space")
    
    if st.session_state["is_sad_mode"]: st.write(f"Hey {user_name}, I am here for you as a peer. What's on your mind?")
    else: st.write(f"Hello {user_name}, what concept are we mastering today?")

    user_input = st.chat_input("Ask a question or topic to learn...")

    if user_input:
        if detect_harmful_keywords(user_input):
            safety_reply = generate_dynamic_safety_response(user_input)
            st.session_state["messages"].append({"role": "user", "content": user_input})
            st.session_state["messages"].append({"role": "assistant", "content": safety_reply})
            st.session_state["current_topic"] = "Safety Intercept Notice"
            save_user_session()
            st.rerun()

        if check_sadness(user_input) and not st.session_state["is_sad_mode"]:
            st.session_state["is_sad_mode"] = True
            st.session_state["current_topic"] = "Friendship Space"

        if st.session_state["is_sad_mode"]:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            chat_context = [{"role": "system", "content": FRIEND_CHAT_PROMPT}] + st.session_state["messages"]
            try:
                response = requests.post(url="https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"}, json={"model": "openrouter/free", "messages": chat_context}, timeout=20)
                st.session_state["messages"].append({"role": "assistant", "content": response.json()["choices"][0]["message"]["content"].strip()})
            except Exception:
                st.session_state["messages"].append({"role": "assistant", "content": "I'm right here with you."})
            save_user_session()
            st.rerun()

        elif st.session_state["current_topic"] is None:
            st.session_state["current_topic"] = user_input
            try:
                response = requests.post(url="https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"}, json={"model": "openrouter/free", "messages": [{"role": "system", "content": HINT_GENERATOR_PROMPT}, {"role": "user", "content": user_input}]}, timeout=20)
                response_content = response.json()["choices"][0]["message"]["content"]
                pattern = r"(HINT1|HINT2|HINT3|EXPLANATION):\s*(.*?)(?=\n\s*(?:HINT1|HINT2|HINT3|EXPLANATION):|\Z)"
                sections = {label: text.strip() for label, text in re.findall(pattern, response_content, re.S)}
                st.session_state["hints"] = {i: sections[f"HINT{i}"] for i in (1, 2, 3) if f"HINT{i}" in sections}
                st.session_state["explanation"] = sections.get("EXPLANATION", "")
            except Exception:
                st.error("API Error. Please retype topic.")
                st.session_state["current_topic"] = None
            save_user_session()
            st.rerun()
        else:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            chat_context = [{"role": "system", "content": TUTOR_CHAT_PROMPT}] + st.session_state["messages"]
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions", 
                    headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"}, 
                    json={"model": "openrouter/free", "messages": chat_context}, 
                    timeout=20
                )
                response.raise_for_status()
                ai_reply = response.json()["choices"][0]["message"]["content"].strip()
                st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
            except Exception:
                st.session_state["messages"].append({"role": "assistant", "content": "⚠️ Sync error. Please resubmit."})
            save_user_session()
            st.rerun()

    # --- Student UI Rendering Logic Panels ---
    if st.session_state["current_topic"] in ["Safety Intercept Notice", "Friendship Space"] or st.session_state["is_sad_mode"]:
        for msg in st.session_state["messages"]:
            avatar_img = "🤖" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar_img):
                st.markdown(msg["content"])
                
    elif st.session_state["current_topic"]:
        st.markdown(f"### 📝 Concepts Working: *{st.session_state['current_topic']}*")
        
        for i in range(1, min(st.session_state["attempt"], 3) + 1):
            if i in st.session_state["hints"]: 
                st.info(f"💡 **Hint {i}:** {st.session_state['hints'][i]}")
                
        if st.session_state["attempt"] < 3:
            if st.button("Need another hint ➡️"):
                st.session_state["attempt"] += 1
                st.rerun()
        elif not st.session_state["show_explanation"]:
            if st.button("🔓 Reveal Full Explanation"):
                st.session_state["show_explanation"] = True
                st.rerun()
                
        if st.session_state["show_explanation"]:
            st.success(st.session_state["explanation"])
            st.markdown("---")

        if len(st.session_state["messages"]) > 0:
            st.subheader("💬 Chat Messages")
            for msg in st.session_state["messages"]:
                avatar_img = "🤖" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=avatar_img):
                    st.markdown(msg["content"])
