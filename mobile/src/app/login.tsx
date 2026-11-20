import { Redirect } from "expo-router";
import { ArrowUpRight, ScanLine, ShieldCheck } from "lucide-react-native";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LineChart } from "../components/charts";
import { ServerSettings } from "../components/server-settings";
import { Badge, Button, ErrorBox, Field, Loading } from "../components/ui";
import { useSession } from "../providers";
import { api } from "../services/api";
import { colors, s } from "../theme";
import { AuthResponse } from "../types";

const illustration = Array.from(
  { length: 65 },
  (_, i) => 100 + i * 0.6 + Math.sin(i * 0.45) * 3 + Math.cos(i * 0.15) * 5,
);
export default function Login() {
  const { user, ready, accept } = useSession();
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  if (!ready) return <Loading />;
  if (user) return <Redirect href="/" />;
  const submit = async (demo = false) => {
    setError(null);
    setBusy(demo ? "demo" : "auth");
    try {
      await accept(
        await api<AuthResponse>(
          demo ? "/auth/demo" : register ? "/auth/register" : "/auth/login",
          "POST",
          demo
            ? undefined
            : {
                email: email.trim(),
                password,
                ...(register ? { name: name.trim() } : {}),
              },
        ),
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{
            padding: 28,
            gap: 30,
            maxWidth: 480,
            width: "100%",
            alignSelf: "center",
            paddingTop: 35,
          }}
        >
          <View style={s.row}>
            <ScanLine color={colors.green} size={28} />
            <Text
              style={{
                color: colors.text,
                fontWeight: "600",
                fontSize: 24,
                letterSpacing: -1,
              }}
            >
              QuantLens.
            </Text>
          </View>
          <View style={{ gap: 18 }}>
            <Badge text="A CLEARER VIEW OF YOUR INVESTMENTS" />
            <Text
              style={{
                color: colors.text,
                fontSize: 42,
                fontWeight: "500",
                lineHeight: 47,
                letterSpacing: -2,
              }}
            >
              Your portfolio.{`\n`}More perspective.
            </Text>
            <Text style={s.subtitle}>
              See the returns. Understand the risk.{`\n`}Explore what comes
              next.
            </Text>
          </View>
          <View
            style={[
              s.card,
              { padding: 16, gap: 6, backgroundColor: "#17271F" },
            ]}
          >
            <View style={s.between}>
              <Text style={s.label}>ONE PORTFOLIO. EVERY ANGLE.</Text>
              <ArrowUpRight size={19} color={colors.green} />
            </View>
            <LineChart
              points={illustration}
              height={80}
              labels={["ILLUSTRATIVE CHART", "NOT MARKET DATA"]}
            />
          </View>
          <ServerSettings />
          <View style={{ gap: 16 }}>
            <Text
              style={{ color: colors.text, fontSize: 21, fontWeight: "500" }}
            >
              {register ? "Create your account" : "Welcome to QuantLens"}
            </Text>
            {register && (
              <Field
                label="Your name"
                value={name}
                onChangeText={setName}
                placeholder="How should we call you?"
              />
            )}
            <Field
              label="Email address"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
            />
            <Field
              label="Password"
              value={password}
              onChangeText={setPassword}
              secure
              placeholder={register ? "At least 8 characters" : "Your password"}
            />
            <ErrorBox error={error} />
            <Button
              title={register ? "Create account" : "Sign in"}
              onPress={() => void submit()}
              busy={busy === "auth"}
              disabled={
                !!busy || !email || !password || (register && !name.trim())
              }
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setRegister(!register);
                setError(null);
              }}
              style={{ padding: 8 }}
            >
              <Text style={[s.small, { textAlign: "center" }]}>
                {register ? "Already have an account? " : "New here? "}
                <Text style={{ color: colors.green }}>
                  {register ? "Sign in" : "Create an account"}
                </Text>
              </Text>
            </Pressable>
            <View style={s.divider} />
            <Button
              title="Explore the demo"
              secondary
              onPress={() => void submit(true)}
              busy={busy === "demo"}
              disabled={!!busy}
            />
            <Text style={[s.small, { textAlign: "center" }]}>
              A personal sandbox with synthetic prices.{`\n`}No real money or
              market observations.
            </Text>
          </View>
          <View style={[s.row, { justifyContent: "center" }]}>
            <ShieldCheck size={14} color={colors.faint} />
            <Text style={[s.small, { color: colors.faint }]}>
              Educational analytics · No trade execution
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
