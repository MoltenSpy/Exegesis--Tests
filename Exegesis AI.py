# =====================================================================
# EXEGESIS AI - IITB SPARKX COMPETITION EDITION
# Comprehensive Student-Centric AI Tutoring & Moderation Platform
# =====================================================================

import re
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta, date
import base64
import json
import streamlit.components.v1 as components

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Exegesis AI - Advanced Student Platform",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================================
# SECTION 1: SECURE API SECRETS & CONFIGURATION
# =====================================================================
if "OPENROUTER_API_KEY" in st.secrets:
    FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    st.error("🔒 API Key Missing! Please add 'OPENROUTER_API_KEY' to your Streamlit Secrets configuration dashboard.")
    st.stop()


# =====================================================================
# SECTION 2: FIREBASE CLOUD DATABASE CONNECTION
# =====================================================================
@st.cache_resource
def init_firebase():
    """Initializes and returns the Firestore client securely using Streamlit Secrets."""
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()


try:
    db = init_firebase()
except Exception as e:
    # Keep secrets and credential contents out of the browser-facing error.
    st.error("⚠️ Exegesis AI could not connect to its database. Please check the Firebase configuration in Streamlit Secrets and the deployment logs.")
    st.caption(f"Error type: {type(e).__name__}. No secret values are displayed.")
    st.stop()


# =====================================================================
# SECTION 3: CORE DATABASE & SESSION UTILITY FUNCTIONS
# =====================================================================
def get_user_doc(username):
    """Retrieves a user document reference and snapshot from Firestore."""
    doc_ref = db.collection("users").document(username)
    doc = doc_ref.get()
    return doc_ref, doc


def normalize_school_value(value):
    """Normalize school identifiers for consistent matching across accounts."""
    return " ".join(str(value or "").strip().casefold().split())


def find_school_account(school_name, school_location=""):
    """Find a registered School Account by name and, when supplied, location."""
    wanted_name = normalize_school_value(school_name)
    wanted_location = normalize_school_value(school_location)
    if not wanted_name:
        return None, False
    same_name_found = False
    for snap in db.collection("users").where("account_type", "==", "School Account").stream():
        data = snap.to_dict() or {}
        if normalize_school_value(data.get("school_name")) == wanted_name:
            same_name_found = True
            if wanted_location and normalize_school_value(data.get("school_location")) == wanted_location:
                return data, True
    return None, same_name_found


def get_class_records(collection_name, school_name, school_location, grade, section):
    """Fetch class items and filter consistently without requiring composite indexes."""
    wanted = (
        normalize_school_value(school_name),
        normalize_school_value(school_location),
        normalize_school_value(grade),
        normalize_school_value(section),
    )
    results = []
    for snap in db.collection(collection_name).stream():
        item = snap.to_dict() or {}
        key = (
            normalize_school_value(item.get("school_name")),
            normalize_school_value(item.get("school_location")),
            normalize_school_value(item.get("grade")),
            normalize_school_value(item.get("section")),
        )
        if key == wanted:
            item["id"] = snap.id
            results.append(item)
    results.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return results


def save_user_session():
    """Persists current user profile data and active session state to Firestore safely."""
    if st.session_state.get("logged_in") and st.session_state.get("user_name"):
        try:
            doc_ref = db.collection("users").document(st.session_state["user_name"])
            doc_ref.set({
                "full_name": st.session_state.get("full_name", ""),
                "messages": st.session_state.get("messages", []),
                "chat_history": st.session_state.get("chat_history", []),
                "friends": st.session_state.get("friends", []),
                "nicknames": st.session_state.get("nicknames", {}),
                "account_type": st.session_state.get("account_type", ""),
                "parent_mode": st.session_state.get("parent_mode", ""),
                "profile_pic": st.session_state.get("profile_pic", ""),
                "user_city": st.session_state.get("user_city", "London"),
                "tutor_prompt": st.session_state.get("tutor_prompt", TUTOR_PROMPT),
                "grade": st.session_state.get("grade", ""),
                "section": st.session_state.get("section", ""),
                "school_name": st.session_state.get("school_name", ""),
                "school_location": st.session_state.get("school_location", ""),
                "last_active": datetime.now(timezone.utc).isoformat()
            }, merge=True)
        except Exception as e:
            st.warning(f"Could not save your session: {e}")


# =====================================================================
# SECTION 4: WEATHER API INTEGRATION
# =====================================================================
def get_weather(city_name):
    """Fetches live weather information for the sidebar widget."""
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


# =====================================================================
# SECTION 5: AI SYSTEM PROMPTS & SCAFFOLDING GUIDELINES
# =====================================================================
TUTOR_PROMPT = (
    "You are Exegesis AI, a supportive and friendly AI built for school students.\n"
    "1. Do not claim to generate finished work on the student's behalf. When asked to generate something, say: 'I cannot generate it for you, but I will help you write it and guide you through doing it.' Then give practical, step-by-step help, ideas, outlines, examples, and feedback so the student can create their own work.\n"
    "2. When reviewing uploaded images, videos, documents, Word files, or presentations, observe everything visible and detail what you notice.\n"
    "3. For general conversation or emotional support: Act like a warm, supportive friend.\n"
    "4. If tagged as @exegesis in group chats, help solve doubts step-by-step with guidance rather than full answers.\n"
    "5. Never disclose private creator information.\n"
    "6. For creative classroom tasks such as SST skits, roleplays, debates, speeches, and presentations, do not simply produce a finished submission. Help the student plan and write it themselves with a clear structure, character ideas, dialogue suggestions, stage-direction ideas, and step-by-step guidance. Ask only for details that are essential. Never answer with 'None' or an empty response.\n"
    "7. If a request is broad, suggest a useful starting structure and explain how the student can develop it; offer to review or improve the student's own draft.\n"
    "8. HINT-FIRST MODE FOR STUDY QUESTIONS ONLY: When the student asks a schoolwork, homework, quiz, exam-practice, or learning question that tests a concept, definition, explanation, or a problem-solving skill, do not immediately reveal the answer. Give exactly ONE useful hint, then ask the student to try. Wait for the student's next message before giving another hint. If the attempt is incorrect, incomplete, or the student says they do not know, give Hint 2 only, then wait. After another unsuccessful attempt, give Hint 3 only, then wait for one final attempt. Each hint must become more helpful but must NOT contain the answer, spell it out, give its initials, or directly reveal it. Never give all three hints in one message. If the student answers correctly at any stage, acknowledge that and explain briefly why it is correct. After the third hint and the student's final attempt (or if the student explicitly asks to reveal the answer), explain the underlying concept in simple, grade-appropriate language FIRST; only after that explanation, state the correct answer clearly and explain why it is correct. Track which hint number has already been given in the conversation and do not restart at Hint 1 for the same question. Start a fresh hint sequence for a genuinely new study question.\n"
    "9. DO NOT USE HINT-FIRST MODE for ordinary factual lookups or quick-reference questions that ask for a specific fact, quantity, measurement, distance, time, date, location, conversion, or current information. Answer these directly and clearly. For example, if asked 'What is the distance from Earth to the Moon?', provide the approximate distance directly rather than giving hints. Do not turn every question into a quiz. If it is unclear whether the student wants tutoring or a direct fact, prefer answering a straightforward factual lookup directly.\n"
    "10. The hint-first rule applies in both solo chats and group chats when responding to a student. Safety-critical or urgent questions must always receive necessary information immediately, without a hint sequence.\n"
    "11. Never mention, display, or summarize how many hints have been used. Do not include a hint-count label or status line; simply give the next hint or explanation naturally."
)



def get_active_tutor_prompt():
    """Return the signed-in user's editable tutor instructions."""
    return st.session_state.get("tutor_prompt", TUTOR_PROMPT)


