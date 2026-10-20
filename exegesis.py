import json
import re
import requests
import streamlit as st
from streamlit_google_auth import Authenticate

# --- Google Credentials File Setup ---
google_creds = {
    "web": {
        "client_id": st.secrets["google_auth"]["client_id"],
        "client_secret": st.secrets["google_auth"]["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

with open("google-login.json", "w") as f:
    json.dump(google_creds, f)

st.set_page_config(page_title="Exegesis AI", layout="wide")

# --- Initialize Authenticator ---
authenticator = Authenticate(
    secret_credentials_path="google-login.json",
    cookie_name="exegesis_cookie",
    cookie_key="super_secret_random_key",
    redirect_uri="https://exegesis-ai.streamlit.app",
)

FULL_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --- System Prompt Engineering Blocks ---
HINT_GENERATOR_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. "
    "Use a scaffolding method: guide the student step by step instead of giving the answer straight away.\n\n"
    "Rules:\n"
    "- Use simple words and short sentences. Add a small everyday example where it helps.\n"
    "- HINT1 is a gentle nudge that points to the key idea. It must NOT contain the answer.\n"
    "- HINT2 is more direct and names the method, rule or concept to use. It must NOT contain the final answer.\n"
    "- HINT3 is almost the full path (for example the first steps of the working) but still leaves the last step to the student.\n"
    "- EXPLANATION gives the complete answer with clear step-by-step reasoning, then one short line to remember.\n"
    "- Keep each hint to 1-2 sentences.\n"
    "- Write plain text only. No markdown, no bullet points, no bold, and no extra headings.\n"
    "- Reply in the same language as the student's question.\n\n"
    "Return your response in EXACTLY this format, with each section separated by a blank line "
    "and nothing before HINT1 or after the explanation:\n"
    "HINT1: <gentle nudge>\n\n"
    "HINT2: <more direct hint>\n\n"
    "HINT3: <almost the full path>\n\n"
    "EXPLANATION: <full answer with step-by-step reasoning>"
)

TUTOR_CHAT_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. "
    "The student has already seen hints and is now asking follow-up questions about the same topic. "
    "Answer clearly in simple words, in a few short sentences. "
    "If the student seems to be working on a problem, guide them with a hint or a question "
    "before giving the final answer. Write plain text only, with no markdown."
)

FRIEND_CHAT_PROMPT = (
    "You are Exegesis AI, but right now you are acting as a warm, comforting, and empathetic friend to the student. "
    "The student shared that they are feeling sad, lonely, or upset. Forget about giving school hints or teaching lessons right now. "
    "Focus entirely on listening, being supportive, and speaking like a kind peer or trusted friend. "
    "Keep your words simple, warm, and highly comforting. Keep responses relatively short (2-3 sentences)."
)

DYNAMIC_SAFETY_PROMPT = (
    "You are a compassionate safety responder for an educational student application. "
    "The user has entered a message that indicates potential harm, self-harm, slang variations of violence (e.g. unalive), or dangerous actions. "
    "Analyze their exact situation and provide a unique, highly specific response. "
    "Do NOT use a generic copy-pasted warning message. Address their context with extreme empathy, "
    "gently explain why you cannot assist with harm or dangerous methods, and immediately urge them to connect with "
    "a trusted family member, counselor, teacher, or helpline. Keep it brief (2-3 sentences) and written in plain language appropriate for youth."
)

# --- Persistent State Controls Initialization ---
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "current_topic" not in st.session_state:
    st.session_state["current_topic"] = None
if "hints" not in st.session_state:
    st.session_state["hints"] = {}
if "explanation" not in st.session_state:
    st.session_state["explanation"] = ""
if "attempt" not in st.session_state:
    st.session_state["attempt"] = 1
if "show_explanation" not in st.session_state:
    st.session_state["show_explanation"] = False
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "is_sad_mode" not in st.session_state:
    st.session_state["is_sad_mode"] = False

# --- Render Authorization Wall ---
if not st.session_state.get("connected", False):
    st.title("=== Welcome to Exegesis AI ===")
    st.write("Please log in with Google to start learning.")
    authenticator.login()
    st.stop()

user_info = st.session_state.get("user_info", {})
user_name = user_info.get("name", "Friend")

# --- Navigation Sidebar Interface Engine ---
with st.sidebar:
    st.title("📂 History")
    if st.button("New Chat", use_container_width=True):
        if st.session_state["current_topic"] or st.session_state["messages"]:
            st.session_state["chat_history"].append({
                "topic": st.session_state["current_topic"],
                "hints": st.session_state["hints"],
                "explanation": st.session_state["explanation"],
                "attempt": st.session_state["attempt"],
                "show_explanation": st.session_state["show_explanation"],
                "messages": st.session_state["messages"],
                "is_sad_mode": st.session_state["is_sad_mode"]
            })
        st.session_state["current_topic"] = None
        st.session_state["hints"] = {}
        st.session_state["explanation"] = ""
        st.session_state["attempt"] = 1
        st.session_state["show_explanation"] = False
        st.session_state["messages"] = []
        st.session_state["is_sad_mode"] = False
        st.rerun()

    st.markdown("---")
    st.write(f"**Logged in as:** {user_name}")
    if st.button("Log out", use_container_width=True):
        authenticator.logout()

    if st.session_state["chat_history"]:
        st.write("Past Sessions:")
        for i, old_session in enumerate(st.session_state["chat_history"]):
            if old_session.get("is_sad_mode"):
                label = f"❤️ Chat {i+1}: Friendly Support"
            else:
                topic_title = old_session["topic"] if old_session["topic"] else "Learning Space"
                label = f"📚 Chat {i+1}: {topic_title[:15]}..."
            
            if st.button(label, key=f"hist_{i}", use_container_width=True):
                st.session_state["current_topic"] = old_session["topic"]
                st.session_state["hints"] = old_session["hints"]
                st.session_state["explanation"] = old_session["explanation"]
                st.session_state["attempt"] = old_session["attempt"]
                st.session_state["show_explanation"] = old_session["show_explanation"]
                st.session_state["messages"] = old_session["messages"]
                st.session_state["is_sad_mode"] = old_session.get("is_sad_mode", False)
                st.rerun()

# --- Security Scanner Infrastructure ---
def detect_harmful_keywords(text):
    harmful_keywords = [
        "kill", "suicide", "harm", "hurt", "violence", "weapon", "gun", "die", 
        "unalive", "end myself", "hurt someone", "kill someone", "attack"
    ]
    cleaned_text = text.lower()
    for word in harmful_keywords:
        if re.search(r'\b' + re.escape(word) + r'\b', cleaned_text):
            return True
    return False

def generate_dynamic_safety_response(violation_text):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": DYNAMIC_SAFETY_PROMPT},
                    {"role": "user", "content": f"User's flagged input: {violation_text}"}
                ]
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return (
            "I can hear that things are incredibly intense right now, but I cannot assist with harm or violent methods. "
            "Please reach out to a counselor, teacher, parent, or trusted adult immediately so you can get the care you deserve."
        )

