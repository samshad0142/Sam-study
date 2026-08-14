
(async function(){
  let auth = null;

  function show(msg){
    const el=document.getElementById("toast");
    if(!el)return;
    el.textContent=msg;el.classList.add("show");
    clearTimeout(window.__toastTimer);
    window.__toastTimer=setTimeout(()=>el.classList.remove("show"),3200);
  }
  window.showToast=show;

  try{
    const cfg=await fetch("/api/firebase-config").then(r=>r.json());
    if(!cfg.apiKey || !cfg.projectId || !cfg.appId){
      console.warn("Firebase web config is incomplete. Set FIREBASE_API_KEY, FIREBASE_APP_ID and related Render variables.");
      return;
    }
    if(!firebase.apps.length) firebase.initializeApp(cfg);
    auth=firebase.auth();
    window.samAuth=auth;

    auth.onAuthStateChanged(async user=>{
      const login=document.getElementById("loginLink");
      const logout=document.getElementById("logoutBtn");
      if(user){
        if(login) login.classList.add("hidden");
        if(logout) logout.classList.remove("hidden");
        window.samUser=user;
      }else{
        if(login) login.classList.remove("hidden");
        if(logout) logout.classList.add("hidden");
        window.samUser=null;
      }
    });

    const logout=document.getElementById("logoutBtn");
    if(logout) logout.onclick=()=>auth.signOut().then(()=>location.href="/");

    const googleButtons=[
      document.getElementById("googleLogin"),
      document.getElementById("googleSignup")
    ].filter(Boolean);

    googleButtons.forEach(btn=>{
      btn.addEventListener("click", async ()=>{
        try{
          const provider=new firebase.auth.GoogleAuthProvider();
          // Redirect is more reliable on mobile browsers than popup.
          await auth.signInWithRedirect(provider);
        }catch(e){
          show("Google login failed: "+friendlyError(e));
        }
      });
    });

    if(location.pathname==="/login"){
      const form=document.getElementById("loginForm");
      const msg=document.getElementById("authMessage");
      if(form) form.addEventListener("submit",async e=>{
        e.preventDefault();
        try{
          await auth.signInWithEmailAndPassword(
            document.getElementById("email").value.trim(),
            document.getElementById("password").value
          );
          location.href="/";
        }catch(err){msg.textContent=friendlyError(err);}
      });

      const forgot=document.getElementById("forgotPassword");
      if(forgot) forgot.onclick=async()=>{
        const email=document.getElementById("email").value.trim();
        if(!email){msg.textContent="Enter your email first.";return;}
        try{
          await auth.sendPasswordResetEmail(email);
          msg.textContent="Password reset email sent.";
        }catch(err){msg.textContent=friendlyError(err);}
      };
    }

    if(location.pathname==="/signup"){
      const form=document.getElementById("signupForm");
      const msg=document.getElementById("authMessage");
      if(form) form.addEventListener("submit",async e=>{
        e.preventDefault();
        try{
          const result=await auth.createUserWithEmailAndPassword(
            document.getElementById("email").value.trim(),
            document.getElementById("password").value
          );
          const name=document.getElementById("name").value.trim();
          if(name) await result.user.updateProfile({displayName:name});
          location.href="/";
        }catch(err){msg.textContent=friendlyError(err);}
      });
    }

    // Process redirect result after returning from Google.
    try{
      const result=await auth.getRedirectResult();
      if(result && result.user) location.href="/";
    }catch(e){
      const msg=document.getElementById("authMessage");
      if(msg) msg.textContent=friendlyError(e);
    }
  }catch(e){
    console.error(e);
  }

  function friendlyError(e){
    const code=e && e.code ? e.code : "";
    const map={
      "auth/api-key-not-valid":"Firebase API key is invalid. Update the Firebase Web App config in Render Environment Variables.",
      "auth/invalid-api-key":"Firebase API key is invalid. Update the Firebase Web App config in Render Environment Variables.",
      "auth/operation-not-allowed":"Enable this sign-in method in Firebase Authentication.",
      "auth/unauthorized-domain":"Add this Render domain to Firebase Authentication → Settings → Authorized domains.",
      "auth/email-already-in-use":"This email already has an account. Login instead.",
      "auth/invalid-credential":"Email or password is incorrect.",
      "auth/weak-password":"Use a stronger password (6+ characters)."
    };
    return map[code] || (e && e.message ? e.message.replace("Firebase: ","") : "Something went wrong.");
  }

  window.getIdToken=async function(){
    if(!auth || !auth.currentUser) return null;
    return auth.currentUser.getIdToken(true);
  };

  window.authFetch=async function(url,options={}){
    const token=await window.getIdToken();
    options.headers=Object.assign({},options.headers||{});
    if(token) options.headers.Authorization="Bearer "+token;
    return fetch(url,options);
  };
})();
