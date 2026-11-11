import { useQuery, useQueryClient } from "@tanstack/react-query";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, setUnauthorized } from "./services/api";
import { tokenStorage as storage } from "./services/session";
import { AuthResponse, Portfolio, Summary, User } from "./types";

type Session = {
  user: User | null;
  ready: boolean;
  accept: (auth: AuthResponse) => Promise<void>;
  logout: () => Promise<void>;
};
const SessionContext = createContext<Session>(null!);

export function SessionProvider({ children }: React.PropsWithChildren) {
  const client = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const clear = useCallback(async () => {
    setUser(null);
    client.clear();
    await storage.clear();
  }, [client]);
  useEffect(() => {
    setUnauthorized(() => {
      void clear();
    });
    let active = true;
    void (async () => {
      try {
        const token = await storage.get();
        if (token) {
          const current = await api<User>("/auth/me");
          if (active) setUser(current);
        }
      } catch {
        await clear();
      } finally {
        if (active) setReady(true);
      }
    })();
    return () => {
      active = false;
      setUnauthorized(null);
    };
  }, [clear]);
  const accept = async (auth: AuthResponse) => {
    await storage.set(auth.access_token);
    client.clear();
    setUser(auth.user);
  };
  const logout = async () => {
    try {
      await api("/auth/logout", "POST");
    } finally {
      await clear();
    }
  };
  return (
    <SessionContext.Provider value={{ user, ready, accept, logout }}>
      {children}
    </SessionContext.Provider>
  );
}
export const useSession = () => useContext(SessionContext);

type PortfolioContextType = {
  portfolios: Portfolio[];
  selected: Portfolio | undefined;
  select: (id: string) => void;
  loading: boolean;
  error: Error | null;
};
const PortfolioContext = createContext<PortfolioContextType>(null!);
export function PortfolioProvider({ children }: React.PropsWithChildren) {
  const { user } = useSession();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["portfolios", user?.id],
    queryFn: () => api<Portfolio[]>("/portfolios"),
    enabled: !!user,
  });
  const portfolios = query.data;
  const selected =
    portfolios?.find((p) => p.id === selectedId) || portfolios?.[0];
  return (
    <PortfolioContext.Provider
      value={{
        portfolios: portfolios || [],
        selected,
        select: setSelectedId,
        loading: !!user && query.isPending,
        error: query.error,
      }}
    >
      {children}
    </PortfolioContext.Provider>
  );
}
export const usePortfolios = () => useContext(PortfolioContext);
export function useSummary(lookback = 252) {
  const { selected } = usePortfolios();
  return useQuery({
    queryKey: ["summary", selected?.id, lookback],
    queryFn: () =>
      api<Summary>(`/portfolios/${selected!.id}/summary?lookback=${lookback}`),
    enabled: !!selected,
  });
}
