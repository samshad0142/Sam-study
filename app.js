
(function(){
  const $=s=>document.querySelector(s);

  // theme
  const toggle=$("#themeToggle");
  function syncTheme(){
    const dark=document.documentElement.dataset.theme==="dark";
    if(toggle) toggle.textContent=dark?"☀":"☾";
  }
  if(toggle) toggle.onclick=()=>{
    const next=document.documentElement.dataset.theme==="dark"?"light":"dark";
    document.documentElement.dataset.theme=next;
    localStorage.setItem("samstudy-theme",next);
    syncTheme();
  };
  syncTheme();

  // notes
  const notesGrid=$("#notesGrid");
  const loadNotes=$("#loadNotes");
  if(loadNotes){
    const render=async()=>{
      const params=new URLSearchParams();
      const y=$("#yearFilter")?.value||"";
      const s=$("#subjectFilter")?.value.trim()||"";
      const u=$("#unitFilter")?.value||"";
      if(y)params.set("year",y);if(s)params.set("subject",s);if(u)params.set("unit",u);
      const data=await fetch("/api/notes?"+params.toString()).then(r=>r.json());
      notesGrid.innerHTML="";
      if(!data.notes.length){$("#notesEmpty")?.classList.remove("hidden");return;}
      $("#notesEmpty")?.classList.add("hidden");
      data.notes.forEach(n=>{
        const card=document.createElement("article");card.className="note-card";
        card.innerHTML=`<div class="note-meta"><span class="pill">Year ${esc(n.year)}</span><span class="pill">${esc(n.subject)}</span><span class="pill">${esc(n.unit)}</span></div><h3>${esc(n.title)}</h3><p>${esc(n.description||"Study material uploaded by SamStudy developer.")}</p><a class="btn btn-soft" href="/download/${encodeURIComponent(n.filename)}">Download ↓</a>`;
        notesGrid.appendChild(card);
      });
    };
    loadNotes.onclick=render;
    render();
  }

  // quiz
  const subjectSelect=$("#quizSubject");
  const yearSelect=$("#quizYear");
  const examSelect=$("#quizExam");
  const subjectMap={
    "1":["Engineering Mathematics-I","Engineering Physics","Engineering Chemistry","Programming for Problem Solving","Fundamentals of Electrical Engineering","Fundamentals of Electronics Engineering","Environment & Ecology"],
    "2":["Engineering Mathematics-III","Data Structures","Discrete Mathematics","Object Oriented Programming","Digital Logic Design","Computer Organization","Operating Systems"],
    "3":["Design & Analysis of Algorithms","Database Management Systems","Computer Networks","Theory of Computation","Software Engineering","Web Technology","Artificial Intelligence"],
    "4":["Machine Learning","Compiler Design","Cloud Computing","Cyber Security","Distributed Systems","Internet of Things","Project / Major Project"],
    "11":["Physics","Chemistry","Mathematics","Biology","Computer Science","English"],
    "12":["Physics","Chemistry","Mathematics","Biology","Computer Science","English"]
  };
  const govtSubjects={"SSC":["Quantitative Aptitude","Reasoning","English","General Awareness"],"UPSC":["History","Geography","Polity","Economy","Science & Technology","Current Affairs"],"NEET":["Physics","Chemistry","Biology"],"Other Government Exam":["Quantitative Aptitude","Reasoning","English","General Awareness","Computer"]};
  function refreshQuizSubjects(){
    if(!subjectSelect)return;
    const y=yearSelect.value, exam=examSelect.value;
    const list=exam==="AKTU"?subjectMap[y]||[]:(govtSubjects[exam]||subjectMap[y]||["General Studies"]);
    subjectSelect.innerHTML=list.map((s,i)=>`<option value="${esc(s)}">${esc(s)}</option>`).join("");
  }
  yearSelect?.addEventListener("change",refreshQuizSubjects); examSelect?.addEventListener("change",refreshQuizSubjects); refreshQuizSubjects();
  const gen=$("#generateQuiz");
  if(gen){
    gen.onclick=async()=>{
      const area=$("#quizArea");
      area.classList.remove("hidden");
      area.innerHTML="<div class='card' style='padding:25px'>Generating a fresh quiz…</div>";
      const body={
        year:$("#quizYear").value,level:$("#quizLevel").value,
        exam:$("#quizExam").value,subject:$("#quizSubject").value||"General Studies",count:5
      };
      try{
        const res=await fetch("/api/ai/quiz",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
        const data=await res.json();
        if(!data.ok) throw new Error(data.error||"Quiz failed");
        area.innerHTML="";
        data.questions.forEach((q,i)=>{
          const card=document.createElement("article");card.className="question-card";
          const options=(q.options||[]).map((o,j)=>`<label class="option"><input type="radio" name="q${i}" value="${j}"> ${esc(o)}</label>`).join("");
          card.innerHTML=`<div class="question-number">QUESTION ${i+1}</div><h3>${esc(q.question)}</h3>${options}<details style="margin-top:12px"><summary style="cursor:pointer;color:var(--blue);font-weight:800">Show answer</summary><p style="margin-top:8px;color:var(--muted)">Correct option: ${Number(q.answer)+1}${q.explanation?` — ${esc(q.explanation)}`:""}</p></details>`;
          area.appendChild(card);
        });
      }catch(e){area.innerHTML=`<div class="card" style="padding:25px;color:#ef4444">${esc(e.message)}</div>`;}
    };
  }

  // doubt
  const solve=$("#solveDoubt");
  if(solve){
    solve.onclick=async()=>{
      const text=$("#doubtText").value.trim();
      if(!text){show("Please enter your doubt.");return;}
      const card=$("#answerCard");
      card.innerHTML="<div class='answer-placeholder'><div class='big-ai'>AI</div><h2>Solving…</h2><p>Please wait.</p></div>";
      try{
        const res=await fetch("/api/ai/doubt",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({doubt:text,context:$("#doubtContext").value.trim()})});
        const data=await res.json();
        if(!data.ok) throw new Error(data.error||"Could not solve");
        card.innerHTML=`<div class="answer-content"><div class="ai-badge">AI</div><h2>Solution</h2><div style="white-space:pre-wrap;margin-top:15px;line-height:1.75;color:var(--text)">${esc(data.answer)}</div></div>`;
      }catch(e){card.innerHTML=`<div class="answer-placeholder"><h2>Could not solve</h2><p>${esc(e.message)}</p></div>`;}
    };
  }

  // admin
  const gate=$("#adminGate"),panel=$("#adminPanel");
  if(gate && panel){
    (async()=>{
      try{
        const res=await authFetch("/api/admin/status");
        if(res.ok){
          gate.classList.add("hidden");panel.classList.remove("hidden");
        }else{
          const d=await res.json().catch(()=>({}));
          $("#adminStatus").textContent=d.error||"Developer login required.";
        }
      }catch(e){$("#adminStatus").textContent="Login first, then open this page again.";}
    })();

    $("#batchForm")?.addEventListener("submit",async e=>{
      e.preventDefault();
      const f=new FormData(e.target);
      const res=await authFetch("/api/admin/batches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(f.entries()))});
      const d=await res.json();
      show(d.ok?"Batch created.":(d.error||"Could not create batch."));
      if(d.ok)e.target.reset();
    });

    $("#noteForm")?.addEventListener("submit",async e=>{
      e.preventDefault();
      const res=await authFetch("/api/admin/notes",{method:"POST",body:new FormData(e.target)});
      const d=await res.json();
      show(d.ok?"Content uploaded.":(d.error||"Upload failed."));
      if(d.ok)e.target.reset();
    });
  }

  function esc(v){
    return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
  }
  function show(msg){
    if(window.showToast)window.showToast(msg);else alert(msg);
  }
})();
