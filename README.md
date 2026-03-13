# Heaven’s Roar WhatsApp Webhook

Automated WhatsApp Message Logging to Google Sheets (Twilio + Render + Google Cloud)

This project is a fully automated WhatsApp webhook system that receives incoming WhatsApp messages through Twilio and logs every message into a Google Sheet in real time. The webhook is deployed on Render.com, runs 24/7 without needing your laptop to be on, and uses a Google Service Account to write data into Google Sheets.

The project is **fully deployed on Render (production-ready)** and monitored using a `/healthz` endpoint.

---

## Features

- Receives WhatsApp messages via Twilio
- Auto-replies to every incoming message
- Logs messages into a CSV file
- Tracks:
  - Timestamp
  - Sender Number
  - Message Body
  - Message Status (received)
- Supports STOP / UNSUBSCRIBE messages
- Health monitoring endpoint (`/healthz`)
- Deployed on Render using **Gunicorn**
- Environment variable security using `.env`

---

## Prerequisites

1. Python 3.10.x
2. Twilio Account with WhatsApp Sender
   * TWILIO_ACCOUNT_SID
   * TWILIO_AUTH_TOKEN
   * TWILIO_WHATSAPP_FROM
3. Google Cloud Project with APIs Enabled
   * Google Drive API
   * Google Sheets API
4. Google Service Account
   * Create a service account
   * Create a JSON key
   * Download the JSON file
   * Share your Google Sheet with: <service-account-name>@<project-id>.iam.gserviceaccount.com
5. Create the Google Sheet
   * Sheet name

## Setup (Local + Render)

1. Install Dependencies
   * pip install -r requirements.txt
2. Create a .env
   * TWILIO_ACCOUNT_SID=xxxxxxxx
   * TWILIO_AUTH_TOKEN=xxxxxxxx
   * TWILIO_WHATSAPP_FROM=whatsapp:+1xxxxxxxxxx
   * PORT=5000
3. Load Google Credentials (Local Development)

## Deploy to Render
1. Create a New Web Service
2. Add Secret File
3. Set Python Version
4. Build and Start Commands

## Webhook URL
   * After deployment, Render gives a URL. 
   * Go to: Twilio Console → Messaging → Senders