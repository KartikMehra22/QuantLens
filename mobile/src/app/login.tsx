import { Redirect } from "expo-router";
import { ArrowDownRight, ScanLine } from "lucide-react-native";
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
import { RecoverySheet } from "../components/recovery-sheet";
import { ServerSettings } from "../components/server-settings";
import { Button, ErrorBox, Field, Loading, Sheet } from "../components/ui";
import { useSession } from "../providers";
import { api } from "../services/api";
import { colors, s } from "../theme";
import { AuthResponse } from "../types";

export default function Login() {
  const { user, ready, accept } = useSession();
  const [mode, setMode] = useState<"welcome" | "signin" | "register">(
    "welcome",
  );
  const [exampleOpen, setExampleOpen] = useState(false);
  const register = mode === "register";
  const changeMode = (next: typeof mode) => {
    setMode(next);
    setError(null);
  };
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
          {mode === "welcome" ? (
            <>
              <View style={{ gap: 12 }}>
                <Text
                  accessibilityRole="header"
                  style={[s.title, { fontSize: 36 }]}
                >
                  Track Indian stocks. Understand your risk.
                </Text>
                <Text style={s.subtitle}>
                  Build a practice portfolio, see what it’s worth, and find out
                  how a market drop could affect it.
                </Text>
              </View>
              <View style={{ gap: 10 }}>
                <Button
                  title="Try a sample portfolio"
                  onPress={() => void submit(true)}
                  busy={busy === "demo"}
                />
                <ErrorBox error={error} />
                <Text style={s.small}>No sign-up. Uses simulated prices.</Text>
                <Button
                  title="Create an account"
                  secondary
                  onPress={() => changeMode("register")}
                  disabled={!!busy}
                />
                <Button
                  title="Sign in"
                  secondary
                  onPress={() => changeMode("signin")}
                  disabled={!!busy}
                />
              </View>
              <Pressable
                accessibilityRole="button"
                onPress={() => setExampleOpen(true)}
                style={({ pressed }) => [
                  s.card,
                  {
                    backgroundColor: colors.greenDark,
                    opacity: pressed ? 0.8 : 1,
                  },
                ]}
              >
                <View style={s.row}>
                  <ArrowDownRight size={20} color={colors.green} />
                  <Text style={[s.body, { flex: 1, fontWeight: "600" }]}>
                    What if the market fell 20%?
                  </Text>
                </View>
                <Text style={s.subtitle}>
                  See a simple example without connecting to a server.
                </Text>
                <Text style={[s.body, { color: colors.green }]}>
                  View example
                </Text>
              </Pressable>
            </>
          ) : (
            <View style={{ gap: 16 }}>
              <Text
                style={{ color: colors.text, fontSize: 21, fontWeight: "500" }}
              >
                {register ? "Create your account" : "Sign in to QuantLens"}
              </Text>
              {register && (
                <Field
                  label="Your name"
                  value={name}
                  onChangeText={setName}
                  placeholder="Your name"
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
                placeholder={
                  register ? "At least 8 characters" : "Your password"
                }
              />
              {!register && <RecoverySheet />}
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
                  changeMode(register ? "signin" : "register");
                }}
                disabled={!!busy}
                style={{ padding: 12 }}
              >
                <Text style={[s.small, { textAlign: "center" }]}>
                  {register ? "Already have an account? " : "New here? "}
                  <Text style={{ color: colors.green }}>
                    {register ? "Sign in" : "Create an account"}
                  </Text>
                </Text>
              </Pressable>
              <Button
                title="Back to welcome"
                secondary
                onPress={() => changeMode("welcome")}
                disabled={!!busy}
              />
            </View>
          )}
          <ServerSettings />
          <Text style={[s.small, { textAlign: "center" }]}>
            For learning with virtual holdings.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
      <Sheet
        title="A sample stress test"
        visible={exampleOpen}
        close={() => setExampleOpen(false)}
      >
        <Text style={s.subtitle}>
          Imagine you hold ₹1,00,000 in stocks and every stock falls by 20%.
        </Text>
        <View style={s.card}>
          <View style={s.between}>
            <Text style={s.body}>Starting value</Text>
            <Text style={s.body}>₹1,00,000</Text>
          </View>
          <View style={s.between}>
            <Text style={s.body}>Estimated loss</Text>
            <Text style={[s.body, { color: colors.red }]}>−₹20,000</Text>
          </View>
          <View style={s.divider} />
          <View style={s.between}>
            <Text style={s.body}>Value after the drop</Text>
            <Text style={[s.body, { color: colors.green }]}>₹80,000</Text>
          </View>
        </View>
        <Text style={s.subtitle}>
          In QuantLens, you can run this scenario on your own practice holdings,
          see which stocks drive the loss, and compare your portfolio with the
          Nifty 50.
        </Text>
        <Button title="Back to welcome" onPress={() => setExampleOpen(false)} />
      </Sheet>
    </SafeAreaView>
  );
}
