import subprocess, time, random
import numpy as np, cv2


class FlowError(RuntimeError):
    pass


class Device:
    def __init__(self, serial, cfg):
        self.serial = serial
        self.cfg = cfg
        self._size = None

    def _sh(self, *args, timeout=25, retries=2):
        last = "unknown"
        for i in range(retries + 1):
            try:
                p = subprocess.run(["adb", "-s", self.serial, *args],
                                   capture_output=True, timeout=timeout)
                if p.returncode != 0 and i < retries:
                    last = p.stderr.decode(errors="ignore").strip()[:120] or "nonzero exit"
                    time.sleep(0.5)
                    continue
                return p.stdout
            except subprocess.TimeoutExpired:
                last = f"timeout {args[:2]}"
                if i == retries:
                    raise FlowError(f"adb {last}")
                time.sleep(0.8)
            except FileNotFoundError:
                raise FlowError("adb not on PATH")
        raise FlowError(f"adb failed: {last}")

    def size(self):
        if self._size is None:
            out = self._sh("shell", "wm", "size").decode(errors="ignore")
            lines = [l for l in out.splitlines() if "x" in l and ":" in l]
            if not lines:
                raise FlowError("cannot read screen size")
            w, h = lines[-1].split(":")[-1].strip().split("x")[:2]
            self._size = (int(w), int(h))
        return self._size

    def shot(self):
        for i in range(3):
            raw = self._sh("exec-out", "screencap", "-p", timeout=20)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is not None and img.size:
                return img
            time.sleep(0.4)
        raise FlowError("empty screenshot")

    def tap_rel(self, rx, ry, jitter=0.006):
        w, h = self.size()
        x = int((rx + random.uniform(-jitter, jitter)) * w)
        y = int((ry + random.uniform(-jitter, jitter)) * h)
        self._sh("shell", "input", "tap", str(x), str(y))
        time.sleep(random.uniform(0.05, 0.16))

    def swipe_rel(self, x1, y1, x2, y2, ms=250):
        w, h = self.size()
        self._sh("shell", "input", "swipe", str(int(x1 * w)), str(int(y1 * h)),
                 str(int(x2 * w)), str(int(y2 * h)), str(ms))
        time.sleep(random.uniform(0.1, 0.25))

    def text(self, s):
        s = str(s)
        for chunk in [s[i:i + 60] for i in range(0, len(s), 60)] or [""]:
            self._sh("shell", "input", "text", chunk.replace(" ", "%s"))
            time.sleep(random.uniform(0.2, 0.4))

    def back(self):
        self._sh("shell", "input", "keyevent", "4")
        time.sleep(random.uniform(0.4, 0.9))

    def launch(self):
        self._sh("shell", "monkey", "-p", self.cfg["game"]["package"],
                 "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(self.cfg["game"]["launch_wait_s"])

    def foreground(self):
        out = self._sh("shell", "dumpsys", "window", "displays").decode(errors="ignore")
        return self.cfg["game"]["package"] in out

    def ensure_foreground(self, tries=3):
        for _ in range(tries):
            if self.foreground():
                return
            self.launch()
        raise FlowError("game not foreground")
