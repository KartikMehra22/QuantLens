import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { api } from "../services/api";
import { colors, s } from "../theme";
import { Button, ErrorBox, Field, Sheet } from "./ui";

export function RecoverySheet() {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<"request" | "confirm" | "done">("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const request = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/request", "POST", {
        email: email.trim(),
      });
      setPhase("confirm");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/confirm", "POST", {
        email: email.trim(),
        code,
        password,
      });
      setPassword("");
      setCode("");
      setPhase("done");
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
        onPress={() => {
          setOpen(true);
          setPhase("request");
          setError(null);
        }}
        style={{ paddingVertical: 8 }}
      >
        <Text style={{ color: colors.green, fontSize: 13, textAlign: "right" }}>
          Forgot password?
        </Text>
      </Pressable>
      <Sheet
        title="Recover your account"
        visible={open}
        close={() => {
          if (!busy) setOpen(false);
        }}
      >
        {phase === "done" ? (
          <>
            <Text style={s.body}>
              Your password has been updated. Sign in with the new password.
              Previous sessions have been signed out.
            </Text>
            <Button title="Back to sign in" onPress={() => setOpen(false)} />
          </>
        ) : (
          <>
            <Text style={s.subtitle}>
              {phase === "request"
                ? "Enter your account email to request an eight-digit reset code."
                : "If your account exists, a reset code has been sent. Enter it within ten minutes. For a classroom demo, the operator can provide the local demo email."}
            </Text>
            <Field
              label="Account email"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
            />
            {phase === "confirm" && (
              <View style={{ gap: 16 }}>
                <Field
                  label="Eight digit reset code"
                  value={code}
                  onChangeText={setCode}
                  numeric
                  placeholder="00000000"
                />
                <Field
                  label="New password"
                  value={password}
                  onChangeText={setPassword}
                  secure
                  placeholder="At least 8 characters"
                />
              </View>
            )}
            <ErrorBox error={error} />
            <Button
              title={
                phase === "request" ? "Send reset code" : "Set new password"
              }
              busy={busy}
              disabled={
                !email.trim() ||
                (phase === "confirm" &&
                  (!/^\d{8}$/.test(code) || password.length < 8))
              }
              onPress={() => void (phase === "request" ? request() : confirm())}
            />
            {phase === "confirm" && (
              <Button
                title="Request a new code"
                secondary
                disabled={busy}
                onPress={() => void request()}
              />
            )}
          </>
        )}
      </Sheet>
    </>
  );
}
