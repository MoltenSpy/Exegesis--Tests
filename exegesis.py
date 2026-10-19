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
if "user_gender" not in st.session_state:
  st.session_state["user_gender"] = ""
if "user_avatar" not in st.session_state:
  st.session_state["user_avatar"] = ""
if "chat_history" not in st.session_state:
  st.session_state["chat_history"] = []
if "messages" not in st.session_state:
  st.session_state["messages"] = [
      {
          "role": "system",
          "content": (
              "You are Exegesis AI, a scaffolded learning tutor acting like a friendly teacher. "
              "Understand common internet slang (like 'lol', 'rn', 'btw', etc.) naturally. "
              "If the user makes spelling mistakes, gently correct them like Microsoft Word.\n\n"
              "TEACHING RULES:\n"
              "1. Give ONLY ONE hint at a time when starting a new topic.\n"
              "2. If the user asks for the direct answer before all 3 hints have been given, you MUST say: 'Not quite, here is another hint!' and provide the next hint instead of the answer.\n"
              "3. If the user says 'I don't understand' or asks for more help, explain the concept further using simple real-world examples.\n"
              "4. If the question is truly incomplete or unclear, politely ask the user to write the whole question."
          ),
      }
  ]

# Step-by-Step Login Screen
if not st.session_state["logged_in"]:
  st.title("=== Welcome to Exegesis AI ===")
  st.write("Please enter your name to start.")

  col1, col2 = st.columns([1, 2])
  with col1:
    entered_name = st.text_input("Your Name", placeholder="e.g., Alex")

    if entered_name.strip() != "":
      st.markdown("---")
      entered_gender = st.radio("Select Gender", ["Male", "Female", "Other"])
      
      if st.button("Start Learning", use_container_width=True):
        st.session_state["logged_in"] = True
        st.session_state["user_name"] = entered_name
        st.session_state["user_gender"] = entered_gender
        
        avatar_seed = f"{entered_name}_{entered_gender}"
        st.session_state["user_avatar"] = (
            f"https://api.dicebear.com/7.x/micah/svg?seed={avatar_seed}"
        )
        st.rerun()
    else:
      st.info("Type your name above to continue.")
  st.stop()

# --- Main App (After Login) ---

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
  st.write(f"**Logged in as:** {st.session_state['user_name']} ({st.session_state['user_gender']})")

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
st.write(f"Hello {st.session_state['user_name']}, How can I help you today?")

# Display conversation history
for i, msg in enumerate(st.session_state["messages"]):
  if msg["role"] != "system":
    avatar_img = (
        st.session_state["user_avatar"] if msg["role"] == "user" else "🤖"
    )
    with st.chat_message(msg["role"], avatar=avatar_img):
      st.markdown(msg["content"])
      
      # Add a speaker button for assistant messages using browser speech synthesis
      if msg["role"] == "assistant":
        safe_text = msg["content"].replace('"', '\\"').replace('\n', ' ')
        speaker_html = f"""
        <button onclick="
            const text = `{safe_text}`;
            const utterance = new SpeechSynthesisUtterance(text);
            window.speechSynthesis.speak(utterance);
        " style="background: none; border: none; cursor: pointer; font-size: 16px; margin-top: 5px;" title="Listen">
            🔊 Listen
        </button>
        """
        st.markdown(speaker_html, unsafe_allow_html=True)

# Gemini-style chat input bar at the bottom
user_input = st.chat_input("Ask a question or topic to learn...")

if user_input:
  with st.chat_message("user", avatar=st.session_state["user_avatar"]):
    st.markdown(user_input)
  st.session_state["messages"].append({"role": "user", "content": user_input})

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
      safe_text = safety_reply.replace('"', '\\"').replace('\n', ' ')
      st.markdown(f"""
      <button onclick="
          const utterance = new SpeechSynthesisUtterance(`{safe_text}`);
          window.speechSynthesis.speak(utterance);
      " style="background: none; border: none; cursor: pointer; font-size: 16px; margin-top: 5px;">
          🔊 Listen
      </button>
      """, unsafe_allow_html=True)
      
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
          safe_text = ai_reply.replace('"', '\\"').replace('\n', ' ')
          st.markdown(f"""
          <button onclick="
              const utterance = new SpeechSynthesisUtterance(`{safe_text}`);
              window.speechSynthesis.speak(utterance);
          " style="background: none; border: none; cursor: pointer; font-size: 16px; margin-top: 5px;">
              🔊 Listen
          </button>
          """, unsafe_allow_html=True)

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
