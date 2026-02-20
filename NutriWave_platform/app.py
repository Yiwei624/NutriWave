
import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import (
    load_data,
    append_strain, append_ingredient, append_rheo_method,
    append_run, append_model,
    iter_runs, iter_models
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

# ---------- Home ----------
if menu.startswith("🏠"):
    st.title("🌱 NutriWave | 结构主导的发酵配方引擎" if lang=="zh" else "🌱 NutriWave | Structure-led Fermentation Formulation Engine")
    st.subheader("需求 → 候选配方(3) → 小试DoE（可选导入消费者数据）" if lang=="zh" else "Brief → candidates(3) → mini-DoE (optional consumer data import)")

# ---------- Recipe Engine ----------
elif menu.startswith("✨"):
    st.title("✨ 生成候选配方" if lang=="zh" else "✨ Generate Candidate Formulations")
    st.caption("仅输入：Brief + Base + Texture。可选导入消费者数据以定制偏好。" if lang=="zh" else "Inputs: Brief + Base + Texture. Optional consumer data import.")

    main_col, side_col = st.columns([2, 1], gap="large")

    with main_col:
        default_text_zh = "大豆酸奶，要去除豆腥味，喜欢甜豆浆的味道，口感要柔和一点的。"
        default_text_en = "Soy yogurt; reduce beany flavor; sweet soymilk notes; softer texture."
        brief = st.text_area("需求简介 / Brief", default_text_zh if lang=="zh" else default_text_en, height=120)

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

                customer_profile = {"rows": int(len(df)),
                                    "beany_mean": _mean(col_beany),
                                    "sweet_mean": _mean(col_sweet),
                                    "texture_mean": _mean(col_texture),
                                    "overall_mean": _mean(col_overall)}
                st.success("✅ 已生成客户偏好画像" if lang=="zh" else "✅ Customer profile created")
                st.json(customer_profile)

    if generate:
        b = (brief or "").lower()
        goals = []
        if ("豆腥" in brief) or ("beany" in b) or ("off-flavor" in b):
            goals.append("anti_beany")
        if ("甜" in brief) or ("sweet" in b):
            goals.append("sweet_notes")
        if texture_sel in ["soft","thick"]:
            goals.append("eps")

        req = UserRequest(lang=lang, product_type="yogurt", base_id=base_map[base_sel], texture=texture_sel,
                          goals=goals, constraints=data.get("constraints", {}).get("default", {}))
        candidates = build_candidate_formulations(data, req, n=3, customer_profile=customer_profile)
        doe = build_minidoe_plan(req)

        pack = {"generated_at": datetime.utcnow().isoformat(),
                "brief": brief,
                "request": {"base": base_sel, "texture": texture_sel, "goals": goals},
                "customer_profile": customer_profile,
                "candidates": candidates,
                "mini_doe": doe}

        st.success("✅ 已生成候选配方！" if lang=="zh" else "✅ Candidates generated!")
        for i, cnd in enumerate(candidates, start=1):
            st.markdown(f"#### Candidate {i}")
            st.json(cnd)
        st.markdown("### Mini-DoE / 小试方法" if lang=="zh" else "### Mini-DoE")
        st.json(doe)
        st.download_button("📥 下载配方包" if lang=="zh" else "📥 Download pack",
                           data=json.dumps(pack, ensure_ascii=False, indent=2),
                           file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                           mime="application/json")

# ---------- Admin Database ----------
else:
    st.title("🧬 管理员数据库 / Admin Database")
    st.caption("现在支持：手动录入 + 上传CSV/JSON 导入（Row1/Row2/Row3），无需改代码。")

    # refresh data to include any new jsonl entries
    if st.button("🔄 刷新数据 / Refresh"):
        st.cache_data.clear()
        data = _load()
        st.success("Refreshed. / 已刷新")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Row1 菌株 / Strains",
        "Row2 流变框架 / Rheology",
        "Row3 物料与供应链 / Ingredients",
        "Row4 实验 Runs",
        "Row5 代理模型 / Models"
    ])

    # ---------- Row1 Strains ----------
    with tab1:
        st.subheader("列表 / List")
        strains = data.get("strains", [])
        df = pd.DataFrame([{
            "strain_id": s.get("strain_id",""),
            "name": s.get("name_zh","") if lang=="zh" else s.get("name_en",""),
            "supplier_id": s.get("supplier_id",""),
            "benefit_tags": ", ".join(s.get("benefit_tags", [])),
            "evidence": s.get("evidence_level",""),
        } for s in strains])
        st.dataframe(df, use_container_width=True)

        st.markdown("### ➕ 手动新增 / Add strain")
        with st.form("add_strain"):
            strain_id = st.text_input("strain_id", value=f"STR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            supplier_id = st.text_input("supplier_id", value="KT")
            benefit_tags = st.text_input("benefit_tags (comma)", value="anti_beany,eps")
            evidence = st.selectbox("evidence_level", ["seed","internal_validated","client_validated"], index=0)
            use_cases = st.text_input("recommended_use_cases (comma)", value="soy_yogurt")
            save = st.form_submit_button("保存 / Save")
            if save:
                append_strain({
                    "strain_id": strain_id,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "supplier_id": supplier_id,
                    "benefit_tags": [x.strip() for x in benefit_tags.split(",") if x.strip()],
                    "recommended_use_cases": [x.strip() for x in use_cases.split(",") if x.strip()],
                    "evidence_level": evidence
                })
                st.success("Saved. Click Refresh. / 已保存，点刷新")

        st.markdown("### ⬆️ 上传导入 / Import (CSV/JSON)")
        up = st.file_uploader("Upload strains.csv or strains.json", type=["csv","json"], key="up_strains")
        if up is not None:
            if up.name.lower().endswith(".csv"):
                imp = pd.read_csv(up).to_dict(orient="records")
            else:
                imp = json.load(up)
                if isinstance(imp, dict):
                    imp = imp.get("strains", [])
            n = 0
            for r in imp:
                if not r.get("strain_id"):
                    continue
                # normalize tags
                bt = r.get("benefit_tags", [])
                if isinstance(bt, str):
                    bt = [x.strip() for x in bt.split(",") if x.strip()]
                r["benefit_tags"] = bt
                append_strain(r)
                n += 1
            st.success(f"Imported {n} strains. Click Refresh. / 导入 {n} 条，点刷新")

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

        st.markdown("### ➕ 手动新增 / Add method")
        with st.form("add_rheo"):
            rid = st.text_input("rheo_method_id", value=f"RHEO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            instrument = st.text_input("instrument", value="Bohlin CVOR")
            geometry = st.text_input("geometry", value="12-blade vane-in-cup")
            r1_mm = st.number_input("r1_mm", min_value=0.0, value=12.5, step=0.1)
            r2_mm = st.number_input("r2_mm", min_value=0.0, value=13.85, step=0.1)
            processing_version = st.text_input("processing_version", value="nw_rheo_0.1")
            lambda_def = st.text_input("lambda_definition", value="tau_crit=tau_y*(r2/r1)^2; Lambda=tau1/tau_crit")
            rule = st.text_input("regime_rule", value="Lambda<1 partial; Lambda>=1 full")
            save = st.form_submit_button("保存 / Save")
            if save:
                append_rheo_method({
                    "rheo_method_id": rid,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "instrument": instrument,
                    "geometry": geometry,
                    "r1_mm": float(r1_mm),
                    "r2_mm": float(r2_mm),
                    "processing_version": processing_version,
                    "lambda_definition": lambda_def,
                    "regime_rule": rule
                })
                st.success("Saved. Click Refresh. / 已保存，点刷新")

        st.markdown("### ⬆️ 上传导入 / Import (CSV/JSON)")
        up = st.file_uploader("Upload rheo_methods.csv or rheo_methods.json", type=["csv","json"], key="up_rheo")
        if up is not None:
            if up.name.lower().endswith(".csv"):
                imp = pd.read_csv(up).to_dict(orient="records")
            else:
                imp = json.load(up)
                if isinstance(imp, dict):
                    imp = imp.get("rheo_methods", [])
            n = 0
            for r in imp:
                if not r.get("rheo_method_id"):
                    continue
                append_rheo_method(r)
                n += 1
            st.success(f"Imported {n} methods. Click Refresh. / 导入 {n} 条，点刷新")

    # ---------- Row3 Ingredients ----------
    with tab3:
        suppliers = {s.get("supplier_id",""): s for s in data.get("suppliers", [])}
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

        st.markdown("### ➕ 手动新增 / Add ingredient")
        with st.form("add_ing"):
            iid = st.text_input("ingredient_id", value=f"ING-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            category = st.selectbox("category", ["protein","sweetener","stabilizer","fat","flavor","other"], index=0)
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            supplier_id = st.text_input("supplier_id", value="TBD-SUP")
            clean = st.checkbox("clean_label", value=True)
            allergens = st.text_input("allergen_flags (comma)", value="")
            compat = st.text_input("compatibility_tags (comma)", value="soy")
            specs_json = st.text_area("specs (json)", value="{}")
            save = st.form_submit_button("保存 / Save")
            if save:
                try:
                    specs = json.loads(specs_json) if specs_json.strip() else {}
                except Exception:
                    specs = {"raw": specs_json}
                append_ingredient({
                    "ingredient_id": iid,
                    "category": category,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "supplier_id": supplier_id,
                    "clean_label": bool(clean),
                    "allergen_flags": [x.strip() for x in allergens.split(",") if x.strip()],
                    "compatibility_tags": [x.strip() for x in compat.split(",") if x.strip()],
                    "specs": specs
                })
                st.success("Saved. Click Refresh. / 已保存，点刷新")

        st.markdown("### ⬆️ 上传导入 / Import (CSV/JSON)")
        up = st.file_uploader("Upload ingredients.csv or ingredients.json", type=["csv","json"], key="up_ing")
        if up is not None:
            if up.name.lower().endswith(".csv"):
                imp = pd.read_csv(up).to_dict(orient="records")
            else:
                imp = json.load(up)
                if isinstance(imp, dict):
                    imp = imp.get("ingredients", [])
            n = 0
            for r in imp:
                if not r.get("ingredient_id"):
                    continue
                af = r.get("allergen_flags", [])
                if isinstance(af, str):
                    af = [x.strip() for x in af.split(",") if x.strip()]
                r["allergen_flags"] = af
                ct = r.get("compatibility_tags", [])
                if isinstance(ct, str):
                    ct = [x.strip() for x in ct.split(",") if x.strip()]
                r["compatibility_tags"] = ct
                append_ingredient(r)
                n += 1
            st.success(f"Imported {n} ingredients. Click Refresh. / 导入 {n} 条，点刷新")

    # ---------- Row4 Runs (admin-only) ----------
    with tab4:
        st.markdown("### 新增实验记录 / Add a run")
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

            c1, c2, c3, c4 = st.columns(4)
            syneresis = c1.number_input("Syneresis (%)", 0.0, 100.0, 0.0, 0.5)
            gprime = c2.number_input("G' (Pa)", 0.0, 0.0, 0.0, 10.0)
            tauy = c3.number_input("τy (Pa)", 0.0, 0.0, 0.0, 1.0)
            Lambda = c4.number_input("Λ (Lambda)", 0.0, 10.0, 0.0, 0.01)
            regime = st.selectbox("Regime", ["partial (Λ<1)","full (Λ≥1)"], index=0)

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
                st.success("Saved / 已保存（点刷新更新列表）")

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
        else:
            st.info("No runs yet.")

    # ---------- Row5 Models ----------
    with tab5:
        st.markdown("### 模型注册 / Model Registry")
        with st.form("model_form"):
            model_id = st.text_input("model_id", value=f"MODEL-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            model_type = st.selectbox("model_type", ["rule_scoring","RF","XGBoost","GP (Bayesian)","NN"], index=0)
            target_outputs = st.text_input("target_outputs (comma)", value="overall,syneresis,beany")
            feature_version = st.text_input("feature_set_version", value="v1")
            metric = st.text_input("metrics", value="TBD")
            deployed = st.checkbox("deployed_version", value=False)
            notes = st.text_area("notes", value="TBD")
            save_model = st.form_submit_button("✅ 保存模型条目 / Save model entry")
            if save_model:
                append_model({
                    "model_id": model_id,
                    "model_type": model_type,
                    "target_outputs": [x.strip() for x in target_outputs.split(",") if x.strip()],
                    "feature_set_version": feature_version,
                    "metrics": metric,
                    "deployed": bool(deployed),
                    "notes": notes
                })
                st.success("Saved / 已保存")
        models = iter_models(limit=200)
        if models:
            dfm = pd.DataFrame([{
                "timestamp": m.get("timestamp_utc",""),
                "model_id": m.get("model_id",""),
                "type": m.get("model_type",""),
                "targets": ", ".join(m.get("target_outputs", [])),
                "deployed": m.get("deployed", False)
            } for m in models])
            st.dataframe(dfm.sort_values("timestamp", ascending=False), use_container_width=True)
        else:
            st.info("No model entries yet.")