def render_answer_actions(answer_text, key="ai_answer"):
    """Compact icon-only Copy and Listen controls with hover tooltips."""
    safe_text = json.dumps(str(answer_text or ""), ensure_ascii=False)
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", str(key))
    theme = str(st.get_option("theme.base") or "light").lower()
    dark = theme == "dark"
    bg = "#252a34" if dark else "#ffffff"
    fg = "#f3f4f6" if dark else "#202938"
    border = "#596273" if dark else "#cbd5e1"
    hover = "#343b49" if dark else "#f1f5f9"
    status = "#cbd5e1" if dark else "#475569"

    html = rf"""
    <div id="actions_{safe_key}" style="display:flex;align-items:center;gap:6px;
         margin:5px 0 10px;font-family:Arial,sans-serif;">
      <button id="speak_{safe_key}" type="button" title="Listen to answer" aria-label="Listen to answer"
        style="width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;
        background:{bg};color:{fg};border:1px solid {border};border-radius:10px;font-size:17px;cursor:pointer;">🔊</button>
      <button id="copy_{safe_key}" type="button" title="Copy answer" aria-label="Copy answer"
        style="width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;
        background:{bg};color:{fg};border:1px solid {border};border-radius:10px;font-size:18px;cursor:pointer;">⧉</button>
      <span id="status_{safe_key}" role="status" aria-live="polite"
        style="font-size:12px;color:{status};"></span>
    </div>
    <script>
    (() => {{
      const raw = {safe_text};
      const clean = (value) => {{
        let t = String(value ?? '');
        t = t.replace(/^\s*```[^\n]*\n?/gm, '').replace(/^\s*```\s*$/gm, '');
        t = t.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
        t = t.replace(/<[^>]*>/g, '').replace(/^\s{0,3}#{1,6}\s+/gm, '').replace(/^\s*>\s?/gm, '');
        t = t.replace(/^\s*[-+]\s+/gm, '• ').replace(/\*{{2,3}}([^*]+?)\*{{2,3}}/g, '$1');
        t = t.replace(/_{{2,3}}([^_]+?)_{{2,3}}/g, '$1').replace(/\*{{2,}}/g, '').replace(/_{{2,}}/g, '');
        t = t.replace(/~~([^~]+?)~~/g, '$1').replace(/`([^`]+)`/g, '$1');
        return t.replace(/\n{{3,}}/g, '\n\n').trim();
      }};
      const plain = clean(raw);
      // Remove pictographs and emoji presentation sequences from spoken output only.
      const spoken = Array.from(plain).filter(ch => {{ const cp = ch.codePointAt(0); return !((cp >= 0x1F000 && cp <= 0x1FAFF) || (cp >= 0x2600 && cp <= 0x27BF) || cp === 0xFE0F || cp === 0xFE0E || cp === 0x200D); }}).join('').replace(/\s+/g, ' ').trim();
      const speak = document.getElementById("speak_{safe_key}");
      const copy = document.getElementById("copy_{safe_key}");
      const statusEl = document.getElementById("status_{safe_key}");
      [speak, copy].forEach(btn => {{
        btn.addEventListener('mouseenter', () => btn.style.background = '{hover}');
        btn.addEventListener('mouseleave', () => btn.style.background = '{bg}');
        btn.addEventListener('focus', () => btn.style.outline = '2px solid #60a5fa');
        btn.addEventListener('blur', () => btn.style.outline = 'none');
      }});
      speak.addEventListener('click', () => {{
        if (!('speechSynthesis' in window)) {{ statusEl.textContent = 'Speech is not supported in this browser.'; return; }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(spoken);
        utterance.rate = 0.96; utterance.pitch = 1.04;
        utterance.onstart = () => statusEl.textContent = 'Speaking…';
        utterance.onend = () => statusEl.textContent = '';
        utterance.onerror = () => statusEl.textContent = 'Could not play audio.';
        window.speechSynthesis.speak(utterance);
      }});
      copy.addEventListener('click', async () => {{
        try {{
          if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(plain);
          else {{
            const area = document.createElement('textarea'); area.value = plain; area.setAttribute('readonly', '');
            area.style.position = 'fixed'; area.style.left = '-9999px'; document.body.appendChild(area);
            area.select(); const ok = document.execCommand('copy'); area.remove(); if (!ok) throw new Error('Copy failed');
          }}
          statusEl.textContent = 'Copied';
        }} catch (e) {{ statusEl.textContent = 'Could not copy automatically.'; }}
      }});
    }})();
    </script>
    """
    components.html(html, height=48, scrolling=False)


# =====================================================================
# SECTION 6: SESSION STATE INITIALIZATION
# =====================================================================
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
if "nicknames" not in st.session_state:
    st.session_state["nicknames"] = {}
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
if "tutor_prompt" not in st.session_state:
    st.session_state["tutor_prompt"] = TUTOR_PROMPT
if "editing_user_prompt" not in st.session_state:
    st.session_state["editing_user_prompt"] = None


# =====================================================================
# SECTION 7: LOGIN & REGISTRATION
# =====================================================================
def _attempt_login(username, password):
    """Validate credentials and populate the logged-in session."""
    clean_name = str(username or "").strip()
    if not clean_name or not password:
        st.error("Please enter both your username and password.")
        return False

    doc_ref, doc = get_user_doc(clean_name)
    if not doc.exists:
        st.error("Invalid username or password.")
        return False

    user_data = doc.to_dict()
    if user_data.get("password") != password:
        st.error("Invalid username or password.")
        return False

    st.session_state["user_name"] = clean_name
    st.session_state["full_name"] = user_data.get("full_name", clean_name)
    stored_role = user_data.get("account_type", "Student Portal")
    if stored_role in ["Principal Account", "Principal Portal"]:
        stored_role = "School Account"
    st.session_state["account_type"] = stored_role
    st.session_state["parent_mode"] = user_data.get("parent_mode", "")
    st.session_state["parent_verified"] = user_data.get("parent_verified", False)
    st.session_state["grade"] = user_data.get("grade", "")
    st.session_state["section"] = user_data.get("section", "")
    st.session_state["school_name"] = user_data.get("school_name", "")
    st.session_state["school_location"] = user_data.get("school_location", "")

    existing_msgs = user_data.get("messages", [])
    existing_history = user_data.get("chat_history", [])
    if existing_msgs:
        chat_title = existing_msgs[0].get("content", "New chat")[:25] + "..."
        existing_history.append({
            "title": chat_title,
            "messages": existing_msgs,
            "time": datetime.now(timezone.utc).isoformat()
        })

    st.session_state["messages"] = []
    st.session_state["chat_history"] = existing_history
    st.session_state["friends"] = user_data.get("friends", [])
    st.session_state["nicknames"] = user_data.get("nicknames", {})
    st.session_state["user_city"] = user_data.get("user_city", "London")
    st.session_state["tutor_prompt"] = user_data.get("tutor_prompt", TUTOR_PROMPT)
    st.session_state["profile_pic"] = user_data.get("profile_pic", "")
    st.session_state["logged_in"] = True
    save_user_session()
    return True


def _login_on_password_enter():
    """Log in when Enter is pressed in the password field."""
    if st.session_state.get("auth_mode_choice") != "Log In":
        return
    if _attempt_login(
        st.session_state.get("login_username", ""),
        st.session_state.get("login_password", "")
    ):
        st.session_state["login_enter_succeeded"] = True


