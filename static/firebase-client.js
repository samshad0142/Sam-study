(async function () {
  let auth = null;

  function show(msg) {
    const el = document.getElementById("toast") || document.getElementById("authMessage");
    if (!el) return;
    el.textContent = msg;
    el.classList.add?.("show");
  }
  window.showToast = show;

  // Stop normal form refresh
  document.addEventListener("submit", e => {
    if (e.target.id === "loginForm" || e.target.id === "signupForm") {
      e.preventDefault();
    }
  });

  function friendlyError(e) {
    const code = e?.code || "";
    const map = {
      "auth/api-key-not-valid": "Firebase API key is invalid.",
      "auth/invalid-api-key": "Firebase API key is invalid.",
      "auth/operation-not-allowed": "Enable Email/Password in Firebase Authentication.",
      "auth/unauthorized-domain": "Add sam-study.onrender.com to Firebase Authorized Domains.",
      "auth/email-already-in-use": "This email already has an account. Login instead.",
      "auth/invalid-credential": "Email or password is incorrect.",
      "auth/weak-password": "Password must be at least 6 characters.",
      "auth/invalid-email": "Enter a valid email address."
    };
    return map[code] || e?.message || "Something went wrong.";
  }

  // Load Firebase SDK if not already loaded
  try {
    if (!window.firebase) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });

      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    const cfg = await fetch("/api/firebase-config").then(r => r.json());

    if (!cfg.apiKey || !cfg.projectId || !cfg.appId) {
      throw new Error("Firebase configuration is incomplete.");
    }

    if (!firebase.apps.length) {
      firebase.initializeApp(cfg);
    }

    auth = firebase.auth();
    window.samAuth = auth;

    auth.onAuthStateChanged(user => {
      const login = document.getElementById("loginLink");
      const logout = document.getElementById("logoutBtn");

      if (user) {
        login?.classList.add("hidden");
        logout?.classList.remove("hidden");
        window.samUser = user;
      } else {
        login?.classList.remove("hidden");
        logout?.classList.add("hidden");
        window.samUser = null;
      }
    });

    // Logout
    const logout = document.getElementById("logoutBtn");
    if (logout) {
      logout.onclick = async () => {
        await auth.signOut();
        location.href = "/";
      };
    }

    // Google Login
    ["googleLogin", "googleSignup"].forEach(id => {
      const btn = document.getElementById(id);
      if (!btn) return;

      btn.onclick = async e => {
        e.preventDefault();

        try {
          const provider = new firebase.auth.GoogleAuthProvider();
          await auth.signInWithRedirect(provider);
        } catch (err) {
          show("Google login failed: " + friendlyError(err));
        }
      };
    });

    // EMAIL LOGIN
    if (location.pathname === "/login") {
      const form = document.getElementById("loginForm");
      const msg = document.getElementById("authMessage");

      if (form) {
        form.onsubmit = async e => {
          e.preventDefault();

          try {
            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;

            if (!email || !password) {
              msg.textContent = "Enter email and password.";
              return;
            }

            await auth.signInWithEmailAndPassword(email, password);

            msg.textContent = "Login successful!";
            location.href = "/";

          } catch (err) {
            msg.textContent = friendlyError(err);
          }
        };
      }

      const forgot = document.getElementById("forgotPassword");

      if (forgot) {
        forgot.onclick = async e => {
          e.preventDefault();

          const email = document.getElementById("email").value.trim();

          if (!email) {
            msg.textContent = "Enter your email first.";
            return;
          }

          try {
            await auth.sendPasswordResetEmail(email);
            msg.textContent = "Password reset email sent.";
          } catch (err) {
            msg.textContent = friendlyError(err);
          }
        };
      }
    }

    // CREATE ACCOUNT
    if (location.pathname === "/signup") {
      const form = document.getElementById("signupForm");
      const msg = document.getElementById("authMessage");

      if (form) {
        form.onsubmit = async e => {
          e.preventDefault();

          try {
            const name = document.getElementById("name").value.trim();
            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;

            if (!name || !email || !password) {
              msg.textContent = "Please fill all fields.";
              return;
            }

            const result =
              await auth.createUserWithEmailAndPassword(email, password);

            if (name) {
              await result.user.updateProfile({
                displayName: name
              });
            }

            msg.textContent = "Account created successfully!";

            location.href = "/";

          } catch (err) {
            msg.textContent = friendlyError(err);
          }
        };
      }
    }

    // Google redirect result
    try {
      const result = await auth.getRedirectResult();

      if (result && result.user) {
        location.href = "/";
      }
    } catch (err) {
      const msg = document.getElementById("authMessage");
      if (msg) msg.textContent = friendlyError(err);
    }

  } catch (err) {
    console.error("Firebase initialization error:", err);

    const msg = document.getElementById("authMessage");

    if (msg) {
      msg.textContent =
        "Firebase connection error: " + friendlyError(err);
    }
  }

  window.getIdToken = async function () {
    if (!auth || !auth.currentUser) return null;
    return await auth.currentUser.getIdToken(true);
  };

  window.authFetch = async function (url, options = {}) {
    const token = await window.getIdToken();

    options.headers = Object.assign(
      {},
      options.headers || {}
    );

    if (token) {
      options.headers.Authorization = "Bearer " + token;
    }

    return fetch(url, options);
  };

})();
