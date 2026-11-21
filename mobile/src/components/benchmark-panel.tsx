import { Text, View } from "react-native";
import { colors, pct, s } from "../theme";
import { Benchmark } from "../types";
import { MultiLineChart } from "./charts";
import { SectionTitle } from "./ui";

export function BenchmarkPanel({ benchmark }: { benchmark?: Benchmark }) {
  if (!benchmark?.available)
    return (
      <View style={s.card}>
        <SectionTitle title="Nifty 50 comparison" />
        <Text style={s.small}>
          {benchmark?.reason ||
            "Benchmark comparison is unavailable for this portfolio."}
        </Text>
      </View>
    );
  const series = benchmark.series || [];
  return (
    <View style={s.card}>
      <SectionTitle
        title="Your portfolio and the Nifty 50"
        caption="Price return comparison · growth of ₹100"
      />
      <MultiLineChart
        labels={series.map((p) => p.date)}
        series={[
          {
            name: "Portfolio price return",
            color: colors.green,
            values: series.map((p) => p.portfolio),
          },
          {
            name: "Nifty 50 price index",
            color: colors.blue,
            values: series.map((p) => p.benchmark),
          },
        ]}
      />
      <View style={s.between}>
        <Text style={s.small}>Portfolio {pct(benchmark.portfolio_return)}</Text>
        <Text style={s.small}>Nifty 50 {pct(benchmark.benchmark_return)}</Text>
      </View>
      <View style={s.between}>
        <Text style={s.small}>Difference</Text>
        <Text style={s.body}>
          {((benchmark.difference || 0) * 100).toFixed(2)} percentage points
        </Text>
      </View>
      <View style={s.between}>
        <Text style={s.small}>Historical beta</Text>
        <Text style={s.body}>{benchmark.beta?.toFixed(2) || "—"}</Text>
      </View>
      <Text style={s.small}>
        {benchmark.basis} This comparison excludes dividends from both series;
        the main risk/performance view uses dividend-adjusted returns.
      </Text>
    </View>
  );
}
