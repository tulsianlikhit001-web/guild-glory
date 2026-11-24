import os, json, urllib.request, urllib.error


class RedisError(RuntimeError):
    pass


def _cfg():
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
    tok = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url:
        raise RedisError("UPSTASH_REDIS_REST_URL is not set")
    if not tok:
        raise RedisError("UPSTASH_REDIS_REST_TOKEN is not set")
    if not url.startswith(("http://", "https://")):
        raise RedisError(
            f"UPSTASH_REDIS_REST_URL must start with https:// — got {url[:50]!r}")
    return url, tok


def _cmd(*args):
    url, tok = _cfg()
    req = urllib.request.Request(
        url, data=json.dumps([str(a) for a in args]).encode(),
        headers={"Authorization": f"Bearer {tok}",
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
    url, tok = _cfg()
    return {
        "url_scheme": url.split("://")[0],
        "url_host": url.split("//", 1)[-1],
        "token_len": len(tok),
        "token_prefix": tok[:2],
        "ping": _cmd("PING"),
        "keys": _cmd("DBSIZE"),
        "functions": sorted(
            n for n, v in globals().items()
            if callable(v) and not n.startswith("_") and n != "RedisError"),
    }
