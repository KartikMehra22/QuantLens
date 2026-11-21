import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { usePortfolios } from "../providers";
import { api } from "../services/api";
import { colors, money, pct, s } from "../theme";
import { Metrics } from "../types";
import { Badge, Button, ErrorBox, Sheet } from "./ui";

type Comparison = {
  portfolios: {
    portfolio_id: string;
    name: string;
    data_mode: string;
    as_of: string;
    value: number;
    pnl_pct: number;
    metrics: Metrics | null;
    period_start: string;
    period_end: string;
  }[];
  assumption: string;
};
export function ComparePortfolios() {
  const { portfolios } = usePortfolios();
  const [open, setOpen] = useState(false);
  const [ids, setIds] = useState<string[] | null>(null);
  const selected = ids || portfolios.slice(0, 2).map((p) => p.id);
  const comparison = useMutation({
    mutationFn: () =>
      api<Comparison>(
        `/portfolio-comparison?${selected.map((id) => `ids=${encodeURIComponent(id)}`).join("&")}`,
      ),
  });
  return (
    <>
      <Button
        title="Compare portfolios"
        secondary
        disabled={portfolios.length < 2}
        onPress={() => {
          setOpen(true);
          setIds(null);
          comparison.reset();
        }}
      />
      {portfolios.length < 2 && (
        <Text style={s.small}>
          Create a second portfolio to compare valuations and risk.
        </Text>
      )}
      <Sheet
        title="Compare your portfolios"
        visible={open}
        close={() => setOpen(false)}
      >
        <Text style={s.small}>
          Select two to five portfolios. Each card shows its own data source and
          available period.
        </Text>
        {portfolios.map((p) => (
          <Pressable
            accessibilityRole="checkbox"
            accessibilityState={{ checked: selected.includes(p.id) }}
            key={p.id}
            onPress={() => {
              setIds(
                selected.includes(p.id)
                  ? selected.filter((id) => id !== p.id)
                  : [...selected, p.id].slice(0, 5),
              );
              comparison.reset();
            }}
            style={[
              s.between,
              {
                padding: 14,
                borderRadius: 10,
                backgroundColor: selected.includes(p.id)
                  ? colors.greenDark
                  : colors.bg,
              },
            ]}
          >
            <Text style={s.body}>{p.name}</Text>
            <Badge
              text={
                selected.includes(p.id) ? "SELECTED" : p.data_mode.toUpperCase()
              }
            />
          </Pressable>
        ))}
        <Button
          title="Compare selected portfolios"
          busy={comparison.isPending}
          disabled={selected.length < 2}
          onPress={() => comparison.mutate()}
        />
        <ErrorBox error={comparison.error} />
        {comparison.data?.portfolios.map((p) => (
          <View key={p.portfolio_id} style={s.card}>
            <Text style={{ color: colors.text, fontSize: 18 }}>{p.name}</Text>
            <Badge text={p.data_mode.toUpperCase()} color={colors.muted} />
            <Text style={{ color: colors.text, fontSize: 27 }}>
              {money(p.value)}
            </Text>
            <View style={s.between}>
              <Text style={s.small}>Unrealized return</Text>
              <Text style={s.body}>{pct(p.pnl_pct)}</Text>
            </View>
            <View style={s.between}>
              <Text style={s.small}>Annual volatility</Text>
              <Text style={s.body}>
                {pct(p.metrics?.annualized_volatility)}
              </Text>
            </View>
            <View style={s.between}>
              <Text style={s.small}>Sharpe ratio</Text>
              <Text style={s.body}>
                {p.metrics?.sharpe_ratio?.toFixed(2) || "—"}
              </Text>
            </View>
            <Text style={s.small}>
              {p.period_start || "No history"} to {p.period_end || "No prices"}
            </Text>
          </View>
        ))}
        {comparison.data && (
          <Text style={s.small}>{comparison.data.assumption}</Text>
        )}
      </Sheet>
    </>
  );
}
