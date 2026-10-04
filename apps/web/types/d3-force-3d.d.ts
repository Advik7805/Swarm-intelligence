// Ambient types for d3-force-3d (loose — engine is used internally only).
declare module "d3-force-3d" {
  export interface SimNode {
    id?: string | number;
    index?: number;
    x?: number; y?: number; z?: number;
    vx?: number; vy?: number; vz?: number;
    fx?: number | null; fy?: number | null; fz?: number | null;
    [k: string]: unknown;
  }
  export function forceSimulation(nodes?: SimNode[], ...rest: unknown[]): any;
  export function forceLink(links?: unknown[]): any;
  export function forceManyBody(...args: unknown[]): any;
  export function forceCenter(x?: number, y?: number, z?: number): any;
  export function forceCollide(radius?: number | ((node: SimNode) => number)): any;
  export function forceX(x?: number): any;
  export function forceY(y?: number): any;
  export function forceZ(z?: number): any;
}
