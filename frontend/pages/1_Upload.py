import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Upload Documents", page_icon="📤", layout="centered")

if not st.session_state.get("token"):
    st.warning("Please log in first.")
    st.stop()

token = st.session_state.token
headers = {"Authorization": f"Bearer {token}"}

st.title("📤 Upload Documents")

# Upload section
uploaded_files = st.file_uploader(
    "Choose PDF file(s) to upload",
    type=["pdf"],
    accept_multiple_files=True,
)

if st.button("Upload & Process", disabled=not uploaded_files):
    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/documents/upload",
                    headers=headers,
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    timeout=300,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(
                        f"✅ **{data['filename']}** - {data['pages']} pages, {data['chunks']} chunks indexed."
                    )
                elif resp.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    st.session_state.token = None
                    st.stop()
                else:
                    st.error(f"Failed to process {uploaded_file.name}: {resp.json().get('detail', 'Unknown error')}")
            except Exception as e:
                st.error(f"Error uploading {uploaded_file.name}: {e}")

# Document list section
st.divider()
st.subheader("Indexed Documents")

try:
    resp = requests.get(f"{BACKEND_URL}/documents", headers=headers, timeout=10)
    if resp.status_code == 200:
        docs = resp.json()
        if not docs:
            st.info("No documents uploaded yet.")
        else:
            for doc in docs:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(
                        f"**{doc['filename']}**  \n"
                        f"Uploaded by `{doc['uploaded_by']}` on {doc['uploaded_at'][:10]}  \n"
                        f"{doc['page_count']} pages · {doc['chunk_count']} chunks"
                    )
                with col2:
                    if st.button("Delete", key=f"del_{doc['id']}"):
                        del_resp = requests.delete(
                            f"{BACKEND_URL}/documents/{doc['id']}",
                            headers=headers,
                            timeout=10,
                        )
                        if del_resp.status_code == 200:
                            st.success(f"Deleted {doc['filename']}")
                            st.rerun()
                        else:
                            st.error("Failed to delete document.")
    else:
        st.error("Could not load document list.")
except Exception as e:
    st.error(f"Error connecting to backend: {e}")
