const cfg = window.FIREBASE_CONFIG || {};
let auth = null;
let currentUser = null;
let testState = null;
let testTimer = null;
let testStart = 0;
let profileLoaded = false;

const $ = id => document.getElementById(id);
const EXAMS = window.EXAM_OPTIONS || [
  "GATE", "SSC", "Railway", "UPSC", "Army", "NEET UG", "NEET PG",
  "JEE Main", "JEE Advanced", "AKTU", "Other Government Exam"
];
const FALLBACK_LOGO = "/static/logo.png";

function esc(s) {
  return String(s ?? "").replace(/[&<>'"]/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;"
  }[c]));
}

function fillExamSelect(id, optional = false) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = (optional ? '<option value="">Select exam</option>' : '') +
    EXAMS.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join("");
}

["qexam", "texam", "profileExam"].forEach(id => fillExamSelect(id, id === "profileExam"));

function isAdmin(u = currentUser) {
  return !!u && (window.ADMIN_EMAILS || []).map(x => String(x).toLowerCase())
    .includes((u.email || "").toLowerCase());
}

function currentPage() {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/") return "home";
  return path.slice(1).split("/")[0];
}

function syncBottomNav() {
  const page = currentPage();
  document.querySelectorAll(".bottomNav a[data-page]").forEach(a => {
    a.classList.toggle("active", a.dataset.page === page);
  });
  const p = $("bottomProfile");
  const label = $("bottomProfileLabel");
  const icon = $("bottomProfileIcon");
  if (p) p.classList.toggle("active", page === "profile" || !!currentUser);
  if (label) label.textContent = currentUser ? "Profile" : "Login / Sign up";
  if (icon) icon.textContent = currentUser ? "●" : "⇥";
}

function goPage(path) {
  location.href = path;
}

function openAuth() {
  if (currentUser) {
    openProfile();
    return;
  }
  const m = $("authModal");
  if (m) m.style.display = "flex";
  if ($("authMsg")) $("authMsg").textContent = "";
}

function closeAuth() {
  const m = $("authModal");
  if (m) m.style.display = "none";
}

function msg(x) {
  if ($("authMsg")) $("authMsg").textContent = x;
}

function lockProtectedPage() {
  document.querySelectorAll("[data-auth-page]").forEach(el => el.classList.add("authLocked"));
}

function unlockProtectedPage() {
  document.querySelectorAll("[data-auth-page]").forEach(el => el.classList.remove("authLocked"));
}

function protectCurrentPage() {
  const protectedPage = document.querySelector("[data-auth-page]");
  if (!protectedPage) return;
  if (currentUser) {
    unlockProtectedPage();
  } else {
    lockProtectedPage();
    openAuth();
  }
}

try {
  if (cfg.apiKey && cfg.projectId && window.firebase) {
    if (!firebase.apps.length) firebase.initializeApp(cfg);
    auth = firebase.auth();
    auth.onAuthStateChanged(async u => {
      currentUser = u || null;
      updateAuthUI(currentUser);
      if (currentUser) {
        const profile = await loadProfile();
        unlockProtectedPage();
        if (!profile || !profile.name || !profile.purpose) {
          setTimeout(openProfile, 180);
        }
        if (isAdmin(currentUser)) loadAdminBatches();
      } else {
        lockProtectedPage();
        if (document.querySelector("[data-auth-page]")) setTimeout(openAuth, 180);
      }
      syncBottomNav();
    });
  } else {
    updateAuthUI(null);
    protectCurrentPage();
  }
} catch (e) {
  console.error(e);
  protectCurrentPage();
}

function updateAuthUI(u) {
  const area = $("authArea");
  if (!area) return;
  area.innerHTML = "";

  const b = document.createElement("button");
  b.id = "loginBtn";
  b.className = "primary";

  if (u) {
    b.textContent = "Profile";
    b.onclick = openProfile;
    area.appendChild(b);

    if (isAdmin(u)) {
      const a = document.createElement("button");
      a.className = "adminBtn";
      a.textContent = "Developer";
      a.onclick = openAdmin;
      area.appendChild(a);
    }

    const hero = $("heroLogin");
    if (hero) {
      hero.textContent = "Open Profile";
      hero.onclick = openProfile;
    }
    closeAuth();
  } else {
    b.textContent = "Login / Sign up";
    b.onclick = openAuth;
    area.appendChild(b);
    const hero = $("heroLogin");
    if (hero) {
      hero.textContent = "Login / Sign up";
      hero.onclick = openAuth;
    }
    closeProfile();
    closeAdmin();
  }
  syncBottomNav();
}

