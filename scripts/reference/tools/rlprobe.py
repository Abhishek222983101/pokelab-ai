import json,os,sys,time,urllib.request,urllib.error
ENV=dict(l.strip().split("=",1) for l in open(sys.argv[1]) if "=" in l)
time.sleep(5)
def call(i):
    body={"model":"deepseek-v4-pro","messages":[{"role":"user","content":f"Reply with the number {i} only."}],"max_tokens":10}
    req=urllib.request.Request("https://elevate1-0.vercel.app/api/ai",data=json.dumps(body).encode(),method="POST",
        headers={"Content-Type":"application/json","Authorization":"Bearer "+ENV["ELEVATE_TEAM_API_KEY"],"User-Agent":"pokelab/0.1"})
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            d=json.loads(r.read()); h=dict(r.headers)
            return r.status,time.time()-t,d.get("usage",{}).get("total_tokens"),None,{k:v for k,v in h.items() if 'limit' in k.lower() or 'elevate' in k.lower()}
    except urllib.error.HTTPError as e: return e.code,time.time()-t,None,e.headers.get("Retry-After"),{}
t0=time.time()
for i in range(16):
    st,dt,tok,ra,h=call(i); print(f"t+{time.time()-t0:5.1f}s req{i:2d} -> {st} {dt:.2f}s tok={tok} retry_after={ra} {h if i==0 else ''}",flush=True)
    if st==429: break
    time.sleep(1.0)
