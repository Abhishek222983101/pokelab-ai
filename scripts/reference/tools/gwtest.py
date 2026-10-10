"""Probe the Elevate gateway (and Groq) for tool-calling, JSON-schema output, latency and parallelism."""
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.error
import urllib.request

ENV = {}
for line in open(sys.argv[1]):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        ENV[k] = v

GW = ("https://elevate1-0.vercel.app/api/ai", ENV["ELEVATE_TEAM_API_KEY"])
GROQ = ("https://api.groq.com/openai/v1/chat/completions", ENV["GROQ_API_KEY_1"])
OUTPARAM = {"gpt-5.6-luna": "max_completion_tokens", "gpt-5-mini": "max_completion_tokens", "deepseek-v4-pro": "max_tokens"}


def call(endpoint, model, messages, max_out=800, **extra):
    url, key = endpoint
    body = {"model": model, "messages": messages, OUTPARAM.get(model, "max_tokens"): max_out, "stream": False}
    body.update(extra)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
            return time.time() - t, r.status, d, dict(r.headers)
    except urllib.error.HTTPError as e:
        return time.time() - t, e.code, {"error": e.read().decode(errors="ignore")[:400]}, dict(e.headers)


def summarize(tag, res):
    dt, status, d, h = res
    if status != 200:
        print(f"{tag}: HTTP {status} {dt:.2f}s {d.get('error')} retry-after={h.get('Retry-After') or h.get('retry-after')}")
        return
    ch = d["choices"][0]
    msg = ch["message"]
    u = d.get("usage", {})
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    tc = msg.get("tool_calls")
    content = (msg.get("content") or "")
    print(f"{tag}: {dt:.2f}s finish={ch.get('finish_reason')} in={u.get('prompt_tokens')} out={u.get('completion_tokens')} reasoning={rt}"
          f" tool_calls={json.dumps(tc)[:220] if tc else None} content={content[:160]!r}")


TOOLS = [{"type": "function", "function": {
    "name": "submit_experiment",
    "description": "Queue a training run for the grokking kit.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["weight_decay", "train_frac", "reason"],
                   "properties": {"weight_decay": {"type": "number"}, "train_frac": {"type": "number"},
                                  "reason": {"type": "string"}}}}}]
TOOL_MSG = [{"role": "system", "content": "You are an experiment designer. Always act through tools."},
            {"role": "user", "content": "Design the weight-decay=0 what-if for Nanda et al. grokking (p=113, 30% train data). Submit it."}]

SCHEMA = {"type": "json_schema", "json_schema": {"name": "claim", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["metric", "value", "dataset", "setup"],
    "properties": {"metric": {"type": "string"}, "value": {"type": "number"}, "dataset": {"type": "string"},
                   "setup": {"type": "string"}}}}}
CLAIM_MSG = [{"role": "user", "content": "Extract the key result as JSON: 'Our distilled 784-800-800-10 net made 74 test errors on MNIST, versus 146 errors for the same net trained on hard labels, and 67 errors for the 1200-1200 teacher.'"}]

PAPER = open(sys.argv[2]).read()[:12000]  # ~3k tokens of paper text
LONG_MSG = [{"role": "system", "content": "You extract reproduction specs from papers. Reply with compact JSON only."},
            {"role": "user", "content": "From this paper text, extract: model architecture, optimizer, lr, weight_decay, batch size, "
             "train fraction, number of steps, and the headline result with figure reference. Paper:\n\n" + PAPER}]

print("== tool calling")
for m in ["gpt-5.6-luna", "deepseek-v4-pro", "gpt-5-mini"]:
    summarize(f"tools/{m}", call(GW, m, TOOL_MSG, 600, tools=TOOLS, tool_choice="auto"))
summarize("tools/groq gpt-oss-120b", call(GROQ, "openai/gpt-oss-120b", TOOL_MSG, 600, tools=TOOLS, tool_choice="auto"))

print("== json_schema response_format")
for m in ["gpt-5.6-luna", "deepseek-v4-pro"]:
    summarize(f"schema/{m}", call(GW, m, CLAIM_MSG, 400, response_format=SCHEMA))
summarize("json_object/deepseek-v4-pro", call(GW, "deepseek-v4-pro", CLAIM_MSG + [{"role": "system", "content": "Return JSON."}], 400, response_format={"type": "json_object"}))

print("== ~3k-token extraction latency")
for m in ["gpt-5.6-luna", "deepseek-v4-pro", "gpt-5-mini"]:
    summarize(f"long/{m}", call(GW, m, LONG_MSG, 1200))
summarize("long/groq gpt-oss-120b", call(GROQ, "openai/gpt-oss-120b", LONG_MSG, 1200))
summarize("long/groq qwen3.8-27b", call(GROQ, "qwen/qwen3.8-27b", LONG_MSG, 1200))

print("== 6 parallel small calls (luna)")
t = time.time()
with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda i: call(GW, "gpt-5.6-luna", [{"role": "user", "content": f"Say the number {i}."}], 50), range(6)))
for i, r in enumerate(res):
    summarize(f"par{i}", r)
print(f"wall for 6 parallel: {time.time()-t:.2f}s")
