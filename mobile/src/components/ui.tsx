import { router } from "expo-router";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ChevronDown,
  ScanLine,
  X,
} from "lucide-react-native";
import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolios, useSession } from "../providers";
import { api } from "../services/api";
import { colors, errorMessage, pct, s } from "../theme";
import { Portfolio } from "../types";

export function Button({
  title,
  onPress,
  secondary = false,
  busy = false,
  danger = false,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  busy?: boolean;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      disabled={busy || disabled}
      onPress={onPress}
      style={({ pressed }) => [
        {
          paddingHorizontal: 18,
          paddingVertical: 14,
          minHeight: 48,
          borderRadius: 12,
          backgroundColor: danger
            ? "#432823"
            : secondary
              ? colors.elevated
              : colors.green,
          opacity: pressed || busy || disabled ? 0.65 : 1,
          alignItems: "center",
          justifyContent: "center",
        },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={secondary ? colors.green : colors.bg} />
      ) : (
        <Text
          style={{
            color: danger ? colors.red : secondary ? colors.text : colors.bg,
            fontSize: 14,
            fontWeight: "600",
          }}
        >
          {title}
        </Text>
      )}
    </Pressable>
  );
}
export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  numeric,
  secure,
  multiline,
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  numeric?: boolean;
  secure?: boolean;
  multiline?: boolean;
}) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={s.small}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        style={[
          s.input,
          multiline && { minHeight: 150, textAlignVertical: "top" },
        ]}
        placeholderTextColor={colors.faint}
        placeholder={placeholder}
        value={value}
        onChangeText={onChangeText}
        keyboardType={
          numeric
            ? "decimal-pad"
            : label.toLowerCase().includes("email")
              ? "email-address"
              : "default"
        }
        autoCapitalize={
          label.toLowerCase().includes("email") ? "none" : "sentences"
        }
        secureTextEntry={secure}
        multiline={multiline}
      />
    </View>
  );
}
export function Sheet({
  title,
  visible,
  close,
  children,
}: React.PropsWithChildren<{
  title: string;
  visible: boolean;
  close: () => void;
}>) {
  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={close}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={ui.overlay}
      >
        <View style={ui.sheet}>
          <View style={s.between}>
            <Text
              style={{ color: colors.text, fontSize: 21, fontWeight: "600" }}
            >
              {title}
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Close dialog"
              onPress={close}
              style={{ padding: 8 }}
            >
              <X color={colors.muted} size={21} />
            </Pressable>
          </View>
          <ScrollView
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ gap: 18, paddingBottom: 6 }}
          >
            {children}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <View
      accessibilityRole="alert"
      style={{ padding: 14, borderRadius: 12, backgroundColor: "#34211E" }}
    >
      <Text style={{ color: colors.red, lineHeight: 21 }}>
        {errorMessage(error)}
      </Text>
    </View>
  ) : null;
}
export function Badge({
  text,
  color = colors.green,
}: {
  text: string;
  color?: string;
}) {
  return (
    <View
      style={{
        alignSelf: "flex-start",
        borderRadius: 6,
        backgroundColor: colors.elevated,
        paddingHorizontal: 9,
        paddingVertical: 5,
      }}
    >
      <Text
        style={{ fontSize: 10, color, fontWeight: "600", letterSpacing: 0.8 }}
      >
        {text}
      </Text>
    </View>
  );
}
export function Change({ value }: { value: number }) {
  const color = value >= 0 ? colors.green : colors.red;
  const Icon = value >= 0 ? ArrowUpRight : ArrowDownLeft;
  return (
    <View style={s.row}>
      <Icon size={14} color={color} />
      <Text style={{ color, fontSize: 13, fontWeight: "500" }}>
        {pct(value, true)}
      </Text>
    </View>
  );
}
export function SectionTitle({
  title,
  caption,
}: {
  title: string;
  caption?: string;
}) {
  return (
    <View style={{ gap: 5 }}>
      <Text style={{ color: colors.text, fontSize: 17, fontWeight: "500" }}>
        {title}
      </Text>
      {caption && <Text style={s.small}>{caption}</Text>}
    </View>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: () => void;
}) {
  return (
    <View style={[s.card, { alignItems: "center", paddingVertical: 42 }]}>
      <ScanLine size={34} color={colors.green} />
      <Text style={{ color: colors.text, fontSize: 19 }}>{title}</Text>
      <Text style={[s.subtitle, { textAlign: "center", maxWidth: 360 }]}>
        {description}
      </Text>
      {action && <Button title="Add your first holding" onPress={action} />}
    </View>
  );
}

