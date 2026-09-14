import { Line, Sparkles } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const STATE_CONFIG = {
  idle: {
    pulseSpeed: 1.2,
    pulseAmount: 0.035,
    particleScale: 1,
    distortion: 0.018,
  },

  listening: {
    pulseSpeed: 1.8,
    pulseAmount: 0.055,
    particleScale: 1.15,
    distortion: 0.035,
  },

  thinking: {
    pulseSpeed: 2.6,
    pulseAmount: 0.075,
    particleScale: 1.3,
    distortion: 0.06,
  },

  speaking: {
    pulseSpeed: 3.4,
    pulseAmount: 0.11,
    particleScale: 1.45,
    distortion: 0.085,
  },
};

function createAvatarParticles(count = 1800) {
  const positions = new Float32Array(count * 3);
  const basePositions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const t = Math.random();

    let x = 0;
    let y = 0;
    let z = 0;

    /*
      HEAD
      --------------------------------------------------
      Dense spherical particle volume.
    */

    if (t < 0.24) {
      const angle = Math.random() * Math.PI * 2;
      const vertical = Math.random() * Math.PI;

      const radiusX =
        0.43 + Math.random() * 0.08;

      const radiusY =
        0.54 + Math.random() * 0.1;

      const radiusZ =
        0.42 + Math.random() * 0.08;

      x =
        Math.sin(vertical) *
        Math.cos(angle) *
        radiusX;

      y =
        1.7 +
        Math.cos(vertical) *
        radiusY;

      z =
        Math.sin(vertical) *
        Math.sin(angle) *
        radiusZ;
    }

    /*
      NECK + UPPER TORSO
      --------------------------------------------------
    */

    else if (t < 0.48) {
      const vertical =
        0.55 + Math.random() * 0.8;

      const width =
        0.43 -
        Math.abs(vertical - 0.9) * 0.11;

      x =
        (Math.random() * 2 - 1) *
        width;

      y =
        0.55 +
        vertical;

      z =
        (Math.random() * 2 - 1) *
        0.22;
    }

    /*
      SHOULDERS
      --------------------------------------------------
    */

    else if (t < 0.66) {
      const side =
        Math.random() > 0.5 ? 1 : -1;

      const shoulderRadius =
        0.28 + Math.random() * 0.28;

      const angle =
        Math.random() * Math.PI * 2;

      x =
        side *
        (0.48 +
          Math.cos(angle) *
            shoulderRadius);

      y =
        0.98 +
        Math.sin(angle) *
          shoulderRadius *
          0.55;

      z =
        Math.cos(angle) *
        shoulderRadius *
        0.5;
    }

    /*
      ARMS
      --------------------------------------------------
    */

    else if (t < 0.82) {
      const side =
        Math.random() > 0.5 ? 1 : -1;

      const armT = Math.random();

      x =
        side *
        (0.63 +
          armT * 0.42);

      y =
        0.9 -
        armT * 0.9 +
        Math.sin(
          armT * Math.PI
        ) *
          0.035;

      z =
        (Math.random() * 2 - 1) *
        0.15;
    }

    /*
      LOWER BODY / DISSOLUTION
      --------------------------------------------------
    */

    else {
      const side =
        Math.random() > 0.5 ? 1 : -1;

      x =
        side *
        (0.18 +
          Math.random() * 0.22);

      y =
        -0.15 -
        Math.random() * 1.0;

      z =
        (Math.random() * 2 - 1) *
        0.17;
    }

    /*
      Organic breakup.
    */

    const noise =
      0.025 +
      Math.random() * 0.04;

    x +=
      (Math.random() * 2 - 1) *
      noise;

    y +=
      (Math.random() * 2 - 1) *
      noise;

    z +=
      (Math.random() * 2 - 1) *
      noise;

    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;

    basePositions[i * 3] = x;
    basePositions[i * 3 + 1] = y;
    basePositions[i * 3 + 2] = z;

    sizes[i] =
      0.012 +
      Math.random() * 0.025;
  }

  return {
    positions,
    basePositions,
    sizes,
  };
}