def render_auth_screen():
    st.title("=== Welcome to Exegesis AI ===")
    auth_mode = st.radio(
        "Choose Action",
        ["Log In", "Create Account"],
        horizontal=True,
        key="auth_mode_choice"
    )

    col1, col2 = st.columns(2)

    with col1:
        entered_name = st.text_input(
            "Username",
            placeholder="Enter your username",
            key="login_username"
        )

        username_taken = False

        if auth_mode == "Create Account" and entered_name.strip():
            _, check_snap = get_user_doc(entered_name.strip())
            if check_snap.exists:
                username_taken = True
                st.warning("⚠️ This username is already taken.")

        entered_pass = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            key="login_password",
            on_change=(
                _login_on_password_enter
                if auth_mode == "Log In" else None
            )
        )

        if auth_mode == "Create Account":
            entered_fullname = st.text_input(
                "Full Name",
                placeholder="Enter your exact Full Name"
            )

            birth_date = st.date_input(
                "Birthdate",
                value=date(2010, 1, 1),
                min_value=date(1920, 1, 1),
                max_value=date.today()
            )

            acc_choice = st.radio(
                "Access Portal Role",
                [
                    "Student Portal",
                    "Teacher Portal",
                    "School Account",
                    "Parent Portal",
                    "Personal Account"
                ]
            )

            school_name = ""
            school_location = ""
            student_grade = ""
            student_section = ""
            if acc_choice in ["Student Portal", "Teacher Portal", "School Account"]:
                school_name = st.text_input("School Name", key="register_school_name")
                school_location = st.text_input(
                    "School Location (City / Area)",
                    key="register_school_location",
                    help="Enter the city or area where the school is located."
                )
            if acc_choice == "Student Portal":
                student_grade = st.selectbox(
                    "Your Grade", [f"Grade {n}" for n in range(1, 13)],
                    key="register_student_grade"
                )
                student_section = st.text_input(
                    "Your Section", placeholder="e.g. A", key="register_student_section"
                )

            parent_sub = ""
            child_usernames_input = ""

            if acc_choice == "Parent Portal":
                parent_sub = st.radio(
                    "Parent Account Type",
                    ["School Account Parent", "Personal Account Parent"]
                )
                child_usernames_input = st.text_input(
                    "Child Username(s)",
                    placeholder="Separate usernames with commas"
                )

            if st.button("Register Account", use_container_width=True):
                clean_name = entered_name.strip()
                clean_fullname = entered_fullname.strip()

                today = date.today()
                age = today.year - birth_date.year - (
                    (today.month, today.day) <
                    (birth_date.month, birth_date.day)
                )

                if not clean_name or not entered_pass or not clean_fullname:
                    st.error("All fields are required.")

                elif username_taken:
                    st.error("This username is already taken.")

                elif acc_choice in ["Student Portal", "Teacher Portal", "School Account"] and not school_name.strip():
                    st.error("Please enter your school name.")

                elif acc_choice in ["Student Portal", "Teacher Portal", "School Account"] and not school_location.strip():
                    st.error("Please enter the school location. A school name alone is not enough to identify the correct school.")

                elif acc_choice == "Student Portal" and not student_section.strip():
                    st.error("Please enter your class section.")

                elif (
                    acc_choice == "Parent Portal"
                    and not child_usernames_input.strip()
                ):
                    st.error("Please enter at least one child's username.")

                else:
                    if acc_choice == "School Account":
                        matched_school, same_name_found = find_school_account(school_name, school_location)
                        if matched_school:
                            st.error("This school is already registered with that location. Please log in to its existing School Account.")
                            st.stop()
                        # A matching name without a location is intentionally not accepted;
                        # the required location above distinguishes schools/campuses.
                    if acc_choice in ["Student Portal", "Teacher Portal"]:
                        registered_school, same_name_found = find_school_account(school_name, school_location)
                        if not registered_school:
                            if same_name_found:
                                st.error("A school with this name is registered, but its location does not match. Check the location with your school administrator.")
                            else:
                                st.error("This school is not registered yet. Ask your school to create a School Account first.")
                            st.stop()
                    if acc_choice == "Parent Portal":
                        parsed_children = [
                            c.strip()
                            for c in child_usernames_input.split(",")
                            if c.strip()
                        ]

                        valid_children = True

                        for c_user in parsed_children:
                            _, c_doc = get_user_doc(c_user)

                            if c_doc.exists:
                                c_data = c_doc.to_dict()
                                c_bday = c_data.get("birth_date")

                                if c_bday:
                                    c_bday_date = datetime.fromisoformat(
                                        c_bday
                                    ).date()

                                    c_age = today.year - c_bday_date.year - (
                                        (today.month, today.day) <
                                        (c_bday_date.month, c_bday_date.day)
                                    )

                                    if c_age >= 18:
                                        st.error(
                                            f"Cannot link parent to {c_user} "
                                            "because they are 18 or older."
                                        )
                                        valid_children = False
                            else:
                                st.warning(
                                    f"Child username '{c_user}' does not "
                                    "exist yet. The link will be saved."
                                )

                        if not valid_children:
                            return

                    doc_ref, doc = get_user_doc(clean_name)

                    if doc.exists:
                        st.error("This username is already taken.")

                    else:
                        new_data = {
                            "password": entered_pass,
                            "full_name": clean_fullname,
                            "birth_date": birth_date.isoformat(),
                            "age": age,
                            "messages": [],
                            "chat_history": [],
                            "friends": [],
                            "nicknames": {},
                            "account_type": acc_choice,
                            "parent_mode": parent_sub,
                            "school_name": school_name.strip(),
                            "school_location": school_location.strip(),
                            "grade": student_grade.strip() if acc_choice == "Student Portal" else "",
                            "section": student_section.strip().upper() if acc_choice == "Student Portal" else "",
                            "user_city": "London",
                            "profile_pic": "",
                            "admin_role": "user"
                        }

                        if acc_choice == "Parent Portal":
                            new_data["child_usernames"] = [
                                c.strip()
                                for c in child_usernames_input.split(",")
                                if c.strip()
                            ]
                            new_data["verified_by_child"] = False

                        doc_ref.set(new_data)
                        st.success(
                            "Account created successfully! Switch to Log In."
                        )

        else:
            if st.button("Log In to Workspace", use_container_width=True):
                if _attempt_login(entered_name, entered_pass):
                    st.rerun()
                
    st.markdown("---")
    st.markdown(
        "By logging in or creating an account, you agree to view our "
        "[Terms and Conditions](https://docs.google.com/document/d/"
        "1ycrKZBunldxtRSEaESQ6utCUIvoAOzA-mSlRxnYhBCI/edit?tab=t.0)."
    )


if not st.session_state["logged_in"]:
    render_auth_screen()
    st.stop()

user_name = st.session_state["user_name"]
user_role = st.session_state["account_type"]


# =====================================================================
# SECTION 8: AUTOMATED BIRTHDAY & 18TH MILESTONE CHECKERS
# =====================================================================
user_doc_ref, user_doc_snapshot = get_user_doc(user_name)

if user_doc_snapshot.exists:
    u_info = user_doc_snapshot.to_dict()
    bday_str = u_info.get("birth_date")

    if bday_str:
        bday_date = datetime.fromisoformat(bday_str).date()
        today_date = date.today()

        if (
            bday_date.month == today_date.month
            and bday_date.day == today_date.day
        ):
            st.success("🎉 Happy Birthday! Wishing you an amazing day!")
            st.balloons()

            current_age = today_date.year - bday_date.year

            if current_age == 18 and not u_info.get(
                "turned_18_notified", False
            ):
                parents = db.collection("users").where(
                    "account_type", "==", "Parent Portal"
                ).stream()

                for p in parents:
                    p_data = p.to_dict()

                    if user_name in p_data.get("child_usernames", []):
                        db.collection("parent_alerts").add({
                            "parent": p_data["full_name"],
                            "alert": (
                                f"Your child {st.session_state['full_name']} "
                                "has turned 18 today!"
                            ),
                            "time": datetime.now(timezone.utc).isoformat()
                        })

                user_doc_ref.set(
                    {"turned_18_notified": True},
                    merge=True
                )


# =====================================================================
# SECTION 9: MODERATION & ACCOUNT RESTRICTION ENFORCEMENT
# =====================================================================
warn_doc = db.collection("user_warnings").document(user_name).get()

if warn_doc.exists:
    w_data = warn_doc.to_dict()

    st.warning(
        f"⚠️ **ADMIN WARNING**: {w_data.get('message', 'Please follow the community rules.')}"
    )

    if st.button("I Understand"):
        db.collection("user_warnings").document(user_name).delete()
        st.rerun()

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


# =====================================================================
# SECTION 10: PARENT LINK VERIFICATION PROTOCOLS
# =====================================================================
if user_role == "Student Portal" and not st.session_state["parent_verified"]:
    st.title(f"Hello {st.session_state['full_name']}!")
    st.subheader("🛡️ Parent Verification Check")

    verification = st.radio(
        "Is the person who wrote your username your parent or not?",
        ["Select...", "Yes", "No"]
    )

    if verification != "Select...":
        if verification == "Yes":
            st.session_state["parent_verified"] = True
            user_doc_ref.set({"parent_verified": True}, merge=True)
            st.rerun()
        else:
            st.warning(
                "Please ask a parent or guardian to verify before proceeding."
            )

    st.stop()

if user_role == "Student Portal":
    parent_reqs = db.collection("users").where(
        "child_usernames", "array_contains", user_name
    ).where("verified_by_child", "==", False).stream()

    for req in parent_reqs:
        p_data = req.to_dict()

        st.title(f"Hello {st.session_state['full_name']}!")
        st.subheader("🛡️ Parent Link Request")

        st.write(
            f"**{p_data['full_name']}** wants to link to your account as your parent."
        )

        confirm = st.radio(
            "Is this person really your parent?",
            ["Select...", "Yes", "No"],
            key=req.id
        )

        if confirm == "Yes":
            db.collection("users").document(req.id).update(
                {"verified_by_child": True}
            )
            st.success("Parent linked successfully!")
            st.rerun()

        elif confirm == "No":
            db.collection("users").document(req.id).delete()
            st.warning("Parent request declined.")
            st.rerun()

        st.stop()
        # =====================================================================
