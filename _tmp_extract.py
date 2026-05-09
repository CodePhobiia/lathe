import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())

def search(obj, key, results=None, parent=""):
    if results is None:
        results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_parent = f"{parent}.{k}" if parent else k
            if k == key:
                results.append((new_parent, v))
            search(v, key, results, new_parent)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            search(item, key, results, f"{parent}[{i}]")
    return results

for key in ["projection_trust", "realness_score", "highlow_fake_detail_penalty",
            "ray_backend_available", "decision", "fake_detail",
            "bake_cleanliness", "normal_richness", "ray_hit_count",
            "fallback_count", "score", "cert_score", "overall_score"]:
    hits = search(data, key)
    for path_str, val in hits[:5]:
        if isinstance(val, (int, float, str, bool)) or val is None:
            print(f"{key:35s} | {path_str[:80]:80s} = {val}")
        else:
            print(f"{key:35s} | {path_str[:80]:80s} = (complex)")
