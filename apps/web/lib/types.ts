/** Shared client-side types matching the backend contracts. */

export type ActionKind = "post" | "reply" | "endorse" | "dispute";

export interface AgentAction {
  id: string;
  agentId: string;
  name: string;
  archetype?: string;
  faction: number;
  platform: string;
  action: ActionKind;
  sentiment: number; // -1..1
  text: string;
  targets: string[];
  influence: number; // 0..1
  round: number;
}

export interface MetricsEvent {
  round: number;
  sentimentAvg: number;
  activityCount: number;
  factionShares: Record<string, number>;
  topInfluencers: { id: string; name: string; faction: number; archetype?: string; score: number }[];
}

export interface InjectedEvent {
  tick: number;
  text: string;
}

export interface FactionUpdate {
  round: number;
  factions: Record<string, number>;
}

export interface WSEvent {
  seq?: number;
  type:
    | "round_started" | "round_batch" | "metrics" | "graph_update"
    | "event_injected" | "report_progress" | "run_complete" | "error" | "ping";
  runId?: string;
  round?: number;
  rounds?: number;
  actions?: AgentAction[];
  metrics?: MetricsEvent;
  factions?: Record<string, number>;
  tick?: number;
  text?: string;
  stage?: string;
  summary?: { rounds: number; totalActions: number; finalSentiment: number; factionCount: number; stopped: boolean };
  message?: string;
}

export interface Persona {
  id: string;
  name: string;
  archetype: string;
  bio: string;
  goals: string[];
  interests: string[];
  stance: number;
  openness: number;
  aggression: number;
  followers: number;
  platform: string;
  faction: number;
}

export interface Project {
  id: string;
  name: string;
  question: string;
  seedText?: string;
  status: "created" | "building" | "built" | "simulating" | "complete" | "failed";
  createdAt: number;
  agentCount: number;
  platformCount: number;
  currentRunId?: string | null;
  graphSummary?: { nodes: number; edges: number; communities: number };
  graph?: { nodes: { id: number; label: string; community: number; weight: number }[]; edges: { a: number; b: number; w: number }[] };
  personas?: Persona[];
}

export interface RunStatus {
  runId: string;
  projectId: string;
  status: "queued" | "running" | "paused" | "stopped" | "reporting" | "complete" | "failed";
  round: number;
  rounds: number;
  seq: number;
  mode: "demo" | "live";
  hasReport: boolean;
}

export interface Report {
  summary: string;
  overallPrediction: string;
  confidence: number;
  keyFindings: { claim: string; evidence: { round: number; agentId: string; agent?: string; quote: string }[]; confidence: number }[];
  scenarioBranches: { name: string; probability: number; trigger: string; outcome: string }[];
  injectableSuggestions: string[];
  topAgents: { id: string; name: string; archetype: string; faction: number; score: number }[];
  meta: { agents: number; rounds: number; actions: number; mode: string; generatedAt: number; finalSentiment: number; polarization: number };
}
