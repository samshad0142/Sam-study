(function () {

  const $ = s => document.querySelector(s);

  /* =========================
     THEME
  ========================= */

  const toggle = $("#themeToggle");

  function syncTheme() {
    const dark =
      document.documentElement.dataset.theme === "dark";

    if (toggle) {
      toggle.textContent = dark ? "☀" : "☾";
    }
  }

  if (toggle) {
    toggle.onclick = () => {

      const next =
        document.documentElement.dataset.theme === "dark"
          ? "light"
          : "dark";

      document.documentElement.dataset.theme = next;

      localStorage.setItem(
        "samstudy-theme",
        next
      );

      syncTheme();
    };
  }

  syncTheme();


  /* =========================
     NOTES
  ========================= */

  const notesGrid = $("#notesGrid");
  const loadNotes = $("#loadNotes");

  if (loadNotes) {

    const render = async () => {

      try {

        const params = new URLSearchParams();

        const y =
          $("#yearFilter")?.value || "";

        const s =
          $("#subjectFilter")?.value.trim() || "";

        const u =
          $("#unitFilter")?.value || "";

        if (y) params.set("year", y);
        if (s) params.set("subject", s);
        if (u) params.set("unit", u);

        const res =
          await fetch(
            "/api/notes?" + params.toString()
          );

        const data =
          await res.json();

        if (!notesGrid) return;

        notesGrid.innerHTML = "";

        if (
          !data.notes ||
          !data.notes.length
        ) {

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
              <span class="pill">
                Year ${esc(n.year)}
              </span>

              <span class="pill">
                ${esc(n.subject)}
              </span>

              <span class="pill">
                ${esc(n.unit)}
              </span>
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
              href="/download/${encodeURIComponent(n.filename)}">
              Download ↓
            </a>
          `;

          notesGrid.appendChild(card);
        });

      } catch (e) {

        console.error(
          "Notes error:",
          e
        );

      }
    };

    loadNotes.onclick = render;

    render();
  }


  /* =========================
     QUIZ SUBJECT DATA
  ========================= */

  const subjectSelect =
    $("#quizSubject");

  const yearSelect =
    $("#quizYear");

  const examSelect =
    $("#quizExam");

  const courseSelect =
    $("#quizCourse");


  const btechSubjects = {

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


  const otherCourseSubjects = {

    "BCA": [
      "Programming",
      "Data Structures",
      "Database Management",
      "Computer Networks",
      "Operating Systems",
      "Computer Organization",
      "Web Development"
    ],

    "MCA": [
      "Advanced Data Structures",
      "DBMS",
      "Computer Networks",
      "Operating Systems",
      "Software Engineering",
      "Artificial Intelligence",
      "Computer Architecture"
    ],

    "M.Tech": [
      "Advanced Algorithms",
      "Advanced Operating Systems",
      "Advanced DBMS",
      "Machine Learning",
      "Artificial Intelligence",
      "Computer Networks"
    ],

    "B.Pharm": [
      "Pharmaceutics",
      "Pharmaceutical Chemistry",
      "Pharmacology",
      "Pharmacognosy",
      "Human Anatomy",
      "Biochemistry"
    ],

    "B.Sc": [
      "Physics",
      "Chemistry",
      "Mathematics",
      "Biology",
      "Computer Science"
    ]

  };


  const governmentSubjects = {

    "GATE": [
      "Engineering Mathematics",
      "General Aptitude",
      "Data Structures",
      "Algorithms",
      "DBMS",
      "Operating Systems",
      "Computer Networks",
      "Computer Organization"
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
      "General Science",
      "English"
    ],

    "NEET UG": [
      "Physics",
      "Chemistry",
      "Biology"
    ],

    "NEET PG": [
      "Anatomy",
      "Physiology",
      "Biochemistry",
      "Pathology",
      "Pharmacology",
      "Medicine"
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

    "Other Government Exam": [
      "Quantitative Aptitude",
      "Reasoning",
      "English",
      "General Awareness",
      "General Science"
    ]

  };


  /* =========================
     QUIZ SUBJECT REFRESH
  ========================= */

  function refreshQuizSubjects() {

    if (!subjectSelect) return;

    const course =
      courseSelect?.value || "B.Tech";

    const year =
      yearSelect?.value || "1";

    const exam =
      examSelect?.value || "AKTU";

    let list = [];

    if (
      governmentSubjects[exam]
    ) {

      list =
        governmentSubjects[exam];

    } else if (
      course === "B.Tech"
    ) {

      list =
        btechSubjects[year] || [];

    } else {

      list =
        otherCourseSubjects[course] ||
        btechSubjects[year] ||
        [];
    }


    subjectSelect.innerHTML = `
      <option value="">
        Select subject
      </option>
    `;

    list.forEach(subject => {

      const option =
        document.createElement("option");

      option.value = subject;

      option.textContent = subject;

      subjectSelect.appendChild(option);

    });

  }


  courseSelect?.addEventListener(
    "change",
    refreshQuizSubjects
  );

  yearSelect?.addEventListener(
    "change",
    refreshQuizSubjects
  );

  examSelect?.addEventListener(
    "change",
    refreshQuizSubjects
  );

  refreshQuizSubjects();


  /* =========================
     QUIZ ENGINE
  ========================= */

  const generateQuiz =
    $("#generateQuiz");

  const quizArea =
    $("#quizArea");

  const quizResult =
    $("#quizResult");


  let quizQuestions = [];

  let currentQuestion = 0;

  let answers = [];

  let quizStartedAt = 0;

  let questionStartedAt = 0;

  let questionTimes = [];


  if (generateQuiz) {

    generateQuiz.onclick =
      async function () {

        if (!quizArea) return;


        const subject =
          subjectSelect?.value || "";

        if (!subject) {

          show(
            "Please select a subject first."
          );

          return;
        }


        const count =
          Number(
            $("#countSelect")?.value || 5
          );


        quizArea.classList.remove(
          "hidden"
        );

        if (quizResult) {

          quizResult.classList.add(
            "hidden"
          );

        }


        quizArea.innerHTML = `
          <div
            class="card"
            style="padding:25px;text-align:center">
            <h2>Generating your test…</h2>
            <p>
              Creating relevant questions.
              Please wait.
            </p>
          </div>
        `;


        const body = {

          year:
            yearSelect?.value || "1",

          course:
            courseSelect?.value ||
            "B.Tech",

          level:
            $("#quizLevel")?.value ||
            "Beginner",

          exam:
            examSelect?.value ||
            "AKTU",

          subject:
            subject,

          count:
            count

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


          if (!data.ok) {

            throw new Error(
              data.error ||
              "Quiz generation failed."
            );

          }


          if (
            !Array.isArray(
              data.questions
            ) ||
            !data.questions.length
          ) {

            throw new Error(
              "No questions were generated."
            );

          }


          quizQuestions =
            data.questions;

          currentQuestion = 0;

          answers =
            new Array(
              quizQuestions.length
            ).fill(null);

          questionTimes =
            new Array(
              quizQuestions.length
            ).fill(0);

          quizStartedAt =
            Date.now();

          questionStartedAt =
            Date.now();


          renderQuestion();

        } catch (e) {

          console.error(
            "Quiz error:",
            e
          );

          quizArea.innerHTML = `
            <div
              class="card"
              style="
                padding:25px;
                color:#ff5964">
              <h2>Quiz could not start</h2>
              <p>
                ${esc(e.message)}
              </p>
            </div>
          `;

        }

      };

  }


  /* =========================
     RENDER ONE QUESTION
  ========================= */

  function renderQuestion() {

    if (!quizArea) return;

    const q =
      quizQuestions[
        currentQuestion
      ];

    if (!q) {

      finishQuiz();

      return;

    }


    questionStartedAt =
      Date.now();


    const total =
      quizQuestions.length;


    const selected =
      answers[currentQuestion];


    quizArea.innerHTML = `

      <div class="quiz-top">

        <div class="question-progress">
          Question
          ${currentQuestion + 1}
          /
          ${total}
        </
