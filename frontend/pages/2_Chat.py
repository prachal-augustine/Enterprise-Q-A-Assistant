import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Chat / Q&A", page_icon="💬", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please log in first.")
    st.stop()

token = st.session_state.token
headers = {"Authorization": f"Bearer {token}"}

st.title("💬 Document Q&A")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("Sources"):
                for cit in msg["citations"]:
                    st.markdown(f"- **{cit['filename']}**, page {cit['page']}")

# Input
question = st.chat_input("Ask a question about your documents...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/qa/ask",
                    headers=headers,
                    json={"question": question},
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    answer_text = data["answer"]
                    citations = data.get("citations", [])

                    st.markdown(answer_text)
                    if citations:
                        with st.expander("Sources"):
                            for cit in citations:
                                st.markdown(f"- **{cit['filename']}**, page {cit['page']}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer_text,
                        "citations": citations,
                    })
                elif resp.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    st.session_state.token = None
                else:
                    st.error(f"Error: {resp.json().get('detail', 'Unknown error')}")
            except Exception as e:
                st.error(f"Could not reach backend: {e}")

if st.session_state.messages:
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
