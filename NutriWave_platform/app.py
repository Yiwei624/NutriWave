\
import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import (
    load_data,
    upsert_strain_combo, delete_strain_combo,
    upsert_ingredient, delete_ingredient,
    upsert_rheo_method, delete_rheo_method,
    upsert_supplier, delete_supplier,
    upsert_formulation, delete_formulation,
    append_run, iter_runs,
    append_model, get_latest_model
)
from core.modeling import train_surrogate
from core.engine import UserRequest, generate_candidates

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
menu = st.sidebar.radio("导航 / Navigation", ["🏠 Home", "✨ Recipe Engine"] + (["🧬 Admin Database"] if admin_ok else []))

if menu.startswith("🏠"):
    st.title("NutriWave (Rows → Fit → Engine)")
    st.write("中文：Row1复合菌｜Row2流变门槛｜Row3物料/供应商｜Row4配方+实验｜Row5拟合模型→引擎输出")
    st.write("English: Row1 combos | Row2 quality gates | Row3 ingredients/suppliers | Row4 formulations & runs | Row5 surrogate fit → engine")

elif menu.startswith("✨"):
    st.title("✨ 配方引擎 / Recipe Engine")
    col1, col2 = st.columns([2,1], gap="large")
    with col1:
        brief = st.text_area("Brief", "大豆酸奶，要去除豆腥味，口感柔和。", height=90)
        bases = data.get("bases", [])
        base_names = [b["name_zh"] if lang=="zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang=="zh" else b["name_en"]): b["id"] for b in bases}
        base_sel = st.selectbox("Base", base_names, 0)
        texture = st.selectbox("Texture", ["soft","thick","refreshing"], 0)
        go = st.button("🚀 Generate", type="primary", use_container_width=True)

    with col2:
        st.markdown("### 🧠 Model status")
        model = get_latest_model("surrogate_v1")
        if model and model.get("ok"):
            st.success(f"surrogate_v1 OK (n_used={model.get('n_used')})")
            st.caption(f"RMSE sy={model.get('rmse_syneresis'):.3f} | RMSE ov={model.get('rmse_overall'):.3f}")
        else:
            st.warning("No trained surrogate model yet.")

    if go:
        model = get_latest_model("surrogate_v1")
        req = UserRequest(lang=lang, product_type="soy_yogurt", base_id=base_map[base_sel], texture=texture, brief=brief)
        cands = generate_candidates(data, req, model=model, k=3)
        st.success("✅ Generated")
        for c in cands:
            st.markdown(f"#### {c['candidate_id']} | combo={c.get('strain_combo_id')}")
            st.json(c)
        st.download_button("Download pack", json.dumps({"generated_at":datetime.utcnow().isoformat(),"candidates":cands}, ensure_ascii=False, indent=2),
                           file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json")

else:
    st.title("🧬 Admin Database (CRUD + Row5 Fit)")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        data = _load()
        st.success("Refreshed")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Row1 Combos", "Row2 Rheology", "Row3 Ingredients/Suppliers", "Row4 Formulations/Runs", "Row5 Surrogate Fit"
    ])

    with tab1:
        combos = data.get("strains", [])
        st.dataframe(pd.DataFrame([{"id":c.get("strain_combo_id"),"name_zh":c.get("name_zh"),"tags":",".join(c.get("benefit_tags",[]))} for c in combos]), use_container_width=True)
        with st.form("combo_upsert"):
            cid = st.text_input("strain_combo_id", value=f"COMBO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            supplier_id = st.text_input("supplier_id", value="KT")
            inoc = st.text_input("inoculation_pct", value="TBD")
            tags = st.text_input("benefit_tags (comma)", value="anti_beany,eps")
            members_json = st.text_area("members (json)", value='[{"id":"TBD","ratio":"1:1"}]')
            save = st.form_submit_button("Save / Upsert")
            if save:
                try:
                    members = json.loads(members_json)
                except Exception:
                    members = [{"id":"TBD","ratio":"TBD"}]
                upsert_strain_combo({"strain_combo_id":cid,"name_zh":name_zh,"name_en":name_en,"supplier_id":supplier_id,
                                    "inoculation_pct":inoc,"benefit_tags":[x.strip() for x in tags.split(",") if x.strip()],
                                    "members":members})
                st.success("Saved. Refresh.")

        del_id = st.selectbox("Delete combo", [c.get("strain_combo_id") for c in combos] or [""])
        if st.button("Delete selected combo"):
            if del_id:
                delete_strain_combo(del_id); st.success("Deleted. Refresh.")

    with tab2:
        methods = data.get("rheo_methods", [])
        st.dataframe(pd.DataFrame([{"id":m.get("rheo_method_id"),"name_zh":m.get("name_zh"),"gates":json.dumps(m.get("quality_gates",{}), ensure_ascii=False)} for m in methods]), use_container_width=True)
        with st.form("rheo_upsert"):
            rid = st.text_input("rheo_method_id", value=f"RHEO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            name_zh = st.text_input("name_zh", value="")
            name_en = st.text_input("name_en", value="")
            req_full = st.checkbox("require_full_regime", True)
            req_torque = st.checkbox("require_torque_floor_ok", True)
            req_rep = st.checkbox("require_repeatability_ok", False)
            save = st.form_submit_button("Save / Upsert")
            if save:
                upsert_rheo_method({"rheo_method_id":rid,"name_zh":name_zh,"name_en":name_en,
                                    "quality_gates":{"require_full_regime":req_full,"require_torque_floor_ok":req_torque,"require_repeatability_ok":req_rep}})
                st.success("Saved. Refresh.")

        del_id = st.selectbox("Delete rheo_method_id", [m.get("rheo_method_id") for m in methods] or [""])
        if st.button("Delete selected method"):
            if del_id:
                delete_rheo_method(del_id); st.success("Deleted. Refresh.")

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            ing = data.get("ingredients", [])
            st.dataframe(pd.DataFrame([{"id":i.get("ingredient_id"),"cat":i.get("category"),"name_zh":i.get("name_zh"),"supplier":i.get("supplier_id")} for i in ing]), use_container_width=True)
            with st.form("ing_upsert"):
                iid = st.text_input("ingredient_id", value=f"ING-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
                cat = st.selectbox("category", ["protein","sweetener","stabilizer","fat","flavor","other"], 0)
                name_zh = st.text_input("name_zh", value="")
                name_en = st.text_input("name_en", value="")
                supplier_id = st.text_input("supplier_id", value="TBD-SUP")
                save = st.form_submit_button("Save / Upsert")
                if save:
                    upsert_ingredient({"ingredient_id":iid,"category":cat,"name_zh":name_zh,"name_en":name_en,"supplier_id":supplier_id})
                    st.success("Saved. Refresh.")
            del_ing = st.selectbox("Delete ingredient", [i.get("ingredient_id") for i in ing] or [""])
            if st.button("Delete selected ingredient"):
                if del_ing:
                    delete_ingredient(del_ing); st.success("Deleted. Refresh.")
        with c2:
            sups = data.get("suppliers", [])
            st.dataframe(pd.DataFrame([{"id":s.get("supplier_id"),"name":s.get("name"),"region":s.get("region")} for s in sups]), use_container_width=True)
            with st.form("sup_upsert"):
                sid = st.text_input("supplier_id", value=f"SUP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
                name = st.text_input("name", value="")
                region = st.text_input("region", value="UK")
                contact = st.text_input("contact", value="")
                save = st.form_submit_button("Save / Upsert")
                if save:
                    upsert_supplier({"supplier_id":sid,"name":name,"region":region,"contact":contact})
                    st.success("Saved. Refresh.")
            del_sup = st.selectbox("Delete supplier", [s.get("supplier_id") for s in sups] or [""])
            if st.button("Delete selected supplier"):
                if del_sup:
                    delete_supplier(del_sup); st.success("Deleted. Refresh.")

    with tab4:
        forms = data.get("formulations", [])
        st.dataframe(pd.DataFrame([{"id":f.get("formulation_id"),"base":f.get("base_id"),"n_items":len((f.get("ingredients") or []))} for f in forms]), use_container_width=True)

        ing = data.get("ingredients", [])
        ing_labels = [f"{i.get('ingredient_id')} | {i.get('name_zh')}" for i in ing]
        ing_map = {lab: lab.split(" | ")[0] for lab in ing_labels}
        base_ids = [b.get("id") for b in data.get("bases", [])]

        with st.form("form_upsert"):
            fid = st.text_input("formulation_id", value=f"FORM-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
            base_id = st.selectbox("base_id", base_ids, 0)
            selected = st.multiselect("pick ingredients", ing_labels, default=ing_labels[:1] if ing_labels else [])
            dosages = {}
            for lab in selected:
                dosages[lab] = st.number_input(f"{lab} dosage_kg/100kg", 0.0, 100.0, 1.0, 0.1)
            save = st.form_submit_button("Save formulation")
            if save:
                items = []
                total = 0.0
                for lab in selected:
                    kg = float(dosages[lab]); total += kg
                    items.append({"ingredient_id": ing_map[lab], "dosage_kg": kg})
                items.append({"ingredient_id": "WATER", "dosage_kg": max(0.0, 100.0-total)})
                upsert_formulation({"formulation_id": fid, "base_id": base_id, "basis": "per_100kg", "ingredients": items})
                st.success("Saved. Refresh.")

        del_form = st.selectbox("Delete formulation", [f.get("formulation_id") for f in forms] or [""])
        if st.button("Delete selected formulation"):
            if del_form:
                delete_formulation(del_form); st.success("Deleted. Refresh.")

        st.markdown("---")
        combos = data.get("strains", [])
        combo_ids = [c.get("strain_combo_id") for c in combos]
        rm_ids = [m.get("rheo_method_id") for m in data.get("rheo_methods", [])]
        form_ids = [f.get("formulation_id") for f in forms]
        form_map = {f.get("formulation_id"): f for f in forms}

        with st.form("run_add"):
            texture = st.selectbox("texture", ["soft","thick","refreshing"], 0)
            combo_id = st.selectbox("strain_combo_id", combo_ids or ["COMBO-TBD"])
            formulation_id = st.selectbox("formulation_id", form_ids or ["(create first)"])
            ferm_time = st.number_input("fermentation_time_h", 0.0, 200.0, 8.0, 0.5)
            end_ph = st.number_input("end_pH", 3.5, 6.5, 4.6, 0.05)
            rm = st.selectbox("rheo_method_id", rm_ids or ["NW-Lambda-v1"])
            torque_ok = st.checkbox("torque_floor_ok", True)
            repeat_ok = st.checkbox("repeatability_ok", True)
            regime = st.selectbox("regime", ["partial (Λ<1)","full (Λ≥1)"], 1)
            sy = st.number_input("syneresis_pct", 0.0, 100.0, 0.0, 0.5)
            overall = st.slider("overall (1-5)", 1, 5, 3)
            save = st.form_submit_button("Save run")
            if save:
                append_run({
                    "run_id": datetime.utcnow().strftime("RUN-%Y%m%d-%H%M%S"),
                    "product_type": "soy_yogurt",
                    "texture": texture,
                    "strain_combo_id": combo_id,
                    "formulation_id": formulation_id,
                    "formulation": form_map.get(formulation_id),
                    "fermentation_time_h": float(ferm_time),
                    "end_ph": float(end_ph),
                    "rheo_method_id": rm,
                    "quality_flags": {"torque_floor_ok": torque_ok, "repeatability_ok": repeat_ok},
                    "rheology": {"syneresis_pct": float(sy), "regime": regime},
                    "sensory": {"overall": int(overall)}
                })
                st.success("Saved run.")

        runs = iter_runs(limit=200)
        if runs:
            st.dataframe(pd.DataFrame([{
                "run_id": r.get("run_id"),
                "texture": r.get("texture"),
                "combo": r.get("strain_combo_id"),
                "form": r.get("formulation_id"),
                "sy": (r.get("rheology") or {}).get("syneresis_pct"),
                "regime": (r.get("rheology") or {}).get("regime"),
                "overall": (r.get("sensory") or {}).get("overall")
            } for r in runs]).tail(50), use_container_width=True)
        else:
            st.info("No runs yet.")

    with tab5:
        st.subheader("Row5 Surrogate Fit (computed from Row4 runs)")
        runs = iter_runs(limit=10000)
        gate_full = st.checkbox("Use quality gate (full regime + torque_ok)", True)
        alpha = st.number_input("Ridge alpha", 0.01, 1000.0, 1.0, 0.1)

        if st.button("Train / Retrain surrogate_v1"):
            model = train_surrogate(runs, alpha=float(alpha), gate_full=gate_full)
            model["model_type"] = "surrogate_v1"
            model["model_id"] = datetime.utcnow().strftime("SURR-%Y%m%d-%H%M%S")
            model["n_used"] = (model.get("schema") or {}).get("n_used", 0)
            append_model(model)
            st.success(f"Trained {model['model_id']} (n_used={model['n_used']})")

        latest = get_latest_model("surrogate_v1")
        if latest:
            st.json({k: latest.get(k) for k in ["model_id","ok","n_used","rmse_syneresis","rmse_overall","alpha","gate_full"]})
        else:
            st.warning("No model yet.")
