const base = require("./app.json").expo;

module.exports = () => {
  const variant = process.env.APP_VARIANT || "production";
  if (!["development", "preview", "production"].includes(variant))
    throw new Error("Unknown APP_VARIANT.");
  if (
    process.env.EXPO_PUBLIC_APP_VARIANT &&
    process.env.EXPO_PUBLIC_APP_VARIANT !== variant
  ) {
    throw new Error("APP_VARIANT and EXPO_PUBLIC_APP_VARIANT must match.");
  }
  if (
    variant === "production" &&
    process.env.EXPO_PUBLIC_API_URL &&
    !process.env.EXPO_PUBLIC_API_URL.startsWith("https://")
  ) {
    throw new Error("Production builds require an HTTPS API URL.");
  }
  const suffix = variant === "production" ? "" : `.${variant}`;
  return {
    ...base,
    name:
      variant === "production"
        ? "QuantLens"
        : `QuantLens ${variant === "preview" ? "Preview" : "Dev"}`,
    ios: {
      ...base.ios,
      bundleIdentifier: `${base.ios.bundleIdentifier}${suffix}`,
    },
    android: { ...base.android, package: `${base.android.package}${suffix}` },
    plugins: [
      ...base.plugins,
      ["./plugins/with-local-network", { enabled: variant !== "production" }],
    ],
  };
};
