import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { api, exportEvaluation } from "../services/api";
import { colors, s, shortDate } from "../theme";
import { Evaluation } from "../types";
import { MultiLineChart } from "./charts";
import { Badge, Button, ErrorBox, Loading, SectionTitle } from "./ui";

export function EvaluationPanel({ portfolioId }: { portfolioId: string }) {
  const [training, setTraining] = useState(504);
  const [days, setDays] = useState(60);
  const [chosen, setChosen] = useState<string | null>(null);
  const client = useQueryClient();
  const path = `/portfolios/${portfolioId}/evaluations`;
  const list = useQuery({
    queryKey: ["evaluations", portfolioId],
    queryFn: () => api<Evaluation[]>(path),
    refetchInterval: (query) =>
      query.state.data?.some((j) => ["queued", "running"].includes(j.status))
        ? 1000
        : false,
  });
  const jobId = chosen || list.data?.[0]?.id;
  const detail = useQuery({
    queryKey: ["evaluation", portfolioId, jobId],
    queryFn: () => api<Evaluation>(`${path}/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) =>
      query.state.data &&
      ["queued", "running"].includes(query.state.data.status)
        ? 1000
        : false,
  });
  const job = detail.data;
  const active = list.data?.some((j) =>
    ["queued", "running"].includes(j.status),
  );
  const create = useMutation({
    mutationFn: () =>
      api<Evaluation>(path, "POST", {
        training_window: training,
        test_days: days,
      }),
    onSuccess: (result) => {
      setChosen(result.id);
      void client.invalidateQueries({ queryKey: ["evaluations", portfolioId] });
    },
  });
  const download = useMutation({
    mutationFn: () => exportEvaluation(portfolioId, jobId!),
  });
  const cancel = useMutation({
    mutationFn: () => api(`${path}/${jobId}`, "DELETE"),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["evaluations", portfolioId] });
      void detail.refetch();
    },
  });
  const result = job?.result;
  const palette = [colors.muted, colors.green, colors.blue];
  return (
    <View style={{ gap: 18 }}>
      <View style={s.card}>
        <SectionTitle
          title="Test the models on unseen days"
          caption="Rolling one-day-ahead forecasts using past observations only"
        />
        <Text style={s.small}>Training window</Text>
        <View style={s.row}>
          {[252, 504, 756].map((value) => (
            <Pressable
              key={value}
              accessibilityRole="button"
              onPress={() => setTraining(value)}
              style={[
                s.chip,
                {
                  backgroundColor:
                    training === value ? colors.greenDark : colors.bg,
                },
              ]}
            >
              <Text
                style={{
                  color: training === value ? colors.green : colors.muted,
                }}
              >
                {value} days
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.small}>Evaluation period</Text>
        <View style={[s.row, { flexWrap: "wrap" }]}>
          {[20, 60, 126, 252].map((value) => (
            <Pressable
              key={value}
              accessibilityRole="button"
              onPress={() => setDays(value)}
              style={[
                s.chip,
                {
                  backgroundColor:
                    days === value ? colors.greenDark : colors.bg,
                },
              ]}
            >
              <Text
                style={{ color: days === value ? colors.green : colors.muted }}
              >
                {value} days
              </Text>
            </Pressable>
          ))}
        </View>
        <Text style={s.small}>
          Each model is fitted again before the next target day. The historical
          baseline, EWMA and GARCH use the same target dates. Runs continue on
          the backend if you leave this screen.
        </Text>
        <ErrorBox error={create.error} />
        <Button
          title="Run out-of-sample evaluation"
          busy={create.isPending}
          disabled={active}
          onPress={() => create.mutate()}
        />
      </View>
      {list.error && <ErrorBox error={list.error} />}
      {list.data && list.data.length > 0 && (
        <View style={s.card}>
          <SectionTitle title="Saved experiments" />
          {list.data.slice(0, 8).map((item) => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Open evaluation ${item.test_days} days ${item.status}`}
              key={item.id}
              onPress={() => setChosen(item.id)}
              style={[s.between, { paddingVertical: 8 }]}
            >
              <View style={{ gap: 4 }}>
                <Text style={s.body}>
                  {item.test_days} target days · {item.training_window} training
                </Text>
                <Text style={s.small}>
                  {shortDate(item.as_of)} · {item.data_mode}
                </Text>
              </View>
              <Badge
                text={item.status.toUpperCase()}
                color={item.status === "failed" ? colors.red : colors.green}
              />
            </Pressable>
          ))}
        </View>
      )}
      {jobId && detail.isPending && <Loading />}
      <ErrorBox error={detail.error} />
      {job && ["queued", "running"].includes(job.status) && (
        <View style={s.card}>
          <Text style={s.body}>
            {job.status === "queued"
              ? "Waiting for the evaluation worker"
              : `Evaluating day ${job.progress} of ${job.total}`}
          </Text>
          <View
            style={{ height: 6, backgroundColor: colors.bg, borderRadius: 4 }}
          >
            <View
              style={{
                height: 6,
                borderRadius: 4,
                backgroundColor: colors.green,
                width: `${(job.progress / job.total) * 100}%`,
              }}
            />
          </View>
          <Button
            title="Cancel evaluation"
            secondary
            busy={cancel.isPending}
            onPress={() => cancel.mutate()}
          />
        </View>
      )}
      {job?.error && <ErrorBox error={new Error(job.error)} />}
      {result && (
        <>
          <Button
            title="Export reproducible evaluation JSON"
            secondary
            busy={download.isPending}
            onPress={() => download.mutate()}
          />
          <ErrorBox error={download.error} />
          <View style={s.card}>
            <SectionTitle
              title="Forecast errors"
              caption="Daily variance scale · lower values indicate lower loss"
            />
            <Badge
              text={
                job.data_mode === "synthetic"
                  ? "SYNTHETIC SOFTWARE TEST"
                  : "HISTORICAL DATA EXPERIMENT"
              }
              color={colors.muted}
            />
            {Object.entries(result.metrics).map(([model, values]) => (
              <View key={model} style={{ gap: 9, paddingVertical: 8 }}>
                <Text style={s.body}>{model}</Text>
                <View style={s.between}>
                  <Text style={s.small}>MAE {values.mae.toExponential(3)}</Text>
                  <Text style={s.small}>
                    RMSE {values.rmse.toExponential(3)}
                  </Text>
                  <Text style={s.small}>QLIKE {values.qlike.toFixed(4)}</Text>
                </View>
              </View>
            ))}
            <Text style={s.small}>
              QLIKE can be negative with this logarithmic loss definition.
              Compare models on the same dates and variance scale.
            </Text>
          </View>
          <View style={s.card}>
            <SectionTitle
              title="Predictions and observed proxy"
              caption="Daily variance × 10,000 · tap the chart to inspect a day"
            />
            <MultiLineChart
              labels={result.evaluation_dates}
              series={[
                {
                  name: "Squared return proxy",
                  color: "#6D8075",
                  values: result.targets.map((v) => v * 10000),
                },
                ...Object.entries(result.predictions).map(
                  ([name, values], i) => ({
                    name,
                    color: palette[i],
                    values: values.map((v) => v * 10000),
                  }),
                ),
              ]}
            />
          </View>
          <View style={s.card}>
            <SectionTitle title="How to interpret the experiment" />
            <Text style={s.small}>
              {result.target}. {result.limitation}
            </Text>
            <Text style={s.small}>
              Targets: {result.evaluation_dates[0]} to{" "}
              {result.evaluation_dates.at(-1)}. No model is assumed to
              outperform the baseline.
            </Text>
          </View>
        </>
      )}
    </View>
  );
}
