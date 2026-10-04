/** REST client. Defaults to same-origin /api (proxied by Next rewrites).
 *  In sandboxed previews where each port is its own host, falls back to
 *  swapping the port prefix (3000-… → 8000-…) if the proxy is unreachable.
 */
const EXPLICIT = process.env.NEXT_PUBLIC_API_BASE;

function fallbackOrigin(): string | null {
  if (typeof window === "undefined") return null;
  const m = window.location.hostname.match(/^\d+-(.+)$/);
  if (!m) return null;
  return `${window.location.protocol}//8000-${m[1]}`;
}

async function doFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const bases = [EXPLICIT || "/api"];
  const fb = fallbackOrigin();
  if (!EXPLICIT && fb) bases.push(`${fb}/api`);

  let lastErr: unknown = null;
  for (const base of bases) {
    try {
      const res = await fetch(`${base}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : data?.detail?.error;
        throw new Error(detail || `HTTP ${res.status}`);
      }
      return data as T;
    } catch (e) {
      lastErr = e;
      if (e instanceof Error && !e.message.startsWith("HTTP") && !e.message.includes("[")) continue;
      throw e; // server answered with a typed error — don't retry on fallback
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("network error");
}

export function apiFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  return doFetch<T>(path, init);
}

export function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  return doFetch<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
}

export function fileToPayload(file: File): Promise<{ name: string; contentBase64: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`failed reading ${file.name}`));
    reader.onload = () => {
      const url = String(reader.result);
      resolve({ name: file.name, contentBase64: url.slice(url.indexOf(",") + 1) });
    };
    reader.readAsDataURL(file);
  });
}
