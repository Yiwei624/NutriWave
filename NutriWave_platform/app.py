import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import load_data
from core.engine import (
    UserRequest,
    build_candidate_formulations,
    build_minidoe_plan,
)

st.set_page_config(page_title="NutriWave", page_icon="🌱", layout="wide")

# ---------- i18n ----------
languages = {"中文": "zh", "English": "en"}
language = st.sidebar.selectbox("🌍 语言 / Language", list(languages.keys()), index=0)
lang = languages[language]

TEXT = {
    "title": {"zh": "🌱 NutriWave | 结构主导的发酵配方引擎", "en": "🌱 NutriWave | Structure-led Fermentation Formulation Engine"},
    "subtitle": {"zh": "从需求 → 候选配方 → 小试DoE（可选导入消费者数据）", "en": "Brief → candidates → mini-DoE (optional consumer data import)"},
    "home": {"zh": "🏠 首页 / Home", "en": "🏠 Home"},
    "engine": {"zh": "✨ 配方引擎 / Recipe Engine", "en": "✨ Recipe Engine"},
    "db": {"zh": "🧬 数据库 / Database", "en": "🧬 Database"},
    "brief": {"zh": "需求简介 / Brief", "en": "Brief"},
    "base": {"zh": "基质 / Base", "en": "Base"},
    "texture": {"zh": "口感目标 / Texture target", "en": "Texture target"},
    "generate": {"zh": "🚀 生成候选配方", "en": "🚀 Generate candidates"},
    "success": {"zh": "✅ 已生成候选配方！", "en": "✅ Candidates generated!"},
    "download": {"zh": "📥 下载配方包", "en": "📥 Download pack"},
}

# ---------- load seed data ----------
@st.cache_data
def _load():
    return load_data()

data = _load()

# ---------- admin auth (secrets) ----------
def check_admin() -> bool:
    pw = st.sidebar.text_input("🔒 管理员密码 (Admin password)", type="password")
    if not pw:
        return False

    expected = st.secrets.get("ADMIN_PASSWORD", "")
    if expected and hmac.compare_digest(pw, expected):
        st.sidebar.success("✅ Admin access granted")
        return True

    st.sidebar.error("❌ Incorrect password")
    return False

admin_ok = check_admin()

# ---------- navigation ----------
menu_options = [TEXT["home"][lang], TEXT["engine"][lang]]
if admin_ok:
    menu_options.append(TEXT["db"][lang])
menu = st.sidebar.radio("导航 / Navigation", menu_options)

# ---------- Home ----------
if menu.startswith("🏠"):
    st.title(TEXT["title"][lang])
    st.subheader(TEXT["subtitle"][lang])

    col1, col2, col3 = st.columns(3)
    col1.metric("Time-to-candidate", "Minutes", "↓")
    col2.metric("Scale-up risk", "Lower", "↓")
    col3.metric("Customer fit", "Better", "↑")

    st.markdown("---")
    st.write(
        "zh: 该平台用于快速生成 3 组候选配方 + 小试方法。可选导入客户消费者数据，使推荐更贴合客户受众。数据库页面仅团队可见。"
        if lang == "zh"
        else
        "This platform generates 3 candidate formulations + a mini test plan. Optionally import customer consumer data to tailor recommendations. Database page is team-only."
    )

