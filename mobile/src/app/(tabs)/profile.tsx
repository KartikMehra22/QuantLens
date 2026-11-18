import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, History, Settings2 } from "lucide-react-native";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import {
  Badge,
  Button,
  ErrorBox,
  Field,
  Loading,
  Screen,
  SectionTitle,
  Sheet,
} from "../../components/ui";
import { usePortfolios, useSession, useSummary } from "../../providers";
import { api, exportReport } from "../../services/api";
import { colors, money, pct, s, shortDate } from "../../theme";
import { Holding, Metrics, Report } from "../../types";

type Detail = {
  kind: string;
  created_at: string;
  payload: {
    as_of: string;
    data_mode: string;
    value?: number;
    pnl?: number;
    before?: number;
    after?: number;
    change?: number;
    holdings?: Holding[];
    metrics?: Metrics;
    models?: Record<string, number[]>;
  };
};
export default function Profile() {
  const { user, logout } = useSession();
  const { selected, select } = usePortfolios();
  const summary = useSummary();
  const client = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [manage, setManage] = useState(false);
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [importing, setImporting] = useState(false);
  const [csv, setCsv] = useState("");
  const [instrument, setInstrument] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const reports = useQuery({
    queryKey: ["reports", selected?.id],
    queryFn: () => api<Report[]>(`/portfolios/${selected!.id}/reports`),
    enabled: !!selected,
  });
  const perform = async (
    key: string,
    action: () => Promise<unknown>,
    success = "",
  ) => {
    setBusy(key);
    setError(null);
    setMessage("");
    try {
      await action();
      setMessage(success);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };
  const invalidate = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["portfolios"] }),
      client.invalidateQueries({ queryKey: ["summary"] }),
      client.invalidateQueries({ queryKey: ["prices"] }),
    ]);
  };
  return (
    <Screen
      title="Your workspace."
      description="Manage your account, data, and saved analyses."
    >
      <View style={s.card}>
        <View style={s.row}>
          <View
            style={{
              width: 48,
              height: 48,
              borderRadius: 24,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: colors.greenDark,
            }}
          >
            <Text style={{ color: colors.green, fontSize: 21 }}>
              {user?.name[0]?.toUpperCase()}
            </Text>
          </View>
          <View style={{ flex: 1, gap: 5 }}>
            <Text style={{ color: colors.text, fontSize: 19 }}>
              {user?.name}
            </Text>
            <Text numberOfLines={1} style={s.small}>
              {user?.email.endsWith("@quantlens.invalid")
                ? "Your isolated demonstration account"
                : user?.email}
            </Text>
          </View>
        </View>
        <Text style={s.small}>QuantLens v0.1 · Virtual portfolios · INR</Text>
      </View>
      <ErrorBox error={error} />
      {message ? (
        <View
          style={{
            padding: 15,
            borderRadius: 12,
            backgroundColor: colors.greenDark,
          }}
        >
          <Text style={{ color: colors.green, fontSize: 13, lineHeight: 20 }}>
            {message}
          </Text>
        </View>
      ) : null}
      {selected && (
        <>
          <View style={s.card}>
            <View style={s.between}>
              <SectionTitle title="Portfolio & data" />
              <Settings2 size={19} color={colors.faint} />
            </View>
            <View style={s.between}>
              <Text style={s.small}>Selected portfolio</Text>
              <Text style={s.body}>{selected.name}</Text>
            </View>
            <View style={s.between}>
              <Text style={s.small}>Price source</Text>
              <Badge
                text={
                  selected.data_mode === "synthetic"
                    ? "SYNTHETIC DEMO"
                    : selected.data_mode.toUpperCase()
                }
                color={colors.muted}
              />
            </View>
            <View style={s.between}>
              <Text style={s.small}>Latest common price date</Text>
              <Text style={s.small}>
                {shortDate(summary.data?.as_of || null)}
              </Text>
            </View>
            <Text style={s.small}>
              Download historical prices for every holding from Yahoo. The
              source switches only after all required downloads and overlap
              checks succeed.
            </Text>
            <Button
              title="Download historical market data"
              secondary
              busy={busy === "refresh"}
              disabled={!!busy}
              onPress={() =>
                void perform(
                  "refresh",
                  async () => {
                    await api(
                      `/portfolios/${selected.id}/data-refreshes`,
                      "POST",
                    );
                    await invalidate();
                  },
                  "Historical prices downloaded. Your portfolio now uses Yahoo data.",
                )
              }
            />
            <View style={{ flexDirection: "row", gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Button
                  title="Manage portfolio"
                  secondary
                  disabled={!!busy}
                  onPress={() => {
                    setName(selected.name);
                    setConfirm(false);
                    setManage(true);
                    setError(null);
                  }}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Button
                  title="Import CSV"
                  secondary
                  disabled={!!busy}
                  onPress={() => {
                    setImporting(true);
                    setError(null);
                  }}
                />
              </View>
            </View>
            {selected.data_mode !== "synthetic" && (
              <Button
                title="Switch to synthetic demo data"
                secondary
                disabled={!!busy}
                onPress={() =>
                  void perform(
                    "source",
                    async () => {
                      await api(`/portfolios/${selected.id}`, "PATCH", {
                        name: selected.name,
                        data_mode: "synthetic",
                      });
                      await invalidate();
                    },
                    "Switched to clearly labelled synthetic demonstration data.",
                  )
                }
              />
            )}
          </View>
          <View style={s.card}>
            <View style={s.between}>
              <SectionTitle
                title="Take your analysis with you"
                caption="Current holdings, source, dates, and assumptions"
              />
              <Download color={colors.faint} size={19} />
            </View>
            <View style={{ flexDirection: "row", gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Button
                  title="Export CSV"
                  secondary
                  busy={busy === "csv"}
                  disabled={!!busy}
                  onPress={() =>
                    void perform(
                      "csv",
                      () => exportReport(selected.id, "csv"),
                      "CSV export prepared.",
                    )
                  }
                />
              </View>
              <View style={{ flex: 1 }}>
                <Button
                  title="Export PDF"
                  secondary
                  busy={busy === "pdf"}
                  disabled={!!busy}
                  onPress={() =>
                    void perform(
                      "pdf",
                      () => exportReport(selected.id, "pdf"),
                      "PDF export prepared.",
                    )
                  }
                />
              </View>
            </View>
          </View>
          <View style={s.card}>
            <View style={s.between}>
              <SectionTitle
                title="Analysis history"
                caption="Saved snapshots retain their original holdings and source."
              />
              <History color={colors.faint} size={19} />
            </View>
            {reports.isPending ? (
              <Loading />
            ) : reports.error ? (
              <ErrorBox error={reports.error} />
            ) : !reports.data?.length ? (
              <Text style={s.small}>
                Save a risk analysis, run a scenario, or generate a forecast to
                start your history.
              </Text>
            ) : (
              reports.data.map((r) => (
                <Pressable
                  key={r.id}
                  accessibilityRole="button"
                  accessibilityLabel={`Open ${r.kind} analysis`}
                  disabled={!!busy}
                  onPress={() =>
                    void perform("report", async () => {
                      setDetail(
                        await api<Detail>(
                          `/portfolios/${selected.id}/reports/${r.id}`,
                        ),
                      );
                    })
                  }
                  style={[s.between, { paddingVertical: 11 }]}
                >
                  <View style={[s.row, { flex: 1 }]}>
                    <FileText size={18} color={colors.muted} />
                    <View style={{ gap: 4 }}>
                      <Text style={s.body}>
                        {r.kind === "risk"
                          ? "Risk snapshot"
                          : r.kind === "stress"
                            ? "Stress scenario"
                            : "Volatility forecast"}
                      </Text>
                      <Text style={s.small}>
                        {new Date(
                          r.created_at.endsWith("Z") ||
                            r.created_at.includes("+")
                            ? r.created_at
                            : `${r.created_at}Z`,
                        ).toLocaleString("en-IN")}
                      </Text>
                    </View>
                  </View>
                  <Badge
                    text={
                      r.data_mode === "synthetic"
                        ? "DEMO"
                        : r.data_mode.toUpperCase()
                    }
                    color={colors.faint}
                  />
                </Pressable>
              ))
            )}
          </View>
        </>
      )}
      <View style={s.card}>
        <SectionTitle title="What QuantLens measures" />
        <Text style={s.subtitle}>
          Current valuation uses share quantities and closing prices. Historical
          analytics simulate today’s value weights rebalanced daily using
          adjusted price returns.
        </Text>
        <Text style={s.small}>
          The default risk view uses up to 252 daily observations, a 6% annual
          risk-free assumption, and one-day 95% historical VaR/CVaR. Forecasts
          estimate conditional variability, not prices. Synthetic data uses
          generated business-day observations, not an exchange calendar.
        </Text>
        <Text style={s.small}>
          Yahoo access depends on provider availability and terms. This
          educational app does not execute trades or provide personalized
          investment advice.
        </Text>
      </View>
      <Button
        title="Sign out"
        secondary
        disabled={!!busy}
        onPress={() => void perform("logout", logout)}
      />
      <Sheet
        title="Manage portfolio"
        visible={manage}
        close={() => {
          if (!busy) setManage(false);
        }}
      >
        <Field label="Portfolio name" value={name} onChangeText={setName} />
        <ErrorBox error={error} />
        <Button
          title="Save name"
          busy={busy === "rename"}
          disabled={!!busy || !name.trim()}
          onPress={() =>
            void perform(
              "rename",
              async () => {
                await api(`/portfolios/${selected!.id}`, "PATCH", {
                  name: name.trim(),
                  data_mode: selected!.data_mode,
                });
                await invalidate();
                setManage(false);
              },
              "Portfolio renamed.",
            )
          }
        />
        <Text style={s.small}>
          Deleting a portfolio also deletes its holdings and saved analyses.
        </Text>
        <Button
          title={confirm ? "Confirm portfolio deletion" : "Delete portfolio"}
          danger
          disabled={!!busy}
          onPress={() =>
            confirm
              ? void perform(
                  "delete",
                  async () => {
                    await api(`/portfolios/${selected!.id}`, "DELETE");
                    select("");
                    await invalidate();
                    setManage(false);
                  },
                  "Portfolio deleted.",
                )
              : setConfirm(true)
          }
        />
      </Sheet>
      <Sheet
        title="Import historical prices"
        visible={importing}
        close={() => {
          if (!busy) setImporting(false);
        }}
      >
        <Text style={s.small}>
          Paste CSV with columns date,close,adjusted_close. Use YYYY-MM-DD
          dates. Import every holding before switching the portfolio source to
          CSV.
        </Text>
        <Field
          label="Instrument ID"
          value={instrument}
          onChangeText={setInstrument}
          placeholder="e.g. TCS.NS"
        />
        <Field
          label="CSV content"
          value={csv}
          onChangeText={setCsv}
          multiline
          placeholder={
            "date,close,adjusted_close\n2025-01-02,4000,3950\n2025-01-03,4020,3970"
          }
        />
        <ErrorBox error={error} />
        {message && <Text style={{ color: colors.green }}>{message}</Text>}
        <Button
          title="Import prices"
          busy={busy === "import"}
          disabled={!!busy || !instrument || !csv}
          onPress={() =>
            void perform(
              "import",
              () =>
                api(`/portfolios/${selected!.id}/prices/import`, "POST", {
                  instrument_id: instrument.trim(),
                  csv_text: csv,
                }),
              "CSV imported. Import any remaining holdings before switching sources.",
            )
          }
        />
        <Button
          title="Use imported CSV data"
          secondary
          disabled={!!busy}
          onPress={() =>
            void perform(
              "source",
              async () => {
                await api(`/portfolios/${selected!.id}`, "PATCH", {
                  name: selected!.name,
                  data_mode: "csv",
                });
                await invalidate();
                setImporting(false);
              },
              "Portfolio source set to CSV. Missing histories will be reported explicitly.",
            )
          }
        />
      </Sheet>
      <Sheet
        title="Saved analysis"
        visible={!!detail}
        close={() => setDetail(null)}
      >
        {detail && (
          <>
            <Badge
              text={`${detail.kind.toUpperCase()} · ${detail.payload.data_mode.toUpperCase()}`}
            />
            <Text style={s.small}>Price date: {detail.payload.as_of}</Text>
            {detail.payload.value != null && (
              <View style={s.between}>
                <Text style={s.body}>Portfolio value</Text>
                <Text style={s.body}>{money(detail.payload.value)}</Text>
              </View>
            )}
            {detail.payload.after != null && (
              <>
                <View style={s.between}>
                  <Text style={s.body}>Stressed value</Text>
                  <Text style={s.body}>{money(detail.payload.after)}</Text>
                </View>
                <Text style={{ color: colors.red }}>
                  Change {money(detail.payload.change || 0)}
                </Text>
              </>
            )}
            {detail.payload.metrics &&
              Object.entries({
                "Annual volatility": pct(
                  detail.payload.metrics.annualized_volatility,
                ),
                "Maximum drawdown": pct(detail.payload.metrics.max_drawdown),
                "95% daily VaR": pct(detail.payload.metrics.var_95),
              }).map(([label, value]) => (
                <View key={label} style={s.between}>
                  <Text style={s.small}>{label}</Text>
                  <Text style={s.body}>{value}</Text>
                </View>
              ))}
            {detail.payload.models &&
              Object.entries(detail.payload.models).map(([model, values]) => (
                <View key={model} style={s.between}>
                  <Text style={s.small}>{model} · day 1</Text>
                  <Text style={s.body}>{pct(values[0])}</Text>
                </View>
              ))}
            <SectionTitle title="Holdings in this snapshot" />
            {detail.payload.holdings?.map((h) => (
              <View key={h.id} style={s.between}>
                <Text style={s.small}>{h.symbol}</Text>
                <Text style={s.body}>{h.quantity} shares</Text>
              </View>
            ))}
          </>
        )}
      </Sheet>
    </Screen>
  );
}
