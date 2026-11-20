export function normalizeServerUrl(
  input: string,
  allowLocalHttp = true,
): string {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    throw new Error(
      "Enter a complete server address, such as http://192.168.1.10:8000.",
    );
  }
  if (!["https:", "http:"].includes(url.protocol)) {
    throw new Error("Use an HTTP or HTTPS server address.");
  }
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  ) {
    throw new Error(
      "Use only the server address and port, without credentials, a path, or query parameters.",
    );
  }
  const hostname = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  const octets = hostname.split(".").map(Number);
  const ipv4 =
    octets.length === 4 &&
    octets.every((n) => Number.isInteger(n) && n >= 0 && n <= 255);
  const privateV4 =
    ipv4 &&
    (octets[0] === 10 ||
      octets[0] === 127 ||
      (octets[0] === 192 && octets[1] === 168) ||
      (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) ||
      (octets[0] === 169 && octets[1] === 254));
  const local =
    hostname === "localhost" ||
    hostname.endsWith(".local") ||
    privateV4 ||
    hostname === "::1" ||
    /^(fc|fd)[0-9a-f]{2}:|^fe[89ab][0-9a-f]:/i.test(hostname);
  if (url.protocol === "http:" && (!allowLocalHttp || !local)) {
    throw new Error(
      allowLocalHttp
        ? "Use HTTPS for a hosted server. HTTP is supported only for local network addresses."
        : "This production build requires an HTTPS server.",
    );
  }
  return url.origin;
}

export async function probeServer(address: string, allowLocalHttp = true) {
  const url = normalizeServerUrl(address, allowLocalHttp);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    // A probe never includes account credentials, including when checking a different server.
    const response = await fetch(`${url}/health`, {
      signal: controller.signal,
      credentials: "omit",
    });
    if (!response.ok)
      throw new Error(`The server returned HTTP ${response.status}.`);
    const data = await response.json();
    if (data.service !== "quantlens" || data.status !== "ok") {
      throw new Error(
        "This address did not identify itself as a ready QuantLens server.",
      );
    }
    return { url, version: String(data.version || "unknown") };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(
        "Connection timed out. Check the address and Wi-Fi connection.",
      );
    }
    if (error instanceof TypeError) {
      throw new Error(
        "Cannot connect. Start the backend and connect your phone to the same Wi-Fi.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