# ---------- Recipe Engine (MINIMAL + Consumer Data) ----------
elif menu.startswith("✨"):
    st.title("✨ 生成候选配方" if lang == "zh" else "✨ Generate Candidate Formulations")
    st.caption(
        "仅输入：需求简介 + 基质 + 口感目标。可选导入消费者数据（客户公司偏好）来定制推荐。"
        if lang == "zh"
        else
        "Inputs: brief + base + texture. Optionally import consumer data (customer preferences) to tailor recommendations."
    )

    main_col, side_col = st.columns([2, 1], gap="large")

    # ---- Main inputs (ONLY 3) ----
    with main_col:
        default_text_zh = "大豆酸奶，要去除豆腥味，喜欢甜豆浆的味道，口感要柔和一点的。"
        default_text_en = "Soy yogurt; reduce beany flavor; sweet soymilk notes; softer texture."
        input_text = st.text_area(TEXT["brief"][lang], default_text_zh if lang == "zh" else default_text_en, height=120)

        bases = data.get("bases", [])
        if not bases:
            st.error("data.json 缺少 bases（至少保留一个 base，如 soy） / Missing 'bases' in data.json")
            st.stop()

        base_names = [b["name_zh"] if lang == "zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang == "zh" else b["name_en"]): b["id"] for b in bases}

        c1, c2 = st.columns(2)
        with c1:
            base_sel = st.selectbox(TEXT["base"][lang], base_names, index=0)
        with c2:
            texture_sel = st.selectbox(TEXT["texture"][lang], ["soft", "thick", "refreshing"], index=0)

        generate = st.button(TEXT["generate"][lang], type="primary", use_container_width=True)

    # ---- Consumer data import (optional) ----
    with side_col:
        st.markdown("### 📊 消费者数据" if lang == "zh" else "### 📊 Consumer Data")
        use_customer = st.toggle("启用客户数据模式" if lang == "zh" else "Enable customer-data mode", value=False)

        customer_profile = None
        if use_customer:
            up = st.file_uploader("上传 CSV/Excel" if lang == "zh" else "Upload CSV/Excel", type=["csv", "xlsx"])

            if up is not None:
                if up.name.lower().endswith(".csv"):
                    df = pd.read_csv(up)
                else:
                    df = pd.read_excel(up)

                st.caption(
                    "选择列映射（可留空）：用于生成客户偏好画像"
                    if lang == "zh"
                    else
                    "Map columns (optional) to build a customer preference profile"
                )

                cols = ["(none)"] + list(df.columns)
                col_beany = st.selectbox("豆腥/异味（低=讨厌）" if lang == "zh" else "Beany/off-flavor (lower=worse)", cols, index=0)
                col_sweet = st.selectbox("甜味喜好" if lang == "zh" else "Sweetness liking", cols, index=0)
                col_texture = st.selectbox("口感/稠度喜好" if lang == "zh" else "Texture/thickness liking", cols, index=0)
                col_overall = st.selectbox("总体喜好/购买意愿" if lang == "zh" else "Overall liking / purchase intent", cols, index=0)

                def _mean(col):
                    if col == "(none)":
                        return None
                    s = pd.to_numeric(df[col], errors="coerce").dropna()
                    return float(s.mean()) if len(s) else None

                customer_profile = {
                    "rows": int(len(df)),
                    "beany_mean": _mean(col_beany),
                    "sweet_mean": _mean(col_sweet),
                    "texture_mean": _mean(col_texture),
                    "overall_mean": _mean(col_overall),
                }

                st.success("✅ 已生成客户偏好画像" if lang == "zh" else "✅ Customer preference profile created")
                st.json(customer_profile)

    # ---- Generate outputs (3 candidates + mini-DoE only) ----
    if generate:
        def infer_goals(brief: str, texture: str) -> list:
            b = (brief or "").lower()
            goals = []
            if ("豆腥" in brief) or ("beany" in b) or ("off-flavor" in b):
                goals.append("anti_beany")
            if ("甜" in brief) or ("sweet" in b):
                goals.append("sweet_notes")
            if texture in ["soft", "thick"]:
                goals.append("eps")
            return goals

        def apply_customer_profile(goals: list, profile: dict | None) -> list:
            if not profile:
                return goals

            bm = profile.get("beany_mean")
            sm = profile.get("sweet_mean")
            tm = profile.get("texture_mean")

            if bm is not None and bm < 3.0:
                if "anti_beany" in goals:
                    goals = ["anti_beany"] + [g for g in goals if g != "anti_beany"]
                else:
                    goals = ["anti_beany"] + goals

            if sm is not None and sm > 3.5 and "sweet_notes" not in goals:
                goals.append("sweet_notes")

            if tm is not None and tm > 3.5 and "eps" not in goals:
                goals.append("eps")

            seen = set()
            out = []
            for g in goals:
                if g not in seen:
                    out.append(g)
                    seen.add(g)
            return out

        goals = infer_goals(input_text, texture_sel)
        goals = apply_customer_profile(goals, customer_profile)

        req = UserRequest(
            lang=lang,
            product_type="yogurt",
            base_id=base_map[base_sel],
            texture=texture_sel,
            goals=goals,
            constraints=data.get("constraints", {}).get("default", {}),
        )

        candidates = build_candidate_formulations(data, req, n=3, customer_profile=customer_profile)
        doe = build_minidoe_plan(req)

        pack = {
            "generated_at": datetime.utcnow().isoformat(),
            "lang": lang,
            "brief": input_text,
            "request": {"base": base_sel, "texture": texture_sel, "goals": goals},
            "customer_profile": customer_profile,
            "candidates": candidates,
            "mini_doe": doe,
        }

        st.success(TEXT["success"][lang])

        st.markdown("### Candidates / 候选配方（3组）" if lang == "zh" else "### Candidates (3)")
        for i, cnd in enumerate(candidates, start=1):
            st.markdown(f"#### Candidate {i}")
            st.json(cnd)

        st.markdown("### Mini-DoE / 小试方法" if lang == "zh" else "### Mini-DoE (test plan)")
        st.json(doe)

        st.download_button(
            TEXT["download"][lang],
            data=json.dumps(pack, ensure_ascii=False, indent=2),
            file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
        )

# ---------- Admin-only Database ----------
elif menu.startswith("🧬"):
    st.title(TEXT["db"][lang])
    st.caption("Admin-only. Seed library only.")

    db_lang_code = "zh" if lang == "zh" else "en"

    st.subheader("Strains / 菌株")
    strains_df = pd.DataFrame([
        {
            "ID": s.get("id", ""),
            "Name": s.get(f"name_{db_lang_code}", ""),
            "Tags": ", ".join(s.get("tags", [])),
            "Supplier": s.get("uk_sup", ""),
        }
        for s in data.get("strains", [])
    ])
    st.dataframe(strains_df, use_container_width=True)

    st.subheader("Targets / 结构目标")
    st.json(data.get("targets", {}))

    st.subheader("Suppliers / 供应商")
    st.json(data.get("suppliers", {}))

st.sidebar.markdown("---")
st.sidebar.info("NutriWave | Minimal Engine + Consumer Data Import + Admin DB")
