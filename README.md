# Heaven's Roar — WhatsApp Campaign Automation

> End-to-end WhatsApp outreach and RSVP automation platform built with **Twilio Content Templates**, **Meta WhatsApp Business API**, **Flask**, and **Google Sheets** — deployed on **Render**.

---

## Overview

This system powers large-scale WhatsApp event campaigns for Heaven's Roar church events. It handles the full lifecycle — from sending personalized invitations to 500+ contacts, tracking delivery and read receipts in real time, capturing RSVP responses via interactive buttons, and logging everything to Google Sheets automatically.

The architecture is split into two components:

| Component | File | Purpose |
|-----------|------|---------|
| **Campaign Sender** | `send_invitations.py` | Bulk sends personalized WhatsApp messages using approved Twilio Content Templates |
| **Webhook Server** | `webhook.py` | Receives incoming replies, status callbacks, and RSVP button events; logs everything to Google Sheets |

---

## How It Works

### 1. Outbound Campaign (`send_invitations.py`)

```
contacts.csv → Twilio Content Template → WhatsApp (via Meta) → Recipient
                                                ↓
                                     Google Sheets (live log)
                                     Local CSV results file
```

- Reads a CSV contact list (Name, Phone)
- Sends each contact a **pre-approved Twilio Content Template** (required by Meta for WhatsApp Business messaging)
- Personalizes messages using template variables (e.g., `{{1}}` → recipient's first name)
- Polls Twilio API every 5 seconds (up to 40s) to capture the final delivery status per message
- Logs each result live to a **Google Sheet tab** (named after the template) and a local CSV file
- Status callbacks are sent to the deployed webhook for real-time read receipt tracking

**Delivery statuses tracked:**

| Icon | Status | Meaning |
|------|--------|---------|
| ✅ | `read` | Recipient opened the message |
| 📬 | `delivered` | Message delivered to device |
| 📤 | `sent` | Message accepted by WhatsApp network |
| 📵 | `no whatsapp` | Number not registered on WhatsApp (error 63024) |
| ⚠️ | `undelivered` | Delivery failed |
| ❌ | `failed` | Message rejected |
| 💀 | `error` | Fatal exception during send |

---

### 2. Webhook Server (`webhook.py`)

```
Recipient replies on WhatsApp
        ↓
    Twilio receives it
        ↓
    POST → /whatsapp-webhook  (Render)
        ↓
    Auto-reply sent back
        ↓
    Logged to Google Sheets (Campaign Tab + Reply History)
```

```
Twilio status update (delivered / read / failed)
        ↓
    POST → /status-callback  (Render)
        ↓
    Logged to ReadReceipts tab in Google Sheets
```

The webhook auto-replies based on message content — RSVP button taps, transportation requests, HELP, STOP, and general queries are all handled and logged with the appropriate status.

---

## Google Sheets Structure

Each campaign automatically creates two tabs: `<template_name>` (outbound send log) and `<template_name> reply` (inbound replies). Permanent tabs — `Reply History`, `ReadReceipts`, and `UnnamedContacts` — are never deleted and track activity across all campaigns.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| WhatsApp API | Meta WhatsApp Business API (via Twilio) |
| Messaging | Twilio Content Templates (pre-approved by Meta) |
| Backend | Python 3, Flask, Gunicorn |
| Deployment | Render.com (always-on web service) |
| Data Storage | Google Sheets API (gspread), Local CSV |
| Auth | Google Service Account (JSON key), python-dotenv |
| Status Tracking | Twilio Status Callbacks → Flask webhook |

---

## Prerequisites

1. **Twilio Account** with WhatsApp Business sender approved by Meta
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_WHATSAPP_FROM` (e.g. `whatsapp:+16575306307`)
   - At least one approved **Content Template SID**

2. **Meta WhatsApp Business** — templates must be approved before sending (Twilio submits on your behalf)

3. **Google Cloud Project** with APIs enabled:
   - Google Sheets API
   - Google Drive API

4. **Google Service Account**
   - Create a service account in Google Cloud Console
   - Generate a JSON key → save as `google_credentials.json`
   - Share your Google Sheet with the service account email

5. **Render.com account** for webhook deployment

---

## Environment Variables

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+1xxxxxxxxxx
GOOGLE_SHEET_ID=                        # optional — falls back to sheet name
GOOGLE_SHEET_NAME=HeavensRoar WhatsApp Logs
GOOGLE_CREDS_FILE=google_credentials.json
BASE_URL=https://your-service.onrender.com
```

---

## Local Setup

```bash
git clone https://github.com/sunilganta-dev/heavensroar.git
cd heavensroar

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your .env and google_credentials.json
# Prepare contacts.csv with columns: Name, Phone

python send_invitations.py
```

---

## Deploy to Render

1. Push code to GitHub (contacts.csv is gitignored — never committed)
2. Create a **New Web Service** on Render → connect your GitHub repo
3. Set **Start Command**: `gunicorn webhook:app`
4. Add all environment variables in Render dashboard
5. Upload `google_credentials.json` as a **Secret File** at path `google_credentials.json`
6. After deploy, copy your Render URL

**Configure Twilio:**
- Twilio Console → Messaging → Senders → your WhatsApp number
- Set **"When a message comes in"**: `https://your-service.onrender.com/whatsapp-webhook`
- Set **Status Callback URL** (in send script via `BASE_URL`): `https://your-service.onrender.com/status-callback`

---

## Running a Campaign

```bash
source venv/bin/activate

# Test send to a single number first
python send_invitations.py --sid HX<content_sid> --test 1xxxxxxxxxx

# Send to all contacts
python send_invitations.py --sid HX<content_sid>
```

The script fetches the template name from Twilio automatically, creates the Google Sheet tab named after the template, and prints a live progress summary on completion.

---

## Contact List Management (`contacts.csv`)

Format: `Name,Phone` (phone without `+`, 11-digit US numbers)

Best practices maintained in this project:
- Named contacts sorted A→Z, unnamed contacts at the end
- Numbers with no WhatsApp (error 63024) removed after each campaign
- STOP/unsubscribed contacts removed before next send
- Names normalized to Title Case; abbreviations preserved (AD, MK, RKS)

---

## Health Check

```
GET https://your-service.onrender.com/healthz  →  200 OK
GET https://your-service.onrender.com/         →  "Heaven's Roar Webhook is running!"
```

---

## Security Notes

- `contacts.csv` and `google_credentials.json` are in `.gitignore` — never pushed to GitHub
- All secrets loaded via environment variables
- Google Sheets access scoped to Sheets + Drive only