def check_sadness(text):
    sad_keywords = ["sad", "lonely", "down", "upset", "cry", "crying", "depressed", "feel bad", "unhappy", "stressed"]
    return any(word in text.lower() for word in sad_keywords)
st.title("=== Exegesis AI ===")

if st.session_state["current_topic"] == "Safety Intercept Notice":
    st.write("Exegesis space is working below to provide direct support.")
elif st.session_state["is_sad_mode"]:
    st.write(f"Hey {user_name}, I am here for you as a friend. What's on your mind today?")
else:
    st.write(f"Hello {user_name}, How can I help you today?")

user_input = st.chat_input("Ask a question or topic to learn...")

if user_input:
    # 1. Action Layer: Intercept Severe Safety Conflicts First
    if detect_harmful_keywords(user_input):
        with st.spinner("Processing custom space configurations..."):
            safety_reply = generate_dynamic_safety_response(user_input)
        st.session_state["messages"].append({"role": "user", "content": user_input})
        st.session_state["messages"].append({"role": "assistant", "content": safety_reply})
        st.session_state["current_topic"] = "Safety Intercept Notice"
        st.rerun()

    # 2. Action Layer: Check for Upset or Sad Context Shifting
    if check_sadness(user_input) and not st.session_state["is_sad_mode"]:
        st.session_state["is_sad_mode"] = True
        st.session_state["current_topic"] = "Friendship Conversation Space"

    # CASE 1: Active Support Chat Mode Flow
    if st.session_state["is_sad_mode"]:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        chat_context = [{"role": "system", "content": FRIEND_CHAT_PROMPT}]
        chat_context.extend(st.session_state["messages"])
        
        with st.spinner("Listening..."):
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "openrouter/free", "messages": chat_context},
                    timeout=20,
                )
                response.raise_for_status()
                ai_reply = response.json()["choices"][0]["message"]["content"].strip()
                st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
            except Exception:
                st.session_state["messages"].append({"role": "assistant", "content": "I'm right here with you. Please go on."})
        st.rerun()

    # CASE 2: Initialize Core Scaffolding Templates for New Concepts
    elif st.session_state["current_topic"] is None or st.session_state["current_topic"] == "Safety Intercept Notice":
        st.session_state["current_topic"] = user_input
        st.session_state["attempt"] = 1
        st.session_state["show_explanation"] = False
        st.session_state["messages"] = []
        
        with st.spinner("Exegesis AI is preparing your hints..."):
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "openrouter/free",
                        "messages": [
                            {"role": "system", "content": HINT_GENERATOR_PROMPT},
                            {"role": "user", "content": f"Help me learn about: {user_input}"}
                        ]
                    },
                    timeout=20,
                )
                response.raise_for_status()
                response_content = response.json()["choices"][0]["message"]["content"]
                
                pattern = r"(HINT1|HINT2|HINT3|EXPLANATION):\s*(.*?)(?=\n\s*(?:HINT1|HINT2|HINT3|EXPLANATION):|\Z)"
                sections = {label: text.strip() for label, text in re.findall(pattern, response_content, re.S)}
                
                st.session_state["hints"] = {i: sections[f"HINT{i}"] for i in (1, 2, 3) if f"HINT{i}" in sections}
                st.session_state["explanation"] = sections.get("EXPLANATION", "")
                
                if len(st.session_state["hints"]) < 3 or not st.session_state["explanation"]:
                    raise ValueError("Template build error from server.")
            except Exception:
                st.error("Connection alert. Please resubmit the question clearly.")
                st.session_state["current_topic"] = None
        st.rerun()

    # CASE 3: Standard Academic Conversation Loop
    else:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        chat_context = [
            {"role": "system", "content": TUTOR_CHAT_PROMPT},
            {"role": "user", "content": f"Help me learn about: {st.session_state['current_topic']}"}
        ]
        if st.session_state["explanation"]:
            chat_context.append({"role": "assistant", "content": f"Context Concept: {st.session_state['explanation']}"})
        chat_context.extend(st.session_state["messages"])
        
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {FULL_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "openrouter/free", "messages": chat_context},
                    timeout=20,
                )
                response.raise_for_status()
                ai_reply = response.json()["choices"][0]["message"]["content"].strip()
                st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
            except Exception:
                st.session_state["messages"].append({"role": "assistant", "content": "⚠️ Connection alert! Please repeat clearly."})
        st.rerun()

