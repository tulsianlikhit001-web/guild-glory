# FF Guild Glory Bot — Control Plane

Render hosts the queue + form. `runner.py` at home polls it and drives ADB.

## Deploy
1. Upstash → new free Redis → copy REST URL + token.
2. Push this repo to a **private** GitHub repo.
3. Render → New → Blueprint → select repo → set ADMIN_TOKEN, RUNNER_TOKEN,
   UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN → deploy.
4. cron-job.org → GET https://<app>.onrender.com/health every 5 minutes.
5. On the phone box: `bash scripts/setup_runner.sh`, then `cp runner.env.example runner.env`,
   fill it, `python runner.py`.
6. Open the Render URL, paste admin token, submit a Guild ID.

## Guild requirements
Open join, min level <= BOT_MIN_LEVEL, free slots. Leader-approval guilds will stall.
