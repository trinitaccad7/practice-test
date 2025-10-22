import json
import random
import time
from pathlib import Path
import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="Practice Test", page_icon="📝", layout="centered")
st.title("📝 Practice Test")
#st.caption("Pick a subject and test, or mix everything. You can also upload a custom JSON.")

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
QUESTIONS_ROOT = BASE_DIR / "questions"  # expects questions/<subject>/*.json

# Optional upload (overrides built-ins if provided)
#uploaded = st.file_uploader("Upload your JSON question file", type=["json"])

# ---------- Helpers ----------
def read_json(path: Path):
    """Read JSON list of questions from disk."""
    return json.loads(path.read_text(encoding="utf-8"))

def normalize_and_shuffle(qs, shuffle_choices: bool):
    """
    Normalize answers to index for MCQs if answer is text or list of texts;
    optionally shuffle choices while keeping correct answer(s) aligned.
    """
    for q in qs:
        if q.get("choices"):
            ch = q.get("choices", [])
            ans = q.get("answer")

            # Normalize to indices
            if isinstance(ans, list):
                # Accept list of ints/strings; convert to unique, sorted indices
                idxs = []
                for a in ans:
                    if isinstance(a, int) and 0 <= a < len(ch):
                        idxs.append(a)
                    elif isinstance(a, str) and a in ch:
                        idxs.append(ch.index(a))
                q["answer"] = sorted(set(idxs))
            elif isinstance(ans, str) and ans in ch:
                q["answer"] = ch.index(ans)
            # else: assume int or malformed; leave as-is

            # Shuffle choices if requested
            if shuffle_choices:
                correct_idx = q.get("answer")
                order = list(range(len(ch)))
                random.shuffle(order)
                q["choices"] = [ch[i] for i in order]

                # Remap answer(s) to new positions
                if isinstance(correct_idx, int) and 0 <= correct_idx < len(order):
                    q["answer"] = order.index(correct_idx)
                elif isinstance(correct_idx, list):
                    remapped = []
                    for ci in correct_idx:
                        if isinstance(ci, int) and 0 <= ci < len(order):
                            remapped.append(order.index(ci))
                    q["answer"] = sorted(set(remapped))
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
    '''
    if uploaded is not None:
        try:
            return json.load(uploaded)
        except Exception as e:
            st.error(f"Could not read uploaded file: {e}")
            return []
    '''
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
    st.info("Pick Subject and Test, then press Start / Restart quiz. Press Submit to go to next question")
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
        is_mcq = bool(q.get("choices"))
        is_two_correct = False

        # Determine if this MCQ has exactly two correct answers
        if is_mcq:
            ans = q.get("answer")
            if isinstance(ans, list) and len(ans) == 2:
                is_two_correct = True

        # ----- Render input widget -----
        if is_mcq:
            if is_two_correct:
                # Multi-select for exactly two correct answers
                answer_widget_value = st.multiselect(
                    "Choose two:",
                    q["choices"],
                    key=f"multi_{i}",
                )
            else:
                answer_widget_value = st.radio(
                    "Choose one:",
                    q["choices"],
                    index=None,
                    key=f"radio_{i}"
                )
        else:
            answer_widget_value = st.text_input("Your answer:", key=f"text_{i}")

        c1, c2 = st.columns(2)
        with c1:
            submitted = st.button("Submit", key=f"submit_{i}", type="primary")
        with c2:
            skipped = st.button("Skip", key=f"skip_{i}")

        if submitted:
            correct = False

            if is_mcq:
                # Build canonical correct indices list (supports int or list[int])
                if isinstance(q.get("answer"), int):
                    correct_indices = [q["answer"]]
                elif isinstance(q.get("answer"), list):
                    correct_indices = sorted(set(int(x) for x in q["answer"]))
                else:
                    # Fallback: try to resolve string to index
                    if isinstance(q.get("answer"), str) and q["answer"] in q["choices"]:
                        correct_indices = [q["choices"].index(q["answer"])]
                    else:
                        correct_indices = []

                if is_two_correct:
                    # Must choose exactly two
                    if not answer_widget_value or len(answer_widget_value) != 2:
                        st.warning("Please select exactly two options before submitting.")
                        st.stop()
                    user_indices = [q["choices"].index(v) for v in answer_widget_value]
                    correct = set(user_indices) == set(correct_indices)
                else:
                    if answer_widget_value is None:
                        st.warning("Please select an option before submitting.")
                        st.stop()
                    user_index = q["choices"].index(answer_widget_value)
                    correct = (user_index == correct_indices[0] if correct_indices else False)
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
                    if is_mcq:
                        # Build readable correct answer text(s)
                        if isinstance(q.get("answer"), int):
                            ans_txts = [q["choices"][q["answer"]]] if 0 <= q["answer"] < len(q["choices"]) else []
                        elif isinstance(q.get("answer"), list):
                            ans_txts = [q["choices"][idx] for idx in q["answer"] if 0 <= idx < len(q["choices"])]
                        elif isinstance(q.get("answer"), str):
                            ans_txts = [q["answer"]]
                        else:
                            ans_txts = []

                        if is_two_correct:
                            st.error("❌ Incorrect. Correct answers: " + ", ".join(map(str, ans_txts)) if ans_txts else "N/A")
                        else:
                            st.error(f"❌ Incorrect. Answer: {ans_txts[0] if ans_txts else 'N/A'}")
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
                    # Determine correct indices set
                    if isinstance(q.get("answer"), int):
                        correct_set = {q["answer"]}
                    elif isinstance(q.get("answer"), list):
                        correct_set = set(q["answer"])
                    else:
                        if isinstance(q.get("answer"), str) and q["answer"] in q["choices"]:
                            correct_set = {q["choices"].index(q["answer"])}
                        else:
                            correct_set = set()

                    for j, c in enumerate(q["choices"]):
                        mark = "✅" if j in correct_set else ""
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
