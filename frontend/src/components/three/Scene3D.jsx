import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, PerspectiveCamera } from "@react-three/drei";
import { useEffect, useRef, useState } from "react";

import NovaAvatar from "./NovaAvatar";
import ParticleField from "./ParticleField";

function CameraController() {
  const { camera, pointer } = useThree();

  useFrame(() => {
    const targetX = pointer.x * 0.12;
    const targetY = 0.15 + pointer.y * 0.05;

    camera.position.x +=
      (targetX - camera.position.x) * 0.025;

    camera.position.y +=
      (targetY - camera.position.y) * 0.025;

    camera.lookAt(0, 0.55, 0);
  });

  return null;
}

function SceneRuntime() {
  const [avatarState, setAvatarState] = useState("idle");
  const [audioLevel, setAudioLevel] = useState(0);

  useEffect(() => {
    const handleAvatarState = (event) => {
      const nextState =
        event.detail?.state || "idle";

      const nextAudioLevel =
        typeof event.detail?.audioLevel === "number"
          ? event.detail.audioLevel
          : 0;

      setAvatarState(nextState);
      setAudioLevel(nextAudioLevel);
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
    <NovaAvatar
      state={avatarState}
      audioLevel={audioLevel}
    />
  );
}

function SceneSetup() {
  const { camera } = useThree();

  useEffect(() => {
    camera.lookAt(0, 0.55, 0);
  }, [camera]);

  return null;
}

export default function Scene3D() {
  return (
    <div className="nova-scene-3d">
      <Canvas
        dpr={[1, 1.75]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        }}
        camera={{
          position: [0, 0.15, 5.8],
          fov: 38,
          near: 0.1,
          far: 100,
        }}
      >
        <PerspectiveCamera
          makeDefault
          position={[0, 0.15, 5.8]}
          fov={38}
          near={0.1}
          far={100}
        />

        <SceneSetup />

        <CameraController />

        <ambientLight intensity={0.28} />

        <directionalLight
          position={[2, 4, 5]}
          intensity={1.8}
        />

        <pointLight
          position={[-2.5, 1.5, 3]}
          intensity={8}
          distance={8}
        />

        <pointLight
          position={[2.5, 0.5, 2]}
          intensity={5}
          distance={7}
        />

        <pointLight
          position={[0, 1, -2]}
          intensity={3}
          distance={6}
        />

        <SceneRuntime />

        <ParticleField />

        <Environment preset="night" />
      </Canvas>
    </div>
  );
}