from datetime import date, timedelta
import sqlite3
import random
import string

def gen_id(prefix):
    return f"{prefix}-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(7))

UAE = {'title': 'Nissan Data Issue in UAE– <P1> – <09/02/2026>', 'incident_date': '09/02/2026', 'services_affected': 'Mobile Data Service (Nissan APN) in UAE – Etisalat (E&)', 'root_cause': 'The issue was caused by Etisalat (E&) specific handling of the VPLMN Dynamic Address flag in HSS/HLR.\nDefault Cubic configuration:\nVPLMN Dynamic Address = Allowed\nPurpose: Allows either VPLMN or Home PLMN to assign IP address.\nCubic configuration aligns with 3GPP standards (which do not mandate rejection).\nEtisalat (E&) implementation rejects session establishment when this flag is enabled.This behaviour is specific to E&.', 'workaround': 'Flag change implemented:\nDisabled / Modified VPLMN Dynamic Address setting in HSS/HLR for Nissan APN\nConfiguration updated on 10th February 2026 at 12:00 UAE time.\nPost-change validation confirmed data connectivity restored.', 'long_term': 'Cubic Internal Testing Governance & Validation Control\nBefore any future Nissan Joint Check Testing (UAE or any other country), end-to-end connectivity validation with the respective MNO will be mandatory.\nTesting results to be reviewed by Wholesale, Product, and Engineering team before signing off\nRe-testing Process to be formalized to track any conditional approval closure\nAn internal ticket must be created to track the missed testing until closure.\nClear ownership (Wholesale / Program Manager) must be assigned to re-trigger testing once the contract issue is resolved.\nCustomer must be informed if any MNO connectivity validation remains pending.\nRequirement Accuracy\nAny special MNO requirements will be formally captured by the Wholesale team from the MNO and documented in the applicable technical document\nVerification of all MNO-specific parameters (e.g., HSS/HLR flags, APN configuration, IP allocation handling) for any new integration before testing\nCustomer Testing Gates:\nCompleted connectivity validation and formal internal sign-off by all involved departments\nA documented and formally acknowledged risk acceptance.', 'actions': ['Cubic Internal Testing Governance & Validation Control', 'Before any future Nissan Joint Check Testing (UAE or any other country), end-to-end connectivity validation with the respective MNO will be mandatory.', 'Testing results to be reviewed by Wholesale, Product, and Engineering team before signing off', 'Re-testing Process to be formalized to track any conditional approval closure', 'An internal ticket must be created to track the missed testing until closure.', 'Clear ownership (Wholesale / Program Manager) must be assigned to re-trigger testing once the contract issue is resolved.', 'Customer must be informed if any MNO connectivity validation remains pending.', 'Requirement Accuracy', 'Any special MNO requirements will be formally captured by the Wholesale team from the MNO and documented in the applicable technical document', 'Verification of all MNO-specific parameters (e.g., HSS/HLR flags, APN configuration, IP allocation handling) for any new integration before testing', 'Customer Testing Gates:', 'Completed connectivity validation and formal internal sign-off by all involved departments', 'A documented and formally acknowledged risk acceptance.'], 'full_text': "Nissan Data Issue in UAE– <P1> – <09/02/2026>\nVersion Date - <11/02/2026>\nIncident Date\n09/02/2026\nIncident / Problem\nReference\nNissan Joint Check Testing – UAE – Data Not Working (Etisalat E&)\nStart Time (UTC)\n09/02/2026 – 05:30 UTC\nService Restoration (UTC)\n10/02/2026 – 08:00 UTC\nEnd time (UTC)\n10/02/2026 – 08:00 UTC\nServices Affected\nMobile Data Service (Nissan APN) in UAE – Etisalat (E&)\nCustomer Impact\nCustomer was unable to use mobile data during Joint Check Testing\nData connectivity is a prerequisite for profile download.\nJoint Check testing was blocked until resolution.\nDescription\nDuring Joint Check testing in UAE, Nissan drive test devices were unable to establish mobile data connectivity when connected to Etisalat (E&).\nThe issue was reported on 09th February 2026 at 09:30 hrs (UAE time).\nA solution was proposed on 09th February at 15:00 hrs and implemented on 10th February at 12:00 hrs (UAE time).\nPost implementation testing confirmed that the issue was resolved as per internal validation\nRoot Cause\nThe issue was caused by Etisalat (E&) specific handling of the VPLMN Dynamic Address flag in HSS/HLR.\nDefault Cubic configuration:\nVPLMN Dynamic Address = Allowed\nPurpose: Allows either VPLMN or Home PLMN to assign IP address.\nCubic configuration aligns with 3GPP standards (which do not mandate rejection).\nEtisalat (E&) implementation rejects session establishment when this flag is enabled.This behaviour is specific to E&.\nContributing Process Factors\nThis was NOT a missed internal technical requirement. However, the issue was not\nidentified earlier (during testing) due to the following process gaps:\nCubic Internal Testing was completed for Nissan with Conditional approval for Etisalat, as Etisalat couldn't be tested due to ongoing contract negotiations.\nOnce the contract issue was resolved, the Cubic Internal Test team was not formally re-notified to execute the pending test.\nThere was no clearly defined process to trigger re-testing after commercial resolution.\nAs per Internal Ticketing system, Conditional approval part was missed to be reviewed again, and Nissan was offered to perform Join Check Testing.\nAs a result, the first live validation for E& occurred during Joint Check Testing by Nissan, where the issue was identified\nWorkaround (Actions to restore service)\nFlag change implemented:\nDisabled / Modified VPLMN Dynamic Address setting in HSS/HLR for Nissan APN\nConfiguration updated on 10th February 2026 at 12:00 UAE time.\nPost-change validation confirmed data connectivity restored.\nLong Term Solutions (Actions to prevent recurrence)\nCubic Internal Testing Governance & Validation Control\nBefore any future Nissan Joint Check Testing (UAE or any other country), end-to-end connectivity validation with the respective MNO will be mandatory.\nTesting results to be reviewed by Wholesale, Product, and Engineering team before signing off\nRe-testing Process to be formalized to track any conditional approval closure\nAn internal ticket must be created to track the missed testing until closure.\nClear ownership (Wholesale / Program Manager) must be assigned to re-trigger testing once the contract issue is resolved.\nCustomer must be informed if any MNO connectivity validation remains pending.\nRequirement Accuracy\nAny special MNO requirements will be formally captured by the Wholesale team from the MNO and documented in the applicable technical document\nVerification of all MNO-specific parameters (e.g., HSS/HLR flags, APN configuration, IP allocation handling) for any new integration before testing\nCustomer Testing Gates:\nCompleted connectivity validation and formal internal sign-off by all involved departments\nA documented and formally acknowledged risk acceptance."}
NZ = {'title': 'MAJOR INCIDENT REPORT – <Low> – <17/02/2026> – <Nissan New Zealand Connectivity Issue – Final Version', 'incident_date': '11.02.2026', 'services_affected': 'Mobile Data Service (4G session) – Nissan testing in New Zealand', 'root_cause': 'No issue was identified within Cubic core network infrastructure.\nTrace logs and SIGOS testing confirmed:\nSuccessful session establishment.\nNo HSS/MME/PGW rejections.\nNo configuration changes impacting service.\nThe issue was determined to be related to the test device behavior, which was dropping 4G sessions intermittently.\nThe successful restoration of connectivity following a device restart confirms that the issue was device-related and not network-related.', 'workaround': 'Test device restart restored 4G session stability and resolved the issue.', 'long_term': 'Continue validating connectivity through internal testing and SIGOS before concluding network-related fault.\nRequest device logs when session drops occur without corresponding network rejection.\nInclude device restart validation as an initial troubleshooting step before escalation to network investigation.', 'actions': ['Continue validating connectivity through internal testing and SIGOS before concluding network-related fault.', 'Request device logs when session drops occur without corresponding network rejection.', 'Include device restart validation as an initial troubleshooting step before escalation to network investigation.'], 'full_text': 'MAJOR INCIDENT REPORT – <Low> – <17/02/2026> – <Nissan New Zealand Connectivity Issue – Final Version\nVersion Date - <18/02/2026>\nIncident Date\n11.02.2026\nIncident / Problem\nReference\nStart Time (UTC)\n00:00\nService Restoration (UTC)\n00:00\nEnd time (UTC)\n00:00\nServices Affected\nMobile Data Service (4G session) – Nissan testing in New Zealand\nCustomer Impact\nTemporary interruption of 4G data session during testing for a Nissan Test device.\nConnectivity instability observed on test device.\nNo impact identified on Cubic core network services.\nDescription\nDuring Nissan testing in New Zealand, a connectivity issue was reported where the device was unable to maintain a stable 4G data session.\nCubic internal validation was performed, and all connectivity tests passed successfully. Internal test case results also confirmed successful session establishment from the network side. Attached trace logs showed no rejection, failure, or abnormal behavior within Cubic network elements.\nNo configuration changes were made on the Cubic side during the incident period.\nFurther analysis indicated that the test device being used was dropping 4G sessions intermittently. After the device was restarted the following day, the data session was successfully established and remained stable. Nissan confirmed that the issue was resolved.\nPassed Test Case1 on qa.ccsconnect.nissan.com APN :\nPassed Test case 2 on qa.ccsapplication.nissan.com APN\nRoot Cause\nNo issue was identified within Cubic core network infrastructure.\nTrace logs and SIGOS testing confirmed:\nSuccessful session establishment.\nNo HSS/MME/PGW rejections.\nNo configuration changes impacting service.\nThe issue was determined to be related to the test device behavior, which was dropping 4G sessions intermittently.\nThe successful restoration of connectivity following a device restart confirms that the issue was device-related and not network-related.\nWorkaround (Actions to restore service)\nTest device restart restored 4G session stability and resolved the issue.\nLong Term Solutions (Actions to prevent recurrence)\nContinue validating connectivity through internal testing and SIGOS before concluding network-related fault.\nRequest device logs when session drops occur without corresponding network rejection.\nInclude device restart validation as an initial troubleshooting step before escalation to network investigation.'}

