#!/usr/bin/env python3
"""Run grok.py with a timeout; log METRIC lines; report launch->first METRIC, launch->first step,
avg/peak process CPU% (sampled from /proc), peak RSS, peak GPU util.
usage: run.py LOGFILE TIMEOUT_S -- cmd...
"""
import os, subprocess, sys, threading, time

log, timeout = sys.argv[1], float(sys.argv[2])
cmd = sys.argv[sys.argv.index("--") + 1:]
TCK = os.sysconf("SC_CLK_TCK")


def tree_stats(root):
    """sum utime+stime (ticks) and RSS (kB) over process tree"""
    pids, tot_t, tot_rss = [root], 0, 0
    try:
        out = subprocess.run(["pgrep", "-P", str(root)], capture_output=True, text=True).stdout.split()
        pids += [int(x) for x in out]
    except Exception:
        pass
    for pid in pids:
        try:
            st = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
            tot_t += int(st[11]) + int(st[12])
            for line in open(f"/proc/{pid}/status"):
                if line.startswith("VmRSS"):
                    tot_rss += int(line.split()[1])
        except Exception:
            pass
    return tot_t, tot_rss


t0 = time.perf_counter()
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
samples, peak_rss, gpu_utils = [], 0, []
stop = False


def sampler():
    global peak_rss
    last_t, last_w = 0, time.perf_counter()
    while not stop:
        time.sleep(1.0)
        ticks, rss = tree_stats(proc.pid)
        now = time.perf_counter()
        samples.append(100 * (ticks - last_t) / TCK / (now - last_w))
        last_t, last_w = ticks, now
        peak_rss = max(peak_rss, rss)
        try:
            u = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
            gpu_utils.append(int(u))
        except Exception:
            pass


th = threading.Thread(target=sampler, daemon=True)
th.start()
first_metric = first_step = None
timer = threading.Timer(timeout, proc.kill)
timer.start()
with open(log, "w") as f:
    for line in proc.stdout:
        now = time.perf_counter() - t0
        f.write(line)
        if line.startswith("METRIC"):
            if first_metric is None:
                first_metric = now
            if first_step is None and " step=" in line:
                first_step = now
            if "event=" in line:
                print(line.strip())
proc.wait()
timer.cancel()
stop = True
total = time.perf_counter() - t0
cpu = samples[1:] or samples
print(f"RUN rc={proc.returncode} total_s={total:.2f} first_metric_s={first_metric} first_step_s={first_step} "
      f"cpu_avg%={sum(cpu)/max(len(cpu),1):.0f} cpu_peak%={max(cpu or [0]):.0f} peak_rss_MB={peak_rss/1024:.0f} "
      f"gpu_util_avg%={sum(gpu_utils)/max(len(gpu_utils),1):.0f}")
