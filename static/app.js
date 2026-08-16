const cfg=window.FIREBASE_CONFIG||{};
let auth=null,currentUser=null,testState=null,testTimer=null,testStart=0;
const $=id=>document.getElementById(id);
const EXAMS=window.EXAM_OPTIONS||["GATE","SSC","Railway","UPSC","Army","NEET UG","NEET PG","JEE Main","JEE Advanced","AKTU","Other Government Exam"];
const FALLBACK_LOGO="/static/logo.png";
function esc(s){return String(s??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}
function fillExamSelect(id,optional=true){const e=$(id);if(!e)return;e.innerHTML=(optional?'<option value="">Select exam (optional)</option>':'')+EXAMS.map(x=>`<option>${esc(x)}</option>`).join("");}
["qexam","texam","profileExam"].forEach(id=>fillExamSelect(id,id==="profileExam"));
function isAdmin(u=currentUser){return !!u&&(window.ADMIN_EMAILS||[]).map(x=>String(x).toLowerCase()).includes((u.email||"").toLowerCase());}

try{
  if(cfg.apiKey&&cfg.projectId){
    firebase.initializeApp(cfg);auth=firebase.auth();
    auth.onAuthStateChanged(async u=>{currentUser=u;updateAuthUI(u);if(u){await loadProfile();loadAdminBatches();}});
  }
}catch(e){console.error(e)}

function updateAuthUI(u){
  const area=$("authArea");if(!area)return;area.innerHTML="";
  const b=document.createElement("button");b.id="loginBtn";b.className="primary";
  const hero=$("heroLogin");
  if(u){b.textContent="Profile";b.onclick=openProfile;area.appendChild(b);if(isAdmin(u)){const a=document.createElement("button");a.className="adminBtn";a.textContent="Developer";a.onclick=openAdmin;area.appendChild(a)}if(hero){hero.textContent="Open Profile";hero.onclick=openProfile}closeAuth()}
  else{b.textContent="Login";b.onclick=openAuth;area.appendChild(b);if(hero){hero.textContent="Login / Sign up";hero.onclick=openAuth}closeProfile();closeAdmin()}
  syncBottomNav();
}
function goTo(id){
  const el=$(id); if(!el)return;
  history.replaceState(null,"","#"+id);
  el.scrollIntoView({behavior:"smooth",block:"start"});
  syncBottomNav();
}
function syncBottomNav(){
  const hash=location.hash||"#home";
  document.querySelectorAll('.bottomNav a').forEach(a=>a.classList.toggle('active',hash===a.getAttribute('href')));
  const p=document.querySelector('.bottomNav button');
  if(p)p.classList.toggle('active',!!document.getElementById('profileModal') && document.getElementById('profileModal').style.display==='flex');
}
window.addEventListener('hashchange',()=>{syncBottomNav(); const id=(location.hash||'#home').slice(1); if($(id)) $(id).scrollIntoView({behavior:'smooth',block:'start'});});
syncBottomNav();
function openAuth(){if(currentUser){openProfile();return}$("authModal").style.display="flex"}
function closeAuth(){$("authModal").style.display="none";syncBottomNav()}
function msg(x){$("authMsg").textContent=x}
async function googleLogin(){if(!auth)return msg("Firebase web config missing. Add Firebase settings in Render.");try{await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());closeAuth()}catch(e){msg(e.message)}}
async function emailLogin(){if(!auth)return msg("Firebase web config missing. Add Firebase settings in Render.");try{await auth.signInWithEmailAndPassword($("email").value.trim(),$("password").value);closeAuth()}catch(e){msg(e.message)}}
async function signup(){if(!auth)return msg("Firebase web config missing. Add Firebase settings in Render.");try{await auth.createUserWithEmailAndPassword($("email").value.trim(),$("password").value);closeAuth()}catch(e){msg(e.message)}}
async function resetPassword(){try{if(!auth)throw Error("Firebase is not configured.");await auth.sendPasswordResetEmail($("email").value.trim());msg("Password reset email sent.")}catch(e){msg(e.message)}}
async function verifyEmail(){try{if(!currentUser)return;if(currentUser.emailVerified){$("verifyStatus").textContent="✓ Gmail verified";return}await currentUser.sendEmailVerification();$("profileMsg").textContent="Verification email sent. Open Gmail and verify it."}catch(e){$("profileMsg").textContent=e.message}}
async function logout(){
  try{if(auth)await auth.signOut()}catch(e){console.error(e)}
  currentUser=null;updateAuthUI(null);closeProfile();closeAdmin();
}
async function api(path,opts={}){
  const h=new Headers(opts.headers||{});
  if(currentUser)h.set("Authorization","Bearer "+await currentUser.getIdToken());
  return fetch(path,{...opts,headers:h});
}

