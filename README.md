# RCA Closed-Loop Dashboard (Upload + Action Tracker)

## What this is
A lightweight, open-source web dashboard to **close the loop** on RCAs:
- Upload RCA DOCX files
- Auto-extract **Root Cause** and **Long Term Solutions**
- Create **remedial actions** automatically from Long Term Solutions
- Track action **owner / due date / status**
- Require **evidence** + **verification**
- "AI flavour": similarity matching to detect likely recurrence (lightweight, no external APIs)

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Render (public URL)
Create a Python web service and set:
- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

> Note: SQLite on free hosting may reset on redeploy. For persistent storage, switch to Postgres later.

## Demo
- Click **Seed demo RCAs (2 Nissan samples)** in the sidebar
- Use **RCA Audit** and **Action Tracker**
- Use **New Incident (AI match)** to show recurrence detection
