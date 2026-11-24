import os, time, uuid
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
import store

app = FastAPI(title="FF Guild Glory Bot")
ADMIN = os.environ["ADMIN_TOKEN"]
RUNNER = os.environ["RUNNER_TOKEN"]
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", 6))
MAX_BOTS = int(os.environ.get("MAX_BOTS_PER_JOB", 4))
MIN_LEVEL = os.environ.get("BOT_MIN_LEVEL", "2")
Q = "queue:jobs"

PAGE = """
<h2>FF Guild Glory Bot</h2>
<form method="post" action="/launch">
  <input name="admin" type="password" placeholder="admin token" required><br><br>
  <label>Guild ID <input name="guild_id" required pattern="[0-9]{6,12}"></label><br>
  <label>Hours <input name="hours" type="number" min="1" max="24" value="{dh}"></label><br>
  <label>Bots <input name="bots" type="number" min="1" max="{mb}" value="{mb}"></label><br><br>
  <button>Launch</button>
</form>
<p><b>Before launching, set the guild to open-join, min level {lv} or lower,
and make sure there are at least {mb} free slots.</b></p>
<p>Runner heartbeat: {hb} &nbsp;|&nbsp; queued: {q}</p>
"""


def _runner(tok):
    if tok != RUNNER:
        raise HTTPException(401, "bad runner token")


@app.get("/health")
def health():
    return {"ok": True, "queued": store.llen(Q), "t": int(time.time())}


@app.get("/", response_class=HTMLResponse)
def index():
    hb = store.get_json("runner:heartbeat") or {}
    seen = f"{int(time.time() - hb['t'])}s ago" if hb.get("t") else "never"
    return PAGE.format(dh=DEFAULT_HOURS, mb=MAX_BOTS, lv=MIN_LEVEL,
                       hb=seen, q=store.llen(Q))


@app.post("/launch", response_class=HTMLResponse)
def launch(admin: str = Form(...), guild_id: str = Form(...),
           hours: int = Form(...), bots: int = Form(...)):
    if admin != ADMIN:
        raise HTTPException(401, "bad admin token")
    bots = max(1, min(bots, MAX_BOTS))
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "guild": guild_id, "hours": max(1, min(hours, 24)),
           "bots": bots, "created": time.time(), "status": "queued",
           "results": [], "log": []}
    store.set_json(f"job:{job_id}", job, ttl=86400)
    store.push(Q, {"id": job_id})
    return (f"<p>queued {job_id} — {bots} bots for {job['hours']}h</p>"
            f"<p><a href='/job/{job_id}'>status</a></p>")


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_page(job_id: str):
    j = store.get_json(f"job:{job_id}")
    if not j:
        raise HTTPException(404, "no such job")
    rows = "".join(f"<li>{r}</li>" for r in j.get("log", [])[-40:])
    res = "".join(f"<li>{r}</li>" for r in j.get("results", []))
    return (f"<p>{job_id} — {j['status']} — guild {j['guild']} — {j['hours']}h</p>"
            f"<h3>log</h3><ul>{rows}</ul><h3>results</h3><ul>{res}</ul>")


@app.get("/api/next-job")
def next_job(x_runner_token: str = Header(...)):
    _runner(x_runner_token)
    head = store.pop(Q)
    if not head:
        return {"job": None}
    job = store.get_json(f"job:{head['id']}")
    if job:
        job["status"] = "running"
        store.set_json(f"job:{job['id']}", job, ttl=86400)
    return {"job": job}


@app.post("/api/job/{job_id}/log")
async def job_log(job_id: str, request: Request,
                  x_runner_token: str = Header(...)):
    _runner(x_runner_token)
    line = (await request.json()).get("line", "")[:300]
    j = store.get_json(f"job:{job_id}")
    if j:
        j.setdefault("log", []).append(line)
        j["log"] = j["log"][-200:]
        store.set_json(f"job:{job_id}", j, ttl=86400)
    return {"ok": True}


@app.post("/api/job/{job_id}/result")
async def job_result(job_id: str, request: Request,
                     x_runner_token: str = Header(...)):
    _runner(x_runner_token)
    body = await request.json()
    j = store.get_json(f"job:{job_id}")
    if j:
        j.setdefault("results", []).append(body)
        j["status"] = "done" if len(j["results"]) >= j["bots"] else "running"
        store.set_json(f"job:{job_id}", j, ttl=86400)
    return {"ok": True}


@app.post("/api/heartbeat")
async def heartbeat(request: Request, x_runner_token: str = Header(...)):
    _runner(x_runner_token)
    body = await request.json()
    store.set_json("runner:heartbeat", {"t": time.time(), **body}, ttl=180)
    return {"ok": True}
