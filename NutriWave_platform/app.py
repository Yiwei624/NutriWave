
import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import load_data, append_run, iter_runs, append_model, iter_models
from core.engine import UserRequest, build_candidate_formulations, build_minidoe_plan

st.set_page_config(page_title="NutriWave", page_icon="🌱", layout="wide")

# ---------- i18n ----------
languages = {"中文": "zh", "English": "en"}
language = st.sidebar.selectbox("🌍 语言 / Language", list(languages.keys()), index=0)
lang = languages[language]

TEXT = {
    "title": {"zh": "🌱 NutriWave | 结构主导的发酵配方引擎", "en": "🌱 NutriWave | Structure-led Fermentation Formulation Engine"},
    "subtitle": {"zh": "需求 → 候选配方(3) → 小试DoE（可选导入消费者数据）", "en": "Brief → candidates(3) → mini-DoE (optional consumer data import)"},
    "home": {"zh": "🏠 首页 / Home", "en": "🏠 Home"},
    "engine": {"zh": "✨ 配方引擎 / Recipe Engine", "en": "✨ Recipe Engine"},
    "db": {"zh": "🧬 管理员数据库 / Admin Database", "en": "🧬 Admin Database"},
}

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
    col3.metric("Data flywheel", "Internal", "🔒")
    st.markdown("---")
    st.write("zh: 客户页仅输出 3 组候选配方 + 小试方法。数据库/回流/模型仅管理员可见。"
             if lang=="zh" else
             "Customer page outputs only 3 candidates + mini-DoE. Database/runs/models are admin-only.")

