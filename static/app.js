(function () {
  const $ = s => document.querySelector(s);

  /* ================= THEME ================= */

  const toggle = $("#themeToggle");

  function syncTheme() {
    const dark = document.documentElement.dataset.theme === "dark";
    if (toggle) toggle.textContent = dark ? "☀" : "☾";
  }

  if (toggle) {
    toggle.onclick = () => {
      const next =
        document.documentElement.dataset.theme === "dark"
          ? "light"
          : "dark";

      document.documentElement.dataset.theme = next;
      localStorage.setItem("samstudy-theme", next);
      syncTheme();
    };
  }

  const savedTheme = localStorage.getItem("samstudy-theme");
  if (savedTheme) {
    document.documentElement.dataset.theme = savedTheme;
  }

  syncTheme();


  /* ================= AUTH / HEADER ================= */

  if (window.samAuth) {
    window.samAuth.onAuthStateChanged(async user => {

      const login = $("#loginLink");
      const profile = $("#profileLink");
      const logout = $("#logoutBtn");

      if (user) {
        if (login) login.classList.add("hidden");
        if (logout) logout.classList.add("hidden");
        if (profile) profile.classList.remove("hidden");

        const name = $("#userName");
        if (name) {
          name.textContent =
            user.displayName ||
            user.email?.split("@")[0] ||
            "Student";
        }

      } else {
        if (login) login.classList.remove("hidden");
        if (profile) profile.classList.add("hidden");
        if (logout) logout.classList.add("hidden");
      }
    });
  }


  /* ================= LOGOUT ================= */

  const logout = $("#logoutBtn");

  if (logout && window.samAuth) {
    logout.onclick = async () => {
      try {
        await window.samAuth.signOut();
        location.href = "/";
      } catch (e) {
        show(e.message);
      }
    };
  }


  /* ================= PROFILE ================= */

  const profileForm = $("#profileForm");

  if (profileForm && window.samAuth) {

    const photoInput =
      $("#profilePhoto") ||
      $("#photoInput") ||
      $("#profileImageInput");

    const photoPreview =
      $("#profilePreview") ||
      $("#profilePhotoPreview") ||
      $("#profileImage");

    const studentName =
      $("#studentName") ||
      $("#profileName") ||
      $("#name");

    const course =
      $("#course") ||
      $("#profileCourse");

    const branch =
      $("#branch") ||
      $("#profileBranch");

    const exam =
      $("#exam") ||
      $("#profileExam");

    const email =
      $("#profileEmail") ||
      $("#email");

    const verifyBtn =
      $("#verifyEmail") ||
      $("#verifyGmail");

    const profileLogout =
      $("#profileLogout") ||
      $("#profileLogoutBtn");

    let photoData = "";

    /* Load Firebase profile */

    async function loadProfile() {

      const user = window.samAuth.currentUser;

      if (!user) return;

      if (email) {
        email.value = user.email || "";
        email.textContent = user.email || "";
      }

      if (studentName) {
        studentName.value =
          user.displayName ||
          localStorage.getItem("samstudy-name") ||
          "";
      }

      if (user.photoURL && photoPreview) {
        photoPreview.src = user.photoURL;
      }

      try {

        const snap = await firebase
          .firestore()
          .collection("users")
          .doc(user.uid)
          .get();

        if (snap.exists) {

          const data = snap.data();

          if (studentName && data.name)
            studentName.value = data.name;

          if (course && data.course)
            course.value = data.course;

          if (branch && data.branch)
            branch.value = data.branch;

          if (exam && data.exam)
            exam.value = data.exam;

          if (data.photo && photoPreview) {
            photoPreview.src = data.photo;
            photoData = data.photo;
          }
        }

      } catch (e) {
        console.log("Profile load:", e);
      }

      updateVerification(user);
    }


    /* Photo */

    if (photoInput) {

      photoInput.addEventListener("change", e => {

        const file = e.target.files[0];

        if (!file) return;

        if (!file.type.startsWith("image/")) {
          show("Please select an image.");
          return;
        }

        const reader = new FileReader();

        reader.onload = event => {

          const img = new Image();

          img.onload = () => {

            const canvas = document.createElement("canvas");

            const size = 400;

            canvas.width = size;
            canvas.height = size;

            const ctx = canvas.getContext("2d");

            const scale =
              Math.max(
                size / img.width,
                size / img.height
              );

            const w = img.width * scale;
            const h = img.height * scale;

            const x = (size - w) / 2;
            const y = (size - h) / 2;

            ctx.drawImage(
              img,
              x,
              y,
              w,
              h
            );

            photoData =
              canvas.toDataURL(
                "image/jpeg",
                0.75
              );

            if (photoPreview) {
              photoPreview.src = photoData;
            }
          };

          img.src = event.target.result;
        };

        reader.readAsDataURL(file);
      });
    }


    /* Save profile */

    profileForm.addEventListener("submit", async e => {

      e.preventDefault();

      const user = window.samAuth.currentUser;

      if (!user) {
        show("Please login first.");
        return;
      }

      const name =
        studentName?.value.trim() || "";

      const selectedCourse =
        course?.value || "";

      const selectedBranch =
        branch?.value.trim() || "";

      const selectedExam =
        exam?.value || "";

      if (!name) {
        show("Please enter your student name.");
        return;
      }

      try {

        await user.updateProfile({
          displayName: name
        });

        const data = {
          name: name,
          email: user.email || "",
          course: selectedCourse,
          branch: selectedBranch,
          exam: selectedExam,
          updatedAt:
            firebase.firestore.FieldValue.serverTimestamp()
        };

        if (photoData) {
          data.photo = photoData;
        }

        await firebase
          .firestore()
          .collection("users")
          .doc(user.uid)
          .set(data, { merge: true });

        localStorage.setItem(
          "samstudy-name",
          name
        );

        show("Profile saved successfully.");

      } catch (e) {

        console.error(e);
        show(
          "Profile save failed: " +
          e.message
        );
      }
    });


    /* Gmail verification */

    function updateVerification(user) {

      const verified = user.emailVerified;

      const status =
        $("#emailVerificationStatus");

      if (status) {
        status.textContent =
          verified
            ? "✓ Gmail verified"
            : "✗ Gmail not verified";

        status.className =
          verified
            ? "verified"
            : "not-verified";
      }

      if (verifyBtn) {
        verifyBtn.style.display =
          verified ? "none" : "";
      }
    }


    if (verifyBtn) {

      verifyBtn.onclick = async () => {

        const user =
          window.samAuth.currentUser;

        if (!user) return;

        try {

          await user.sendEmailVerification();

          show(
            "Verification email sent to " +
            user.email
          );

        } catch (e) {

          show(e.message);
        }
      };
    }


    /* Profile logout */

    if (profileLogout) {

      profileLogout.onclick = async () => {

        try {

          await window.samAuth.signOut();

          location.href = "/";

        } catch (e) {

          show(e.message);
        }
      };
    }


    window.samAuth.onAuthStateChanged(user => {

      if (user) {
        loadProfile();
      }

    });
  }


  /* ================= NOTES ================= */

  const notesGrid = $("#notesGrid");
  const loadNotes = $("#loadNotes");

  if (loadNotes) {

    const render = async () => {

      const params =
        new URLSearchParams();

      const y =
        $("#yearFilter")?.value || "";

      const s =
        $("#subjectFilter")?.value.trim() || "";

      const u =
        $("#unitFilter")?.value || "";

      if (y) params.set("year", y);
      if (s) params.set("subject", s);
      if (u) params.set("unit", u);

      try {

        const data =
          await fetch(
            "/api/notes?" +
            params.toString()
          ).then(r => r.json());

        if (!notesGrid) return;

        notesGrid.innerHTML = "";

        if (!data.notes?.length) {

          $("#notesEmpty")
            ?.classList.remove("hidden");

          return;
        }

        $("#notesEmpty")
          ?.classList.add("hidden");

        data.notes.forEach(n => {

          const card =
            document.createElement("article");

          card.className = "note-card";

          card.innerHTML = `
            <div class="note-meta">
              <span class="pill">Year ${esc(n.year)}</span>
              <span class="pill">${esc(n.subject)}</span>
              <span class="pill">${esc(n.unit)}</span>
            </div>

            <h3>${esc(n.title)}</h3>

            <p>
              ${esc(
                n.description ||
                "Study material uploaded by SamStudy developer."
              )}
            </p>

            <a
              class="btn btn-soft"
              href="/download/${encodeURIComponent(n.filename)}"
            >
              Download ↓
            </a>
          `;

          notesGrid.appendChild(card);
        });

      } catch (e) {

        show("Could not load notes.");
      }
    };

    loadNotes.onclick = render;
    render();
  }


  /* ================= QUIZ ================= */

  const subjectSelect =
    $("#quizSubject");

  const yearSelect =
    $("#quizYear");

  const examSelect =
    $("#quizExam");

  const countSelect =
    $("#quizCount");

  const subjectMap = {

    "1": [
      "Engineering Mathematics-I",
      "Engineering Physics",
      "Engineering Chemistry",
      "Programming for Problem Solving",
      "Fundamentals of Electrical Engineering",
      "Fundamentals of Electronics Engineering",
      "Environment & Ecology"
    ],

    "2": [
      "Engineering Mathematics-III",
      "Data Structures",
      "Discrete Mathematics",
      "Object Oriented Programming",
      "Digital Logic Design",
      "Computer Organization",
      "Operating Systems"
    ],

    "3": [
      "Design & Analysis of Algorithms",
      "Database Management Systems",
      "Computer Networks",
      "Theory of Computation",
      "Software Engineering",
      "Web Technology",
      "Artificial Intelligence"
    ],

    "4": [
      "Machine Learning",
      "Compiler Design",
      "Cloud Computing",
      "Cyber Security",
      "Distributed Systems",
      "Internet of Things",
      "Project / Major Project"
    ]
  };


  const examSubjects = {

    "JEE Mains": [
      "Physics",
      "Chemistry",
      "Mathematics"
    ],

    "JEE Advance": [
      "Physics",
      "Chemistry",
      "Mathematics"
    ],

    "NEET UG": [
      "Physics",
      "Chemistry",
      "Biology"
    ],

    "NEET PG": [
      "Medicine",
      "Surgery",
      "Pharmacology",
      "Pathology"
    ],

    "GATE": [
      "Engineering Mathematics",
      "Programming",
      "Data Structures",
      "Algorithms",
      "Computer Networks",
      "Operating Systems",
      "DBMS"
    ],

    "SSC": [
      "Quantitative Aptitude",
      "Reasoning",
      "English",
      "General Awareness"
    ],

    "Railway": [
      "Mathematics",
      "Reasoning",
      "General Science",
      "General Awareness"
    ],

    "UPSC": [
      "History",
      "Geography",
      "Polity",
      "Economy",
      "Science & Technology",
      "Current Affairs"
    ],

    "Army": [
      "Mathematics",
      "Reasoning",
      "General Knowledge",
      "English"
    ]
  };


  function refreshQuizSubjects() {

    if (!subjectSelect) return;

    const y =
      yearSelect?.value || "1";

    const exam =
      examSelect?.value || "AKTU";

    let list;

    if (exam === "AKTU") {
      list =
        subjectMap[y] || [];
    } else {
      list =
        examSubjects[exam] || [
          "General Studies"
        ];
    }

    subjectSelect.innerHTML =
      list.map(
        s =>
          `<option value="${esc(s)}">${esc(s)}</option>`
      ).join("");
  }


  yearSelect?.addEventListener(
    "change",
    refreshQuizSubjects
  );

  examSelect?.addEventListener(
    "change",
    refreshQuizSubjects
  );

  refreshQuizSubjects();


  /* ================= AI QUIZ ================= */

  const gen =
    $("#generateQuiz");

  if (gen) {

    gen.onclick = async () => {

      const area =
        $("#quizArea");

      area.classList.remove("hidden");

      area.innerHTML = `
        <div class="card" style="padding:25px">
          Generating fresh questions…
        </div>
      `;

      const body = {

        year:
          $("#quizYear")?.value || "1",
        course: $("#quizCourse")?.value || "B.Tech",

        level:
          $("#quizLevel")?.value ||
          "Beginner",

        exam:
          $("#quizExam")?.value ||
          "AKTU",

        subject:
          $("#quizSubject")?.value ||
          "General Studies",

        count:
          Number(
            countSelect?.value || 5
          )
      };


      try {

        const res =
          await fetch(
            "/api/ai/quiz",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json"
              },
              body:
                JSON.stringify(body)
            }
          );

        const data =
          await res.json();

        if (!data.ok)
          throw new Error(
            data.error ||
            "Quiz failed"
          );

        area.innerHTML = "";

        let current = 0;
        let answers = [];

        const questions =
          data.questions || [];


        function showQuestion() {

          const q =
            questions[current];

          if (!q) {
            finishQuiz();
            return;
          }

          const options =
            (q.options || [])
              .map(
                (o, j) =>
                  `
                  <button
                    class="quiz-option"
                    data-index="${j}"
                  >
                    ${esc(o)}
                  </button>
                  `
              ).join("");


          area.innerHTML = `

            <article class="question-card">

              <div class="question-number">
                QUESTION ${current + 1}
                / ${questions.length}
              </div>

              <h3>
                ${esc(q.question)}
              </h3>

              <div class="quiz-options">
                ${options}
              </div>

              <div
                id="quizExplanation"
                style="
                  margin-top:15px;
                  display:none;
                "
              ></div>

              <div
                style="
                  display:flex;
                  gap:10px;
                  margin-top:20px;
                  flex-wrap:wrap;
                "
              >

                ${
                  current > 0
                    ? `<button
                         id="prevQuestion"
                         class="btn btn-soft"
                       >
                         Previous
                       </button>`
                    : ""
                }

                ${
                  current <
                  questions.length - 1
                    ? `<button
                         id="nextQuestion"
                         class="btn btn-primary"
                       >
                         Next Question →
                       </button>`
                    : `<button
                         id="finishQuestion"
                         class="btn btn-primary"
                       >
                         Submit Test
                       </button>`
                }

                <button
                  id="submitEarly"
                  class="btn btn-soft"
                >
                  Submit Now
                </button>

              </div>

            </article>
          `;


          document
            .querySelectorAll(
              ".quiz-option"
            )
            .forEach(btn => {

              btn.onclick = () => {

                const selected =
                  Number(
                    btn.dataset.index
                  );

                const correct =
                  Number(q.answer);

                answers[current] =
                  selected;


                document
                  .querySelectorAll(
                    ".quiz-option"
                  )
                  .forEach(b => {

                    b.disabled = true;

                    const i =
                      Number(
                        b.dataset.index
                      );

                    if (i === correct) {

                      b.style.background =
                        "#16a34a";

                      b.style.color =
                        "white";

                    } else if (
                      i === selected
                    ) {

                      b.style.background =
                        "#dc2626";

                      b.style.color =
                        "white";
                    }
                  });


                const explanation =
                  $("#quizExplanation");

                if (explanation) {

                  explanation.style.display =
                    "block";

                  explanation.innerHTML = `
                    <strong>
                      ${
                        selected === correct
                          ? "✓ Correct"
                          : "✗ Wrong"
                      }
                    </strong>

                    <p>
                      Correct answer:
                      ${esc(
                        q.options?.[correct] ||
                        ""
                      )}
                    </p>

                    ${
                      q.explanation
                        ? `<p>${esc(q.explanation)}</p>`
                        : ""
                    }
                  `;
                }
              };
            });


          $("#nextQuestion")?.addEventListener(
            "click",
            () => {

              current++;

              showQuestion();
            }
          );


          $("#prevQuestion")?.addEventListener(
            "click",
            () => {

              current--;

              showQuestion();
            }
          );


          $("#submitEarly")?.addEventListener(
            "click",
            finishQuiz
          );


          $("#finishQuestion")?.addEventListener(
            "click",
            finishQuiz
          );
        }


        function finishQuiz() {

          let correct = 0;

          questions.forEach(
            (q, i) => {

              if (
                answers[i] !== undefined &&
                Number(answers[i]) ===
                Number(q.answer)
              ) {
                correct++;
              }
            }
          );

          const attempted =
            answers.filter(
              x => x !== undefined
            ).length;

          const total =
            questions.length;

          const accuracy =
            attempted
              ? Math.round(
                  (correct / attempted) *
                  100
                )
              : 0;


          area.innerHTML = `

            <article
              class="card"
              style="padding:30px"
            >

              <h2>Test Submitted 🎯</h2>

              <p>
                Score:
                <strong>
                  ${correct}/${total}
                </strong>
              </p>

              <p>
                Attempted:
                ${attempted}/${total}
              </p>

              <p>
                Accuracy:
                ${accuracy}%
              </p>

              <button
                id="newQuiz"
                class="btn btn-primary"
              >
                Take Another Test
              </button>

            </article>
          `;

          $("#newQuiz").onclick =
            () => gen.click();
        }


        showQuestion();

      } catch (e) {

        area.innerHTML = `
          <div
            class="card"
            style="
              padding:25px;
              color:#ef4444;
            "
          >
            ${esc(e.message)}
          </div>
        `;
      }
    };
  }


  /* ================= AI DOUBT ================= */

  const solve =
    $("#solveDoubt");

  if (solve) {

    solve.onclick = async () => {

      const text =
        $("#doubtText")?.value.trim();

      if (!text) {

        show(
          "Please enter your doubt."
        );

        return;
      }

      const card =
        $("#answerCard");

      card.innerHTML = `
        <div class="answer-placeholder">
          <div class="big-ai">AI</div>
          <h2>Solving…</h2>
          <p>Please wait.</p>
        </div>
      `;


      try {

        const res =
          await fetch(
            "/api/ai/doubt",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json"
              },
              body:
                JSON.stringify({
                  doubt: text,

                  context:
                    $("#doubtContext")
                      ?.value.trim() || ""
                })
            }
          );


        const data =
          await res.json();

        if (!data.ok)
          throw new Error(
            data.error ||
            "Could not solve"
          );


        card.innerHTML = `
          <div class="answer-content">

            <div class="ai-badge">
              AI
            </div>

            <h2>
              Solution
            </h2>

            <div
              style="
                white-space:pre-wrap;
                margin-top:15px;
                line-height:1.75;
                color:var(--text);
              "
            >
              ${esc(data.answer)}
            </div>

          </div>
        `;

      } catch (e) {

        card.innerHTML = `
          <div class="answer-placeholder">
            <h2>
              Could not solve
            </h2>

            <p>
              ${esc(e.message)}
            </p>
          </div>
        `;
      }
    };
  }


  /* ================= ADMIN ================= */

  const gate =
    $("#adminGate");

  const panel =
    $("#adminPanel");

  if (gate && panel) {

    (async () => {

      try {

        const res =
          await authFetch(
            "/api/admin/status"
          );

        if (res.ok) {

          gate.classList.add(
            "hidden"
          );

          panel.classList.remove(
            "hidden"
          );

        } else {

          const d =
            await res.json()
              .catch(() => ({}));

          $("#adminStatus").textContent =
            d.error ||
            "Developer login required.";
        }

      } catch (e) {

        $("#adminStatus").textContent =
          "Login first, then open this page again.";
      }

    })();


    $("#batchForm")
      ?.addEventListener(
        "submit",
        async e => {

          e.preventDefault();

          const f =
            new FormData(e.target);

          const res =
            await authFetch(
              "/api/admin/batches",
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json"
                },
                body:
                  JSON.stringify(
                    Object.fromEntries(
                      f.entries()
                    )
                  )
              }
            );

          const d =
            await res.json();

          show(
            d.ok
              ? "Batch created."
              : d.error ||
                "Could not create batch."
          );

          if (d.ok)
            e.target.reset();
        }
      );


    $("#noteForm")
      ?.addEventListener(
        "submit",
        async e => {

          e.preventDefault();

          const res =
            await authFetch(
              "/api/admin/notes",
              {
                method: "POST",
                body:
                  new FormData(e.target)
              }
            );

          const d =
            await res.json();

          show(
            d.ok
              ? "Content uploaded."
              : d.error ||
                "Upload failed."
          );

          if (d.ok)
            e.target.reset();
        }
      );
  }


  /* ================= HELPERS ================= */

  function esc(v) {

    return String(v ?? "")
      .replace(
        /[&<>"']/g,
        m =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
          }[m])
      );
  }


  function show(msg) {

    if (window.showToast)
      window.showToast(msg);
    else
      alert(msg);
  }

})();
