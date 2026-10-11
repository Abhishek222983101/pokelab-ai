/**
 * Minimal real audio (P9.7): plays actual tones via the Web Audio API
 * directly. We don't have real PokeAPI cry files downloaded (P9.6's
 * fuller asset pipeline covers that — tracked as a follow-on), so this
 * is honestly a placeholder SFX layer, not silence — every spawn/retire/
 * reproduction still makes a real, audible sound, just not a Pokémon cry
 * yet. howler (the pinned dependency) is the natural place to swap in
 * real .ogg files once they're fetched, without changing call sites.
 */
let audioCtx: AudioContext | null = null;

function ctx(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    try {
      audioCtx = new AudioContext();
    } catch {
      return null;
    }
  }
  return audioCtx;
}

export function playTone(frequencyHz: number, durationMs: number, type: OscillatorType = "sine"): void {
  const c = ctx();
  if (!c) return;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = type;
  osc.frequency.value = frequencyHz;
  gain.gain.setValueAtTime(0.15, c.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + durationMs / 1000);
  osc.connect(gain).connect(c.destination);
  osc.start();
  osc.stop(c.currentTime + durationMs / 1000);
}

export function sfxSpawn(): void {
  playTone(660, 150);
  setTimeout(() => playTone(880, 200), 100);
}

export function sfxRetire(): void {
  playTone(220, 400, "triangle");
}

export function sfxReproduced(): void {
  playTone(523, 120);
  setTimeout(() => playTone(659, 120), 120);
  setTimeout(() => playTone(784, 250), 240);
}