function PortfolioPicker() {
  const { portfolios, selected, select } = usePortfolios();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const p = await api<Portfolio>("/portfolios", "POST", {
        name: name.trim(),
      });
      await client.invalidateQueries({ queryKey: ["portfolios"] });
      select(p.id);
      setName("");
      setOpen(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={
          selected ? "Choose portfolio" : "Create a portfolio"
        }
        onPress={() => setOpen(true)}
        style={[
          s.row,
          !selected && s.chip,
          {
            alignSelf: "flex-start",
            paddingVertical: 12,
            marginBottom: selected ? 0 : 10,
          },
        ]}
      >
        <Text
          style={{
            color: selected ? colors.muted : colors.green,
            fontSize: 13,
          }}
        >
          {selected?.name || "Create a portfolio"}
        </Text>
        <ChevronDown color={colors.muted} size={14} />
      </Pressable>
      <Sheet
        title="Your portfolios"
        visible={open}
        close={() => setOpen(false)}
      >
        {portfolios.map((p) => (
          <Pressable
            key={p.id}
            onPress={() => {
              select(p.id);
              setOpen(false);
            }}
            accessibilityRole="button"
            style={[
              s.card,
              {
                backgroundColor:
                  p.id === selected?.id ? colors.greenDark : colors.card,
                padding: 15,
              },
            ]}
          >
            <Text style={s.body}>{p.name}</Text>
            <Text style={s.small}>
              {p.data_mode === "synthetic"
                ? "Synthetic demo data"
                : p.data_mode === "csv"
                  ? "Imported historical data"
                  : "Yahoo historical data"}
            </Text>
          </Pressable>
        ))}
        <Field
          label="New portfolio name"
          value={name}
          onChangeText={setName}
          placeholder="e.g. Long-term investments"
        />
        <Text style={s.small}>
          New portfolios start with labelled synthetic data. You can download
          historical prices from Profile.
        </Text>
        <ErrorBox error={error} />
        <Button
          title="Create portfolio"
          onPress={() => void create()}
          busy={busy}
          disabled={!name.trim()}
        />
      </Sheet>
    </>
  );
}

export function Screen({
  title,
  description,
  children,
  refreshing = false,
  onRefresh,
}: React.PropsWithChildren<{
  title: string;
  description: string;
  refreshing?: boolean;
  onRefresh?: () => void;
}>) {
  const { user } = useSession();
  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={{ flex: 1, backgroundColor: colors.bg }}
    >
      <ScrollView
        contentContainerStyle={ui.page}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          onRefresh ? (
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.green}
            />
          ) : undefined
        }
      >
        <View
          style={[
            s.between,
            {
              paddingBottom: 12,
              borderBottomWidth: 1,
              borderBottomColor: colors.line,
            },
          ]}
        >
          <View style={s.row}>
            <View style={ui.brandIcon}>
              <ScanLine size={19} color={colors.bg} />
            </View>
            <Text
              style={{
                color: colors.text,
                fontSize: 19,
                letterSpacing: -0.6,
                fontWeight: "600",
              }}
            >
              QuantLens<Text style={{ color: colors.green }}>.</Text>
            </Text>
          </View>
          <Pressable
            accessibilityLabel="Open profile"
            accessibilityRole="button"
            onPress={() => router.push("/profile")}
            style={ui.avatar}
          >
            <Text style={{ color: colors.green, fontWeight: "600" }}>
              {user?.name.slice(0, 1).toUpperCase()}
            </Text>
          </Pressable>
        </View>
        <View>
          <PortfolioPicker />
          <View style={{ gap: 7 }}>
            <Text style={s.title}>{title}</Text>
            <Text style={s.subtitle}>{description}</Text>
          </View>
        </View>
        {children}
        <Text
          style={[
            s.small,
            { textAlign: "center", paddingTop: 10, color: colors.faint },
          ]}
        >
          QUANTLENS · UNDERSTAND WHAT YOU HOLD
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
export function Loading() {
  return (
    <View style={{ padding: 60 }}>
      <ActivityIndicator color={colors.green} />
    </View>
  );
}
export const ui = StyleSheet.create({
  page: {
    padding: 22,
    gap: 25,
    width: "100%",
    maxWidth: 1080,
    alignSelf: "center",
    paddingBottom: 35,
  },
  overlay: {
    flex: 1,
    backgroundColor: "#000000B8",
    justifyContent: "center",
    padding: 20,
  },
  sheet: {
    width: "100%",
    maxWidth: 500,
    maxHeight: "90%",
    alignSelf: "center",
    borderRadius: 22,
    backgroundColor: colors.card,
    padding: 22,
    gap: 22,
    borderColor: colors.line,
    borderWidth: 1,
  },
  brandIcon: {
    backgroundColor: colors.green,
    width: 32,
    height: 32,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.greenDark,
    alignItems: "center",
    justifyContent: "center",
  },
});
