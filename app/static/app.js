const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");
const dashboard = document.getElementById("dashboard");
const linkStartForm = document.getElementById("linkStartForm");
const codeForm = document.getElementById("codeForm");
const passwordForm = document.getElementById("passwordForm");
const deviceList = document.getElementById("deviceList");
const loadingBox = document.getElementById("loading");
const logBox = document.getElementById("log");

let token = "";
let phoneRef = "";

function setLoading(isLoading) {
  loadingBox.classList.toggle("hidden", !isLoading);
}

function log(message, data = null) {
  const line = data ? `${message}\n${JSON.stringify(data, null, 2)}` : message;
  logBox.textContent = `${new Date().toLocaleTimeString()}  ${line}\n\n${logBox.textContent}`;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const raw = await response.text();

  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(raw);
    } catch {
      throw new Error("Invalid JSON response from server.");
    }
  }

  if (!response.ok) {
    throw new Error(`Server returned non-JSON response (${response.status}).`);
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw new Error("Unexpected non-JSON response from server.");
  }
}

async function api(path, payload = null, method = "GET") {
  setLoading(true);
  try {
    const options = { method, headers: {} };
    if (token) options.headers["X-Auth-Token"] = token;
    if (payload) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }

    const response = await fetch(path, options);
    const data = await parseResponse(response);

    if (!response.ok) throw new Error(data.detail || "Request failed.");
    return data;
  } finally {
    setLoading(false);
  }
}

async function refreshDashboard() {
  const data = await api("/api/v1/dashboard/me");
  deviceList.innerHTML = "";

  for (const item of data.linked_devices) {
    const li = document.createElement("li");
    li.innerHTML = `
      <span>${item.phone} (${item.active ? "active" : "offline"})</span>
      <button data-phone="${item.phone}" class="danger">Unlink</button>
    `;
    deviceList.appendChild(li);
  }

  deviceList.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const data = await api("/api/v1/dashboard/unlink", { phone: btn.dataset.phone }, "POST");
        log("Device unlinked", data);
        await refreshDashboard();
      } catch (error) {
        log(`Error: ${error.message}`);
      }
    });
  });

  dashboard.classList.remove("hidden");
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registerForm);
  try {
    const data = await api("/api/v1/account/register", {
      api_id: Number(formData.get("api_id")),
      api_hash: formData.get("api_hash"),
    }, "POST");
    log("Account created", data);
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginForm);
  try {
    const data = await api("/api/v1/account/login", {
      api_id: Number(formData.get("api_id")),
      api_hash: formData.get("api_hash"),
    }, "POST");
    token = data.token;
    log("Login success.");
    await refreshDashboard();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

linkStartForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(linkStartForm);
  try {
    const data = await api("/api/v1/dashboard/link/start", { phone: formData.get("phone") }, "POST");
    phoneRef = data.phone;
    codeForm.classList.remove("hidden");
    log("Login code sent", data);
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

codeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(codeForm);
  try {
    const data = await api("/api/v1/dashboard/link/verify-code", { phone: phoneRef, code: formData.get("code") }, "POST");
    if (data.status === "2fa_required") {
      passwordForm.classList.remove("hidden");
      log("2FA required");
      return;
    }
    log("Device authorized", data);
    await refreshDashboard();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(passwordForm);
  try {
    const data = await api("/api/v1/dashboard/link/verify-password", { phone: phoneRef, password: formData.get("password") }, "POST");
    log("2FA success", data);
    await refreshDashboard();
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});
