import sys, cv2, yaml

sys.path.insert(0, ".")
from ffguildbot.device import Device

dev = Device(sys.argv[1], yaml.safe_load(open("config.yaml")))
img = dev.shot()
h, w = img.shape[:2]
for i in range(1, 20):
    cv2.line(img, (int(w * i / 20), 0), (int(w * i / 20), h), (0, 255, 0), 1)
    cv2.line(img, (0, int(h * i / 20)), (w, int(h * i / 20)), (0, 255, 0), 1)
    cv2.putText(img, f"{i/20:.2f}", (int(w * i / 20) + 2, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
cv2.imwrite("grid.png", img)
print("wrote grid.png")
