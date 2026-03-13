import csv
import os
from twilio.rest import Client
from dotenv import load_dotenv
import time
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
content_sid = "HXd67fd70d72c4e95c37c6119865206e9a"  # col_easter template

client = Client(account_sid, auth_token)

print("🔐 Using SID:", account_sid)
print("📤 Using FROM:", whatsapp_from)

# Load unsubscribed numbers from ALL sheets in Google Sheet
print("\n📋 Loading unsubscribed list from Google Sheet (all tabs)...")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("google_credentials.json", scopes=SCOPES)
gs_client = gspread.authorize(creds)
spreadsheet = gs_client.open_by_key("1nXTpDZc0YfmsbgfUSuYKanEcura_j8L3-xueGArRWXk")

unsubscribed = set()
for ws in spreadsheet.worksheets():
    all_rows = ws.get_all_values()
    if not all_rows:
        continue
    # Find header row(s) and process data
    for i, row in enumerate(all_rows):
        if row and row[0].lower() in ("name", "phone_number"):
            headers = [h.lower() for h in row]
            try:
                phone_idx = headers.index("phone_number")
                status_idx = headers.index("status")
            except ValueError:
                continue
            for data_row in all_rows[i+1:]:
                if len(data_row) > max(phone_idx, status_idx):
                    if data_row[status_idx].upper() == "UNSUBSCRIBED":
                        # Strip leading + if present
                        phone = data_row[phone_idx].strip().lstrip("+")
                        if phone:
                            unsubscribed.add(phone)

print(f"🚫 Found {len(unsubscribed)} unsubscribed numbers across all sheets: {unsubscribed}")

# Save Results
results_file = "send_results.csv"
with open(results_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Name",
        "PhoneNumber",
        "MessageSID",
        "Status",
        "Error_Code",
        "Error_Message"
    ])

print("\n📌 Loading contacts...")

# Clean header function
def clean_header(h):
    return (
        h.replace("\ufeff","")
         .replace("ï»¿", "")
         .replace("ï»", "")
         .replace("»¿", "")
         .strip()
    )

# Load CSV
with open("contacts.csv", "r", encoding="latin-1") as f:
    reader = csv.DictReader(f)
    reader.fieldnames = [clean_header(n) for n in reader.fieldnames]
    rows = list(reader)

# Filter out unsubscribed contacts
filtered_rows = []
skipped = []
for row in rows:
    phone = row["PhoneNumber"].strip()
    if phone in unsubscribed:
        skipped.append(row["Name"].strip())
    else:
        filtered_rows.append(row)

if skipped:
    print(f"⏭️  Skipping {len(skipped)} unsubscribed contacts: {', '.join(skipped)}")

print(f"📌 Sending to {len(filtered_rows)} contacts (out of {len(rows)} total)\n")

# Send + Delivery Check
for row in filtered_rows:
    name = row["Name"].strip()
    phone = row["PhoneNumber"].strip()

    print(f"\n📨 Sending to {name} ({phone}) ...")

    try:
        msg = client.messages.create(
            from_=whatsapp_from,
            to=f"whatsapp:+{phone}",
            content_sid=content_sid,
            content_variables=f'{{"1": "{name}"}}'
        )

        # Wait for Twilio to update status
        time.sleep(3)
        msg_check = client.messages(msg.sid).fetch()

        status = msg_check.status
        e_code = msg_check.error_code
        e_msg = msg_check.error_message

        print(f"➡️ Status: {status} | Error: {e_code}")

        # Save result
        with open(results_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                name,
                phone,
                msg.sid,
                status,
                e_code,
                e_msg
            ])

    except Exception as e:
        print("❌ Fatal Error:", e)

print("\n🎉 DONE — All messages processed.")
print("📁 Results saved to send_results.csv")
