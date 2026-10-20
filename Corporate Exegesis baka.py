import json
import os
import re
import requests
import streamlit as st

st.set_page_config(page_title="Exegesis AI", page_icon="🎓", layout="wide")

# --- Secure Secrets Fetching ---
if "OPENROUTER_API_KEY" in st.secrets:
    FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    st.error("🔒 API Key Missing! Please add 'OPENROUTER_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- Persistent File Storage for Users & History ---
USER_FILE = "users_database.json"

def load_database():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {
        "Aarav": {"password": "123", "messages": [], "hint_step": 0, "attempts": 0, "account_type": "Personal Account", "gender": "Male"}
    }

def save_database():
    with open(USER_FILE, "w") as f:
        json.dump(st.session_state["users_db"], f)

# --- Strict Scaffolding Prompt Blocks ---
TUTOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. "
    "Follow a strict scaffolding process for questions or problems:\n"
    "1. Never give the final answer right away.\n"
    "2. Provide exactly up to 3 progressive hints over the conversation to guide the student.\n"
    "3. Do NOT include meta-labels or describe the hint level (never write words like 'Hint 1', 'vague hint', 'subtle hint', or 'obvious hint'). Speak directly to the student.\n"
    "4. The first hint must be broad and conceptual. The second hint points to the specific method. The third hint guides the next step without revealing the final answer.\n"
    "5. Check student responses: if correct, praise and explain. If incorrect, progress to the next hint. After 3 hints are given, provide the full solution step-by-step."
)
FRIEND_CHAT_PROMPT = "You are Exegesis AI, acting as a warm, comforting friend to a student who feels sad."
DYNAMIC_SAFETY_PROMPT = "You are a compassionate safety responder urging a student to connect with a trusted adult."

# --- Initialize App State ---
if "mock_db_initialized" not in st.session_state:
    st.session_state["school_ai_enabled"] = True
    st.session_state["assigned_school_tasks"] = [
        "Complete Quadratic Formula practice sheet",
        "Read Chapter 3 on plant cell structures"
    ]
    st.session_state["users_db"] = load_database()
    st.session_state["mock_db_initialized"] = True

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "account_type" not in st.session_state: st.session_state["account_type"] = ""
if "user_gender" not in st.session_state: st.session_state["user_gender"] = "Not Disclosed"
if "messages" not in st.session_state: st.session_state["messages"] = []
if "hint_step" not in st.session_state: st.session_state["hint_step"] = 0
if "attempts" not in st.session_state: st.session_state["attempts"] = 0
if "is_sad_mode" not in st.session_state: st.session_state["is_sad_mode"] = False

# --- Custom CSS for Professional Fly-In Animation ---
def render_animated_greeting(text):
    animated_html = f"""
    <style>
    @keyframes flyIn {{
        0% {{
            opacity: 0;
            transform: translateY(-15px);
        }}
        100% {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    .professional-greeting {{
        animation: flyIn 0.8s cubic-bezier(0.25, 1, 0.5, 1) forwards;
        font-size: 1.1rem;
        color: #4A5568;
        margin-bottom: 1rem;
    }}
    </style>
    <div class="professional-greeting">{text}</div>
    """
    st.markdown(animated_html, unsafe_allow_html=True)

