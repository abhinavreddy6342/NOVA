import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";

function Head() {
  const meshRef = useRef();

  useFrame((state) => {
    if (!meshRef.current) return;

    const time = state.clock.elapsedTime;

    meshRef.current.rotation.y =
      Math.sin(time * 0.35) * 0.08;

    meshRef.current.position.x =
      Math.sin(time * 0.45) * 0.025;
  });

  return (
    <mesh ref={meshRef} position={[0, 1.55, 0]}>
      <sphereGeometry args={[0.38, 32, 32]} />

      <meshStandardMaterial
        color="#b9f3ff"
        emissive="#36cfff"
        emissiveIntensity={1.6}
        transparent
        opacity={0.72}
        roughness={0.2}
        metalness={0.7}
      />
    </mesh>
  );
}

function Body() {
  const materialProps = {
    color: "#7ddff8",
    emissive: "#159ed0",
    emissiveIntensity: 1.05,
    transparent: true,
    opacity: 0.52,
    roughness: 0.3,
    metalness: 0.65,
  };

  return (
    <group>
      {/* torso */}
      <mesh position={[0, 0.45, 0]}>
        <capsuleGeometry args={[0.55, 1.15, 10, 24]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* neck */}
      <mesh position={[0, 1.12, 0]}>
        <cylinderGeometry args={[0.17, 0.2, 0.3, 20]} />

        <meshStandardMaterial
          color="#b9f3ff"
          emissive="#36cfff"
          emissiveIntensity={1.3}
          transparent
          opacity={0.68}
          roughness={0.25}
          metalness={0.7}
        />
      </mesh>

      {/* left shoulder */}
      <mesh position={[-0.58, 0.78, 0]}>
        <sphereGeometry args={[0.23, 24, 24]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* right shoulder */}
      <mesh position={[0.58, 0.78, 0]}>
        <sphereGeometry args={[0.23, 24, 24]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* left arm */}
      <mesh
        position={[-0.82, 0.22, 0]}
        rotation={[0, 0, -0.16]}
      >
        <capsuleGeometry args={[0.13, 0.9, 8, 18]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* right arm */}
      <mesh
        position={[0.82, 0.22, 0]}
        rotation={[0, 0, 0.16]}
      >
        <capsuleGeometry args={[0.13, 0.9, 8, 18]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* left leg */}
      <mesh position={[-0.28, -0.8, 0]}>
        <capsuleGeometry args={[0.17, 1.45, 8, 20]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>

      {/* right leg */}
      <mesh position={[0.28, -0.8, 0]}>
        <capsuleGeometry args={[0.17, 1.45, 8, 20]} />

        <meshStandardMaterial {...materialProps} />
      </mesh>
    </group>
  );
}

function EnergyCore() {
  const coreRef = useRef();

  useFrame((state) => {
    if (!coreRef.current) return;

    const time = state.clock.elapsedTime;

    const pulse =
      1 + Math.sin(time * 2.5) * 0.08;

    coreRef.current.scale.setScalar(pulse);

    coreRef.current.rotation.z += 0.008;
  });

  return (
    <mesh ref={coreRef} position={[0, 0.45, 0.48]}>
      <sphereGeometry args={[0.18, 24, 24]} />

      <meshStandardMaterial
        color="#e8fbff"
        emissive="#4edcff"
        emissiveIntensity={4}
        transparent
        opacity={0.95}
      />
    </mesh>
  );
}

function SilhouetteParticles() {
  const groupRef = useRef();

  const particles = useMemo(() => {
    return Array.from({ length: 90 }, (_, index) => {
      const angle = Math.random() * Math.PI * 2;
      const radius = 0.8 + Math.random() * 0.9;
      const height = -1.8 + Math.random() * 3.5;

      return {
        key: index,

        position: [
          Math.cos(angle) * radius,
          height,
          Math.sin(angle) * radius * 0.5,
        ],

        scale: 0.008 + Math.random() * 0.018,
      };
    });
  }, []);

  useFrame((state) => {
    if (!groupRef.current) return;

    groupRef.current.rotation.y =
      state.clock.elapsedTime * 0.04;
  });

  return (
    <group ref={groupRef}>
      {particles.map((particle) => (
        <mesh
          key={particle.key}
          position={particle.position}
          scale={particle.scale}
        >
          <sphereGeometry args={[1, 6, 6]} />

          <meshBasicMaterial
            color="#8eeaff"
            transparent
            opacity={0.6}
          />
        </mesh>
      ))}
    </group>
  );
}

export default function HumanSilhouette() {
  const groupRef = useRef();

  useFrame((state) => {
    if (!groupRef.current) return;

    const time = state.clock.elapsedTime;

    groupRef.current.position.y =
      Math.sin(time * 0.7) * 0.035;

    groupRef.current.rotation.y =
      Math.sin(time * 0.3) * 0.04;
  });

  return (
    <group ref={groupRef}>
      <Head />

      <Body />

      <EnergyCore />

      <SilhouetteParticles />

      <pointLight
        position={[0, 0.5, 1]}
        intensity={4}
        distance={4}
      />
    </group>
  );
}