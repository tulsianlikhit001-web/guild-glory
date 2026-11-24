import os, re, time, uuid
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import store

app = FastAPI(title="FF Guild Glory Bot")

ADMIN = os.environ["ADMIN_TOKEN"]
RUNNER = os.environ["RUNNER_TOKEN"]
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", 6))
MAX_BOTS = int(os.environ.get("MAX_BOTS_PER_JOB", 4))
MIN_LEVEL = os.environ.get("BOT_MIN_LEVEL", "2")
Q = "queue:jobs"
GUILD_RE = re.compile(r"^\d{6,12}$")

CSS = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#0b0e14;color:#e6e9ef;
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding:40px 20px 64px}
h1{font-size:22px;letter-spacing:-.02em;margin:0 0 4px}
.sub{color:#8b93a7;font-size:13px;margin:0 0 28px}
.card{background:#141924;border:1px solid #232a3a;border-radius:14px;padding:22px}
label{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;
color:#8b93a7;margin:0 0 6px}
.field{margin-bottom:16px}
input{width:100%;background:#0b0e14;border:1px solid #2b3448;border-radius:9px;
padding:11px 13px;color:#e6e9ef;font:inherit;font-variant-numeric:tabular-nums}
input:focus{outline:none;border-color:#3d7dff;box-shadow:0 0 0 3px #3d7dff22}
.row{display:flex;gap:14px}
.row .field{flex:1}
button{width:100%;margin-top:6px;background:#3d7dff;border:0;border-radius:9px;
padding:12px;color:#fff;font:inherit;font-weight:600;cursor:pointer}
button:hover{background:#2f6ae6}
.note{font-size:13px;color:#8b93a7;margin:20px 0 0;padding:14px 16px;
background:#141924;border:1px solid #232a3a;border-left:3px solid #f5a524;border-radius:9px}
.bar{display:flex;gap:20px;margin-top:16px;font-size:13px;color:#8b93a7}
.pill{display:inline-flex;align-items:center;gap:6px}
.dot{width:7px;height:7px;border-radius:50%;background:#3fb950}
.dot.off{background:#6b7280}
.dot.warn{background:#f5a524}
pre{background:#0b0e14;border:1px solid #232a3a;border-radius:10px;padding:14px;
overflow-x:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#c8cede}
ul{list-style:none;padding:0;margin:0;font:12px/1.7 ui-monospace,monospace;color:#aeb6c7}
ul li{padding:3px 0;border-bottom:1px solid #1a2030}
.err{color:#ff7b72}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#8b93a7;
margin:26px 0 8px}
a{color:#5d9bff}
.meta{font-size:13px;color:#8b93a7;margin-bottom:20px}
"""

SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FF Guild Glory</title>__REFRESH__<style>__CSS__</style></head>
<body><main>__BODY__</main></body></html>"""


def _html(body, status=200, refresh=None):
    head = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    page = (SHELL.replace("__CSS__", CSS).replace("__REFRESH__", head)
            .replace("__BODY__", body))
    return HTMLResponse(page, status_code=status)


def _runner(tok):
    if tok != RUNNER:
        raise HTTPException(401, "bad runner token")


@app.get("/health")
def health():
    try:
        return {"ok": True, "queued": store.llen(Q)}
    except Exception as e:
        return JSONResponse(status_code=503,
                            content={"ok": False, "error": str(e)[:140]})


@app.get("/diag")
def diag():
    try:
        return {"ok": True, **store.diagnose()}
    except Exception as e:
        return JSONResponse(status_code=503, content={
            "ok": False,
            "error": f"{type(e).__name__}: {e}"[:200],
            "url": os.environ.get("UPSTASH_REDIS_REST_URL", "")[:60],
            "token_len": len(os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")),
        })


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        hb = store.get_json("runner:heartbeat") or {}
        q = store.llen(Q)
        age = int(time.time() - hb["t"]) if hb.get("t") else None
        if age is None:
            beat = '<span class="pill"><span class="dot off"></span>never seen</span>'
        elif age < 180:
            beat = f'<span class="pill"><span class="dot"></span>runner {age}s ago</span>'
        else:
            beat = f'<span class="pill"><span class="dot warn"></span>stale {age // 60}m</span>'
        free = hb.get("free")
        devs = f' &nbsp;·&nbsp; {free}/{hb["devices"]} devices free' if devs_ok(hb) else ""
        body = f"""
<h1>FF Guild Glory Bot</h1>
<p class="sub">Queue a guild join, the phone box does the rest.</p>
<div class="card">
<form method="post" action="/launch">
  <div class="field">
    <label for="admin">Admin token</label>
    <input id="admin" name="admin" type="password" required autocomplete="current-password">
  </div>
  <div class="field">
    <label for="guild">Guild ID</label>
    <input id="guild" name="guild_id" required pattern="[0-9]{{6,12}}"
           inputmode="numeric" placeholder="e.g. 3057005250">
  </div>
  <div class="row">
    <div class="field"><label for="hours">Hours</label>
      <input id="hours" name="hours" type="number" min="1" max="24" value="{DEFAULT_HOURS}" required></div>
    <div class="field"><label for="bots">Bots</label>
      <input id="bots" name="bots" type="number" min="1" max="{MAX_BOTS}" value="{MAX_BOTS}" required></div>
  </div>
  <button>Launch</button>
</form>
</div>
<p class="note"><b>Before launching:</b> set the guild to open-join, min level
{MIN_LEVEL} or lower, and leave at least {MAX_BOTS} free slots.</p>
<div class="bar"><span>{beat}</span><span>queued: {q}</span>{devs}</div>
<script>
const a = document.getElementById("admin");
a.value = localStorage.getItem("ff_admin") || "";
document.querySelector("form").addEventListener("submit",
  () => localStorage.setItem("ff_admin", a.value));
</script>"""
        return _html(body)
    except Exception as e:
        return _html(
            f'<h1>FF Guild Glory Bot</h1>'
            f'<p class="err">{type(e).__name__}: {e}</p>'
            f'<p><a href="/diag">open /diag</a></p>', status=503)


def devs_ok(hb):
    return hb.get("devices") is not None and hb.get("free") is not None


@app.post("/launch")
def launch(admin: str = Form(...), guild_id: str = Form(...),
           hours: int = Form(...), bots: int = Form(...)):
    if admin != ADMIN:
        raise HTTPException(401, "bad admin token")
    guild_id = guild_id.strip()
    if not GUILD_RE.match(guild_id):
        raise HTTPException(400, "guild id must be 6-12 digits")
    bots = max(1, min(bots, MAX_BOTS))
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "guild": guild_id, "hours": max(1, min(hours, 24)),
           "bots": bots, "created": time.time(), "status": "queued",
           "results": [], "log": []}
    store.set_json(f"job:{job_id}", job, ttl=86400)
    store.push(Q, {"id": job_id})
    return RedirectResponse(f"/job/{job_id}", status_code=303)


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_page(job_id: str):
    j = store.get_json(f"job:{job_id}")
    if not j:
        raise HTTPException(404, "no such job")
    live = j["status"] in ("queued", "running")
    rows = "".join(f"<li>{r}</li>" for r in j.get("log", [])[-40:]) or "<li>—</li>"
    res = "".join(f"<li>{r}</li>" for r in j.get("results", [])) or "<li>—</li>"
    body = f"""
<h1>Job {job_id}</h1>
<p class="meta">guild {j['guild']} &nbsp;·&nbsp; {j['hours']}h &nbsp;·&nbsp;
{j['bots']} bots &nbsp;·&nbsp; <b>{j['status']}</b></p>
<h2>Log</h2><ul>{rows}</ul>
<h2>Results</h2><ul>{res}</ul>
<p class="meta" style="margin-top:24px"><a href="/">new job</a></p>"""
    return _html(body, refresh=8 if live else None)
