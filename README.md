# LinkedIn "Hiring – Product Manager" Post Finder

Reads Google Alerts emails (delivered to a Gmail inbox you control) for
"we're hiring / Product Manager" style LinkedIn posts, and appends new
matches to a Google Sheet — with a direct link to each post.

**Why Gmail instead of a search API:** an earlier version of this called
Google's Custom Search JSON API directly. That API is closed to new Google
Cloud projects (as of 2025) and is being shut down entirely on January 1,
2027 — so it can't be used for a fresh setup. Google Alerts + Gmail has no
such restriction and is genuinely free forever.

## What you need to set up (one-time, ~20 minutes)

### 1. Create a Google Sheet
- Create a new blank Google Sheet.
- Copy its **Sheet ID** from the URL:
  `https://docs.google.com/spreadsheets/d/`**`THIS_PART_IS_THE_ID`**`/edit`

### 2. Create Google Alerts
1. Go to https://www.google.com/alerts (log into the Gmail account you'll use).
2. Create an alert for each query below (paste one at a time, click "Create Alert"):
   - `site:linkedin.com/posts "Product Manager" "we're hiring"`
   - `site:linkedin.com/posts "Product Manager" "hiring" "apply"`
   - `site:linkedin.com/posts "Senior Product Manager" "hiring"`
   - `site:linkedin.com/posts "Product Manager" "join our team"`
   - `site:linkedin.com/posts "Group Product Manager" hiring`
   - `site:linkedin.com/posts "Associate Product Manager" hiring`
   - `site:linkedin.com/posts "Principal Product Manager" hiring`
   - (add more variants any time — no limit, no cost)
3. For each alert, click the settings (pencil/gear icon) and set:
   - **How often**: "As-it-happens" if offered, otherwise "At most once a day"
   - **Deliver to**: your email (the Gmail address you'll use below)
4. Honest limitation: delivery timing depends on Google, not on this
   script — some alerts arrive within hours, others once a day. This is
   the trade-off for something that's free and requires no API access.

### 3. Enable IMAP on that Gmail account
1. In Gmail, go to Settings (gear icon) → "See all settings" → "Forwarding and POP/IMAP" tab.
2. Under "IMAP access", select **Enable IMAP** → Save Changes.

### 4. Turn on 2-Step Verification and create an App Password
1. Go to https://myaccount.google.com/security
2. Turn on **2-Step Verification** if it isn't already on (required for App Passwords).
3. Go to https://myaccount.google.com/apppasswords
4. Under "App name", type something like `linkedin-agent` and click **Create**.
5. Copy the 16-character password shown (no spaces) — this is your `GMAIL_APP_PASSWORD`.
   This is **not** your normal Gmail password — don't use that one.

### 5. Create a Google Service Account (so the script can write to your Sheet)
1. Go to https://console.cloud.google.com/, create or select a project.
2. Enable the **Google Sheets API** (APIs & Services → Library → search for it → Enable).
3. Go to IAM & Admin → Service Accounts → Create Service Account (any name, e.g. `sheet-writer`).
4. Click into it → Keys tab → Add Key → Create new key → JSON → Create.
   This downloads a `service_account.json` file.
5. Open your Google Sheet → Share → paste the service account's email
   (found inside that JSON file as `client_email`) → give it **Editor** access.

### 6. Put the code in a GitHub repo and add secrets
1. Push these files to a GitHub repo: `search_agent.py`, `requirements.txt`,
   `.github/workflows/search_schedule.yml`
2. Repo → Settings → Secrets and variables → Actions → New repository secret.
   Add these four:
   - `GMAIL_ADDRESS` — the Gmail address receiving your alerts
   - `GMAIL_APP_PASSWORD` — the 16-character app password from step 4
   - `GOOGLE_SHEET_ID` — from step 1
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the **entire contents** of the
     `service_account.json` file from step 5

(If you previously added `GOOGLE_API_KEY` or `GOOGLE_CSE_ID` secrets from
an earlier version, they're no longer used — safe to delete or leave alone.)

That's it — GitHub Actions runs the script every 3 hours automatically,
even with your laptop off, appending new rows to your Google Sheet with:

| Date Found (UTC) | Alert Subject | Post Title | Post Link | Email Date |

## Running it manually first (to test)

```bash
pip install -r requirements.txt
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="16-char-app-password"
export GOOGLE_SHEET_ID="..."
export GOOGLE_SERVICE_ACCOUNT_FILE="service_account.json"   # path to the downloaded file
python search_agent.py
```

You can also trigger a run manually anytime from GitHub: repo → Actions
tab → "LinkedIn PM Post Finder (every 3 hours)" → **Run workflow**.

## Notes and honest limitations
- This only catches posts that trigger a Google Alert, so coverage depends
  entirely on Google's own alerting system — it won't be 100%, and timing
  can lag by hours.
- The script only reads **unread** emails from Google's alerts sender and
  marks them read after processing, so nothing gets double-counted even if
  the script runs before a new alert email arrives.
- To adjust coverage, add or remove Google Alerts queries any time at
  google.com/alerts — no code changes needed, since the script processes
  whatever alert emails show up regardless of which query triggered them.
- If alerts land in Spam or Promotions instead of the inbox, the script
  still catches them since it searches Gmail's "All Mail" folder — but
  it's worth checking your filters occasionally to make sure Google isn't
  blocking them outright.
