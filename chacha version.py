import streamlit as st
import re
import requests
import base64

encoded_key = "c2stb3ItdjEtNTkwZTM1MWQyMDQxMjcxZWExZjUzOTljODc4OTRlNjMyZThiMmZhNmI1NTVkNzdlMzY2NmY4ZDc1ZDgwZDhkZg=="
FULL_API_KEY = base64.b64decode(encoded_key).decode("utf-8").strip()

st.set_page_config(page_title="Exegesis AI", page_icon="🎓")

CHAT_PROMPT = (
    "You are Exegesis AI, a friendly tutor for school students. "
    "The student has already seen hints and is now asking follow-up questions about the same topic. "
    "Answer clearly in simple words, in a few short sentences. "
    "If the student seems to be working on a problem, guide them with a hint or a question "
    "before giving the final answer. Write plain text only, with no markdown."
)


def ask_followup(topic, explanation, chat):
    messages = [
        {"role": "system", "content": CHAT_PROMPT},
        {"role": "user", "content": f"Help me learn about: {topic}"},
    ]
    if explanation:
        messages.append({"role": "assistant", "content": explanation})
    messages += chat

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {FULL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": "openrouter/free", "messages": messages},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


st.title("🎓 Exegesis AI")
st.caption("Your personal scaffolded learning tutor")

with st.sidebar:
    st.header("How it works")
    st.markdown(
        "1. Ask about any topic\n2. Reveal hints one by one\n3. See the full answer\n4. Keep chatting with follow-up questions"
    )
    if st.button("Start a new topic"):
        st.session_state.clear()
        st.rerun()

prompt = st.chat_input("Type a topic or question...")

# The first message sets the topic; later messages are follow-ups.
has_topic = "zonal_round_question" in st.session_state
user_question = st.session_state["zonal_round_question"] if has_topic else prompt
follow_up = prompt if has_topic else None

if user_question:
    with st.chat_message("user"):
        st.write(user_question)

    if "zonal_round_question" not in st.session_state or st.session_state.get("retry"):
        st.session_state["zonal_round_question"] = user_question
        st.session_state["attempt"] = 1
        st.session_state["hints"] = {}
        st.session_state["explanation"] = ""
        st.session_state["show_explanation"] = False
        st.session_state["error"] = False
        st.session_state["retry"] = False
        st.session_state["chat"] = []

        with st.spinner("Exegesis AI is thinking of a helpful hint..."):
            instructions = (
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
                "- Reply in the same language as the student's question.\n"
                "- If the topic is not suitable for students or is not a learning topic, "
                "reply in the same format with hints that gently guide the student back to studying.\n\n"
                "Return your response in EXACTLY this format, with each section separated by a blank line "
                "and nothing before HINT1 or after the explanation:\n"
                "HINT1: <gentle nudge>\n\n"
                "HINT2: <more direct hint>\n\n"
                "HINT3: <almost the full path>\n\n"
                "EXPLANATION: <full answer with step-by-step reasoning>"
            )

            try:
                # OpenRouter free auto-router model
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {FULL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "openrouter/free",
                        "messages": [
                            {"role": "system", "content": instructions},
                            {
                                "role": "user",
                                "content": f"Help me learn about: {user_question}",
                            },
                        ],
                    },
                    timeout=20,
                )
                response.raise_for_status()

                response_data = response.json()
                response_content = response_data["choices"][0]["message"]["content"]

                # Each section ends where the next label begins, so blank lines
                # inside a hint no longer break parsing.
                pattern = (
                    r"(HINT1|HINT2|HINT3|EXPLANATION):\s*(.*?)"
                    r"(?=\n\s*(?:HINT1|HINT2|HINT3|EXPLANATION):|\Z)"
                )
                sections = {
                    label: text.strip()
                    for label, text in re.findall(pattern, response_content, re.S)
                }
                hints = {
                    i: sections[f"HINT{i}"] for i in (1, 2, 3) if f"HINT{i}" in sections
                }
                explanation = sections.get("EXPLANATION", "")

                if len(hints) < 3 or not explanation:
                    raise ValueError("Response was missing hints or explanation")

                st.session_state["hints"] = hints
                st.session_state["explanation"] = explanation

            except (requests.RequestException, KeyError, IndexError, ValueError):
                st.session_state["error"] = True
                st.session_state["hints"] = {}
                st.session_state["explanation"] = ""

    hints = st.session_state.get("hints", {})
    attempt = st.session_state.get("attempt", 1)

    with st.chat_message("assistant"):
        if st.session_state.get("error"):
            st.warning(
                "Sorry, the tutor could not be reached right now. "
                "Please check your internet connection and try again."
            )
            if st.button("Try again"):
                st.session_state["retry"] = True
                st.rerun()

        for i in range(1, min(attempt, 3) + 1):
            if i in hints:
                st.info(f"💡 Hint {i}: {hints[i]}")

        if hints:
            if attempt < 3:
                st.progress(attempt / 3, text=f"Hint {attempt} of 3")
                if st.button("Need another hint"):
                    st.session_state["attempt"] += 1
                    st.rerun()
            elif st.button("Show full explanation"):
                st.session_state["show_explanation"] = True

            if st.session_state.get("show_explanation"):
                st.success(st.session_state["explanation"])

    for message in st.session_state["chat"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if follow_up and hints:
        with st.chat_message("user"):
            st.write(follow_up)

        with st.chat_message("assistant"):
            reply = None
            with st.spinner("Thinking..."):
                try:
                    reply = ask_followup(
                        user_question,
                        st.session_state["explanation"],
                        st.session_state["chat"]
                        + [{"role": "user", "content": follow_up}],
                    )
                except (requests.RequestException, KeyError, IndexError):
                    st.warning("Could not send your message. Please try again.")
            if reply:
                st.write(reply)
                st.session_state["chat"] += [
                    {"role": "user", "content": follow_up},
                    {"role": "assistant", "content": reply},
                ]
else:
    st.info(
        "👋 Type a topic or question below, e.g. 3 multiplied by 6, Photosynthesis, Gravity"
    )
