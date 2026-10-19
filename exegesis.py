import base64
import json
import requests
import streamlit as st

encoded_key = "c2stb3ItdjEtNTkwZTM1MWQyMDQxMjcxZWExZjUzOTljODc4OTRlNjMyZThiMmZhNmI1NTVkNzdlMzY2NmY4ZDc1ZDgwZDhkZg=="
FULL_API_KEY = base64.b64decode(encoded_key).decode("utf-8").strip()

st.title("=== Exegesis AI ===")
st.write("Your personal scaffolded learning tutor!")

# Initialize chat history
if "messages" not in st.session_state:
  st.session_state["messages"] = [
      {
          "role": "system",
          "content": (
              "You are Exegesis AI, a scaffolded learning tutor. "
              "When teaching a topic, return your response in EXACTLY this format, separated by double newlines:\n"
              "HINT1: <a subtle first hint, NO direct answer>\n"
              "HINT2: <a more direct second hint, STILL NO direct answer>\n"
              "HINT3: <a clear guiding hint, STILL NO direct answer>\n"
              "EXPLANATION: <the full clear answer and explanation>\n\n"
              "CRITICAL RULES:\n"
              "1. NEVER reveal the direct answer in HINT1, HINT2, or HINT3. The answer belongs ONLY in EXPLANATION.\n"
              "2. If the user asks for dangerous, illegal, or harmful things (like weapons, violence, or self-harm), "
              "refuse immediately and provide a supportive message or suggest talking to a trusted adult.\n"
              "3. If the question is incomplete or unclear (like 'what is'), politely ask the user to write the whole question."
          ),
      }
  ]

# Display conversation history
for msg in st.session_state["messages"]:
  if msg["role"] != "system":
    with st.chat_message(msg["role"]):
      st.markdown(msg["content"])

# Gemini-style chat input bar at the bottom
user_input = st.chat_input("Ask a question or topic to learn...")

if user_input:
  st.chat_message("user").markdown(user_input)
  st.session_state["messages"].append({"role": "user", "content": user_input})

  with st.chat_message("assistant"):
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
            "⚠️ SparkX Live Connection Alert!\n\n"
            "Please write out the whole question clearly so we can continue learning!"
        )
        st.markdown(fallback_msg)
        st.session_state["messages"].append(
            {"role": "assistant", "content": fallback_msg}
        )
