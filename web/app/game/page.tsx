"use client";

import { useEffect } from "react";

// The standalone Region/Gym scenes are not built yet; the Lab desk (/lab) is the working game view
// (live room + agents + console), so /game forwards there instead of showing an unfinished scene.
export default function GamePage() {
  useEffect(() => { window.location.replace("/lab/?layout=game"); }, []);
  return <main className="fixed inset-0 bg-navy-deep" />;
}
