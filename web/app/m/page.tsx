export default function PokegearPage() {
  return (
    <main style={{ padding: 16 }}>
      <h1>Pokégear</h1>
      <p>Pair with the lab by scanning the QR code shown on the desk console.</p>
      <p style={{ opacity: 0.6, fontSize: 13 }}>
        Pairing (via /api/pair/claim) and the approve/redirect/kill controls are
        not wired up yet — this is the PWA shell only.
      </p>
    </main>
  );
}
