import json
import random
import time
from pathlib import Path
import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="Practice Test", page_icon="📝", layout="centered")
st.title("📝 Practice Test")
st.caption("Pick a subject and test, or mix everything. You can also upload a custom JSON.")

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
QUESTIONS_ROOT = BASE_DIR / "questions"  # expects questions/<subject>/*.json

# Optional upload (overrides built-ins if provided)
uploaded = st.file_uploader("Upload a questions JSON (optional)", type=["json"])

# ---------- Helpers ----------
def read_json(path: Path):
    """Read JSON list of questions from disk."""
    return json.loads(path.read_text(encoding="utf-8"))

def normalize_and_shuffle(qs, shuffle_choices: bool):
    """
    Normalize answers to index for MCQs if answer is text;
    optionally shuffle choices while keeping correct answer aligned.
    """
    for q in qs:
        if q.get("choices"):
            # Normalize text answer to index when possible
            if isinstance(q.get("answer"), str) and q["answer"] in q["choices"]:
                q["answer"] = q["choices"].index(q["answer"])
            # Shuffle choices if requested
            if shuffle_choices:
                correct_idx = q.get("answer")
                ch = q.get("choices", [])[:]
                order = list(range(len(ch)))
                random.shuffle(order)
                q["choices"] = [ch[i] for i in order]
                if isinstance(correct_idx, int) and 0 <= correct_idx < len(order):
                    q["answer"] = order.index(correct_idx)
    return qs

def list_subjects_and_tests(root: Path):
    """
    Discover subjects (subfolders) and test files (json).
    Returns: subjects (list[str]), subject_to_tests (dict[name] -> list[Path])
    """
    subjects = []
    subject_to_tests = {}
    if root.exists():
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            tests = sorted(sub.glob("*.json"))
            if tests:  # only include subjects that have at least one JSON
                subjects.append(sub.name)
                subject_to_tests[sub.name] = tests
    return subjects, subject_to_tests

# ---------- Discover content ----------
subjects, subject_to_tests = list_subjects_and_tests(QUESTIONS_ROOT)
SUBJECT_LABELS = ["All Subjects (mix everything)"] + [s.replace("_", " ").title() for s in subjects]
SUBJECT_KEYS   = ["__ALL__"] + subjects  # parallel keys for internal use

# ---------- Sidebar controls ----------
with st.sidebar:
    st.header("Settings")

    chosen_subject_label = st.selectbox("Subject", SUBJECT_LABELS)
    chosen_subject_key = SUBJECT_KEYS[SUBJECT_LABELS.index(chosen_subject_label)]

    # Test dropdown depends on subject
    if chosen_subject_key == "__ALL__":
        test_labels = ["(All tests in all subjects)"]
    else:
        files = subject_to_tests.get(chosen_subject_key, [])
        test_labels = ["All tests (mix in subject)"] + [p.stem for p in files]

    chosen_test_label = st.selectbox("Test", test_labels)

    num_questions = st.number_input("Number of questions (0 = all)", 0, 2000, 0)
    shuffle_q = st.checkbox("Shuffle questions", True)
    shuffle_c = st.checkbox("Shuffle choices (MCQ)", True)
    reveal = st.checkbox("Reveal immediately after each submission", True)
    time_limit_min = st.number_input("Time limit (minutes, 0 = none)", 0, 240, 0)

# ---------- Load questions ----------
def load_questions():
    # 1) Uploaded JSON overrides everything
    if uploaded is not None:
        try:
            return json.load(uploaded)
        except Exception as e:
            st.error(f"Could not read uploaded file: {e}")
            return []

    # 2) Built-ins from questions/ structure
    if not subjects:
        st.warning("No built-in question banks found. Add files under questions/<subject>/*.json or upload a JSON.")
        return []

    qs = []
    if chosen_subject_key == "__ALL__":
        # Mix everything across all subjects
        for files in subject_to_tests.values():
            for f in files:
                try:
                    qs.extend(read_json(f))
                except Exception as e:
                    st.warning(f"Could not read {f.name}: {e}")
    else:
        if chosen_test_label == "All tests (mix in subject)":
            for f in subject_to_tests.get(chosen_subject_key, []):
                try:
                    qs.extend(read_json(f))
                except Exception as e:
                    st.warning(f"Could not read {f.name}: {e}")
        else:
            # Specific test file
            files = subject_to_tests.get(chosen_subject_key, [])
            # account for the "All tests" at index 0
            idx = test_labels.index(chosen_test_label) - 1
            if 0 <= idx < len(files):
                f = files[idx]
                try:
                    qs = read_json(f)
                except Exception as e:
                    st.error(f"Could not read {f.name}: {e}")
                    qs = []
    return qs

questions = load_questions()

# ---------- Quiz state ----------
if "qs" not in st.session_state:
    st.session_state.qs = []
if "i" not in st.session_state:
    st.session_state.i = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "done" not in st.session_state:
    st.session_state.done = False
if "answers" not in st.session_state:
    st.session_state.answers = []
if "deadline" not in st.session_state:
    st.session_state.deadline = None

def time_left_str():
    if not st.session_state.deadline:
        return None
    remain = int(st.session_state.deadline - time.time())
    if remain < 0:
        remain = 0
    m, s = divmod(remain, 60)
    return f"{m:d}:{s:02d}"