async function googleLogin() {
  if (!auth) return msg("Firebase web config is missing in Render.");
  try {
    const provider = new firebase.auth.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    await auth.signInWithPopup(provider);
  } catch (e) {
    msg(e.message || "Google sign-in failed.");
  }
}

async function emailLogin() {
  if (!auth) return msg("Firebase web config is missing in Render.");
  const email = $("email").value.trim();
  const password = $("password").value;
  if (!email || !password) return msg("Enter email and password.");
  try {
    await auth.signInWithEmailAndPassword(email, password);
  } catch (e) {
    msg(e.message || "Login failed.");
  }
}

async function signup() {
  if (!auth) return msg("Firebase web config is missing in Render.");
  const email = $("email").value.trim();
  const password = $("password").value;
  if (!email || !password) return msg("Enter email and password.");
  if (password.length < 6) return msg("Password must contain at least 6 characters.");
  try {
    await auth.createUserWithEmailAndPassword(email, password);
  } catch (e) {
    msg(e.message || "Account creation failed.");
  }
}

async function resetPassword() {
  try {
    if (!auth) throw Error("Firebase is not configured.");
    const email = $("email").value.trim();
    if (!email) throw Error("Enter your email first.");
    await auth.sendPasswordResetEmail(email);
    msg("Password reset email sent. Check your inbox.");
  } catch (e) {
    msg(e.message || "Unable to send reset email.");
  }
}

async function verifyEmail() {
  try {
    if (!currentUser) return openAuth();
    await currentUser.reload();
    currentUser = auth.currentUser;
    if (currentUser.emailVerified) {
      $("verifyStatus").textContent = "✓ Gmail verified";
      return;
    }
    await currentUser.sendEmailVerification();
    $("profileMsg").textContent = "Verification email sent. Open Gmail and verify it.";
  } catch (e) {
    $("profileMsg").textContent = e.message || "Verification could not be sent.";
  }
}

async function logout() {
  try {
    if (auth) await auth.signOut();
  } catch (e) {
    console.error(e);
  }
  currentUser = null;
  profileLoaded = false;
  closeProfile();
  closeAdmin();
  updateAuthUI(null);
  if (currentPage() !== "home") location.href = "/";
  else openAuth();
}

async function api(path, opts = {}) {
  const h = new Headers(opts.headers || {});
  if (currentUser) h.set("Authorization", "Bearer " + await currentUser.getIdToken());
  return fetch(path, { ...opts, headers: h });
}

async function loadBatches() {
  const el = $("batchList");
  if (!el) return;
  try {
    const r = await fetch("/api/batches");
    const data = await r.json();
    if (!data.length) {
      el.innerHTML = [1,2,3,4].map(y => yearCard(y, "Subjects • notes • unit-wise content")).join("");
      return;
    }
    el.innerHTML = [1,2,3,4].map(y => {
      const arr = data.filter(x => x.year === y);
      return yearCard(y, arr.length ? arr.map(x => esc(x.name)).join(" • ") : "No batch published yet");
    }).join("");
  } catch (e) {
    el.innerHTML = '<div class="output">Unable to load batches.</div>';
  }
}

function yearCard(y, desc) {
  const suffix = ["th", "st", "nd", "rd"][y] || "th";
  return `<a class="year" href="/notes" role="button"><div class="yearNum">${y}${suffix}</div><div><h3>${y}${suffix} Year</h3><p>${desc}</p></div><div class="arrow">→</div></a>`;
}

