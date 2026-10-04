"use client";

/** The mission-control 3D scene: agents as instanced glowing orbs laid out
 *  by a 3D force-directed layout of the interaction graph; the currently
 *  displayed round's interactions render as links; injected events ripple.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force-3d";
import type { AgentAction, InjectedEvent } from "@/lib/types";

export const FACTION_COLORS = ["#ffab00", "#2fe6ff", "#8f6bff", "#ff5470", "#2fd08c", "#f4f1de", "#ff8a3d", "#7dd3fc"];

interface AgentLite {
  id: string;
  name: string;
  archetype: string;
  faction: number;
  influence: number;
}

interface Props {
  agents: Record<string, AgentLite>;
  actionsByRound: Record<number, AgentAction[]>;
  displayRound: number;
  events: InjectedEvent[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  highlightText?: string;
}

type PosMap = Map<string, [number, number, number]>;

function layoutAgents(agents: AgentLite[], edges: { a: string; b: string; w: number }[]): PosMap {
  const out: PosMap = new Map();
  if (!agents.length) return out;
  const nodes = agents.map((a) => ({ id: a.id }));
  const links = edges
    .filter((e) => agents.some((a) => a.id === e.a) && agents.some((a) => a.id === e.b))
    .map((e) => ({ source: e.a, target: e.b, value: e.w }));
  const radius = Math.cbrt(Math.max(1, agents.length)) * 1.35;
  const sim = forceSimulation(nodes, 3)
    .force("charge", forceManyBody().strength(-radius * 0.55))
    .force("center", forceCenter(0, 0, 0).strength(0.25))
    .force("collide", forceCollide(0.32))
    .stop();
  if (links.length) {
    sim.force("link", forceLink(links).id((d: { id: string }) => d.id).distance(0.9).strength(0.4));
  }
  for (let i = 0; i < 110; i++) sim.tick();
  for (const n of nodes as unknown as { id: string; x: number; y: number; z: number }[]) {
    out.set(n.id, [n.x ?? 0, n.y ?? 0, n.z ?? 0]);
  }
  return out;
}

function AgentMeshes({ agents, positions, activeIds, hovered, selected, onHover, onSelect }: {
  agents: AgentLite[]; positions: PosMap; activeIds: Set<string>;
  hovered: string | null; selected: string | null;
  onHover: (id: string | null) => void; onSelect: (id: string | null) => void;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);

  useEffect(() => {
    if (!mesh.current) return;
    agents.forEach((a, i) => {
      const [x, y, z] = positions.get(a.id) ?? [0, 0, 0];
      const s = 0.6 + a.influence * 2.4;
      dummy.position.set(x, y, z);
      dummy.scale.setScalar(s * (a.id === selected || a.id === hovered ? 1.5 : 1));
      dummy.updateMatrix();
      mesh.current.setMatrixAt(i, dummy.matrix);
      const base = new THREE.Color(FACTION_COLORS[a.faction % FACTION_COLORS.length]);
      const dim = activeIds.size === 0 ? 1.0 : activeIds.has(a.id) ? 1.0 : 0.28;
      color.copy(base).multiplyScalar(dim);
      mesh.current.setColorAt(i, color);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  }, [agents, positions, activeIds, hovered, selected, dummy, color]);

  return (
    <instancedMesh
      key={agents.length}
      ref={mesh}
      args={[undefined, undefined, Math.max(1, agents.length)]}
      onPointerMove={(e) => {
        e.stopPropagation();
        const idx = e.instanceId ?? null;
        onHover(idx !== null && agents[idx] ? agents[idx].id : null);
      }}
      onPointerOut={() => onHover(null)}
      onClick={(e) => {
        e.stopPropagation();
        const idx = e.instanceId;
        if (idx !== undefined && agents[idx]) onSelect(agents[idx].id);
      }}
    >
      <icosahedronGeometry args={[0.11, 1]} />
      <meshStandardMaterial roughness={0.25} metalness={0.1} toneMapped={false} />
    </instancedMesh>
  );
}

function RoundLinks({ actions, positions }: { actions: AgentAction[]; positions: PosMap }) {
  const geometry = useMemo(() => {
    const verts: number[] = [];
    for (const a of actions) {
      const from = positions.get(a.agentId);
      const to = positions.get(a.targets[0] ?? "");
      if (!from || !to) continue;
      verts.push(from[0], from[1], from[2], to[0], to[1], to[2]);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    return g;
  }, [actions, positions]);
  if (geometry.getAttribute("position").count === 0) return null;
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#2fe6ff" transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} />
    </lineSegments>
  );
}

function Ripple({ trigger }: { trigger: number }) {
  const ref = useRef<THREE.Mesh>(null!);
  const start = useRef<number>(-1);
  const [armed, setArmed] = useState(0);
  useEffect(() => { if (trigger > 0) { start.current = -1; setArmed(trigger); } }, [trigger]);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    if (start.current < 0) start.current = clock.elapsedTime;
    const t = clock.elapsedTime - start.current;
    if (t > 2.2) { ref.current.visible = false; return; }
    ref.current.visible = true;
    ref.current.scale.setScalar(0.4 + t * 4.5);
    (ref.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 0.7 * (1 - t / 2.2));
    ref.current.rotation.z = clock.elapsedTime * 0.2;
  });
  return (
    <mesh ref={ref} visible={false} rotation={[Math.PI / 2.6, 0, 0]}>
      <ringGeometry args={[0.92, 1, 96]} />
      <meshBasicMaterial color="#ffab00" transparent opacity={0.7} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} />
    </mesh>
  );
}

export default function SwarmCanvas({ agents, actionsByRound, displayRound, events, selected, onSelect, highlightText }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);
  const agentList = useMemo(
    () => Object.values(agents).sort((a, b) => a.id.localeCompare(b.id)),
    [agents]
  );

  const layoutKey = useMemo(() => {
    let actions = 0;
    const rounds = Object.keys(actionsByRound).map(Number);
    for (const r of rounds) actions += (actionsByRound[r] || []).length;
    return `${agentList.length}:${actions}`;
  }, [agentList.length, actionsByRound]);

  const positions = useMemo(() => {
    const edges: { a: string; b: string; w: number }[] = [];
    const acc = new Map<string, number>();
    for (const acts of Object.values(actionsByRound)) {
      for (const act of acts) {
        if (!act.targets?.length) continue;
        const key = `${act.agentId}|${act.targets[0]}`;
        acc.set(key, (acc.get(key) ?? 0) + 1);
      }
    }
    for (const [key, w] of acc) {
      const [a, b] = key.split("|");
      edges.push({ a, b, w });
    }
    return layoutAgents(agentList, edges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutKey]);

  const displayActions = actionsByRound[displayRound] ?? [];
  const activeIds = useMemo(() => new Set(displayActions.map((a) => a.agentId)), [displayActions]);
  const hoverAgent = hovered ? agents[hovered] : null;
  const hoverPos = hovered ? positions.get(hovered) : null;

  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 6, 13], fov: 50 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onPointerMissed={() => onSelect(null)}
    >
      <color attach="background" args={["#05070f"]} />
      <fog attach="fog" args={["#05070f", 18, 34]} />
      <ambientLight intensity={0.7} />
      <pointLight position={[8, 10, 8]} intensity={140} color="#ffd9a0" />
      <pointLight position={[-10, -6, -6]} intensity={60} color="#2fe6ff" />
      <Stars radius={60} depth={40} count={1600} factor={3} saturation={0.4} fade speed={0.6} />

      <AgentMeshes
        agents={agentList}
        positions={positions}
        activeIds={activeIds}
        hovered={hovered}
        selected={selected}
        onHover={setHovered}
        onSelect={onSelect}
      />
      <RoundLinks actions={displayActions} positions={positions} />
      <Ripple trigger={events.length} />

      {hoverAgent && hoverPos && (
        <Html position={[hoverPos[0], hoverPos[1] + 0.5, hoverPos[2]]} center distanceFactor={12} className="pointer-events-none">
          <div className="glass-panel w-52 !p-3 text-xs">
            <div className="font-semibold text-foreground">{hoverAgent.name}</div>
            <div className="mono mt-0.5 text-[10px] uppercase tracking-wider text-muted-fg">
              {hoverAgent.archetype || "agent"} · faction {hoverAgent.faction}
            </div>
            <div className="mono mt-1 text-[10px] text-hive-cyan">influence {(hoverAgent.influence * 100).toFixed(0)}%</div>
          </div>
        </Html>
      )}

      {highlightText && displayRound > 0 && (
        <Html position={[0, 6, 0]} center className="pointer-events-none">
          <div className="mono rounded-full border border-border bg-surface/80 px-4 py-1.5 text-xs tracking-widest text-hive-amber backdrop-blur">
            ROUND {displayRound} · {highlightText}
          </div>
        </Html>
      )}

      <OrbitControls makeDefault enableDamping dampingFactor={0.08} autoRotate autoRotateSpeed={0.5} minDistance={4} maxDistance={30} />
    </Canvas>
  );
}
