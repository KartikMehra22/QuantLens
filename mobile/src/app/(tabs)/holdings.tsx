import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Plus, Search } from "lucide-react-native";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { LineChart } from "../../components/charts";
import {
  Badge,
  Button,
  Change,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Screen,
  Sheet,
} from "../../components/ui";
import { usePortfolios, useSummary } from "../../providers";
import { api } from "../../services/api";
import { colors, money, pct, s } from "../../theme";
import { Holding, Instrument } from "../../types";

type PriceHistory = {
  prices: { date: string; close: number }[];
  source: string;
};
export default function Holdings() {
  const { selected } = usePortfolios();
  const query = useSummary();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(true);
  const [holding, setHolding] = useState<Holding | null>(null);
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [search, setSearch] = useState("");
  const [quantity, setQuantity] = useState("");
  const [cost, setCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirm, setConfirm] = useState(false);
  const instruments = useQuery({
    queryKey: ["instruments", search],
    queryFn: () =>
      api<Instrument[]>(`/instruments/search?q=${encodeURIComponent(search)}`),
    enabled: open && editing && !holding,
  });
  const history = useQuery({
    queryKey: [
      "prices",
      selected?.id,
      holding?.instrument_id,
      selected?.data_mode,
    ],
    queryFn: () =>
      api<PriceHistory>(
        `/instruments/${encodeURIComponent(holding!.instrument_id)}/prices?source=${selected!.data_mode}&portfolio_id=${selected!.id}`,
      ),
    enabled: open && !editing && !!holding && !!selected,
  });
  const show = (item: Holding | null) => {
    setHolding(item);
    setEditing(!item);
    setInstrument(item ? { ...item, id: item.instrument_id } : null);
    setQuantity(item ? String(item.quantity) : "");
    setCost(item ? String(item.average_cost) : "");
    setSearch("");
    setError(null);
    setConfirm(false);
    setOpen(true);
  };
  const save = async (remove = false) => {
    if (!selected || !instrument) return;
    if (
      !remove &&
      (!Number.isFinite(Number(quantity)) ||
        !Number.isFinite(Number(cost)) ||
        Number(quantity) <= 0 ||
        Number(cost) <= 0)
    ) {
      setError(
        new Error("Enter a positive quantity and average purchase price."),
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(
        `/portfolios/${selected.id}/holdings${holding ? `/${holding.id}` : ""}`,
        remove ? "DELETE" : holding ? "PATCH" : "POST",
        remove
          ? undefined
          : { instrument_id: instrument.id, quantity, average_cost: cost },
      );
      await client.invalidateQueries({ queryKey: ["summary"] });
      setOpen(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen
      title="What you hold."
      description="Your equities, allocations, and unrealized returns."
      refreshing={query.isRefetching}
      onRefresh={() => void query.refetch()}
    >
      <View style={s.between}>
        <Text style={s.label}>
          {query.data?.holdings.length || 0} EQUITY HOLDINGS
        </Text>
        <Pressable
          disabled={!selected}
          accessibilityRole="button"
          accessibilityLabel="Add holding"
          onPress={() => show(null)}
          style={[s.row, s.chip]}
        >
          <Plus size={15} color={colors.green} />
          <Text style={{ color: colors.green, fontSize: 13 }}>Add holding</Text>
        </Pressable>
      </View>
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : selected && query.isPending ? (
        <Loading />
      ) : !query.data?.holdings.length ? (
        <Empty
          title="Make it your portfolio"
          description="Create a portfolio using the selector above, then add an equity with its quantity and average purchase price."
          action={selected ? () => show(null) : undefined}
        />
      ) : (
        <>
          <Badge
            text={
              query.data.data_mode === "synthetic"
                ? "SYNTHETIC DEMONSTRATION PRICES"
                : `HISTORICAL PRICES · ${query.data.as_of}`
            }
            color={colors.muted}
          />
          <View style={[s.card, { padding: 0, overflow: "hidden", gap: 0 }]}>
            {query.data.holdings.map((h, index) => (
              <Pressable
                key={h.id}
                accessibilityRole="button"
                accessibilityLabel={`View ${h.symbol}`}
                onPress={() => show(h)}
                style={({ pressed }) => ({
                  padding: 18,
                  gap: 16,
                  backgroundColor: pressed ? colors.elevated : "transparent",
                  borderTopWidth: index ? 1 : 0,
                  borderTopColor: colors.line,
                })}
              >
                <View style={s.between}>
                  <View style={[s.row, { flex: 1 }]}>
                    <View
                      style={{
                        backgroundColor: `${h.color}1F`,
                        width: 40,
                        height: 40,
                        borderRadius: 12,
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Text
                        style={{
                          color: h.color,
                          fontSize: 14,
                          fontWeight: "600",
                        }}
                      >
                        {h.symbol.slice(0, 2)}
                      </Text>
                    </View>
                    <View style={{ flex: 1, gap: 4 }}>
                      <Text
                        style={{
                          color: colors.text,
                          fontSize: 15,
                          fontWeight: "500",
                        }}
                      >
                        {h.symbol}
                      </Text>
                      <Text style={s.small}>
                        {h.quantity} shares · {h.exchange}
                      </Text>
                    </View>
                  </View>
                  <View style={{ gap: 5, alignItems: "flex-end" }}>
                    <Text style={{ color: colors.text, fontSize: 16 }}>
                      {money(h.value)}
                    </Text>
                    <Change value={h.pnl_pct} />
                  </View>
                </View>
                <View style={s.between}>
                  <Text style={s.small}>Avg. {money(h.average_cost, 2)}</Text>
                  <Text style={s.small}>{pct(h.weight)} of portfolio</Text>
                  <ArrowUpRight size={14} color={colors.faint} />
                </View>
              </Pressable>
            ))}
          </View>
          <Text style={s.small}>
            Holdings are current positions. Editing a quantity or average cost
            does not record a historical transaction.
          </Text>
        </>
      )}
      <Sheet
        title={
          editing
            ? holding
              ? "Edit holding"
              : "Add an equity"
            : holding?.name || "Equity details"
        }
        visible={open}
        close={() => {
          if (!busy) setOpen(false);
        }}
      >
        {!editing && holding ? (
          <>
            <View style={s.between}>
              <View style={{ gap: 6 }}>
                <Badge text={`${holding.symbol} · ${holding.exchange}`} />
                <Text style={{ color: colors.text, fontSize: 34 }}>
                  {money(holding.price, 2)}
                </Text>
              </View>
              <Change value={holding.pnl_pct} />
            </View>
            <Text style={s.small}>
              {selected?.data_mode === "synthetic"
                ? "Synthetic demonstration prices"
                : "Historical closing prices"}{" "}
              · {holding.sector}
            </Text>
            {history.isPending ? (
              <Loading />
            ) : history.error ? (
              <ErrorBox error={history.error} />
            ) : (
              history.data && (
                <LineChart
                  points={history.data.prices.map((p) => p.close)}
                  labels={history.data.prices.map((p) => p.date)}
                  height={150}
                />
              )
            )}
            <View style={s.between}>
              <Text style={s.small}>Your position</Text>
              <Text style={s.body}>{holding.quantity} shares</Text>
            </View>
            <View style={s.between}>
              <Text style={s.small}>Average purchase price</Text>
              <Text style={s.body}>{money(holding.average_cost, 2)}</Text>
            </View>
            <View style={s.between}>
              <Text style={s.small}>Unrealized P&L</Text>
              <Text
                style={{ color: holding.pnl >= 0 ? colors.green : colors.red }}
              >
                {money(holding.pnl, 2)}
              </Text>
            </View>
            <Button
              title="Edit this holding"
              onPress={() => setEditing(true)}
            />
          </>
        ) : (
          <>
            {!holding && (
              <>
                <View style={[s.row, s.input]}>
                  <Search size={18} color={colors.faint} />
                  <TextInput
                    accessibilityLabel="Search equities"
                    placeholder="Search a company or symbol"
                    placeholderTextColor={colors.faint}
                    value={search}
                    onChangeText={setSearch}
                    style={{ color: colors.text, flex: 1, fontSize: 14 }}
                  />
                </View>
                {instruments.isPending ? (
                  <Loading />
                ) : instruments.error ? (
                  <ErrorBox error={instruments.error} />
                ) : (
                  <View style={{ gap: 6 }}>
                    {instruments.data?.slice(0, instrument ? 3 : 8).map((i) => (
                      <Pressable
                        key={i.id}
                        accessibilityRole="button"
                        onPress={() => setInstrument(i)}
                        style={[
                          s.between,
                          {
                            padding: 12,
                            borderRadius: 10,
                            backgroundColor:
                              instrument?.id === i.id
                                ? colors.greenDark
                                : colors.bg,
                          },
                        ]}
                      >
                        <View style={{ flex: 1, gap: 3 }}>
                          <Text style={s.body}>{i.symbol}</Text>
                          <Text style={s.small}>{i.name}</Text>
                        </View>
                        <Text style={s.small}>{i.exchange}</Text>
                      </Pressable>
                    ))}
                    {!instruments.data?.length && (
                      <Text style={s.small}>
                        No matches in the curated equity catalog.
                      </Text>
                    )}
                  </View>
                )}
              </>
            )}
            {instrument && (
              <Badge
                text={`SELECTED · ${instrument.symbol} · ${instrument.exchange}`}
              />
            )}
            <Field
              label="Quantity"
              value={quantity}
              onChangeText={setQuantity}
              numeric
              placeholder="e.g. 10"
            />
            <Field
              label="Average purchase price (₹)"
              value={cost}
              onChangeText={setCost}
              numeric
              placeholder="e.g. 1500.00"
            />
            <ErrorBox error={error} />
            <Button
              title="Save holding"
              onPress={() => void save()}
              busy={busy}
              disabled={!instrument || !quantity || !cost}
            />
            {holding && (
              <Button
                title={confirm ? "Confirm removal" : "Remove this holding"}
                danger
                onPress={() => (confirm ? void save(true) : setConfirm(true))}
                disabled={busy}
              />
            )}
          </>
        )}
      </Sheet>
    </Screen>
  );
}
