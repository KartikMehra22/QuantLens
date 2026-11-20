import { Server } from "lucide-react-native";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { useSession } from "../providers";
import { allowLocalHttp, getServerUrl } from "../services/connection";
import { probeServer } from "../services/server-url";
import { colors, s } from "../theme";
import { Badge, Button, ErrorBox, Sheet } from "./ui";

export function ServerSettings() {
  const { changeServer, user } = useSession();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [verified, setVerified] = useState<{
    url: string;
    version: string;
  } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const show = async () => {
    setOpen(true);
    setError(null);
    setVerified(null);
    try {
      setUrl((await getServerUrl()) || "");
    } catch (e) {
      setError(e);
    }
  };
  const check = async () => {
    setBusy(true);
    setError(null);
    setVerified(null);
    try {
      const result = await probeServer(url, allowLocalHttp);
      setUrl(result.url);
      setVerified(result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    if (!verified) return;
    setBusy(true);
    setError(null);
    try {
      await changeServer(verified.url);
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
        accessibilityLabel="Server connection"
        onPress={() => void show()}
        style={[s.row, { paddingVertical: 12, justifyContent: "center" }]}
      >
        <Server color={colors.muted} size={16} />
        <Text style={s.small}>Server connection</Text>
      </Pressable>
      <Sheet
        title="Connect to QuantLens"
        visible={open}
        close={() => {
          if (!busy) setOpen(false);
        }}
      >
        <Text style={s.subtitle}>
          Enter the address of your QuantLens server. For a laptop on the same
          Wi-Fi, use its local IP address and port 8000.
        </Text>
        <Text style={s.small}>Server address</Text>
        <TextInput
          accessibilityLabel="Server address"
          value={url}
          placeholder="http://192.168.1.10:8000"
          placeholderTextColor={colors.faint}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          editable={!busy}
          onChangeText={(value) => {
            setUrl(value);
            setVerified(null);
            setError(null);
          }}
          style={s.input}
        />
        <ErrorBox error={error} />
        {verified && (
          <Badge text={`CONNECTED · QUANTLENS ${verified.version}`} />
        )}
        <Button
          title="Test connection"
          secondary
          onPress={() => void check()}
          busy={busy}
          disabled={!url.trim()}
        />
        <Button
          title="Save connection"
          onPress={() => void save()}
          disabled={!verified || busy}
        />
        <View style={{ gap: 8 }}>
          {user && (
            <Text style={s.small}>
              Changing servers signs you out of the current account. Your
              portfolios remain on their original server.
            </Text>
          )}
          <Text style={s.small}>
            {allowLocalHttp
              ? "Use HTTPS for hosted servers. Local HTTP is available in this preview."
              : "This production build connects over HTTPS."}
          </Text>
        </View>
      </Sheet>
    </>
  );
}
