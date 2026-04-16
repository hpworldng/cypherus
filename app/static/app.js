const authForm = document.getElementById("authForm");
const codeForm = document.getElementById("codeForm");
const passwordForm = document.getElementById("passwordForm");
const logBox = document.getElementById("log");

let phoneRef = "";

function log(message, data = null) {
  const line = data ? `${message}\n${JSON.stringify(data, null, 2)}` : message;
  logBox.textContent = `${line}\n\n${logBox.textContent}`;
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(authForm);
  const payload = {
    api_id: Number(formData.get("api_id")),
    api_hash: formData.get("api_hash"),
    phone: formData.get("phone"),
  };

  try {
    const data = await postJson("/api/v1/auth/start", payload);
    phoneRef = data.phone;
    codeForm.classList.remove("hidden");
    log("Login code sent.", data);
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

codeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(codeForm);

  try {
    const data = await postJson("/api/v1/auth/verify-code", {
      phone: phoneRef,
      code: formData.get("code"),
    });

    if (data.status === "2fa_required") {
      passwordForm.classList.remove("hidden");
      log("2FA required.");
      return;
    }

    log("Authorized successfully.", data);
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(passwordForm);

  try {
    const data = await postJson("/api/v1/auth/verify-password", {
      phone: phoneRef,
      password: formData.get("password"),
    });
    log("2FA verified. Authorized successfully.", data);
  } catch (error) {
    log(`Error: ${error.message}`);
  }
});
