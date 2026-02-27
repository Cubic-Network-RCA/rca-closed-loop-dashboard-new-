import streamlit as st
import sqlite3
from datetime import date, timedelta
import difflib
import os
import re
import random
import string

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

DB_PATH = "rca.db"

# Upload restriction: set this in Render "Environment" as UPLOAD_PASSWORD
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD", "")

HEADINGS = [
    "Incident Date",
    "Incident / Problem",
    "Services Affected",
    "Customer Impact",
    "Description",
    "Root Cause",
    "Workaround",
    "Workaround (Actions to restore service)",
    "Long Term Solutions",
    "Long Term Solutions (Actions to prevent recurrence)",
    "Contributing Process Factors",
    "Stage",
]

# ---------------------- Helpers ----------------------
def gen_id(prefix: str) -> str:
    return f"{prefix}-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def exec_sql(sql: str, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()

def exec_many(sql: str, rows):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    conn.close()

def query_rows(sql: str, params=()):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def query_one(sql: str, params=()):
    rows = query_rows(sql, params)
    return rows[0] if rows else None

def safe_table(rows, use_container_width=True):
    """Render a list[dict] without pandas."""
    if not rows:
        st.info("No data.")
        return
    st.dataframe(rows, use_container_width=use_container_width)

# ---------------------- Upload access gate ----------------------
def upload_authorised() -> bool:
    """
    Upload is restricted via password stored in env var UPLOAD_PASSWORD.
    If UPLOAD_PASSWORD is not set, upload is locked (safe by default).
    """
    if not UPLOAD_PASSWORD:
        st.warning("Upload is currently disabled because UPLOAD_PASSWORD is not set on the server.")
        st.info("Ask an admin to set UPLOAD_PASSWORD in Render Environment Variables.")
        return False

    if "upload_ok" not in st.session_state:
        st.session_state.upload_ok = False

    if st.session_state.upload_ok:
        return True

    st.info("Upload access is restricted. Enter password to unlock.")
    pwd = st.text_input("Upload Access Password", type="password")
    if st.button("Unlock Upload"):
        if pwd == UPLOAD_PASSWORD:
            st.session_state.upload_ok = True
            st.success("Upload unlocked.")
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