def seed_demo(db_path="rca.db"):
    conn = sqlite3.connect(db_path)
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
        status TEXT NOT NULL DEFAULT 'Open'
    );

    CREATE TABLE IF NOT EXISTS actions (
        action_id TEXT PRIMARY KEY,
        rca_id TEXT NOT NULL,
        action_text TEXT NOT NULL,
        owner_team TEXT,
        owner_person TEXT,
        due_date TEXT,
        status TEXT NOT NULL DEFAULT 'To Do',
        verification_method TEXT,
        verified_by TEXT,
        verified_at TEXT,
        notes TEXT
    );
    """)

    cur.execute("SELECT COUNT(*) FROM rcas")
    if cur.fetchone()[0] >= 2:
        conn.close()
        return

    today = date.today().isoformat()

    def insert_rca(sample, env):
        rid = gen_id("RCA")
        cur.execute("""
            INSERT INTO rcas (rca_id,oem,environment,title,incident_date,services_affected,root_cause,workaround,long_term_solutions,full_text,created_at,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (rid, "Nissan", env, sample["title"], sample.get("incident_date",""), sample.get("services_affected",""),
              sample.get("root_cause",""), sample.get("workaround",""), sample.get("long_term",""), sample.get("full_text",""), today, "Open"))

        for atext in sample.get("actions", [])[:10]:
            aid = gen_id("ACT")
            cur.execute("""
                INSERT INTO actions (action_id,rca_id,action_text,owner_team,owner_person,due_date,status,verification_method,verified_by,verified_at,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (aid, rid, atext, "Tech", "", (date.today()+timedelta(days=14)).isoformat(), "To Do",
                  "Evidence link + independent verification", None, None, None))
        return rid

    insert_rca(UAE, "UAT")
    insert_rca(NZ, "Testing")

    conn.commit()
    conn.close()
