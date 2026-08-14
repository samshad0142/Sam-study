(async function () {
  let auth = null;

  function show(msg) {
    const el = document.getElementById("toast");
    const msgEl = document.getElementById("authMessage");

    if (el) {
      el.textContent = msg;
      el.classList.add("show");
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
    }

    if (msgEl) msgEl.textContent = msg;
    console.log(msg);
  }

  window.showToast = show;

  // Load Firebase Compat SDK automatically
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load Firebase SDK"));
      document.head.appendChild(s);
    });
  }

  try {
    // Firebase SDK
    if (!window.firebase) {
      await loadScript(
        "https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"
      );
    }

    if (!window.firebase.auth) {
      await loadScript(
        "https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"
      );
    }

    // Get Firebase configuration from Render
    const response = await fetch("/api/firebase-config");
    const cfg = await response.json();

    console.log("Firebase config:", cfg);

    if (!cfg.apiKey || !cfg.projectId || !cfg.appId) {
      show("Firebase configuration is incomplete.");
      console.error("Missing Firebase config:", cfg);
      return;
    }

    // Initialize Firebase
    if (!firebase.apps.length) {
      firebase.initializeApp(cfg);
    }

    auth = firebase.auth();
    window.samAuth = auth;

    // Login/logout UI
    auth.onAuthStateChanged(function (user) {
      const login = document.getElementById("loginLink");
      const logout = document.getElementById("logoutBtn");

      if (user) {
        if (login) login.classList.add("hidden");
        if (logout) logout.classList.remove("hidden");

        window.samUser = user;
        console.log("Logged in:", user.email);
      } else {
        if (login) login.classList.remove("hidden");
        if (logout) logout.classList.add("hidden");

        window.samUser = null;
      }
    });

    // Logout
    const logout = document.getElementById("logoutBtn");

    if (logout) {
      logout.onclick = async function () {
        try {
          await auth.signOut();
          location.href = "/";
        } catch (e) {
          show(friendlyError(e));
        }
      };
    }

    // Google Login / Signup
    const googleButtons = [
      document.getElementById("
