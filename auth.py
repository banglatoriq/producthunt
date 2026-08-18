"""
auth.py — সহজ কিন্তু কাজের পাসওয়ার্ড গেট।

দুইভাবে পাসওয়ার্ড সেট করা যায় (.streamlit/secrets.toml ফাইলে):

  1) সরাসরি টেক্সট  :  APP_PASSWORD = "আমার-গোপন-পাসওয়ার্ড"
  2) SHA-256 হ্যাশ   :  APP_PASSWORD_HASH = "a1b2c3..."   ← এটাই ভালো

হ্যাশ বানাতে টার্মিনালে:
  python -c "import hashlib;print(hashlib.sha256('তোমার-পাসওয়ার্ড'.encode()).hexdigest())"

নোট: এটি একটি প্রাইভেট, একক-ব্যবহারকারীর টুলের জন্য যথেষ্ট। এটা পূর্ণাঙ্গ
অথেনটিকেশন সিস্টেম নয় — পাবলিক ইন্টারনেটে হোস্ট করলে অবশ্যই HTTPS ব্যবহার
করবে এবং পাসওয়ার্ড কখনো git-এ কমিট করবে না।
"""

import hashlib
import hmac
import time

import streamlit as st

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300          # ৫ মিনিট
SESSION_HOURS = 12             # এতক্ষণ পর আবার লগইন লাগবে


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _matches(entered: str) -> bool:
    hashed = st.secrets.get("APP_PASSWORD_HASH", "")
    if hashed:
        return hmac.compare_digest(_sha256(entered), hashed.strip().lower())
    plain = st.secrets.get("APP_PASSWORD", "")
    if plain:
        return hmac.compare_digest(entered, plain)
    return False


def _secret_configured() -> bool:
    return bool(st.secrets.get("APP_PASSWORD_HASH", "") or st.secrets.get("APP_PASSWORD", ""))


def logout():
    for key in ("authed", "auth_time", "attempts", "locked_until"):
        st.session_state.pop(key, None)
    st.rerun()


def require_login() -> bool:
    """
    লগইন না থাকলে ফর্ম দেখায় এবং False রিটার্ন করে।
    লগইন থাকলে True রিটার্ন করে।
    """
    # সেশন এক্সপায়ার
    if st.session_state.get("authed"):
        age_h = (time.time() - st.session_state.get("auth_time", 0)) / 3600
        if age_h > SESSION_HOURS:
            st.session_state["authed"] = False
        else:
            return True

    st.markdown("## 🔒 প্রাইভেট টুল")

    if not _secret_configured():
        st.error(
            "পাসওয়ার্ড সেট করা নেই।\n\n"
            "`.streamlit/secrets.toml` ফাইলে `APP_PASSWORD_HASH` অথবা "
            "`APP_PASSWORD` যোগ করো। বিস্তারিত README.md-তে আছে।"
        )
        st.stop()

    # লকআউট চেক
    locked_until = st.session_state.get("locked_until", 0)
    if time.time() < locked_until:
        wait = int(locked_until - time.time())
        st.error(f"অনেকবার ভুল হয়েছে। {wait // 60} মিনিট {wait % 60} সেকেন্ড পর আবার চেষ্টা করো।")
        st.stop()

    with st.form("login_form"):
        pw = st.text_input("পাসওয়ার্ড", type="password", key="pw_input")
        ok = st.form_submit_button("ঢুকো", use_container_width=True)

    if ok:
        if _matches(pw):
            st.session_state["authed"] = True
            st.session_state["auth_time"] = time.time()
            st.session_state["attempts"] = 0
            st.rerun()
        else:
            st.session_state["attempts"] = st.session_state.get("attempts", 0) + 1
            left = MAX_ATTEMPTS - st.session_state["attempts"]
            if left <= 0:
                st.session_state["locked_until"] = time.time() + LOCKOUT_SECONDS
                st.session_state["attempts"] = 0
                st.error("অনেকবার ভুল হয়েছে — ৫ মিনিটের জন্য বন্ধ।")
            else:
                st.error(f"ভুল পাসওয়ার্ড। আর {left} বার চেষ্টা করতে পারবে।")

    st.caption("এটি একটি ব্যক্তিগত প্রজেক্ট। অনুমতি ছাড়া প্রবেশ নিষেধ।")
    return False