# ---------- Recipe Engine (minimal + consumer data) ----------
elif menu.startswith("✨"):
    st.title("✨ 生成候选配方" if lang=="zh" else "✨ Generate Candidate Formulations")
    st.caption("仅输入：Brief + Base + Texture。可选导入消费者数据以定制偏好。"
               if lang=="zh" else
               "Inputs: Brief + Base + Texture. Optional consumer data import to tailor preferences.")

    main_col, side_col = st.columns([2, 1], gap="large")

    with main_col:
        default_text_zh = "大豆酸奶，要去除豆腥味，喜欢甜豆浆的味道，口感要柔和一点的。"
        default_text_en = "Soy yogurt; reduce beany flavor; sweet soymilk notes; softer texture."
        input_text = st.text_area("需求简介 / Brief", default_text_zh if lang=="zh" else default_text_en, height=120)

        bases = data.get("bases", [])
        base_names = [b["name_zh"] if lang=="zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang=="zh" else b["name_en"]): b["id"] for b in bases}
        c1, c2 = st.columns(2)
        with c1:
            base_sel = st.selectbox("基质 / Base", base_names, index=0)
        with c2:
            texture_sel = st.selectbox("口感目标 / Texture target", ["soft","thick","refreshing"], index=0)

        generate = st.button("🚀 生成候选配方" if lang=="zh" else "🚀 Generate candidates", type="primary", use_container_width=True)

    with side_col:
        st.markdown("### 📊 消费者数据" if lang=="zh" else "### 📊 Consumer Data")
        use_customer = st.toggle("启用客户数据模式" if lang=="zh" else "Enable customer-data mode", value=False)
        customer_profile = None
        if use_customer:
            up = st.file_uploader("上传 CSV/Excel" if lang=="zh" else "Upload CSV/Excel", type=["csv","xlsx"])
            if up is not None:
                if up.name.lower().endswith(".csv"):
                    df = pd.read_csv(up)
                else:
                    df = pd.read_excel(up)
                cols = ["(none)"] + list(df.columns)
                col_beany = st.selectbox("豆腥/异味（低=讨厌）" if lang=="zh" else "Beany/off-flavor (lower=worse)", cols, index=0)
                col_sweet = st.selectbox("甜味喜好" if lang=="zh" else "Sweetness liking", cols, index=0)
                col_texture = st.selectbox("口感/稠度喜好" if lang=="zh" else "Texture/thickness liking", cols, index=0)
                col_overall = st.selectbox("总体喜好/购买意愿" if lang=="zh" else "Overall liking / intent", cols, index=0)

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
                st.success("✅ 已生成客户偏好画像" if lang=="zh" else "✅ Customer profile created")
                st.json(customer_profile)

    if generate:
        # infer goals from brief + texture
        b = (input_text or "").lower()
        goals = []
        if ("豆腥" in input_text) or ("beany" in b) or ("off-flavor" in b):
            goals.append("anti_beany")
        if ("甜" in input_text) or ("sweet" in b):
            goals.append("sweet_notes")
        if texture_sel in ["soft","thick"]:
            goals.append("eps")

        # small bias from customer profile
        if customer_profile and customer_profile.get("beany_mean") is not None and customer_profile["beany_mean"] < 3.0:
            if "anti_beany" in goals:
                goals = ["anti_beany"] + [g for g in goals if g != "anti_beany"]
            else:
                goals = ["anti_beany"] + goals

        req = UserRequest(lang=lang, product_type="yogurt", base_id=base_map[base_sel], texture=texture_sel,
                          goals=goals, constraints=data.get("constraints", {}).get("default", {}))
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

        st.success("✅ 已生成候选配方！" if lang=="zh" else "✅ Candidates generated!")
        for i, cnd in enumerate(candidates, start=1):
            st.markdown(f"#### Candidate {i}")
            st.json(cnd)
        st.markdown("### Mini-DoE / 小试方法" if lang=="zh" else "### Mini-DoE")
        st.json(doe)

        st.download_button(
            "📥 下载配方包" if lang=="zh" else "📥 Download pack",
            data=json.dumps(pack, ensure_ascii=False, indent=2),
            file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
        )

# ---------- Admin Database (5 rows) ----------
elif menu.startswith("🧬"):
    st.title("🧬 管理员数据库 / Admin Database")
    st.caption("Row1 Strains | Row2 Rheology | Row3 Ingredients+Suppliers | Row4 Runs | Row5 Surrogate Models")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Row1 菌株 / Strains",
        "Row2 流变框架 / Rheology",
        "Row3 物料与供应链 / Ingredients",
        "Row4 实验 Runs",
        "Row5 代理模型 / Models"
    ])

    # ---------- Row1 Strains ----------
    with tab1:
        strains = data.get("strains", [])
        df = pd.DataFrame([{
            "strain_id": s.get("strain_id",""),
            "name": s.get("name_zh","") if lang=="zh" else s.get("name_en",""),
            "supplier_id": s.get("supplier_id",""),
            "benefit_tags": ", ".join(s.get("benefit_tags", [])),
            "evidence": s.get("evidence_level",""),
        } for s in strains])
        st.dataframe(df, use_container_width=True)

        st.markdown("### 详情 / Details")
        if strains:
            options = { (s.get("name_zh") if lang=="zh" else s.get("name_en")) : s for s in strains }
            sel = st.selectbox("选择菌株 / Select strain", list(options.keys()), index=0)
            st.json(options[sel])
        else:
            st.info("No strains yet. Add entries to data/data.json.")

    # ---------- Row2 Rheology ----------
    with tab2:
        methods = data.get("rheo_methods", [])
        dfm = pd.DataFrame([{
            "rheo_method_id": m.get("rheo_method_id",""),
            "name": m.get("name_zh","") if lang=="zh" else m.get("name_en",""),
            "geometry": m.get("geometry",""),
            "processing_version": m.get("processing_version","")
        } for m in methods])
        st.dataframe(dfm, use_container_width=True)

        st.markdown("### 详情 / Details")
        if methods:
            opt = { (m.get("name_zh") if lang=="zh" else m.get("name_en")) : m for m in methods }
            sel = st.selectbox("选择测量框架 / Select method", list(opt.keys()), index=0)
            st.json(opt[sel])
        else:
            st.info("No rheology methods yet. Add entries to data/data.json.")

    # ---------- Row3 Ingredients & Suppliers ----------
    with tab3:
        suppliers = {s["supplier_id"]: s for s in data.get("suppliers", [])}
        ing = data.get("ingredients", [])
        rows = []
        for it in ing:
            sid = it.get("supplier_id","")
            rows.append({
                "ingredient_id": it.get("ingredient_id",""),
                "category": it.get("category",""),
                "name": it.get("name_zh","") if lang=="zh" else it.get("name_en",""),
                "supplier": suppliers.get(sid, {}).get("name", sid),
                "clean_label": it.get("clean_label", True),
                "allergens": ", ".join(it.get("allergen_flags", []))
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        st.markdown("### 供应商 / Suppliers")
        st.dataframe(pd.DataFrame([{
            "supplier_id": s.get("supplier_id",""),
            "name": s.get("name",""),
            "region": s.get("region",""),
            "MOQ": s.get("MOQ",""),
            "lead_time": s.get("lead_time","")
        } for s in data.get("suppliers", [])]), use_container_width=True)

    # ---------- Row4 Runs (admin logging) ----------
    with tab4:
        st.markdown("### 新增实验记录 / Add a run (Admin-only)")
        strains = data.get("strains", [])
        strain_names = [(s.get("name_zh") if lang=="zh" else s.get("name_en")) for s in strains] or ["TBD"]
        strain_map = { (s.get("name_zh") if lang=="zh" else s.get("name_en")): s.get("strain_id") for s in strains }

        ing = data.get("ingredients", [])
        ing_names = [(i.get("name_zh") if lang=="zh" else i.get("name_en")) for i in ing] or ["TBD"]
        ing_map = { (i.get("name_zh") if lang=="zh" else i.get("name_en")): i.get("ingredient_id") for i in ing }

        methods = data.get("rheo_methods", [])
        method_names = [(m.get("name_zh") if lang=="zh" else m.get("name_en")) for m in methods] or ["NW-Lambda-v1"]
        method_map = { (m.get("name_zh") if lang=="zh" else m.get("name_en")): m.get("rheo_method_id") for m in methods }

        with st.form("run_form"):
            product_type = st.text_input("产品 / Product", value="soy_yogurt")
            strain_sel = st.selectbox("菌株 / Strain", strain_names, index=0)
            ing_sel = st.multiselect("物料 / Ingredients", ing_names, default=ing_names[:1])
            ferm_time = st.number_input("发酵时间 (h)", min_value=0.0, value=8.0, step=0.5)
            end_ph = st.number_input("终点 pH", min_value=3.5, max_value=6.5, value=4.6, step=0.05)
            rheo_method_sel = st.selectbox("流变框架 / Rheology method", method_names, index=0)

            st.markdown("**流变数据 / Rheology**")
            c1, c2, c3, c4 = st.columns(4)
            syneresis = c1.number_input("Syneresis (%)", 0.0, 100.0, 0.0, 0.5)
            gprime = c2.number_input("G' (Pa)", 0.0, 0.0, 0.0, 10.0)
            tauy = c3.number_input("τy (Pa)", 0.0, 0.0, 0.0, 1.0)
            Lambda = c4.number_input("Λ (Lambda)", 0.0, 10.0, 0.0, 0.01)
            regime = st.selectbox("Regime", ["partial (Λ<1)","full (Λ≥1)"], index=0)

            st.markdown("**风味/感官 / Flavor & Sensory**")
            s_beany = st.slider("Beany(-)", 1, 5, 3)
            s_sweet = st.slider("Sweet", 1, 5, 3)
            s_smooth = st.slider("Smooth", 1, 5, 3)
            s_overall = st.slider("Overall", 1, 5, 3)

            save = st.form_submit_button("✅ 保存 / Save run")
            if save:
                run = {
                    "run_id": datetime.utcnow().strftime("RUN-%Y%m%d-%H%M%S"),
                    "product_type": product_type,
                    "strain_id": strain_map.get(strain_sel, "TBD"),
                    "ingredient_ids": [ing_map.get(x, "TBD") for x in ing_sel],
                    "fermentation_time_h": float(ferm_time),
                    "end_ph": float(end_ph),
                    "rheo_method_id": method_map.get(rheo_method_sel, "NW-Lambda-v1"),
                    "rheology": {"syneresis_pct": float(syneresis), "G_prime_pa": float(gprime), "tau_y_pa": float(tauy), "Lambda": float(Lambda), "regime": regime},
                    "sensory": {"beany": int(s_beany), "sweet": int(s_sweet), "smooth": int(s_smooth), "overall": int(s_overall)},
                    "outcome_label": "iterate"
                }
                append_run(run)
                st.success("Saved / 已保存")

        st.markdown("---")
        st.markdown("### 最近 Runs / Latest runs")
        runs = iter_runs(limit=300)
        if runs:
            dfr = pd.DataFrame([{
                "timestamp": r.get("timestamp_utc",""),
                "run_id": r.get("run_id",""),
                "product": r.get("product_type",""),
                "strain_id": r.get("strain_id",""),
                "end_pH": r.get("end_ph", None),
                "Lambda": r.get("rheology", {}).get("Lambda", None),
                "overall": r.get("sensory", {}).get("overall", None),
                "syneresis": r.get("rheology", {}).get("syneresis_pct", None),
            } for r in runs])
            st.dataframe(dfr.sort_values("timestamp", ascending=False), use_container_width=True)
            st.download_button("Download runs.jsonl", "\n".join(json.dumps(x, ensure_ascii=False) for x in runs), file_name="runs_export.jsonl")
        else:
            st.info("No runs yet. Use the form above to add the first one.")

    # ---------- Row5 Models (registry) ----------
    with tab5:
        st.markdown("### 模型注册 / Model Registry (Admin-only)")
        with st.form("model_form"):
            model_id = st.text_input("model_id", value=f"MODEL-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            model_type = st.selectbox("model_type", ["rule_scoring","RF","XGBoost","GP (Bayesian)","NN"], index=0)
            target_outputs = st.text_input("target_outputs (comma)", value="overall,syneresis,beany")
            feature_version = st.text_input("feature_set_version", value="v1")
            n_runs = st.number_input("n_runs_used", min_value=0, value=len(iter_runs(limit=500)), step=10)
            metric = st.text_input("metrics (e.g., MAE=..., RMSE=...)", value="TBD")
            deployed = st.checkbox("deployed_version", value=False)
            notes = st.text_area("notes", value="TBD")

            save_model = st.form_submit_button("✅ 保存模型条目 / Save model entry")
            if save_model:
                append_model({
                    "model_id": model_id,
                    "model_type": model_type,
                    "target_outputs": [x.strip() for x in target_outputs.split(",") if x.strip()],
                    "feature_set_version": feature_version,
                    "n_runs_used": int(n_runs),
                    "metrics": metric,
                    "deployed": bool(deployed),
                    "notes": notes
                })
                st.success("Saved / 已保存")

        st.markdown("---")
        models = iter_models(limit=200)
        if models:
            dfm = pd.DataFrame([{
                "timestamp": m.get("timestamp_utc",""),
                "model_id": m.get("model_id",""),
                "type": m.get("model_type",""),
                "targets": ", ".join(m.get("target_outputs", [])),
                "n_runs": m.get("n_runs_used", None),
                "deployed": m.get("deployed", False)
            } for m in models])
            st.dataframe(dfm.sort_values("timestamp", ascending=False), use_container_width=True)
            st.download_button("Download models.jsonl", "\n".join(json.dumps(x, ensure_ascii=False) for x in models), file_name="models_export.jsonl")
        else:
            st.info("No model entries yet.")
