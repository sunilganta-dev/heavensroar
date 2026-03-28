import csv
import os
import json
import time
import argparse
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

parser = argparse.ArgumentParser()
parser.add_argument("--test", metavar="PHONE", help="Send only to this number (test mode)")
parser.add_argument("--sid", metavar="CONTENT_SID", help="Twilio Content Template SID to use")
args = parser.parse_args()

load_dotenv()

account_sid   = os.getenv("TWILIO_ACCOUNT_SID")
auth_token    = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
BASE_URL      = os.getenv("BASE_URL", "").strip().rstrip("/")

# ── Template SID: pass via --sid or falls back to the last used one ───────────
content_sid = args.sid or "HXa038c957fa181caffa072c782cb8e588"   # copy_sat_play

if not account_sid or not auth_token or not whatsapp_from:
    raise ValueError("Missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_WHATSAPP_FROM in .env")

client = Client(account_sid, auth_token)

# ── Status helpers ────────────────────────────────────────────────────────────
# WhatsApp error codes that mean the number has no WhatsApp account
NO_WHATSAPP_CODES = {63024, 63003, 63016, 21211}

STATUS_ICON = {
    "read":        "✅ read",
    "delivered":   "📬 delivered",
    "sent":        "📤 sent",
    "undelivered": "⚠️  undelivered",
    "failed":      "❌ failed",
    "fatal_error": "💀 error",
}

def icon(status, error_code=""):
    code = int(error_code) if str(error_code).isdigit() else 0
    if status in ("failed", "undelivered") and code in NO_WHATSAPP_CODES:
        return "📵 no whatsapp"
    return STATUS_ICON.get(status, f"❓ {status}")

# ── Google Sheets setup ───────────────────────────────────────────────────────
SCOPES    = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
CREDS_FILE  = os.getenv("GOOGLE_CREDS_FILE", "google_credentials.json")
SHEET_ID    = os.getenv("GOOGLE_SHEET_ID", "").strip()
SHEET_NAME  = os.getenv("GOOGLE_SHEET_NAME", "HeavensRoar WhatsApp Logs")

print(f"🔍 Fetching template info for {content_sid} ...")
template      = client.content.v1.contents(content_sid).fetch()
template_name = template.friendly_name
print(f"📋 Template : {template_name}")

SYSTEM_TABS = {"Reply History", "ReadReceipts", "UnnamedContacts"}

if args.test:
    campaign_sheet = None
    print("🧪 TEST MODE — skipping Google Sheet logging")
else:
    creds       = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc          = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SHEET_ID) if SHEET_ID else gc.open(SHEET_NAME)

    # Use a fixed tab name so all sends + responses stay in one place
    tab_title = template_name  # e.g. "play_update"

    # Remove placeholder tab if it exists
    for ws in spreadsheet.worksheets():
        if ws.title == "— Ready for next campaign —":
            spreadsheet.del_worksheet(ws)

    existing_titles = [ws.title for ws in spreadsheet.worksheets()]
    if tab_title in existing_titles:
        campaign_sheet = spreadsheet.worksheet(tab_title)
        print(f"✅ Using existing Google Sheet tab: {tab_title}")
    else:
        campaign_sheet = spreadsheet.add_worksheet(title=tab_title, rows=1000, cols=8)
        campaign_sheet.append_row([
            "Name", "Phone Number", "Message SID",
            "Status", "Error Code", "Error Message", "Sent At"
        ])
        campaign_sheet.freeze(rows=1)
        print(f"✅ Created Google Sheet tab: {tab_title}")

# ── Load contacts ─────────────────────────────────────────────────────────────
def clean_header(h):
    return h.replace("\ufeff","").replace("ï»¿","").strip()

def normalize_phone(phone):
    phone = phone.strip().replace(" ","").replace("-","")
    if phone.startswith("whatsapp:"):
        phone = phone[len("whatsapp:"):]
    if not phone.startswith("+"):
        phone = "+" + phone
    return f"whatsapp:{phone}"

