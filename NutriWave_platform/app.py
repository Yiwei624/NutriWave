import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import (
    load_data,
    append_strain, append_ingredient, append_rheo_method, append_formulation,
    append_run, append_model,
    iter_runs, iter_models,
    compute_learning_scores
)
from core.engine import UserRequest, build_candidate_formulations, build_minidoe_plan

st.set_page_config(page_title="NutriWave", page_icon="🌱", layout="wide")

languages = {"中文": "zh", "English": "en"}
language = st.sidebar.selectbox("🌍 语言 / Language", list(languages.keys()), index=0)
lang = languages[language]

@st.cache_data
def _load():
    return load_data()

data = _load()

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

menu_options = ["🏠 首页 / Home", "✨ 配方引擎 / Recipe Engine"]
if admin_ok:
    menu_options.append("🧬 管理员数据库 / Admin Database")
menu = st.sidebar.radio("导航 / Navigation", menu_options)

if menu.startswith("🏠"):
    st.title("🌱 NutriWave | 结构主导的发酵配方引擎" if lang=="zh" else "🌱 NutriWave | Structure-led Fermentation Formulation Engine")
    st.write("逻辑：Row1/2/3 → Row4 runs（含Formulation剂量）→ Row5 learning scores → 引擎输出"
             if lang=="zh" else
             "Flow: Row1/2/3 → Row4 runs (with formulation dosages) → Row5 learning scores → Engine output")