async function loadNotes() {
  const el = $("notesList");
  if (!el) return;
  try {
    const r = await fetch("/api/notes");
    const data = await r.json();
    if (!data.length) {
      el.innerHTML = '<div class="output">No notes uploaded yet. Developer can add notes from the Developer Console.</div>';
      return;
    }
    el.innerHTML = data.map(n => `<article class="noteCard">
      <div class="noteIcon">▤</div>
      <div>
        <small>${esc(n.batch_name)} • ${esc(n.subject)} • ${esc(n.unit)}</small>
        <h3>${esc(n.title)}</h3>
        <p>${esc(n.details || "Open details to see the complete content.")}</p>
        <button class="outline" onclick='showNote(${JSON.stringify(n)})'>View details</button>
        ${n.filename ? `<a class="primary linkBtn" href="/uploads/${encodeURIComponent(n.filename)}">Download</a>` : ""}
        ${n.url ? `<a class="outline linkBtn" target="_blank" rel="noopener" href="${esc(n.url)}">Open link</a>` : ""}
      </div>
    </article>`).join("");
  } catch (e) {
    el.innerHTML = '<div class="output">Notes could not be loaded.</div>';
  }
}

function showNote(n) {
  $("noteTitle").textContent = n.title || "Note";
  $("noteMeta").textContent = `${n.batch_name || "Batch"} • ${n.subject || "Subject"} • ${n.unit || "All Units"}`;
  $("noteDetail").textContent = n.details || "No additional details were added for this note.";
  let links = "";
  if (n.filename) links += `<a class="primary linkBtn" href="/uploads/${encodeURIComponent(n.filename)}">Download file</a>`;
  if (n.url) links += `<a class="outline linkBtn" target="_blank" rel="noopener" href="${esc(n.url)}">Open external link</a>`;
  $("noteLinks").innerHTML = links;
  $("noteModal").style.display = "flex";
}
function closeNote() { if ($("noteModal")) $("noteModal").style.display = "none"; }

function syncPurposeFields(prefix) {
  const purpose = $(prefix + "purpose")?.value || "course";
  const courseWrap = $(prefix + "courseWrap");
  const examWrap = $(prefix + "examWrap");
  if (!courseWrap || !examWrap) return;
  const isCourse = purpose === "course";
  courseWrap.hidden = !isCourse;
  examWrap.hidden = isCourse;
  if (isCourse) {
    if ($(prefix + "exam")) $(prefix + "exam").value = "";
  } else {
    if ($(prefix + "course")) $(prefix + "course").value = "";
  }
}

function syncProfilePurpose() {
  const purpose = $("profilePurpose")?.value || "";
  $("profileCourseWrap").hidden = purpose !== "course";
  $("profileExamWrap").hidden = purpose !== "government";
  if (purpose === "course") $("profileExam").value = "";
  if (purpose === "government") $("profileCourse").value = "";
}

async function generateQuiz() {
  if (!currentUser) return openAuth();
  const purpose = $("qpurpose").value;
  const payload = {
    purpose,
    course: purpose === "course" ? $("qcourse").value : "General",
    exam: purpose === "government" ? $("qexam").value : "General",
    subject: $("qsubject").value.trim() || "General",
    difficulty: $("qlevel").value,
    count: +$("qcount").value
  };
  $("quizOut").textContent = "Generating fresh AI/PYQ-focused questions...";
  try {
    const r = await api("/api/ai/quiz", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || "Quiz generation failed.");
    renderQuiz(d.questions || []);
  } catch (e) { $("quizOut").textContent = e.message; }
}

function renderQuiz(qs) {
  if (!qs.length) { $("quizOut").textContent = "No new questions returned. Try another subject/exam."; return; }
  $("quizOut").innerHTML = `<div class="quizHeader"><b>${qs.length} questions</b><span>Green = correct • Red = wrong</span><button class="primary" onclick="submitQuiz()">Submit quiz</button></div>` +
    qs.map((q,i) => `<div class="quizCard" id="qc${i}"><b>${i+1}. ${esc(q.question)}</b>${(q.options||[]).map((o,j)=>`<label><input type="radio" name="q${i}" value="${j}"> ${esc(o)}</label>`).join("")}<small>${esc(q.source||"AI")}</small><div class="quizExplain" id="qe${i}"></div></div>`).join("");
  window.activeQuiz = qs;
}

function submitQuiz() {
  (window.activeQuiz || []).forEach((q,i) => {
    const sel = document.querySelector(`input[name=q${i}]:checked`);
    const card = $("qc"+i);
    card.classList.remove("right","wrong");
    if (sel) card.classList.add(+sel.value === +q.answer ? "right" : "wrong");
    $("qe"+i).innerHTML = `<b>Correct answer: ${esc(q.options[q.answer] || "")}</b><br>${esc(q.explanation || "Detailed explanation unavailable.")}`;
  });
}

