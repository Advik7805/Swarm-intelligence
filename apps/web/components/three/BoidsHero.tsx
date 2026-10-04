"use client";

/** Ambient 3D boid-style swarm background for the landing hero.
 *  CPU-animated point cloud through a sine flow field, amber/cyan palette,
 *  additive blending + fog. Degrades gracefully under reduced motion.
 */
import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

const N = 900;
const BOUNDS = { x: 10, y: 5.5, z: 5.5 };

function SwarmPoints() {
  const ref = useRef<THREE.Points>(null!);
  const mouse = useRef({ x: 0, y: 0 });

  const { positions, velocities, sizes } = useMemo(() => {
    const positions = new Float32Array(N * 3);
    const velocities = new Float32Array(N * 3);
    const sizes = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      positions[i * 3] = (Math.random() * 2 - 1) * BOUNDS.x;
      positions[i * 3 + 1] = (Math.random() * 2 - 1) * BOUNDS.y;
      positions[i * 3 + 2] = (Math.random() * 2 - 1) * BOUNDS.z;
      velocities[i * 3] = (Math.random() - 0.5) * 0.02;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.02;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;
      sizes[i] = 0.5 + Math.random();
    }
    return { positions, velocities, sizes };
  }, []);

  const colors = useMemo(() => {
    const amber = new THREE.Color("#ffab00");
    const cyan = new THREE.Color("#2fe6ff");
    const out = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const c = Math.random() < 0.62 ? amber : cyan;
      out[i * 3] = c.r; out[i * 3 + 1] = c.g; out[i * 3 + 2] = c.b;
    }
    return out;
  }, []);

  useFrame(({ clock, pointer }) => {
    const t = clock.elapsedTime;
    mouse.current.x = pointer.x * 0.6;
    mouse.current.y = pointer.y * 0.4;
    const pos = ref.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i < N; i++) {
      const ix = i * 3;
      const x = pos[ix], y = pos[ix + 1], z = pos[ix + 2];
      velocities[ix] += Math.sin(y * 0.6 + t * 0.35) * 0.00045;
      velocities[ix + 1] += Math.cos(x * 0.5 + t * 0.28) * 0.00045;
      velocities[ix + 2] += Math.sin((x + y) * 0.4 + t * 0.22) * 0.0004;
      // gentle mouse parallax pull
      velocities[ix] += mouse.current.x * 0.00018;
      velocities[ix + 1] += mouse.current.y * 0.00018;
      const sp = Math.hypot(velocities[ix], velocities[ix + 1], velocities[ix + 2]) || 1;
      const cap = 0.028;
      if (sp > cap) {
        velocities[ix] *= cap / sp; velocities[ix + 1] *= cap / sp; velocities[ix + 2] *= cap / sp;
      }
      let nx = x + velocities[ix], ny = y + velocities[ix + 1], nz = z + velocities[ix + 2];
      if (Math.abs(nx) > BOUNDS.x) nx = -Math.sign(nx) * BOUNDS.x;
      if (Math.abs(ny) > BOUNDS.y) ny = -Math.sign(ny) * BOUNDS.y;
      if (Math.abs(nz) > BOUNDS.z) nz = -Math.sign(nz) * BOUNDS.z;
      pos[ix] = nx; pos[ix + 1] = ny; pos[ix + 2] = nz;
    }
    ref.current.geometry.attributes.position.needsUpdate = true;
    ref.current.rotation.y = t * 0.02;
  });

  return (
    <points ref={ref} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.045}
        vertexColors
        transparent
        opacity={0.85}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

export default function BoidsHero() {
  const reduced =
    typeof window !== "undefined" &&
    (window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      (navigator.hardwareConcurrency ?? 8) < 4);
  if (reduced) {
    return <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(38_100%_55%/0.10),transparent_60%)]" />;
  }
  return (
    <div className="absolute inset-0" aria-hidden>
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [0, 0, 9], fov: 55 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <fog attach="fog" args={[new THREE.Color("#04060d"), 9, 18]} />
        <SwarmPoints />
      </Canvas>
    </div>
  );
}
