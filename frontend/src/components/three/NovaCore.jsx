import { Canvas, useFrame } from "@react-three/fiber";
import {
  Float,
  OrbitControls,
  Sphere,
} from "@react-three/drei";
import { useRef } from "react";

function IntelligenceCore() {
  const core = useRef(null);
  const outerRing = useRef(null);
  const middleRing = useRef(null);
  const innerRing = useRef(null);

  useFrame((_, delta) => {
    if (core.current) {
      core.current.rotation.x += delta * 0.18;
      core.current.rotation.y += delta * 0.24;
    }

    if (outerRing.current) {
      outerRing.current.rotation.x += delta * 0.12;
      outerRing.current.rotation.z -= delta * 0.1;
    }

    if (middleRing.current) {
      middleRing.current.rotation.y -= delta * 0.18;
      middleRing.current.rotation.z += delta * 0.08;
    }

    if (innerRing.current) {
      innerRing.current.rotation.x -= delta * 0.2;
      innerRing.current.rotation.y += delta * 0.14;
    }
  });

  return (
    <group>
      <ambientLight intensity={0.35} />

      <pointLight
        position={[0, 0, 1.5]}
        intensity={12}
        distance={7}
      />

      <pointLight
        position={[2, 1, 2]}
        intensity={4}
        distance={5}
      />

      <Sphere
        ref={core}
        args={[0.65, 40, 40]}
      >
        <meshStandardMaterial
          color="#e9f7ff"
          metalness={0.95}
          roughness={0.14}
          emissive="#51cfff"
          emissiveIntensity={0.8}
        />
      </Sphere>

      <mesh ref={innerRing}>
        <torusGeometry
          args={[0.93, 0.018, 16, 128]}
        />

        <meshStandardMaterial
          color="#8de4ff"
          emissive="#37c9ff"
          emissiveIntensity={2.2}
        />
      </mesh>

      <mesh
        ref={middleRing}
        rotation={[0.7, 0.2, 0.6]}
      >
        <torusGeometry
          args={[1.32, 0.013, 12, 128]}
        />

        <meshStandardMaterial
          color="#b9e9ff"
          emissive="#4db9ff"
          emissiveIntensity={1.8}
        />
      </mesh>

      <mesh
        ref={outerRing}
        rotation={[1.1, 0.4, 1]}
      >
        <torusGeometry
          args={[1.7, 0.009, 10, 128]}
        />

        <meshStandardMaterial
          color="#83d5ff"
          emissive="#168ad4"
          emissiveIntensity={1.4}
        />
      </mesh>

      <Float
        speed={1.7}
        rotationIntensity={0.4}
        floatIntensity={0.7}
      >
        <Sphere
          args={[0.055, 16, 16]}
          position={[1.55, 0.5, 0]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#62d7ff"
            emissiveIntensity={4}
          />
        </Sphere>
      </Float>

      <Float
        speed={1.3}
        rotationIntensity={0.5}
        floatIntensity={0.6}
      >
        <Sphere
          args={[0.06, 16, 16]}
          position={[-1.15, 0.8, 0.15]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#63baff"
            emissiveIntensity={4}
          />
        </Sphere>
      </Float>

      <Float
        speed={1.9}
        rotationIntensity={0.3}
        floatIntensity={0.8}
      >
        <Sphere
          args={[0.05, 16, 16]}
          position={[0.15, -1.5, 0.3]}
        >
          <meshStandardMaterial
            color="#ffffff"
            emissive="#56dfff"
            emissiveIntensity={4}
          />
        </Sphere>
      </Float>
    </group>
  );
}

export default function NovaCore() {
  return (
    <div className="nova-core-container">
      <Canvas
        camera={{
          position: [0, 0, 4.8],
          fov: 42,
        }}
        dpr={[1, 1.6]}
      >
        <IntelligenceCore />

        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.25}
          minPolarAngle={Math.PI / 2.45}
          maxPolarAngle={Math.PI / 1.8}
        />
      </Canvas>
    </div>
  );
}