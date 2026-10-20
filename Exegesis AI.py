import re
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import base64

st.set_page_config(page_title="Exegesis AI", page_icon="🎓", layout="wide")

# --- Secure API Secrets Fetching ---
if "OPENROUTER_API_KEY" in st.secrets:
    FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    st.error("🔒 API Key Missing! Please add 'OPENROUTER_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- Firebase Cloud Database Connection ---
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = init_firebase()
except Exception as e:
    st.error("⚠️ Firebase connection error. Please verify your Streamlit Secrets configuration.")
    st.stop()

# --- Database Helper Functions ---
def get_user_doc(username):
    doc_ref = db.collection("users").document(username)
    doc = doc_ref.get()
    return doc_ref, doc

def save_user_session():
    if st.session_state.get("logged_in") and st.session_state.get("user_name"):
        doc_ref = db.collection("users").document(st.session_state["user_name"])
        doc_ref.set({
            "messages": st.session_state.get("messages", []),
            "chat_history": st.session_state.get("chat_history", []),
            "hint_step": st.session_state.get("hint_step", 0),
            "attempts": st.session_state.get("attempts", 0),
            "account_type": st.session_state.get("account_type", ""),
            "gender": st.session_state.get("user_gender", ""),
            "profile_pic": st.session_state.get("profile_pic", ""),
            "last_active": datetime.now(timezone.utc).isoformat()
        }, merge=True)

# --- System Prompt Engineering Blocks ---
TUTOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. "
    "Follow a strict scaffolding process for questions or problems:\n"
    "1. Never give the final answer right away.\n"
    "2. Provide exactly up to 3 progressive hints over the conversation.\n"
    "3. Do NOT include meta-labels or describe the hint level.\n"
)
FRIEND_CHAT_PROMPT = "You are Exegesis AI, acting as a warm, comforting friend to a student who feels sad."
DYNAMIC_SAFETY_PROMPT = "You are a compassionate safety responder urging a student to connect with a trusted adult."

# --- Initialize App Session States ---
if "school_ai_enabled" not in st.session_state: st.session_state["school_ai_enabled"] = True
if "assigned_school_tasks" not in st.session_state:
    st.session_state["assigned_school_tasks"] = [
        "Complete Quadratic Formula practice sheet",
        "Read Chapter 3 on plant cell structures"
    ]

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "account_type" not in st.session_state: st.session_state["account_type"] = ""
if "user_gender" not in st.session_state: st.session_state["user_gender"] = "Not Disclosed"
if "messages" not in st.session_state: st.session_state["messages"] = []
if "chat_history" not in st.session_state: st.session_state["chat_history"] = []
if "profile_pic" not in st.session_state: st.session_state["profile_pic"] = ""
if "hint_step" not in st.session_state: st.session_state["hint_step"] = 0
if "attempts" not in st.session_state: st.session_state["attempts"] = 0
if "is_sad_mode" not in st.session_state: st.session_state["is_sad_mode"] = False
if "temp_profile_pic" not in st.session_state: st.session_state["temp_profile_pic"] = ""

