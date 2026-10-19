import base64
import json
import requests
import streamlit as st

encoded_key = "c2stb3ItdjEtNTkwZTM1MWQyMDQxMjcxZWExZjUzOTljODc4OTRlNjMyZThiMmZhNmI1NTVkNzdlMzY2NmY4ZDc1ZDgwZDhkZg=="
FULL_API_KEY = base64.b64decode(encoded_key).decode("utf-8").strip()

st.set_page_config(page_title="Exegesis AI", layout="wide")

# Initialize session state for login and history
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
if "user_name" not in st.session_state:
  st.session_state["user_name"] = ""
if "user_avatar" not in st.session_state:
  st.session_state["user_avatar"] = ""
if "chat_history" not in st.session_state:
  st.session_state["chat_history"] = []
if "messages" not in st.session_state:
  st.session_state["messages"] = [
      {
          "role": "system",
          "content": (
              "You are Exegesis AI, a scaffolded learning tutor. "
              "Understand common internet slang (like 'lol', 'rn', 'btw', etc.) "
              "naturally without treating them as typos. "
              "If the user makes spelling mistakes, gently correct them like Microsoft Word.\n\n"
              "When teaching a topic, return your response in EXACTLY this format, "
              "separated by double newlines:\n"
              "HINT1: <a subtle first hint, NO direct answer>\n"
              "HINT2: <a more direct second hint, STILL NO direct answer>\n"
              "HINT3: <a clear guiding hint, STILL NO direct answer>\n"
              "EXPLANATION: <the full clear answer and explanation>\n\n"
              "CRITICAL RULES:\n"
              "1. NEVER reveal the direct answer in HINT1, HINT2, or HINT3. "
              "The answer belongs ONLY in EXPLANATION.\n"
              "2. If the question is truly incomplete or unclear (like 'what is'), "
              "politely ask the user to write the whole question."
          ),
      }
  ]

# Google Sign-In Screen if not logged in
if not st.session_state["logged_in"]:
  st.title("=== Welcome to Exegesis AI ===")
  st.write("Please sign in with your Google account to start learning.")

  col1, col2 = st.columns([1, 2])
  with col1:
    entered_name = st.text_input("Your Name", placeholder="e.g., Alex")
    if st.button("🔵 Sign in with Google", use_container_width=True):
      if entered_name.strip() != "":
        st.session_state["logged_in"] = True
        st.session_state["user_name"] = entered_name
        # Using a standard Google-style placeholder profile picture avatar
        st.session_state["user_avatar"] = (
            "https://api.dicebear.com/7.x/avataaars/svg?seed=" + entered_name
        )
        st.rerun()
      else:
        st.warning("Please enter your name to continue.")
  st.stop()

# --- Main App (After Login) ---

# Top Left Sidebar for History Button
with st.sidebar:
  st.title("📂 History")
  if st.button("New Chat", use_container_width=True):
    if len(st.session_state["messages"]) > 1:
      st.session_state["chat_history"].append(
          st.session_state["messages"][1:]
      )
    st.session_state["messages"] = [st.session_state["messages"][0]]
    st.rerun()

  st.markdown("---")
  st.write(f"**Logged in as:** {st.session_state['user_name']}")

  if st.session_state["chat_history"]:
    st.write("Past Sessions:")
    for i, chat in enumerate(st.session_state["chat_history"]):
      preview = (
          chat[0]["content"][:20] + "..."
          if len(chat) > 0
          else f"Session {i+1}"
      )
      if st.button(f"Chat {i+1}: {preview}", key=f"hist_{i}"):
        st.session_state["messages"] = [st.session_state["messages"][0]] + chat
        st.rerun()

st.title("=== Exegesis AI ===")
st.write(f"Welcome back, {st.session_state['user_name']}!")

# Display conversation history using Google profile avatar for user
for msg in st.session_state["messages"]:
  if msg["role"] != "system":
    avatar_img = (
        st.session_state["user_avatar"] if msg["role"] == "user" else "🤖"
    )
    with st.chat_message(msg["role"], avatar=avatar_img):
      st.markdown(msg["content"])

# Gemini-style chat input bar at the bottom
user_input = st.chat_input("Ask a question or topic to learn...")

if user_input:
  with st.chat_message("user", avatar=st.session_state["user_avatar"]):
    st.markdown(user_input)
  st.session_state["messages"].append({"role": "user", "content": user_input})

  # Safety filter for violence, harm, or self-harm
  harmful_keywords = [
      "kill",
      "suicide",
      "harm",
      "hurt",
      "violence",
      "weapon",
      "gun",
      "die",
  ]
  if any(word in user_input.lower() for word in harmful_keywords):
    safety_reply = (
        "It sounds like you are going through a really tough time. "
        "Violence or harm is never the right choice. "
        "Please talk to a trusted adult, teacher, or parent right away so you can get support and stay safe."
    )
    with st.chat_message("assistant", avatar="🤖"):
      st.markdown(safety_reply)
    st.session_state["messages"].append(
        {"role": "assistant", "content": safety_reply}
    )

  else:
    with st.chat_message("assistant", avatar="🤖"):
      with st.spinner("Exegesis AI is thinking..."):
        try:
          response = requests.post(
              url="https://openrouter.ai/api/v1/chat/completions",
              headers={
                  "Authorization": f"Bearer {FULL_API_KEY}",
                  "Content-Type": "application/json",
              },
              data=json.dumps({
                  "model": "openrouter/free",
                  "messages": st.session_state["messages"],
              }),
          )

          response_data = response.json()
          ai_reply = response_data["choices"][0]["message"]["content"]

          st.markdown(ai_reply)
          st.session_state["messages"].append(
              {"role": "assistant", "content": ai_reply}
          )

        except Exception as e:
          fallback_msg = (
              "⚠️ SparkX Connection Alert!\n\n"
              "Please write out the whole question clearly so we can continue learning!"
          )
          st.markdown(fallback_msg)
          st.session_state["messages"].append(
              {"role": "assistant", "content": fallback_msg}
          )