async function loadBatches(){
  try{const r=await fetch("/api/batches"),data=await r.json(),el=$("batchList");
    if(!data.length){el.innerHTML=[1,2,3,4].map(y=>yearCard(y,"AKTU subjects • notes • unit-wise content")).join("");return}
    el.innerHTML=[1,2,3,4].map(y=>{const arr=data.filter(x=>x.year===y);return yearCard(y,arr.length?arr.map(x=>esc(x.name)).join(" • "):"No batch published yet")}).join("");
  }catch(e){$("batchList").innerHTML='<div class="output">Unable to load batches.</div>'}
}
function yearCard(y,desc){const s=["th","st","nd","rd"][y]||"th";return `<article class="year" onclick="location.hash='notes'" role="button"><div class="yearNum">${y}${s}</div><div><h3>${y}${s} Year</h3><p>${desc}</p></div><div class="arrow">→</div></article>`}

async function loadNotes(){
  try{const r=await fetch("/api/notes"),data=await r.json(),el=$("notesList");
    if(!data.length){el.innerHTML='<div class="output">No notes uploaded yet. Developer can add notes from the Developer Console.</div>';return}
    el.innerHTML=data.map(n=>`<article class="noteCard"><div class="noteIcon">▤</div><div><small>${esc(n.batch_name)} • ${esc(n.subject)} • ${esc(n.unit)}</small><h3>${esc(n.title)}</h3><p>${esc(n.details||"Open details to see the complete content.")}</p><button class="outline" onclick='showNote(${JSON.stringify(n)})'>View details</button>${n.filename?` <a class="primary linkBtn" href="/uploads/${encodeURIComponent(n.filename)}">Download</a>`:""}${n.url?` <a class="outline linkBtn" target="_blank" rel="noopener" href="${esc(n.url)}">Open link</a>`:""}</div></article>`).join("");
  }catch(e){$("notesList").innerHTML='<div class="output">Notes could not be loaded.</div>'}
}
function showNote(n){$("noteTitle").textContent=n.title||"Note";$("noteMeta").textContent=`${n.batch_name||"Batch"} • ${n.subject||"Subject"} • ${n.unit||"All Units"}`;$("noteDetail").textContent=n.details||"No additional details were added for this note.";let links="";if(n.filename)links+=`<a class="primary linkBtn" href="/uploads/${encodeURIComponent(n.filename)}">Download file</a>`;if(n.url)links+=`<a class="outline linkBtn" target="_blank" rel="noopener" href="${esc(n.url)}">Open external link</a>`;$("noteLinks").innerHTML=links;$("noteModal").style.display="flex"}
function closeNote(){$("noteModal").style.display="none"}

