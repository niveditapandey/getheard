# Admin Guide — GetHeard

**For Nivedita (Platform Admin)**

This guide covers everything you can do as the GetHeard admin — monitoring the platform, managing studies, handling payouts, and adjusting pricing.

---

## Admin Login

**URL:** https://getheard.space/admin/login

**Credentials (from `.env`):**
```
Username: admin
Password: getheard-admin-2026   ← CHANGE THIS before going live!
```

---

## Admin Dashboard Overview

At `/admin`, you'll see:

### Stats Cards
| Card | What It Shows |
|------|--------------|
| Total Clients | All registered client companies |
| Active Studies | Studies currently in progress (not completed/cancelled) |
| Total Respondents | All enrolled panel members |
| Pending Redemptions | Payout requests waiting for your action |

### Tables
- **Recent Clients** — Company name, email, study count, join date
- **Active Studies** — Study name, client, status, respondent progress
- **Pending Redemptions** — Who wants to be paid, how much, method

---

## Managing Studies

### View All Studies
Go to `/admin` → Studies table shows all active studies.

**Columns:** Study name | Client | Status | Respondents (done/total) | Created date

**Status meanings:**
| Status | Action Needed? |
|--------|---------------|
| briefing | Client is still briefing — no action |
| pricing | Client reviewing quote — no action |
| panel_building | System is recruiting — monitor |
| panel_approval | Waiting for client to approve panel |
| interviewing | Interviews in progress — monitor count |
| analysis | AI generating report — no action |
| completed | Done! Check quality if needed |

### When a Study Gets Stuck
If a study hasn't progressed in 24+ hours:
1. Check the project JSON file in `projects/` folder
2. Look at the `pipeline` object to see what stage it's stuck at
3. Common fixes:
   - Panel building stuck → Manually run PanelAgent via `/agent`
   - Analysis stuck → Re-trigger via `POST /agent/api/reports/generate`
   - Payment stuck → Check Razorpay dashboard for failed/pending orders

---

## Managing Clients

### View All Clients
Go to `/admin` → Clients table.

**Each client shows:** Name, company, email, number of studies, join date.

### Adding a Client Manually
Currently there's no admin UI for this. To add a client manually:
1. SSH into server
2. Run Python:
```python
from src.storage.client_store import create_client
client = create_client({
    "name": "Priya Sharma",
    "company": "ACME Corp",
    "email": "priya@acme.com",
    "password": "temp-password-2026",
    "country": "IN"
})
print(client["client_id"])
```

### Resetting a Client Password
Edit their JSON file in `clients/{client_id}.json`:
```python
import hashlib, json
new_hash = hashlib.sha256("new-password".encode()).hexdigest()
# Update "password_hash" field in the JSON file
```

---

## Managing the Respondent Panel

### Enrolling Respondents (Bulk)
To bulk-enroll respondents from a CSV:
1. Go to `/panel/api/csv-upload` (via API call)
2. Or manually import using the Python store:
```bash
curl -X POST http://localhost:8000/panel/api/csv-upload \
  -F "csv_file=@respondents.csv" \
  -F "project_id=your_project_id"
```

### Viewing the Panel
- **Full list:** `GET /api/respondents` (filterable by language, status, country)
- **Stats:** `GET /api/respondents/stats`

### Updating Respondent Status
```bash
curl -X PATCH http://localhost:8000/api/respondents/{id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "inactive"}'
```

**Valid statuses:** `enrolled` | `scheduled` | `interviewed` | `inactive` | `blocked`

### Adding Points Manually
If a respondent completed an interview but points weren't credited:
```bash
curl -X POST http://localhost:8000/api/respondents/{id}/points/add \
  -H "Content-Type: application/json" \
  -d '{"amount": 400, "reason": "Interview completion — manual credit", "study_id": "proj_abc123"}'
```

---

## Processing Redemptions (Payouts)

This is your most frequent admin task. Respondents request payouts and you process them manually.

### Step 1: See Pending Requests
On the admin dashboard, the **Pending Redemptions** table shows:
- Respondent name + phone
- Points requested
- Cash value + currency
- Method (UPI / Gift Card)
- UPI ID (if UPI)
- Request date

OR via API:
```bash
curl http://localhost:8000/api/admin/redemptions?status=pending
```

### Step 2: Process the Payout

**For UPI (India):**
1. Open your UPI app (Google Pay, PhonePe, Paytm, etc.)
2. Send the cash amount to the UPI ID provided (e.g., `ravi@okaxis`)
3. Note the transaction reference

**For Gift Cards:**
1. Purchase the relevant gift card (Amazon, Flipkart, etc.) from their portal
2. Copy the gift card code
3. Note: gift card value = points × rate × 1.10 (10% bonus)

### Step 3: Mark as Completed
```bash
curl -X PATCH http://localhost:8000/api/admin/redemptions/{request_id} \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "notes": "UPI transferred ₹100 to ravi@okaxis — ref TXN123456"
  }'
```

Or update the `redemptions/{request_id}.json` file directly.

