// Standalone page: talks to hermie_web.py with the private token from the link.
"use strict";
(function () {
  let token = "";
  const hash = new URLSearchParams(location.hash.slice(1));
  if (hash.has("token")) {
    token = hash.get("token") || "";
    sessionStorage.setItem("hermie_token", token);
    history.replaceState(null, "", location.pathname);
  } else {
    token = sessionStorage.getItem("hermie_token") || "";
  }

  async function call(path, body) {
    const options = { headers: { "X-Hermie-Token": token } };
    if (body) {
      options.method = "POST";
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    const data = await response.json();
    if (response.status === 401) throw new Error("Open the private link printed by the server.");
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  HermieView.mount(document.getElementById("app"), {
    load: () => call("/api/pet"),
    act: (action, name) => call("/api/action", { action, name }),
  });
})();
