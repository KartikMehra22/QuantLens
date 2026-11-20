const { withAndroidManifest, withInfoPlist } = require("expo/config-plugins");

module.exports = (config, { enabled = false } = {}) => {
  config = withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application?.[0];
    if (!application)
      throw new Error("Android application manifest was not generated.");
    application.$["android:usesCleartextTraffic"] = enabled ? "true" : "false";
    return config;
  });
  return withInfoPlist(config, (config) => {
    config.modResults.NSAppTransportSecurity = enabled
      ? { NSAllowsArbitraryLoads: true, NSAllowsLocalNetworking: true }
      : { NSAllowsArbitraryLoads: false };
    if (enabled)
      config.modResults.NSLocalNetworkUsageDescription =
        "Connect to your QuantLens backend on the same Wi-Fi network.";
    else delete config.modResults.NSLocalNetworkUsageDescription;
    return config;
  });
};
