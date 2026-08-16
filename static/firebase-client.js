(function () {
  "use strict";

  let auth = null;

  function show(msg) {
    const el = document.getElementById("toast");
    if (el) {
      el.textContent = msg;
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 3500);
    }
  }

  window.showToast = show;

  function friendlyError(e) {
    const code = e && e.code ? e.code : "";

    const errors = {
      "auth/api-key-not-valid":
        "Firebase API key is invalid.",
      "auth/invalid-api-key":
        "Firebase API key is invalid.",
      "auth/operation-not-allowed":
        "This login method is disabled in Firebase.",
      "auth/unauthorized-domain":
        "This website domain is not authorized in Firebase.",
      "auth/email-already-in-use":
        "This email already has an account. Login instead.",
      "auth/invalid-credential":
        "Email or password is incorrect.",
      "auth/invalid-login-credentials":
        "Email or password is incorrect.",
      "auth/wrong-password":
        "Incorrect password.",
      "auth/user-not-found":
        "No account found with this email.",
      "auth/weak-password":
        "Password must be at least 6 characters.",
      "auth/popup-blocked":
        "Google popup was blocked. Please allow popups and try again.",
      "auth/popup-closed-by-user":
        "Google login was cancelled.",
      "auth/cancelled-popup-request":
        "Google login was cancelled."
    };

    return errors[code] ||
      (e && e.message
        ? e.message.replace("Firebase: ", "")
        : "Something went wrong.");
  }

  async function init() {
    try {
      const response = await fetch("/api/firebase-config", {
        cache: "no-store"
      });

      if (!response.ok) {
        throw new Error("Firebase config API failed.");
      }

      const cfg = await response.json();

      console.log("Firebase config loaded:", {
        projectId: cfg.projectId,
        authDomain: cfg.authDomain,
        appId: cfg.appId
      });

      if (
        !cfg.apiKey ||
        !cfg.authDomain ||
        !cfg.projectId ||
        !cfg.appId
      ) {
        console.error("Incomplete Firebase config:", cfg);
        show("Firebase configuration is incomplete.");
        return;
      }

      if (!firebase.apps.length) {
        firebase.initializeApp(cfg);
      }

      auth = firebase.auth();
      window.samAuth = auth;

      await auth.setPersistence(
        firebase.auth.Auth.Persistence.LOCAL
      );

      window.samUser = auth.currentUser || null;

      auth.onAuthStateChanged(function (user) {
        window.samUser = user || null;

        const login = document.getElementById("loginLink");
        const logout = document.getElementById("logoutBtn");

        if (user) {
          if (login) login.classList.add("hidden");
          if (logout) logout.classList.remove("hidden");
        } else {
          if (login) login.classList.remove("hidden");
          if (logout) logout.classList.add("hidden");
        }
      });

      /* LOGOUT */
      const logout = document.getElementById("logoutBtn");

      if (logout) {
        logout.addEventListener("click", async function (e) {
          e.preventDefault();

          try {
            await auth.signOut();
            window.location.href = "/";
          } catch (err) {
            console.error(err);
            show(friendlyError(err));
          }
        });
      }

      /* GOOGLE LOGIN */
      async function googleLoginHandler(e) {
        e.preventDefault();
        e.stopPropagation();

        if (!auth) {
          show("Firebase is not ready. Please wait.");
          return;
        }

        try {
          const provider =
            new firebase.auth.GoogleAuthProvider();

          provider.setCustomParameters({
            prompt: "select_account"
          });

          /*
           * Popup avoids the redirect loop you were getting.
           */
          const result = await auth.signInWithPopup(provider);

          if (result && result.user) {
            window.location.href = "/";
          }

        } catch (err) {
          console.error("Google login error:", err);

          /*
           * If popup is blocked, try redirect.
           */
          if (
            err.code === "auth/popup-blocked" ||
            err.code === "auth/operation-not-supported-in-this-environment"
          ) {
            try {
              const provider =
                new firebase.auth.GoogleAuthProvider();

              provider.setCustomParameters({
                prompt: "select_account"
              });

              await auth.signInWithRedirect(provider);
              return;

            } catch (redirectError) {
              console.error(
                "Google redirect error:",
                redirectError
              );

              show(friendlyError(redirectError));
              return;
            }
          }

          show("Google login failed: " + friendlyError(err));
        }
      }

      const googleLogin =
        document.getElementById("googleLogin");

      const googleSignup =
        document.getElementById("googleSignup");

      if (googleLogin) {
        googleLogin.onclick = googleLoginHandler;
      }

      if (googleSignup) {
        googleSignup.onclick = googleLoginHandler;
      }

      /* PROCESS GOOGLE REDIRECT */
      try {
        const redirectResult =
          await auth.getRedirectResult();

        if (
          redirectResult &&
          redirectResult.user
        ) {
          window.location.href = "/";
          return;
        }
      } catch (err) {
        console.error(
          "Google redirect result error:",
          err
        );

        const msg =
          document.getElementById("authMessage");

        if (msg) {
          msg.textContent = friendlyError(err);
        }
      }

      /* LOGIN PAGE */
      const path =
        window.location.pathname.replace(/\/+$/, "");

      if (path === "/login") {
        const form =
          document.getElementById("loginForm");

        const msg =
          document.getElementById("authMessage");

        if (form) {
          form.onsubmit = async function (e) {
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
                    "Email and password required.";
                }
                return false;
              }

              if (msg) {
                msg.textContent = "Logging in...";
              }

              await auth.signInWithEmailAndPassword(
                email,
                password
              );

              window.location.href = "/";

            } catch (err) {
              console.error(err);

              if (msg) {
                msg.textContent =
                  friendlyError(err);
              }
            }

            return false;
          };
        }

        /* FORGOT PASSWORD */
        const forgot =
          document.getElementById("forgotPassword");

        if (forgot) {
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
              console.error(err);

              if (msg) {
                msg.textContent =
                  friendlyError(err);
              }
            }
          };
        }
      }

      /* SIGNUP PAGE */
      if (path === "/signup") {
        const form =
          document.getElementById("signupForm");

        const msg =
          document.getElementById("authMessage");

        if (form) {
          form.onsubmit = async function (e) {
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
                return false;
              }

              if (password.length < 6) {
                if (msg) {
                  msg.textContent =
                    "Password must be at least 6 characters.";
                }
                return false;
              }

              if (msg) {
                msg.textContent =
                  "Creating account...";
              }

              const result =
                await auth.createUserWithEmailAndPassword(
                  email,
                  password
                );

              if (result.user && name) {
                await result.user.updateProfile({
                  displayName: name
                });
              }

              window.location.href = "/";

            } catch (err) {
              console.error(err);

              if (msg) {
                msg.textContent =
                  friendlyError(err);
              }
            }

            return false;
          };
        }
      }

      console.log("SamStudy Firebase Auth ready.");

    } catch (err) {
      console.error(
        "Firebase initialization error:",
        err
      );

      show(
        "Firebase connection error: " +
        (err.message || "Unknown error")
      );
    }
  }

  /*
   * Start after HTML is ready.
   */
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      init
    );
  } else {
    init();
  }

  /* ID TOKEN */
  window.getIdToken = async function () {
    if (!auth || !auth.currentUser) {
      return null;
    }

    return await auth.currentUser.getIdToken(true);
  };

  /* AUTH FETCH */
  window.authFetch = async function (
    url,
    options = {}
  ) {
    const token =
      await window.getIdToken();

    options.headers = Object.assign(
      {},
      options.headers || {}
    );

    if (token) {
      options.headers.Authorization =
        "Bearer " + token;
    }

    return fetch(url, options);
  };

})();
