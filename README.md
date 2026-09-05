# LinkedIn "Hiring – Product Manager" Post Finder

Runs every 3 hours, searches Google's index of LinkedIn posts (not LinkedIn
directly — this keeps you compliant with LinkedIn's Terms of Service, which
prohibit bots/scrapers accessing LinkedIn itself), and appends any new
"we're hiring / Product Manager" style posts to a Google Sheet, with a
direct link to each post.

## What you need to set up (one-time, ~15 minutes)

### 1. Create a Google Sheet
- Create a new blank Google Sheet.
- Copy its **Sheet ID** from the URL:
  `https://docs.google.com/spreadsheets/d/`**`THIS_PART_IS_THE_ID`**`/edit`

### 2. Enable the Custom Search API + get an API key
1. Go to https://console.cloud.google.com/ and create (or pick) a project.
2. Enable the **"Custom Search API"** under APIs & Services → Library.
3. Go to APIs & Services → Credentials → Create Credentials → API key.
   This is your `GOOGLE_API_KEY`.
4. Free tier = 100 queries/day. This script runs every 3 hours (8 times/day)
   with 12 keyword variants per run = 96/day, staying just under the free
   limit. (Enable billing later if you want even more keyword variants.)

### 3. Create a Programmable Search Engine
1. Go to https://programmablesearchengine.google.com/
2. Create a new search engine, set it to **search the entire web**.
3. Copy the **Search engine ID** — this is your `GOOGLE_CSE_ID`.

### 4. Create a Google Service Account (so the script can write to your Sheet)
1. In Google Cloud Console → IAM & Admin → Service Accounts → Create.
2. Once created, go to it → Keys → Add Key → JSON. This downloads a
   `service_account.json` file — keep it private.
3. Enable the **Google Sheets API** for your project (same Library page as step 2).
4. Open your Google Sheet → Share → paste the service account's email
   (looks like `something@your-project.iam.gserviceaccount.com`) → give it
   **Editor** access.

### 5. Put the code in a GitHub repo
1. Create a new (private is fine) GitHub repo and push these files to it:
   `search_agent.py`, `requirements.txt`, `.github/workflows/search_schedule.yml`
2. Go to the repo → Settings → Secrets and variables → Actions → New repository secret.
   Add these three secrets:
   - `GOOGLE_API_KEY` — from step 2
   - `GOOGLE_CSE_ID` — from step 3
   - `GOOGLE_SHEET_ID` — from step 1
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the **entire contents** of the
     `service_account.json` file from step 4

That's it — GitHub Actions will now run the script automatically every hour,
even with your laptop off, and append new rows to your Google Sheet with:

| Date Found (UTC) | Search Term | Post Title | Post Link | Snippet |

## Running it manually first (to test)
You can test locally before relying on GitHub Actions:

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="..."
export GOOGLE_CSE_ID="..."
export GOOGLE_SHEET_ID="..."
export GOOGLE_SERVICE_ACCOUNT_FILE="service_account.json"   # path to the downloaded file
python search_agent.py
```

You can also trigger a run manually anytime from GitHub: go to the repo →
Actions tab → "LinkedIn PM Post Finder (every 3 hours)" → **Run workflow**.

## Notes and honest limitations
- This only catches posts that Google has already indexed, so there will be
  some delay (usually minutes to a few hours) and some posts may never get
  indexed at all. It will not catch literally 100%, but it's the best
  coverage achievable without violating LinkedIn's Terms of Service.
- To adjust which posts get caught, edit the `KEYWORD_QUERIES` list in
  `search_agent.py` — e.g. add specific cities, industries, or company
  names. Keep the total per run at 12 or fewer to stay in the free quota
  at the current every-3-hours schedule.
- If you outgrow the free tier, Google charges $5 per additional 1,000
  queries — you'd increase `KEYWORD_QUERIES` and enable billing on the
  Custom Search API.
