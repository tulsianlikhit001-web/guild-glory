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
        raise RedisError(f"UPSTASH_REDIS_REST_URL must start with https:// — got {url[:50]!r}")
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
