import { Platform } from "react-native";
import { tokenStorage } from "./session";
import { createAuthorizedRequester } from "./http-client";
import { getServerUrl } from "./connection";
import { isRenderServer } from "./server-url";

let unauthorized: (() => void) | null = null;
export const setUnauthorized = (callback: (() => void) | null) => {
  unauthorized = callback;
};

const authorizedRequest = createAuthorizedRequester({
  read: tokenStorage.read,
  save: (value) =>
    tokenStorage.save(value.access_token, value.refresh_token, value.user_id),
  clear: tokenStorage.clear,
  currentServer: getServerUrl,
  expired: () => unauthorized?.(),
});

export async function request(path: string, options: RequestInit = {}) {
  const baseUrl = await getServerUrl();
  if (!baseUrl)
    throw new Error(
      "Open Server connection and save a server address to continue.",
    );
  const hostedOnRender = isRenderServer(baseUrl);
  const controller = new AbortController();
  const timeout = path.includes("data-refreshes") ? 150000 : 45000;
  const timer = setTimeout(
    () => controller.abort(),
    hostedOnRender ? timeout + 75000 : timeout,
  );
  try {
    const response = await authorizedRequest(baseUrl, path, {
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail =
        typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg;
      throw new Error(detail || `Request failed (${response.status}).`);
    }
    return response;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error(
        hostedOnRender
          ? "The server is taking longer than usual to respond. Please retry."
          : "The request timed out. Please retry.",
      );
    if (error instanceof TypeError)
      throw new Error(
        baseUrl.startsWith("https:")
          ? "Cannot reach QuantLens. Check your internet connection and server address."
          : "Cannot reach QuantLens. Check that the backend is running and your phone is on the same Wi-Fi.",
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
  await shareDownload(
    response,
    `quantlens-report.${format}`,
    format === "pdf" ? "application/pdf" : "text/csv",
  );
}

export async function exportEvaluation(
  portfolioId: string,
  evaluationId: string,
) {
  const response = await request(
    `/api/v1/portfolios/${portfolioId}/evaluations/${evaluationId}/export.json`,
  );
  await shareDownload(
    response,
    "quantlens-evaluation.json",
    "application/json",
  );
}

async function shareDownload(
  response: Response,
  filename: string,
  mimeType: string,
) {
  if (Platform.OS === "web") {
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } else {
    const { File, Paths } = await import("expo-file-system");
    const Sharing = await import("expo-sharing");
    if (!(await Sharing.isAvailableAsync()))
      throw new Error("File sharing is unavailable on this device.");
    const file = new File(Paths.cache, `${Date.now()}-${filename}`);
    file.create();
    await file.write(new Uint8Array(await response.arrayBuffer()));
    await Sharing.shareAsync(file.uri, { mimeType });
  }
}
