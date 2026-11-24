import os, json, urllib.request

_URL = os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/")
_TOK = os.environ["UPSTASH_REDIS_REST_TOKEN"]


def _cmd(*args):
    req = urllib.request.Request(
        _URL, data=json.dumps([str(a) for a in args]).encode(),
        headers={"Authorization": f"Bearer {_TOK}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["result"]


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