# --- Onboarding Login & Signup Screen ---
if not st.session_state["logged_in"]:
    st.title("=== Welcome to Exegesis AI ===")
    
    auth_mode = st.radio("Choose Action", ["Log In", "Create Account"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entered_name = st.text_input("Your Name", placeholder="Enter your username")
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
                        "hint_step": 0,
                        "attempts": 0,
                        "account_type": acc_choice,
                        "gender": gender_choice
                    }
                    save_database()
                    st.success("Account created successfully! Switch to 'Log In' to enter.")
        else:
            if st.button("Log In to Workspace", use_container_width=True):
                clean_name = entered_name.strip()
                if clean_name in st.session_state["users_db"] and st.session_state["users_db"][clean_name]["password"] == entered_pass:
                    user_data = st.session_state["users_db"][clean_name]
                    st.session_state["user_name"] = clean_name
                    st.session_state["account_type"] = user_data["account_type"]
                    st.session_state["user_gender"] = user_data["gender"]
                    st.session_state["messages"] = user_data.get("messages", [])
                    st.session_state["hint_step"] = user_data.get("hint_step", 0)
                    st.session_state["attempts"] = user_data.get("attempts", 0)
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    st.stop()

user_name = st.session_state["user_name"]
account_label = st.session_state["account_type"]

def save_user_session():
    if user_name in st.session_state["users_db"]:
        st.session_state["users_db"][user_name]["messages"] = st.session_state["messages"]
        st.session_state["users_db"][user_name]["hint_step"] = st.session_state["hint_step"]
        st.session_state["users_db"][user_name]["attempts"] = st.session_state["attempts"]
        save_database()

# --- Navigation Sidebar Interface Engine ---
with st.sidebar:
    st.title("📂 Workspace Settings")
    st.write(f"👤 **Active User:** {user_name}")
    st.write(f"🏫 **Access:** {account_label}")
    
    if st.button("Log out System Session", use_container_width=True):
        save_user_session()
        st.session_state["logged_in"] = False
        st.rerun()

    # Manage Account (Blocked for Students)
    if account_label != "Student Portal":
        st.markdown("---")
        with st.expander("⚙️ Manage Account"):
            new_user_name = st.text_input("New Username", value=user_name)
            new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
            if st.button("Update Account Details"):
                if new_user_name.strip() != "" and new_password.strip() != "":
                    if new_user_name != user_name:
                        st.session_state["users_db"][new_user_name] = st.session_state["users_db"].pop(user_name)
                        st.session_state["user_name"] = new_user_name
                    st.session_state["users_db"][st.session_state["user_name"]]["password"] = new_password
                    save_database()
                    st.success("Account updated successfully!")
                    st.rerun()

    if account_label != "Personal Account":
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
    if st.button("New Chat / Topic", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["hint_step"] = 0
        st.session_state["attempts"] = 0
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
# INTERFACE PANELS
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

elif account_label == "Teacher Portal":
    st.title("📋 Teacher Monitoring Dashboard")
    st.write("Track student activity and accounts.")
    st.write(f"Registered Users in Database: {list(st.session_state['users_db'].keys())}")

else:
    if not st.session_state["school_ai_enabled"] and account_label == "Student Portal":
        st.error("🔒 Access Suspended by administration.")
        st.stop()

    st.title("🎓 Exegesis Learning Space")
    
    if st.session_state["is_sad_mode"]: 
        render_animated_greeting(f"Hey {user_name}, I am here for you as a peer. What's on your mind?")
    else: 
        render_animated_greeting("What is on your mind today?")

    # Render chat messages
    for msg in st.session_state["messages"]:
        avatar_img = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar_img):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask a question or type your answer / where you got stuck...")

    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        if detect_harmful_keywords(user_input):
            with st.spinner("Exegesis AI is thinking..."):
                safety_reply = generate_dynamic_safety_response(user_input)
            st.session_state["messages"].append({"role": "assistant", "content": safety_reply})
            save_user_session()
            st.rerun()

        if check_sadness(user_input) and not st.session_state["is_sad_mode"]:
            st.session_state["is_sad_mode"] = True

        if st.session_state["is_sad_mode"]:
            chat_context = [{"role": "system", "content": FRIEND_CHAT_PROMPT}] + st.session_state["messages"]
            with st.spinner("Exegesis AI is thinking..."):
                try:
                    response = requests.post(url="https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"}, json={"model": "openrouter/free", "messages": chat_context}, timeout=20)
                    ai_reply = response.json()["choices"][0]["message"]["content"].strip()
                except Exception:
                    ai_reply = "I'm right here with you."
            st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
        else:
            chat_context = [{"role": "system", "content": TUTOR_PROMPT}] + st.session_state["messages"]
            with st.spinner("Exegesis AI is thinking..."):
                try:
                    response = requests.post(
                        url="https://openrouter.ai/api/v1/chat/completions", 
                        headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"}, 
                        json={"model": "openrouter/free", "messages": chat_context}, 
                        timeout=20
                    )
                    ai_reply = response.json()["choices"][0]["message"]["content"].strip()
                except Exception:
                    ai_reply = "⚠️ Sync error. Please resubmit your response."
            st.session_state["messages"].append({"role": "assistant", "content": ai_reply})

        save_user_session()
        st.rerun()