if args.test:
    contacts = [{"Name": "Sunil", "PhoneNumber": args.test}]
    print(f"🧪 TEST MODE — sending only to {args.test}")
else:
    with open("contacts.csv", "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [clean_header(n) for n in reader.fieldnames]
        contacts = list(reader)

total = len(contacts)

# ── Results file ──────────────────────────────────────────────────────────────
results_file = f"send_results_{template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(results_file, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerow(["Name","PhoneNumber","MessageSID","Status","Error_Code","Error_Message"])

print(f"📄 Results → {results_file}")
print(f"🚀 Starting send to {total} contacts ...\n")
print(f"{'─'*65}")

# ── Counters ──────────────────────────────────────────────────────────────────
counts = {
    "read": 0, "delivered": 0, "sent": 0,
    "undelivered": 0, "failed": 0, "fatal_error": 0,
    "no_whatsapp": 0
}

def record(status, error_code=""):
    code = int(error_code) if str(error_code).isdigit() else 0
    if status in ("failed", "undelivered") and code in NO_WHATSAPP_CODES:
        counts["no_whatsapp"] += 1
    else:
        counts[status] = counts.get(status, 0) + 1

# ── Send loop ─────────────────────────────────────────────────────────────────
for idx, row in enumerate(contacts, 1):
    name  = row.get("Name", "").strip() or "There"
    phone = row.get("PhoneNumber", row.get("Phone", "")).strip()
    to_number = normalize_phone(phone)

    prefix = f"[{idx:>4}/{total}]"

    try:
        msg = client.messages.create(
            from_=whatsapp_from,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps({"1": name}),
            **( {"status_callback": f"{BASE_URL}/status-callback"} if BASE_URL else {} )
        )

        final_status = msg.status
        final_error_code    = ""
        final_error_message = ""

        # Poll for final status (up to 8 × 5s = 40s)
        for _ in range(8):
            time.sleep(5)
            fetched = client.messages(msg.sid).fetch()
            final_status        = fetched.status
            final_error_code    = str(fetched.error_code or "")
            final_error_message = str(fetched.error_message or "")
            if final_status in ["read", "delivered", "sent", "failed", "undelivered"]:
                break

        record(final_status, final_error_code)
        print(f"{prefix} {name:<28} {phone}  →  {icon(final_status, final_error_code)}"
              + (f"  [err {final_error_code}]" if final_error_code else ""))

        # Log to CSV
        with open(results_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([name, phone, msg.sid, final_status, final_error_code, final_error_message])

        # Log to Google Sheet (skipped in test mode)
        if campaign_sheet:
            try:
                sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # 24hr
                campaign_sheet.append_row([
                    name, phone, msg.sid,
                    final_status, final_error_code, final_error_message, sent_at
                ])
            except Exception as gs_err:
                print(f"         ⚠️  Google Sheet log error: {gs_err}")

    except Exception as e:
        record("fatal_error")
        err_msg = str(e)
        print(f"{prefix} {name:<28} {phone}  →  💀 error  [{err_msg[:60]}]")
        with open(results_file, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([name, phone, "", "fatal_error", "", err_msg])

# ── Final summary ─────────────────────────────────────────────────────────────
done = sum(counts.values())
print(f"\n{'='*55}")
print(f"  SEND COMPLETE — {template_name}")
print(f"{'='*55}")
print(f"  ✅  Read           : {counts['read']:>4}")
print(f"  📬  Delivered      : {counts['delivered']:>4}")
print(f"  📤  Sent (transit) : {counts['sent']:>4}")
print(f"  📵  No WhatsApp    : {counts['no_whatsapp']:>4}")
print(f"  ⚠️   Undelivered    : {counts['undelivered']:>4}")
print(f"  ❌  Failed         : {counts['failed']:>4}")
print(f"  💀  Errors         : {counts['fatal_error']:>4}")
print(f"{'─'*55}")
print(f"  Total processed    : {done:>4} / {total}")
print(f"  Results file       : {results_file}")
print(f"{'='*55}")
