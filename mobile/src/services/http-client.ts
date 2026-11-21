export type Credentials = {
  access_token: string;
  refresh_token?: string;
  user_id?: string;
};
type Dependencies = {
  read: () => Promise<Credentials | null>;
  save: (value: Credentials) => Promise<void>;
  clear: () => Promise<void>;
  currentServer: () => Promise<string | null>;
  expired: () => void;
};

export function createAuthorizedRequester(dependencies: Dependencies) {
  const pending = new Map<string, Promise<void>>();
  async function renew(baseUrl: string, credentials: Credentials) {
    const current = await dependencies.read();
    if (
      (await dependencies.currentServer()) !== baseUrl ||
      !current ||
      current.user_id !== credentials.user_id
    ) {
      throw new Error("Account or server changed.");
    }
    if (current.access_token !== credentials.access_token) return;
    const key = `${baseUrl}:${credentials.refresh_token}`;
    if (!pending.has(key)) {
      const renewal = (async () => {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 12000);
        try {
          const response = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: credentials.refresh_token }),
            signal: controller.signal,
          });
          if (!response.ok) throw new Error("Session renewal failed.");
          const value = await response.json();
          if (
            typeof value.access_token !== "string" ||
            typeof value.refresh_token !== "string"
          )
            throw new Error("Invalid renewal response.");
          const latest = await dependencies.read();
          if (
            (await dependencies.currentServer()) !== baseUrl ||
            !latest ||
            latest.refresh_token !== credentials.refresh_token ||
            latest.user_id !== credentials.user_id
          ) {
            throw new Error("Account or server changed during renewal.");
          }
          await dependencies.save({
            access_token: value.access_token,
            refresh_token: value.refresh_token,
            user_id: credentials.user_id,
          });
        } finally {
          clearTimeout(timer);
        }
      })().finally(() => {
        pending.delete(key);
      });
      pending.set(key, renewal);
    }
    return pending.get(key);
  }

  return async function authorizedRequest(
    baseUrl: string,
    path: string,
    options: RequestInit = {},
  ) {
    const credentials = await dependencies.read();
    const send = (access?: string) => {
      const headers = new Headers(options.headers);
      if (options.body && !headers.has("Content-Type"))
        headers.set("Content-Type", "application/json");
      if (access) headers.set("Authorization", `Bearer ${access}`);
      return fetch(`${baseUrl}${path}`, { ...options, headers });
    };
    let response = await send(credentials?.access_token);
    const renewAllowed =
      !path.startsWith("/api/v1/auth/") ||
      ["/api/v1/auth/me", "/api/v1/auth/logout"].includes(path);
    if (response.status === 401 && credentials && renewAllowed) {
      try {
        if (!credentials.refresh_token)
          throw new Error("No renewable session.");
        await renew(baseUrl, credentials);
        const latest = await dependencies.read();
        if (
          (await dependencies.currentServer()) !== baseUrl ||
          latest?.user_id !== credentials.user_id
        )
          throw new Error("Account or server changed.");
        response = await send(latest?.access_token);
      } catch {
        const latest = await dependencies.read();
        if (
          latest?.access_token === credentials.access_token &&
          (await dependencies.currentServer()) === baseUrl
        ) {
          await dependencies.clear();
          dependencies.expired();
        }
      }
    }
    return response;
  };
}
