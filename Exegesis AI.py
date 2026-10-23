import re
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta, date
import base64

# --- Page Configuration ---
st.set_page_config(
    page_title="Exegesis AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize Session State Variables ---
if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "Light"
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""
if "full_name" not in st.session_state:
    st.session_state["full_name"] = ""
if "account_type" not in st.session_state:
    st.session_state["account_type"] = "Student Portal"
if "parent_mode" not in st.session_state:
    st.session_state["parent_mode"] = ""
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "friends" not in st.session_state:
    st.session_state["friends"] = []
if "active_group_id" not in st.session_state:
    st.session_state["active_group_id"] = None
if "profile_pic" not in st.session_state:
    st.session_state["profile_pic"] = ""
if "user_city" not in st.session_state:
    st.session_state["user_city"] = "London"
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "Solo Study / AI Chat"
if "parent_verified" not in st.session_state:
    st.session_state["parent_verified"] = False
if "pending_prompt" not in st.session_state:
    st.session_state["pending_prompt"] = ""
if "show_full_settings" not in st.session_state:
    st.session_state["show_full_settings"] = False

# --- Dynamic High-Contrast CSS Engine ---
if st.session_state["theme_mode"] == "Dark":
    st.markdown("""
    <style>
        .stApp {
            background-color: #0b0f17;
            color: #f8fafc;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, .stMarkdown, div {
            color: #f8fafc !important;
        }
        .sub-text {
            color: #94a3b8 !important;
        }
        .feature-card {
            background-color: #121824;
            padding: 20px;
            border-radius: 16px;
            border: 1px solid #1f293d;
            height: 100%;
            margin-bottom: 15px;
        }
        .settings-card {
            background-color: #121824;
            padding: 30px;
            border-radius: 20px;
            border: 1px solid #1f293d;
            margin-bottom: 20px;
        }
        .stTextInput input, .stTextArea textarea, .stSelectbox div {
            background-color: #1e293b !important;
            color: #ffffff !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        .stTextInput input::placeholder {
            color: #94a3b8 !important;
        }
        .stButton>button {
            background-color: #3b82f6 !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 8px 16px !important;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .stApp {
            background-color: #f8fafc;
            color: #0f172a;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, .stMarkdown, div {
            color: #0f172a !important;
        }
        .sub-text {
            color: #64748b !important;
        }
        .feature-card {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.03);
            height: 100%;
            margin-bottom: 15px;
        }
        .settings-card {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 20px;
            border: 1px solid #e2e8f0;
            box-shadow: 0px 6px 18px rgba(0, 0, 0, 0.04);
            margin-bottom: 20px;
        }
        .stTextInput input, .stTextArea textarea, .stSelectbox div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }
        .stTextInput input::placeholder {
            color: #64748b !important;
        }
        .stButton>button {
            background-color: #2563eb !important;
            color: #ffffff !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 8px 16px !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- API Keys Verification ---
if "OPENROUTER_API_KEY" in st.secrets:
    FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    st.error("🔒 API Key Missing! Please add 'OPENROUTER_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- Firebase Connection Engine ---
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

# --- Helper Database Functions ---
def get_user_doc(username):
    doc_ref = db.collection("users").document(username)
    doc = doc_ref.get()
    return doc_ref, doc

def save_user_session():
    if st.session_state.get("logged_in") and st.session_state.get("user_name"):
        doc_ref = db.collection("users").document(st.session_state["user_name"])
        doc_ref.set({
            "full_name": st.session_state.get("full_name", ""),
            "messages": st.session_state.get("messages", []),
            "chat_history": st.session_state.get("chat_history", []),
            "friends": st.session_state.get("friends", []),
            "account_type": st.session_state.get("account_type", ""),
            "parent_mode": st.session_state.get("parent_mode", ""),
            "profile_pic": st.session_state.get("profile_pic", ""),
            "user_city": st.session_state.get("user_city", "London"),
            "theme_mode": st.session_state.get("theme_mode", "Light"),
            "last_active": datetime.now(timezone.utc).isoformat()
        }, merge=True)

# --- Weather Integration Function ---
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

# --- Master System Prompt ---
TUTOR_PROMPT = (
    "You are Exegesis AI, a supportive and friendly AI built for school students.\n"
    "1. For study questions or homework: Act as a helpful tutor using scaffolding. Never give the final answer right away. Provide up to 3 progressive hints to help the student learn.\n"
    "2. For general conversation or emotional support: Act like a warm, supportive friend. Listen, give encouragement, and keep the tone friendly and conversational.\n"
    "3. If tagged as @exegesis in group chats, help solve doubts step-by-step."
)

# --- Onboarding / Authentication View ---
if not st.session_state["logged_in"]:
    st.title("=== Welcome to Exegesis AI ===")
    auth_mode = st.radio("Choose Action", ["Log In", "Create Account"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entered_name = st.text_input("Username", placeholder="Enter your username")
        entered_pass = st.text_input("Password", type="password", placeholder="Enter your password")
        
        if auth_mode == "Create Account":
            entered_fullname = st.text_input("Full Name", placeholder="Enter your exact Full Name")
            birth_date = st.date_input("Birthdate", value=date(2010, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
            acc_choice = st.radio("Access Portal Role", ["Student Portal", "Teacher Portal", "School Account", "Parent Portal", "Personal Account"])
            
            school_name = ""
            if acc_choice == "School Account":
                school_name = st.text_input("School Name", placeholder="Enter school name")

            parent_sub = ""
            child_usernames_input = ""
            if acc_choice == "Parent Portal":
                parent_sub = st.radio("Parent Account Type", ["School Account Parent", "Personal Account Parent"])
                child_usernames_input = st.text_input("Child Username(s)", placeholder="Enter child username(s) separated by commas")

            if st.button("Register Account", use_container_width=True):
                clean_name = entered_name.strip()
                clean_fullname = entered_fullname.strip()
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

                if not clean_name or not entered_pass or not clean_fullname:
                    st.error("All fields including full name are required.")
                elif acc_choice == "Parent Portal" and not child_usernames_input.strip():
                    st.error("Parents must fill in at least one child's username to create an account.")
                else:
                    if acc_choice == "Parent Portal":
                        parsed_children = [c.strip() for c in child_usernames_input.split(",") if c.strip()]
                        valid_children = True
                        for c_user in parsed_children:
                            _, c_doc = get_user_doc(c_user)
                            if c_doc.exists:
                                c_data = c_doc.to_dict()
                                c_bday = c_data.get("birth_date")
                                if c_bday:
                                    c_bday_date = datetime.fromisoformat(c_bday).date()
                                    c_age = today.year - c_bday_date.year - ((today.month, today.day) < (c_bday_date.month, c_bday_date.day))
                                    if c_age >= 18:
                                        st.error(f"Cannot link parent to {c_user} because they are 18 or older.")
                                        valid_children = False
                            else:
                                st.warning(f"Child username '{c_user}' does not exist yet, but link will be saved.")
                        if not valid_children:
                            st.stop()

                    doc_ref, doc = get_user_doc(clean_name)
                    if doc.exists:
                        st.error("Username already exists.")
                    else:
                        new_data = {
                            "password": entered_pass,
                            "full_name": clean_fullname,
                            "birth_date": birth_date.isoformat(),
                            "age": age,
                            "messages": [],
                            "chat_history": [],
                            "friends": [],
                            "account_type": acc_choice,
                            "parent_mode": parent_sub,
                            "school_name": school_name,
                            "user_city": "London",
                            "profile_pic": "",
                            "theme_mode": "Light",
                            "admin_role": "super_admin" if clean_name == "MoltenSpy" else "user"
                        }
                        if acc_choice == "Parent Portal":
                            new_data["child_usernames"] = [c.strip() for c in child_usernames_input.split(",") if c.strip()]
                            new_data["verified_by_child"] = False

                        doc_ref.set(new_data)
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
                        st.session_state["parent_mode"] = user_data.get("parent_mode", "")
                        st.session_state["messages"] = user_data.get("messages", [])
                        st.session_state["chat_history"] = user_data.get("chat_history", [])
                        st.session_state["friends"] = user_data.get("friends", [])
                        st.session_state["user_city"] = user_data.get("user_city", "London")
                        st.session_state["profile_pic"] = user_data.get("profile_pic", "")
                        st.session_state["theme_mode"] = user_data.get("theme_mode", "Light")
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")
    st.stop()

user_name = st.session_state["user_name"]
user_role = st.session_state["account_type"]

# --- Birthday & 18th Birthday Monitoring ---
user_doc_ref, user_doc_snapshot = get_user_doc(user_name)
if user_doc_snapshot.exists:
    u_info = user_doc_snapshot.to_dict()
    bday_str = u_info.get("birth_date")
    if bday_str:
        bday_date = datetime.fromisoformat(bday_str).date()
        today_date = date.today()
        if bday_date.month == today_date.month and bday_date.day == today_date.day:
            st.balloons()
            st.success("🎉 Happy Birthday! Wishing you an amazing day!")
            
            current_age = today_date.year - bday_date.year
            if current_age == 18 and not u_info.get("turned_18_notified", False):
                parents = db.collection("users").where("account_type", "==", "Parent Portal").stream()
                for p in parents:
                    p_data = p.to_dict()
                    if user_name in p_data.get("child_usernames", []):
                        db.collection("parent_alerts").add({
                            "parent": p_data["full_name"],
                            "alert": f"Your child {st.session_state['full_name']} has turned 18 today!",
                            "time": datetime.now(timezone.utc).isoformat()
                        })
                user_doc_ref.set({"turned_18_notified": True}, merge=True)

# --- Admin Warnings System ---
warn_doc = db.collection("user_warnings").document(user_name).get()
if warn_doc.exists:
    w_data = warn_doc.to_dict()
    st.warning(f"⚠️ **ADMIN WARNING**: {w_data.get('message', 'Please do not use bad language or inappropriate text or your account might get suspended or banned.')}")
    if st.button("I Understand"):
        db.collection("user_warnings").document(user_name).delete()
        st.rerun()

# --- Account Suspension / Ban Handler ---
action_doc = db.collection("account_actions").document(user_name).get()
if action_doc.exists:
    action_data = action_doc.to_dict()
    status_type = action_data.get("type", "suspended").upper()
    reason = action_data.get("reason", "No reason provided.")
    
    st.title("🚫 Account Access Restricted")
    st.error(f"Your account has been **{status_type}**.")
    st.write(f"**Reason:** {reason}")
    if st.button("Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()
    st.stop()

# --- Student Portal Parent Verification Check ---
if user_role == "Student Portal" and not st.session_state["parent_verified"]:
    st.title(f"Hello {st.session_state['full_name']}!")
    st.subheader("🛡️ Parent Verification Check")
    verification = st.radio("Is the person who wrote your username your parent or not?", ["Select...", "Yes", "No"])
    if verification != "Select...":
        if verification == "Yes":
            st.session_state["parent_verified"] = True
            st.rerun()
        else:
            st.warning("Please ask a parent or guardian to verify before proceeding.")
    st.stop()

# --- Parent Linking Confirmations ---
if user_role == "Student Portal":
    parent_reqs = db.collection("users").where("child_usernames", "array_contains", user_name).where("verified_by_child", "==", False).stream()
    for req in parent_reqs:
        p_data = req.to_dict()
        st.title(f"Hello {st.session_state['full_name']}!")
        st.subheader("🛡️ Parent Link Request")
        st.write(f"**{p_data['full_name']}** wants to link to your account as your parent.")
        
        confirm = st.radio("Is this person really your parent?", ["Select...", "Yes", "No"], key=req.id)
        if confirm == "Yes":
            db.collection("users").document(req.id).update({"verified_by_child": True})
            st.success("Parent linked successfully!")
            st.rerun()
        elif confirm == "No":
            db.collection("users").document(req.id).delete()
            st.warning("Parent request declined. The parent account has been removed.")
            st.rerun()
        st.stop()

# --- Sidebar Workspace Navigation ---
with st.sidebar:
    st.title("📂 Workspace")
    st.session_state["app_mode"] = st.radio("Select Mode", ["Solo Study / AI Chat", "👥 Friends & Study Groups"])
    st.markdown("---")
    
    current_user_doc = user_doc_snapshot.to_dict() if user_doc_snapshot.exists else {}
    current_admin_role = current_user_doc.get("admin_role", "user")
    
    # Moderators & Admins Access
    if user_name == "MoltenSpy" or current_admin_role in ["admin", "super_admin"]:
        st.subheader("👑 Moderation Panel")
        reports = list(db.collection("violations").stream())
        if not reports:
            st.info("No violation reports right now!")
        else:
            for rep in reports:
                rep_data = rep.to_dict()
                u_target = rep_data.get("username", "Unknown")
                v_count = rep_data.get("count", 1)
                last_msg = rep_data.get("last_message", "")
                st.markdown(f"👤 **{u_target}** | **Violations:** {v_count}")
                st.caption(f"Last offense: \"{last_msg}\"")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("⚠️ Warn", key=f"warn_{rep.id}"):
                        db.collection("user_warnings").document(u_target).set({
                            "message": "You have been flagged for using bad language.",
                            "time": datetime.now(timezone.utc).isoformat()
                        })
                        st.success(f"Warning sent to {u_target}!")
                with c2:
                    if st.button("⏸️ Suspend", key=f"sus_{rep.id}"):
                        db.collection("account_actions").document(u_target).set({
                            "type": "suspended",
                            "reason": f"Repeated inappropriate language ({v_count} times).",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        st.success(f"Suspended {u_target}!")
                with c3:
                    if st.button("🚫 Ban", key=f"ban_{rep.id}"):
                        db.collection("account_actions").document(u_target).set({
                            "type": "banned",
                            "reason": f"Exceeded bad behavior limit ({v_count} violations).",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        st.success(f"Banned {u_target}!")
                st.markdown("---")

        # Exclusive Super Admin Controls
        if user_name == "MoltenSpy" or current_admin_role == "super_admin":
            st.subheader("⚙️ Super Admin Controls")
            target_user = st.text_input("Target Username", key="admin_target")
            action_type = st.selectbox("Action", ["Ban Account", "Suspend Account", "Unban / Remove Action", "Make Admin (Moderator)", "Make Super Admin", "Remove Admin Role"])
            action_reason = st.text_area("Reason", key="admin_reason")
            
            if st.button("Apply Super Action", use_container_width=True):
                clean_target = target_user.strip()
                if not clean_target:
                    st.error("Please enter a username.")
                else:
                    target_ref, target_snap = get_user_doc(clean_target)
                    if not target_snap.exists:
                        st.error("Target user does not exist.")
                    else:
                        if action_type == "Unban / Remove Action":
                            db.collection("account_actions").document(clean_target).delete()
                            st.success(f"Restrictions removed for {clean_target}.")
                        elif action_type == "Make Admin (Moderator)":
                            target_ref.set({"admin_role": "admin"}, merge=True)
                            st.success(f"{clean_target} is now an Admin (Moderator).")
                        elif action_type == "Make Super Admin":
                            if user_name == "MoltenSpy":
                                target_ref.set({"admin_role": "super_admin"}, merge=True)
                                st.success(f"{clean_target} is now a Super Admin.")
                            else:
                                st.error("Only MoltenSpy can appoint Super Admins.")
                        elif action_type == "Remove Admin Role":
                            target_ref.set({"admin_role": "user"}, merge=True)
                            st.success(f"Admin role removed for {clean_target}.")
                        else:
                            status_text = "banned" if action_type == "Ban Account" else "suspended"
                            db.collection("account_actions").document(clean_target).set({
                                "type": status_text,
                                "reason": action_reason.strip() if action_reason.strip() else "Violation of terms.",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            st.success(f"Account '{clean_target}' is now {status_text}.")
            st.markdown("---")

    if st.session_state["app_mode"] == "Solo Study / AI Chat":
        if st.button("➕ New Chat / Topic", use_container_width=True):
            if st.session_state["messages"]:
                chat_title = st.session_state["messages"][0]["content"][:25] + "..."
                st.session_state["chat_history"].append({
                    "title": chat_title,
                    "messages": st.session_state["messages"],
                    "time": datetime.now(timezone.utc).isoformat()
                })
            st.session_state["messages"] = []
            save_user_session()
            st.rerun()

        st.subheader("💬 Solo Chat History")
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

    elif st.session_state["app_mode"] == "👥 Friends & Study Groups":
        st.subheader("🟣 Group Chats")
        if st.session_state["active_group_id"]:
            if st.button("❌ Close Current Group", use_container_width=True):
                st.session_state["active_group_id"] = None
                st.rerun()
            st.markdown("---")

        groups_query = db.collection("groups").stream()
        for g in groups_query:
            g_data = g.to_dict()
            members = g_data.get("members", [])
            if user_name in members or g_data.get("creator") == st.session_state["full_name"]:
                if st.button(f"🟣 {g_data['name']}", key=f"sidebar_group_{g.id}", use_container_width=True):
                    st.session_state["active_group_id"] = g.id
                    st.rerun()

    st.markdown("---")
    st.subheader("🌤️ Weather Report")
    user_location = st.text_input("Location:", value=st.session_state["user_city"])
    if user_location != st.session_state["user_city"]:
        st.session_state["user_city"] = user_location
        save_user_session()
    st.markdown(get_weather(st.session_state["user_city"]))

    st.markdown("---")
    if st.button("Log out", use_container_width=True):
        save_user_session()
        st.session_state["logged_in"] = False
        st.rerun()

    st.markdown("---")
    st.subheader("⚠️ Danger Zone")
    confirm_del = st.checkbox("Confirm Account Deletion", key="del_acc_chk")
    if st.button("Delete My Account", use_container_width=True):
        if confirm_del:
            db.collection("users").document(user_name).delete()
            st.session_state["logged_in"] = False
            st.success("Account deleted successfully.")
            st.rerun()
        else:
            st.error("Please check the confirmation box first.")

# --- Automated Moderation Systems ---
def detect_harmful_keywords(text):
    harmful_keywords = ["kill", "suicide", "harm", "hurt", "violence", "weapon", "gun", "die", "unalive"]
    found = any(re.search(r'\b' + re.escape(w) + r'\b', text.lower()) for w in harmful_keywords)
    if found and user_role == "Personal Account":
        db.collection("parent_alerts").add({
            "child": st.session_state["full_name"],
            "alert": "Child expressed distressing thoughts.",
            "time": datetime.now(timezone.utc).isoformat()
        })
    return found

def detect_foul_language(text):
    foul_words = ["badword1", "badword2", "idiot", "stupid", "mother", "father", "parents", "trash", "hate"]
    found = any(re.search(r'\b' + re.escape(w) + r'\b', text.lower()) for w in foul_words)
    if found:
        v_doc = db.collection("violations").document(user_name).get()
        current_count = v_doc.to_dict().get("count", 0) + 1 if v_doc.exists else 1
        db.collection("violations").document(user_name).set({
            "username": user_name,
            "full_name": st.session_state["full_name"],
            "count": current_count,
            "last_message": text,
            "time": datetime.now(timezone.utc).isoformat()
        })
    return found

# =====================================================================
# PARENT PORTAL VIEW
# =====================================================================
if user_role == "Parent Portal":
    doc_ref, doc = get_user_doc(user_name)
    if doc.exists and not doc.to_dict().get("verified_by_child", True):
        st.title(f"Hello {st.session_state['full_name']} (Parent Dashboard)")
        st.warning("⏳ Waiting for your child to confirm your request.")
        if st.button("Log out"):
            st.session_state["logged_in"] = False
            st.rerun()
        st.stop()

    st.title(f"Hello {st.session_state['full_name']} (Parent Dashboard)")
    st.subheader("👶 Manage Children")
    current_data = doc.to_dict()
    children_list = current_data.get("child_usernames", [])
    st.write(f"Linked Children: {', '.join(children_list) if children_list else 'None'}")
    
    new_child_input = st.text_input("Add Another Child Username")
    if st.button("Add Child"):
        if new_child_input.strip():
            _, c_check = get_user_doc(new_child_input.strip())
            if c_check.exists:
                if new_child_input.strip() not in children_list:
                    children_list.append(new_child_input.strip())
                    doc_ref.set({"child_usernames": children_list}, merge=True)
                    st.success("Child added successfully!")
                    st.rerun()
                else:
                    st.warning("Child is already added.")
            else:
                st.error("Child username does not exist.")

    if st.session_state["parent_mode"] == "School Account Parent":
        st.subheader("🏫 School Account Monitoring")
        st.info("Here you can access your child's completed tasks and connect directly with teachers.")
        teacher_msg = st.text_area("Send direct message to teacher:")
        if st.button("Send to Teacher"):
            if teacher_msg.strip():
                db.collection("teacher_parent_messages").add({
                    "parent": st.session_state["full_name"],
                    "message": teacher_msg,
                    "time": datetime.now(timezone.utc).isoformat()
                })
                st.success("Message sent to teacher!")
    else:
        st.subheader("🏠 Personal Account Monitoring")
        st.info("AI Safety Monitoring & Activity Tracker")
        alerts = db.collection("parent_alerts").stream()
        st.markdown("### ⚠️ Child Activity & Safety Alerts")
        for alert in alerts:
            a_data = alert.to_dict()
            st.warning(f"**{a_data['parent']}** - {a_data['alert']} ({a_data['time']})")
    st.stop()

# =====================================================================
# TEACHER PORTAL VIEW
# =====================================================================
if user_role == "Teacher Portal":
    st.title(f"🍎 Teacher Dashboard ({st.session_state['full_name']})")
    t_tab1, t_tab2 = st.tabs(["📩 Parent Messages", "📋 Class Assignments"])
    with t_tab1:
        st.subheader("Messages from Parents")
        p_msgs = db.collection("teacher_parent_messages").stream()
        for pm in p_msgs:
            pm_data = pm.to_dict()
            st.info(f"**From:** {pm_data.get('parent', 'Parent')}\n\n**Message:** {pm_data.get('message')}")
    with t_tab2:
        st.subheader("Create Classroom Task")
        task_title = st.text_input("Task Title")
        task_desc = st.text_area("Task Instructions")
        if st.button("Assign Task"):
            if task_title.strip():
                db.collection("assignments").add({
                    "teacher": st.session_state["full_name"],
                    "title": task_title.strip(),
                    "instructions": task_desc.strip(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                st.success("Task assigned successfully!")
    st.stop()

# =====================================================================
# MODE 1: SOLO STUDY / AI CHAT
# =====================================================================
if st.session_state["app_mode"] == "Solo Study / AI Chat":
    c_head1, c_head2, c_head3 = st.columns([7, 1, 1])
    with c_head1:
        st.markdown(f"""
            <h1 style='margin:0; font-size: 28px;'>🎓 Exegesis <span style='color: #3b82f6;'>AI</span></h1>
            <p class='sub-text' style='margin-top:-5px;'>Your AI thinking companion</p>
        """, unsafe_allow_html=True)
    with c_head2:
        if st.button("📝", help="New Chat"):
            st.session_state["messages"] = []
            st.rerun()

    with c_head3:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state["show_full_settings"] = not st.session_state["show_full_settings"]
            st.rerun()

    # --- FULL SCREEN SETTINGS OVERLAY ---
    if st.session_state["show_full_settings"]:
        st.markdown("---")
        st.markdown("## ⚙️ Account & Application Settings")
        
        col_set1, col_set2 = st.columns(2)
        
        with col_set1:
            st.markdown("""
                <div class="settings-card">
                    <h3>👤 Profile Details</h3>
                </div>
            """, unsafe_allow_html=True)
            uploaded_profile = st.file_uploader("Upload New Profile Picture", type=["png", "jpg", "jpeg"], key="gear_full_profile_uploader")
            if uploaded_profile:
                pic_bytes = base64.b64encode(uploaded_profile.read()).decode("utf-8")
                st.session_state["profile_pic"] = f"data:image/png;base64,{pic_bytes}"
                save_user_session()
                st.success("Profile picture updated!")

            if st.session_state["profile_pic"]:
                st.image(st.session_state["profile_pic"], width=100)

            st.markdown("---")
            st.markdown("""
                <div class="settings-card">
                    <h3>🎨 Theme Appearance</h3>
                </div>
            """, unsafe_allow_html=True)
            selected_theme = st.radio("Display Mode", ["Light", "Dark"], index=0 if st.session_state["theme_mode"] == "Light" else 1, key="gear_full_theme_radio", horizontal=True)
            if selected_theme != st.session_state["theme_mode"]:
                st.session_state["theme_mode"] = selected_theme
                save_user_session()
                st.rerun()

        with col_set2:
            st.markdown("""
                <div class="settings-card">
                    <h3>🔒 Change Password</h3>
                </div>
            """, unsafe_allow_html=True)
            new_pass = st.text_input("New Password", type="password", key="gear_full_new_pass")
            confirm_pass = st.text_input("Confirm New Password", type="password", key="gear_full_conf_pass")
            if st.button("Update Password Now", use_container_width=True):
                if not new_pass or not confirm_pass:
                    st.error("Please enter a new password.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                else:
                    db.collection("users").document(user_name).update({"password": new_pass})
                    st.success("Password updated successfully!")

        st.markdown("---")
        if st.button("❌ Close Settings View", use_container_width=True):
            st.session_state["show_full_settings"] = False
            st.rerun()
        st.stop()

    st.markdown("---")

    if not st.session_state["messages"]:
        st.markdown("<h2 style='text-align: center; margin-top: 20px;'>What's on your mind?</h2>", unsafe_allow_html=True)
        st.markdown("<p class='sub-text' style='text-align: center;'>Let's understand it together.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
                <div class="feature-card">
                    <h3 style="color:#ec4899;">💖</h3>
                    <h4>Emotional Buddy</h4>
                    <p>Helps you feel heard, supported and calmer during tough times.</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Talk to Emotional Buddy", key="card1", use_container_width=True):
                st.session_state["pending_prompt"] = "I need some encouragement and emotional support today."
                st.rerun()

            st.markdown("""
                <div class="feature-card">
                    <h3 style="color:#f59e0b;">✨</h3>
                    <h4>What our ai offers</h4>
                    <p>Get all the features a free AI offers to its users.</p>
                    <p style="font-size:12px; margin-top:5px;" class="sub-text">• Makes it easy to understand step by step.</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("See AI Features", key="card3", use_container_width=True):
                st.session_state["pending_prompt"] = "What features can you help me with?"
                st.rerun()

        with col2:
            st.markdown("""
                <div class="feature-card">
                    <h3 style="color:#06b6d4;">💡</h3>
                    <h4>Explore ideas</h4>
                    <p>Discover new perspectives.</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Start Exploring", key="card2", use_container_width=True):
                st.session_state["pending_prompt"] = "Help me brainstorm some fresh perspectives on a problem."
                st.rerun()

            st.markdown("""
                <div class="feature-card">
                    <h3 style="color:#10b981;">🎓</h3>
                    <h4>Think deeply</h4>
                    <p>Helps you analyse, reflect and find better solutions.</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Think Deeply", key="card4", use_container_width=True):
                st.session_state["pending_prompt"] = "Can you help me analyze a topic step by step?"
                st.rerun()

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Message Exegesis AI...")
    if st.session_state["pending_prompt"]:
        user_input = st.session_state["pending_prompt"]
        st.session_state["pending_prompt"] = ""

    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        if detect_harmful_keywords(user_input):
            reply = "Please connect with a counselor, family member, or teacher right away to keep you safe."
            st.session_state["messages"].append({"role": "assistant", "content": reply})
            save_user_session()
            st.rerun()

        chat_context = [{"role": "system", "content": TUTOR_PROMPT}] + st.session_state["messages"]
        try:
            resp = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {FULL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct",
                    "messages": chat_context
                },
                timeout=20
            )
            response_json = resp.json()
            if "choices" in response_json and len(response_json["choices"]) > 0:
                ai_reply = response_json["choices"][0]["message"]["content"].strip()
            else:
                ai_reply = f"⚠️ Unable to generate a response. Details: {response_json.get('error', 'Unknown error')}"
        except Exception as e:
            ai_reply = f"⚠️ Connection error: {e}"

        st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
        save_user_session()
        st.rerun()

# =====================================================================
# MODE 2: FRIENDS & STUDY GROUPS
# =====================================================================
elif st.session_state["app_mode"] == "👥 Friends & Study Groups":
    st.title(f"Hello {st.session_state['full_name']}! 👥 Friends & Study Groups")
    tab1, tab2, tab3 = st.tabs(["Friend Requests", "Create Group Chat", "Active Group Chat Room"])
    
    with tab1:
        st.subheader("Add Friend (Requires Full Name)")
        target_fullname = st.text_input("Enter Peer's Exact Full Name")
        if st.button("Send Friend Request"):
            if target_fullname.strip() == "":
                st.error("Please enter a valid full name.")
            else:
                db.collection("friend_requests").add({
                    "from_user": user_name,
                    "from_fullname": st.session_state["full_name"],
                    "to_fullname": target_fullname.strip(),
                    "status": "pending"
                })
                st.success("Friend request sent!")

        st.subheader("Your Friends")
        accepted_reqs = db.collection("friend_requests").where("status", "==", "accepted").stream()
        friend_cols = st.columns(4)
        idx = 0
        for r in accepted_reqs:
            r_data = r.to_dict()
            if r_data["from_fullname"] == st.session_state["full_name"] or r_data["to_fullname"] == st.session_state["full_name"]:
                friend_name = r_data["to_fullname"] if r_data["from_fullname"] == st.session_state["full_name"] else r_data["from_fullname"]
                with friend_cols[idx % 4]:
                    st.markdown(f"👤 **{friend_name}**")
                    confirm_unfriend = st.checkbox(f"Confirm Unfriend {friend_name}", key=f"chk_unfriend_{r.id}")
                    if st.button(f"Unfriend {friend_name}", key=f"unfriend_btn_{r.id}"):
                        if confirm_unfriend:
                            db.collection("friend_requests").document(r.id).delete()
                            st.success(f"Unfriended {friend_name}.")
                            st.rerun()
                        else:
                            st.error("Please check the confirmation box first.")
                idx += 1

        st.subheader("Pending Requests")
        reqs = db.collection("friend_requests").where("to_fullname", "==", st.session_state["full_name"]).where("status", "==", "pending").stream()
        for r in reqs:
            r_data = r.to_dict()
            st.write(f"Request from: **{r_data['from_fullname']}**")
            if st.button("Accept", key=r.id):
                db.collection("friend_requests").document(r.id).update({"status": "accepted"})
                st.success("Friend added!")
                st.rerun()

    with tab2:
        st.subheader("Create a New Study Group")
        new_group_name = st.text_input("Group Name")
        members_input = st.text_input("Member Full Names (separate with commas)")
        if st.button("Create Group"):
            if not new_group_name.strip():
                st.error("Please provide a group name.")
            else:
                parsed_members = [m.strip() for m in members_input.split(",") if m.strip()]
                if st.session_state["full_name"] not in parsed_members:
                    parsed_members.append(st.session_state["full_name"])
                db.collection("groups").add({
                    "name": new_group_name.strip(),
                    "members": parsed_members,
                    "creator": st.session_state["full_name"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                st.success(f"Group '{new_group_name}' created successfully!")
                st.rerun()

    with tab3:
        st.subheader("Study Room Chat (Tag @exegesis for help)")
        all_groups = list(db.collection("groups").stream())
        group_options = {g.id: g.to_dict()["name"] for g in all_groups}
        
        if not group_options:
            st.info("No groups created yet. Go to 'Create Group Chat' tab to start one!")
        else:
            selected_gid = st.selectbox(
                "Select Group Chat",
                options=list(group_options.keys()),
                format_func=lambda x: f"🟣 {group_options[x]}",
                index=list(group_options.keys()).index(st.session_state["active_group_id"]) if st.session_state["active_group_id"] in group_options else 0
            )
            st.session_state["active_group_id"] = selected_gid
            
            room_msgs = db.collection("groups").document(selected_gid).collection("messages").order_by("time").stream()
            for msg in room_msgs:
                m = msg.to_dict()
                is_me = (m['sender'] == st.session_state["full_name"])
                chat_role = "user" if is_me else "assistant"
                with st.chat_message(chat_role):
                    st.markdown(f"**{m['sender']}**: {m['text']}")
            
            group_input = st.chat_input("Message group...", key="group_chat_input_box")
            if group_input:
                if detect_foul_language(group_input):
                    st.error("⚠️ Bad language detected and logged to Admin Panel!")

                db.collection("groups").document(selected_gid).collection("messages").add({
                    "sender": st.session_state["full_name"],
                    "text": group_input,
                    "time": datetime.now(timezone.utc).isoformat()
                })
                if "@exegesis" in group_input.lower():
                    try:
                        resp = requests.post(
                            url="https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {FULL_API_KEY}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "meta-llama/llama-3.1-8b-instruct",
                                "messages": [
                                    {"role": "system", "content": TUTOR_PROMPT},
                                    {"role": "user", "content": group_input}
                                ]
                            },
                            timeout=20
                        )
                        g_resp_json = resp.json()
                        ai_help = g_resp_json["choices"][0]["message"]["content"].strip() if "choices" in g_resp_json else "Error"
                        db.collection("groups").document(selected_gid).collection("messages").add({
                            "sender": "Exegesis AI 🤖",
                            "text": ai_help,
                            "time": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception:
                        pass
                st.rerun()
