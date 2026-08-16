(async function () {

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


  function setVisible(id, visible) {

    const el = document.getElementById(id);

    if (!el) return;

    if (visible) {
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  }


  function loadProfilePhoto(user) {

    const photoBox =
      document.getElementById("headerProfilePhoto");

    if (!photoBox || !user) return;


    const key =
      "samstudy_profile_" + user.uid;


    try {

      const saved =
        JSON.parse(
          localStorage.getItem(key)
        );


      if (saved && saved.photo) {

        photoBox.innerHTML =
          "<img src=\"" +
          saved.photo +
          "\" alt=\"Profile\">";

        return;

      }

    } catch (e) {

      console.error(e);

    }


    /*
     * Google/Firebase profile photo
     */

    if (user.photoURL) {

      photoBox.innerHTML =
        "<img src=\"" +
        user.photoURL +
        "\" alt=\"Profile\">";

    } else {

      photoBox.textContent = "👤";

    }

  }


  try {

    /*
     * Get Firebase configuration
     */

    const r =
      await fetch("/api/firebase-config");


    const cfg =
      await r.json();


    if (
      !cfg.apiKey ||
      !cfg.authDomain ||
      !cfg.projectId ||
      !cfg.appId
    ) {

      console.error(
        "Firebase configuration incomplete:",
        cfg
      );

      show(
        "Firebase configuration is incomplete."
      );

      return;

    }


    /*
     * Initialize Firebase
     */

    if (!firebase.apps.length) {

      firebase.initializeApp(cfg);

    }


    auth =
      firebase.auth();


    window.samAuth =
      auth;


    /*
     * Authentication state
     */

    auth.onAuthStateChanged(
      function (user) {

        window.samUser =
          user || null;


        if (user) {

          /*
           * USER IS LOGGED IN
           */

          setVisible(
            "loginLink",
            false
          );


          setVisible(
            "profileLink",
            true
          );


          loadProfilePhoto(user);


        } else {

          /*
           * USER IS LOGGED OUT
           */

          setVisible(
            "loginLink",
            true
          );


          setVisible(
            "profileLink",
            false
          );

        }

      }
    );


    /*
     * GOOGLE LOGIN
     */

    const googleLogin =
      document.getElementById(
        "googleLogin"
      );


    const googleSignup =
      document.getElementById(
        "googleSignup"
      );


    async function googleLoginHandler(e) {

      e.preventDefault();


      try {

        const provider =
          new firebase.auth.GoogleAuthProvider();


        /*
         * Popup is better for normal web login.
         */

        await auth.signInWithPopup(
          provider
        );


      } catch (err) {

        console.error(err);

        /*
         * If popup is blocked,
         * use redirect.
         */

        if (
          err.code ===
          "auth/popup-blocked"
        ) {

          try {

            const provider =
              new firebase.auth.GoogleAuthProvider();

            await auth.signInWithRedirect(
              provider
            );

          } catch (redirectError) {

            console.error(
              redirectError
            );

            show(
              friendlyError(
                redirectError
              )
            );

          }

        } else {

          show(
            friendlyError(err)
          );

        }

      }

    }


    if (googleLogin) {

      googleLogin.addEventListener(
        "click",
        googleLoginHandler
      );

    }


    if (googleSignup) {

      googleSignup.addEventListener(
        "click",
        googleLoginHandler
      );

    }


    /*
     * EMAIL LOGIN
     */

    if (
      location.pathname ===
      "/login"
    ) {

      const form =
        document.getElementById(
          "loginForm"
        );


      const msg =
        document.getElementById(
          "authMessage"
        );


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


              await auth
                .signInWithEmailAndPassword(
                  email,
                  password
                );


              location.href =
                "/";

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

              await auth
                .sendPasswordResetEmail(
                  email
                );


              msg.textContent =
                "Password reset email sent.";

            } catch (err) {

              msg.textContent =
                friendlyError(err);

            }

          };

      }

    }


    /*
     * SIGNUP
     */

    if (
      location.pathname ===
      "/signup"
    ) {

      const form =
        document.getElementById(
          "signupForm"
        );


      const msg =
        document.getElementById(
          "authMessage"
        );


      if (form) {

        form.addEventListener(
          "submit",
          async function (e) {

            e.preventDefault();


            try {

              const name =
                document
                  .getElementById("name")
                  .value
                  .trim();


              const email =
                document
                  .getElementById("email")
                  .value
                  .trim();


              const password =
                document
                  .getElementById("password")
                  .value;


              if (
                !name ||
                !email ||
                !password
              ) {

                msg.textContent =
                  "Please fill all fields.";

                return;

              }


              const result =
                await auth
                  .createUserWithEmailAndPassword(
                    email,
                    password
                  );


              if (name) {

                await result.user
                  .updateProfile({

                    displayName:
                      name

                  });

              }


              location.href =
                "/profile";


            } catch (err) {

              console.error(err);

              msg.textContent =
                friendlyError(err);

            }

          }
        );

      }

    }


    /*
     * Google redirect result
     */

    try {

      const result =
        await auth.getRedirectResult();


      if (
        result &&
        result.user
      ) {

        location.href =
          "/profile";

      }

    } catch (err) {

      console.error(
        "Redirect error:",
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


  } catch (err) {

    console.error(
      "Firebase initialization error:",
      err
    );

    show(
      "Firebase connection error."
    );

  }


  /*
   * Friendly Firebase errors
   */

  function friendlyError(e) {

    const code =
      e && e.code
        ? e.code
        : "";


    const map = {

      "auth/api-key-not-valid":
        "Firebase API key is invalid.",

      "auth/invalid-api-key":
        "Firebase API key is invalid.",

      "auth/operation-not-allowed":
        "This login method is disabled in Firebase.",

      "auth/unauthorized-domain":
        "This website domain is not authorized in Firebase.",

      "auth/popup-closed-by-user":
        "Google login was cancelled.",

      "auth/popup-blocked":
        "Google popup was blocked. Trying another method.",

      "auth/email-already-in-use":
        "This email already has an account. Login instead.",

      "auth/invalid-credential":
        "Email or password is incorrect.",

      "auth/invalid-login-credentials":
        "Email or password is incorrect.",

      "auth/weak-password":
        "Password must be at least 6 characters.",

      "auth/user-not-found":
        "No account found with this email.",

      "auth/wrong-password":
        "Incorrect password."

    };


    return (
      map[code] ||
      (
        e && e.message
          ? e.message.replace(
              "Firebase: ",
              ""
            )
          : "Something went wrong."
      )
    );

  }


  /*
   * Firebase ID token
   */

  window.getIdToken =
    async function () {

      if (
        !auth ||
        !auth.currentUser
      ) {

        return null;

      }


      return await auth
        .currentUser
        .getIdToken(true);

    };


  /*
   * Authenticated API request
   */

  window.authFetch =
    async function (
      url,
      options = {}
    ) {

      const token =
        await window.getIdToken();


      options.headers =
        Object.assign(
          {},
          options.headers || {}
        );


      if (token) {

        options.headers.Authorization =
          "Bearer " + token;

      }


      return fetch(
        url,
        options
      );

    };

})();
