// Hermes dashboard tab: wraps the shared Hermie view in a React component
// and routes its calls through the dashboard's authenticated fetch.
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__ || !window.HermieView) return;
  const React = SDK.React;

  async function call(path, body) {
    const init = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined;
    try {
      return await SDK.fetchJSON("/api/plugins/hermie" + path, init);
    } catch (error) {
      // fetchJSON throws Error("<status>: <body>"); surface the server's reason.
      const text = String((error && error.message) || error);
      const json = text.slice(text.indexOf("{"));
      let detail = null;
      try { detail = JSON.parse(json).detail; } catch (_) { /* not JSON */ }
      throw new Error(typeof detail === "string" ? detail : text);
    }
  }

  function HermiePage() {
    const ref = SDK.hooks.useRef(null);
    SDK.hooks.useEffect(function () {
      return window.HermieView.mount(ref.current, {
        load: function () { return call("/pet"); },
        act: function (action, name) { return call("/action", { action: action, name: name }); },
      });
    }, []);
    return React.createElement("div", { ref: ref });
  }

  window.__HERMES_PLUGINS__.register("hermie", HermiePage);
})();
