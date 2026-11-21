import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";
import { createAuthorizedRequester } from "../src/services/http-client.ts";

async function serve(handler, run) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    await run(`http://127.0.0.1:${server.address().port}`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

test("concurrent expired requests rotate once and retry using the new access token", async () => {
  let refreshes = 0;
  await serve(
    (request, response) => {
      response.setHeader("Content-Type", "application/json");
      if (request.url === "/api/v1/auth/refresh") {
        refreshes += 1;
        setTimeout(
          () =>
            response.end(
              JSON.stringify({
                access_token: "fresh",
                refresh_token: "rotated",
              }),
            ),
          20,
        );
      } else if (request.headers.authorization === "Bearer fresh")
        response.end('{"ok":true}');
      else {
        response.statusCode = 401;
        response.end("{}");
      }
    },
    async (base) => {
      let credentials = {
        access_token: "expired",
        refresh_token: "original",
        user_id: "user-a",
      };
      const client = createAuthorizedRequester({
        read: async () => credentials,
        save: async (value) => {
          credentials = value;
        },
        clear: async () => {
          credentials = null;
        },
        currentServer: async () => base,
        expired: () => assert.fail("Unexpected logout"),
      });
      const results = await Promise.all(
        Array.from({ length: 8 }, () => client(base, "/api/v1/portfolios")),
      );
      assert.ok(results.every((response) => response.ok));
      assert.equal(refreshes, 1);
      assert.equal(credentials.refresh_token, "rotated");
    },
  );
});

test("failed renewal clears the expired session exactly once for a request", async () => {
  await serve(
    (_, response) => {
      response.statusCode = 401;
      response.end("{}");
    },
    async (base) => {
      let credentials = {
        access_token: "expired",
        refresh_token: "revoked",
        user_id: "user-a",
      };
      let expired = 0;
      const client = createAuthorizedRequester({
        read: async () => credentials,
        save: async () => assert.fail(),
        clear: async () => {
          credentials = null;
        },
        currentServer: async () => base,
        expired: () => {
          expired += 1;
        },
      });
      assert.equal((await client(base, "/api/v1/portfolios")).status, 401);
      assert.equal(credentials, null);
      assert.equal(expired, 1);
    },
  );
});

test("a response from the previous server cannot overwrite a newly signed-in account", async () => {
  let currentServer;
  let credentials = {
    access_token: "expired",
    refresh_token: "original",
    user_id: "user-a",
  };
  await serve(
    (request, response) => {
      response.setHeader("Content-Type", "application/json");
      if (request.url.endsWith("/refresh")) {
        currentServer = "https://new-server.example";
        credentials = {
          access_token: "new-account-token",
          refresh_token: "new-account-refresh",
          user_id: "user-b",
        };
        response.end(
          JSON.stringify({
            access_token: "old-server-token",
            refresh_token: "old-server-refresh",
          }),
        );
      } else {
        response.statusCode = 401;
        response.end("{}");
      }
    },
    async (base) => {
      currentServer = base;
      const client = createAuthorizedRequester({
        read: async () => credentials,
        save: async () => assert.fail("Overwrote a new account"),
        clear: async () => assert.fail("Cleared a new account"),
        currentServer: async () => currentServer,
        expired: () => assert.fail(),
      });
      assert.equal((await client(base, "/api/v1/portfolios")).status, 401);
      assert.equal(credentials.access_token, "new-account-token");
    },
  );
});
