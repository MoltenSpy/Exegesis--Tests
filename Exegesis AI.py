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
            "parent_mode": st.session_state.get("parent_mode", ""),
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

# --- Initialize Session States ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user_name" not in st.session_state: st.session_state["user_name"] = ""
if "full_name" not in st.session_state: st.session_state["full_name"] = ""
if "account_type" not in st.session_state: st.session_state["account_type"] = "Student Portal"
if "parent_mode" not in st.session_state: st.session_state["parent_mode"] = ""
if "messages" not in st.session_state: st.session_state["messages"] = []
if "chat_history" not in st.session_state: st.session_state["chat_history"] = []
if "friends" not in st.session_state: st.session_state["friends"] = []
if "active_group_id" not in st.session_state: st.session_state["active_group_id"] = None
if "profile_pic" not in st.session_state: st.session_state["profile_pic"] = ""
if "user_city" not in st.session_state: st.session_state["user_city"] = "London"
if "app_mode" not in st.session_state: st.session_state["app_mode"] = "Solo Study / AI Chat"
if "parent_verified" not in st.session_state: st.session_state["parent_verified"] = False

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
            acc_choice = st.radio("Access Portal Role", ["Student Portal", "Teacher Portal", "Principal Control Panel", "Parent Portal", "Personal Account"])
            
            parent_sub = ""
            if acc_choice == "Parent Portal":
                parent_sub = st.radio("Parent Account Type", ["School Account Parent", "Personal Account Parent"])

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
                            "parent_mode": parent_sub,
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
                        st.session_state["parent_mode"] = user_data.get("parent_mode", "")
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

# --- Student Account Parent Verification Check ---
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

# --- Sidebar Navigation ---
with st.sidebar:
    st.title("📂 Workspace")
    
    st.session_state["app_mode"] = st.radio("Select Mode", ["Solo Study / AI Chat", "👥 Friends & Study Groups"])
    
    st.markdown("---")
    
    # --- Profile Picture Section ---
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
        st.markdown("---")

    # Group Chats Sidebar History
    st.subheader("🟣 Group Chat History")
    groups_query = db.collection("groups").stream()
    for g in groups_query:
        g_data = g.to_dict()
        members = g_data.get("members", [])
        
        # Check if current user is the creator or a member
        if user_name in members or g_data.get("creator") == st.session_state["full_name"]:
            if st.button(f"🟣 {g_data['name']}", key=f"sidebar_group_{g.id}", use_container_width=True):
                st.session_state["active_group_id"] = g.id
                st.session_state["app_mode"] = "👥 Friends & Study Groups"
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
        st.session_state["parent_verified"] = False
        st.rerun()

# --- Security & Foul Language Checkers ---
def detect_harmful_keywords(text):
    harmful_keywords = ["kill", "suicide", "harm", "hurt", "violence", "weapon", "gun", "die", "unalive"]
    found = any(re.search(r'\b' + re.escape(w) + r'\b', text.lower()) for w in harmful_keywords)
    if found and user_role == "Personal Account":
        db.collection("parent_alerts").add({
            "child": st.session_state["full_name"],
            "alert": "Child expressed distressing or harmful thoughts.",
            "time": datetime.now(timezone.utc).isoformat()
        })
    return found

def detect_foul_language(text):
    foul_words = ["badword1", "badword2", "idiot", "stupid"]
    return any(re.search(r'\b' + re.escape(w) + r'\b', text.lower()) for w in foul_words)

def check_chat_suspension():
    sus_ref = db.collection("suspensions").document(user_name)
    sus_doc = sus_ref.get()
    if sus_doc.exists:
        sus_data = sus_doc.to_dict()
        expiry_time = datetime.fromisoformat(sus_data["expires_at"])
        if datetime.now(timezone.utc) < expiry_time:
            return True
        else:
            sus_ref.delete()
    return False

# =====================================================================
# PARENT PORTAL VIEW
# =====================================================================
if user_role == "Parent Portal":
    st.title(f"Hello {st.session_state['full_name']} (Parent Dashboard)")
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
            st.warning(f"**{a_data['child']}** - {a_data['alert']} ({a_data['time']})")
        st.markdown("### 💡 Ways to Console Your Child")
        st.markdown("- Listen actively and without judgment.\n- Reassure them of your unconditional support.\n- Connect with professional counseling or guidance if needed.")
    st.stop()

# =====================================================================
# MODE 1: SOLO STUDY / AI CHAT
# =====================================================================
if st.session_state["app_mode"] == "Solo Study / AI Chat":
    st.title(f"Hello {st.session_state['full_name']}!")
    st.subheader("What's on your mind today?")
    
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask a study question...")

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
                    "model": "meta-llama/llama-3.2-3b-instruct:free",
                    "messages": chat_context
                },
                timeout=20
            )
            ai_reply = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            ai_reply = f"⚠️ Sync error: {e}"

        st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
        save_user_session()
        st.rerun()

# =====================================================================
# MODE 2: FRIENDS & STUDY GROUPS WITH @exegesis
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
        members_input = st.text_input("Member Usernames (separate with commas)", placeholder="e.g. john123, alex_99")
        uploaded_group_pic = st.file_uploader("Group Profile Picture", type=["png", "jpg", "jpeg"], key="group_pic_upload")
        
        if st.button("Create Group"):
            if not new_group_name.strip():
                st.error("Please provide a group name.")
            else:
                pic_data = ""
                if uploaded_group_pic:
                    pic_data = f"data:image/png;base64,{base64.b64encode(uploaded_group_pic.read()).decode('utf-8')}"
                
                # Parse member usernames list and include creator
                parsed_members = [m.strip() for m in members_input.split(",") if m.strip()]
                if user_name not in parsed_members:
                    parsed_members.append(user_name)
                
                group_ref = db.collection("groups").add({
                    "name": new_group_name.strip(),
                    "members": parsed_members,
                    "creator": st.session_state["full_name"],
                    "profile_pic": pic_data,
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
            
            g_doc = db.collection("groups").document(selected_gid).get()
            if g_doc.exists:
                g_info = g_doc.to_dict()
                if g_info.get("profile_pic"):
                    st.image(g_info["profile_pic"], width=60)
            
            if check_chat_suspension():
                st.error("🚫 Your chat access is suspended for 1 day due to foul language violations.")
                st.stop()
                
            room_msgs = db.collection("groups").document(selected_gid).collection("messages").order_by("time").stream()
            for msg in room_msgs:
                m = msg.to_dict()
                st.markdown(f"**{m['sender']}**: {m['text']}")
                
            group_input = st.text_input("Message group...", key="group_chat_input_box")
            if st.button("Send Message", key="send_group_btn"):
                if group_input.strip():
                    if detect_foul_language(group_input):
                        sus_until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                        db.collection("suspensions").document(user_name).set({"expires_at": sus_until})
                        st.error("⚠️ Foul language detected! Your chat is suspended for 1 day.")
                        st.rerun()
                        
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
                                    "model": "meta-llama/llama-3.2-3b-instruct:free",
                                    "messages": [
                                        {"role": "system", "content": TUTOR_PROMPT},
                                        {"role": "user", "content": group_input}
                                    ]
                                },
                                timeout=20
                            )
                            ai_help = resp.json()["choices"][0]["message"]["content"].strip()
                            db.collection("groups").document(selected_gid).collection("messages").add({
                                "sender": "Exegesis AI 🤖",
                                "text": ai_help,
                                "time": datetime.now(timezone.utc).isoformat()
                            })
                        except Exception:
                            pass
                    st.rerun()
