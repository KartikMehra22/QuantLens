import { router } from "expo-router";
import {
  ArrowRight,
  ArrowUpRight,
  FlaskConical,
  ShieldCheck,
} from "lucide-react-native";
import { useState } from "react";
import { Pressable, Text, View, useWindowDimensions } from "react-native";
import { AllocationDonut, LineChart } from "../../components/charts";
import {
  Badge,
  Change,
  Empty,
  ErrorBox,
  Loading,
  Screen,
  SectionTitle,
} from "../../components/ui";
import { usePortfolios, useSession, useSummary } from "../../providers";
import { colors, money, pct, s, shortDate } from "../../theme";

export default function Overview() {
  const [period, setPeriod] = useState(252);
  const { user } = useSession();
  const { selected, loading, error } = usePortfolios();
  const query = useSummary(period);
  const data = query.data;
  const wide = useWindowDimensions().width >= 800;
  return (
    <Screen
      title={`Your portfolio, in focus.`}
      description={`Welcome back, ${user?.name.split(" ")[0]}. Here's the bigger picture.`}
      refreshing={query.isRefetching}
      onRefresh={() => void query.refetch()}
    >
      {loading || (selected && query.isPending) ? (
        <Loading />
      ) : error || query.error ? (
        <ErrorBox error={error || query.error} />
      ) : !data?.holdings.length ? (
        <Empty
          title="Start with what you hold"
          description="Choose or create a portfolio above, then add your first equity to explore its performance and risk."
          action={() => router.push("/holdings")}
        />
      ) : (
        <>
          <View
            style={[
              s.card,
              {
                backgroundColor: "#1D3026",
                borderColor: "#354B35",
                padding: 24,
                gap: 20,
              },
            ]}
          >
            <View style={s.between}>
              <Text style={s.label}>TOTAL PORTFOLIO VALUE</Text>
              <Badge
                text={
                  data.data_mode === "synthetic"
                    ? "SYNTHETIC DEMO"
                    : "HISTORICAL CLOSE"
                }
              />
            </View>
            <View style={{ gap: 10 }}>
              <Text
                adjustsFontSizeToFit
                numberOfLines={1}
                style={{
                  color: colors.text,
                  fontSize: 45,
                  fontWeight: "500",
                  letterSpacing: -2,
                }}
              >
                {money(data.value, 2)}
              </Text>
              <View style={s.row}>
                <Change value={data.pnl_pct} />
                <Text style={s.small}>unrealized return</Text>
              </View>
            </View>
            <View
              style={[
                s.between,
                {
                  paddingTop: 18,
                  borderTopWidth: 1,
                  borderTopColor: "#3A4C3A",
                },
              ]}
            >
              <View style={{ gap: 6 }}>
                <Text style={s.small}>Invested amount</Text>
                <Text style={{ color: colors.text, fontSize: 18 }}>
                  {money(data.invested)}
                </Text>
              </View>
              <View style={{ gap: 6, alignItems: "flex-end" }}>
                <Text style={s.small}>Unrealized P&L</Text>
                <Text
                  style={{
                    color: data.pnl >= 0 ? colors.green : colors.red,
                    fontSize: 18,
                  }}
                >
                  {data.pnl >= 0 ? "+" : "−"}
                  {money(Math.abs(data.pnl))}
                </Text>
              </View>
            </View>
            <Text style={s.small}>Price date · {shortDate(data.as_of)}</Text>
          </View>
          <View style={{ flexDirection: wide ? "row" : "column", gap: 18 }}>
            <View style={[s.card, { flex: wide ? 1.6 : undefined }]}>
              <View style={s.between}>
                <SectionTitle
                  title="The historical picture"
                  caption="Hypothetical growth of ₹100"
                />
                <ArrowUpRight size={20} color={colors.green} />
              </View>
              <Text
                style={{ color: colors.text, fontSize: 30, letterSpacing: -1 }}
              >
                {pct(data.metrics?.cumulative_return, true)}
              </Text>
              <View style={[s.row, { gap: 6 }]}>
                {[
                  [21, "1M"],
                  [63, "3M"],
                  [126, "6M"],
                  [252, "1Y"],
                  [756, "3Y"],
                ].map(([days, label]) => (
                  <Pressable
                    key={days}
                    accessibilityRole="button"
                    accessibilityState={{ selected: period === days }}
                    onPress={() => setPeriod(Number(days))}
                    style={{
                      paddingVertical: 8,
                      paddingHorizontal: 13,
                      borderRadius: 7,
                      backgroundColor:
                        period === days ? colors.elevated : "transparent",
                    }}
                  >
                    <Text
                      style={{
                        color: period === days ? colors.green : colors.faint,
                        fontSize: 12,
                      }}
                    >
                      {label}
                    </Text>
                  </Pressable>
                ))}
              </View>
              <LineChart
                points={data.series.map((p) => p.value)}
                labels={data.series.map((p) => p.date)}
              />
              <Text style={s.small}>
                Selected value weights, rebalanced daily. This is a simulation,
                not your actual return history.
              </Text>
            </View>
            <View style={[s.card, { flex: wide ? 1 : undefined }]}>
              <SectionTitle
                title="Where you're invested"
                caption="Current value allocation"
              />
              <View style={{ alignItems: "center" }}>
                <AllocationDonut holdings={data.holdings} />
              </View>
              {data.holdings.slice(0, 6).map((h) => (
                <View key={h.id} style={s.between}>
                  <View style={s.row}>
                    <View
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: 3,
                        backgroundColor: h.color,
                      }}
                    />
                    <Text style={s.small}>{h.symbol}</Text>
                  </View>
                  <Text style={s.body}>{pct(h.weight)}</Text>
                </View>
              ))}
            </View>
          </View>
          <View style={s.between}>
            <SectionTitle
              title="A closer look at risk"
              caption="Historical estimates · selected chart period"
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="View risk analytics"
              onPress={() => router.push("/analytics")}
            >
              <ArrowRight size={21} color={colors.green} />
            </Pressable>
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
            {[
              [
                "Annual volatility",
                pct(data.metrics?.annualized_volatility),
                "Annualized daily variability",
              ],
              [
                "Maximum drawdown",
                pct(data.metrics?.max_drawdown),
                "Largest simulated peak-to-trough loss",
              ],
              [
                "Sharpe ratio",
                data.metrics?.sharpe_ratio?.toFixed(2) || "—",
                "Return relative to variability",
              ],
            ].map(([label, value, caption]) => (
              <View
                key={label}
                style={[
                  s.card,
                  { flexGrow: 1, flexBasis: wide ? 220 : 140, gap: 11 },
                ]}
              >
                <ShieldCheck color={colors.faint} size={17} />
                <Text style={s.small}>{label}</Text>
                <Text style={{ color: colors.text, fontSize: 26 }}>
                  {value}
                </Text>
                <Text style={s.small}>{caption}</Text>
              </View>
            ))}
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push("/scenarios")}
            style={[s.card, s.between]}
          >
            <View style={[s.row, { flex: 1 }]}>
              <FlaskConical color={colors.green} size={24} />
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={s.body}>What if the market falls?</Text>
                <Text style={s.small}>
                  Explore your portfolio under pressure.
                </Text>
              </View>
            </View>
            <ArrowRight size={19} color={colors.muted} />
          </Pressable>
        </>
      )}
    </Screen>
  );
}