async function generateQuiz(){
  const payload={course:$("qcourse").value,exam:$("qexam").value||"General",subject:$("qsubject").value.trim()||"General",difficulty:$("qlevel").value,count:+$("qcount").value};
  $("quizOut").textContent="Generating fresh AI/PYQ-focused questions...";
  try{const r=await api("/api/ai/quiz",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw Error(d.error||"Quiz generation failed.");renderQuiz(d.questions||[])}catch(e){$("quizOut").textContent=e.message}
}
function renderQuiz(qs){
  if(!qs.length){$("quizOut").textContent="No new questions returned. Try another subject/exam.";return}
  $("quizOut").innerHTML=`<div class="quizHeader"><b>${qs.length} questions</b><span>Green = correct • Red = wrong • detailed answer after submit</span><button class="primary" onclick="submitQuiz()">Submit quiz</button></div>`+qs.map((q,i)=>`<div class="quizCard" id="qc${i}"><b>${i+1}. ${esc(q.question)}</b>${(q.options||[]).map((o,j)=>`<label><input type="radio" name="q${i}" value="${j}"> ${esc(o)}</label>`).join("")}<small>${esc(q.source||"AI")}</small><div class="quizExplain" id="qe${i}"></div></div>`).join("");window.activeQuiz=qs;
}
function submitQuiz(){(window.activeQuiz||[]).forEach((q,i)=>{const sel=document.querySelector(`input[name=q${i}]:checked`),card=$("qc"+i);card.classList.remove("right","wrong");if(sel){const ok=+sel.value===+q.answer;card.classList.add(ok?"right":"wrong")}$("qe"+i).innerHTML=`<b>Correct answer: ${esc(q.options[q.answer]||"")}</b><br>${esc(q.explanation||"Detailed explanation unavailable.")}`})}

async function generateTest(){
  const payload={course:$("tcourse").value,exam:$("texam").value||"General",subject:$("tsubject").value.trim()||"General",difficulty:$("tdifficulty").value,count:+$("tcount").value};
  $("testOut").textContent="Building your exam-style test...";
  try{const r=await api("/api/ai/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw Error(d.error||"Test generation failed.");startTest(d.questions||[],payload)}catch(e){$("testOut").textContent=e.message}
}
function startTest(qs,payload){testState={questions:qs,payload,answers:{},perQStart:Date.now(),qTimes:{},index:0};testStart=Date.now();clearInterval(testTimer);if(!qs.length){$("testOut").textContent="No test questions returned.";return}renderTest();testTimer=setInterval(()=>{const s=Math.floor((Date.now()-testStart)/1000),t=$("testClock");if(t)t.textContent=formatTime(s)},1000)}
function renderTest(){const s=testState,i=s.index,q=s.questions[i];$("testOut").innerHTML=`<div class="testTop"><b>${esc(s.payload.exam)} • ${esc(s.payload.subject)}</b><span id="testClock">${formatTime(Math.floor((Date.now()-testStart)/1000))}</span><span>Q ${i+1}/${s.questions.length}</span></div><div class="progress"><i style="width:${((i+1)/s.questions.length)*100}%"></i></div><div class="testQ"><small>${esc(q.level||"Exam level")} • +${q.marks??1} / −${q.negative??0}</small><h3>${i+1}. ${esc(q.question)}</h3>${(q.options||[]).map((o,j)=>`<label><input type="radio" name="topt" value="${j}" ${s.answers[i]===j?"checked":""}> ${esc(o)}</label>`).join("")}</div><div class="testNav"><button class="outline" onclick="prevQ()">Previous</button><button class="outline" onclick="nextQ()">Next</button><button class="primary" onclick="finishTest()">Final Submit</button></div>`}
function saveCurrent(){if(!testState)return;const x=document.querySelector('input[name="topt"]:checked');if(x)testState.answers[testState.index]=+x.value;testState.qTimes[testState.index]=Math.max(0,Math.round((Date.now()-testState.perQStart)/1000));testState.perQStart=Date.now()}
function nextQ(){saveCurrent();if(testState.index<testState.questions.length-1){testState.index++;renderTest()}}
function prevQ(){saveCurrent();if(testState.index>0){testState.index--;renderTest()}}
async function finishTest(){
  saveCurrent();clearInterval(testTimer);
  try{const r=await api("/api/test/submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({questions:testState.questions,answers:testState.answers,duration:Math.round((Date.now()-testStart)/1000),exam:testState.payload.exam,course:testState.payload.course,subject:testState.payload.subject})}),d=await r.json();if(!r.ok)throw Error(d.error||"Submit failed.");$("testOut").innerHTML=`<div class="resultHero"><h3>Test submitted</h3><div class="resultGrid"><div><b>${d.score}</b><small>Marks</small></div><div><b>${d.accuracy.toFixed(1)}%</b><small>Accuracy</small></div><div><b>${formatTime(d.duration)}</b><small>Total time</small></div></div></div>`+d.results.map((x,i)=>`<div class="resultRow ${x.correct?"right":"wrong"}"><b>Q${i+1}: ${x.correct?"Correct":"Wrong / Unanswered"}</b><span>Level: ${esc(x.level)} • Time: ${testState.qTimes[i]||0}s</span><p>Correct option: ${esc(testState.questions[i].options[x.answer]||"")}</p><small>${esc(x.explanation)}</small></div>`).join("")}catch(e){$("testOut").textContent=e.message}
}
function formatTime(s){s=Math.max(0,Number(s)||0);return `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`}

async function solveDoubt(){
  const text=$("doubtText").value.trim(),file=$("doubtImage").files[0];if(!text&&!file){$("doubtOut").textContent="Type, speak or upload a doubt first.";return}$("doubtOut").textContent="AI is solving your doubt...";
  let image="";if(file)image=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=rej;r.readAsDataURL(file)});
  try{const r=await fetch("/api/ai/doubt",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({doubt:text,image})}),d=await r.json();if(!r.ok)throw Error(d.error||"Unable to solve.");$("doubtOut").innerHTML=`<div>${formatAiText(d.answer||"")}</div>${image?`<img class="doubtImg" src="${image}" alt="Uploaded doubt">`:""}`}catch(e){$("doubtOut").textContent=e.message}
}
function formatAiText(t){return esc(t).replace(/\n\n/g,"<br><br>").replace(/\n/g,"<br>")}
function startVoice(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("doubtOut").textContent="Voice input is not supported in this browser.";return}const r=new SR();r.lang="en-IN";r.onresult=e=>$("doubtText").value+=($("doubtText").value?" ":"")+e.results[0][0].transcript;r.start()}
$("doubtImage").onchange=()=>{const f=$("doubtImage").files[0];$("doubtPreview").innerHTML=f?`<img class="doubtImg" src="${URL.createObjectURL(f)}" alt="Selected doubt">`:""}
function open3D(topic){$("threeOut").innerHTML=`<b>${esc(topic)} 3-D module</b><p>Visual module ready. Interactive content can be attached here from the Developer Console.</p><div class="modelOrb">3D</div>`}

function localProfile(){try{return currentUser?JSON.parse(localStorage.getItem("samstudy-profile-"+currentUser.uid)||"{}"):{} }catch{return {}}}
function saveLocalProfile(p){if(currentUser)localStorage.setItem("samstudy-profile-"+currentUser.uid,JSON.stringify(p))}
function compressImage(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>{const img=new Image();img.onload=()=>{const max=512,scale=Math.min(1,max/Math.max(img.width,img.height)),c=document.createElement("canvas");c.width=Math.round(img.width*scale);c.height=Math.round(img.height*scale);c.getContext("2d").drawImage(img,0,0,c.width,c.height);resolve(c.toDataURL("image/jpeg",.82))};img.onerror=reject;img.src=r.result};r.onerror=reject;r.readAsDataURL(file)})}
async function loadProfile(){
  if(!currentUser)return;let p=localProfile();
  try{const r=await api("/api/profile"),d=await r.json();if(r.ok)p={...p,...(d.profile||{})};else if(r.status!==503&&r.status!==401)throw Error(d.error||"Profile load failed")}
  catch(e){console.warn("Profile server unavailable; using local profile",e)}
  $("profileEmail").textContent=currentUser.email||p.email||"";$("profileName").value=p.name||currentUser.displayName||"";$("profileCourse").value=p.course||"";$("profileExam").value=p.exam||"";$("profilePhoto").src=p.photo||currentUser.photoURL||FALLBACK_LOGO;$("verifyStatus").textContent=currentUser.emailVerified?"✓ Gmail verified":"⚠ Gmail not verified";
}
function openProfile(){if(!currentUser){openAuth();return}$("profileModal").style.display="flex";loadProfile()}
function closeProfile(){$("profileModal").style.display="none";syncBottomNav()}
async function saveProfile(){
  const name=$("profileName").value.trim(),course=$("profileCourse").value,exam=$("profileExam").value;let photo=localProfile().photo||currentUser.photoURL||"";
  if($("profileFile").files[0])photo=await compressImage($("profileFile").files[0]);
  const local={uid:currentUser.uid,email:currentUser.email,name,course,exam,photo};saveLocalProfile(local);$("profilePhoto").src=photo||FALLBACK_LOGO;
  try{const fd=new FormData();fd.append("name",name);fd.append("course",course);fd.append("exam",exam);if($("profileFile").files[0])fd.append("photo",$("profileFile").files[0]);const r=await api("/api/profile",{method:"POST",body:fd}),d=await r.json();if(!r.ok&&r.status!==503)throw Error(d.error||"Save failed");$("profileMsg").textContent=r.ok?"Profile saved successfully.":"Profile saved on this device. Configure Firebase Admin on Render for cloud saving.";if(r.ok)saveLocalProfile({...local,...(d.profile||{})})}
  catch(e){$("profileMsg").textContent="Profile saved on this device. Server storage is not configured yet."}
}
$("profileFile").onchange=()=>{const f=$("profileFile").files[0];if(f)$("profilePhoto").src=URL.createObjectURL(f)}

