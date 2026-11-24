import os, json, urllib.request, urllib.error

_URL = os.environ["UPSTASH_REDIS_REST_URL"].strip().rstrip("/")
_TOK = os.environ["UPSTASH_REDIS_REST_TOKEN"].strip()

if not _URL.startswith(("http://", "https://")):
    raise RuntimeError(
        f"UPSTASH_REDIS_REST_URL must start with https:// — got {_URL[:50]!r}")


class RedisError(RuntimeError):
    pass


def _cmd(*args):
    req = urllib.request.Request(
        _URL, data=json.dumps([str(a) for a in args]).encode(),
        headers={"Authorization": f"Bearer {_TOK}",
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode(errors="ignore")
        raise RedisError(f"HTTP {e.code} from Upstash: {detail}") from None
    except urllib.error.URLError as e:
        raise RedisError(f"cannot reach Upstash: {e.reason}") from None
    if isinstance(body, dict) and body.get("error"):
        raise RedisError(body["error"])
    return body.get("result")


def set_json(key, obj, ttl=None):
    if ttl:
        _cmd("SET", key, json.dumps(obj), "EX", ttl)
    else:
        _cmd("SET", key, json.dumps(obj))


def get_json(key):
    raw = _cmd("GET", key)
    return json.loads(raw) if raw else None


def push(key, val):
    _cmd("RPUSH", key, json.dumps(val))


def pop(key):
    raw = _cmd("LPOP", key)
    return json.loads(raw) if raw else None


def llen(key):
    return int(_cmd("LLEN", key) or 0)


def diagnose():
    return {
        "url_scheme": _URL.split("://")[0],
        "url_host": _URL.split("//", 1)[-1],
        "token_len": len(_TOK),
        "token_prefix": _TOK[:2],
        "ping": _cmd("PING"),
        "keys": _cmd("DBSIZE"),
    }
