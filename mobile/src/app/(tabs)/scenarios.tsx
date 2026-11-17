import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, FlaskConical } from "lucide-react-native";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Screen,
  SectionTitle,
} from "../../components/ui";
import { usePortfolios, useSummary } from "../../providers";
import { api } from "../../services/api";
import { colors, money, pct, s } from "../../theme";
import { Scenario } from "../../types";

export default function Scenarios() {
  const { selected } = usePortfolios();
  const query = useSummary();
  const data = query.data;
  const client = useQueryClient();
  const [decline, setDecline] = useState("10");
  const [custom, setCustom] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [resultKey, setResultKey] = useState("");
  const key = `${selected?.id}:${data?.as_of}:${data?.value}:${data?.data_mode}`;
  const scenario = useMutation({
    mutationFn: async () => {
      const value = Number(decline);
      if (
        !decline.trim() ||
        !Number.isFinite(value) ||
        value < 0 ||
        value > 100
      )
        throw new Error("Enter a decline between 0% and 100%.");
      const shocks: Record<string, number> = {};
      if (custom)
        for (const [id, text] of Object.entries(overrides)) {
          if (!text.trim()) continue;
          const number = Number(text);
          if (!Number.isFinite(number) || number < 0 || number > 100)
            throw new Error("Each asset decline must be between 0% and 100%.");
          shocks[id] = -number / 100;
        }
      setResultKey(key);
      return api<Scenario>(`/portfolios/${selected!.id}/stress-tests`, "POST", {
        shock: -value / 100,
        overrides: shocks,
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  const result = resultKey === key ? scenario.data : undefined;
  return (
    <Screen
      title="Explore the what-ifs."
      description="See how assumed price shocks affect what you hold."
    >
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : selected && query.isPending ? (
        <Loading />
      ) : !data?.holdings.length ? (
        <Empty
          title="Build a portfolio first"
          description="Scenarios apply hypothetical shocks to your current holdings."
        />
      ) : (
        <>
          <View style={[s.card, { backgroundColor: "#222820" }]}>
            <View style={s.between}>
              <FlaskConical color={colors.green} size={27} />
              <Badge text="HYPOTHETICAL SCENARIOS" color={colors.amber} />
            </View>
            <SectionTitle
              title="How much pressure can you picture?"
              caption="Choose a uniform decline, then adjust individual assets if needed."
            />
            <View style={{ flexDirection: "row", gap: 10 }}>
              {[
                [5, "Mild"],
                [10, "Moderate"],
                [20, "Severe"],
              ].map(([amount, label]) => (
                <Pressable
                  key={amount}
                  accessibilityRole="button"
                  onPress={() => {
                    setDecline(String(amount));
                    scenario.reset();
                  }}
                  style={{
                    flex: 1,
                    borderRadius: 12,
                    paddingVertical: 17,
                    alignItems: "center",
                    gap: 8,
                    borderWidth: 1,
                    borderColor:
                      Number(decline) === amount ? colors.green : colors.line,
                    backgroundColor:
                      Number(decline) === amount ? colors.greenDark : colors.bg,
                  }}
                >
                  <Text style={{ color: colors.text, fontSize: 24 }}>
                    −{amount}%
                  </Text>
                  <Text style={s.small}>{label}</Text>
                </Pressable>
              ))}
            </View>
            <Field
              label="Assumed decline (%)"
              value={decline}
              onChangeText={(v) => {
                setDecline(v);
                scenario.reset();
              }}
              numeric
              placeholder="0 to 100"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setCustom(!custom);
                scenario.reset();
              }}
              style={[s.between, { paddingVertical: 9 }]}
            >
              <Text style={s.body}>Adjust each holding</Text>
              <Badge
                text={custom ? "ON" : "OFF"}
                color={custom ? colors.green : colors.muted}
              />
            </Pressable>
            {custom && (
              <View style={{ gap: 12 }}>
                {data.holdings.map((h) => (
                  <View key={h.id} style={s.between}>
                    <Text style={s.small}>{h.symbol}</Text>
                    <View style={[s.row, { width: 115 }]}>
                      <TextInput
                        accessibilityLabel={`${h.symbol} decline percentage`}
                        placeholder={decline}
                        placeholderTextColor={colors.faint}
                        keyboardType="decimal-pad"
                        value={overrides[h.instrument_id] || ""}
                        onChangeText={(v) => {
                          setOverrides({ ...overrides, [h.instrument_id]: v });
                          scenario.reset();
                        }}
                        style={[
                          s.input,
                          { flex: 1, paddingVertical: 9, minHeight: 42 },
                        ]}
                      />
                      <Text style={s.small}>%</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
            <ErrorBox error={scenario.error} />
            <Button
              title="Run stress test"
              busy={scenario.isPending}
              onPress={() => scenario.mutate()}
            />
          </View>
          {result && (
            <>
              <View style={[s.card, { padding: 24 }]}>
                <Text style={s.label}>YOUR SCENARIO RESULT</Text>
                <View style={{ gap: 8 }}>
                  <Text style={s.small}>Current portfolio value</Text>
                  <Text style={{ color: colors.text, fontSize: 25 }}>
                    {money(result.before)}
                  </Text>
                </View>
                <ArrowDown size={20} color={colors.faint} />
                <View style={{ gap: 8 }}>
                  <Text style={s.small}>Estimated value after shock</Text>
                  <Text
                    style={{
                      color: colors.text,
                      fontSize: 36,
                      letterSpacing: -1,
                    }}
                  >
                    {money(result.after)}
                  </Text>
                </View>
                <View
                  style={[
                    s.between,
                    {
                      paddingTop: 15,
                      borderTopWidth: 1,
                      borderTopColor: colors.line,
                    },
                  ]}
                >
                  <Text style={{ color: colors.red }}>
                    {money(result.change)}
                  </Text>
                  <Text style={{ color: colors.red }}>
                    {pct(result.change_pct)}
                  </Text>
                </View>
              </View>
              <View style={s.card}>
                <SectionTitle title="Where the loss comes from" />
                {result.holdings.map((h) => (
                  <View key={h.id} style={s.between}>
                    <View style={{ gap: 4 }}>
                      <Text style={s.body}>{h.symbol}</Text>
                      <Text style={s.small}>{pct(h.shock)} assumed shock</Text>
                    </View>
                    <Text style={{ color: colors.red }}>{money(h.change)}</Text>
                  </View>
                ))}
              </View>
            </>
          )}
          <Text style={s.small}>
            These calculations apply entered price shocks directly to current
            holdings. They do not estimate scenario probability, model changing
            correlations, or predict future losses. Results are saved to your
            analysis history.
          </Text>
        </>
      )}
    </Screen>
  );
}
