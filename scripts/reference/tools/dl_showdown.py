"""Mirror the Showdown assets we may use into a local folder (venue Wi-Fi blocks the site)."""
import json, re, sys, urllib.request, concurrent.futures as cf
from pathlib import Path
BASE = "https://play.pokemonshowdown.com/"
OUT = Path(sys.argv[1])
def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
def listing(path):
    html = get(BASE + path).decode("utf-8", "ignore")
    return [h for h in re.findall(r'href="([^"?]+)"', html) if not h.startswith("..") and not h.endswith("/")]
dex = json.loads(get(BASE + "data/pokedex.json"))
mons = sorted({k for k, v in dex.items() if 1 <= v.get("num", 0) <= 251 and not v.get("forme")})
jobs = []
for d in ["ani", "ani-back", "gen5", "gen5-back", "gen3", "gen3-back"]:
    jobs += [(f"sprites/{d}/{m}.{'gif' if d.startswith('ani') else 'png'}", OUT / "sprites" / d) for m in mons]
for f in listing("sprites/trainers/"): jobs.append((f"sprites/trainers/{f}", OUT / "sprites" / "trainers"))
for f in listing("fx/"): jobs.append((f"fx/{f}", OUT / "fx"))
for f in ["poke-ball", "great-ball", "ultra-ball", "master-ball", "rare-candy", "everstone", "leftovers"]:
    jobs.append((f"sprites/itemicons/{f}.png", OUT / "sprites" / "itemicons"))
def fetch(job):
    rel, d = job; d.mkdir(parents=True, exist_ok=True); dst = d / rel.rsplit("/", 1)[1]
    if dst.exists() and dst.stat().st_size: return "skip"
    try: dst.write_bytes(get(BASE + rel)); return "ok"
    except Exception as e: return f"fail {rel} {e}"
with cf.ThreadPoolExecutor(16) as ex: res = list(ex.map(fetch, jobs))
(OUT / "pokedex.json").write_bytes(json.dumps({m: dex[m] for m in mons}).encode())
print("jobs", len(jobs), "ok", res.count("ok"), "skip", res.count("skip"), "fail", sum(r.startswith("fail") for r in res))
for r in [r for r in res if r.startswith("fail")][:15]: print(r)
