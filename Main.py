import os
import streamlit as st
import bcrypt
from dotenv import load_dotenv

from src.agent import BaseballBuddy

load_dotenv()

st.set_page_config(page_title="Baseball Buddy")
st.title("Baseball Buddy")
st.caption("Ask me questions about MLB hitters!")


def get_password_hash():
    try:
        if "HASHED_PASSWORD" in st.secrets:
            return st.secrets["HASHED_PASSWORD"]
    except Exception:
        # No secrets file found locally, fall back to .env
        pass
    return os.getenv("HASHED_PASSWORD")


def check_password():
    if st.session_state.get("authed"):  # this will reset when the page is refreshed for now
        return True

    stored_hash = get_password_hash()
    pw = st.text_input("Password", type="password")
    if pw:
        if bcrypt.checkpw(pw.encode(), stored_hash.encode()):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False


if not check_password():
    st.stop()


def get_api_key():
    try:
        if "API_KEY" in st.secrets:
            return st.secrets["API_KEY"]
    except Exception:
        # should never reach this path once deployed
        pass
    return os.getenv("API_KEY")


# load from the env if running locally, but should come from streamlit secrets
api_key = get_api_key()
if not api_key:
    st.error("API KEY is missing, check to make sure you have correctly uploaded it to your Streamlit App's Secrets")
    st.stop()

if "agent" not in st.session_state:
    st.session_state.agent = BaseballBuddy(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state.messages = []

# main application loop !!!!
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant" and msg.get("model"):
        st.caption(f"Answered with `{msg['model']}`")

if prompt := st.chat_input("Try: How many HR did Aaron Judge hit in 2022?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Baseball Buddy is thinking..."):
            agent = st.session_state.agent
            agent.last_model_used = None
            try:
                reply = agent.ask(prompt)
            except Exception as e:
                reply = f"Something went wrong: {e}"
            model_used = agent.last_model_used

        st.markdown(reply)
        if model_used:
            st.caption(f"Answered by `{model_used}`")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": reply,
            "model": model_used,
        }
    )
