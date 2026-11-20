import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";
import { normalizeServerUrl, probeServer } from "../src/services/server-url.ts";

test("normalizes local preview and hosted origins", () => {
  assert.equal(
    normalizeServerUrl(" http://192.168.1.20:8000/ "),
    "http://192.168.1.20:8000",
  );
  assert.equal(
    normalizeServerUrl("http://10.0.2.2:8000"),
    "http://10.0.2.2:8000",
  );
  assert.equal(
    normalizeServerUrl("https://api.example.com/"),
    "https://api.example.com",
  );
  assert.equal(normalizeServerUrl("http://[::1]:8000"), "http://[::1]:8000");
});

test("rejects public cleartext, disguised LAN addresses, credentials and URL payloads", () => {
  for (const url of [
    "http://api.example.com",
    "http://192.168.1.2.example.com",
    "http://172.32.0.1",
    "https://user:password@example.com",
    "https://example.com/?token=secret",
    "https://example.com/path",
    "https://example.com/#token",
    "javascript:alert(1)",
    "not a url",
  ]) {
    assert.throws(() => normalizeServerUrl(url), Error, url);
  }
  assert.throws(
    () => normalizeServerUrl("http://192.168.1.2:8000", false),
    /HTTPS/,
  );
});

test("connection probes identify QuantLens and do not send credentials", async () => {
  const server = createServer((request, response) => {
    assert.equal(request.url, "/health");
    assert.equal(request.headers.authorization, undefined);
    assert.equal(request.headers.cookie, undefined);
    response.setHeader("Content-Type", "application/json");
    response.end(
      JSON.stringify({ status: "ok", service: "quantlens", version: "0.1.0" }),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = `http://127.0.0.1:${server.address().port}`;
    assert.deepEqual(await probeServer(address), {
      url: address,
      version: "0.1.0",
    });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("rejects a healthy service which is not QuantLens", async () => {
  const server = createServer((_, response) => {
    response.setHeader("Content-Type", "application/json");
    response.end(JSON.stringify({ status: "ok", service: "another-app" }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    await assert.rejects(
      () => probeServer(`http://127.0.0.1:${server.address().port}`),
      /QuantLens/,
    );
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
