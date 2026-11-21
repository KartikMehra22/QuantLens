import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

export type Credentials = {
  access_token: string;
  refresh_token?: string;
  user_id?: string;
};
const KEY = "quantlens-token";
const readRaw = async () =>
  Platform.OS === "web"
    ? sessionStorage.getItem(KEY)
    : SecureStore.getItemAsync(KEY);
const write = async (value: string) => {
  if (Platform.OS === "web") sessionStorage.setItem(KEY, value);
  else await SecureStore.setItemAsync(KEY, value);
};
async function read(): Promise<Credentials | null> {
  const raw = await readRaw();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed.access_token === "string" ? parsed : null;
  } catch {
    return { access_token: raw };
  } // Existing v0.1 sessions remain usable until expiry.
}
export const tokenStorage = {
  read,
  get: async () => (await read())?.access_token || null,
  set: async (access_token: string) => write(JSON.stringify({ access_token })),
  save: async (
    access_token: string,
    refresh_token?: string,
    user_id?: string,
  ) => write(JSON.stringify({ access_token, refresh_token, user_id })),
  clear: async () => {
    if (Platform.OS === "web") sessionStorage.removeItem(KEY);
    else await SecureStore.deleteItemAsync(KEY);
  },
};
