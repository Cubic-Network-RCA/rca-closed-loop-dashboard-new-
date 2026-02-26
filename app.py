import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
import difflib
import re
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

DB_PATH = "rca.db"

HEADINGS = [
    "Incident Date","Incident / Problem","Services Affected","Customer Impact","Description","Root Cause",
    "Workaround","Workaround (Actions to restore service)","Long Term Solutions","Long Term Solutions (Actions to prevent recurrence)",
    "Contributing Process Factors","Stage"
]

# ---------------------- DB ----------------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS rcas (
        rca_id TEXT PRIMARY KEY,
        oem TEXT NOT NULL,
        environment TEXT NOT NULL,
        title TEXT NOT NULL,
        incident_date TEXT,
        services_affected TEXT,
        root_cause TEXT,
        workaround TEXT,
        long_term_solutions TEXT,
        full_text TEXT,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open','Closed','Reopened'))
    );

    CREATE TABLE IF NOT EXISTS actions (
        action_id TEXT PRIMARY KEY,
        rca_id TEXT NOT NULL,
        action_text TEXT NOT NULL,
        owner_team TEXT,
        owner_person TEXT,
        due_date TEXT,
        status TEXT NOT NULL DEFAULT 'To Do' CHECK(status IN ('To Do','In Progress','Evidence Submitted','Verified','Closed')),
        verification_method TEXT,
        verified_by TEXT,
        verified_at TEXT,
        notes TEXT,
        FOREIGN KEY (rca_id) REFERENCES rcas(rca_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS evidence (
        evidence_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        evidence_type TEXT NOT NULL CHECK(evidence_type IN ('Link','File note','Screenshot note','Test run note','Monitoring note')),
        evidence_ref TEXT NOT NULL,
        submitted_by TEXT,
        submitted_at TEXT NOT NULL,
        FOREIGN KEY (action_id) REFERENCES actions(action_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        oem TEXT NOT NULL,
        environment TEXT NOT NULL,
        system_component TEXT,
        severity TEXT,
        summary TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

def qdf(sql, params=None):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params or {})
    conn.close()
    return df

def exec_sql(sql, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params or {})
    conn.commit()
    conn.close()

def exec_many(sql, rows):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    conn.close()

def gen_id(prefix):
    import random, string
    return f"{prefix}-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))

# ---------------------- DOCX parsing ----------------------
def iter_block_items(doc):
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)

def doc_text_in_order(doc):
    items = []
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = (block.text or "").strip()
            if t:
                items.append(t)
        else:
            for row in block.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        t = (p.text or "").strip()
                        if t:
                            items.append(t)
    return items

def parse_rca_docx(uploaded_file):
    doc = Document(uploaded_file)
    items = doc_text_in_order(doc)

    def is_heading(t):
        tl = t.strip().lower()
        return any(tl == h.lower() or tl.startswith(h.lower()) for h in HEADINGS)

    def find_heading(key):
        kl = key.lower()
        for i, t in enumerate(items):
            tl = t.strip().lower()
            if tl == kl or tl.startswith(kl):
                return i
        return None

    def section(key):
        i = find_heading(key)
        if i is None:
            return ""
        j = len(items)
        for k in range(i + 1, len(items)):
            if is_heading(items[k]):
                j = k
                break
        return "\n".join(items[i + 1:j]).strip()

    def value_after(key):
        i = find_heading(key)
        if i is None:
            return ""
        for k in range(i + 1, min(i + 12, len(items))):
            if items[k].strip() and not is_heading(items[k]):
                return items[k].strip()
        return ""

    # Title heuristic
    title = uploaded_file.name
    for t in items[:25]:
        if "nissan" in t.lower() and any(w in t.lower() for w in ["issue","data","connect","testing"]):
            title = t.strip()
            break

    incident_date = value_after("Incident Date")
    services_affected = value_after("Services Affected")
    root_cause = section("Root Cause")
    workaround = section("Workaround")
    long_term = section("Long Term Solutions")

    raw_lines = [ln.strip(" \t•-") for ln in re.split(r"[\n\r]+", long_term) if ln.strip()]
    actions = [ln for ln in raw_lines if len(ln) > 8]

    return {
        "title": title,
        "incident_date": incident_date,
        "services_affected": services_affected,
        "root_cause": root_cause,
        "workaround": workaround,
        "long_term_solutions": long_term,
        "actions": actions,
        "full_text": "\n".join(items),
    }

# ---------------------- Similarity (AI flavour) ----------------------
def top_similar_rcas(query_text, topk=5, oem=None):
    rcas = qdf("SELECT rca_id, oem, environment, title, root_cause, created_at, status FROM rcas")
    if oem:
        rcas = rcas[rcas["oem"].str.contains(oem, case=False, na=False)]
    if rcas.empty:
        return pd.DataFrame()

    combined = (rcas["title"].fillna("") + " " + rcas["root_cause"].fillna("")).tolist()
    scores = []
    for text in combined:
        score = difflib.SequenceMatcher(None, query_text.lower(), text.lower()).ratio()
        scores.append(score)

    rcas = rcas.copy()
    rcas["similarity"] = scores
    rcas = rcas.sort_values("similarity", ascending=False).head(topk)
    return rcas[["rca_id","title","oem","environment","created_at","status","similarity"]]

# ---------------------- App ----------------------
st.set_page_config(page_title="RCA Closed-Loop Dashboard", layout="wide")
init_db()

st.title("RCA Closed-Loop Dashboard")
st.caption("Upload RCAs, track remedial actions, require evidence + verification, and detect recurrence using lightweight NLP similarity (open-source).")

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    f_oem = st.text_input("OEM contains", value="")
    f_env = st.multiselect("Environment", ["Pre-Live","UAT","Production","Testing"], default=["Pre-Live","UAT","Production","Testing"])
    f_status = st.multiselect("RCA Status", ["Open","Closed","Reopened"], default=["Open","Reopened","Closed"])
    last6_prelive = st.checkbox("Pre-Live last 6 months (audit)", value=False)
    st.divider()
    if st.button("Seed demo RCAs (2 Nissan samples)"):
        from seed import seed_demo
        seed_demo(DB_PATH)
        st.success("Seeded demo RCAs + actions.")
        st.rerun()

rcas = qdf("SELECT * FROM rcas")
actions = qdf("SELECT * FROM actions")
evidence = qdf("SELECT * FROM evidence")

# apply filters
if f_oem.strip():
    rcas = rcas[rcas["oem"].str.contains(f_oem.strip(), case=False, na=False)]
if f_env:
    rcas = rcas[rcas["environment"].isin(f_env)]
if f_status:
    rcas = rcas[rcas["status"].isin(f_status)]
if last6_prelive:
    cutoff = (date.today() - timedelta(days=183)).isoformat()
    rcas = rcas[(rcas["environment"]=="Pre-Live") & (rcas["created_at"] >= cutoff)]

# KPIs
def kpis():
    if rcas.empty:
        return dict(open_actions=0, overdue=0, missing_evidence=0, evidenced_pct=0.0, verified_pct=0.0)
    a = actions[actions["rca_id"].isin(rcas["rca_id"])].copy()
    if a.empty:
        return dict(open_actions=0, overdue=0, missing_evidence=0, evidenced_pct=0.0, verified_pct=0.0)
    open_actions = int(a["status"].isin(["To Do","In Progress","Evidence Submitted"]).sum())
    today = date.today().isoformat()
    a_due = a.dropna(subset=["due_date"]).copy()
    overdue = int(((a_due["due_date"] < today) & (a_due["status"].isin(["To Do","In Progress","Evidence Submitted"]))).sum())
    ev_actions = set(evidence["action_id"].unique().tolist())
    missing_evidence = int(((~a["action_id"].isin(ev_actions)) & (a["status"].isin(["To Do","In Progress","Evidence Submitted"]))).sum())
    evidenced_pct = float((a["action_id"].isin(ev_actions)).mean() * 100.0)
    verified_pct = float((a["status"].isin(["Verified","Closed"])).mean() * 100.0)
    return dict(open_actions=open_actions, overdue=overdue, missing_evidence=missing_evidence,
                evidenced_pct=evidenced_pct, verified_pct=verified_pct)

k = kpis()
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Open actions", k["open_actions"])
c2.metric("Overdue actions", k["overdue"])
c3.metric("Missing evidence", k["missing_evidence"])
c4.metric("Evidenced %", f'{k["evidenced_pct"]:.0f}%')
c5.metric("Verified/Closed %", f'{k["verified_pct"]:.0f}%')

tab_upload, tab_audit, tab_actions, tab_detail, tab_incident, tab_admin = st.tabs(
    ["Upload RCA", "RCA Audit", "Action Tracker", "RCA Detail", "New Incident (AI match)", "Admin"]
)

with tab_upload:
    st.subheader("Upload RCA (DOCX)")
    st.write("Anyone can upload an RCA document. The app extracts key sections and auto-creates remedial actions from **Long Term Solutions**.")
    col1,col2,col3 = st.columns(3)
    with col1:
        oem = st.text_input("OEM*", value="Nissan")
    with col2:
        env = st.selectbox("Environment*", ["Pre-Live","UAT","Production","Testing"], index=1)
    with col3:
        created_at = st.date_input("RCA created date", value=date.today()).isoformat()

    up = st.file_uploader("Upload RCA (.docx)", type=["docx"])
    if up is not None:
        parsed = parse_rca_docx(up)
        st.markdown("#### Preview extracted fields")
        st.write(f"**Title:** {parsed['title']}")
        st.write(f"**Incident date:** {parsed['incident_date']}")
        st.write(f"**Services affected:** {parsed['services_affected']}")
        st.markdown("**Root cause (preview)**")
        st.write((parsed["root_cause"][:600] + "…") if len(parsed["root_cause"])>600 else parsed["root_cause"])
        st.markdown("**Auto-extracted remedial actions (from Long Term Solutions)**")
        if parsed["actions"]:
            st.write(pd.DataFrame({"action_text": parsed["actions"]}))
        else:
            st.info("No actions detected. You can add actions manually in Admin tab.")

        if st.button("Save RCA to DB"):
            if not oem.strip():
                st.warning("OEM is required.")
            else:
                rid = gen_id("RCA")
                exec_sql("""
                    INSERT INTO rcas (rca_id,oem,environment,title,incident_date,services_affected,root_cause,workaround,long_term_solutions,full_text,created_at,status)
                    VALUES (:rca_id,:oem,:environment,:title,:incident_date,:services_affected,:root_cause,:workaround,:long_term_solutions,:full_text,:created_at,'Open')
                """, dict(
                    rca_id=rid, oem=oem.strip(), environment=env, title=parsed["title"],
                    incident_date=parsed["incident_date"], services_affected=parsed["services_affected"],
                    root_cause=parsed["root_cause"], workaround=parsed["workaround"],
                    long_term_solutions=parsed["long_term_solutions"], full_text=parsed["full_text"],
                    created_at=created_at
                ))

                # create actions
                rows = []
                for atext in parsed["actions"]:
                    aid = gen_id("ACT")
                    rows.append((aid, rid, atext, "Tech", "", (date.today()+timedelta(days=14)).isoformat(),
                                 "To Do", "Evidence link + independent verification", None, None, None))
                if rows:
                    exec_many("""
                        INSERT INTO actions (action_id,rca_id,action_text,owner_team,owner_person,due_date,status,verification_method,verified_by,verified_at,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, rows)
                st.success(f"Saved {rid} with {len(rows)} actions.")
                st.rerun()

with tab_audit:
    st.subheader("RCA Audit")
    st.write("Use sidebar filter **Pre-Live last 6 months** to run your pre-Live assurance review.")
    if rcas.empty:
        st.info("No RCAs match your filters.")
    else:
        a = actions.groupby("rca_id").size().rename("actions_total")
        a_open = actions[actions["status"].isin(["To Do","In Progress","Evidence Submitted"])].groupby("rca_id").size().rename("actions_open")
        ev = evidence.groupby("action_id").size().rename("evidence_count")
        action_ev = actions[["action_id","rca_id"]].merge(ev, how="left", on="action_id").fillna({"evidence_count":0})
        ev_missing = action_ev[action_ev["evidence_count"]==0].groupby("rca_id").size().rename("actions_missing_evidence")
        view = rcas.merge(a, left_on="rca_id", right_index=True, how="left") \
                   .merge(a_open, left_on="rca_id", right_index=True, how="left") \
                   .merge(ev_missing, left_on="rca_id", right_index=True, how="left") \
                   .fillna({"actions_total":0,"actions_open":0,"actions_missing_evidence":0})
        view = view.sort_values(["created_at"], ascending=[False])
        st.dataframe(view[[
            "rca_id","oem","environment","title","incident_date","services_affected","created_at","status",
            "actions_total","actions_open","actions_missing_evidence"
        ]], use_container_width=True, hide_index=True)

with tab_actions:
    st.subheader("Action Tracker")
    st.write("Rule: **not done until Evidence Submitted + Verified**.")
    if rcas.empty:
        st.info("No RCAs match your filters.")
    else:
        a = actions[actions["rca_id"].isin(rcas["rca_id"])].copy()
        if a.empty:
            st.info("No actions for selected RCAs.")
        else:
            ev_actions = set(evidence["action_id"].unique().tolist())
            a["evidence_present"] = a["action_id"].isin(ev_actions)
            st.dataframe(a[[
                "action_id","rca_id","action_text","owner_team","owner_person","due_date","status",
                "evidence_present","verification_method","verified_by","verified_at"
            ]], use_container_width=True, hide_index=True)

with tab_detail:
    st.subheader("RCA Detail")
    if rcas.empty:
        st.info("No RCAs match your filters.")
    else:
        pick = st.selectbox("Select RCA", rcas["rca_id"].tolist(),
                            format_func=lambda rid: f"{rid} — {rcas.set_index('rca_id').loc[rid,'title']}")
        r = rcas.set_index("rca_id").loc[pick].to_dict()
        st.markdown(f"### {r['title']}")
        st.write(f"**OEM:** {r['oem']}  |  **Env:** {r['environment']}  |  **Incident date:** {r.get('incident_date','')}")
        st.write(f"**Services affected:** {r.get('services_affected','')}")
        st.write(f"**Created:** {r['created_at']}  |  **Status:** {r['status']}")
        st.markdown("**Root cause**")
        st.write(r.get("root_cause",""))
        st.markdown("**Workaround**")
        st.write(r.get("workaround",""))
        st.markdown("**Long term solutions**")
        st.write(r.get("long_term_solutions",""))

        st.divider()
        st.markdown("#### Remedial actions")
        a = actions[actions["rca_id"]==pick].copy()
        if a.empty:
            st.info("No actions found.")
        else:
            ev_actions = set(evidence["action_id"].unique().tolist())
            a["evidence_present"] = a["action_id"].isin(ev_actions)
            st.dataframe(a[[
                "action_id","action_text","owner_team","owner_person","due_date","status","evidence_present",
                "verification_method","verified_by","verified_at","notes"
            ]], use_container_width=True, hide_index=True)

        st.markdown("#### Evidence")
        ev = evidence.merge(actions[["action_id","rca_id","action_text"]], on="action_id", how="left")
        ev = ev[ev["rca_id"]==pick].copy()
        if ev.empty:
            st.info("No evidence uploaded/linked yet.")
        else:
            st.dataframe(ev[["evidence_id","action_id","evidence_type","evidence_ref","submitted_by","submitted_at"]],
                         use_container_width=True, hide_index=True)

with tab_incident:
    st.subheader("New Incident (AI match)")
    st.write("Paste a new incident summary. The app suggests similar RCAs using lightweight text similarity.")
    inc_oem = st.text_input("OEM", value="Nissan")
    inc_env = st.selectbox("Environment", ["Production","UAT","Pre-Live","Testing"], index=0)
    inc_sev = st.selectbox("Severity", ["P1","P2","P3","P4"], index=1)
    inc_summary = st.text_area("Incident summary", height=120, placeholder="Describe the issue (e.g., 'same timeout in production as UAT')")

    colA, colB = st.columns([1,1])
    with colA:
        if st.button("Find similar RCAs"):
            if not inc_summary.strip():
                st.warning("Please enter an incident summary.")
            else:
                sims = top_similar_rcas(f"{inc_oem} {inc_env} {inc_sev} {inc_summary}", topk=8, oem=inc_oem.strip() or None)
                if sims.empty:
                    st.info("No RCAs in DB yet. Upload RCAs first.")
                else:
                    st.dataframe(sims, use_container_width=True, hide_index=True)

    with colB:
        if st.button("Log incident"):
            if not inc_summary.strip():
                st.warning("Please enter an incident summary.")
            else:
                iid = gen_id("INC")
                exec_sql("""
                    INSERT INTO incidents (incident_id,oem,environment,system_component,severity,summary,created_at)
                    VALUES (:incident_id,:oem,:environment,:system_component,:severity,:summary,:created_at)
                """, dict(incident_id=iid,oem=inc_oem,environment=inc_env,system_component="",severity=inc_sev,
                          summary=inc_summary,created_at=date.today().isoformat()))
                st.success(f"Incident logged: {iid}")

with tab_admin:
    st.subheader("Admin")
    st.write("Use this to add/maintain actions, evidence, and verification.")
    st.divider()

    with st.expander("Add action manually", expanded=False):
        rca_list = qdf("SELECT rca_id, title FROM rcas ORDER BY created_at DESC")
        if rca_list.empty:
            st.info("No RCAs yet.")
        else:
            rid = st.selectbox("RCA", rca_list["rca_id"].tolist(),
                               format_func=lambda x: f"{x} — {rca_list.set_index('rca_id').loc[x,'title']}")
            c1,c2,c3 = st.columns(3)
            with c1:
                owner_team = st.text_input("Owner team", value="Tech")
                owner_person = st.text_input("Owner person", value="")
            with c2:
                due_date = st.date_input("Due date", value=date.today()+timedelta(days=14)).isoformat()
                status = st.selectbox("Status", ["To Do","In Progress","Evidence Submitted","Verified","Closed"], index=0)
            with c3:
                verification_method = st.text_input("Verification method (required)", value="Evidence link + independent verification")
                verified_by = st.text_input("Verified by", value="")

            action_text = st.text_area("Action text*", height=90)
            notes = st.text_area("Notes", height=60)
            if st.button("Add action"):
                if not action_text.strip():
                    st.warning("Action text is required.")
                elif not verification_method.strip():
                    st.warning("Verification method is required.")
                else:
                    aid = gen_id("ACT")
                    exec_sql("""
                        INSERT INTO actions (action_id,rca_id,action_text,owner_team,owner_person,due_date,status,verification_method,verified_by,verified_at,notes)
                        VALUES (:action_id,:rca_id,:action_text,:owner_team,:owner_person,:due_date,:status,:verification_method,:verified_by,:verified_at,:notes)
                    """, dict(action_id=aid,rca_id=rid,action_text=action_text,owner_team=owner_team,owner_person=owner_person,
                              due_date=due_date,status=status,verification_method=verification_method,
                              verified_by=verified_by or None, verified_at=date.today().isoformat() if status in ("Verified","Closed") else None,
                              notes=notes or None))
                    st.success(f"Added action {aid}")
                    st.rerun()

    with st.expander("Add evidence to an action", expanded=False):
        a_list = qdf("SELECT action_id, rca_id, action_text FROM actions ORDER BY due_date ASC")
        if a_list.empty:
            st.info("No actions yet.")
        else:
            aid = st.selectbox("Action", a_list["action_id"].tolist(),
                               format_func=lambda x: f"{x} — {a_list.set_index('action_id').loc[x,'action_text'][:70]}")
            etype = st.selectbox("Evidence type", ["Link","File note","Screenshot note","Test run note","Monitoring note"])
            eref = st.text_input("Evidence reference (URL or note)", value="")
            submitted_by = st.text_input("Submitted by", value="")
            if st.button("Add evidence"):
                if not eref.strip():
                    st.warning("Evidence reference is required.")
                else:
                    evid = gen_id("EVD")
                    exec_sql("""
                        INSERT INTO evidence (evidence_id,action_id,evidence_type,evidence_ref,submitted_by,submitted_at)
                        VALUES (:evidence_id,:action_id,:evidence_type,:evidence_ref,:submitted_by,:submitted_at)
                    """, dict(evidence_id=evid,action_id=aid,evidence_type=etype,evidence_ref=eref,
                              submitted_by=submitted_by,submitted_at=date.today().isoformat()))
                    st.success(f"Added evidence {evid}")
                    st.rerun()

    with st.expander("Update action status / verify", expanded=False):
        a_list = qdf("SELECT action_id, action_text, status FROM actions ORDER BY due_date ASC")
        if a_list.empty:
            st.info("No actions yet.")
        else:
            aid = st.selectbox("Action to update", a_list["action_id"].tolist(),
                               format_func=lambda x: f"{x} — {a_list.set_index('action_id').loc[x,'status']} — {a_list.set_index('action_id').loc[x,'action_text'][:60]}")
            new_status = st.selectbox("New status", ["In Progress","Evidence Submitted","Verified","Closed"], index=2)
            verified_by = st.text_input("Verified by (if applicable)", value="")
            notes = st.text_area("Verification/notes", height=70)
            if st.button("Update"):
                exec_sql("""
                    UPDATE actions
                    SET status=:status,
                        verified_by=COALESCE(:verified_by, verified_by),
                        verified_at=COALESCE(:verified_at, verified_at),
                        notes=COALESCE(:notes, notes)
                    WHERE action_id=:action_id
                """, dict(status=new_status,
                          verified_by=verified_by.strip() or None,
                          verified_at=date.today().isoformat() if new_status in ("Verified","Closed") else None,
                          notes=notes.strip() or None,
                          action_id=aid))
                st.success("Updated.")
                st.rerun()
