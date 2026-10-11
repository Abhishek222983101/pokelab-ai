'use client';

/**
 * REPLAY driver. Walks a fixed script over the fixture in lib/demo.ts so the lab visibly moves when labd is offline.
 * Every step emits a feed event with a `why`, exactly like a real decision event would — the world still only
 * reacts to state, never to this script directly.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { DEMO_AGENTS, DEMO_FEED, type AgentStatus, type DemoAgent, type DemoEvent, type Station } from './demo';

interface Step {
  agent: string;
  station: Station;
  status: AgentStatus;
  task: string;
  thought: string;
  event: Omit<DemoEvent, 'seq' | 't'>;
  oak?: string;
}

const SCRIPT: Step[] = [
  { agent: 'a-debug', station: 'server_rack', status: 'working', task: 'Fix CUDA OOM on job #12 retry', thought: 'Recalled fix #3: halve the batch, scale LR by √ratio. Re-queuing.',
    event: { kind: 'agent.task_started', who: 'squirtle', text: 'Squirtle woke up to debug the OOM', why: 'Medic routed failure sig cuda_oom → capability “debug”', tone: 'info' },
    oak: 'A crash! Squirtle, you are up — the Pokédex has a fix for this one.' },
  { agent: 'a-scribe', station: 'scribe_desk', status: 'thinking', task: 'Draft the evidence table', thought: 'Collecting seeds 0–4 and the paper’s claim 3 into one Markdown table.',
    event: { kind: 'agent.task_started', who: 'hoothoot', text: 'Hoothoot started the report draft', why: 'Analyst verdict PARTIAL unblocked “Write report”', tone: 'info' } },
  { agent: 'a-run', station: 'arena_door', status: 'working', task: 'job #13: wd=0.1 × frac=0.5 on local GPU', thought: 'Router: local pred 14 s, Kaggle queue 55 s → staying local.',
    event: { kind: 'compute.route_decided', who: 'magneton', text: 'Job #13 routed to local GPU', why: 'Predicted 14 s local vs 55 s queue on Kaggle', tone: 'info' },
    oak: 'Three battles at once! The Oracle will call retreat for the losers.' },
  { agent: 'a-debug', station: 'lawn', status: 'asleep', task: 'Idle — nothing failing', thought: '',
    event: { kind: 'agent.task_completed', who: 'squirtle', text: 'Squirtle fixed the OOM and went back to sleep', why: 'reward 0.84 · cost 6 GPU-s · human 👍', tone: 'good' } },
  { agent: 'a-impl', station: 'library_desk', status: 'thinking', task: 'Cross-check weight init with the paper', thought: 'Appendix B says init std 1/√d. My config used 0.02 — that may explain the late grok.',
    event: { kind: 'agent.thought', who: 'charmeleon', text: 'Charmeleon found a config mismatch vs the paper', why: 'Cited paper §A.2 (claim span 14) — will raise to the Analyst', tone: 'warn' },
    oak: 'Interesting. Charmeleon, show the Analyst — that is a lead on why we differ.' },
  { agent: 'a-analyst', station: 'quest_board', status: 'working', task: 'Test H2: init-scale explains the remaining gap', thought: 'Scheduling 3 diagnostic runs (init 0.02 / 0.05 / 1/√d). Oracle budget 90 GPU-s.',
    event: { kind: 'oak.selection', who: 'kadabra', text: 'Oak sent Kadabra to the quest board', why: 'Thompson draw: Kadabra 0.88 vs Abra 0.55', tone: 'info' } },
];

const clock = (d = new Date()) => d.toTimeString().slice(0, 8);

export function useReplay(running = true) {
  const [agents, setAgents] = useState<DemoAgent[]>(DEMO_AGENTS);
  const [feed, setFeed] = useState<DemoEvent[]>(DEMO_FEED);
  const [oakSay, setOakSay] = useState('Welcome back, Ash! Three projects are waiting on you.');
  const [approved, setApproved] = useState(false);
  const step = useRef(0);
  const seq = useRef(1042);

  const push = useCallback((e: Omit<DemoEvent, 'seq' | 't'>) => {
    seq.current += 1;
    setFeed((f) => [{ ...e, seq: seq.current, t: clock() }, ...f].slice(0, 60));
  }, []);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      const s = SCRIPT[step.current % SCRIPT.length];
      step.current += 1;
      setAgents((as) => as.map((a) => (a.id === s.agent ? { ...a, station: s.station, status: s.status, task: s.task, thought: s.thought } : a)));
      push(s.event);
      if (s.oak) setOakSay(s.oak);
    }, 6500);
    return () => window.clearInterval(id);
  }, [running, push]);

  /** Researcher approves the Eevee spawn (the Poké Ball moment). */
  const approveSpawn = useCallback(() => {
    setApproved(true);
    push({ kind: 'human.approved', who: 'ash', text: 'You approved the Eevee spawn', why: 'Approval gate: spawn_agent requires the researcher', tone: 'good' });
    setAgents((as) => as.map((a) => (a.id === 'a-eevee' ? { ...a, station: 'quest_board', status: 'thinking', task: 'Learning fourier_analysis', thought: 'Reading the Grokking appendix on the Fourier-features circuit.', level: 6 } : a)));
    window.setTimeout(() => push({ kind: 'agent.spawned', who: 'eevee', text: 'Eevee joined the team', why: 'Spec #9 inserted · capability fourier_analysis · v1', tone: 'good' }), 400);
    setOakSay('Go, Eevee! A new specialist for the team.');
  }, [push]);

  const rejectSpawn = useCallback(() => {
    setApproved(true);
    push({ kind: 'human.rejected', who: 'ash', text: 'You sent Eevee away', why: 'Spawn rejected — gap stays open, Scout will re-propose later', tone: 'warn' });
    setAgents((as) => as.filter((a) => a.id !== 'a-eevee'));
  }, [push]);

  return { agents, feed, oakSay, approved, approveSpawn, rejectSpawn };
}
