(async function () {
  let auth = null;

  function show(msg) {
    const el = document.getElementById("toast");
    const msgEl = document.getElementById("authMessage");

    if (el) {
      el.textContent = msg;
      el.classList.add("show");

      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => {
        el.classList.remove("show");
      }, 3200);
    }

    if (msgEl) {
      msgEl.textContent = msg;
    }

    console.log(msg);
  }

  window.showToast = show;

  try {
    // Get Firebase configuration from your Flask/Render API
    const response = await fetch("/api/firebase-config");

    if (!response.ok) {
      throw new Error("Could not load Firebase configuration.");
    }

    const cfg = await response.json();

    console.log("Firebase config loaded:", {
      projectId: cfg.projectId,
      appId: cfg.appId,
      authDomain: cfg.authDomain
    });

    // Check required configuration
    if (!cfg.apiKey || !cfg.projectId || !cfg.appId) {
      show("Firebase configuration is incomplete.");
      console.error("Missing Firebase configuration:", cfg);
      return;
    }

    // Firebase SDK must already be loaded by HTML
    if (!window.firebase) {
      show("Firebase SDK is not loaded.");
      console.error(
        "Firebase SDK missing. Load firebase-app-compat.js and firebase-auth-compat.js before firebase-client.js."
      );
      return;
    }

    // Initialize Firebase
    if (!firebase.apps.length) {
      firebase.initializeApp(cfg);
    }

    auth = firebase.auth();
    window.samAuth = auth;

    console.log("Firebase initialized successfully.");

    // --------------------------------------------------
    // AUTH STATE
    // --------------------------------------------------

    auth.onAuthStateChanged(function (user) {
      const login = document.getElementById("loginLink");
      const logout = document.getElementById("logoutBtn");

      if (user) {
        console.log("User logged in:", user.email);

        if (login) {
          login.classList.add("hidden");
        }

        if (logout) {
          logout.classList.remove("hidden");
        }

        window.samUser = user;
      } else {
        if (login) {
          login.classList.remove("hidden");
        }

        if (logout) {
          logout.classList.add("hidden");
        }

        window.samUser = null;
      }
    });

    // --------------------------------------------------
    // LOGOUT
    // --------------------------------------------------

    const logout = document.getElementById("logoutBtn");

    if (logout) {
      logout.type = "button";

      logout.onclick = async function (e) {
        e.preventDefault();

        try {
          await auth.signOut();
          window.location.href = "/";
        } catch (err) {
          show(friendlyError(err));
        }
      };
    }

    // --------------------------------------------------
    // GOOGLE LOGIN
    // --------------------------------------------------

    const googleButtons = [
      document.getElementById("googleLogin"),
      document.getElementById("googleSignup")
    ].filter(Boolean);

    googleButtons.forEach(function (button) {
      button.type = "button";

      button.addEventListener("click", async function (e) {
        e.preventDefault();
        e.stopPropagation();

        try {
          console.log("Starting Google login...");

          const provider =
            new firebase.auth.GoogleAuthProvider();

          provider.setCustomParameters({
            prompt: "select_account"
          });

          await auth.signInWithRedirect(provider);

        } catch (err) {
          console.error("Google login error:", err);
          show("Google login failed: " + friendlyError(err));
        }
      });
    });

    // --------------------------------------------------
    // EMAIL LOGIN
    // --------------------------------------------------

    if (location.pathname === "/login") {

      const form =
        document.getElementById("loginForm");

      const msg =
        document.getElementById("authMessage");

      if (form) {

        form.addEventListener("submit", async function (e) {

          e.preventDefault();
          e.stopPropagation();

          try {

            const email =
              document.getElementById("email").value.trim();

            const password =
              document.getElementById("password").value;

            if (!email || !password) {
              if (msg) {
                msg.textContent =
                  "Enter email and password.";
              }
              return;
            }

            console.log("Logging in:", email);

            await auth.signInWithEmailAndPassword(
              email,
              password
            );

            console.log("Email login successful.");

            window.location.href = "/";

          } catch (err) {

            console.error("Email login error:", err);

            if (msg) {
              msg.textContent =
                friendlyError(err);
            }
          }
        });
      }

      // ------------------------------------------------
      // FORGOT PASSWORD
      // ------------------------------------------------

      const forgot =
        document.getElementById("forgotPassword");

      if (forgot) {

        forgot.type = "button";

        forgot.onclick = async function (e) {

          e.preventDefault();

          const email =
            document.getElementById("email").value.trim();

          if (!email) {
            if (msg) {
              msg.textContent =
                "Enter your email first.";
            }
            return;
          }

          try {

            await auth.sendPasswordResetEmail(email);

            if (msg) {
              msg.textContent =
                "Password reset email sent.";
            }

          } catch (err) {

            if (msg) {
              msg.textContent =
                friendlyError(err);
            }
          }
        };
      }
    }

    // --------------------------------------------------
    // CREATE ACCOUNT
    // --------------------------------------------------

    if (location.pathname === "/signup") {

      const form =
        document.getElementById("signupForm");

      const msg =
        document.getElementById("authMessage");

      if (form) {

        form.addEventListener("submit", async function (e) {

          e.preventDefault();
          e.stopPropagation();

          try {

            const name =
              document.getElementById("name").value.trim();

            const email =
              document.getElementById("email").value.trim();

            const password =
              document.getElementById("password").value;

            if (!name || !email || !password) {

              if (msg) {
                msg.textContent =
                  "Please fill all fields.";
              }

              return;
            }

            console.log("Creating account:", email);

            const result =
              await auth.createUserWithEmailAndPassword(
                email,
                password
              );

            if (name) {

              await result.user.updateProfile({
                displayName: name
              });
            }

            console.log("Account created successfully.");

            window.location.href = "/";

          } catch (err) {

            console.error("Signup error:", err);

            if (msg) {
              msg.textContent =
                friendlyError(err);
            }
          }
        });
      }
    }

    // --------------------------------------------------
    // GOOGLE REDIRECT RESULT
    // --------------------------------------------------

    try {

     
