import streamlit as st
import sqlite3
from datetime import date, timedelta
import difflib
import os
import random
import string

from docx import Document

DB_PATH = "rca.db"
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD", "")

# ---------------- Utilities ----------------
def gen_id(prefix):
    return f"{prefix}-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def query(sql, params=()):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def execute(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()

# ---------------- DB Init ----------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS rcas (
        rca_id TEXT PRIMARY KEY,
        oem TEXT,
        environment TEXT,
        title TEXT,
        root_cause TEXT,
        full_text TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS actions (
        action_id TEXT PRIMARY KEY,
        rca_id TEXT,
        action_text TEXT,
        status TEXT,
        due_date TEXT
    );
    """)

    conn.commit()
    conn.close()

# ---------------- Password Gate ----------------
def upload_authorised():
    if "upload_ok" not in st.session_state:
        st.session_state.upload_ok = False

    if not st.session_state.upload_ok:
        pwd = st.text_input("Upload Access Password", type="password")
        if st.button("Unlock Upload"):
            if pwd == UPLOAD_PASSWORD:
                st.session_state.upload_ok = True
                st.success("Upload access granted.")
                st.rerun()
            else:
                st.error("Incorrect password.")
        return False

    return True

# ---------------- AI Similarity ----------------
def find_similar(text):
    rcas = query("SELECT rca_id, title, root_cause FROM rcas")
    results = []
    for r in rcas:
        combined = (r["title"] or "") + " " + (r["root_cause"] or "")
        score = difflib.SequenceMatcher(None, text.lower(), combined.lower()).ratio()
        results.append({
            "RCA ID": r["rca_id"],
            "Title": r["title"],
            "Similarity": round(score, 2)
        })
    results.sort(key=lambda x: x["Similarity"], reverse=True)
    return results[:5]

# ---------------- App UI ----------------
st.set_page_config(page_title="RCA Dashboard", layout="wide")
init_db()

st.title("RCA Closed-Loop Governance Dashboard")

tabs = st.tabs([
    "Upload RCA 🔒",
    "RCA Audit",
    "Action Tracker",
    "AI Recurrence Detection"
])

# ---------------- Upload Tab ----------------
with tabs[0]:
    if not upload_authorised():
        st.warning("Upload access is restricted.")
        st.stop()

    st.subheader("Upload New RCA")

    oem = st.text_input("OEM")
    env = st.selectbox("Environment", ["Pre-Live", "UAT", "Production", "Testing"])
    file = st.file_uploader("Upload RCA DOCX", type=["docx"])

    if file:
        doc = Document(file)
        full_text = "\n".join([p.text for p in doc.paragraphs])
        root_cause = full_text[:800]

        if st.button("Save RCA"):
            rid = gen_id("RCA")
            execute("""
                INSERT INTO rcas (rca_id, oem, environment, title, root_cause, full_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rid,
                oem,
                env,
                file.name,
                root_cause,
                full_text,
                date.today().isoformat()
            ))
            st.success(f"Saved RCA {rid}")

# ---------------- RCA Audit ----------------
with tabs[1]:
    st.subheader("RCA Audit View")
    rcas = query("SELECT * FROM rcas ORDER BY created_at DESC")
    st.dataframe(rcas, use_container_width=True)

# ---------------- Action Tracker ----------------
with tabs[2]:
    st.subheader("Action Tracker")
    actions = query("SELECT * FROM actions ORDER BY due_date ASC")
    st.dataframe(actions, use_container_width=True)

# ---------------- AI Recurrence ----------------
with tabs[3]:
    st.subheader("AI Recurrence Detection (NLP Similarity)")
    text = st.text_area("Enter new incident description")

    if st.button("Find Similar RCAs"):
        if text.strip():
            results = find_similar(text)
            st.dataframe(results, use_container_width=True)
        else:
            st.warning("Please enter text.")