# --- UI Render Engine Loop Matrix ---
if st.session_state["current_topic"] == "Safety Intercept Notice" or st.session_state["is_sad_mode"]:
    st.markdown("---")
    if st.session_state["is_sad_mode"]:
        st.info("❤️ **Friendship Support Active:** Chatting freely without structural study constraints.")
        
    for msg in st.session_state["messages"]:
        avatar_img = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar_img):
            st.markdown(msg["content"])

elif st.session_state["current_topic"]:
    st.markdown(f"### 📝 Target Concept: *{st.session_state['current_topic']}*")
    hints = st.session_state["hints"]
    current_attempt = st.session_state["attempt"]
    
    st.markdown("---")
    for i in range(1, min(current_attempt, 3) + 1):
        if i in hints:
            st.info(f"💡 **Hint {i}:** {hints[i]}")
            
    if current_attempt < 3:
        st.progress(current_attempt / 3, text=f"Progressing through scaffolds: Level {current_attempt} of 3")
        if st.button("Need another hint ➡️"):
            st.session_state["attempt"] += 1
            st.rerun()
    elif not st.session_state["show_explanation"]:
        if st.button("🔓 Reveal Full Explanation"):
            st.session_state["show_explanation"] = True
            st.rerun()
            
    if st.session_state["show_explanation"]:
        st.success(f"✏️ **Complete Breakdown:**\n\n{st.session_state['explanation']}")
        st.markdown("---")
        st.subheader("💬 Follow-up Questions")
        
        for msg in st.session_state["messages"]:
            avatar_img = "🤖" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar_img):
                st.markdown(msg["content"])
