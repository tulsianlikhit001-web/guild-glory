import os, time
import cv2
import pytesseract

TPL_DIR = os.path.join(os.path.dirname(__file__), "templates")
_cache = {}


def _load(name):
    if name not in _cache:
        path = os.path.join(TPL_DIR, name + ".png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"missing template {path}")
        _cache[name] = cv2.imread(path, cv2.IMREAD_COLOR)
    return _cache[name]


def find(screen, name, conf=0.82, region=None):
    tpl = _load(name)
    h, w = screen.shape[:2]
    if region:
        x1, y1, x2, y2 = (int(region[0] * w), int(region[1] * h),
                          int(region[2] * w), int(region[3] * h))
        view, ox, oy = screen[y1:y2, x1:x2], x1, y1
    else:
        view, ox, oy = screen, 0, 0
    if view.shape[0] < tpl.shape[0] or view.shape[1] < tpl.shape[1]:
        return None
    res = cv2.matchTemplate(view, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < conf:
        return None
    th, tw = tpl.shape[:2]
    return ((ox + loc[0] + tw / 2) / w, (oy + loc[1] + th / 2) / h, score)


def wait_for(dev, name, timeout=30, conf=0.82, region=None, poll=0.4):
    end = time.time() + timeout
    while time.time() < end:
        hit = find(dev.shot(), name, conf, region)
        if hit:
            return hit
        time.sleep(poll)
    return None


def tap_if(dev, name, **kw):
    hit = wait_for(dev, name, **kw)
    if not hit:
        return False
    dev.tap_rel(hit[0], hit[1])
    return True


def exists(dev, name, conf=0.82, region=None):
    return find(dev.shot(), name, conf, region) is not None


def read_int(screen, region, whitelist="0123456789"):
    h, w = screen.shape[:2]
    x1, y1, x2, y2 = (int(region[0] * w), int(region[1] * h),
                      int(region[2] * w), int(region[3] * h))
    crop = screen[y1:y2, x1:x2]
    crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    txt = pytesseract.image_to_string(
        crop, config=f"--psm 7 -c tessedit_char_whitelist={whitelist}")
    digits = "".join(c for c in txt if c.isdigit())
    return int(digits) if digits else None