# --- Onboarding Login & Signup Screen ---
if not st.session_state["logged_in"]:
    st.title("=== Welcome to Exegesis AI ===")
    auth_mode = st.radio("Choose Action", ["Log In", "Create Account"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entered_name = st.text_input("Username / Email", placeholder="Enter your username")
        entered_pass = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if auth_mode == "Create Account":
            acc_choice = st.radio("Access Portal Role", ["Student Portal", "Teacher Portal", "Principal Control Panel", "Personal Account"])
            gender_choice = st.radio("Select Gender", ["Male", "Female", "Other"])
            
            if st.button("Register Account", use_container_width=True):
                clean_name = entered_name.strip()
                if clean_name == "" or entered_pass == "":
                    st.error("Name and password cannot be empty.")
                else:
                    doc_ref, doc = get_user_doc(clean_name)
                    if doc.exists:
                        st.error("Username already exists. Please log in.")
                    else:
                        doc_ref.set({
                            "password": entered_pass,
                            "messages": [],
                            "chat_history": [],
                            "hint_step": 0,
                            "attempts": 0,
                            "account_type": acc_choice,
                            "gender": gender_choice,
                            "profile_pic": ""
                        })
                        st.success("Account created successfully! Switch to 'Log In'.")
        else:
            if st.button("Log In to Workspace", use_container_width=True):
                clean_name = entered_name.strip()
                doc_ref, doc = get_user_doc(clean_name)
                
                if doc.exists:
                    user_data = doc.to_dict()
                    if user_data.get("password") == entered_pass:
                        st.session_state["user_name"] = clean_name
                        st.session_state["account_type"] = user_data.get("account_type", "Personal Account")
                        st.session_state["user_gender"] = user_data.get("gender", "Not Disclosed")
                        st.session_state["messages"] = user_data.get("messages", [])
                        st.session_state["chat_history"] = user_data.get("chat_history", [])
                        st.session_state["profile_pic"] = user_data.get("profile_pic", "")
                        st.session_state["hint_step"] = user_data.get("hint_step", 0)
                        st.session_state["attempts"] = user_data.get("attempts", 0)
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")
    st.stop()

user_name = st.session_state["user_name"]
account_label = st.session_state["account_type"]

# --- Navigation Sidebar Interface Engine ---
with st.sidebar:
    st.title("📂 Workspace Settings")
    
    current_pic = st.session_state["profile_pic"]
    if current_pic:
        st.image(current_pic, width=80)
    
    uploaded_image = st.file_uploader("Upload Profile Picture", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        encoded_img = base64.b64encode(uploaded_image.read()).decode("utf-8")
        st.session_state["temp_profile_pic"] = f"data:image/png;base64,{encoded_img}"
        st.image(st.session_state["temp_profile_pic"], width=80, caption="Preview")

    if st.session_state["temp_profile_pic"]:
        if st.button("Confirm Profile Picture", use_container_width=True):
            st.session_state["profile_pic"] = st.session_state["temp_profile_pic"]
            st.session_state["temp_profile_pic"] = ""
            save_user_session()
            st.success("Profile picture updated!")
            st.rerun()

    st.write(f"👤 **Active User:** {user_name}")
    st.write(f"🏫 **Access:** {account_label}")
    
    if st.button("Log out System Session", use_container_width=True):
        save_user_session()
        st.session_state["logged_in"] = False
        st.rerun()

    st.markdown("---")
    if st.button("➕ New Chat / Topic", use_container_width=True):
        if st.session_state["messages"]:
            chat_title = st.session_state["messages"][0]["content"][:25] + "..."
            st.session_state["chat_history"].append({
                "title": chat_title,
                "messages": st.session_state["messages"],
                "time": datetime.now(timezone.utc).isoformat()
            })
        st.session_state["messages"] = []
        st.session_state["hint_step"] = 0
        st.session_state["attempts"] = 0
        st.session_state["is_sad_mode"] = False
        save_user_session()
        st.rerun()

    st.subheader("💬 Chat History")
    for i, chat in enumerate(st.session_state["chat_history"]):
        cols = st.columns([4, 1])
        with cols[0]:
            if st.button(chat["title"], key=f"history_{i}"):
                st.session_state["messages"] = chat["messages"]
                st.rerun()
        with cols[1]:
            if st.button("❌", key=f"del_chat_{i}"):
                st.session_state["chat_history"].pop(i)
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
st.title("🎓 Exegesis AI")
st.subheader("Your guide for learning and a comforting pal when you need it.")

for msg in st.session_state["messages"]:
    if msg["role"] == "assistant":
        avatar_img = "🤖"
    else:
        avatar_img = st.session_state.get("profile_pic") if st.session_state.get("profile_pic") else "👤"
        
    with st.chat_message(msg["role"], avatar=avatar_img):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask a question or type your answer...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    
    user_avatar = st.session_state.get("profile_pic") if st.session_state.get("profile_pic") else "👤"
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(user_input)

    if detect_harmful_keywords(user_input):
        with st.spinner("Exegesis AI is thinking..."):
            safety_reply = generate_dynamic_safety_response(user_input)
        st.session_state["messages"].append({"role": "assistant", "content": safety_reply})
        save_user_session()
        st.rerun()

    if check_sadness(user_input) and not st.session_state["is_sad_mode"]:
        st.session_state["is_sad_mode"] = True

    chat_context = [{"role": "system", "content": FRIEND_CHAT_PROMPT if st.session_state["is_sad_mode"] else TUTOR_PROMPT}] + st.session_state["messages"]
    
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
