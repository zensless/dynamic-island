"""Penyimpanan catatan (JSON di folder data aplikasi)."""
import json

from config import data_dir


class Notes:
    def __init__(self):
        self.path = data_dir() / "notes.json"
        self.items = []
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [
                {"text": str(i.get("text", ""))[:200], "done": bool(i.get("done", False))}
                for i in data
                if isinstance(i, dict) and i.get("text")
            ]
        except Exception:
            self.items = []

    def save(self):
        try:
            self.path.write_text(json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, text: str):
        text = text.strip()
        if not text:
            return
        self.items.insert(0, {"text": text[:200], "done": False})
        self.save()

    def toggle(self, i: int):
        if not 0 <= i < len(self.items):
            return
        item = self.items.pop(i)
        item["done"] = not item["done"]
        if item["done"]:
            self.items.append(item)  # selesai -> ke bawah
        else:
            self.items.insert(0, item)
        self.save()

    def remove(self, i: int):
        if 0 <= i < len(self.items):
            self.items.pop(i)
            self.save()