elif menu.startswith("✨"):
    st.title("✨ 生成候选配方" if lang=="zh" else "✨ Generate candidates")
    main_col, side_col = st.columns([2,1], gap="large")

    with main_col:
        brief = st.text_area("需求简介 / Brief",
                             "大豆酸奶，要去除豆腥味，喜欢甜豆浆的味道，口感要柔和一点的。" if lang=="zh" else
                             "Soy yogurt; reduce beany; sweet soymilk notes; softer texture.", height=120)
        bases = data.get("bases", [])
        base_names = [b["name_zh"] if lang=="zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang=="zh" else b["name_en"]): b["id"] for b in bases}
        c1, c2 = st.columns(2)
        with c1:
            base_sel = st.selectbox("基质 / Base", base_names, index=0)
        with c2:
            texture = st.selectbox("口感目标 / Texture", ["soft","thick","refreshing"], index=0)
        generate = st.button("🚀 生成候选配方" if lang=="zh" else "🚀 Generate", type="primary", use_container_width=True)

    with side_col:
        st.markdown("### 📊 消费者数据" if lang=="zh" else "### 📊 Consumer Data")
        use_customer = st.toggle("启用客户数据模式" if lang=="zh" else "Enable customer data", value=False)
        customer_profile = None
        if use_customer:
            up = st.file_uploader("上传 CSV/Excel" if lang=="zh" else "Upload CSV/Excel", type=["csv","xlsx"])
            if up is not None:
                df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
                cols = ["(none)"] + list(df.columns)
                cb = st.selectbox("Beany/off-flavor", cols, 0)
                cs = st.selectbox("Sweet liking", cols, 0)
                ct = st.selectbox("Texture liking", cols, 0)
                def mean(col):
                    if col=="(none)":
                        return None
                    s = pd.to_numeric(df[col], errors="coerce").dropna()
                    return float(s.mean()) if len(s) else None
                customer_profile = {"rows": int(len(df)), "beany_mean": mean(cb), "sweet_mean": mean(cs), "texture_mean": mean(ct)}
                st.json(customer_profile)

    if generate:
        b = (brief or "").lower()
        goals = []
        if ("豆腥" in brief) or ("beany" in b) or ("off-flavor" in b):
            goals.append("anti_beany")
        if ("甜" in brief) or ("sweet" in b):
            goals.append("sweet_notes")
        if texture in ["soft","thick"]:
            goals.append("eps")

        learning_scores = compute_learning_scores(data, product_type="soy_yogurt", texture=texture)

        req = UserRequest(lang=lang, product_type="soy_yogurt", base_id=base_map[base_sel], texture=texture,
                          goals=goals, constraints=data.get("constraints", {}).get("default", {}),
                          customer_profile=customer_profile, learning_scores=learning_scores)
        candidates = build_candidate_formulations(data, req, n=3)
        doe = build_minidoe_plan(req)
        st.success(("已生成（使用历史n=%d）" % learning_scores.get("n_used",0)) if lang=="zh" else ("Generated (history n=%d)" % learning_scores.get("n_used",0)))
        for i, c in enumerate(candidates, 1):
            st.markdown(f"#### Candidate {i}")
            st.json(c)
        st.markdown("### Mini-DoE")
        st.json(doe)

        pack = {"generated_at": datetime.utcnow().isoformat(), "brief": brief, "request": {"base": base_sel, "texture": texture, "goals": goals},
                "customer_profile": customer_profile, "learning_scores_summary": {"n_used": learning_scores.get("n_used",0)}, "candidates": candidates, "mini_doe": doe}
        st.download_button("📥 下载配方包" if lang=="zh" else "📥 Download pack",
                           data=json.dumps(pack, ensure_ascii=False, indent=2),
                           file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                           mime="application/json")

else:
    st.title("🧬 管理员数据库 / Admin Database")
    if st.button("🔄 刷新数据 / Refresh"):
        st.cache_data.clear()
        data = _load()
        st.success("Refreshed / 已刷新")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Row1 菌株&复合菌", "Row2 流变框架", "Row3 物料库", "Row4 配方&实验", "Row5 学习&模型"])

    with tab1:
        st.subheader("Strains + Combos")
        strains = data.get("strains", [])
        st.dataframe(pd.DataFrame([{"kind": s.get("kind"), "id": s.get("strain_combo_id") or s.get("strain_id"),
                                    "name": s.get("name_zh") if lang=="zh" else s.get("name_en"),
                                    "benefit_tags": ",".join(s.get("benefit_tags", []))} for s in strains]), use_container_width=True)
        with st.form("add_combo"):
            cid = st.text_input("strain_combo_id", value=f"COMBO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            tags = st.text_input("benefit_tags (comma)", value="anti_beany,eps")
            members_json = st.text_area("members (json)", value='[{"id":"TBD-001","ratio":"1:1"}]')
            inoc = st.text_input("inoculation_pct", value="TBD")
            save = st.form_submit_button("保存复合菌 / Save combo")
            if save:
                try:
                    members = json.loads(members_json)
                except Exception:
                    members = [{"id":"TBD-001","ratio":"TBD"}]
                append_strain({"kind":"combo","strain_combo_id": cid, "name_zh": name_zh, "name_en": name_en, "supplier_id": "KT",
                               "members": members, "inoculation_pct": inoc, "benefit_tags": [x.strip() for x in tags.split(",") if x.strip()],
                               "evidence_level": "seed"})
                st.success("Saved. Refresh to apply.")

    with tab2:
        st.subheader("Rheology methods + Quality gates")
        methods = data.get("rheo_methods", [])
        st.dataframe(pd.DataFrame([{"id": m.get("rheo_method_id"), "name": m.get("name_zh") if lang=="zh" else m.get("name_en"),
                                    "gates": json.dumps(m.get("quality_gates", {}), ensure_ascii=False)} for m in methods]), use_container_width=True)

    with tab3:
        st.subheader("Ingredients")
        ing = data.get("ingredients", [])
        st.dataframe(pd.DataFrame([{"ingredient_id": i.get("ingredient_id"), "category": i.get("category"),
                                    "name": i.get("name_zh") if lang=="zh" else i.get("name_en")} for i in ing]), use_container_width=True)

    with tab4:
        st.subheader("Formulations (Row4B)")
        forms = data.get("formulations", [])
        st.dataframe(pd.DataFrame([{"formulation_id": f.get("formulation_id"), "base_id": f.get("base_id"),
                                    "n_items": len(f.get("ingredients") or [])} for f in forms]), use_container_width=True)
        ing_names = [(i.get("name_zh") if lang=="zh" else i.get("name_en")) for i in ing]
        ing_map = { (i.get("name_zh") if lang=="zh" else i.get("name_en")): i.get("ingredient_id") for i in ing }
        bases = data.get("bases", [])
        base_names = [b["name_zh"] if lang=="zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang=="zh" else b["name_en"]): b["id"] for b in bases}
        with st.form("add_form"):
            fid = st.text_input("formulation_id", value=f"FORM-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            base_sel = st.selectbox("base", base_names, index=0)
            selected = st.multiselect("ingredients", ing_names, default=ing_names[:1] if ing_names else [])
            dosage = {}
            for nm in selected:
                dosage[nm] = st.number_input(f"{nm} dosage_kg/100kg", min_value=0.0, value=1.0, step=0.1)
            savef = st.form_submit_button("保存配方 / Save formulation")
            if savef:
                total = 0.0
                items = []
                for nm in selected:
                    kg = float(dosage[nm]); total += kg
                    items.append({"ingredient_id": ing_map.get(nm, "TBD"), "name": nm, "dosage_kg": kg})
                items.append({"ingredient_id": "WATER", "name": "Water", "dosage_kg": max(0.0, 100.0-total)})
                append_formulation({"formulation_id": fid, "base_id": base_map[base_sel], "basis": "per_100kg", "ingredients": items, "version": "v1"})
                st.success("Saved. Refresh to apply.")

        st.markdown("---")
        st.subheader("Runs (Row4A)")
        combos = [s for s in strains if s.get("kind")=="combo"]
        combo_names = [(c.get("name_zh") if lang=="zh" else c.get("name_en")) for c in combos] or ["Combo TBD"]
        combo_map = { (c.get("name_zh") if lang=="zh" else c.get("name_en")): c.get("strain_combo_id") for c in combos }
        method_names = [(m.get("name_zh") if lang=="zh" else m.get("name_en")) for m in methods] or ["NW-Lambda-v1"]
        method_map = { (m.get("name_zh") if lang=="zh" else m.get("name_en")): m.get("rheo_method_id") for m in methods }
        form_ids = [f.get("formulation_id") for f in forms] or []
        with st.form("add_run"):
            texture = st.selectbox("texture", ["soft","thick","refreshing"], index=0, key="run_tex")
            combo_sel = st.selectbox("strain_combo", combo_names, index=0)
            form_sel = st.selectbox("formulation_id", form_ids if form_ids else ["(create first)"], index=0)
            t_h = st.number_input("fermentation_time_h", 0.0, 200.0, 8.0, 0.5)
            end_ph = st.number_input("end_pH", 3.5, 6.5, 4.6, 0.05)
            rm = st.selectbox("rheo_method", method_names, index=0)
            torque_ok = st.checkbox("torque_floor_ok", True)
            rep_ok = st.checkbox("repeatability_ok", True)
            sy = st.number_input("syneresis_pct", 0.0, 100.0, 0.0, 0.5)
            lam = st.number_input("Lambda", 0.0, 10.0, 0.0, 0.01)
            regime = st.selectbox("regime", ["partial (Λ<1)","full (Λ≥1)"], 1)
            overall = st.slider("overall", 1, 5, 3)
            save = st.form_submit_button("保存run")
            if save:
                append_run({
                    "run_id": datetime.utcnow().strftime("RUN-%Y%m%d-%H%M%S"),
                    "product_type": "soy_yogurt",
                    "texture": texture,
                    "strain_combo_id": combo_map.get(combo_sel, "COMBO-TBD"),
                    "formulation_id": form_sel,
                    "ingredient_ids": [x.get("ingredient_id") for x in (next((f for f in forms if f.get("formulation_id")==form_sel), {}).get("ingredients", []) or []) if x.get("ingredient_id") not in ["WATER"]],
                    "fermentation_time_h": float(t_h),
                    "end_ph": float(end_ph),
                    "rheo_method_id": method_map.get(rm, "NW-Lambda-v1"),
                    "quality_flags": {"torque_floor_ok": bool(torque_ok), "repeatability_ok": bool(rep_ok)},
                    "rheology": {"syneresis_pct": float(sy), "Lambda": float(lam), "regime": regime},
                    "sensory": {"overall": int(overall)}
                })
                st.success("Saved. Refresh and see Row5 scores.")

        runs = iter_runs(limit=100)
        st.dataframe(pd.DataFrame([{"run_id": r.get("run_id"), "texture": r.get("texture"), "combo": r.get("strain_combo_id"),
                                    "formulation": r.get("formulation_id"), "sy": (r.get("rheology") or {}).get("syneresis_pct"),
                                    "regime": (r.get("rheology") or {}).get("regime"), "overall": (r.get("sensory") or {}).get("overall")} for r in runs]), use_container_width=True)

    with tab5:
        st.subheader("Row5A Learning Scores")
        tex = st.selectbox("compute texture", ["soft","thick","refreshing"], 0, key="ls_tex")
        scores = compute_learning_scores(data, "soy_yogurt", tex)
        st.json(scores)
        st.subheader("Models registry")
        with st.form("add_model"):
            mid = st.text_input("model_id", value=f"MODEL-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            mtype = st.selectbox("model_type", ["learning_score","RF","XGBoost","GP"], 0)
            save = st.form_submit_button("save model")
            if save:
                append_model({"model_id": mid, "model_type": mtype, "notes": "TBD"})
                st.success("Saved.")
        st.dataframe(pd.DataFrame([{"model_id": m.get("model_id"), "type": m.get("model_type"), "ts": m.get("timestamp_utc")} for m in iter_models(100)]), use_container_width=True)
