import re
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta
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
            "friends": st.session_state.get("friends", []),
            "account_type": st.session_state.get("account_type", ""),
            "gender": st.session_state.get("user_gender", ""),
            "profile_pic": st.session_state.get("profile_pic", ""),
            "user_city": st.session_state.get("user_city", "London"),
            "last_active": datetime.now(timezone.utc).isoformat()
        }, merge=True)

# --- Weather Function ---
def get_weather(city_name):
    if not city_name:
        return "Please enter a location."
    try:
        url_j1 = f"https://wttr.in/{city_name}?format=j1"
        resp_j1 = requests.get(url_j1, timeout=5)
        
        if resp_j1.status_code == 200:
            data = resp_j1.json()
            condition = data["current_condition"][0]["weatherDesc"][0]["value"]
            temp_c = data["current_condition"][0]["temp_C"]
            temp_f = data["current_condition"][0]["temp_F"]
            today = data["weather"][0]
            
            return (
                f"**Condition:** {condition}\n\n"
                f"🌡️ **Current:** {temp_c}°C / {temp_f}°F\n\n"
                f"📉 **Lowest:** {today['mintempC']}°C / {today['mintempF']}°F\n\n"
                f"📈 **Highest:** {today['maxtempC']}°C / {today['maxtempF']}°F"
            )
    except Exception:
        pass
    return "Unable to fetch weather data."

# --- System Prompt Blocks ---
TUTOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students.\n"
    "Follow a strict scaffolding process for questions or problems:\n"
    "1. Never give the final answer right away.\n"
    "2. Provide exactly up to 3 progressive hints over the conversation.\n"
    "3. Do NOT include meta-labels or describe the hint level.\n"
    "4. If tagged as @exegesis in group chats, solve the students' doubts step-by-step."
)
FRIEND_CHAT_PROMPT = "You are Exegesis AI, acting as a warm, comforting friend."
DYNAMIC_SAFETY_PROMPT = "You are a compassionate safety responder urging a student to connect with a trusted adult."

# --- Initialize Session States ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "full_name" not in st.session_state: st.session_state["full_name"] = ""
if "account_type" not in st.session_state: st.session_state["account_type"] = "Student Portal"
if "messages" not in st.session_state: st.session_state["messages"] = []
if "chat_history" not in st.session_state: st.session_state["chat_history"] = []
if "friends" not in st.session_state: st.session_state["friends"] = []
if "active_group_id" not in st.session_state: st.session_state["active_group_id"] = None
if "profile_pic" not in st.session_state: st.session_state["profile_pic"] = ""
if "user_city" not in st.session_state: st.session_state["user_city"] = "London"
if "app_mode" not in st.session_state: st.session_state["app_mode"] = "Solo Study / AI Chat"

# --- Onboarding Login & Signup ---
if not st.session_state["logged_in"]:
    st.title("=== Welcome to Exegesis AI ===")
    auth_mode = st.radio("Choose Action", ["Log In", "Create Account"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entered_name = st.text_input("Username", placeholder="Enter your username")
        entered_pass = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if auth_mode == "Create Account":
            entered_fullname = st.text_input("Full Name", placeholder="Enter your exact Full Name")
            acc_choice = st.radio("Access Portal Role", ["Student Portal", "Teacher Portal", "Principal Control Panel", "Personal Account"])
            
            if st.button("Register Account", use_container_width=True):
                clean_name = entered_name.strip()
                clean_fullname = entered_fullname.strip()
                if not clean_name or not entered_pass or not clean_fullname:
                    st.error("All fields including full name are required.")
                else:
                    doc_ref, doc = get_user_doc(clean_name)
                    if doc.exists:
                        st.error("Username already exists.")
                    else:
                        doc_ref.set({
                            "password": entered_pass,
                            "full_name": clean_fullname,
                            "messages": [],
                            "chat_history": [],
                            "friends": [],
                            "account_type": acc_choice,
                            "user_city": "London",
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
                        st.session_state["full_name"] = user_data.get("full_name", clean_name)
                        st.session_state["account_type"] = user_data.get("account_type", "Student Portal")
                        st.session_state["messages"] = user_data.get("messages", [])
                        st.session_state["chat_history"] = user_data.get("chat_history", [])
                        st.session_state["friends"] = user_data.get("friends", [])
                        st.session_state["user_city"] = user_data.get("user_city", "London")
                        st.session_state["profile_pic"] = user_data.get("profile_pic", "")
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")
    st.stop()

user_name = st.session_state["user_name"]
user_role = st.session_state["account_type"]

# --- Sidebar Navigation ---
with st.sidebar:
    st.title("📂 Workspace")
    
    st.session_state["app_mode"] = st.radio("Select Mode", ["Solo Study / AI Chat", "👥 Friends & Study Groups"])
    
    st.markdown("---")
    
    # --- Profile Picture Section (Directly below Workspace) ---
    st.subheader("👤 Profile Picture")
    uploaded_profile = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"], key="sidebar_profile_uploader")
    if uploaded_profile:
        pic_bytes = base64.b64encode(uploaded_profile.read()).decode("utf-8")
        st.session_state["profile_pic"] = f"data:image/png;base64,{pic_bytes}"
        save_user_session()
        st.success("Profile picture updated!")

    if st.session_state["profile_pic"]:
        st.image(st.session_state["profile_pic"], width=80)

    st.markdown("---")
    
    # Show Chat History & New Chat only when in Solo Study mode
    if st.session_state["app_mode"] == "Solo Study
