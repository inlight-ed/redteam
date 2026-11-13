import json
import os

class EventLogger:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "a", encoding="utf-8")

    def write(self, payload):
        self.f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()
