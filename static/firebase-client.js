(function () {
  let auth = null;

  function show(msg) {
    const el = document.getElementById("toast");
    if (!el) return;

    el.textContent = msg;
    el.classList.add("show");

    setTimeout(() => {
      el.classList.remove("show");
    }, 3500);
  }

  window.showToast = show;

  function friendlyError(e) {
    const code = e && e.code ? e.code : "";

    const errors = {
      "auth/unauthorized-domain":
        "This website is not authorized in Firebase.",

      "auth/popup-closed-by-user":
        "Google login was cancelled.",

      "auth/popup-blocked":
        "Google popup was blocked.",

      "auth/operation-not-allowed":
        "Google login is disabled in Firebase.",

      "auth/email-already-in-use":
        "This email already has an account.",

      "auth/invalid-credential":
        "Invalid email or password.",

      "auth/user-not-found":
        "No account found with this email.",

      "auth/wrong-password":
        "Incorrect password.",

      "auth/weak-password":
        "Password must contain at least 6 characters."
    };

    return errors[code] ||
      (e && e.message
        ? e.message.replace("Firebase: ", "")
        : "Something went wrong.");
  }


  async function init() {

    try {

      const response = await fetch("/api/firebase-config");
      const cfg = await response.json();

      if (
        !cfg.apiKey ||
        !cfg.authDomain ||
        !cfg.projectId ||
        !cfg.appId
      ) {
        console.error("Firebase configuration incomplete:", cfg);
        show("Firebase configuration is incomplete.");
        return;
      }


      if (!firebase.apps.length) {
        firebase.initializeApp(cfg);
      }

      auth = firebase.auth();

      window.samAuth = auth;


      /*
       * AUTH STATE
       */

      auth.onAuthStateChanged(function (user) {

        window.samUser = user || null;

        const loginLink =
          document.getElementById("loginLink");

        const profileLink =
          document.getElementById("profileLink");

        const profileName =
          document.getElementById("profileName");

        const profileAvatar =
          document.getElementById("profileAvatar");


        if (user) {

          /* Hide Login */
          if (loginLink) {
            loginLink.classList.add("hidden");
          }

          /* Show Profile */
          if (profileLink) {
            profileLink.classList.remove("hidden");
          }


          /*
           * Google/profile information
           */

          if (profileName) {

            profileName.textContent =
              user.displayName ||
              user.email ||
              "Profile";

          }


          if (profileAvatar) {

            if (user.photoURL) {

              profileAvatar.innerHTML =
                '<img src="' +
                user.photoURL +
                '" alt="Profile">';

            } else {

              profileAvatar.textContent = "👤";

            }

          }

        } else {

          /* Show Login */
          if (loginLink) {
            loginLink.classList.remove("hidden");
          }

          /* Hide Profile */
          if (profileLink) {
            profileLink.classList.add("hidden");
          }

        }

      });


      /*
       * GOOGLE LOGIN
       */

      async function googleLogin() {

        try {

          const provider =
            new firebase.auth.GoogleAuthProvider();

          provider.setCustomParameters({
            prompt: "select_account"
          });

          await auth.signInWithRedirect(provider);

        } catch (err) {

          console.error(
            "Google login error:",
            err
          );

          show(
            "Google login failed: " +
            friendlyError(err)
          );
        }

      }


      const googleLoginButton =
        document.getElementById("googleLogin");

      const googleSignupButton =
        document.getElementById("googleSignup");


      if (googleLoginButton) {

        googleLoginButton.onclick =
          function (e) {

            e.preventDefault();
            googleLogin();

          };

      }


      if (googleSignupButton) {

        googleSignupButton.onclick =
          function (e) {

            e.preventDefault();
            googleLogin();

          };

      }


      /*
       * GOOGLE REDIRECT RESULT
       */

      try {

        const result =
          await auth.getRedirectResult();

        if (result && result.user) {

          console.log(
            "Google login successful:",
            result.user.email
          );

          window.location.href = "/";

        }

      } catch (err) {

        console.error(
          "Google redirect error:",
          err
        );

        const msg =
          document.getElementById(
            "authMessage"
          );

        if (msg) {
          msg.textContent =
            friendlyError(err);
        }

      }


      /*
       * EMAIL LOGIN
       */

      if (location.pathname === "/login") {

        const form =
          document.getElementById("loginForm");

        const msg =
          document.getElementById("authMessage");


        if (form) {

          form.addEventListener(
            "submit",
            async function (e) {

              e.preventDefault();

              try {

                const email =
                  document
                    .getElementById("email")
                    .value
                    .trim();

                const password =
                  document
                    .getElementById("password")
                    .value;


                if (!email || !password) {

                  msg.textContent =
                    "Email and password required.";

                  return;

                }


                await auth.signInWithEmailAndPassword(
                  email,
                  password
                );


                window.location.href = "/";

              } catch (err) {

                console.error(err);

                msg.textContent =
                  friendlyError(err);

              }

            }
          );

        }


        /*
         * FORGOT PASSWORD
         */

        const forgot =
          document.getElementById(
            "forgotPassword"
          );


        if (forgot) {

          forgot.onclick =
            async function (e) {

              e.preventDefault();

              const email =
                document
                  .getElementById("email")
                  .value
                  .trim();


              if (!email) {

                msg.textContent =
                  "Enter your email first.";

                return;

              }


              try {

                await auth.sendPasswordResetEmail(
                  email
                );

                msg.textContent =
                  "Password reset email sent.";

              } catch (err) {

                msg.textContent =
                  friendlyError(err);

             