async function addBatch(){try{const r=await api("/api/admin/batches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({year:$("ayear").value,name:$("aname").value,description:$("adesc").value})}),d=await r.json();$("adminMsg").textContent=d.error||"Batch added successfully.";if(r.ok){loadBatches();loadAdminBatches()}}catch(e){$("adminMsg").textContent=e.message}}
async function addNote(){try{const fd=new FormData();["batch_id","subject","unit","title","details","url"].forEach((x,i)=>fd.append(x,$(["abatch","asubject","aunit","atitle","adetails","aurl"][i]).value));if($("afile").files[0])fd.append("file",$("afile").files[0]);const r=await api("/api/admin/notes",{method:"POST",body:fd}),d=await r.json();$("adminMsg").textContent=d.error||"Content added successfully.";if(r.ok)loadNotes()}catch(e){$("adminMsg").textContent=e.message}}
async function loadAdminBatches(){if(!isAdmin()||!$("abatch"))return;try{const r=await fetch("/api/batches"),data=await r.json();$("abatch").innerHTML=data.map(x=>`<option value="${x.id}">${x.year}${["th","st","nd","rd"][x.year]||"th"} Year — ${esc(x.name)}</option>`).join("")}catch(e){}}
function openAdmin(){if(!isAdmin())return;$("adminModal").style.display="flex";$("adminUser").textContent=currentUser.email;loadAdminBatches()}
function closeAdmin(){$("adminModal").style.display="none"}

// Theme is deliberately kept independent from authentication.
const savedTheme=localStorage.getItem("samstudy-theme")||"dark";document.body.classList.toggle("light",savedTheme==="light");
function syncThemeButton(){const t=$("theme");if(!t)return;const light=document.body.classList.contains("light");t.textContent=light?"☀":"☾";t.title=light?"Switch to dark mode":"Switch to light mode";t.setAttribute("aria-label",t.title)}
syncThemeButton();$("theme").onclick=()=>{document.body.classList.toggle("light");localStorage.setItem("samstudy-theme",document.body.classList.contains("light")?"light":"dark");syncThemeButton()};
loadBatches();loadNotes();

// Make every modal button reliable on mobile: close on backdrop/Escape without touching the existing design.
document.addEventListener("click",e=>{
  if(e.target.classList.contains("modal")){e.target.style.display="none";syncBottomNav();}
});
document.addEventListener("keydown",e=>{
  if(e.key!=="Escape")return;
  document.querySelectorAll(".modal").forEach(m=>m.style.display="none");
  syncBottomNav();
});
