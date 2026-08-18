"""
Product Hunter BD — চায়না-টু-বাংলাদেশ ইম্পোর্ট প্রোডাক্ট রিসার্চ টুল

চালাতে:  streamlit run app.py
"""

import json
from datetime import datetime

import pandas as pd
import streamlit as st

import ai
import auth
import calc
import discover
import providers
import store

# --------------------------------------------------------------------------
# পেজ সেটআপ
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="Product Hunter BD",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1300px; }
      div[data-testid="stMetricValue"] { font-size: 1.5rem; }
      .verdict-good { background:#0f5132; color:#d1e7dd; padding:14px 18px;
                      border-radius:8px; font-weight:600; }
      .verdict-ok   { background:#664d03; color:#fff3cd; padding:14px 18px;
                      border-radius:8px; font-weight:600; }
      .verdict-bad  { background:#58151c; color:#f8d7da; padding:14px 18px;
                      border-radius:8px; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# লগইন গেট — এর আগে কিছুই দেখা যাবে না
# --------------------------------------------------------------------------

if not auth.require_login():
    st.stop()

# --------------------------------------------------------------------------
# সাইডবার
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🎯 Product Hunter BD")
    st.caption("চায়না → বাংলাদেশ প্রোডাক্ট রিসার্চ")
    st.divider()

    st.markdown("**AI প্রোভাইডার (সব ফ্রি)**")
    keys = list(providers.PROVIDERS.keys())
    saved_pref = st.secrets.get("PROVIDER", providers.DEFAULT_PROVIDER)
    prov_key = st.selectbox(
        "প্রোভাইডার",
        keys,
        index=keys.index(saved_pref) if saved_pref in keys else 0,
        format_func=lambda k: providers.PROVIDERS[k].label,
        label_visibility="collapsed",
    )
    P = providers.PROVIDERS[prov_key]

    # --- API key ---
    if P.needs_key:
        secret_name = f"{prov_key.upper()}_API_KEY"
        api_key = st.secrets.get(secret_name, "")
        if api_key:
            st.success("key লোড হয়েছে", icon="✅")
        else:
            api_key = st.text_input(
                "API Key",
                type="password",
                key=f"key_{prov_key}",
                help=f"secrets.toml-এ {secret_name} হিসেবে রাখলে প্রতিবার দিতে হবে না",
            )
            if not api_key:
                st.warning("AI ট্যাব চালাতে key লাগবে", icon="⚠️")
            st.caption(f"[ফ্রি key নাও →]({P.signup_url})")
    else:
        api_key = ""
        st.info("এই প্রোভাইডারে key লাগে না", icon="🖥️")

    # --- মডেল লিস্ট (লাইভ, ক্যাশড) ---
    cache_key = f"models_{prov_key}"
    if st.button("🔄 মডেল লিস্ট রিফ্রেশ", use_container_width=True):
        st.session_state.pop(cache_key, None)

    if cache_key not in st.session_state:
        with st.spinner("মডেল লিস্ট আনছি…"):
            st.session_state[cache_key] = providers.list_models(prov_key, api_key)

    model_list, src = st.session_state[cache_key]
    if model_list:
        model = st.selectbox("মডেল", model_list)
        if src == "fallback":
            st.caption("⚠️ লাইভ লিস্ট আনা যায়নি — অনুমান দেখানো হচ্ছে। key দিয়ে রিফ্রেশ করো।")
    else:
        model = st.text_input("মডেলের নাম হাতে লেখো", value="")

    with st.expander("এই প্রোভাইডার সম্পর্কে"):
        st.caption(P.note)
        if not P.supports_vision:
            st.caption("📷 ছবি আপলোড এখানে কাজ করবে না।")

    if st.button("🔌 কানেকশন টেস্ট", use_container_width=True):
        if not model:
            st.error("আগে মডেল বাছো")
        else:
            ok, msg = providers.test_connection(prov_key, api_key, model)
            st.success(f"কাজ করছে — {msg}") if ok else st.error(msg)

    st.divider()
    st.markdown("**ডিফল্ট রেট**")
    default_rate = st.number_input("¥1 = ৳", value=17.0, step=0.5, format="%.2f")
    default_freight = st.number_input("ফ্রেইট ৳/কেজি", value=900.0, step=50.0)
    st.caption("রেট বদলায় — এজেন্টের কাছ থেকে যাচাই করে নাও।")

    st.divider()
    rows = store.load_all()
    st.metric("সেভ করা প্রোডাক্ট", len(rows))
    if st.button("লগআউট", use_container_width=True):
        auth.logout()

# --------------------------------------------------------------------------
# ট্যাব
# --------------------------------------------------------------------------

tab_ideas, tab_calc, tab_ai, tab_score, tab_saved = st.tabs(
    [
        "💡 প্রোডাক্ট আইডিয়া",
        "💰 মার্জিন ক্যালকুলেটর",
        "🎯 পারসোনা রিসার্চ (AI)",
        "📊 স্কোরকার্ড",
        "📁 সেভ করা প্রোডাক্ট",
    ]
)


# ==========================================================================
# ট্যাব ০ — প্রোডাক্ট আইডিয়া (ডিসকভারি)
# ==========================================================================

with tab_ideas:
    st.subheader("কী প্রোডাক্ট আনব?")
    st.warning(
        "⚠️ **এগুলো আইডিয়া, প্রমাণ নয়।** AI-এর কাছে বাংলাদেশের লাইভ সেলস ডেটা নেই — "
        "এই লিস্ট শুধু শূন্য থেকে শুরু করার জন্য। প্রতিটা আইডিয়ার নিচে যাচাইয়ের "
        "লিঙ্ক আছে; **ওগুলোতে ক্লিক করে নিজের চোখে দেখাই আসল কাজ।**"
    )

    with st.form("idea_form"):
        i1, i2 = st.columns([2, 1])
        with i1:
            cats = st.multiselect(
                "ক্যাটাগরি (খালি রাখলে যেকোনো)",
                discover.CATEGORIES,
                default=[],
            )
            audience = st.text_input(
                "টার্গেট ক্রেতা (ঐচ্ছিক)",
                placeholder="যেমন: ঢাকার চাকরিজীবী নারী, বা ছোট দোকানদার",
            )
            extra = st.text_area(
                "অতিরিক্ত নির্দেশনা (ঐচ্ছিক)",
                height=70,
                placeholder="যেমন: এমন কিছু যা Daraz-এ এখনো কম পাওয়া যায়",
            )
        with i2:
            pmin, pmax = st.slider("সেল প্রাইস রেঞ্জ (৳)", 200, 6000, (800, 3000), step=100)
            season = st.selectbox("মৌসুম / উপলক্ষ", discover.SEASONS)
            n_ideas = st.slider("কয়টা আইডিয়া", 5, 15, 10)
            max_w = st.select_slider("সর্বোচ্চ ওজন (গ্রাম)", [200, 300, 500, 800, 1500], value=500)
            no_batt = st.checkbox("ব্যাটারিওয়ালা জিনিস বাদ", value=True)
            skip_seen = st.checkbox("আগে সেভ করা প্রোডাক্ট বাদ", value=True)

        go = st.form_submit_button("💡 আইডিয়া বের করো", type="primary", use_container_width=True)

    if go:
        if P.needs_key and not api_key:
            st.error("সাইডবারে API key দাও (ফ্রি — লিঙ্ক ওখানেই আছে)।")
        elif not model:
            st.error("সাইডবারে একটা মডেল বাছো।")
        else:
            seen = [r.get("name", "") for r in store.load_all()] if skip_seen else []
            with st.spinner(f"{model} আইডিয়া খুঁজছে…"):
                try:
                    st.session_state["ideas"] = discover.generate_ideas(
                        provider_key=prov_key,
                        api_key=api_key,
                        model=model,
                        categories=cats,
                        price_min=float(pmin),
                        price_max=float(pmax),
                        count=int(n_ideas),
                        season=season,
                        audience=audience.strip(),
                        extra=extra.strip(),
                        exclude=[s for s in seen if s],
                        avoid_battery=no_batt,
                        max_weight_g=int(max_w),
                    )
                except Exception as e:
                    st.error(f"সমস্যা হয়েছে: {e}")

    idea_data = st.session_state.get("ideas")
    if idea_data:
        st.divider()
        if idea_data.get("notes"):
            st.info(idea_data["notes"])

        for n, idea in enumerate(idea_data.get("ideas", [])):
            comp = idea.get("competition_guess", "")
            badge = {"কম": "🟢", "মাঝারি": "🟡", "বেশি": "🔴"}.get(comp, "⚪")
            title = f"{badge} {idea['name_bn']}"
            if idea.get("name_en"):
                title += f"  ·  {idea['name_en']}"

            with st.expander(title, expanded=(n < 3)):
                cA, cB = st.columns([3, 2])
                with cA:
                    st.markdown(f"**কেন চলতে পারে:** {idea.get('why_bd','')}")
                    st.markdown(f"**কে কিনবে:** {idea.get('who_buys','')}")
                    if idea.get("risk"):
                        st.markdown(f"**⚠️ ঝুঁকি:** {idea['risk']}")
                with cB:
                    cmin, cmax = idea["est_cny_min"], idea["est_cny_max"]
                    st.markdown(
                        f"**আনুমানিক দাম:** ¥{cmin:.0f}–{cmax:.0f}  \n"
                        f"**আনুমানিক ওজন:** {idea['est_weight_g']:.0f} গ্রাম  \n"
                        f"**প্রতিযোগিতা:** {comp or 'অজানা'}  \n"
                        f"**ক্যাটাগরি:** {idea.get('category','')}"
                    )

                st.markdown("**🔎 যাচাই করো — এখানেই আসল উত্তর:**")
                links = discover.verify_links(idea)
                names = list(links.keys())
                for row_start in range(0, len(names), 4):
                    cols = st.columns(4)
                    for col, nm in zip(cols, names[row_start : row_start + 4]):
                        col.link_button(nm, links[nm], use_container_width=True)

                st.caption(
                    "FB Ad Library-তে যে অ্যাড ৩০+ দিন চলছে সেটাই সবচেয়ে শক্ত সিগন্যাল। "
                    "Daraz-এ সেলার সংখ্যা আর সাম্প্রতিক রিভিউর তারিখ দেখো।"
                )

                b1, b2 = st.columns(2)
                if b1.button("💰 ক্যালকুলেটরে পাঠাও", key=f"tocalc_{n}", use_container_width=True):
                    st.session_state["from_idea"] = {
                        "name": idea["name_bn"],
                        "cny": (cmin + cmax) / 2 if cmax else cmin,
                        "weight": idea["est_weight_g"],
                        "desc": idea.get("why_bd", ""),
                    }
                    st.success("পাঠানো হয়েছে — 'মার্জিন ক্যালকুলেটর' ট্যাবে যাও")
                if b2.button("💾 লিস্টে সেভ করো", key=f"saveidea_{n}", use_container_width=True):
                    store.add_product(
                        {"name": idea["name_bn"], "type": "idea", "idea": idea}
                    )
                    st.success("সেভ হয়েছে")

        st.divider()
        st.download_button(
            "⬇️ পুরো লিস্ট JSON-এ নামাও",
            data=json.dumps(idea_data, ensure_ascii=False, indent=2),
            file_name="product_ideas.json",
            mime="application/json",
        )
        st.caption(
            f"মডেল: {idea_data.get('_model','')}  ·  চেষ্টা: {idea_data.get('_attempts',1)}"
        )


# ==========================================================================
# ট্যাব ১ — মার্জিন ক্যালকুলেটর
# ==========================================================================

with tab_calc:
    st.subheader("প্রোডাক্টটা আসলে লাভজনক কিনা")
    st.caption(
        "উল্টো দিক থেকে হিসাব — অ্যাড, কুরিয়ার আর COD রিটার্ন বাদ দেওয়ার পর "
        "হাতে কত থাকে সেটাই আসল সংখ্যা।"
    )

    fi = st.session_state.get("from_idea", {})
    if fi:
        st.success(f"আইডিয়া থেকে এসেছে: **{fi['name']}** — সংখ্যাগুলো আনুমানিক, 1688 দেখে ঠিক করো।")

    pname = st.text_input(
        "প্রোডাক্টের নাম",
        value=fi.get("name", ""),
        key="calc_name",
        placeholder="যেমন: মিনি নেক ম্যাসাজার",
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("##### 🇨🇳 সোর্সিং")
        cny = st.number_input(
            "1688 দাম (¥/পিস)", value=float(fi.get("cny", 30.0)), min_value=0.0, step=1.0
        )
        rate = st.number_input("¥1 = ৳", value=float(default_rate), step=0.5, format="%.2f")
        weight = st.number_input(
            "ওজন (গ্রাম/পিস)", value=float(fi.get("weight", 300.0)), min_value=1.0, step=25.0
        )
        freight = st.number_input("ফ্রেইট (৳/কেজি)", value=float(default_freight), step=50.0)
        duty = st.number_input("ডিউটি + ক্লিয়ারেন্স (%)", value=30.0, step=5.0)
        agent = st.number_input("এজেন্ট কমিশন (%)", value=5.0, step=1.0)
        packing = st.number_input("দেশে প্যাকেজিং (৳/পিস)", value=25.0, step=5.0)

    with c2:
        st.markdown("##### 🛒 বিক্রয়")
        sell = st.number_input("সেল প্রাইস (৳)", value=2500.0, min_value=1.0, step=50.0)
        qty = st.number_input("প্রথম লটে কত পিস", value=50, min_value=1, step=10)
        st.markdown("##### 📣 অর্ডারপ্রতি খরচ")
        cac = st.number_input("অ্যাড খরচ / অর্ডার (৳)", value=350.0, step=25.0)
        d_fwd = st.number_input("কুরিয়ার ফরোয়ার্ড (৳)", value=100.0, step=10.0)
        d_ret = st.number_input("রিটার্ন চার্জ (৳)", value=60.0, step=10.0)
        gateway = st.number_input("COD/গেটওয়ে চার্জ (%)", value=1.0, step=0.5)

    with c3:
        st.markdown("##### ⚠️ ঝুঁকি")
        ret_rate = st.slider("COD রিটার্ন হার (%)", 0, 60, 25)
        damage = st.slider("রিটার্নে নষ্ট হয় (%)", 0, 30, 5)
        st.markdown("##### 🎯 টার্গেট")
        target_margin = st.slider("চাই নেট মার্জিন (%)", 0, 50, 20)

    ci = calc.CostInput(
        cny_price=cny,
        cny_to_bdt=rate,
        unit_weight_g=weight,
        freight_per_kg=freight,
        duty_pct=duty,
        agent_fee_pct=agent,
        local_packaging=packing,
        sell_price=sell,
        order_qty=int(qty),
        cac=cac,
        delivery_fwd=d_fwd,
        delivery_return=d_ret,
        gateway_pct=gateway,
        return_rate_pct=float(ret_rate),
        damage_pct=float(damage),
    )
    r = calc.compute(ci)

    st.divider()

    st.markdown(
        f'<div class="verdict-{r.verdict_level}">{r.verdict}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("ল্যান্ডেড কস্ট", f"৳{r.landed_unit:,.0f}", help="প্রতি পিস, বাংলাদেশে পৌঁছে")
    m2.metric("মার্কআপ", f"{r.markup_x:.1f}x", help="সেল প্রাইস ÷ ল্যান্ডেড কস্ট")
    m3.metric("নেট প্রফিট/অর্ডার", f"৳{r.net_per_delivered:,.0f}")
    m4.metric("নেট মার্জিন", f"{r.net_margin_pct:.1f}%")
    m5.metric("লটের মোট বিনিয়োগ", f"৳{r.total_investment:,.0f}")

    st.write("")
    left, right = st.columns(2)

    with left:
        st.markdown("##### ল্যান্ডেড কস্ট ব্রেকডাউন (প্রতি পিস)")
        bd = pd.DataFrame(
            {
                "খাত": ["পণ্যের দাম", "ফ্রেইট", "ডিউটি + ক্লিয়ারেন্স", "এজেন্ট ফি", "প্যাকেজিং", "মোট"],
                "টাকা": [
                    r.product_bdt,
                    r.freight_bdt,
                    r.duty_bdt,
                    r.agent_bdt,
                    r.packaging_bdt,
                    r.landed_unit,
                ],
            }
        )
        bd["টাকা"] = bd["টাকা"].map(lambda x: f"৳{x:,.0f}")
        st.dataframe(bd, hide_index=True, use_container_width=True)

    with right:
        st.markdown("##### ১০০ অর্ডারের সিমুলেশন")
        sim = pd.DataFrame(
            {
                "খাত": [
                    f"বিক্রি ({r.delivered:.0f} ডেলিভার্ড)",
                    "− অ্যাড খরচ",
                    "− কুরিয়ার (ফরোয়ার্ড + রিটার্ন)",
                    "− COD/গেটওয়ে চার্জ",
                    "− পণ্যের খরচ (COGS)",
                    "− রিটার্নে ক্ষতি",
                    "= নেট লাভ",
                ],
                "টাকা": [
                    r.revenue_100,
                    -r.ad_cost_100,
                    -r.courier_cost_100,
                    -r.gateway_cost_100,
                    -r.cogs_100,
                    -r.damage_cost_100,
                    r.net_100,
                ],
            }
        )
        sim["টাকা"] = sim["টাকা"].map(lambda x: f"৳{x:,.0f}")
        st.dataframe(sim, hide_index=True, use_container_width=True)

    st.write("")
    p1, p2 = st.columns(2)
    be = r.breakeven_price
    need = calc.min_viable_price(ci, target_margin_pct=float(target_margin))
    p1.info(
        f"**ব্রেক-ইভেন প্রাইস: ৳{be:,.0f}**\n\n"
        f"এর নিচে বেচলে সরাসরি লস।"
        if be != float("inf")
        else "**ব্রেক-ইভেন সম্ভব নয়** — খরচের গঠন ঠিক করো।"
    )
    p2.success(
        f"**{target_margin}% মার্জিন পেতে দাম হতে হবে: ৳{need:,.0f}**"
        if need != float("inf")
        else f"**{target_margin}% মার্জিন এই খরচে সম্ভব নয়।**"
    )

    if r.warnings:
        st.markdown("##### ⚠️ যেসব দিকে নজর দাও")
        for w in r.warnings:
            st.warning(w)

    st.divider()
    sc1, sc2 = st.columns([1, 3])
    with sc1:
        if st.button("💾 এই হিসাব সেভ করো", type="primary", use_container_width=True):
            if not pname.strip():
                st.error("আগে প্রোডাক্টের নাম দাও")
            else:
                rec = calc.to_dict(ci, r)
                rec["name"] = pname.strip()
                rec["type"] = "margin"
                store.add_product(rec)
                st.success("সেভ হয়েছে")
    with sc2:
        st.caption(
            "সেভ করা হিসাব 'সেভ করা প্রোডাক্ট' ট্যাবে পাবে এবং CSV-তে নামাতে পারবে।"
        )

    # AI ট্যাবে প্রি-ফিল করার জন্য
    st.session_state["prefill"] = {
        "name": pname,
        "cny": cny,
        "landed": r.landed_unit,
        "sell": sell,
        "desc": fi.get("desc", ""),
    }


# ==========================================================================
# ট্যাব ২ — AI পারসোনা রিসার্চ
# ==========================================================================

with tab_ai:
    st.subheader("এই প্রোডাক্ট কার জন্য?")
    st.caption(
        "AI প্রোডাক্টটা বিশ্লেষণ করে বলবে কে কিনবে, কেন কিনবে, কোন অ্যাঙ্গেলে "
        "বেচতে হবে আর 1688-এ কোন কীওয়ার্ডে খুঁজতে হবে।"
    )

    pf = st.session_state.get("prefill", {})

    with st.form("ai_form"):
        a1, a2 = st.columns([2, 1])
        with a1:
            ai_name = st.text_input("প্রোডাক্টের নাম", value=pf.get("name", ""))
            ai_desc = st.text_area(
                "বিবরণ (কী জিনিস, কী কাজ করে, ফিচার)",
                value=pf.get("desc", ""),
                height=110,
                placeholder="যেমন: রিচার্জেবল, ৩টা স্পিড মোড, ঘাড় ও কাঁধে ব্যবহার করা যায়",
            )
            ai_notes = st.text_area(
                "অতিরিক্ত তথ্য (কোথায় দেখেছ, কে বেচছে, কী সিগন্যাল পেয়েছ)",
                height=80,
                placeholder="যেমন: ইন্ডিয়ার Meesho-তে ভালো চলছে, বাংলাদেশে FB-তে ২টা পেজ বেচছে",
            )
        with a2:
            ai_cny = st.number_input("চায়নায় দাম (¥)", value=float(pf.get("cny", 0.0)), step=1.0)
            ai_landed = st.number_input(
                "ল্যান্ডেড কস্ট (৳)", value=float(pf.get("landed", 0.0)), step=10.0
            )
            ai_sell = st.number_input(
                "পরিকল্পিত সেল প্রাইস (৳)", value=float(pf.get("sell", 0.0)), step=50.0
            )
            img = st.file_uploader(
                "প্রোডাক্টের ছবি (ঐচ্ছিক)",
                type=["jpg", "jpeg", "png", "webp"],
                disabled=not P.supports_vision,
                help="এই প্রোভাইডারে ছবি সাপোর্ট নেই" if not P.supports_vision else None,
            )

        run = st.form_submit_button("🔍 বিশ্লেষণ করো", type="primary", use_container_width=True)

    if run:
        if P.needs_key and not api_key:
            st.error("সাইডবারে API key দাও (ফ্রি — লিঙ্ক ওখানেই আছে)।")
        elif not model:
            st.error("সাইডবারে একটা মডেল বাছো।")
        elif not ai_name.strip():
            st.error("প্রোডাক্টের নাম দাও।")
        else:
            with st.spinner(f"{model} বিশ্লেষণ করছে…"):
                try:
                    img_bytes = img.getvalue() if img else None
                    media = f"image/{img.name.split('.')[-1].lower()}" if img else "image/jpeg"
                    if media == "image/jpg":
                        media = "image/jpeg"
                    result = ai.research_product(
                        provider_key=prov_key,
                        api_key=api_key,
                        model=model,
                        name=ai_name.strip(),
                        description=ai_desc.strip(),
                        cny_price=ai_cny or None,
                        landed_cost=ai_landed or None,
                        target_price=ai_sell or None,
                        notes=ai_notes.strip(),
                        image_bytes=img_bytes,
                        image_media_type=media,
                    )
                    st.session_state["ai_result"] = result
                    st.session_state["ai_name"] = ai_name.strip()
                except Exception as e:
                    st.error(f"সমস্যা হয়েছে: {e}")

    res = st.session_state.get("ai_result")
    if res:
        st.divider()
        if res.get("_warning"):
            st.warning(res["_warning"])

        sc = res.get("score", 0)
        rec = res.get("recommendation", "")
        level = "good" if sc >= 70 else "ok" if sc >= 50 else "bad"

        h1, h2 = st.columns([1, 3])
        h1.metric("স্কোর", f"{sc}/100")
        h2.markdown(
            f'<div class="verdict-{level}">{rec} — {res.get("score_reason","")}</div>',
            unsafe_allow_html=True,
        )

        st.write("")
        st.markdown(f"**প্রোডাক্ট:** {res.get('product_summary','')}")

        st.markdown("### 👤 কে কিনবে")
        for p in res.get("personas", []):
            tag = "🥇" if p.get("priority") == "প্রধান" else "🥈"
            with st.expander(
                f"{tag} {p.get('title','')} — {p.get('age_range','')} · {p.get('profession','')}",
                expanded=(p.get("priority") == "প্রধান"),
            ):
                pc1, pc2 = st.columns(2)
                pc1.markdown(
                    f"**লিঙ্গ:** {p.get('gender','')}  \n"
                    f"**আয়:** {p.get('income_level','')}  \n"
                    f"**এলাকা:** {p.get('location','')}"
                )
                pc2.markdown(f"**কোথায় পাবে:** {p.get('where_to_reach','')}")
                st.markdown(f"**কেন কিনবে:** {p.get('why_they_buy','')}")
                st.markdown(f"**প্রধান আপত্তি:** {p.get('main_objection','')}")

        pos = res.get("positioning", {})
        if pos:
            st.markdown("### 📣 কীভাবে বেচবে")
            st.info(f"**হুক:** {pos.get('hook','')}")
            st.markdown(f"**অ্যাঙ্গেল:** {pos.get('angle','')}")
            with st.expander("ফেসবুক অ্যাড কপি", expanded=True):
                st.text_area(
                    "কপি করে নাও",
                    value=pos.get("ad_copy", ""),
                    height=160,
                    label_visibility="collapsed",
                )
            ideas = pos.get("content_ideas", [])
            if ideas:
                st.markdown("**কনটেন্ট আইডিয়া**")
                for i in ideas:
                    st.markdown(f"- {i}")

        g1, g2 = st.columns(2)
        with g1:
            pr = res.get("pricing", {})
            if pr:
                st.markdown("### 💵 দাম")
                st.markdown(
                    f"**সাজেস্টেড রেঞ্জ:** {pr.get('suggested_range','')}  \n"
                    f"**প্রাইস সেনসিটিভিটি:** {pr.get('price_sensitivity','')}  \n\n"
                    f"{pr.get('reasoning','')}"
                )
        with g2:
            cp = res.get("competition", {})
            if cp:
                st.markdown("### ⚔️ প্রতিযোগিতা")
                st.markdown(
                    f"**মাত্রা:** {cp.get('level','')}  \n"
                    f"**কারা বেচে:** {cp.get('who_sells_it','')}"
                )
                for d in cp.get("differentiation", []):
                    st.markdown(f"- {d}")

        r1, r2 = st.columns(2)
        with r1:
            if res.get("risks"):
                st.markdown("### ⚠️ ঝুঁকি")
                for x in res["risks"]:
                    st.markdown(f"- {x}")
            if res.get("logistics_flags"):
                st.markdown("### 📦 লজিস্টিকস সতর্কতা")
                for x in res["logistics_flags"]:
                    st.markdown(f"- {x}")
        with r2:
            kw = res.get("sourcing_keywords", {})
            if kw:
                st.markdown("### 🔎 সোর্সিং কীওয়ার্ড")
                if kw.get("chinese"):
                    st.markdown("**1688 / Taobao (চাইনিজ)**")
                    st.code("  ".join(kw["chinese"]), language=None)
                if kw.get("english"):
                    st.markdown("**Alibaba (ইংরেজি)**")
                    st.code("  ".join(kw["english"]), language=None)

        if res.get("validation_steps"):
            st.markdown("### ✅ যাচাই করার ধাপ")
            for i, s in enumerate(res["validation_steps"], 1):
                st.markdown(f"{i}. {s}")

        st.divider()
        b1, b2, b3 = st.columns(3)
        if b1.button("💾 রিপোর্ট সেভ করো", type="primary", use_container_width=True):
            store.add_product(
                {
                    "name": st.session_state.get("ai_name", ""),
                    "type": "ai_research",
                    "score": sc,
                    "recommendation": rec,
                    "report": res,
                }
            )
            st.success("সেভ হয়েছে")
        b2.download_button(
            "⬇️ JSON নামাও",
            data=json.dumps(res, ensure_ascii=False, indent=2),
            file_name=f"{st.session_state.get('ai_name','product')}_research.json",
            mime="application/json",
            use_container_width=True,
        )
        u = res.get("_usage", {})
        b3.caption(
            f"{res.get('_provider','')}  \n"
            f"মডেল: {res.get('_model','')}  \n"
            f"টোকেন: {u.get('input_tokens',0)} in / {u.get('output_tokens',0)} out  ·  "
            f"চেষ্টা: {res.get('_attempts',1)}"
        )


# ==========================================================================
# ট্যাব ৩ — স্কোরকার্ড
# ==========================================================================

with tab_score:
    st.subheader("১০০ পয়েন্টের স্কোরকার্ড")
    st.caption("৭০-এর নিচে হলে প্রোডাক্ট বাদ দাও। নিজের বিচার + AI রিপোর্ট মিলিয়ে নম্বর দাও।")

    sname = st.text_input("প্রোডাক্টের নাম", key="score_name")

    s1, s2 = st.columns(2)
    with s1:
        v_margin = st.slider("মার্জিন (মার্কআপ ৩x+ = পূর্ণ নম্বর)", 0, 30, 15)
        v_demand = st.slider("ডিমান্ড সিগন্যাল (কয়টা সোর্সে পেয়েছ)", 0, 25, 12)
        v_comp = st.slider("কম্পিটিশন (কম = বেশি নম্বর)", 0, 20, 10)
    with s2:
        v_ship = st.slider("শিপিং সহজতা (হালকা, ব্যাটারিহীন, অভঙ্গুর)", 0, 15, 8)
        v_repeat = st.slider("রিপিট পারচেজ / আপসেল সম্ভাবনা", 0, 10, 5)

    total = v_margin + v_demand + v_comp + v_ship + v_repeat
    lvl = "good" if total >= 70 else "ok" if total >= 55 else "bad"
    msg = (
        "সবুজ সংকেত — স্যাম্পল আনাও"
        if total >= 70
        else "হলুদ — দুর্বল দিকটা ঠিক করা যায় কিনা দেখো"
        if total >= 55
        else "লাল — বাদ দাও, পরেরটায় যাও"
    )

    st.write("")
    k1, k2 = st.columns([1, 3])
    k1.metric("মোট স্কোর", f"{total}/100")
    k2.markdown(f'<div class="verdict-{lvl}">{msg}</div>', unsafe_allow_html=True)

    st.progress(total / 100)

    if st.button("💾 স্কোর সেভ করো", type="primary"):
        if not sname.strip():
            st.error("প্রোডাক্টের নাম দাও")
        else:
            store.add_product(
                {
                    "name": sname.strip(),
                    "type": "scorecard",
                    "score": total,
                    "margin": v_margin,
                    "demand": v_demand,
                    "competition": v_comp,
                    "shipping": v_ship,
                    "repeat": v_repeat,
                    "verdict": msg,
                }
            )
            st.success("সেভ হয়েছে")


# ==========================================================================
# ট্যাব ৪ — সেভ করা প্রোডাক্ট
# ==========================================================================

with tab_saved:
    st.subheader("সেভ করা প্রোডাক্ট")
    rows = store.load_all()

    if not rows:
        st.info("এখনো কিছু সেভ করোনি। অন্য ট্যাব থেকে সেভ করলে এখানে দেখাবে।")
    else:
        kinds = ["সব"] + sorted({r.get("type", "?") for r in rows})
        pick = st.selectbox("ফিল্টার", kinds)
        view = rows if pick == "সব" else [r for r in rows if r.get("type") == pick]

        flat = []
        for r in view:
            flat.append(
                {
                    "id": r.get("id"),
                    "নাম": r.get("name"),
                    "ধরন": r.get("type"),
                    "স্কোর": r.get("score", ""),
                    "ল্যান্ডেড": round(r.get("out_landed_unit", 0) or 0),
                    "সেল প্রাইস": round(r.get("in_sell_price", 0) or 0),
                    "নেট মার্জিন %": round(r.get("out_net_margin_pct", 0) or 0, 1),
                    "সেভ": r.get("saved_at"),
                }
            )
        df = pd.DataFrame(flat)
        st.dataframe(df, hide_index=True, use_container_width=True)

        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "⬇️ CSV নামাও",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"products_{datetime.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        d2.download_button(
            "⬇️ সম্পূর্ণ JSON",
            data=json.dumps(view, ensure_ascii=False, indent=2),
            file_name=f"products_{datetime.now():%Y%m%d}.json",
            mime="application/json",
            use_container_width=True,
        )

        st.divider()
        del_id = st.selectbox(
            "মুছতে চাইলে বেছে নাও",
            [""] + [f"{r.get('id')} — {r.get('name')}" for r in view],
        )
        if del_id and st.button("🗑️ মুছে ফেলো"):
            store.delete_product(del_id.split(" — ")[0])
            st.rerun()

        picked = st.selectbox(
            "বিস্তারিত দেখো",
            [""] + [f"{r.get('id')} — {r.get('name')}" for r in view],
            key="detail_pick",
        )
        if picked:
            rec = store.get_product(picked.split(" — ")[0])
            st.json(rec)