### Rejecting a Request
If the UPI ID is invalid or request is suspicious:
```json
{
  "status": "rejected",
  "notes": "Invalid UPI ID — please re-submit with correct details"
}
```

---

## Managing Pricing

### Access the Pricing Editor
Go to `/admin/pricing` — you'll see an inline editor for all pricing tiers.

### What You Can Edit
- **Base prices** for all 4 study types
- **Panel size multiplier tiers** (add/remove tiers, change multipliers)
- **Recruitment fees** (DB per-respondent, targeted base per-respondent)
- **Market multipliers** (per country)
- **Industry multipliers** (per industry)
- **Urgency premium** (currently 25%)

### How to Change Prices
1. Click any cell in the pricing table
2. Type new value
3. Click **Save Changes**

Changes take effect immediately for all new quotes. Existing confirmed quotes are not retroactively changed.

### Live Price Calculator
The admin pricing page has a live calculator — enter parameters and see the total computed in real-time. Use this to sanity-check pricing before saving.

### Pricing File
Prices are stored in `config/pricing.json`. If needed, edit directly:
```bash
nano /path/to/getHeard/config/pricing.json
```
Then restart the server (or it auto-reloads if using `--reload`).

---

## Monitoring WhatsApp

### Check Active WhatsApp Sessions
```bash
curl http://localhost:8000/api/whatsapp/stats
```

### Send a Test WhatsApp
```bash
curl -X POST http://localhost:8000/api/whatsapp/send \
  -H "Content-Type: application/json" \
  -d '{"to": "+919876543210", "message": "Test from GetHeard admin"}'
```

### WhatsApp Token Expiry
The Meta WhatsApp access token expires every 60 days. Before it expires:
1. Go to Meta Business Manager → System Users
2. Generate a new access token
3. Update `.env`: `WHATSAPP_ACCESS_TOKEN=new_token`
4. Restart server

**Current token generated:** ~March 2026 → expires ~May 2026

---

## Monitoring Email

### Check Resend Domain Status
```bash
curl https://api.resend.com/domains/44ace173-7e2c-4028-b25c-18022833d4b6 \
  -H "Authorization: Bearer re_YOUR_RESEND_API_KEY"
```

### Send a Test Email
```python
from src.notifications.notifier import send_email
import asyncio

asyncio.run(send_email(
    to="np@dendrons.ai",
    subject="GetHeard test email",
    html="<p>This is a test from the GetHeard platform.</p>"
))
```

---

## Running the Server

### Start Server (Development)
```bash
cd /Users/niveditapandey/Documents/AI\ Projects/getHeard
source venv/bin/activate
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

### Or use Claude Code launch config
The `.claude/launch.json` has a ready-to-run config named `getHeard`.

### Check Server is Running
```bash
curl http://localhost:8000/health
```

---

## Manually Triggering AI Agents

### Re-run AnalysisAgent on a project
```bash
curl -X POST http://localhost:8000/agent/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"project_id": "proj_abc123"}'
```

### Run BriefAgent for a project
Go to `/agent/brief` in browser.

### Run DesignerAgent
```bash
curl -X POST http://localhost:8000/agent/api/design \
  -H "Content-Type: application/json" \
  -d '{"brief": {"project_name": "...", "research_type": "...", ...}}'
```

---

## Adding New Client Credentials

To give a client portal access without self-signup, add to `.env`:
```env
CLIENT_CREDENTIALS=demo:demo123,acme:acme2026,newclient:theirpassword
```
Then restart server. They can log in with `newclient` / `theirpassword`.

For proper accounts (with study history), they should sign up at `/listen/signup`.

---

## Backup & Data

All data is stored as JSON files. Back up these directories regularly:
```
projects/
transcripts/
reports/
clients/
respondents/
panels/
redemptions/
```

Quick backup:
```bash
tar -czf getHeard_backup_$(date +%Y%m%d).tar.gz \
  projects/ transcripts/ reports/ clients/ respondents/ panels/ redemptions/
```

---

## Security Checklist (Do Before Going Live)

- [ ] Change `SECRET_KEY` in `.env` to a long random string
- [ ] Change `ADMIN_CREDENTIALS` to a strong password
- [ ] Change `API_KEY` to a new value
- [ ] Enable HTTPS on the hosting server
- [ ] Set up automated backups for JSON data directories
- [ ] Rotate WhatsApp token (get permanent system user token)
- [ ] Add Resend DKIM record and verify domain (check status above)
- [ ] Test all payment flows with real small amounts
- [ ] Set up error monitoring (Sentry)
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom, etc.)

---

## Key Admin URLs

| URL | Purpose |
|-----|---------|
| `/admin` | Main dashboard |
| `/admin/pricing` | Edit pricing |
| `/api/admin/stats` | Platform stats JSON |
| `/api/admin/clients` | All clients JSON |
| `/api/admin/studies` | All studies JSON |
| `/api/admin/redemptions` | All payout requests |
| `/api/respondents/stats` | Panel statistics |
| `/health` | Server health check |
