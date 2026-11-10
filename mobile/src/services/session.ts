import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

// Read the persisted credential for requests so development module reloads cannot
// leave a signed-in React tree with an empty in-memory authorization header.
export const tokenStorage = {
  get: async () =>
    Platform.OS === "web"
      ? sessionStorage.getItem("quantlens-token")
      : SecureStore.getItemAsync("quantlens-token"),
  set: async (value: string) => {
    if (Platform.OS === "web") sessionStorage.setItem("quantlens-token", value);
    else await SecureStore.setItemAsync("quantlens-token", value);
  },
  clear: async () => {
    if (Platform.OS === "web") sessionStorage.removeItem("quantlens-token");
    else await SecureStore.deleteItemAsync("quantlens-token");
  },
};