def init_quiz():
    qs = questions[:]

    # Sample size (random subset) if requested
    if num_questions and num_questions > 0:
        random.shuffle(qs)
        qs = qs[:num_questions]

    # Shuffle question order
    if shuffle_q:
        random.shuffle(qs)

    # Normalize and (optionally) shuffle choices
    qs = normalize_and_shuffle(qs, shuffle_choices=shuffle_c)

    st.session_state.qs = qs
    st.session_state.i = 0
    st.session_state.score = 0
    st.session_state.done = False
    st.session_state.answers = []
    start = time.time()
    st.session_state.deadline = (start + time_limit_min * 60) if time_limit_min else None

def end_quiz():
    st.session_state.done = True

# ---------- Controls ----------
if st.button("Start / Restart quiz", type="primary"):
    if not questions:
        st.warning("No questions loaded. Upload a JSON or add files under questions/<subject>/*.json.")
    else:
        init_quiz()

# ---------- Render quiz ----------
qs = st.session_state.qs
i = st.session_state.i
n = len(qs)

if n == 0:
    st.info("Load questions (upload or built-ins), then press **Start / Restart quiz**.")
else:
    # Header metrics
    cols = st.columns(3)
    with cols[0]:
        st.metric("Question", f"{min(i+1, n)}/{n}")
    with cols[1]:
        st.metric("Score", f"{st.session_state.score}")
    with cols[2]:
        tl = time_left_str()
        st.metric("Time left", tl if tl is not None else "∞")

    # Timer
    if st.session_state.deadline and time.time() >= st.session_state.deadline:
        st.warning("⏰ Time is up!")
        end_quiz()

    if not st.session_state.done and i < n:
        q = qs[i]
        st.subheader(q.get("prompt", ""))
        answer_widget_value = None

        if q.get("choices"):
            answer_widget_value = st.radio("Choose one:", q["choices"], index=None, key=f"radio_{i}")
        else:
            answer_widget_value = st.text_input("Your answer:", key=f"text_{i}")

        c1, c2 = st.columns(2)
        with c1:
            submitted = st.button("Submit", key=f"submit_{i}", type="primary")
        with c2:
            skipped = st.button("Skip", key=f"skip_{i}")

        if submitted:
            correct = False
            if q.get("choices"):
                if answer_widget_value is None:
                    st.warning("Please select an option before submitting.")
                else:
                    # Ensure answer index exists
                    correct_idx = q["answer"] if isinstance(q.get("answer"), int) else (
                        q["choices"].index(q["answer"]) if q.get("answer") in q.get("choices", []) else -1
                    )
                    correct = (q["choices"].index(answer_widget_value) == correct_idx)
            else:
                def norm(s): return (s or "").strip().lower()
                acceptable = q["answer"] if isinstance(q.get("answer"), list) else [q.get("answer", "")]
                correct = norm(answer_widget_value) in [norm(a) for a in acceptable]

            st.session_state.answers.append({
                "q_index": i,
                "user": answer_widget_value,
                "correct": bool(correct)
            })
            if correct:
                st.session_state.score += 1

            if reveal:
                if correct:
                    st.success("✅ Correct!")
                else:
                    # Show correct answer text if MCQ
                    if q.get("choices"):
                        ans_txt = None
                        if isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q["choices"]):
                            ans_txt = q["choices"][q["answer"]]
                        elif isinstance(q.get("answer"), str):
                            ans_txt = q["answer"]
                        st.error(f"❌ Incorrect. Answer: {ans_txt if ans_txt is not None else 'N/A'}")
                    else:
                        ac = q["answer"] if isinstance(q.get("answer"), list) else [q.get("answer", "")]
                        st.error("❌ Incorrect.")
                        st.write("Accepted answers: " + ", ".join(map(str, ac)))
                if q.get("explanation"):
                    st.caption(q["explanation"])

            st.session_state.i += 1
            if st.session_state.i >= n:
                end_quiz()

        if skipped:
            st.session_state.answers.append({
                "q_index": i,
                "user": None,
                "correct": False
            })
            st.session_state.i += 1
            if st.session_state.i >= n:
                end_quiz()

    # End + Review
    if st.session_state.done:
        st.success("🎉 Quiz finished!")
        st.write(f"Score: **{st.session_state.score} / {len(st.session_state.qs)}**")
        with st.expander("Review answers"):
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            for idx, rec in enumerate(st.session_state.answers, 1):
                q = st.session_state.qs[rec["q_index"]]
                st.markdown(f"**Q{idx}. {q.get('prompt','')}**")
                if q.get("choices"):
                    for j, c in enumerate(q["choices"]):
                        mark = "✅" if (isinstance(q.get("answer"), int) and j == q["answer"]) else ""
                        st.write(f"{letters[j]}. {c} {mark}")
                st.write(f"Your answer: {rec['user']}")
                st.write(f"Correct: {'Yes' if rec['correct'] else 'No'}")
                if q.get("explanation"):
                    st.caption(q["explanation"])
                st.markdown("---")
        st.download_button(
            "Download your results (JSON)",
            data=json.dumps(st.session_state.answers, indent=2),
            file_name="results.json",
            mime="application/json"
        )
