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
    st.error(f"⚠️ Firebase connection error: {e}")
    st.stop()


# =====================================================================
# SECTION 3: CORE DATABASE & SESSION UTILITY FUNCTIONS
# =====================================================================
def get_user_doc(username):
    """Retrieves a user document reference and snapshot from Firestore."""
    doc_ref = db.collection("users").document(username)
    doc = doc_ref.get()
    return doc_ref, doc


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
    "7. If a request is broad, suggest a useful starting structure and explain how the student can develop it; offer to review or improve the student's own draft."
)


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


# =====================================================================
# SECTION 7: LOGIN & REGISTRATION
# =====================================================================
def render_auth_screen():
    st.title("=== Welcome to Exegesis AI ===")
    auth_mode = st.radio(
        "Choose Action",
        ["Log In", "Create Account"],
        horizontal=True
    )

    col1, col2 = st.columns(2)

    with col1:
        entered_name = st.text_input(
            "Username",
            placeholder="Enter your username"
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
            placeholder="Enter your password"
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
            if acc_choice == "School Account":
                school_name = st.text_input("School Name")

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

                elif (
                    acc_choice == "Parent Portal"
                    and not child_usernames_input.strip()
                ):
                    st.error("Please enter at least one child's username.")

                else:
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
                            "school_name": school_name,
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
                clean_name = entered_name.strip()
                doc_ref, doc = get_user_doc(clean_name)

                if doc.exists:
                    user_data = doc.to_dict()

                    if user_data.get("password") == entered_pass:
                        st.session_state["user_name"] = clean_name
                        st.session_state["full_name"] = user_data.get(
                            "full_name", clean_name
                        )
                        st.session_state["account_type"] = user_data.get(
                            "account_type", "Student Portal"
                        )
                        st.session_state["parent_mode"] = user_data.get(
                            "parent_mode", ""
                        )

                        existing_msgs = user_data.get("messages", [])
                        existing_history = user_data.get("chat_history", [])

                        if existing_msgs:
                            chat_title = (
                                existing_msgs[0]["content"][:25] + "..."
                            )
                            existing_history.append({
                                "title": chat_title,
                                "messages": existing_msgs,
                                "time": datetime.now(timezone.utc).isoformat()
                            })

                        st.session_state["messages"] = []
                        st.session_state["chat_history"] = existing_history
                        st.session_state["friends"] = user_data.get(
                            "friends", []
                        )
                        st.session_state["nicknames"] = user_data.get(
                            "nicknames", {}
                        )
                        st.session_state["user_city"] = user_data.get(
                            "user_city", "London"
                        )
                        st.session_state["profile_pic"] = user_data.get(
                            "profile_pic", ""
                        )
                        st.session_state["logged_in"] = True

                        save_user_session()
                        st.rerun()

                    else:
                        st.error("Invalid username or password.")
                else:
                    st.error("Invalid username or password.")

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
# SECTION 14: TEACHER PORTAL DASHBOARD VIEW
# =====================================================================
if user_role == "Teacher Portal":

    st.title(
        f"🍎 Teacher Dashboard "
        f"({st.session_state['full_name']})"
    )

    t_tab1, t_tab2 = st.tabs([
        "📩 Parent Messages",
        "📋 Class Assignments"
    ])

    with t_tab1:
        st.subheader("Messages from Parents")

        p_msgs = db.collection("teacher_parent_messages").stream()

        for pm in p_msgs:
            pm_data = pm.to_dict()

            st.info(
                f"**From:** {pm_data.get('parent', 'Parent')}\n\n"
                f"**Message:** {pm_data.get('message')}"
            )

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
# SECTION 15: MAIN APPLICATION - SOLO STUDY & AI TUTOR CHAT
# =====================================================================
def _streamlit_fragment(func):
    """Use Streamlit fragments when supported; otherwise keep normal behavior."""
    fragment_api = getattr(st, "fragment", None)
    return fragment_api(func) if callable(fragment_api) else func


def _rerun_current_chat_fragment():
    """Refresh only the active chat fragment on modern Streamlit versions."""
    if callable(getattr(st, "fragment", None)):
        st.rerun(scope="fragment")
    else:
        st.rerun()


@_streamlit_fragment
def render_solo_study_chat():

    st.title(f"Hello {st.session_state['full_name']}!")

    st.subheader("What's on your mind today? 😊")

    st.caption(
        "💡 Emojis: On laptop/PC press Windows + . "
        "to open emojis!"
    )

    # ---------------------------------------------------------------
    # DISPLAY EXISTING CHAT MESSAGES
    # ---------------------------------------------------------------
    for msg in st.session_state["messages"]:

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
    # Streamlit chat_input submits the message when the user presses Enter.
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
            file_bytes = file_obj.read()

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
                "content": TUTOR_PROMPT
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

                    ai_reply = (
                        f"⚠️ OpenRouter error ({resp.status_code}): "
                        f"{error_message}"
                    )

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
                    ai_reply = (
                        "⚠️ No AI response received. "
                        f"Details: {response_json}"
                    )

            except requests.Timeout:
                ai_reply = (
                    "⚠️ The AI service took too long to respond. "
                    "Please try again."
                )

            except requests.RequestException as e:
                ai_reply = (
                    f"⚠️ Network connection problem: {e}"
                )

            except Exception as e:
                ai_reply = (
                    f"⚠️ Unexpected AI error: {e}"
                )

        # -----------------------------------------------------------
        # IMPORTANT FIX: SAVE AND DISPLAY AI RESPONSE IMMEDIATELY
        # -----------------------------------------------------------
        st.session_state["messages"].append({
            "role": "assistant",
            "content": ai_reply
        })

        with st.chat_message("assistant"):
            st.markdown(ai_reply)

        save_user_session()
        # =====================================================================
# SECTION 16: COLLABORATIVE STUDY GROUPS & NICKNAMES
# =====================================================================
@_streamlit_fragment
def render_group_study_chats():

    st.title(
        f"Hello {st.session_state['full_name']}! "
        "👥 Friends & Study Groups"
    )

    tab1, tab2, tab3 = st.tabs([
        "Friend Requests & Nicknames",
        "Create Group Chat",
        "Active Group Chat Room"
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

        members_input = st.text_input(
            "Member Full Names (separate with commas)"
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

                parsed_members = [
                    m.strip()
                    for m in members_input.split(",")
                    if m.strip()
                ]

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
    # TAB 3: ACTIVE GROUP CHAT
    # ================================================================
    with tab3:

        st.subheader(
            "Study Room Chat (Tag @exegesis for help)"
        )

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

            selected_gid = st.selectbox(
                "Select Group Chat",
                options=list(group_options.keys()),
                format_func=lambda x: (
                    f"🟣 {group_options[x]}"
                ),
                index=(
                    list(group_options.keys()).index(
                        st.session_state["active_group_id"]
                    )
                    if st.session_state["active_group_id"]
                    in group_options
                    else 0
                )
            )

            st.session_state["active_group_id"] = selected_gid

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

            # --------------------------------------------------------
            # GROUP CHAT INPUT
            # --------------------------------------------------------
            # Streamlit chat_input submits the message when the user presses Enter.
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
                                            "content": TUTOR_PROMPT
                                        },
                                        {
                                            "role": "user",
                                            "content": group_input
                                        }
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

                                ai_help = (
                                    f"OpenRouter error "
                                    f"({resp.status_code}): "
                                    f"{error_message}"
                                )

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

                        except requests.RequestException as e:

                            ai_help = (
                                f"Network connection problem: {e}"
                            )

                        except Exception as e:

                            ai_help = (
                                f"Unexpected AI error: {e}"
                            )

                    # SAVE AI RESPONSE TO FIRESTORE
                    group_ref.collection("messages").add({
                        "sender": "Exegesis AI 🤖",
                        "sender_username": "exegesis_ai",
                        "text": ai_help,
                        "time": datetime.now(
                            timezone.utc
                        ).isoformat()
                    })

                # Refresh only this chat fragment so the whole page does not flash.
                _rerun_current_chat_fragment()


# =====================================================================
# SECTION 17: EXECUTE ACTIVE WORKSPACE MODE
# =====================================================================
if st.session_state["app_mode"] == "Solo Study / AI Chat":

    render_solo_study_chat()

elif st.session_state["app_mode"] == "👥 Friends & Study Groups":

    render_group_study_chats()
