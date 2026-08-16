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

  syncTheme();


  /* ================= AUTH / HEADER ================= */

  function updateHeader(user) {
    const login = $("#loginLink");
    const profile = $("#profileLink");
    const logout = $("#logoutBtn");
    const photo = $("#headerProfilePhoto");

    if (user) {
      if (login) login.classList.add("hidden");
      if (logout) logout.classList.add("hidden");

      if (profile) {
        profile.classList.remove("hidden");
        profile.href = "/profile";
      }

      if (photo) {
        photo.src =
          user.photoURL ||
          "https://ui-avatars.com/api/?name=" +
            encodeURIComponent(user.displayName || "Student");
        photo.classList.remove("hidden");
      }
    } else {
      if (login) login.classList.remove("hidden");
      if (profile) profile.classList.add("hidden");
      if (logout) logout.classList.add("hidden");
      if (photo) photo.classList.add("hidden");
    }
  }

  if (window.samAuth) {
    window.samAuth.onAuthStateChanged(updateHeader);
  }

  $("#logoutBtn")?.addEventListener("click", async () => {
    try {
      await window.samAuth.signOut();
      location.href = "/";
    } catch (e) {
      show("Logout failed.");
    }
  });


  /* ================= PROFILE ================= */

  if (location.pathname === "/profile" && window.samAuth) {
    window.samAuth.onAuthStateChanged(user => {
      if (!user) {
        location.href = "/login";
        return;
      }

      const name = $("#studentName");
      const email = $("#studentEmail");
      const photo = $("#profilePhoto");

      if (name && !name.value) {
        name.value = user.displayName || "";
      }

      if (email) {
        email.textContent = user.email || "";
      }

      if (photo) {
        photo.src =
          user.photoURL ||
          "https://ui-avatars.com/api/?name=" +
            encodeURIComponent(user.displayName || "Student");
      }

      const verified = $("#emailVerified");

      if (verified) {
        verified.textContent = user.emailVerified
          ? "✓ Gmail verified"
          : "⚠ Gmail not verified";
      }
    });
  }


  /* ================= NOTES ================= */

  const notesGrid = $("#notesGrid");
  const loadNotes = $("#loadNotes");

  if (loadNotes) {
    const render = async () => {
      try {
        const params = new URLSearchParams();

        const y = $("#yearFilter")?.value || "";
        const s = $("#subjectFilter")?.value.trim() || "";
        const u = $("#unitFilter")?.value || "";

        if (y) params.set("year", y);
        if (s) params.set("subject", s);
        if (u) params.set("unit", u);

        const data =
          await fetch("/api/notes?" + params.toString()).then(r => r.json());

        if (!notesGrid) return;

        notesGrid.innerHTML = "";

        if (!data.notes.length) {
          $("#notesEmpty")?.classList.remove("hidden");
          return;
        }

        $("#notesEmpty")?.classList.add("hidden");

        data.notes.forEach(n => {
          const card = document.createElement("article");
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

            <a class="btn btn-soft"
               href="/download/${encodeURIComponent(n.filename)}">
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


  /* ================= QUIZ SUBJECTS ================= */

  const subjectSelect = $("#quizSubject");
  const yearSelect = $("#quizYear");
  const examSelect = $("#quizExam");

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
    ],

    "11": [
      "Physics",
      "Chemistry",
      "Mathematics",
      "Biology",
      "Computer Science",
      "English"
    ],

    "12": [
      "Physics",
      "Chemistry",
      "Mathematics",
      "Biology",
      "Computer Science",
      "English"
    ]
  };


  const govtSubjects = {
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

    "NEET": [
      "Physics",
      "Chemistry",
      "Biology"
    ],

    "JEE Mains": [
      "Physics",
      "Chemistry",
      "Mathematics"
    ],

    "JEE Advanced": [
      "Physics",
      "Chemistry",
      "Mathematics"
    ],

    "GATE": [
      "Engineering Mathematics",
      "Computer Science",
      "Aptitude"
    ],

    "Army": [
      "Mathematics",
      "Reasoning",
      "General Knowledge",
      "General Science"
    ],

    "Other Government Exam": [
      "Quantitative Aptitude",
      "Reasoning",
      "English",
      "General Awareness",
      "Computer"
    ]
  };


  function refreshQuizSubjects() {
    if (!subjectSelect) return;

    const y = yearSelect?.value || "1";
    const exam = examSelect?.value || "AKTU";

    let list;

    if (exam === "AKTU") {
      list = subjectMap[y] || [];
    } else {
      list =
        govtSubjects[exam] ||
        subjectMap[y] ||
        ["General Studies"];
    }

    subjectSelect.innerHTML = list
      .map(
        s =>
          `<option value="${esc(s)}">${esc(s)}</option>`
      )
      .join("");
  }

  yearSelect?.addEventListener("change", refreshQuizSubjects);
  examSelect?.addEventListener("change", refreshQuizSubjects);

  refreshQuizSubjects();


  /* ================= QUIZ ================= */

  const gen = $("#generateQuiz");

  if (gen) {
    gen.onclick = async () => {

      const area = $("#quizArea");

      if (!area) return;

      area.classList.remove("hidden");

      area.innerHTML = `
        <div class="card" style="padding:25px">
          Generating a fresh quiz…
        </div>
      `;

      const countElement =
        $("#quizCount") ||
        $("#questionCount");

      const count = countElement
        ? Number(countElement.value || 5)
        : 5;

      const body = {
        year: $("#quizYear")?.value || "1",
        level: $("#quizLevel")?.value || "Beginner",
        exam: $("#quizExam")?.value || "AKTU",
        subject:
          $("#quizSubject")?.value ||
          "General Studies",
        count: Math.min(Math.max(count, 3), 50)
      };

      try {

        const res = await fetch("/api/ai/quiz", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(body)
        });

        const data = await res.json();

        if (!data.ok) {
          throw new Error(data.error || "Quiz failed");
        }

        const questions = data.questions || [];

        if (!questions.length) {
          throw new Error("No questions generated.");
        }

        let current = 0;
        let score = 0;
        let answered = 0;
        let startTime = Date.now();

        function renderQuestion() {

          const q = questions[current];

          area.innerHTML = `
            <article class="question-card">

              <div class="question-number">
                QUESTION ${current + 1} / ${questions.length}
              </div>

              <h3>${esc(q.question)}</h3>

              <div id="optionsArea">
                ${(q.options || [])
                  .map(
                    (o, j) => `
                      <label
                        class="option"
                        data-option="${j}"
                        style="display:block;cursor:pointer;margin:10px 0"
                      >
                        <input
                          type="radio"
                          name="currentQuestion"
                          value="${j}"
                        >
                        ${esc(o)}
                      </label>
                    `
                  )
                  .join("")}
              </div>

              <div
                id="questionResult"
                style="margin-top:15px"
              ></div>

              <div
                style="
                  display:flex;
                  gap:10px;
                  flex-wrap:wrap;
                  margin-top:20px;
                "
              >

                <button
                  class="btn btn-soft"
                  id="submitAnswer"
                >
                  Submit Answer
                </button>

                <button
                  class="btn btn-soft"
                  id="nextQuestion"
                  style="display:none"
                >
                  Next Question →
                </button>

                <button
                  class="btn btn-soft"
                  id="finishQuiz"
                  style="
                    border-color:#ef4444;
                    color:#ef4444;
                  "
                >
                  Submit Test
                </button>

              </div>

            </article>
          `;

          const submit = $("#submitAnswer");
          const next = $("#nextQuestion");
          const finish = $("#finishQuiz");
          const result = $("#questionResult");

          let submitted = false;

          submit.onclick = () => {

            if (submitted) return;

            const selected =
              document.querySelector(
                'input[name="currentQuestion"]:checked'
              );

            if (!selected) {
              show("Please select an answer first.");
              return;
            }

            submitted = true;
            answered++;

            const selectedIndex =
              Number(selected.value);

            const correctIndex =
              Number(q.answer);

            const labels =
              document.querySelectorAll(".option");

            labels.forEach((label, index) => {

              if (index === correctIndex) {
                label.style.border =
                  "2px solid #22c55e";
                label.style.color =
                  "#22c55e";
              }

              if (
                index === selectedIndex &&
                selectedIndex !== correctIndex
              ) {
                label.style.border =
                  "2px solid #ef4444";
                label.style.color =
                  "#ef4444";
              }
            });

            if (selectedIndex === correctIndex) {
              score++;

              result.innerHTML = `
                <div style="color:#22c55e;font-weight:800">
                  ✓ Correct Answer
                </div>
              `;
            } else {

              result.innerHTML = `
                <div style="color:#ef4444;font-weight:800">
                  ✕ Wrong Answer
                </div>

                <div style="margin-top:8px">
                  <b>Correct Answer:</b>
                  ${esc(q.options[correctIndex] || "")}
                </div>
              `;
            }

            if (q.explanation) {
              result.innerHTML += `
                <div
                  style="
                    margin-top:12px;
                    line-height:1.7;
                  "
                >
                  <b>Detailed Explanation:</b><br>
                  ${esc(q.explanation)}
                </div>
              `;
            }

            submit.style.display = "none";

            if (current < questions.length - 1) {
              next.style.display = "inline-block";
            } else {
              finish.textContent = "View Result";
            }
          };


          next.onclick = () => {

            if (current < questions.length - 1) {
              current++;
              renderQuestion();
            }
          };


          finish.onclick = () => {
            showResult();
          };
        }


        function showResult() {

          const totalTime =
            Math.round(
              (Date.now() - startTime) / 1000
            );

          const accuracy =
            answered === 0
              ? 0
              : Math.round(
                  (score / answered) * 100
                );

          area.innerHTML = `
            <article
              class="card"
              style="padding:25px"
            >

              <h2>Test Result</h2>

              <p>
                <b>Score:</b>
                ${score} / ${questions.length}
              </p>

              <p>
                <b>Attempted:</b>
                ${answered} / ${questions.length}
              </p>

              <p>
                <b>Accuracy:</b>
                ${accuracy}%
              </p>

              <p>
                <b>Time Used:</b>
                ${formatTime(totalTime)}
              </p>

              <button
                class="btn btn-soft"
                id="restartQuiz"
              >
                Take Another Test
              </button>

            </article>
          `;

          $("#restartQuiz").onclick = () => {
            gen.click();
          };
        }


        renderQuestion();

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


  /* ================= DOUBT ================= */

  const solve = $("#solveDoubt");

  if (solve) {

    solve.onclick = async () => {

      const
