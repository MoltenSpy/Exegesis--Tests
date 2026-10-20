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
            "user_city": st.session_state.get("user_city", "London"),
            "last_active": datetime.now(timezone.utc).isoformat()
        }, merge=True)

# --- Weather Function (Only Temperature & Conditions) ---
def get_weather(city_name):
    if not city_name:
        return "Please enter a location."
    try:
        url_j1 = f"https://wttr.in/{city_name}?format=j1"
        resp_j1 = requests.get(url_j1, timeout=5)
        
        if resp_j1.status_code == 200:
            data = resp_j1.json()
            
            # Current Condition & Temps
            condition = data["current_condition"][0]["weatherDesc"][0]["value"]
            temp_c = data["current_condition"][0]["temp_C"]
            temp_f = data["current_condition"][0]["temp_F"]
            
            # Today's High & Low
            today = data["weather"][0]
            min_c = today["mintempC"]
            max_c = today["maxtempC"]
            min_f = today["mintempF"]
            max_f = today["maxtempF"]
            
            weather_text = (
                f"**Condition:** {condition}\n\n"
                f"🌡️ **Current:** {temp_c}°C / {temp_f}°F\n\n"
                f"📉 **Lowest:** {min_c}°C / {min_f}°F\n\n"
                f"📈 **Highest:** {max_c}°C / {max_f}°F"
            )
            return weather_text
    except Exception:
        pass
    return "Unable to fetch weather data."

# --- System Prompt Engineering Blocks ---
TUTOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students.\n"
    "Follow a strict scaffolding process for questions or problems:\n"
    "1. Never give the final answer right away.\n"
    "2. Provide exactly up to 3 progressive hints over the conversation.\n"
    "3. Do NOT include meta-labels or describe the hint level.\n"
    "4. TIME INSTRUCTIONS: If the user asks for the current time, tell them you do not know their location and ask which country or city they are in. "
    "If the user provides a country or city, calculate and tell them the current local time for that location."
)
FRIEND_CHAT_PROMPT = "You are Exegesis AI, acting as a warm, comforting friend."
DYNAMIC_SAFETY_PROMPT = "You are a compassionate safety responder urging a student to connect with a trusted adult."

# --- Initialize Session States ---
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
if "user_city" not in st.session_state: st.session_state["user_city"] = "London"

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
                            "profile_pic": "",
                            "user_city": "London"
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
                        st.session_state["user_city"] = user_data.get("user_city", "London")
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

    st.markdown("---")
    
    st.subheader("🌤️ Weather Report")
    
    user_location = st.text_input("Enter Location for Weather:", value=st.session_state["user_city"])
    if user_location != st.session_state["user_city"]:
        st.session_state["user_city"] = user_location
        save_user_session()
        
    weather_info = get_weather(st.session_state["user_city"])
    st.markdown(weather_info)

    st.markdown("---")
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
        return "Please connect with a counselor, family member, or teacher
