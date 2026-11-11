import Constants from "expo-constants";
import { Platform } from "react-native";
import { tokenStorage } from "./session";

const host =
  Platform.OS === "web" && typeof window !== "undefined"
    ? window.location.hostname
    : Constants.expoConfig?.hostUri?.split(":")[0] || "localhost";
export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL || `http://${host}:8000`
).replace(/\/$/, "");
let unauthorized: (() => void) | null = null;
export const setUnauthorized = (callback: (() => void) | null) => {
  unauthorized = callback;
};

export async function request(path: string, options: RequestInit = {}) {
  const token = await tokenStorage.get();
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    path.includes("data-refreshes") ? 150000 : 45000,
  );
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      if (response.status === 401 && token) unauthorized?.();
      const detail =
        typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg;
      throw new Error(detail || `Request failed (${response.status}).`);
    }
    return response;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error("The request timed out. Please retry.");
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach QuantLens. Check that the backend is running and your phone is on the same Wi-Fi.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await request(`/api/v1${path}`, {
    method,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function exportReport(portfolioId: string, format: "csv" | "pdf") {
  const response = await request(
    `/api/v1/portfolios/${portfolioId}/export.${format}`,
  );
  if (Platform.OS === "web") {
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `quantlens-report.${format}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } else {
    const { File, Paths } = await import("expo-file-system");
    const Sharing = await import("expo-sharing");
    if (!(await Sharing.isAvailableAsync()))
      throw new Error("File sharing is unavailable on this device.");
    const file = new File(Paths.cache, `quantlens-${Date.now()}.${format}`);
    file.create();
    await file.write(new Uint8Array(await response.arrayBuffer()));
    await Sharing.shareAsync(file.uri, {
      mimeType: format === "pdf" ? "application/pdf" : "text/csv",
    });
  }
}
