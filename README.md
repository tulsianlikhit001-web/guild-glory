# FF Guild Glory Bot — Control Plane

Render hosts the queue + form. `runner.py` on the phone box polls it and drives ADB.

## Deploy

1. Upstash → new free Redis → copy REST URL + token.
2. Render → New → Blueprint → select this repo → set ADMIN_TOKEN, RUNNER_TOKEN,
   UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN → deploy.
3. cron-job.org → GET `https://<service>.onrender.com/health` every 5 minutes.
4. On the phone box: `bash scripts/setup_runner.sh`, then
   `cp runner.env.example runner.env`, fill it, `python runner.py`.
5. Open the Render URL, paste the admin token, submit a Guild ID.

## Before the first job

- `python scripts/check_templates.py` must print `27/27 required templates present`.
  Missing templates mean missing taps.
- `ffapi.py` must exist in the repo root (run `python patch_ffapi.py` once).

## Guild requirements

Open join, min level <= BOT_MIN_LEVEL, free slots >= bots.
Leader-approval guilds stall until a leader approves.

## Debugging a job

The job page streams the runner log and each bot's result. `outcome` is the
verdict: `ok`, `guild full — free a slot`, `level N < 2 after warmup`,
`no join or apply button`, `guild button not found`, `crash ...`.

## Env

| var | where | meaning |
|---|---|---|
| `BOT_MIN_LEVEL` | both | accounts below this get warmed, then rejected |
| `FF_NO_LEAVE` | runner | keep accounts in the guild after the job |
| `FF_NO_WARMER` | runner | disable the account pool warmer |
