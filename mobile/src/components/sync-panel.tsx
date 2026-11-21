import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Switch, Text, View } from "react-native";
import { api } from "../services/api";
import { colors, s } from "../theme";
import { Portfolio } from "../types";
import { Badge, ErrorBox, SectionTitle } from "./ui";

type Sync = {
  id: string;
  status: string;
  created_at: string;
  instruments: number;
  message: string;
};
export function SyncPanel({ portfolio }: { portfolio: Portfolio }) {
  const client = useQueryClient();
  const history = useQuery({
    queryKey: ["sync-history", portfolio.id],
    queryFn: () => api<Sync[]>(`/portfolios/${portfolio.id}/sync-history`),
  });
  const change = useMutation({
    mutationFn: (auto_sync: boolean) =>
      api(`/portfolios/${portfolio.id}/settings`, "PATCH", { auto_sync }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["portfolios"] });
    },
  });
  return (
    <View style={s.card}>
      <SectionTitle
        title="Historical data refresh"
        caption="Runs once per day while the backend is running"
      />
      <View style={s.between}>
        <Text style={s.body}>Automatic daily refresh</Text>
        <Switch
          accessibilityLabel="Automatic daily refresh"
          value={!!portfolio.auto_sync}
          onValueChange={(value) => change.mutate(value)}
          disabled={change.isPending || portfolio.data_mode !== "yahoo"}
          trackColor={{ true: colors.greenDark, false: colors.bg }}
          thumbColor={portfolio.auto_sync ? colors.green : colors.muted}
        />
      </View>
      {portfolio.data_mode !== "yahoo" && (
        <Text style={s.small}>
          Download historical market data to enable automatic refresh.
        </Text>
      )}
      <ErrorBox error={change.error || history.error} />
      {history.data?.slice(0, 5).map((run) => (
        <View key={run.id} style={{ gap: 6, paddingVertical: 8 }}>
          <View style={s.between}>
            <Badge
              text={run.status.toUpperCase()}
              color={run.status === "failed" ? colors.red : colors.green}
            />
            <Text style={s.small}>{run.instruments} holdings</Text>
          </View>
          <Text style={s.small}>{run.message}</Text>
          <Text style={s.small}>
            {new Date(
              run.created_at.endsWith("Z") || run.created_at.includes("+")
                ? run.created_at
                : `${run.created_at}Z`,
            ).toLocaleString("en-IN")}
          </Text>
        </View>
      ))}
      {!history.data?.length && (
        <Text style={s.small}>
          Refresh history will appear after downloading historical prices.
        </Text>
      )}
    </View>
  );
}
