import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { normalizeServerUrl } from "./server-url";

const KEY = "quantlens-server-url";
export const allowLocalHttp =
  __DEV__ ||
  ["preview", "development"].includes(
    process.env.EXPO_PUBLIC_APP_VARIANT || "",
  );

function defaultUrl(): string | null {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  if (Platform.OS === "web" && typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  const devHost = Constants.expoConfig?.hostUri?.split(":")[0];
  // A standalone app's localhost is the phone itself; require explicit configuration instead.
  return __DEV__ && devHost ? `http://${devHost}:8000` : null;
}

export async function getServerUrl(): Promise<string | null> {
  const saved =
    Platform.OS === "web"
      ? localStorage.getItem(KEY)
      : await SecureStore.getItemAsync(KEY);
  const candidate = saved || defaultUrl();
  return candidate ? normalizeServerUrl(candidate, allowLocalHttp) : null;
}

export async function saveServerUrl(url: string) {
  const normalized = normalizeServerUrl(url, allowLocalHttp);
  if (Platform.OS === "web") localStorage.setItem(KEY, normalized);
  else await SecureStore.setItemAsync(KEY, normalized);
}
