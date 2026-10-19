"""深挖 demo 登记：python -m radar.deep <owner/repo> <slug>，写入 data/deep.json 并重建网站。"""
import json
import sys
from datetime import datetime

from . import config, site


def register(full_name: str, slug: str):
    f = config.DATA / "deep.json"
    items = json.loads(f.read_text()) if f.exists() else []
    items = [x for x in items if x["slug"] != slug]
    items.append({"date": datetime.now(config.BJ).date().isoformat(), "full_name": full_name,
                  "slug": slug, "url": f"https://github.com/{full_name}"})
    f.write_text(json.dumps(items, ensure_ascii=False, indent=1))
    site.build()


if __name__ == "__main__":
    register(sys.argv[1], sys.argv[2])