function AvatarParticles({
  state,
  audioLevel,
}) {
  const pointsRef = useRef();

  const particleData = useMemo(
    () => createAvatarParticles(),
    []
  );

  const config =
    STATE_CONFIG[state] ||
    STATE_CONFIG.idle;

  useFrame((frameState) => {
    if (!pointsRef.current) return;

    const time =
      frameState.clock.elapsedTime;

    const positionAttribute =
      pointsRef.current.geometry
        .attributes.position;

    const positions =
      positionAttribute.array;

    const base =
      particleData.basePositions;

    const speakingEnergy =
      state === "speaking"
        ? Math.max(
            0.2,
            audioLevel || 0
          )
        : 0;

    for (
      let i = 0;
      i < positions.length;
      i += 3
    ) {
      const baseX = base[i];
      const baseY = base[i + 1];
      const baseZ = base[i + 2];

      const wave =
        Math.sin(
          time *
            config.pulseSpeed +
            baseY * 4.2 +
            i * 0.008
        ) *
        config.distortion;

      const breath =
        Math.sin(
          time * 1.1 +
            baseY * 2.2
        ) *
        config.pulseAmount *
        0.18;

      const voiceMotion =
        speakingEnergy *
        Math.sin(
          time * 9 +
            baseY * 5
        ) *
        0.035;

      positions[i] =
        baseX +
        wave +
        breath +
        voiceMotion;

      positions[i + 1] =
        baseY +
        Math.cos(
          time * 1.15 +
            baseX * 3
        ) *
          config.pulseAmount *
          0.35;

      positions[i + 2] =
        baseZ +
        Math.sin(
          time * 1.35 +
            baseX * 2.8
        ) *
          config.distortion *
          0.45;
    }

    positionAttribute.needsUpdate =
      true;

    pointsRef.current.rotation.y =
      Math.sin(time * 0.18) *
      0.035;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={
            particleData.positions.length /
            3
          }
          array={
            particleData.positions
          }
          itemSize={3}
        />
      </bufferGeometry>

      <pointsMaterial
        color="#d9f9ff"
        size={
          0.026 *
          config.particleScale
        }
        sizeAttenuation
        transparent
        opacity={
          state === "speaking"
            ? 0.92
            : 0.72
        }
        depthWrite={false}
        blending={
          THREE.AdditiveBlending
        }
      />
    </points>
  );
}

function EnergyCore({
  state,
  audioLevel,
}) {
  const coreRef = useRef();
  const glowRef = useRef();

  useFrame((frameState) => {
    if (
      !coreRef.current ||
      !glowRef.current
    ) {
      return;
    }

    const time =
      frameState.clock.elapsedTime;

    const energy =
      state === "speaking"
        ? Math.max(
            0.25,
            audioLevel || 0
          )
        : state === "thinking"
          ? 0.65
          : state === "listening"
            ? 0.4
            : 0.15;

    const pulse =
      1 +
      Math.sin(
        time *
          (state === "speaking"
            ? 8
            : 2.4)
      ) *
        (0.08 + energy * 0.08);

    coreRef.current.scale.setScalar(
      pulse
    );

    glowRef.current.scale.setScalar(
      1.2 +
        energy * 0.8 +
        Math.sin(time * 2) * 0.04
    );

    coreRef.current.rotation.z +=
      0.008;
  });

  return (
    <group position={[0, 0.72, 0.34]}>
      <mesh ref={glowRef}>
        <sphereGeometry
          args={[0.18, 24, 24]}
        />

        <meshBasicMaterial
          color="#4edcff"
          transparent
          opacity={
            state === "speaking"
              ? 0.1
              : 0.055
          }
          depthWrite={false}
          blending={
            THREE.AdditiveBlending
          }
        />
      </mesh>

      <mesh ref={coreRef}>
        <sphereGeometry
          args={[0.095, 24, 24]}
        />

        <meshBasicMaterial
          color="#f1fdff"
          transparent
          opacity={0.96}
          blending={
            THREE.AdditiveBlending
          }
        />
      </mesh>
    </group>
  );
}

function NeuralLines({ state }) {
  const lineGroupRef =
    useRef();

  useFrame((frameState) => {
    if (!lineGroupRef.current) {
      return;
    }

    const time =
      frameState.clock.elapsedTime;

    lineGroupRef.current.rotation.y =
      Math.sin(time * 0.22) *
      0.025;

    lineGroupRef.current.rotation.x =
      Math.sin(time * 0.16) *
      0.018;
  });

  const intensity =
    state === "speaking"
      ? 0.82
      : state === "thinking"
        ? 0.62
        : 0.35;

  return (
    <group ref={lineGroupRef}>
      <Line
        points={[
          [-0.42, 1.75, 0.04],
          [-0.16, 1.96, 0.12],
          [0.18, 1.9, 0.08],
          [0.4, 1.68, 0.02],
        ]}
        color="#bdf4ff"
        transparent
        opacity={intensity}
        lineWidth={0.7}
      />

      <Line
        points={[
          [-0.42, 1.15, 0.05],
          [-0.16, 1.32, 0.14],
          [0.15, 1.25, 0.08],
          [0.4, 1.08, 0.02],
        ]}
        color="#79dcf7"
        transparent
        opacity={
          intensity * 0.72
        }
        lineWidth={0.5}
      />

      <Line
        points={[
          [-0.67, 0.94, 0],
          [-0.38, 0.71, 0.12],
          [-0.08, 0.6, 0.03],
          [0.2, 0.72, 0.12],
          [0.68, 0.94, 0],
        ]}
        color="#6ddcff"
        transparent
        opacity={
          intensity * 0.55
        }
        lineWidth={0.5}
      />
    </group>
  );
}

function AvatarSilhouette({
  state,
  audioLevel,
}) {
  const groupRef = useRef();

  useFrame((frameState) => {
    if (!groupRef.current) {
      return;
    }

    const time =
      frameState.clock.elapsedTime;

    const pointerX =
      frameState.pointer.x;

    const pointerY =
      frameState.pointer.y;

    const targetRotationY =
      pointerX * 0.12;

    const targetRotationX =
      -pointerY * 0.045;

    groupRef.current.rotation.y =
      THREE.MathUtils.lerp(
        groupRef.current.rotation.y,
        targetRotationY,
        0.035
      );

    groupRef.current.rotation.x =
      THREE.MathUtils.lerp(
        groupRef.current.rotation.x,
        targetRotationX,
        0.035
      );

    const voiceEnergy =
      state === "speaking"
        ? Math.max(
            0.15,
            audioLevel || 0
          )
        : 0;

    groupRef.current.position.y =
      Math.sin(time * 0.75) *
        0.018 +
      voiceEnergy *
        Math.sin(time * 8) *
        0.012;
  });

  return (
    <group ref={groupRef}>
      <AvatarParticles
        state={state}
        audioLevel={audioLevel}
      />

      <EnergyCore
        state={state}
        audioLevel={audioLevel}
      />

      <NeuralLines state={state} />

      <Sparkles
        count={
          state === "speaking"
            ? 120
            : 70
        }
        scale={[
          2.8,
          4.3,
          2.4,
        ]}
        size={
          state === "speaking"
            ? 1.55
            : 1.1
        }
        speed={
          state === "thinking"
            ? 0.7
            : 0.25
        }
        color="#9eeaff"
        opacity={0.55}
      />
    </group>
  );
}

export default function NovaAvatar({
  state = "idle",
  audioLevel = 0,
}) {
  return (
    <AvatarSilhouette
      state={state}
      audioLevel={audioLevel}
    />
  );
}