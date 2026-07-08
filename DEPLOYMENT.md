# Deploying Khata

You've already done the Supabase setup (database + storage bucket). Here's the rest.

## Before you deploy: rotate your Supabase secrets one more time

You've pasted your real database password and your Supabase secret key into
this chat during setup. Treat both as burned - reset the database password
again (Project Settings → Database → Reset database password) and create a
fresh secret key (Project Settings → API Keys → create new secret key, then
delete the old one). Takes about a minute total, and it's the right habit
any time a credential has touched a chat window.

## 1. Push the code to GitHub

If you haven't already:
```
cd invoice-tool
git init
git add .
git commit -m "Initial commit"
```
Create a new repo on GitHub, then:
```
git remote add origin https://github.com/YOUR_USERNAME/khata.git
git push -u origin main
```

## 2. Deploy the backend to Render

1. Go to [render.com](https://render.com) → sign up → **New → Web Service**
2. Connect your GitHub repo
3. Set:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment Variables**, add all of these (see `.env.example` in the backend folder):

| Key | Value |
|---|---|
| `DATABASE_URL` | Your Supabase connection string (Session pooler, password URL-encoded) |
| `GEMINI_API_KEY` | Your free Gemini key from aistudio.google.com/apikey |
| `SUPABASE_URL` | `https://wqwyzgcwqemrtkrcibba.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Your new secret key (starts with `sb_secret_`) |
| `SUPABASE_BUCKET` | `invoice` |
| `BACKUP_RETENTION_COUNT` | `14` |
| `ALLOWED_ORIGINS` | leave blank for now, fill in after step 3 |

5. Click **Create Web Service**. First deploy takes a few minutes.
6. Once live, copy your Render URL (something like `https://khata-backend.onrender.com`)
7. Test it: visit `https://your-render-url.onrender.com/api/health` - should show `{"status":"ok"}`

**Note on Render's free tier:** it spins down after 15 minutes of no traffic and takes ~30-60 seconds to wake back up on the next request. Fine for personal use, just expect the first load of the day to feel slow.

## 3. Deploy the frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → sign up → **Add New → Project**
2. Import the same GitHub repo
3. Set:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (should auto-detect)
   - **Output Directory**: `dist`
4. Add environment variable:
   - `VITE_API_URL` = your Render backend URL from step 2 (e.g. `https://khata-backend.onrender.com`)
5. Click **Deploy**
6. Once live, copy your Vercel URL (e.g. `https://khata.vercel.app`)

## 4. Lock down CORS

Go back to Render → your backend service → Environment Variables → set:
- `ALLOWED_ORIGINS` = your Vercel URL from step 3 (e.g. `https://khata.vercel.app`)

Save - Render will redeploy automatically with the tightened setting.

## 5. Test the whole thing

Open your Vercel URL on your phone and on a laptop. Try:
- Uploading an invoice photo
- Checking it appears in the party dashboard
- Running a manual backup from the Backups tab
- Exporting a PDF statement

## Ongoing costs

At your usage level (2 people, personal bookkeeping), this should stay entirely on free tiers:
- Supabase free tier: 500MB database, 1GB storage - plenty for this
- Render free tier: fine for low-traffic personal use
- Vercel free tier: generous for a small frontend
- Gemini API free tier: should cover your invoice volume

The one thing to watch is Supabase's free tier pausing a project after a week of no activity - if that happens, just log in and click "Restore" on the project, takes a minute.
