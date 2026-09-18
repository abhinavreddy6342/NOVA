import React, { useMemo } from "react";

function createParticles(count = 70) {
  return Array.from({ length: count }, (_, index) => {
    const seed = index + 1;

    const random = (offset) => {
      const value = Math.sin(seed * 12.9898 + offset * 78.233) * 43758.5453;
      return value - Math.floor(value);
    };

    const size = 1 + random(1) * 2.2;
    const left = random(2) * 100;
    const opacity = 0.16 + random(3) * 0.62;
    const duration = 7 + random(4) * 9;
    const delay = -(random(5) * duration);
    const drift = -18 + random(6) * 36;
    const blur = random(7) > 0.78 ? 1.2 : random(8) * 0.45;

    return {
      id: index,
      left: `${left}%`,
      size: `${size.toFixed(2)}px`,
      opacity: opacity.toFixed(2),
      duration: `${duration.toFixed(2)}s`,
      delay: `${delay.toFixed(2)}s`,
      drift: `${drift.toFixed(1)}px`,
      blur: `${blur.toFixed(2)}px`,
      top: `${-(5 + random(9) * 35)}%`,
    };
  });
}

export default function LoginBackground3D() {
  const particles = useMemo(() => createParticles(70), []);

  return (
    <div
      className="nova-auth-snow-background"
      aria-hidden="true"
    >
      <div className="nova-auth-snow-atmosphere" />

      <div className="nova-auth-snow-field">
        {particles.map((particle) => (
          <span
            key={particle.id}
            className="nova-auth-snow-particle"
            style={{
              left: particle.left,
              top: particle.top,
              width: particle.size,
              height: particle.size,
              opacity: particle.opacity,
              filter: `blur(${particle.blur})`,
              "--snow-duration": particle.duration,
              "--snow-delay": particle.delay,
              "--snow-drift": particle.drift,
            }}
          />
        ))}
      </div>
    </div>
  );
}