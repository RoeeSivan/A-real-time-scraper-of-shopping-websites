"use client";

import { useEffect, useState } from "react";

export function LiveClock() {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    // Set initial time
    setTime(new Date().toLocaleTimeString("en-US", { hour24: true }));

    // Update every second
    const interval = setInterval(() => {
      setTime(new Date().toLocaleTimeString("en-US", { hour24: true }));
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className="font-mono text-sm tracking-wider"
      style={{
        color: "#FFB347",
        textShadow: "0 0 10px rgba(255, 179, 71, 0.3)",
      }}
    >
      {time || "00:00:00"}
    </div>
  );
}
