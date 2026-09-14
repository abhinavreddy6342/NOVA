import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

export default function ParticleField() {
  const pointsRef = useRef();

  const positions = useMemo(() => {
    const count = 900;
    const data = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const radius = 3.2 + Math.random() * 4.5;

      const theta =
        Math.random() * Math.PI * 2;

      const phi =
        Math.acos(2 * Math.random() - 1);

      data[i * 3] =
        radius *
        Math.sin(phi) *
        Math.cos(theta);

      data[i * 3 + 1] =
        radius * Math.cos(phi);

      data[i * 3 + 2] =
        radius *
        Math.sin(phi) *
        Math.sin(theta);
    }

    return data;
  }, []);

  useFrame((state) => {
    if (!pointsRef.current) return;

    const time = state.clock.elapsedTime;

    pointsRef.current.rotation.y =
      time * 0.015;

    pointsRef.current.rotation.x =
      Math.sin(time * 0.08) * 0.03;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>

      <pointsMaterial
        color="#9beaff"
        size={0.035}
        sizeAttenuation
        transparent
        opacity={0.48}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}