
import json, random, time
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Practice Test", page_icon="📝", layout="centered")

st.title("📝 Practice Test")
st.caption("Mobile-friendly quiz app. Upload your JSON or use the built-in Chapter 1 bank.")

# --- Load questions ---
DEFAULT_JSON = Path(__file__).with_name("chapter_1_test_questions.json")
uploaded = st.file_uploader("Upload a questions JSON (optional)", type=["json"], help="If not provided, the built-in Chapter 1 questions will be used.")

def load_questions():
    if uploaded is not None:
        try:
            return json.load(uploaded)
        except Exception as e:
            st.error(f"Could not read uploaded file: {e}")
            return []
    else:
        if DEFAULT_JSON.exists():
            try:
                return json.loads(DEFAULT_JSON.read_text(encoding="utf-8"))
            except Exception as e:
                st.error(f"Could not load default question bank: {e}")
                return []
        else:
            st.warning("No question file found. Please upload a JSON file.")
            return []

questions = load_questions()

# --- Sidebar controls ---
with st.sidebar:
    st.header("Settings")
    shuffle_q = st.checkbox("Shuffle questions", True)
    shuffle_c = st.checkbox("Shuffle choices", True)
    reveal = st.checkbox("Reveal immediately after each submission", True)
    time_limit_min = st.number_input("Time limit (minutes, 0 = none)", 0, 240, 0)
    st.markdown("---")
    st.caption("Tip: Add this site to your phone's Home Screen for an app-like experience.")

if "state" not in st.session_state:
    st.session_state.state = {}

def init_quiz():
    qs = questions[:]
    if shuffle_q:
        random.shuffle(qs)
    # Normalize and optionally shuffle choices
    for q in qs:
        if q.get("choices"):
            # If answer given as text, normalize to index
            if isinstance(q.get("answer"), str):
                try:
                    q["answer"] = q["choices"].index(q["answer"])
                except Exception:
                    pass
            if shuffle_c:
                # Keep track of correct answer when shuffling
                correct = q.get("answer")
                ch = q.get("choices", [])[:]
                order = list(range(len(ch)))
                random.shuffle(order)
                shuffled = [ch[i] for i in order]
                if isinstance(correct, int) and 0 <= correct < len(order):
                    new_idx = order.index(correct)
                    q["answer"] = new_idx
                q["choices"] = shuffled
    st.session_state.qs = qs
    st.session_state.i = 0
    st.session_state.score = 0
    st.session_state.done = False
    st.session_state.answers = []  # list of dicts: {idx, user, correct_bool}
    st.session_state.start = time.time()
    st.session_state.deadline = (st.session_state.start + time_limit_min*60) if time_limit_min else None

def time_left_str():
    if not st.session_state.get("deadline"):
        return None
    remain = int(st.session_state.deadline - time.time())
    if remain < 0: remain = 0
    m, s = divmod(remain, 60)
    return f"{m:d}:{s:02d}"

def end_quiz():
    st.session_state.done = True

if st.button("Start / Restart quiz", type="primary"):
    init_quiz()

if "qs" not in st.session_state or not st.session_state.get("qs"):
    st.info("Load questions and press **Start / Restart quiz**.")
else:
    qs = st.session_state.qs
    i = st.session_state.i
    n = len(qs)

    # Timer / progress
    cols = st.columns(3)
    with cols[0]:
        st.metric("Question", f"{min(i+1,n)}/{n}")
    with cols[1]:
        st.metric("Score", f"{st.session_state.score}")
    with cols[2]:
        tl = time_left_str()
        st.metric("Time left", tl if tl is not None else "∞")

    if st.session_state.deadline and time.time() >= st.session_state.deadline:
        st.warning("⏰ Time is up!")
        end_quiz()

    if not st.session_state.done and i < n:
        q = qs[i]
        st.subheader(q["prompt"])

        user_choice = None
        if q.get("choices"):
            user_choice = st.radio("Choose one:", q["choices"], index=None, key=f"radio_{i}")
        else:
            user_choice = st.text_input("Your answer:", key=f"text_{i}")

        c1, c2 = st.columns([1,1])
        with c1:
            submitted = st.button("Submit", key=f"submit_{i}", type="primary")
        with c2:
            skip = st.button("Skip", key=f"skip_{i}")

        if submitted:
            correct = False
            if q.get("choices"):
                if user_choice is None:
                    st.warning("Please select an option before submitting.")
                else:
                    correct_idx = q["answer"] if isinstance(q["answer"], int) else q["choices"].index(q["answer"])
                    correct = (q["choices"].index(user_choice) == correct_idx)
            else:
                def norm(s): return (s or "").strip().lower()
                acceptable = q["answer"] if isinstance(q["answer"], list) else [q["answer"]]
                correct = norm(user_choice) in [norm(a) for a in acceptable]

            st.session_state.answers.append({"q_index": i, "user": user_choice, "correct": bool(correct)})
            if correct:
                st.session_state.score += 1

            if reveal:
                if correct:
                    st.success("✅ Correct!")
                else:
                    if q.get("choices"):
                        if isinstance(q["answer"], int) and q.get("choices"):
                            ans_text = q["choices"][q["answer"]]
                        elif isinstance(q["answer"], str):
                            ans_text = q["answer"]
                        else:
                            ans_text = "N/A"
                        st.error(f"❌ Incorrect. Answer: {ans_text}")
                    else:
                        ac = q["answer"] if isinstance(q["answer"], list) else [q["answer"]]
                        st.error("❌ Incorrect.")
                        st.write("Accepted answers: " + ", ".join(map(str, ac)))
                if q.get("explanation"):
                    st.caption(q["explanation"])

            st.session_state.i += 1
            if st.session_state.i >= n:
                end_quiz()

        if skip:
            st.session_state.answers.append({"q_index": i, "user": None, "correct": False})
            st.session_state.i += 1
            if st.session_state.i >= n:
                end_quiz()

    if st.session_state.done:
        st.success("🎉 Quiz finished!")
        st.write(f"Score: **{st.session_state.score} / {len(st.session_state.qs)}**")
        # Review section
        with st.expander("Review answers"):
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            for idx, rec in enumerate(st.session_state.answers, 1):
                q = st.session_state.qs[rec["q_index"]]
                st.markdown(f"**Q{idx}. {q['prompt']}**")
                if q.get("choices"):
                    for j, c in enumerate(q["choices"]):
                        mark = "✅" if isinstance(q["answer"], int) and j == q["answer"] else " "
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
