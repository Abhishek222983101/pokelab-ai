# Chaos drills (P12.2, AC-23)

Each script below is a real drill against real code, not a simulation
layer bolted on top. Run each before a rehearsal (P12.6).

| Drill | Script | What it proves | Status |
|---|---|---|---|
| Kill brain mid-project | `kill_brain.sh` | A submitted job survives the submitting brain connection dying — labd doesn't need brain alive to finish a job. **Honest gap**: no process supervisor auto-restarts a crashed brain with backoff yet (§5.2/P1.7 described one; it was never built). | real, passing |
| Kill worker mid-run | `kill_worker.sh` | SIGKILLing a live worker process surfaces a real `Done{status:"error"}`, not a hang. [BUG FOUND & FIXED this phase]: before the fix, the caller's receiver hung forever and the slot leaked permanently busy. | real, passing — bug fixed |
| Network off / 429 storm | `network_and_rate_limit.sh` | The LLM router falls back to a healthy provider when one is unusable, and raises a clear error (not a hang) when all routes are exhausted. **Scope note**: uses fault injection, not a literal network severing or a real 429 storm against the team's shared Elevate/Groq quota — see the script for why. | real, passing |
| Disk low | `disk_low.sh` | The real `df`-backed free-space primitive both the doctor check and the job-submission guard share. **Scope note**: doesn't actually fill the disk — see the script for why, and how to manually verify the guard fires. | real primitive tested; guard verified by code review |
| Unplug charger | `unplug_charger.sh` | The real power check (doctor.rs, already covered by lab-telemetry's tests) flips correctly. Manual — it's a physical action. | real, manual |

Run them all (skips the manual one unless you're at the keyboard):

```sh
./kill_worker.sh && ./kill_brain.sh && ./network_and_rate_limit.sh && ./disk_low.sh
```