# SECTION 11: SIDEBAR NAVIGATION & ADMIN CONTROLS
# =====================================================================
with st.sidebar:
    st.title("📂 Workspace")

    st.session_state["app_mode"] = st.radio(
        "Select Mode",
        ["Solo Study / AI Chat", "👥 Friends & Study Groups"]
    )

    st.markdown("---")

    current_user_doc = (
        user_doc_snapshot.to_dict()
        if user_doc_snapshot.exists else {}
    )

    current_admin_role = current_user_doc.get("admin_role", "user")

    if user_name == "MoltenSpy" or current_admin_role in [
        "admin", "super_admin"
    ]:
        st.subheader("👑 Admin Control Panel")

        feedbacks = list(db.collection("feedbacks").stream())

        if len(feedbacks) >= 10:
            st.markdown("### 📊 Feedback Summary (10+ Received)")

            fb_texts = [
                f.to_dict().get("feedback", "")
                for f in feedbacks
            ]

            st.info(
                f"Total Feedbacks: {len(feedbacks)}\n\n"
                f'Latest Feedback Sample: "{fb_texts[-1]}"'
            )

            if st.button("Clear Feedback Archive"):
                for f in feedbacks:
                    db.collection("feedbacks").document(f.id).delete()

                st.success("Feedback archive cleared!")

        st.markdown("### 🚨 Violation Reports")

        reports = list(db.collection("violations").stream())

        if not reports:
            st.info("No violation reports right now!")

        else:
            for rep in reports:
                rep_data = rep.to_dict()
                u_target = rep_data.get("username", "Unknown")
                v_count = rep_data.get("count", 1)
                last_msg = rep_data.get("last_message", "")

                st.markdown(
                    f"👤 **{u_target}** | **Violations:** {v_count}"
                )
                st.caption(f'Last offense: "{last_msg}"')

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    if st.button("⚠️ Warn", key=f"warn_{rep.id}"):
                        db.collection("user_warnings").document(
                            u_target
                        ).set({
                            "message": (
                                "You have been flagged for inappropriate "
                                "language. Please follow the community rules."
                            ),
                            "time": datetime.now(timezone.utc).isoformat()
                        })

                        db.collection("violations").document(
                            rep.id
                        ).delete()

                        st.success(f"Warning sent to {u_target}!")

                with c2:
                    if st.button("⏸️ Suspend", key=f"sus_{rep.id}"):
                        db.collection("account_actions").document(
                            u_target
                        ).set({
                            "type": "suspended",
                            "reason": (
                                f"Repeated inappropriate language "
                                f"({v_count} times)."
                            ),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                        db.collection("violations").document(
                            rep.id
                        ).delete()

                        st.success(f"Suspended {u_target}!")

                with c3:
                    if st.button("🚫 Ban", key=f"ban_{rep.id}"):
                        db.collection("account_actions").document(
                            u_target
                        ).set({
                            "type": "banned",
                            "reason": (
                                f"Exceeded inappropriate behaviour limit "
                                f"({v_count} violations)."
                            ),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                        db.collection("violations").document(
                            rep.id
                        ).delete()

                        st.success(f"Banned {u_target}!")

                with c4:
                    if st.button("❌ Dismiss", key=f"dismiss_{rep.id}"):
                        db.collection("violations").document(
                            rep.id
                        ).delete()

                        st.success(f"Report dismissed for {u_target}!")

                st.markdown("---")

        target_user = st.text_input(
            "Target Username",
            key="admin_target"
        )

        action_type = st.selectbox(
            "Action",
            [
                "Ban Account",
                "Suspend Account",
                "Unban / Remove Action",
                "Make Admin (Moderator)",
                "Make Super Admin",
                "Remove Admin Role"
            ]
        )

        action_reason = st.text_area(
            "Reason",
            key="admin_reason"
        )

        if st.button("Apply Action", use_container_width=True):
            clean_target = target_user.strip()

            if not clean_target:
                st.error("Please enter a username.")

            else:
                target_ref, target_snap = get_user_doc(clean_target)

                if not target_snap.exists:
                    st.error(
                        f"Target user '{clean_target}' does not exist."
                    )

                else:
                    target_data = target_snap.to_dict()
                    target_admin_role = target_data.get(
                        "admin_role", "user"
                    )

                    if (
                        action_type in ["Ban Account", "Suspend Account"]
                        and (
                            clean_target == "MoltenSpy"
                            or target_admin_role == "super_admin"
                        )
                    ):
                        st.error("You cannot restrict a super administrator.")

                    else:
                        if action_type == "Unban / Remove Action":
                            db.collection("account_actions").document(
                                clean_target
                            ).delete()

                            st.success(
                                f"Restrictions removed for {clean_target}."
                            )

                        elif action_type == "Make Admin (Moderator)":
                            target_ref.set(
                                {"admin_role": "admin"},
                                merge=True
                            )

                            st.success(
                                f"{clean_target} is now an Admin."
                            )

                        elif action_type == "Make Super Admin":
                            if user_name == "MoltenSpy":
                                target_ref.set(
                                    {"admin_role": "super_admin"},
                                    merge=True
                                )

                                st.success(
                                    f"{clean_target} is now a Super Admin."
                                )
                            else:
                                st.error(
                                    "Only the authorized administrator "
                                    "can appoint Super Admins."
                                )

                        elif action_type == "Remove Admin Role":
                            target_ref.set(
                                {"admin_role": "user"},
                                merge=True
                            )

                            st.success(
                                f"Admin role removed for {clean_target}."
                            )

                        else:
                            status_text = (
                                "banned"
                                if action_type == "Ban Account"
                                else "suspended"
                            )

                            db.collection("account_actions").document(
                                clean_target
                            ).set({
                                "type": status_text,
                                "reason": (
                                    action_reason.strip()
                                    if action_reason.strip()
                                    else "Violation of terms."
                                ),
                                "timestamp": datetime.now(
                                    timezone.utc
                                ).isoformat()
                            })

                            st.success(
                                f"Account '{clean_target}' is now "
                                f"{status_text}."
                            )

        st.markdown("---")

    st.subheader("👤 Profile Picture")

    uploaded_profile = st.file_uploader(
        "Upload Photo",
        type=["png", "jpg", "jpeg"],
        key="sidebar_profile_uploader"
    )

    if uploaded_profile:
        pic_bytes = base64.b64encode(
            uploaded_profile.read()
        ).decode("utf-8")

        st.session_state["profile_pic"] = (
            f"data:image/png;base64,{pic_bytes}"
        )

        save_user_session()
        st.success("Profile picture updated!")

    if st.session_state["profile_pic"]:
        st.image(
            st.session_state["profile_pic"],
            width=80
        )

    st.markdown("---")

    st.subheader("⚙️ Account Settings")

    with st.expander("Update Profile / Password"):
        new_name_val = st.text_input(
            "New Full Name",
            value=st.session_state["full_name"]
        )

        if st.button("Update Full Name"):
            if new_name_val.strip():
                st.session_state["full_name"] = new_name_val.strip()

                db.collection("users").document(user_name).update({
                    "full_name": new_name_val.strip()
                })

                st.success("Full name updated successfully!")

            else:
                st.error("Full name cannot be empty.")

        st.markdown("---")

        new_pass_val = st.text_input(
            "New Password",
            type="password"
        )

        confirm_pass_val = st.text_input(
            "Confirm New Password",
            type="password"
        )

        if st.button("Change Password"):
            if not new_pass_val or not confirm_pass_val:
                st.error("Password fields cannot be empty.")

            elif new_pass_val != confirm_pass_val:
                st.error("Passwords do not match.")

            else:
                db.collection("users").document(user_name).update({
                    "password": new_pass_val
                })

                st.success("Password updated successfully!")

    st.markdown("---")

    if st.session_state["app_mode"] == "Solo Study / AI Chat":

        if st.button(
            "➕ New Chat / Topic",
            use_container_width=True
        ):
            if st.session_state["messages"]:
                chat_title = (
                    st.session_state["messages"][0]["content"][:25]
                    + "..."
                )

                st.session_state["chat_history"].append({
                    "title": chat_title,
                    "messages": st.session_state["messages"],
                    "time": datetime.now(timezone.utc).isoformat()
                })

            st.session_state["messages"] = []
            save_user_session()
            st.rerun()

        with st.expander("💬 Solo Chat History"):

            if len(st.session_state["chat_history"]) > 3:
                if st.button(
                    "🗑️ Clear All Chats",
                    use_container_width=True
                ):
                    st.session_state["chat_history"] = []
                    save_user_session()
                    st.success("All chat history cleared!")
                    st.rerun()

            for i, chat in enumerate(
                st.session_state["chat_history"]
            ):
                cols = st.columns([4, 1])

                with cols[0]:
                    if st.button(
                        chat["title"],
                        key=f"history_{i}"
                    ):
                        st.session_state["messages"] = chat["messages"]
                        st.rerun()

                with cols[1]:
                    if st.button(
                        "❌",
                        key=f"del_chat_{i}"
                    ):
                        st.session_state["chat_history"].pop(i)
                        save_user_session()
                        st.rerun()

    elif st.session_state["app_mode"] == "👥 Friends & Study Groups":

        st.subheader("🟣 Group Chats")

        if st.session_state["active_group_id"]:
            if st.button(
                "❌ Close Current Group",
                use_container_width=True
            ):
                st.session_state["active_group_id"] = None
                st.rerun()

            st.markdown("---")

        groups_query = db.collection("groups").stream()

        for g in groups_query:
            g_data = g.to_dict()
            members = g_data.get("members", [])

            if (
                user_name in members
                or g_data.get("creator") == st.session_state["full_name"]
            ):
                if st.button(
                    f"🟣 {g_data['name']}",
                    key=f"sidebar_group_{g.id}",
                    use_container_width=True
                ):
                    st.session_state["active_group_id"] = g.id
                    st.rerun()

    st.markdown("---")

    # The user's sent message is editable in the chat itself using the pencil icon.

    st.subheader("🌤️ Weather Report")

    user_location = st.text_input(
        "Location:",
        value=st.session_state["user_city"]
    )

    if user_location != st.session_state["user_city"]:
        st.session_state["user_city"] = user_location
        save_user_session()

    st.markdown(
        get_weather(st.session_state["user_city"])
    )

    st.markdown("---")

    if st.button("Log out", use_container_width=True):
        save_user_session()
        st.session_state["logged_in"] = False
        st.session_state["parent_verified"] = False
        st.rerun()

    st.markdown("---")

    st.subheader("📝 Send Feedback")

    user_feedback_text = st.text_area(
        "Share your feedback or suggestions:",
        key="sidebar_feedback_input"
    )

    if st.button("Submit Feedback"):
        if user_feedback_text.strip():
            db.collection("feedbacks").add({
                "username": user_name,
                "full_name": st.session_state["full_name"],
                "feedback": user_feedback_text.strip(),
                "time": datetime.now(timezone.utc).isoformat()
            })

            st.success("Thank you for your feedback!")

        else:
            st.error("Feedback cannot be empty.")

    st.markdown("---")

    st.subheader("⚠️ Danger Zone")

    confirm_del = st.checkbox(
        "Confirm Account Deletion",
        key="del_acc_chk"
    )

    if st.button("Delete My Account"):
        if confirm_del:
            db.collection("users").document(user_name).delete()

            st.session_state["logged_in"] = False

            st.success("Account deleted successfully.")
            st.rerun()

        else:
            st.error("Please check the confirmation box first.")


# =====================================================================
# SECTION 12: SECURITY & MODERATION ENGINES
# =====================================================================
def detect_harmful_keywords(text):
    harmful_keywords = [
        "kill yourself",
        "commit suicide",
        "want to die"
    ]

    found = any(
        re.search(
            r'\b' + re.escape(w) + r'\b',
            text.lower()
        )
        for w in harmful_keywords
    )

    if found and user_role == "Personal Account":
        db.collection("parent_alerts").add({
            "child": st.session_state["full_name"],
            "alert": "Child expressed distressing or harmful thoughts.",
            "time": datetime.now(timezone.utc).isoformat()
        })

    return found


def detect_foul_language(text):
    foul_words = [
        "badword1",
        "badword2",
        "idiot",
        "stupid",
        "mother",
        "father",
        "parents",
        "trash",
        "hate"
    ]

    found = any(
        re.search(
            r'\b' + re.escape(w) + r'\b',
            text.lower()
        )
        for w in foul_words
    )

    if found:
        v_doc = db.collection("violations").document(user_name).get()

        current_count = (
            v_doc.to_dict().get("count", 0) + 1
            if v_doc.exists else 1
        )

        db.collection("violations").document(user_name).set({
            "username": user_name,
            "full_name": st.session_state["full_name"],
            "count": current_count,
            "last_message": text,
            "time": datetime.now(timezone.utc).isoformat()
        })

    return found


def check_chat_suspension():
    sus_ref = db.collection("suspensions").document(user_name)
    sus_doc = sus_ref.get()

    if sus_doc.exists:
        sus_data = sus_doc.to_dict()
        expiry_time = datetime.fromisoformat(
            sus_data["expires_at"]
        )

        if datetime.now(timezone.utc) < expiry_time:
            return True

        else:
            sus_ref.delete()

    return False


# =====================================================================
# SECTION 13: PARENT PORTAL DASHBOARD VIEW
# =====================================================================
if user_role == "Parent Portal":

    doc_ref, doc = get_user_doc(user_name)

    if doc.exists and not doc.to_dict().get(
        "verified_by_child", True
    ):
        st.title(
            f"Hello {st.session_state['full_name']} "
            "(Parent Dashboard)"
        )

        st.warning(
            "⏳ Waiting for your child to confirm your request. "
            "Please ask your child to log in and approve the parent link."
        )

        if st.button("Log out"):
            st.session_state["logged_in"] = False
            st.rerun()

        st.stop()

    st.title(
        f"Hello {st.session_state['full_name']} "
        "(Parent Dashboard)"
    )

    st.subheader("👶 Manage Children")

    current_data = doc.to_dict()
    children_list = current_data.get("child_usernames", [])

    st.write(
        f"Linked Children: "
        f"{', '.join(children_list) if children_list else 'None'}"
    )

    new_child_input = st.text_input(
        "Add Another Child Username"
    )

    if st.button("Add Child"):
        if new_child_input.strip():
            _, c_check = get_user_doc(new_child_input.strip())

            if c_check.exists:
                if new_child_input.strip() not in children_list:
                    children_list.append(new_child_input.strip())

                    doc_ref.set({
                        "child_usernames": children_list
                    }, merge=True)

                    st.success("Child added successfully!")

                else:
                    st.warning("Child is already added.")

            else:
                st.error("Child username does not exist.")

    if st.session_state["parent_mode"] == "School Account Parent":

        st.subheader("🏫 School Account Monitoring")

        st.info(
            "Here you can access your child's completed tasks "
            "and connect directly with teachers."
        )

        teacher_msg = st.text_area(
            "Send direct message to teacher:"
        )

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

            st.warning(
                f"**{a_data.get('child', 'Child')}** - "
                f"{a_data.get('alert', '')} "
                f"({a_data.get('time', '')})"
            )

        st.markdown("### 💡 Ways to Console Your Child")

        st.markdown(
            "- Listen actively and without judgment.\n"
            "- Reassure them of your support.\n"
            "- Connect with professional counseling or guidance if needed."
        )

    st.stop()


# =====================================================================
# SECTION 14: SCHOOL & TEACHER PORTAL DASHBOARDS
# =====================================================================
if user_role == "Teacher Portal":
    teacher_data = user_doc_snapshot.to_dict() if user_doc_snapshot.exists else {}
    school_name = teacher_data.get("school_name", st.session_state.get("school_name", ""))
    school_location = teacher_data.get("school_location", st.session_state.get("school_location", ""))
    st.title(f"🍎 Teacher Dashboard — {st.session_state['full_name']}")
    st.caption(f"{school_name} · {school_location}")

    teacher_tabs = st.tabs(["📩 Parent Messages", "📋 Homework & Tasks", "📚 Learning Resources"])
    with teacher_tabs[0]:
        st.subheader("Messages from Parents")
        p_msgs = db.collection("teacher_parent_messages").stream()
        found_messages = False
        for pm in p_msgs:
            pm_data = pm.to_dict() or {}
            if normalize_school_value(pm_data.get("school_name")) in ("", normalize_school_value(school_name)):
                found_messages = True
                st.info(f"**From:** {pm_data.get('parent', 'Parent')}\n\n**Message:** {pm_data.get('message', '')}")
        if not found_messages:
            st.caption("No parent messages yet.")

    with teacher_tabs[1]:
        st.subheader("Assign Homework / Task")
        with st.form("teacher_create_task_form"):
            grade = st.selectbox("Select Grade", [f"Grade {n}" for n in range(1, 13)], key="teacher_task_grade")
            section = st.selectbox("Select Section", [chr(code) for code in range(65, 91)], key="teacher_task_section")
            title = st.text_input("Task Title", key="teacher_task_title")
            instructions = st.text_area("Task Instructions", key="teacher_task_instructions")
            due_date = st.date_input("Due Date", value=date.today(), key="teacher_task_due")
            submitted = st.form_submit_button("Assign to this Grade & Section", use_container_width=True)
        if submitted:
            if not section.strip() or not title.strip():
                st.error("Please enter a section and task title.")
            else:
                db.collection("assignments").add({
                    "school_name": school_name,
                    "school_location": school_location,
                    "grade": grade,
                    "section": section.strip().upper(),
                    "title": title.strip(),
                    "instructions": instructions.strip(),
                    "due_date": due_date.isoformat(),
                    "teacher": st.session_state["full_name"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "type": "task"
                })
                st.success(f"Task assigned to {grade}, Section {section.strip().upper()}.")

    with teacher_tabs[2]:
        st.subheader("Share a Learning Resource")
        with st.form("teacher_create_resource_form"):
            resource_grade = st.selectbox("Select Grade", [f"Grade {n}" for n in range(1, 13)], key="teacher_resource_grade")
            resource_section = st.selectbox("Select Section", [chr(code) for code in range(65, 91)], key="teacher_resource_section")
            resource_title = st.text_input("Resource Title", key="teacher_resource_title")
            resource_description = st.text_area("Description", key="teacher_resource_description")
            resource_url = st.text_input("Resource Link (optional)", placeholder="https://...", key="teacher_resource_url")
            resource_submit = st.form_submit_button("Share Resource", use_container_width=True)
        if resource_submit:
            if not resource_section.strip() or not resource_title.strip():
                st.error("Please enter a section and resource title.")
            elif resource_url.strip() and not resource_url.strip().startswith(("https://", "http://")):
                st.error("Please enter a valid link beginning with http:// or https://.")
            else:
                db.collection("class_resources").add({
                    "school_name": school_name,
                    "school_location": school_location,
                    "grade": resource_grade,
                    "section": resource_section.strip().upper(),
                    "title": resource_title.strip(),
                    "description": resource_description.strip(),
                    "url": resource_url.strip(),
                    "teacher": st.session_state["full_name"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                st.success(f"Resource shared with {resource_grade}, Section {resource_section.strip().upper()}.")
    st.stop()


if user_role == "School Account":
    school_data = user_doc_snapshot.to_dict() if user_doc_snapshot.exists else {}
    school_name = school_data.get("school_name", "")
    school_location = school_data.get("school_location", "")
    st.title(f"🏫 School Account — {school_name}")
    st.caption(school_location)
    school_users = []
    for account in db.collection("users").stream():
        data = account.to_dict() or {}
        if normalize_school_value(data.get("school_name")) == normalize_school_value(school_name) and normalize_school_value(data.get("school_location")) == normalize_school_value(school_location):
            school_users.append((account.id, data))
    students = [u for _, u in school_users if u.get("account_type") == "Student Portal"]
    teachers = [u for _, u in school_users if u.get("account_type") == "Teacher Portal"]
    school_tabs = st.tabs(["📊 Overview", "📋 School Tasks", "📚 Shared Resources"])
    with school_tabs[0]:
        a, b = st.columns(2)
        a.metric("Students", len(students))
        b.metric("Teachers", len(teachers))
        st.subheader("Registered Teachers")
        for teacher in teachers:
            st.write(f"• {teacher.get('full_name', 'Teacher')}")
        st.subheader("Registered Classes")
        class_pairs = sorted({(u.get("grade", ""), u.get("section", "")) for u in students if u.get("grade") and u.get("section")})
        if class_pairs:
            for grade_value, section_value in class_pairs:
                st.write(f"• {grade_value} — Section {section_value}")
        else:
            st.caption("No student classes registered yet.")
    with school_tabs[1]:
        all_tasks = db.collection("assignments").stream()
        count = 0
        for task in all_tasks:
            item = task.to_dict() or {}
            if normalize_school_value(item.get("school_name")) == normalize_school_value(school_name) and normalize_school_value(item.get("school_location")) == normalize_school_value(school_location):
                count += 1
                st.info(f"**{item.get('title', 'Task')}** · {item.get('grade', '')}, Section {item.get('section', '')}\n\n{item.get('instructions', '')}\n\nAssigned by {item.get('teacher', 'Teacher')} · Due: {item.get('due_date', 'Not set')}")
        if not count:
            st.caption("No tasks have been assigned yet.")
    with school_tabs[2]:
        all_resources = db.collection("class_resources").stream()
        count = 0
        for resource in all_resources:
            item = resource.to_dict() or {}
            if normalize_school_value(item.get("school_name")) == normalize_school_value(school_name) and normalize_school_value(item.get("school_location")) == normalize_school_value(school_location):
                count += 1
                st.markdown(f"**{item.get('title', 'Resource')}** · {item.get('grade', '')}, Section {item.get('section', '')}")
                if item.get("description"):
                    st.write(item["description"])
                if item.get("url"):
                    st.markdown(f"[Open resource]({item['url']})")
        if not count:
            st.caption("No resources have been shared yet.")
    st.stop()


# SECTION 15: MAIN APPLICATION - SOLO STUDY & AI TUTOR CHAT
# =====================================================================
def _rerun_current_chat_fragment():
    """Refresh the normal Streamlit app after a group chat update."""
    st.rerun()


# Keep both chat renderers in the normal app layout. Streamlit's native
# st.chat_input then anchors to the viewport bottom and automatically uses
# the available main-area width as the sidebar expands or contracts.


def render_user_prompt_editor(message_index):
    """Inline editor for a user's own previously sent chat prompt."""
    messages = st.session_state.get("messages", [])
    if not (0 <= message_index < len(messages)):
        st.session_state["editing_user_prompt"] = None
        return
    original = str(messages[message_index].get("content", ""))
    with st.form(key=f"edit_user_prompt_form_{message_index}"):
        revised = st.text_area("Edit your message", value=original, key=f"edit_user_prompt_text_{message_index}", height=100)
        save_col, cancel_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Save changes", use_container_width=True)
        with cancel_col:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        if save:
            if revised.strip():
                messages[message_index]["content"] = revised.strip()
                # Remove later conversation turns so the next reply uses the edited prompt.
                st.session_state["messages"] = messages[:message_index + 1]
                st.session_state["editing_user_prompt"] = None
                save_user_session()
                st.rerun()
            else:
                st.error("Your message cannot be empty.")
        elif cancel:
            st.session_state["editing_user_prompt"] = None
            st.rerun()


def render_solo_study_chat():

    st.title(f"Hello {st.session_state['full_name']}!")

    if user_role == "Student Portal":
        student_data = user_doc_snapshot.to_dict() if user_doc_snapshot.exists else {}
        student_school = student_data.get("school_name", "")
        student_location = student_data.get("school_location", "")
        student_grade = student_data.get("grade", "")
        student_section = student_data.get("section", "")
        with st.expander(f"📚 Homework & Tasks — {student_grade}, Section {student_section}", expanded=True):
            st.subheader("Assigned Homework & Tasks")
            student_tasks = get_class_records("assignments", student_school, student_location, student_grade, student_section)
            if student_tasks:
                for task in student_tasks:
                    st.info(f"**{task.get('title', 'Task')}**\n\n{task.get('instructions', '')}\n\n**Due:** {task.get('due_date', 'Not specified')} · **Teacher:** {task.get('teacher', 'Teacher')}")
            else:
                st.caption("No homework or tasks have been assigned to your class yet.")
            st.divider()
            st.subheader("Learning Resources")
            student_resources = get_class_records("class_resources", student_school, student_location, student_grade, student_section)
            if student_resources:
                for resource in student_resources:
                    st.markdown(f"**{resource.get('title', 'Resource')}**")
                    if resource.get("description"):
                        st.write(resource["description"])
                    if resource.get("url"):
                        st.markdown(f"[Open resource]({resource['url']})")
            else:
                st.caption("No learning resources have been shared with your class yet.")

    st.subheader("What's on your mind today? 😊")

    st.caption(
        "💡 Emojis: On laptop/PC press Windows + . "
        "to open emojis!"
    )

    # ---------------------------------------------------------------
    # DISPLAY EXISTING CHAT MESSAGES
    # ---------------------------------------------------------------
    for msg_index, msg in enumerate(st.session_state["messages"]):

        avatar_img = (
            st.session_state.get("profile_pic", None)
            if msg["role"] == "user"
            else None
        )

        with st.chat_message(
            msg["role"],
            avatar=avatar_img
        ):
            st.markdown(msg["content"])
            if msg["role"] == "user":
                if st.button("✏️", key=f"edit_user_prompt_{msg_index}", help="Edit your message"):
                    st.session_state["editing_user_prompt"] = msg_index
                if st.session_state.get("editing_user_prompt") == msg_index:
                    render_user_prompt_editor(msg_index)
            if msg["role"] == "assistant":
                render_answer_actions(msg["content"], key=f"solo_history_{len(st.session_state['messages'])}_{hash(str(msg['content']))}")

            if msg.get("file_data"):

                if msg.get("file_type", "").startswith("image/"):
                    st.image(
                        msg["file_data"],
                        width=250
                    )

                elif msg.get("file_type", "").startswith("video/"):
                    st.video(msg["file_data"])

                else:
                    st.info(
                        f"📎 Attached file: "
                        f"{msg.get('file_name', 'File')}"
                    )

    # ---------------------------------------------------------------
    # CHAT INPUT
    # ---------------------------------------------------------------
    st.caption("Exegesis AI can make mistakes. Double check important information.")
    # Streamlit chat_input sends the message with Enter and stays anchored at the bottom.
    prompt = st.chat_input(
        "Ask a study question... (press Enter to send) 💬",
        accept_file=True,
        file_type=[
            "png", "jpg", "jpeg",
            "mp4", "mov", "avi",
            "pdf", "txt", "docx", "odt"
        ]
    )

    if prompt:

        user_text = (
            prompt.text
            if hasattr(prompt, "text")
            else str(prompt)
        )

        uploaded_files = (
            prompt.files
            if hasattr(prompt, "files")
            else []
        )

        file_data_str = ""
        file_type_str = ""
        file_name_str = ""

        if uploaded_files:

            file_obj = uploaded_files[0]
            try:
                file_bytes = file_obj.read()
            except (FileNotFoundError, OSError):
                st.error("That attachment is no longer available. Please upload it again and resend your message.")
                return

            file_bytes_str = base64.b64encode(
                file_bytes
            ).decode("utf-8")

            file_type_str = str(file_obj.type or "")
            file_name_str = str(file_obj.name or "file")

            file_data_str = (
                f"data:{file_type_str};base64,{file_bytes_str}"
            )

            if file_type_str.startswith("image/"):
                user_text = (
                    f"[Attached Image: {file_name_str}]\n{user_text}"
                )

            elif file_type_str.startswith("video/"):
                user_text = (
                    f"[Attached Video: {file_name_str}]\n{user_text}"
                )

            else:
                user_text = (
                    f"[Attached File: {file_name_str}]\n{user_text}"
                )

        content_to_send = str(
            user_text if user_text else "Sent an attachment."
        )

        msg_payload = {
            "role": "user",
            "content": content_to_send,
            "file_data": file_data_str,
            "file_type": file_type_str,
            "file_name": file_name_str
        }

        # SAVE USER MESSAGE
        st.session_state["messages"].append(msg_payload)

        with st.chat_message(
            "user",
            avatar=st.session_state.get("profile_pic", None)
        ):
            st.markdown(content_to_send)

            if file_data_str:
                if file_type_str.startswith("image/"):
                    st.image(file_data_str, width=250)

                elif file_type_str.startswith("video/"):
                    st.video(file_data_str)

                else:
                    st.info(f"📎 Attached file: {file_name_str}")

        # SAFETY CHECK
        if detect_harmful_keywords(content_to_send):

            reply = (
                "Please connect with a trusted family member, "
                "teacher, or counselor for support."
            )

            st.session_state["messages"].append({
                "role": "assistant",
                "content": reply
            })

            with st.chat_message("assistant"):
                st.markdown(reply)
                render_answer_actions(reply, key="solo_safety_reply")

            save_user_session()
            return

        if detect_foul_language(content_to_send):
            st.warning(
                "⚠️ Inappropriate language flagged and sent to admin."
            )

        # PREPARE AI CONVERSATION
        chat_context = [
            {
                "role": "system",
                "content": get_active_tutor_prompt()
            }
        ] + [
            {
                "role": str(m["role"]),
                "content": str(m["content"])
            }
            for m in st.session_state["messages"]
        ]

        # -----------------------------------------------------------
        # FIXED OPENROUTER COMMUNICATION
        # -----------------------------------------------------------
        with st.spinner("Exegesis AI is thinking..."):

            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",

                    headers={
                        "Authorization": f"Bearer {FULL_API_KEY}",
                        "Content-Type": "application/json"
                    },

                    json={
                        "model": "openrouter/free",
                        "messages": chat_context
                    },

                    timeout=60
                )

                try:
                    response_json = resp.json()
                except ValueError:
                    response_json = {}

                if not resp.ok:

                    error_data = response_json.get(
                        "error",
                        {}
                    )

                    if isinstance(error_data, dict):
                        error_message = error_data.get(
                            "message",
                            str(error_data)
                        )
                    else:
                        error_message = str(error_data)

                    # Avoid echoing raw provider payloads that may contain sensitive details.
                    ai_reply = f"⚠️ The AI service returned an error (HTTP {resp.status_code}). Please try again shortly. If it continues, ask the app administrator to check the deployment logs."

                elif response_json.get("choices"):

                    message_data = (
                        response_json["choices"][0].get(
                            "message",
                            {}
                        )
                    )

                    ai_reply = message_data.get("content")

                    if isinstance(ai_reply, list):
                        text_parts = []
                        for part in ai_reply:
                            if isinstance(part, dict) and part.get("text"):
                                text_parts.append(str(part["text"]))
                            elif isinstance(part, str):
                                text_parts.append(part)
                        ai_reply = "\n".join(text_parts)

                    if ai_reply is None:
                        ai_reply = ""

                    ai_reply = str(ai_reply).strip()

                    if not ai_reply or ai_reply.lower() == "none":
                        ai_reply = (
                            "I didn't receive a usable answer from the AI service. "
                            "Please try asking again in a moment."
                        )

                else:
                    ai_reply = "⚠️ The AI service did not return a usable response. Please try again shortly."

            except requests.Timeout:
                ai_reply = (
                    "⚠️ The AI service took too long to respond. "
                    "Please try again."
                )

            except requests.RequestException:
                ai_reply = "⚠️ Network connection problem. Please check the internet connection and try again."

            except Exception as e:
                ai_reply = f"⚠️ Something went wrong while preparing the AI response ({type(e).__name__}). Your chat is still available; please try again."

        # -----------------------------------------------------------
        # IMPORTANT FIX: SAVE AND DISPLAY AI RESPONSE IMMEDIATELY
        # -----------------------------------------------------------
        st.session_state["messages"].append({
            "role": "assistant",
            "content": ai_reply
        })

        with st.chat_message("assistant"):
            st.markdown(ai_reply)
            render_answer_actions(ai_reply, key="solo_latest_reply")

        save_user_session()
        # =====================================================================
# SECTION 16: COLLABORATIVE STUDY GROUPS & NICKNAMES
# =====================================================================
def render_group_study_chats():

    st.title(
        f"Hello {st.session_state['full_name']}! "
        "👥 Friends & Study Groups"
    )

    tab1, tab2 = st.tabs([
        "Friend Requests & Nicknames",
        "Create Group Chat"
    ])

    # ================================================================
    # TAB 1: FRIEND REQUESTS
    # ================================================================
    with tab1:

        st.subheader("Add Friend")

        target_username = st.text_input(
            "Enter their username",
            key="friend_username_input",
            placeholder="Exact username"
        )

        if st.button("Send Friend Request"):
            clean_target_username = target_username.strip()

            if not clean_target_username:
                st.error("Please enter a username.")
            elif clean_target_username == user_name:
                st.warning("You cannot send a friend request to yourself.")
            else:
                target_ref, target_doc = get_user_doc(clean_target_username)

                if not target_doc.exists:
                    st.error(
                        "No account was found with that username. "
                        "Check the spelling and try again."
                    )
                else:
                    target_data = target_doc.to_dict()
                    target_fullname = target_data.get(
                        "full_name", clean_target_username
                    )

                    existing_requests = list(
                        db.collection("friend_requests").stream()
                    )
                    already_connected = False
                    pending_exists = False

                    for existing in existing_requests:
                        existing_data = existing.to_dict()
                        same_pair = (
                            existing_data.get("from_user") == user_name
                            and existing_data.get("to_user") == clean_target_username
                        ) or (
                            existing_data.get("from_user") == clean_target_username
                            and existing_data.get("to_user") == user_name
                        )

                        # Support friend requests created by older app versions.
                        if not same_pair:
                            same_pair = (
                                existing_data.get("from_fullname") == st.session_state["full_name"]
                                and existing_data.get("to_fullname") == target_fullname
                            ) or (
                                existing_data.get("from_fullname") == target_fullname
                                and existing_data.get("to_fullname") == st.session_state["full_name"]
                            )

                        if same_pair:
                            if existing_data.get("status") == "accepted":
                                already_connected = True
                            elif existing_data.get("status") == "pending":
                                pending_exists = True

                    if already_connected:
                        st.info("You are already friends with this user.")
                    elif pending_exists:
                        st.info("A friend request for this user is already pending.")
                    else:
                        db.collection("friend_requests").add({
                            "from_user": user_name,
                            "from_fullname": st.session_state["full_name"],
                            "to_user": clean_target_username,
                            "to_fullname": target_fullname,
                            "status": "pending",
                            "time": datetime.now(timezone.utc).isoformat()
                        })
                        st.success(f"Friend request sent to @{clean_target_username}!")
                        st.rerun()

        st.subheader(
            "Your Friends"
        )

        accepted_reqs = db.collection(
            "friend_requests"
        ).where("status", "==", "accepted").stream()

        friend_cols = st.columns(3)
        idx = 0

        for r in accepted_reqs:

            r_data = r.to_dict()

            if (
                r_data["from_fullname"] ==
                st.session_state["full_name"]
                or
                r_data["to_fullname"] ==
                st.session_state["full_name"]
            ):

                friend_real_name = (
                    r_data["to_fullname"]
                    if r_data["from_fullname"] ==
                    st.session_state["full_name"]
                    else r_data["from_fullname"]
                )

                friend_nick = st.session_state[
                    "nicknames"
                ].get(friend_real_name, friend_real_name)

                with friend_cols[idx % 3]:

                    st.markdown(f"👤 **{friend_nick}**")

                    st.caption(
                        f"Real Name: @{friend_real_name}"
                    )

                    with st.expander("🏷️ Edit Nickname"):

                        new_nick = st.text_input(
                            "Set Nickname",
                            value=friend_nick,
                            key=f"nick_input_{r.id}"
                        )

                        if st.button(
                            "Save Nickname",
                            key=f"save_nick_{r.id}"
                        ):

                            if new_nick.strip():

                                st.session_state[
                                    "nicknames"
                                ][friend_real_name] = new_nick.strip()

                                save_user_session()

                                st.success("Nickname updated!")
                                st.rerun()

                    confirm_unfriend = st.checkbox(
                        "Confirm Unfriend",
                        key=f"chk_unfriend_{r.id}"
                    )

                    if st.button(
                        "Unfriend",
                        key=f"unfriend_btn_{r.id}"
                    ):

                        if confirm_unfriend:

                            db.collection(
                                "friend_requests"
                            ).document(r.id).delete()

                            st.success(
                                f"Unfriended {friend_real_name}."
                            )

                            st.rerun()

                        else:
                            st.error(
                                "Please check the confirmation box first."
                            )

                idx += 1

        # ------------------------------------------------------------
        # PENDING FRIEND REQUESTS
        # ------------------------------------------------------------
        st.subheader("Pending Requests")

        reqs = db.collection(
            "friend_requests"
        ).where(
            "to_fullname",
            "==",
            st.session_state["full_name"]
        ).where(
            "status",
            "==",
            "pending"
        ).stream()

        for r in reqs:

            r_data = r.to_dict()

            st.write(
                f"Request from: **{r_data['from_fullname']}**"
            )

            if st.button("Accept", key=f"accept_{r.id}"):

                db.collection(
                    "friend_requests"
                ).document(r.id).update({
                    "status": "accepted"
                })

                st.success("Friend added!")
                st.rerun()

    # ================================================================
    # TAB 2: CREATE STUDY GROUP
    # ================================================================
    with tab2:

        st.subheader("Create a New Study Group")

        new_group_name = st.text_input("Group Name")

        accepted_reqs = db.collection(
            "friend_requests"
        ).where("status", "==", "accepted").stream()

        friend_names = []

        for r in accepted_reqs:

            r_data = r.to_dict()

            if (
                r_data["from_fullname"] ==
                st.session_state["full_name"]
                or
                r_data["to_fullname"] ==
                st.session_state["full_name"]
            ):

                friend_name = (
                    r_data["to_fullname"]
                    if r_data["from_fullname"] ==
                    st.session_state["full_name"]
                    else r_data["from_fullname"]
                )

                friend_names.append(friend_name)

        st.write(
            f"Your Friends: "
            f"{', '.join(friend_names) if friend_names else 'None'}"
        )

        selected_friend_names = st.multiselect(
            "Add friends from your friends list",
            options=sorted(set(friend_names)),
            help="Select one or more friends here instead of typing their names.",
            key="group_friend_picker"
        )

        members_input = st.text_input(
            "Or enter friend full names manually (separate with commas)",
            placeholder="Optional — you can use the dropdown above instead"
        )

        uploaded_group_pic = st.file_uploader(
            "Group Profile Picture",
            type=["png", "jpg", "jpeg"],
            key="group_pic_upload"
        )

        if st.button("Create Group"):

            if not new_group_name.strip():
                st.error("Please provide a group name.")

            else:

                parsed_members = list(dict.fromkeys(
                    selected_friend_names + [
                        m.strip()
                        for m in members_input.split(",")
                        if m.strip()
                    ]
                ))

                invalid_members = [
                    m for m in parsed_members
                    if m not in friend_names
                ]

                if invalid_members:

                    st.error(
                        "You can only add your friends to a group! "
                        f"Not friends with: {', '.join(invalid_members)}"
                    )

                else:

                    pic_data = ""

                    if uploaded_group_pic:

                        pic_data = (
                            "data:image/png;base64,"
                            + base64.b64encode(
                                uploaded_group_pic.read()
                            ).decode("utf-8")
                        )

                    if (
                        st.session_state["full_name"]
                        not in parsed_members
                    ):
                        parsed_members.append(
                            st.session_state["full_name"]
                        )

                    group_ref = db.collection("groups").add({
                        "name": new_group_name.strip(),
                        "members": parsed_members,
                        "creator": st.session_state["full_name"],
                        "profile_pic": pic_data,
                        "created_at": datetime.now(
                            timezone.utc
                        ).isoformat()
                    })

                    st.success(
                        f"Group '{new_group_name}' created successfully!"
                    )

                    st.session_state["active_group_id"] = (
                        group_ref[1].id
                    )

                    st.rerun()

    # ================================================================
    # GROUP CHAT ROOM — SELECT A GROUP BEFORE OPENING
    # ================================================================
    st.markdown("---")
    st.subheader("Open a Study Group")
    st.caption("Choose one of your groups to open its chat room.")

    all_groups = list(
        db.collection("groups").stream()
    )

    # Only show groups the current user belongs to.
    group_options = {
        g.id: g.to_dict()["name"]
        for g in all_groups
        if (
            user_name in g.to_dict().get("members", [])
            or
            st.session_state["full_name"]
            == g.to_dict().get("creator")
        )
    }

    if not group_options:

        st.info(
            "No groups available. Go to Create Group Chat "
            "to start one!"
        )

    else:

        if (
            st.session_state.get("open_group_chat_selector")
            not in group_options
        ):
            st.session_state["open_group_chat_selector"] = (
                st.session_state.get("active_group_id")
                if st.session_state.get("active_group_id") in group_options
                else None
            )

        selected_gid = st.selectbox(
            "Select a group to open",
            options=list(group_options.keys()),
            format_func=lambda x: f"🟣 {group_options[x]}",
            index=(
                list(group_options.keys()).index(st.session_state["active_group_id"])
                if st.session_state.get("active_group_id") in group_options
                else None
            ),
            placeholder="Choose a group...",
            key="open_group_chat_selector"
        )

        if not selected_gid:
            st.info("Select a group above to open its chat room.")
            return

        st.session_state["active_group_id"] = selected_gid
        st.subheader("Study Room Chat (Tag @exegesis for help)")

        group_ref = (
            db.collection("groups")
            .document(selected_gid)
        )

        g_doc = group_ref.get()

        if g_doc.exists:

            g_info = g_doc.to_dict()

            if g_info.get("profile_pic"):
                st.image(
                    g_info["profile_pic"],
                    width=60
                )

        if check_chat_suspension():

            st.error(
                "🚫 Your chat access is suspended due to "
                "inappropriate language violations."
            )

            return

        # --------------------------------------------------------
        # DISPLAY GROUP MESSAGES
        # --------------------------------------------------------
        room_msgs = (
            group_ref.collection("messages")
            .order_by("time")
            .stream()
        )

        profile_pic_cache = {user_name: st.session_state.get("profile_pic", "")}

        for msg in room_msgs:
            m = msg.to_dict()
            sender_username = m.get("sender_username", "")
            sender_name = m.get("sender", "Unknown")

            is_me = sender_username == user_name
            chat_role = "user" if is_me else "assistant"
            sender_display = st.session_state["nicknames"].get(
                sender_name, sender_name
            )

            # Look up each sender's saved profile picture once per page run.
            msg_avatar = profile_pic_cache.get(sender_username, "")
            if not msg_avatar and sender_username and sender_username != "exegesis_ai":
                try:
                    _, sender_doc = get_user_doc(sender_username)
                    if sender_doc.exists:
                        msg_avatar = sender_doc.to_dict().get("profile_pic", "") or ""
                    profile_pic_cache[sender_username] = msg_avatar
                except Exception:
                    profile_pic_cache[sender_username] = ""

            with st.chat_message(chat_role):
                avatar_col, message_col = st.columns([0.10, 0.90])
                with avatar_col:
                    if msg_avatar:
                        st.image(msg_avatar, width=42)
                    else:
                        st.write("🤖" if sender_username == "exegesis_ai" else "👤")
                with message_col:
                    st.markdown(f"**{sender_display}**: {m.get('text', '')}")
                    if sender_username == "exegesis_ai":
                        render_answer_actions(m.get("text", ""), key=f"group_{group_ref.id}_{msg.id}")

        # --------------------------------------------------------
        # GROUP CHAT INPUT
        # --------------------------------------------------------
        st.caption("Exegesis AI can make mistakes. Double check important information.")
        # Streamlit chat_input sends the message with Enter and stays anchored at the bottom.
        group_input = st.chat_input(
            "Message group... (press Enter to send) 💬",
            key="group_chat_input_box"
        )

        if group_input:

            if detect_foul_language(group_input):

                st.warning(
                    "⚠️ Inappropriate language detected "
                    "and logged to the Admin Panel."
                )

            # SAVE USER MESSAGE
            group_ref.collection("messages").add({
                "sender": st.session_state["full_name"],
                "sender_username": user_name,
                "text": group_input,
                "time": datetime.now(
                    timezone.utc
                ).isoformat()
            })

            # ----------------------------------------------------
            # EXEGESIS AI GROUP CHAT RESPONSE
            # ----------------------------------------------------
            if "@exegesis" in group_input.lower():

                with st.spinner(
                    "Exegesis AI is thinking..."
                ):

                    try:

                        resp = requests.post(
                            "https://openrouter.ai/api/v1/chat/completions",

                            headers={
                                "Authorization": (
                                    f"Bearer {FULL_API_KEY}"
                                ),
                                "Content-Type": "application/json"
                            },

                            json={
                                "model": "openrouter/free",
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": get_active_tutor_prompt()
                                    }
                                ] + [
                                    {
                                        "role": (
                                            "assistant"
                                            if room_message.to_dict().get("sender_username") == "exegesis_ai"
                                            else "user"
                                        ),
                                        "content": str(room_message.to_dict().get("text", ""))
                                    }
                                    for room_message in list(
                                        group_ref.collection("messages")
                                        .order_by("time")
                                        .stream()
                                    )[-30:]
                                    if room_message.to_dict().get("text")
                                ]
                            },

                            timeout=60
                        )

                        g_resp_json = resp.json()

                        if not resp.ok:

                            error_data = g_resp_json.get(
                                "error",
                                {}
                            )

                            if isinstance(error_data, dict):
                                error_message = error_data.get(
                                    "message",
                                    str(error_data)
                                )
                            else:
                                error_message = str(error_data)

                            ai_help = f"The AI service returned an error (HTTP {resp.status_code}). Please try again shortly."

                        elif g_resp_json.get("choices"):

                            ai_help = (
                                g_resp_json["choices"][0]
                                ["message"].get("content")
                            )

                            if ai_help is None:
                                ai_help = ""

                            ai_help = str(ai_help).strip()

                            if not ai_help or ai_help.lower() == "none":
                                ai_help = (
                                    "I received an empty response. "
                                    "Please try again."
                                )

                        else:

                            ai_help = (
                                "I'm having trouble receiving "
                                "an AI response right now."
                            )

                    except requests.Timeout:

                        ai_help = (
                            "The AI service took too long to respond. "
                            "Please try again."
                        )

                    except requests.RequestException:
                        ai_help = "Network connection problem. Please check the internet connection and try again."

                    except Exception as e:
                        ai_help = f"Something went wrong while preparing the AI response ({type(e).__name__}). Please try again."

                # SAVE AI RESPONSE TO FIRESTORE
                group_ref.collection("messages").add({
                    "sender": "Exegesis AI 🤖",
                    "sender_username": "exegesis_ai",
                    "text": ai_help,
                    "time": datetime.now(
                        timezone.utc
                    ).isoformat()
                })

            # Refresh the selected group chat after sending the message.
            _rerun_current_chat_fragment()


# =====================================================================
# SECTION 17: EXECUTE ACTIVE WORKSPACE MODE
# =====================================================================
if st.session_state["app_mode"] == "Solo Study / AI Chat":

    render_solo_study_chat()

elif st.session_state["app_mode"] == "👥 Friends & Study Groups":

    render_group_study_chats()