# ---------------------- DB ----------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
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
            status TEXT NOT NULL DEFAULT 'To Do'
                CHECK(status IN ('To Do','In Progress','Evidence Submitted','Verified','Closed')),
            verification_method TEXT,
            verified_by TEXT,
            verified_at TEXT,
            notes TEXT,
            FOREIGN KEY (rca_id) REFERENCES rcas(rca_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL
                CHECK(evidence_type IN ('Link','File note','Screenshot note','Test run note','Monitoring note')),
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
        """
    )
    conn.commit()
    conn.close()

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
        return "\n".join(items[i + 1 : j]).strip()

    def value_after(key):
        i = find_heading(key)
        if i is None:
            return ""
        for k in range(i + 1, min(i + 12, len(items))):
            if items[k].strip() and not is_heading(items[k]):
                return items[k].strip()
        return ""

    # Title: use filename unless doc contains something better
    title = uploaded_file.name
    for t in items[:25]:
        if len(t) > 8 and len(t) < 140:
            # a reasonable candidate title
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

# ---------------------- AI similarity ----------------------
def top_similar_rcas(query_text: str, topk=8, oem_filter: str | None = None):
    rcas = query_rows("SELECT rca_id, oem, environment, title, root_cause, created_at, status FROM rcas")
    if oem_filter:
        rcas = [r for r in rcas if oem_filter.lower() in (r.get("oem") or "").lower()]

    if not rcas:
        return []

    scored = []
    for r in rcas:
        combined = f"{r.get('title','')} {r.get('root_cause','')}".strip()
        score = difflib.SequenceMatcher(None, query_text.lower(), combined.lower()).ratio()
        scored.append({**r, "similarity": score})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:topk]

# ---------------------- KPI + derived views ----------------------
def compute_kpis(rca_ids: set[str]):
    if not rca_ids:
        return dict(open_actions=0, overdue=0, missing_evidence=0, evidenced_pct=0.0, verified_pct=0.0)

    actions = query_rows(
        "SELECT action_id, rca_id, due_date, status FROM actions WHERE rca_id IN (%s)"
        % ",".join(["?"] * len(rca_ids)),
        tuple(rca_ids),
    )
    if not actions:
        return dict(open_actions=0, overdue=0, missing_evidence=0, evidenced_pct=0.0, verified_pct=0.0)

    evidence = query_rows(
        "SELECT DISTINCT action_id FROM evidence WHERE action_id IN (%s)"
        % ",".join(["?"] * len(actions)),
        tuple([a["action_id"] for a in actions]),
    )
    ev_action_ids = set(e["action_id"] for e in evidence)

    open_statuses = {"To Do", "In Progress", "Evidence Submitted"}
    today = date.today().isoformat()

    open_actions = sum(1 for a in actions if a["status"] in open_statuses)
    overdue = sum(1 for a in actions if (a.get("due_date") and a["due_date"] < today and a["status"] in open_statuses))
    missing_evidence = sum(
        1 for a in actions if (a["status"] in open_statuses and a["action_id"] not in ev_action_ids)
    )

    evidenced_pct = (sum(1 for a in actions if a["action_id"] in ev_action_ids) / max(len(actions), 1)) * 100.0
    verified_pct = (sum(1 for a in actions if a["status"] in {"Verified", "Closed"}) / max(len(actions), 1)) * 100.0

    return dict(
        open_actions=int(open_actions),
        overdue=int(overdue),
        missing_evidence=int(missing_evidence),
        evidenced_pct=float(evidenced_pct),
        verified_pct=float(verified_pct),
    )

def audit_rows(rcas):
    if not rcas:
        return []
    rca_ids = [r["rca_id"] for r in rcas]

    acts = query_rows(
        "SELECT action_id, rca_id, status FROM actions WHERE rca_id IN (%s)"
        % ",".join(["?"] * len(rca_ids)),
        tuple(rca_ids),
    )
    ev = query_rows("SELECT DISTINCT action_id FROM evidence")
    ev_action_ids = set(e["action_id"] for e in ev)

    total_by, open_by, missing_ev_by = {}, {}, {}
    open_statuses = {"To Do", "In Progress", "Evidence Submitted"}

    for a in acts:
        rid = a["rca_id"]
        total_by[rid] = total_by.get(rid, 0) + 1
        if a["status"] in open_statuses:
            open_by[rid] = open_by.get(rid, 0) + 1
            if a["action_id"] not in ev_action_ids:
                missing_ev_by[rid] = missing_ev_by.get(rid, 0) + 1

    out = []
    for r in rcas:
        rid = r["rca_id"]
        out.append(
            {
                "rca_id": rid,
                "oem": r.get("oem"),
                "environment": r.get("environment"),
                "title": r.get("title"),
                "incident_date": r.get("incident_date"),
                "services_affected": r.get("services_affected"),
                "created_at": r.get("created_at"),
                "status": r.get("status"),
                "actions_total": total_by.get(rid, 0),
                "actions_open": open_by.get(rid, 0),
                "actions_missing_evidence": missing_ev_by.get(rid, 0),
            }
        )
    out.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    return out

# ---------------------- UI ----------------------
st.set_page_config(page_title="RCA Closed-Loop Dashboard", layout="wide")
init_db()

st.title("RCA Closed-Loop Dashboard")
st.caption(
    "Upload RCAs (restricted), auto-create remedial actions, track evidence + verification, and detect recurrence using lightweight similarity."
)

# Sidebar Filters (no seed button)
with st.sidebar:
    st.header("Filters")
    f_oem = st.text_input("OEM contains", value="")
    f_env = st.multiselect(
        "Environment",
        ["Pre-Live", "UAT", "Production", "Testing"],
        default=["Pre-Live", "UAT", "Production", "Testing"],
    )
    f_status = st.multiselect("RCA Status", ["Open", "Closed", "Reopened"], default=["Open", "Reopened", "Closed"])
    last6_prelive = st.checkbox("Pre-Live last 6 months (audit)", value=False)

# Load RCAs and apply filters
rcas_all = query_rows("SELECT * FROM rcas")
rcas = rcas_all

if f_oem.strip():
    rcas = [r for r in rcas if f_oem.strip().lower() in (r.get("oem") or "").lower()]
if f_env:
    rcas = [r for r in rcas if r.get("environment") in set(f_env)]
if f_status:
    rcas = [r for r in rcas if r.get("status") in set(f_status)]
if last6_prelive:
    cutoff = (date.today() - timedelta(days=183)).isoformat()
    rcas = [r for r in rcas if r.get("environment") == "Pre-Live" and (r.get("created_at") or "") >= cutoff]

rca_ids = set(r["rca_id"] for r in rcas)

# KPIs
k = compute_kpis(rca_ids)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Open actions", k["open_actions"])
c2.metric("Overdue actions", k["overdue"])
c3.metric("Missing evidence", k["missing_evidence"])
c4.metric("Evidenced %", f'{k["evidenced_pct"]:.0f}%')
c5.metric("Verified/Closed %", f'{k["verified_pct"]:.0f}%')

tab_upload, tab_audit, tab_actions, tab_detail, tab_incident, tab_admin = st.tabs(
    ["Upload RCA (Restricted)", "RCA Audit", "Action Tracker", "RCA Detail", "New Incident (AI match)", "Admin"]
)

# ---------------------- Upload RCA (Restricted) ----------------------
with tab_upload:
    st.subheader("Upload RCA (DOCX) — Restricted Access")

    # Password gate
    if not upload_authorised():
        st.stop()

    st.write("Upload an RCA document. The app extracts key sections and auto-creates remedial actions from **Long Term Solutions**.")

    col1, col2, col3 = st.columns(3)
    with col1:
        oem = st.text_input("OEM*", value="")  # no Nissan default
    with col2:
        env = st.selectbox("Environment*", ["Pre-Live", "UAT", "Production", "Testing"], index=1)
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
        rc_preview = parsed["root_cause"] or ""
        st.write((rc_preview[:700] + "…") if len(rc_preview) > 700 else rc_preview)

        st.markdown("**Auto-extracted remedial actions (from Long Term Solutions)**")
        if parsed["actions"]:
            safe_table([{"action_text": a} for a in parsed["actions"]])
        else:
            st.info("No actions detected. You can add actions manually in Admin tab.")

        if st.button("Save RCA to DB"):
            if not oem.strip():
                st.warning("OEM is required.")
            else:
                rid = gen_id("RCA")
                exec_sql(
                    """
                    INSERT INTO rcas (
                        rca_id,oem,environment,title,incident_date,services_affected,
                        root_cause,workaround,long_term_solutions,full_text,created_at,status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'Open')
                    """,
                    (
                        rid,
                        oem.strip(),
                        env,
                        parsed["title"],
                        parsed["incident_date"],
                        parsed["services_affected"],
                        parsed["root_cause"],
                        parsed["workaround"],
                        parsed["long_term_solutions"],
                        parsed["full_text"],
                        created_at,
                    ),
                )

                rows = []
                for atext in parsed["actions"]:
                    aid = gen_id("ACT")
                    rows.append(
                        (
                            aid,
                            rid,
                            atext,
                            "Tech",
                            "",
                            (date.today() + timedelta(days=14)).isoformat(),
                            "To Do",
                            "Evidence link + independent verification",
                            None,
                            None,
                            None,
                        )
                    )
                if rows:
                    exec_many(
                        """
                        INSERT INTO actions (
                            action_id,rca_id,action_text,owner_team,owner_person,due_date,status,
                            verification_method,verified_by,verified_at,notes
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        rows,
                    )

                st.success(f"Saved {rid} with {len(rows)} actions.")
                st.rerun()

# ---------------------- RCA Audit ----------------------
with tab_audit:
    st.subheader("RCA Audit")
    if not rcas:
        st.info("No RCAs match your filters.")
    else:
        safe_table(audit_rows(rcas))

# ---------------------- Action Tracker ----------------------
with tab_actions:
    st.subheader("Action Tracker")
    st.write("Rule: **not done until Evidence Submitted + Verified**.")
    if not rcas:
        st.info("No RCAs match your filters.")
    else:
        acts = query_rows(
            "SELECT * FROM actions WHERE rca_id IN (%s) ORDER BY due_date ASC"
            % ",".join(["?"] * len(rca_ids)),
            tuple(rca_ids),
        )
        if not acts:
            st.info("No actions for selected RCAs.")
        else:
            ev = query_rows("SELECT DISTINCT action_id FROM evidence")
            ev_action_ids = set(e["action_id"] for e in ev)
            for a in acts:
                a["evidence_present"] = a["action_id"] in ev_action_ids

            safe_table(
                [
                    {
                        "action_id": a["action_id"],
                        "rca_id": a["rca_id"],
                        "action_text": a["action_text"],
                        "owner_team": a.get("owner_team"),
                        "owner_person": a.get("owner_person"),
                        "due_date": a.get("due_date"),
                        "status": a.get("status"),
                        "evidence_present": a.get("evidence_present"),
                        "verification_method": a.get("verification_method"),
                        "verified_by": a.get("verified_by"),
                        "verified_at": a.get("verified_at"),
                    }
                    for a in acts
                ]
            )

# ---------------------- RCA Detail ----------------------
with tab_detail:
    st.subheader("RCA Detail")
    if not rcas:
        st.info("No RCAs match your filters.")
    else:
        id_to_title = {r["rca_id"]: r.get("title", "") for r in rcas}
        pick = st.selectbox(
            "Select RCA",
            [r["rca_id"] for r in rcas],
            format_func=lambda rid: f"{rid} — {id_to_title.get(rid,'')}",
        )
        r = query_one("SELECT * FROM rcas WHERE rca_id = ?", (pick,))
        if not r:
            st.error("RCA not found.")
        else:
            st.markdown(f"### {r['title']}")
            st.write(f"**OEM:** {r['oem']}  |  **Env:** {r['environment']}  |  **Incident date:** {r.get('incident_date','')}")
            st.write(f"**Services affected:** {r.get('services_affected','')}")
            st.write(f"**Created:** {r['created_at']}  |  **Status:** {r['status']}")

            st.markdown("**Root cause**")
            st.write(r.get("root_cause", ""))

            st.markdown("**Workaround**")
            st.write(r.get("workaround", ""))

            st.markdown("**Long term solutions**")
            st.write(r.get("long_term_solutions", ""))

            st.divider()
            st.markdown("#### Remedial actions")
            acts = query_rows("SELECT * FROM actions WHERE rca_id = ? ORDER BY due_date ASC", (pick,))
            if not acts:
                st.info("No actions found.")
            else:
                ev = query_rows("SELECT DISTINCT action_id FROM evidence")
                ev_action_ids = set(e["action_id"] for e in ev)
                for a in acts:
                    a["evidence_present"] = a["action_id"] in ev_action_ids

                safe_table(
                    [
                        {
                            "action_id": a["action_id"],
                            "action_text": a["action_text"],
                            "owner_team": a.get("owner_team"),
                            "owner_person": a.get("owner_person"),
                            "due_date": a.get("due_date"),
                            "status": a.get("status"),
                            "evidence_present": a.get("evidence_present"),
                            "verification_method": a.get("verification_method"),
                            "verified_by": a.get("verified_by"),
                            "verified_at": a.get("verified_at"),
                            "notes": a.get("notes"),
                        }
                        for a in acts
                    ]
                )

            st.markdown("#### Evidence")
            ev_rows = query_rows(
                """
                SELECT e.evidence_id, e.action_id, e.evidence_type, e.evidence_ref, e.submitted_by, e.submitted_at
                FROM evidence e
                JOIN actions a ON a.action_id = e.action_id
                WHERE a.rca_id = ?
                ORDER BY e.submitted_at DESC
                """,
                (pick,),
            )
            if not ev_rows:
                st.info("No evidence uploaded/linked yet.")
            else:
                safe_table(ev_rows)

# ---------------------- Incident AI match ----------------------
with tab_incident:
    st.subheader("New Incident (AI match)")
    st.write("Paste a new incident summary. The app suggests similar RCAs using lightweight text similarity.")

    inc_oem = st.text_input("OEM (optional filter)", value="")
    inc_env = st.selectbox("Environment", ["Production", "UAT", "Pre-Live", "Testing"], index=0)
    inc_sev = st.selectbox("Severity", ["P1", "P2", "P3", "P4"], index=1)
    inc_summary = st.text_area("Incident summary", height=120, placeholder="Describe the issue (e.g., 'same timeout in production as UAT')")

    cA, cB = st.columns(2)

    with cA:
        if st.button("Find similar RCAs"):
            if not inc_summary.strip():
                st.warning("Please enter an incident summary.")
            else:
                sims = top_similar_rcas(
                    f"{inc_oem} {inc_env} {inc_sev} {inc_summary}",
                    topk=8,
                    oem_filter=inc_oem.strip() or None,
                )
                if not sims:
                    st.info("No RCAs in DB yet. Upload RCAs first (restricted).")
                else:
                    safe_table(
                        [
                            {
                                "rca_id": s["rca_id"],
                                "title": s["title"],
                                "oem": s["oem"],
                                "environment": s["environment"],
                                "created_at": s["created_at"],
                                "status": s["status"],
                                "similarity": f"{s['similarity']:.2f}",
                            }
                            for s in sims
                        ]
                    )

    with cB:
        if st.button("Log incident"):
            if not inc_summary.strip():
                st.warning("Please enter an incident summary.")
            else:
                iid = gen_id("INC")
                exec_sql(
                    """
                    INSERT INTO incidents (incident_id,oem,environment,system_component,severity,summary,created_at)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (iid, inc_oem.strip() or "Unknown", inc_env, "", inc_sev, inc_summary, date.today().isoformat()),
                )
                st.success(f"Incident logged: {iid}")

# ---------------------- Admin ----------------------
with tab_admin:
    st.subheader("Admin")
    st.write("Add/maintain actions, evidence, and verification.")
    st.divider()

    with st.expander("Add action manually", expanded=False):
        rca_list = query_rows("SELECT rca_id, title FROM rcas ORDER BY created_at DESC")
        if not rca_list:
            st.info("No RCAs yet.")
        else:
            rca_ids_list = [r["rca_id"] for r in rca_list]
            title_map = {r["rca_id"]: r["title"] for r in rca_list}

            rid = st.selectbox("RCA", rca_ids_list, format_func=lambda x: f"{x} — {title_map.get(x,'')}")
            c1, c2, c3 = st.columns(3)
            with c1:
                owner_team = st.text_input("Owner team", value="Tech")
                owner_person = st.text_input("Owner person", value="")
            with c2:
                due_date = st.date_input("Due date", value=date.today() + timedelta(days=14)).isoformat()
                status = st.selectbox("Status", ["To Do", "In Progress", "Evidence Submitted", "Verified", "Closed"], index=0)
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
                    verified_at = date.today().isoformat() if status in ("Verified", "Closed") else None
                    exec_sql(
                        """
                        INSERT INTO actions (
                            action_id,rca_id,action_text,owner_team,owner_person,due_date,status,
                            verification_method,verified_by,verified_at,notes
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            aid,
                            rid,
                            action_text,
                            owner_team,
                            owner_person,
                            due_date,
                            status,
                            verification_method,
                            (verified_by.strip() or None),
                            verified_at,
                            (notes.strip() or None),
                        ),
                    )
                    st.success(f"Added action {aid}")
                    st.rerun()

    with st.expander("Add evidence to an action", expanded=False):
        a_list = query_rows("SELECT action_id, rca_id, action_text FROM actions ORDER BY due_date ASC")
        if not a_list:
            st.info("No actions yet.")
        else:
            action_ids = [a["action_id"] for a in a_list]
            text_map = {a["action_id"]: a["action_text"] for a in a_list}

            aid = st.selectbox("Action", action_ids, format_func=lambda x: f"{x} — {text_map.get(x,'')[:70]}")
            etype = st.selectbox("Evidence type", ["Link", "File note", "Screenshot note", "Test run note", "Monitoring note"])
            eref = st.text_input("Evidence reference (URL or note)", value="")
            submitted_by = st.text_input("Submitted by", value="")

            if st.button("Add evidence"):
                if not eref.strip():
                    st.warning("Evidence reference is required.")
                else:
                    evid = gen_id("EVD")
                    exec_sql(
                        """
                        INSERT INTO evidence (evidence_id,action_id,evidence_type,evidence_ref,submitted_by,submitted_at)
                        VALUES (?,?,?,?,?,?)
                        """,
                        (evid, aid, etype, eref, (submitted_by.strip() or None), date.today().isoformat()),
                    )
                    st.success(f"Added evidence {evid}")
                    st.rerun()

    with st.expander("Update action status / verify", expanded=False):
        a_list = query_rows("SELECT action_id, action_text, status FROM actions ORDER BY due_date ASC")
        if not a_list:
            st.info("No actions yet.")
        else:
            action_ids = [a["action_id"] for a in a_list]
            status_map = {a["action_id"]: a["status"] for a in a_list}
            text_map = {a["action_id"]: a["action_text"] for a in a_list}

            aid = st.selectbox(
                "Action to update",
                action_ids,
                format_func=lambda x: f"{x} — {status_map.get(x,'')} — {text_map.get(x,'')[:60]}",
            )
            new_status = st.selectbox("New status", ["In Progress", "Evidence Submitted", "Verified", "Closed"], index=2)
            verified_by = st.text_input("Verified by (if applicable)", value="")
            notes = st.text_area("Verification/notes", height=70)

            if st.button("Update"):
                verified_at = date.today().isoformat() if new_status in ("Verified", "Closed") else None
                exec_sql(
                    """
                    UPDATE actions
                    SET status=?,
                        verified_by=COALESCE(?, verified_by),
                        verified_at=COALESCE(?, verified_at),
                        notes=COALESCE(?, notes)
                    WHERE action_id=?
                    """,
                    (new_status, (verified_by.strip() or None), verified_at, (notes.strip() or None), aid),
                )
                st.success("Updated.")
                st.rerun()
