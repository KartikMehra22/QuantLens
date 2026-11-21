import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowRight, Info, ScanLine } from "lucide-react-native";
import { useState } from "react";
import {
  Pressable,
  ScrollView,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { LineChart } from "../../components/charts";
import { BenchmarkPanel } from "../../components/benchmark-panel";
import { EvaluationPanel } from "../../components/evaluation-panel";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Loading,
  Screen,
  SectionTitle,
} from "../../components/ui";
import { usePortfolios, useSummary } from "../../providers";
import { api } from "../../services/api";
import { colors, money, pct, s, shortDate } from "../../theme";
import { Forecast } from "../../types";

export default function Analytics() {
  const [tab, setTab] = useState("Risk");
  const [saved, setSaved] = useState(false);
  const { selected } = usePortfolios();
  const query = useSummary();
  const data = query.data;
  const client = useQueryClient();
  const wide = useWindowDimensions().width > 800;
  const save = useMutation({
    mutationFn: () => api(`/portfolios/${selected!.id}/analyses`, "POST"),
    onSuccess: () => {
      setSaved(true);
      void client.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  const forecasting = useMutation({
    mutationFn: () =>
      api<Forecast>(`/portfolios/${selected!.id}/forecasts`, "POST"),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  // Mutation results are scoped explicitly so switching portfolios cannot show another portfolio's forecast.
  const [forecastPortfolio, setForecastPortfolio] = useState<
    string | undefined
  >();
  const forecastKey = `${selected?.id}:${data?.as_of}:${data?.value}:${data?.data_mode}`;
  const forecast =
    forecastPortfolio === forecastKey ? forecasting.data : undefined;
  const metrics = data?.metrics;
  return (
    <Screen
      title="Beyond the returns."
      description="Understand the relationships and risks behind your portfolio."
    >
      <View
        style={[
          s.row,
          {
            gap: 6,
            padding: 5,
            backgroundColor: colors.card,
            borderRadius: 12,
          },
        ]}
      >
        {["Risk", "Diversification", "Forecasts", "Evaluation"].map((name) => (
          <Pressable
            key={name}
            accessibilityRole="button"
            accessibilityState={{ selected: tab === name }}
            onPress={() => setTab(name)}
            style={{
              flex: 1,
              alignItems: "center",
              paddingVertical: 11,
              borderRadius: 8,
              backgroundColor: tab === name ? colors.elevated : "transparent",
            }}
          >
            <Text
              style={{
                color: tab === name ? colors.green : colors.muted,
                fontSize: 12,
              }}
            >
              {name}
            </Text>
          </Pressable>
        ))}
      </View>
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : selected && query.isPending ? (
        <Loading />
      ) : !data?.holdings.length ? (
        <Empty
          title="Insights begin with holdings"
          description="Add equities to your portfolio to calculate risk and explore diversification."
        />
      ) : (
        <>
          <View style={s.between}>
            <Badge
              text={
                data.data_mode === "synthetic"
                  ? "SYNTHETIC DEMO DATA"
                  : "HISTORICAL OBSERVATIONS"
              }
              color={colors.muted}
            />
            <Text style={s.small}>
              {metrics?.observations || 0} daily returns
            </Text>
          </View>
          {tab === "Risk" && (
            <>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
                {[
                  [
                    "Annual volatility",
                    pct(metrics?.annualized_volatility),
                    "Daily return variability, annualized using 252 trading days.",
                  ],
                  [
                    "Sharpe ratio",
                    metrics?.sharpe_ratio?.toFixed(2) || "—",
                    "Average excess return per unit of variability; assumes a 6% annual risk-free rate.",
                  ],
                  [
                    "Maximum drawdown",
                    pct(metrics?.max_drawdown),
                    "Largest peak-to-trough decline in the hypothetical wealth curve.",
                  ],
                  [
                    "Historical VaR · 95%",
                    pct(metrics?.var_95),
                    "Estimated one-day loss threshold at 95% confidence. Losses can exceed it.",
                  ],
                  [
                    "Historical CVaR · 95%",
                    pct(metrics?.cvar_95),
                    "Average loss in the worst 5% of this historical daily-return sample.",
                  ],
                  [
                    "Annualized growth",
                    pct(metrics?.cagr),
                    "Annualized geometric growth of the hypothetical daily-rebalanced portfolio.",
                  ],
                ].map(([label, value, detail]) => (
                  <View
                    key={label}
                    style={[
                      s.card,
                      { flexBasis: wide ? "30%" : "45%", flexGrow: 1, gap: 14 },
                    ]}
                  >
                    <View style={s.between}>
                      <Activity color={colors.faint} size={16} />
                      <Info color={colors.faint} size={13} />
                    </View>
                    <Text style={s.small}>{label}</Text>
                    <Text
                      style={{
                        color: colors.text,
                        fontSize: 29,
                        letterSpacing: -1,
                      }}
                    >
                      {value}
                    </Text>
                    <Text style={s.small}>{detail}</Text>
                  </View>
                ))}
              </View>
              {metrics && (
                <View style={[s.card, { backgroundColor: "#202B22" }]}>
                  <SectionTitle title="Put tail risk in context" />
                  <Text style={s.subtitle}>
                    At your current valuation, the estimated one-day 95% VaR is{" "}
                    {money(data.value * metrics.var_95)}. Historical losses
                    beyond this threshold averaged{" "}
                    {money(data.value * metrics.cvar_95)}.
                  </Text>
                  <Text style={s.small}>
                    These are sample estimates—not a maximum loss or a
                    prediction.
                  </Text>
                </View>
              )}
              <ErrorBox error={save.error} />
              <Button
                title={
                  saved && save.isSuccess
                    ? "Snapshot saved · see Profile"
                    : "Save this risk analysis"
                }
                secondary
                busy={save.isPending}
                onPress={() => {
                  setSaved(false);
                  save.mutate();
                }}
              />
            </>
          )}
          {tab === "Evaluation" && (
            <EvaluationPanel key={selected!.id} portfolioId={selected!.id} />
          )}
          {tab === "Risk" && <BenchmarkPanel benchmark={data.benchmark} />}
          {tab === "Diversification" && (
            <>
              <View style={s.card}>
                <SectionTitle
                  title="Allocation ≠ risk contribution"
                  caption="A smaller position can contribute more portfolio volatility."
                />
                {data.holdings.map((h) => (
                  <View key={h.id} style={{ gap: 9, paddingVertical: 7 }}>
                    <View style={s.between}>
                      <Text style={s.body}>{h.symbol}</Text>
                      <Text style={s.small}>
                        Weight {pct(h.weight)} · Risk {pct(h.risk_contribution)}
                      </Text>
                    </View>
                    <View
                      style={{
                        backgroundColor: colors.bg,
                        height: 6,
                        borderRadius: 4,
                      }}
                    >
                      <View
                        style={{
                          backgroundColor: h.color,
                          height: 6,
                          borderRadius: 4,
                          width: `${Math.min(100, Math.max(0, (h.risk_contribution || 0) * 100))}%`,
                        }}
                      />
                    </View>
                  </View>
                ))}
                <Text style={s.small}>
                  Bars show positive volatility contributions; negative
                  contributions, if any, remain visible numerically.
                </Text>
              </View>
              <View style={s.card}>
                <SectionTitle
                  title="How your holdings move together"
                  caption="Pearson correlation · same aligned daily observations"
                />
                {data.diversification ? (
                  <ScrollView horizontal showsHorizontalScrollIndicator>
                    <View style={{ gap: 5 }}>
                      <View style={s.row}>
                        <View style={{ width: 65 }} />
                        {data.diversification.symbols.map((symbol, i) => (
                          <Text
                            key={`${symbol}-${i}`}
                            style={[
                              s.small,
                              { width: 54, fontSize: 9, textAlign: "center" },
                            ]}
                          >
                            {symbol.slice(0, 7)}
                          </Text>
                        ))}
                      </View>
                      {data.diversification.correlations.map((row, i) => (
                        <View key={i} style={s.row}>
                          <Text style={[s.small, { width: 65, fontSize: 10 }]}>
                            {data.diversification!.symbols[i].slice(0, 9)}
                          </Text>
                          {row.map((v, j) => (
                            <View
                              key={j}
                              style={{
                                width: 54,
                                height: 43,
                                borderRadius: 5,
                                alignItems: "center",
                                justifyContent: "center",
                                backgroundColor:
                                  v == null
                                    ? colors.bg
                                    : v >= 0
                                      ? `rgba(139,190,132,${0.12 + v * 0.6})`
                                      : `rgba(211,142,132,${0.12 + Math.abs(v) * 0.6})`,
                              }}
                            >
                              <Text
                                style={{ color: colors.text, fontSize: 11 }}
                              >
                                {v?.toFixed(2) || "—"}
                              </Text>
                            </View>
                          ))}
                        </View>
                      ))}
                    </View>
                  </ScrollView>
                ) : (
                  <Text style={s.small}>
                    More observations are needed to calculate correlations.
                  </Text>
                )}
                <Text style={s.small}>
                  +1: move together · 0: little linear relationship · −1: move
                  oppositely. Historical relationships can change.
                </Text>
              </View>
              <View style={s.card}>
                <SectionTitle title="Sector exposure" />
                {Array.from(new Set(data.holdings.map((h) => h.sector))).map(
                  (sector) => (
                    <View key={sector} style={s.between}>
                      <Text style={s.body}>{sector}</Text>
                      <Text style={s.small}>
                        {pct(
                          data.holdings
                            .filter((h) => h.sector === sector)
                            .reduce((total, h) => total + h.weight, 0),
                        )}
                      </Text>
                    </View>
                  ),
                )}
              </View>
            </>
          )}
          {tab === "Forecasts" && (
            <>
              <View
                style={[s.card, { padding: 24, backgroundColor: "#1B2926" }]}
              >
                <ScanLine color={colors.green} size={30} />
                <SectionTitle
                  title="Forecast variability. Understand uncertainty."
                  caption="EWMA + GARCH(1,1) + a historical baseline"
                />
                <Text style={s.subtitle}>
                  Compare conditional volatility estimates for the next five
                  trading days. Models use up to three years of aligned returns
                  and assume a zero conditional mean.
                </Text>
                <Button
                  title={
                    forecast
                      ? "Regenerate forecasts"
                      : "Generate volatility forecasts"
                  }
                  busy={forecasting.isPending}
                  onPress={() => {
                    setForecastPortfolio(forecastKey);
                    forecasting.mutate();
                  }}
                />
                <ErrorBox error={forecasting.error} />
              </View>
              {forecast && (
                <>
                  <View style={s.card}>
                    <SectionTitle
                      title="Five trading days ahead"
                      caption="Annualized volatility · each horizon is a daily variance forecast"
                    />
                    {Object.entries(forecast.models).map(
                      ([name, values], i) => (
                        <View key={name} style={{ gap: 12 }}>
                          <View style={s.between}>
                            <View style={s.row}>
                              <View
                                style={{
                                  height: 7,
                                  width: 7,
                                  borderRadius: 4,
                                  backgroundColor: [
                                    colors.muted,
                                    colors.green,
                                    colors.blue,
                                  ][i],
                                }}
                              />
                              <Text style={s.body}>{name}</Text>
                            </View>
                            <Text style={s.body}>{pct(values[0])}</Text>
                          </View>
                          <LineChart
                            points={values.map((v) => v * 100)}
                            labels={values.map(
                              (_, index) => `Day ${index + 1}`,
                            )}
                            color={[colors.muted, colors.green, colors.blue][i]}
                            height={70}
                          />
                        </View>
                      ),
                    )}
                    <Text style={s.small}>
                      Fit through {shortDate(forecast.as_of)} ·{" "}
                      {forecast.observations} observations. EWMA and the
                      baseline have flat multi-step variance forecasts under
                      these assumptions.
                    </Text>
                  </View>
                  <View style={s.card}>
                    <SectionTitle title="Inside the GARCH model" />
                    {Object.entries(forecast.parameters).map(([key, value]) => (
                      <View key={key} style={s.between}>
                        <Text style={s.small}>{key}</Text>
                        <Text style={s.body}>{value.toFixed(6)}</Text>
                      </View>
                    ))}
                    <Text style={s.small}>{forecast.warning}</Text>
                  </View>
                </>
              )}
              <View style={[s.row, { alignItems: "flex-start" }]}>
                <ArrowRight size={17} color={colors.faint} />
                <Text style={[s.small, { flex: 1 }]}>
                  Current forecasts are saved to your analysis history. The
                  repository also includes a rolling out-of-sample evaluation
                  script for the project experiment.
                </Text>
              </View>
            </>
          )}
          <View style={s.card}>
            <SectionTitle title="Know the assumptions" />
            {data.warnings.map((w) => (
              <Text key={w} style={s.small}>
                • {w}
              </Text>
            ))}
            <Text style={s.small}>
              Period: {data.period_start} → {data.period_end}. Educational
              analysis; estimates do not guarantee future outcomes.
            </Text>
          </View>
        </>
      )}
    </Screen>
  );
}
