(async function(){
  let auth=null;

  function show(msg){
    const el=document.getElementById("toast");
    if(!el)return;
    el.textContent=msg;
    el.classList.add("show");
    clearTimeout(window.__toastTimer);
    window.__toastTimer=setTimeout(
      ()=>el.classList.remove("show"),4000
    );
  }

  window.showToast=show;

  try{
    const cfg=await fetch("/api/firebase-config").then(r=>r.json());

    if(!cfg.apiKey || !cfg.projectId || !cfg.appId || !cfg.authDomain){
      console.error("Incomplete Firebase config:",cfg);
      show("Firebase configuration is incomplete.");
      return;
    }

    if(!firebase.apps.length){
      firebase.initializeApp(cfg);
    }

    auth=firebase.auth();
    window.samAuth=auth;

    await auth.setPersistence(
      firebase.auth.Auth.Persistence.LOCAL
    );

    auth.onAuthStateChanged(user=>{
      const login=document.getElementById("loginLink");
      const logout=document.getElementById("logoutBtn");

      if(user){
        window.samUser=user;

        if(login) login.classList.add("hidden");
        if(logout) logout.classList.remove("hidden");

        // Login/signup page se successful login ke baad home
        if(
          location.pathname==="/login" ||
          location.pathname==="/signup"
        ){
          location.replace("/");
        }
      }else{
        window.samUser=null;

        if(login) login.classList.remove("hidden");
        if(logout) logout.classList.add("hidden");
      }
    });

    const logout=document.getElementById("logoutBtn");

    if(logout){
      logout.onclick=async()=>{
        await auth.signOut();
        location.replace("/");
      };
    }

    // GOOGLE LOGIN
    const googleButtons=[
      document.getElementById("googleLogin"),
      document.getElementById("googleSignup")
    ].filter(Boolean);

    googleButtons.forEach(btn=>{
      btn.addEventListener("click",async e=>{
        e.preventDefault();

        try{
          const provider=new firebase.auth.GoogleAuthProvider();

          provider.setCustomParameters({
            prompt:"select_account"
          });

          await auth.signInWithRedirect(provider);

        }catch(err){
          console.error("Google error:",err);
          show("Google login failed: "+friendlyError(err));
        }
      });
    });

    // EMAIL LOGIN
    if(location.pathname==="/login"){

      const form=document.getElementById("loginForm");
      const msg=document.getElementById("authMessage");

      if(form){
        form.addEventListener("submit",async e=>{
          e.preventDefault();

          try{
            const email=
              document.getElementById("email").value.trim();

            const password=
              document.getElementById("password").value;

            if(!email || !password){
              if(msg) msg.textContent="Enter email and password.";
              return;
            }

            await auth.signInWithEmailAndPassword(
              email,
              password
            );

          }catch(err){
            console.error("Login error:",err);

            if(msg){
              msg.textContent=friendlyError(err);
            }
          }
        });
      }

      const forgot=document.getElementById("forgotPassword");

      if(forgot){
        forgot.onclick=async()=>{
          const email=
            document.getElementById("email").value.trim();

          if(!email){
            if(msg) msg.textContent="Enter your email first.";
            return;
          }

          try{
            await auth.sendPasswordResetEmail(email);

            if(msg){
              msg.textContent="Password reset email sent.";
            }

          }catch(err){
            if(msg){
              msg.textContent=friendlyError(err);
            }
          }
        };
      }
    }

    // SIGNUP
    if(location.pathname==="/signup"){

      const form=document.getElementById("signupForm");
      const msg=document.getElementById("authMessage");

      if(form){
        form.addEventListener("submit",async e=>{
          e.preventDefault();

          try{
            const email=
              document.getElementById("email").value.trim();

            const password=
              document.getElementById("password").value;

            const name=
              document.getElementById("name").value.trim();

            if(!email || !password){
              if(msg)
                msg.textContent="Enter email and password.";
              return;
            }

            const result=
              await auth.createUserWithEmailAndPassword(
                email,
                password
              );

            if(name){
              await result.user.updateProfile({
                displayName:name
              });
            }

          }catch(err){
            console.error("Signup error:",err);

            if(msg){
              msg.textContent=friendlyError(err);
            }
          }
        });
      }
    }

    // GOOGLE REDIRECT RESULT
    try{
      await auth.getRedirectResult();
    }catch(err){
      console.error("Redirect error:",err);

      const msg=document.getElementById("authMessage");

      if(msg){
        msg.textContent=friendlyError(err);
      }
    }

  }catch(err){
    console.error("Firebase initialization error:",err);
    show("Firebase connection error.");
  }


  function friendlyError(e){

    const code=e && e.code ? e.code : "";

    const map={

      "auth/api-key-not-valid":
        "Firebase API key is invalid.",

      "auth/invalid-api-key":
        "Firebase API key is invalid.",

      "auth/operation-not-allowed":
        "This sign-in method is not enabled in Firebase.",

      "auth/unauthorized-domain":
        "Add sam-study.onrender.com to Firebase Authorized domains.",

      "auth/email-already-in-use":
        "This email already has an account. Login instead.",

      "auth/invalid-credential":
        "Email or password is incorrect.",

      "auth/user-not-found":
        "No account found with this email.",

      "auth/wrong-password":
        "Incorrect password.",

      "auth/weak-password":
        "Password must contain at least 6 characters.",

      "auth/network-request-failed":
        "Network error. Check your internet connection."
    };

    return map[code] ||
      (e && e.message
        ? e.message.replace("Firebase: ","")
        : "Something went wrong.");
  }


  window.getIdToken=async function(){

    if(!auth || !auth.currentUser)
      return null;

    return auth.currentUser.getIdToken(true);
  };


  window.authFetch=async function(url,options={}){

    const token=await window.getIdToken();

    options.headers=Object.assign(
      {},
      options.headers || {}
    );

    if(token){
      options.headers.Authorization=
        "Bearer "+token;
    }

    return fetch(url,options);
  };

})();
