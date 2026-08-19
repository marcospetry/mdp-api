(() => {
  const state = {
    preauthToken: null,
    accessToken: null,
    refreshToken: null,
  };

  const $ = (id) => document.getElementById(id);
  const steps = ["loginStep", "mfaStep", "mfaSetupStep", "dashboardStep"];

  function showStep(id) {
    steps.forEach((step) => $(step).classList.toggle("hidden", step !== id));
    hideMessage();
  }

  function showMessage(text, type = "error") {
    const el = $("message");
    el.textContent = text;
    el.className = `message ${type}`;
  }

  function hideMessage() {
    const el = $("message");
    el.textContent = "";
    el.className = "message hidden";
  }

  async function request(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (state.accessToken) {
      headers.Authorization = `Bearer ${state.accessToken}`;
    }

    const response = await fetch(path, { ...options, headers });
    let body = null;
    try {
      body = await response.json();
    } catch (_) {}

    if (!response.ok) {
      const detail = body?.detail || `Falha HTTP ${response.status}`;
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  async function loadMe() {
    const me = await request("/api/auth/me");
    $("welcomeName").textContent = `Olá, ${me.nome}`;
    $("companyId").textContent = me.empresa_id || "Acesso global";
    $("profileName").textContent = me.perfil || "Global";
    $("superadminFlag").textContent = me.is_superadmin ? "Sim" : "Não";
    $("userEmail").textContent = me.email;
    showStep("dashboardStep");
  }

  async function finishAuthentication(body) {
    state.accessToken = body.access_token;
    state.refreshToken = body.refresh_token;
    state.preauthToken = null;
    await loadMe();
  }

  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideMessage();
    const button = $("loginButton");
    button.disabled = true;
    button.textContent = "Entrando...";

    try {
      const body = await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: $("email").value.trim(),
          senha: $("senha").value,
          empresa_id: null,
        }),
      });

      if (body.status === "AUTHENTICATED") {
        await finishAuthentication(body);
        return;
      }

      state.preauthToken = body.preauth_token;

      if (body.status === "MFA_VERIFY") {
        $("mfaCode").value = "";
        showStep("mfaStep");
        $("mfaCode").focus();
        return;
      }

      if (body.status === "MFA_SETUP") {
        const setup = await request(
          `/api/auth/mfa/setup?preauth_token=${encodeURIComponent(state.preauthToken)}`,
          { method: "POST" },
        );
        $("mfaSecret").textContent = setup.secret;
        $("mfaSetupCode").value = "";
        showStep("mfaSetupStep");
        $("mfaSetupCode").focus();
        return;
      }

      throw new Error(`Status de autenticação não reconhecido: ${body.status}`);
    } catch (error) {
      showMessage(error.message || "Não foi possível entrar.");
    } finally {
      button.disabled = false;
      button.textContent = "Entrar";
    }
  });

  $("mfaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("mfaButton");
    button.disabled = true;
    button.textContent = "Verificando...";

    try {
      const code = $("mfaCode").value.replace(/\D/g, "");
      if (code.length !== 6) throw new Error("Informe os 6 dígitos do autenticador.");

      const body = await request("/api/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({
          preauth_token: state.preauthToken,
          codigo: code,
        }),
      });
      await finishAuthentication(body);
    } catch (error) {
      showMessage(error.message || "Código de verificação inválido.");
    } finally {
      button.disabled = false;
      button.textContent = "Verificar e entrar";
    }
  });

  $("mfaSetupForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("mfaSetupButton");
    button.disabled = true;
    button.textContent = "Confirmando...";

    try {
      const code = $("mfaSetupCode").value.replace(/\D/g, "");
      if (code.length !== 6) throw new Error("Informe os 6 dígitos do autenticador.");

      const body = await request("/api/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({
          preauth_token: state.preauthToken,
          codigo: code,
        }),
      });
      await finishAuthentication(body);
    } catch (error) {
      showMessage(error.message || "Não foi possível confirmar o MFA.");
    } finally {
      button.disabled = false;
      button.textContent = "Confirmar MFA e entrar";
    }
  });

  $("logoutButton").addEventListener("click", async () => {
    try {
      if (state.accessToken) {
        await request("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: state.refreshToken }),
        });
      }
    } catch (_) {
      // Mesmo se a sessão já estiver expirada, limpamos o estado local.
    } finally {
      state.preauthToken = null;
      state.accessToken = null;
      state.refreshToken = null;
      $("senha").value = "";
      $("mfaCode").value = "";
      $("mfaSetupCode").value = "";
      showStep("loginStep");
      $("email").focus();
    }
  });

  $("togglePassword").addEventListener("click", () => {
    const field = $("senha");
    const visible = field.type === "text";
    field.type = visible ? "password" : "text";
    $("togglePassword").textContent = visible ? "Mostrar" : "Ocultar";
  });

  $("mfaCode").addEventListener("input", (event) => {
    event.target.value = event.target.value.replace(/\D/g, "").slice(0, 6);
  });

  $("mfaSetupCode").addEventListener("input", (event) => {
    event.target.value = event.target.value.replace(/\D/g, "").slice(0, 6);
  });

  $("copySecret").addEventListener("click", async () => {
    const secret = $("mfaSecret").textContent;
    try {
      await navigator.clipboard.writeText(secret);
      showMessage("Chave copiada.", "info");
    } catch (_) {
      showMessage("Selecione e copie a chave manualmente.", "info");
    }
  });

  $("backToLogin").addEventListener("click", () => {
    state.preauthToken = null;
    showStep("loginStep");
  });

  $("backFromSetup").addEventListener("click", () => {
    state.preauthToken = null;
    showStep("loginStep");
  });
})();