async function generateTest() {
  if (!currentUser) return openAuth();
  const purpose = $("tpurpose").value;
  const payload = {
    purpose,
    course: purpose === "course" ? $("tcourse").value : "General",
    exam: purpose === "government" ? $("texam").value : "General",
    subject: $("tsubject").value.trim() || "General",
    difficulty: $("tdifficulty").value,
    count: +$("tcount").value
  };
  $("testOut").textContent = "Building your exam-style test...";
  try {
    const r = await api("/api/ai/test", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || "Test generation failed.");
    startTest(d.questions || [], payload);
  } catch (e) { $("testOut").textContent = e.message; }
}

function startTest(qs,payload) {
  testState={questions:qs,payload,answers:{},perQStart:Date.now(),qTimes:{},index:0};
  testStart=Date.now();
  clearInterval(testTimer);
  if(!qs.length){$("testOut").textContent="No test questions returned.";return;}
  renderTest();
  testTimer=setInterval(()=>{const s=Math.floor((Date.now()-testStart)/1000),t=$("testClock");if(t)t.textContent=formatTime(s)},1000);
}

function renderTest(){
  const s=testState,i=s.index,q=s.questions[i];
  $("testOut").innerHTML=`<div class="testTop"><b>${esc(s.payload.exam !== "General" ? s.payload.exam : s.payload.course)} • ${esc(s.payload.subject)}</b><span id="testClock">${formatTime(Math.floor((Date.now()-testStart)/1000))}</span><span>Q ${i+1}/${s.questions.length}</span></div><div class="progress"><i style="width:${((i+1)/s.questions.length)*100}%"></i></div><div class="testQ"><small>${esc(q.level||"Exam level")} • +${q.marks??1} / −${q.negative??0}</small><h3>${i+1}. ${esc(q.question)}</h3>${(q.options||[]).map((o,j)=>`<label><input type="radio" name="topt" value="${j}" ${s.answers[i]===j?"checked":""}> ${esc(o)}</label>`).join("")}</div><div class="testNav"><button class="outline" onclick="prevQ()">Previous</button><button class="outline" onclick="nextQ()">Next</button><button class="primary" onclick="finishTest()">Final Submit</button></div>`;
}
function saveCurrent(){if(!testState)return;const x=document.querySelector('input[name="topt"]:checked');if(x)testState.answers[testState.index]=+x.value;testState.qTimes[testState.index]=Math.max(0,Math.round((Date.now()-testState.perQStart)/1000));testState.perQStart=Date.now();}
function nextQ(){saveCurrent();if(testState.index<testState.questions.length-1){testState.index++;renderTest();}}
function prevQ(){saveCurrent();if(testState.index>0){testState.index--;renderTest();}}
async function finishTest(){
  saveCurrent();clearInterval(testTimer);
  try{
    const r=await api("/api/test/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({questions:testState.questions,answers:testState.answers,duration:Math.round((Date.now()-testStart)/1000),exam:testState.payload.exam,course:testState.payload.course,subject:testState.payload.subject})});
    const d=await r.json();if(!r.ok)throw Error(d.error||"Submit failed.");
    $("testOut").innerHTML=`<div class="resultHero"><h3>Test submitted</h3><div class="resultGrid"><div><b>${d.score}</b><small>Marks</small></div><div><b>${d.accuracy.toFixed(1)}%</b><small>Accuracy</small></div><div><b>${formatTime(d.duration)}</b><small>Total time</small></div></div></div>`+d.results.map((x,i)=>`<div class="resultRow ${x.correct?"right":"wrong"}"><b>Q${i+1}: ${x.correct?"Correct":"Wrong / Unanswered"}</b><span>Level: ${esc(x.level)} • Time: ${testState.qTimes[i]||0}s</span><p>Correct option: ${esc(testState.questions[i].options[x.answer]||"")}</p><small>${esc(x.explanation)}</small></div>`).join("");
  }catch(e){$("testOut").textContent=e.message;}
}
function formatTime(s){s=Math.max(0,Number(s)||0);return `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;}

async function solveDoubt(){
  if(!currentUser)return openAuth();
  const text=$("doubtText").value.trim(),file=$("doubtImage").files[0];
  if(!text&&!file){$("doubtOut").textContent="Type, speak or upload a doubt first.";return;}
  $("doubtOut").textContent="AI is solving your doubt...";
  let image="";
  if(file) image=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=rej;r.readAsDataURL(file)});
  try{
    const r=await fetch("/api/ai/doubt",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({doubt:text,image})});
    const d=await r.json();if(!r.ok)throw Error(d.error||"Unable to solve.");
    $("doubtOut").innerHTML=`<div>${formatAiText(d.answer||"")}</div>${image?`<img class="doubtImg" src="${image}" alt="Uploaded doubt">`:""}`;
  }catch(e){$("doubtOut").textContent=e.message;}
}
function formatAiText(t){return esc(t).replace(/\n\n/g,"<br><br>").replace(/\n/g,"<br>");}
function startVoice(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("doubtOut").textContent="Voice input is not supported in this browser.";return;}const r=new SR();r.lang="en-IN";r.onresult=e=>$("doubtText").value+=($("doubtText").value?" ":"")+e.results[0][0].transcript;r.start();}
if($("doubtImage")) $("doubtImage").onchange=()=>{const f=$("doubtImage").files[0];$("doubtPreview").innerHTML=f?`<img class="doubtImg" src="${URL.createObjectURL(f)}" alt="Selected doubt">`:""};
function open3D(topic){$("threeOut").innerHTML=`<b>${esc(topic)} 3-D module</b><p>Visual module ready. Interactive content can be attached here from the Developer Console.</p><div class="modelOrb">3D</div>`;}

function localProfile(){try{return currentUser?JSON.parse(localStorage.getItem("samstudy-profile-"+currentUser.uid)||"{}"):{};}catch{return {};}}
function saveLocalProfile(p){if(currentUser)localStorage.setItem("samstudy-profile-"+currentUser.uid,JSON.stringify(p));}
function compressImage(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>{const img=new Image();img.onload=()=>{const max=512,scale=Math.min(1,max/Math.max(img.width,img.height)),c=document.createElement("canvas");c.width=Math.round(img.width*scale);c.height=Math.round(img.height*scale);c.getContext("2d").drawImage(img,0,0,c.width,c.height);resolve(c.toDataURL("image/jpeg",.82));};img.onerror=reject;img.src=r.result;};r.onerror=reject;r.readAsDataURL(file);});}

async function loadProfile(){
  if(!currentUser)return null;
  let p=localProfile();
  try{
    const r=await api("/api/profile"),d=await r.json();
    if(r.ok)p={...p,...(d.profile||{})};
  }catch(e){console.warn("Profile server unavailable; using local profile",e);}
  if($("profileEmail")) $("profileEmail").textContent=currentUser.email||p.email||"";
  if($("profileName")) $("profileName").value=p.name||currentUser.displayName||"";
  if($("profilePurpose")) $("profilePurpose").value=p.purpose||"";
  if($("profileCourse")) $("profileCourse").value=p.course||"";
  if($("profileExam")) $("profileExam").value=p.exam||"";
  if($("profilePhoto")) $("profilePhoto").src=p.photo||currentUser.photoURL||FALLBACK_LOGO;
  if($("verifyStatus")) $("verifyStatus").textContent=currentUser.emailVerified?"✓ Gmail verified":"⚠ Gmail not verified";
  syncProfilePurpose();
  profileLoaded=true;
  return p;
}

function openProfile(){if(!currentUser){openAuth();return;}$("profileModal").style.display="flex";loadProfile();syncBottomNav();}
function closeProfile(){if($("profileModal"))$("profileModal").style.display="none";syncBottomNav();}

async function saveProfile(){
  if(!currentUser)return openAuth();
  const name=$("profileName").value.trim();
  const purpose=$("profilePurpose").value;
  const course=purpose==="course"?$("profileCourse").value:"";
  const exam=purpose==="government"?$("profileExam").value:"";
  if(!name)return $("profileMsg").textContent="Enter your student name.";
  if(!purpose)return $("profileMsg").textContent="Choose your purpose.";
  if(purpose==="course"&&!course)return $("profileMsg").textContent="Choose your course.";
  if(purpose==="government"&&!exam)return $("profileMsg").textContent="Choose your government exam.";

  let photo=localProfile().photo||currentUser.photoURL||"";
  if($("profileFile").files[0])photo=await compressImage($("profileFile").files[0]);
  const local={uid:currentUser.uid,email:currentUser.email,name,purpose,course,exam,photo};
  saveLocalProfile(local);
  $("profilePhoto").src=photo||FALLBACK_LOGO;

  try{
    const fd=new FormData();fd.append("name",name);fd.append("purpose",purpose);fd.append("course",course);fd.append("exam",exam);
    if($("profileFile").files[0])fd.append("photo",$("profileFile").files[0]);
    const r=await api("/api/profile",{method:"POST",body:fd}),d=await r.json();
    if(!r.ok)throw Error(d.error||"Server profile save failed.");
    saveLocalProfile({...local,...(d.profile||{})});
    $("profileMsg").textContent="Profile saved successfully.";
  }catch(e){
    $("profileMsg").textContent="Profile saved locally, but server profile storage could not be confirmed: " + (e.message || "server error");
  }
}
if($("profileFile"))$("profileFile").onchange=()=>{const f=$("profileFile").files[0];if(f)$("profilePhoto").src=URL.createObjectURL(f);};

async function addBatch(){try{const r=await api("/api/admin/batches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({year:$("ayear").value,name:$("aname").value,description:$("adesc").value})}),d=await r.json();$("adminMsg").textContent=d.error||"Batch added successfully.";if(r.ok){loadBatches();loadAdminBatches();}}catch(e){$("adminMsg").textContent=e.message;}}
async function addNote(){try{const fd=new FormData();["batch_id","subject","unit","title","details","url"].forEach((x,i)=>fd.append(x,$(["abatch","asubject","aunit","atitle","adetails","aurl"][i]).value));if($("afile").files[0])fd.append("file",$("afile").files[0]);const r=await api("/api/admin/notes",{method:"POST",body:fd}),d=await r.json();$("adminMsg").textContent=d.error||"Content added successfully.";if(r.ok)loadNotes();}catch(e){$("adminMsg").textContent=e.message;}}
async function loadAdminBatches(){if(!isAdmin()||!$("abatch"))return;try{const r=await fetch("/api/batches"),data=await r.json();$("abatch").innerHTML=data.map(x=>`<option value="${x.id}">${x.year}${["th","st","nd","rd"][x.year]||"th"} Year — ${esc(x.name)}</option>`).join("");}catch(e){}}
function openAdmin(){if(!isAdmin())return;$("adminModal").style.display="flex";$("adminUser").textContent=currentUser.email;loadAdminBatches();}
function closeAdmin(){if($("adminModal"))$("adminModal").style.display="none";}

const savedTheme=localStorage.getItem("samstudy-theme")||"dark";
document.body.classList.toggle("light",savedTheme==="light");
function syncThemeButton(){const t=$("theme");if(!t)return;const light=document.body.classList.contains("light");t.textContent=light?"☀":"☾";t.title=light?"Switch to dark mode":"Switch to light mode";t.setAttribute("aria-label",t.title);const m=document.querySelector('meta[name="theme-color"]');if(m)m.content=light?"#f2f8fc":"#06111d";}
syncThemeButton();
if($("theme"))$("theme").onclick=()=>{document.body.classList.toggle("light");localStorage.setItem("samstudy-theme",document.body.classList.contains("light")?"light":"dark");syncThemeButton();};

if($("qpurpose"))syncPurposeFields("q");
if($("tpurpose"))syncPurposeFields("t");
if($("profilePurpose"))syncProfilePurpose();
if($("batchList"))loadBatches();
if($("notesList"))loadNotes();
syncBottomNav();

// Close modals by backdrop or Escape.
document.addEventListener("click", e => { if(e.target.classList.contains("modal")){e.target.style.display="none";syncBottomNav();} });
document.addEventListener("keydown", e => { if(e.key!=="Escape")return;document.querySelectorAll(".modal").forEach(m=>m.style.display="none");syncBottomNav(); });
