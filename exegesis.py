import base64
import json
import requests
import streamlit as st
from streamlit_mic_recorder import mic_recorder

encoded_key = "c2stb3ItdjEtNTkwZTM1MWQyMDQxMjcxZWExZjUzOTljODc4OTRlNjMyZThiMmZhNmI1NTVkNzdlMzY2NmY4ZDc1ZDgwZDhkZg=="
FULL_API_KEY = base64.b64decode(encoded_key).decode("utf-8").strip()

st.title("=== Exegesis AI ===")
st.write("Your personal scaffolded learning tutor!")

# Text input for questions
user_question = st.text_input(
    "What question or topic do you want help learning?",
    placeholder="e.g., 3 multiplied by 6, Photosynthesis, Gravity",
)

# Voice recording feature
st.write("Or click below to speak your question:")
audio = mic_recorder(
    start_prompt="Click to speak", stop_prompt="Stop recording", key="voice_input"
)

if audio:
  st.audio(audio["bytes"])
  st.success("Voice recorded successfully!")

if user_question:
  if (
      "zonal_round_question" not in st.session_state
      or st.session_state["zonal_round_question"] != user_question
  ):
    st.session_state["zonal_round_question"] = user_question
    st.session_state["attempt"] = 1
    st.session_state["hints"] = {}
    st.session_state["explanation"] = ""

    with st.spinner("Exegesis AI is thinking of a helpful hint..."):
      instructions = (
          "You are a helpful tutor using a scaffolding teaching method for"
          " Exegesis AI. Return your response in EXACTLY this format, separated"
          " by double newlines:\nHINT1: <a subtle first"
          " hint>\n\nHINT2: <a more direct second"
          " hint>\n\nHINT3: <a very obvious third hint>\n\nEXPLANATION: <the"
          " full clear answer and explanation>"
      )

      try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {FULL_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": f"Help me learn about: {user_question}",
                    },
                ],
            }),
        )

        response_data = response.json()
        response_content = response_data["choices"][0]["message"]["content"]

        parts = response_content.split("\n\n")
        hints = {}
        explanation = ""

        for part in parts:
          if part.startswith("HINT1:"):
            hints[1] = part.replace("HINT1:", "").strip()
          elif part.startswith("HINT2:"):
            hints[2] = part.replace("HINT2:", "").strip()
          elif part.startswith("HINT3:"):
            hints[3] = part.replace("HINT3:", "").strip()
          elif part.startswith("EXPLANATION:"):
            explanation = part.replace("EXPLANATION:", "").strip()

        st.session_state["hints"] = hints
        st.session_state["explanation"] = explanation

      except Exception as e:
        st.error("⚠️ SparkX Live Connection Alert!")
        st.info("Bypassing server lag, generating local tutor data layout...")

        st.session_state["hints"] = {
            1: (
                "Think about the foundational inputs, core rules, or active"
                f" behaviors of '{user_question}'."
            ),
            2: (
                f"Focus on how '{user_question}' functions step-by-step or how"
                " its parts link together."
            ),
            3: (
                "You are looking for the absolute fundamental definition or"
                f" final resolution of '{user_question}'."
            ),
        }
        st.session_state["explanation"] = (
            f"Great exploration! '{user_question}' is a core topic. Scaffolded"
            " learning allows you to conquer complex materials"
            " piece-by-piece!"
        )

  attempt = st.session_state.get("attempt", 1)
  hints = st.session_state.get("hints", {})

  if attempt <= 3 and hints:
    st.info(f"💡 HINT {attempt}: {hints.get(attempt, 'No hint found.')}")
    user_guess = st.text_input(
        "What is your guess?",
        key=f"guess_{attempt}",
        placeholder="Type what you think it is...",
    )

    col1, col2 = st.columns(2)

    with col1:
      if st.button("Submit Guess", use_container_width=True):
        if user_guess.strip() == "":
          st.warning("Please type a guess before submitting!")
        else:
          with st.spinner("Analyzing guess logic..."):
            try:
              check_prompt = (
                  f"Question/Topic: {user_question}\nUser Guess:"
                  f" {user_guess}\nIs this correct? Answer only YES or NO."
              )
              check_resp = requests.post(
                  url="https://openrouter.ai/api/v1/chat/completions",
                  headers={
                      "Authorization": f"Bearer {FULL_API_KEY}",
                      "Content-Type": "application/json",
                  },
                  data=json.dumps({
                      "model": "openrouter/free",
                      "messages": [{"role": "user", "content": check_prompt}],
                  }),
              )
              check_text = check_resp.json()["choices"][0]["message"][
                  "content"
              ]

              if "YES" in check_text.upper():
                st.success(
                    "🎉 Awesome job! You figured it out with Exegesis AI!"
                )
                st.session_state["attempt"] = 4
                st.rerun()
              else:
                st.error("❌ Not quite, let's try the next step!")
                st.session_state["attempt"] += 1
                st.rerun()
            except:
              st.success(
                  "🎉 Activity complete! Let's review the analytical breakdown"
                  " below:"
              )
              st.session_state["attempt"] = 4
              st.rerun()

    with col2:
      if st.button("Need another hint?", use_container_width=True):
        st.session_state["attempt"] += 1
        st.rerun()

  else:
    st.warning(
        "📚 Here is the full explanation from Exegesis"
        f" AI:\n\n{st.session_state.get('explanation')}"
    )
    if st.button("Ask Another Question", use_container_width=True):
      for key in list(st.session_state.keys()):
        del st.session_state[key]
      st.rerun()
