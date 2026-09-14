import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Float,
  OrbitControls,
  Sphere,
} from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";

const STATE_CONFIG = {
  idle: {
    corePulse: 0.035,
    ringSpeed: 0.6,
    particleSpeed: 0.2,
    glow: 0.8,
  },

  thinking: {
    corePulse: 0.07,
    ringSpeed: 1.2,
    particleSpeed: 0.55,
    glow: 1.35,
  },

  speaking: {
    corePulse: 0.11,
    ringSpeed: 1.55,
    particleSpeed: 0.8,
    glow: 1.8,
  },
};

function OrbParticles({ state }) {
  const pointsRef = useRef(null);

  const config =
    STATE_CONFIG[state] ||
    STATE_CONFIG.idle;

  const positions = useMemo(() => {
    const count = 320;
    const data = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const radius =
        1.15 + Math.random() * 1.5;

      const theta =
        Math.random() * Math.PI * 2;

      const phi =
        Math.acos(
          2 * Math.random() - 1
        );

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

  useFrame((frameState) => {
    if (!pointsRef.current) {
      return;
    }

    const time =
      frameState.clock.elapsedTime;

    pointsRef.current.rotation.y =
      time * config.particleSpeed * 0.18;

    pointsRef.current.rotation.x =
      Math.sin(time * 0.25) * 0.025;
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
        color="#9eeaff"
        size={
          state === "speaking"
            ? 0.033
            : state === "thinking"
              ? 0.028
              : 0.023
        }
        sizeAttenuation
        transparent
        opacity={
          state === "speaking"
            ? 0.62
            : 0.42
        }
        depthWrite={false}
      />
    </points>
  );
}

function IntelligenceCore({
  state,
  audioLevel,
}) {
  const core = useRef(null);
  const outerRing = useRef(null);
  const middleRing = useRef(null);
  const innerRing = useRef(null);
  const glow = useRef(null);

  const { pointer } = useThree();

  const config =
    STATE_CONFIG[state] ||
    STATE_CONFIG.idle;

  useFrame((_, delta) => {
    if (!core.current) {
      return;
    }

    const time =
      performance.now() * 0.001;

    const voiceEnergy =
      state === "speaking"
        ? Math.max(
            0.15,
            audioLevel || 0
          )
        : 0;

    const pulse =
      1 +
      Math.sin(
        time *
          (state === "speaking"
            ? 7
            : 2.2)
      ) *
        (config.corePulse +
          voiceEnergy * 0.05);

    core.current.scale.setScalar(
      pulse
    );

    core.current.rotation.x +=
      delta * 0.12;

    core.current.rotation.y +=
      delta * 0.22;

    if (innerRing.current) {
      innerRing.current.rotation.x +=
        delta * config.ringSpeed * 0.42;

      innerRing.current.rotation.y +=
        delta * config.ringSpeed * 0.65;
    }

    if (middleRing.current) {
      middleRing.current.rotation.y -=
        delta * config.ringSpeed * 0.34;

      middleRing.current.rotation.z +=
        delta * config.ringSpeed * 0.2;
    }

    if (outerRing.current) {
      outerRing.current.rotation.x +=
        delta * config.ringSpeed * 0.2;

      outerRing.current.rotation.z -=
        delta * config.ringSpeed * 0.3;
    }

    if (glow.current) {
      glow.current.scale.setScalar(
        1.05 +
          config.glow * 0.12 +
          voiceEnergy * 0.25 +
          Math.sin(time * 1.8) *
            0.025
      );
    }

    const targetX =
      pointer.x * 0.16;

    const targetY =
      pointer.y * 0.09;

    core.current.position.x +=
      (targetX -
        core.current.position.x) *
      0.035;

    core.current.position.y +=
      (targetY -
        core.current.position.y) *
      0.035;
  });

  return (
    <group>
      {/* atmospheric glow */}
      <Sphere
        ref={glow}
        args={[0.72, 32, 32]}
      >
        <meshBasicMaterial
          color="#4edcff"
          transparent
          opacity={
            state === "speaking"
              ? 0.075
              : 0.045
          }
          depthWrite={false}
        />
      </Sphere>

      {/* central intelligence core */}
      <Sphere
        ref={core}
        args={[0.65, 40, 40]}
      >
        <meshStandardMaterial
          color="#eefaff"
          metalness={0.92}
          roughness={0.12}
          emissive="#51cfff"
          emissiveIntensity={
            0.65 +
            config.glow * 0.25 +
            (state === "speaking"
              ? 0.5
              : 0)
          }
        />
      </Sphere>

      {/* inner energy ring */}
      <mesh ref={innerRing}>
        <torusGeometry
          args={[
            0.92,
            0.018,
            16,
            128,
          ]}
        />

        <meshStandardMaterial
          color="#b9efff"
          emissive="#37c9ff"
          emissiveIntensity={
            state === "speaking"
              ? 3
              : 2
          }
        />
      </mesh>

      {/* middle energy ring */}
      <mesh
        ref={middleRing}
        rotation={[
          0.7,
          0.2,
          0.6,
        ]}
      >
        <torusGeometry
          args={[
            1.3,
            0.014,
            12,
            128,
          ]}
        />

        <meshStandardMaterial
          color="#c5edff"
          emissive="#4db9ff"
          emissiveIntensity={
            state === "thinking"
              ? 2.4
              : 1.8
          }
        />
      </mesh>

      {/* outer orbital ring */}
      <mesh
        ref={outerRing}
        rotation={[
          1.1,
          0.4,
          1,
        ]}
      >
        <torusGeometry
          args={[
            1.68,
            0.009,
            10,
            128,
          ]}
        />

        <meshStandardMaterial
          color="#88ddff"
          emissive="#168ad4"
          emissiveIntensity={
            state === "speaking"
              ? 2
              : 1.4
          }
        />
      </mesh>
    </group>
  );
}

function FloatingNodes({
  state,
}) {
  const config =
    STATE_CONFIG[state] ||
    STATE_CONFIG.idle;

  return (
    <>
      <Float
        speed={
          1.15 +
          config.particleSpeed
        }
        rotationIntensity={0.45}
        floatIntensity={0.65}
      >
        <Sphere
          args={[0.055, 16, 16]}
          position={[
            1.55,
            0.5,
            0,
          ]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#62d7ff"
            emissiveIntensity={
              3.5 * config.glow
            }
          />
        </Sphere>
      </Float>

      <Float
        speed={
          1.05 +
          config.particleSpeed
        }
        rotationIntensity={0.5}
        floatIntensity={0.7}
      >
        <Sphere
          args={[0.06, 16, 16]}
          position={[
            -1.18,
            0.8,
            0.15,
          ]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#63baff"
            emissiveIntensity={
              3.5 * config.glow
            }
          />
        </Sphere>
      </Float>

      <Float
        speed={
          1.45 +
          config.particleSpeed
        }
        rotationIntensity={0.3}
        floatIntensity={0.8}
      >
        <Sphere
          args={[0.05, 16, 16]}
          position={[
            0.15,
            -1.5,
            0.3,
          ]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#56dfff"
            emissiveIntensity={
              3.5 * config.glow
            }
          />
        </Sphere>
      </Float>
    </>
  );
}

function OrbRuntime() {
  const [state, setState] =
    useState("idle");

  const [audioLevel, setAudioLevel] =
    useState(0);

  useEffect(() => {
    const handleAvatarState =
      (event) => {
        setState(
          event.detail?.state ||
            "idle"
        );

        setAudioLevel(
          typeof event.detail
            ?.audioLevel ===
            "number"
            ? event.detail
                .audioLevel
            : 0
        );
      };

    window.addEventListener(
      "nova:avatar-state",
      handleAvatarState
    );

    return () => {
      window.removeEventListener(
        "nova:avatar-state",
        handleAvatarState
      );
    };
  }, []);

  return (
    <>
      <IntelligenceCore
        state={state}
        audioLevel={audioLevel}
      />

      <OrbParticles
        state={state}
      />

      <FloatingNodes
        state={state}
      />
    </>
  );
}

export default function NovaCore() {
  return (
    <div className="nova-core-container">
      <Canvas
        camera={{
          position: [
            0,
            0,
            4.8,
          ],
          fov: 42,
          near: 0.1,
          far: 100,
        }}
        dpr={[1, 1.6]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference:
            "high-performance",
        }}
      >
        <ambientLight
          intensity={0.35}
        />

        <pointLight
          position={[
            0,
            0,
            1.5,
          ]}
          intensity={12}
          distance={7}
        />

        <pointLight
          position={[
            2,
            1,
            2,
          ]}
          intensity={4}
          distance={5}
        />

        <pointLight
          position={[
            -2,
            -1,
            1,
          ]}
          intensity={2}
          distance={4}
        />

        <OrbRuntime />

        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.18}
          minPolarAngle={
            Math.PI / 2.45
          }
          maxPolarAngle={
            Math.PI / 1.8
          }
        />
      </Canvas>
    </div>
  );
}