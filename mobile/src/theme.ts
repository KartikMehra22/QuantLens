import { StyleSheet } from "react-native";

export const colors = {
  bg: "#0C1312",
  card: "#141E1C",
  elevated: "#1B2825",
  line: "#293731",
  text: "#F0F4EB",
  muted: "#9BAAA1",
  faint: "#708078",
  green: "#B9ED9E",
  greenDark: "#20382A",
  red: "#F2A6A0",
  amber: "#E8C795",
  blue: "#A8B8FF",
};
export const s = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  between: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  title: {
    color: colors.text,
    fontSize: 30,
    fontWeight: "600",
    letterSpacing: -1.2,
  },
  subtitle: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  label: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  body: { color: colors.text, fontSize: 14, lineHeight: 21 },
  small: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: colors.line,
    gap: 15,
  },
  divider: { height: 1, backgroundColor: colors.line },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 12,
    backgroundColor: colors.bg,
    paddingHorizontal: 15,
    paddingVertical: 14,
    color: colors.text,
    fontSize: 15,
    minHeight: 50,
  },
  chip: {
    backgroundColor: colors.elevated,
    paddingVertical: 7,
    paddingHorizontal: 11,
    borderRadius: 8,
  },
});
export const money = (n: number, decimals = 0) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(n);
export const pct = (n: number | null | undefined, signed = false) =>
  n == null ? "—" : `${signed && n > 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
export const shortDate = (date: string | null) =>
  date
    ? new Date(`${date}T12:00:00`).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "No prices yet";
export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
