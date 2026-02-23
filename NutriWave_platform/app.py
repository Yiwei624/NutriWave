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

# -----------------------------
# i18n
# -----------------------------
I18N = {
    # Sidebar / Navigation
    "lang_selector": {"zh": "🌍 语言 / Language", "en": "🌍 Language"},
    "nav_title": {"zh": "导航", "en": "Navigation"},
    "nav_home": {"zh": "🏠 首页", "en": "🏠 Home"},
    "nav_engine": {"zh": "✨ 配方引擎", "en": "✨ Recipe Engine"},
    "nav_admin": {"zh": "🧬 管理员数据库", "en": "🧬 Admin Database"},

    # Admin auth
    "admin_pw": {"zh": "🔒 管理员密码", "en": "🔒 Admin password"},
    "admin_ok": {"zh": "✅ 已获得管理员权限", "en": "✅ Admin access granted"},
    "admin_bad": {"zh": "❌ 密码错误", "en": "❌ Incorrect password"},

    # Home
    "home_title": {"zh": "NutriWave（Rows → 拟合 → 引擎）", "en": "NutriWave (Rows → Fit → Engine)"},
    "home_line_zh": {"zh": "Row1复合菌｜Row2流变门槛｜Row3物料/供应商｜Row4配方+实验｜Row5拟合模型 → 引擎输出", "en": ""},
    "home_line_en": {"zh": "", "en": "Row1 combos | Row2 quality gates | Row3 ingredients/suppliers | Row4 formulations & runs | Row5 surrogate fit → engine"},
    "tip_lang": {"zh": "提示：语言切换已稳定（所有控件状态绑定语言）。", "en": "Tip: Language switch is stable (widgets are language-bound)."},

    # Engine page
    "engine_title": {"zh": "✨ 配方引擎", "en": "✨ Recipe Engine"},
    "brief": {"zh": "需求简介", "en": "Brief"},
    "brief_default_zh": {"zh": "大豆酸奶，要去除豆腥味，口感柔和。", "en": ""},
    "brief_default_en": {"zh": "", "en": "Soy yogurt; reduce beany flavor; soft texture."},
    "base": {"zh": "基质", "en": "Base"},
    "texture": {"zh": "口感目标", "en": "Texture target"},
    "generate": {"zh": "🚀 生成", "en": "🚀 Generate"},
    "download_pack": {"zh": "📥 下载配方包", "en": "📥 Download pack"},
    "generated_ok": {"zh": "✅ 已生成候选配方", "en": "✅ Candidates generated"},

    # Model status
    "model_status": {"zh": "🧠 模型状态", "en": "🧠 Model status"},
    "no_model": {"zh": "还没有训练好的代理模型（Row5 训练后这里会自动启用）。", "en": "No trained surrogate model yet (train in Row5 to enable)."},
    "using_model": {"zh": "正在使用 surrogate_v1（训练样本数 n_used=", "en": "Using surrogate_v1 (n_used="},

    # Consumer data
    "consumer_title": {"zh": "📊 消费者数据（可选）", "en": "📊 Consumer data (optional)"},
    "consumer_toggle": {"zh": "启用消费者数据", "en": "Enable consumer data"},
    "consumer_upload": {"zh": "上传 CSV/Excel（生成偏好画像）", "en": "Upload CSV/Excel (build preference profile)"},
    "consumer_loaded": {"zh": "已读取", "en": "Loaded"},
    "col_overall": {"zh": "总体喜好/购买意愿列", "en": "Overall liking / purchase intent column"},
    "col_sweet": {"zh": "甜味喜好列", "en": "Sweetness liking column"},
    "col_texture": {"zh": "口感/稠度喜好列", "en": "Texture/thickness liking column"},
    "col_beany": {"zh": "豆腥/异味列（越低越讨厌）", "en": "Beany/off-flavor column (lower=worse)"},
    "profile_ok": {"zh": "✅ 已生成偏好画像", "en": "✅ Preference profile created"},
    "parse_fail": {"zh": "读取失败：", "en": "Failed to parse file: "},

    # Admin page
    "admin_title": {"zh": "🧬 管理员数据库（CRUD + Row5 拟合）", "en": "🧬 Admin Database (CRUD + Row5 Fit)"},
    "refresh": {"zh": "🔄 刷新数据", "en": "🔄 Refresh data"},
    "refreshed": {"zh": "已刷新", "en": "Refreshed"},
    "row1": {"zh": "Row1 复合菌", "en": "Row1 Combos"},
    "row2": {"zh": "Row2 流变框架", "en": "Row2 Rheology"},
    "row3": {"zh": "Row3 物料/供应商", "en": "Row3 Ingredients/Suppliers"},
    "row4": {"zh": "Row4 配方/实验", "en": "Row4 Formulations/Runs"},
    "row5": {"zh": "Row5 代理模型拟合", "en": "Row5 Surrogate Fit"},

    # Common buttons/labels
    "save_upsert": {"zh": "保存 / 更新", "en": "Save / Upsert"},
    "delete_selected": {"zh": "删除所选", "en": "Delete selected"},
    "delete": {"zh": "删除", "en": "Delete"},
    "list": {"zh": "列表", "en": "List"},
    "add_update": {"zh": "新增 / 更新", "en": "Add / Update"},

    # Row1 fields
    "combo_id": {"zh": "复合菌ID", "en": "strain_combo_id"},
    "name_zh": {"zh": "中文名", "en": "name_zh"},
    "name_en": {"zh": "英文名", "en": "name_en"},
    "supplier_id": {"zh": "供应商ID", "en": "supplier_id"},
    "inoculation_pct": {"zh": "接种量(%)", "en": "inoculation_pct"},
    "benefit_tags": {"zh": "功效标签（逗号分隔）", "en": "benefit_tags (comma)"},
    "members_json": {"zh": "成员（JSON）", "en": "members (json)"},
    "delete_combo": {"zh": "删除复合菌", "en": "Delete combo"},

    # Row2 fields
    "rheo_id": {"zh": "流变方法ID", "en": "rheo_method_id"},
    "require_full": {"zh": "质量门槛：必须全动员（Λ≥1）", "en": "Gate: require full regime (Λ≥1)"},
    "require_torque": {"zh": "质量门槛：torque_floor_ok", "en": "Gate: torque_floor_ok"},
    "require_rep": {"zh": "质量门槛：repeatability_ok", "en": "Gate: repeatability_ok"},
    "delete_rheo": {"zh": "删除流变方法", "en": "Delete rheology method"},

    # Row3 fields
    "ingredient_id": {"zh": "物料ID", "en": "ingredient_id"},
    "category": {"zh": "类别", "en": "category"},
    "supplier": {"zh": "供应商", "en": "supplier"},
    "delete_ing": {"zh": "删除物料", "en": "Delete ingredient"},
    "supplier_table": {"zh": "供应商表", "en": "Suppliers"},
    "ingredient_table": {"zh": "物料表", "en": "Ingredients"},
    "sup_id": {"zh": "供应商ID", "en": "supplier_id"},
    "sup_name": {"zh": "供应商名称", "en": "supplier name"},
    "region": {"zh": "地区", "en": "region"},
    "contact": {"zh": "联系人", "en": "contact"},
    "delete_sup": {"zh": "删除供应商", "en": "Delete supplier"},

    # Row4 fields
    "form_id": {"zh": "配方ID", "en": "formulation_id"},
    "base_id": {"zh": "基质ID", "en": "base_id"},
    "pick_ing": {"zh": "选择物料", "en": "pick ingredients"},
    "dosage": {"zh": "用量（kg/100kg）", "en": "dosage_kg per 100kg"},
    "save_form": {"zh": "保存配方", "en": "Save formulation"},
    "delete_form": {"zh": "删除配方", "en": "Delete formulation"},

    "run_add": {"zh": "新增实验记录（Run）", "en": "Add run"},
    "ferm_time": {"zh": "发酵时间(h)", "en": "fermentation_time_h"},
    "end_ph": {"zh": "终点pH", "en": "end_pH"},
    "torque_ok": {"zh": "torque_floor_ok", "en": "torque_floor_ok"},
    "rep_ok": {"zh": "repeatability_ok", "en": "repeatability_ok"},
    "regime": {"zh": "动员状态", "en": "regime"},
    "syneresis": {"zh": "分水率(%)", "en": "syneresis_pct"},
    "overall": {"zh": "总体评分(1-5)", "en": "overall (1-5)"},
    "save_run": {"zh": "保存实验", "en": "Save run"},
    "saved_run": {"zh": "已保存实验记录", "en": "Run saved"},

    # Row5
    "fit_title": {"zh": "Row5：根据 Row4 Runs 自动拟合代理模型", "en": "Row5: Fit surrogate model from Row4 runs"},
    "gate_full": {"zh": "训练时启用质量门槛（full regime + torque_ok）", "en": "Use quality gate (full regime + torque_ok)"},
    "alpha": {"zh": "Ridge 正则系数 alpha", "en": "Ridge alpha"},
    "train_btn": {"zh": "训练 / 重新训练 surrogate_v1", "en": "Train / Retrain surrogate_v1"},
    "no_runs": {"zh": "还没有足够的 runs（至少 8 条含 syneresis + overall + 配方剂量）。", "en": "Not enough usable runs yet (need ≥8 with syneresis+overall+dosages)."},
}

def t(key: str) -> str:
    v = I18N.get(key, {})
    return v.get(lang, key) if isinstance(v, dict) else str(v)

# -----------------------------
# Stable widget keys with lang
# -----------------------------
def k(name: str) -> str:
    return f"{name}_{lang}"

# Clear language-bound widget state on switch
if "prev_lang" not in st.session_state:
    st.session_state["prev_lang"] = lang
elif st.session_state["prev_lang"] != lang:
    for kk in list(st.session_state.keys()):
        if kk.endswith("_zh") or kk.endswith("_en"):
            del st.session_state[kk]
    st.session_state["prev_lang"] = lang

@st.cache_data
def _load():
    return load_data()

data = _load()

# -----------------------------
# Admin check (not lang-bound)
# -----------------------------
def check_admin() -> bool:
    pw = st.sidebar.text_input(t("admin_pw"), type="password", key="admin_pw")
    if not pw:
        return False
    expected = st.secrets.get("ADMIN_PASSWORD", "")
    if expected and hmac.compare_digest(pw, expected):
        st.sidebar.success(t("admin_ok"))
        return True
    st.sidebar.error(t("admin_bad"))
    return False

admin_ok = check_admin()

menu_items = [t("nav_home"), t("nav_engine")] + ([t("nav_admin")] if admin_ok else [])
menu = st.sidebar.radio(t("nav_title"), menu_items, key=k("menu"))

# -----------------------------
# Home
# -----------------------------
if menu == t("nav_home"):
    st.title(t("home_title"))
    if lang == "zh":
        st.write(t("home_line_zh"))
    else:
        st.write(t("home_line_en"))
    st.caption(t("tip_lang"))

# -----------------------------
# Recipe Engine
# -----------------------------
elif menu == t("nav_engine"):
    st.title(t("engine_title"))
    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        default_brief = t("brief_default_zh") if lang == "zh" else t("brief_default_en")
        brief = st.text_area(t("brief"), default_brief, height=90, key=k("brief"))

        bases = data.get("bases", [])
        base_names = [b["name_zh"] if lang == "zh" else b["name_en"] for b in bases]
        base_map = {(b["name_zh"] if lang == "zh" else b["name_en"]): b["id"] for b in bases}

        base_sel = st.selectbox(t("base"), base_names, 0, key=k("base_sel"))
        texture = st.selectbox(t("texture"), ["soft", "thick", "refreshing"], 0, key=k("texture"))

        go = st.button(t("generate"), type="primary", use_container_width=True, key=k("go"))

    with col2:
        st.markdown(f"### {t('model_status')}")
        model = get_latest_model("surrogate_v1")
        if model and model.get("ok"):
            st.success(t("using_model") + f"{model.get('n_used')})")
            try:
                st.caption(f"RMSE sy={model.get('rmse_syneresis'):.3f} | RMSE ov={model.get('rmse_overall'):.3f}")
            except Exception:
                pass
        else:
            st.warning(t("no_model"))

        st.markdown("---")
        st.markdown(f"### {t('consumer_title')}")

        use_customer = st.toggle(t("consumer_toggle"), value=False, key=k("use_customer"))
        customer_profile = None

        if use_customer:
            up = st.file_uploader(t("consumer_upload"), type=["csv", "xlsx"], key=k("consumer_file"))
            if up is not None:
                try:
                    df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
                    st.caption(f"{t('consumer_loaded')} {len(df)} rows")
                    cols = ["(none)"] + list(df.columns)

                    col_overall = st.selectbox(t("col_overall"), cols, 0, key=k("col_overall"))
                    col_sweet = st.selectbox(t("col_sweet"), cols, 0, key=k("col_sweet"))
                    col_texture = st.selectbox(t("col_texture"), cols, 0, key=k("col_texture"))
                    col_beany = st.selectbox(t("col_beany"), cols, 0, key=k("col_beany"))

                    def _mean(cname: str):
                        if cname == "(none)":
                            return None
                        s = pd.to_numeric(df[cname], errors="coerce").dropna()
                        return float(s.mean()) if len(s) else None

                    customer_profile = {
                        "rows": int(len(df)),
                        "overall_mean": _mean(col_overall),
                        "sweet_mean": _mean(col_sweet),
                        "texture_mean": _mean(col_texture),
                        "beany_mean": _mean(col_beany),
                    }
                    st.success(t("profile_ok"))
                    st.json(customer_profile)
                except Exception as e:
                    st.error(t("parse_fail") + str(e))

    if go:
        model = get_latest_model("surrogate_v1")
        req = UserRequest(
            lang=lang,
            product_type="soy_yogurt",
            base_id=base_map[base_sel],
            texture=texture,
            brief=brief,
            customer_profile=customer_profile
        )
        cands = generate_candidates(data, req, model=model, k=3)
        st.success(t("generated_ok"))
        for c in cands:
            st.markdown(f"#### {c['candidate_id']} | combo={c.get('strain_combo_id')}")
            st.json(c)

        st.download_button(
            t("download_pack"),
            json.dumps({"generated_at": datetime.utcnow().isoformat(),
                        "customer_profile": customer_profile,
                        "candidates": cands},
                       ensure_ascii=False, indent=2),
            file_name=f"nutriwave_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            key=k("download_pack")
        )

# -----------------------------
# Admin Database
# -----------------------------
else:
    st.title(t("admin_title"))
    if st.button(t("refresh"), key=k("refresh")):
        st.cache_data.clear()
        data = _load()
        st.success(t("refreshed"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([t("row1"), t("row2"), t("row3"), t("row4"), t("row5")])

    # -------- Row1: Combos --------
    with tab1:
        combos = data.get("strains", [])
        st.subheader(t("combo_list"))
        st.dataframe(pd.DataFrame([{
            "id": c.get("strain_combo_id"),
            "name": c.get("name_zh") if lang=="zh" else c.get("name_en"),
            "tags": ",".join(c.get("benefit_tags", []))
        } for c in combos]), use_container_width=True)

        st.subheader(t("add_update"))
        with st.form(key=k("combo_form")):
            cid = st.text_input(t("combo_id"), value=f"COMBO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("combo_id"))
            name_zh = st.text_input(t("name_zh"), value="", key=k("combo_name_zh"))
            name_en = st.text_input(t("name_en"), value="", key=k("combo_name_en"))
            supplier_id = st.text_input(t("supplier_id"), value="KT", key=k("combo_supplier"))
            inoc = st.text_input(t("inoculation_pct"), value="TBD", key=k("combo_inoc"))
            tags = st.text_input(t("benefit_tags"), value="anti_beany,eps", key=k("combo_tags"))
            members_json = st.text_area(t("members_json"), value='[{"id":"TBD","ratio":"1:1"}]', key=k("combo_members"))
            save = st.form_submit_button(t("save_upsert"))
            if save:
                try:
                    members = json.loads(members_json)
                except Exception:
                    members = [{"id": "TBD", "ratio": "TBD"}]
                upsert_strain_combo({
                    "strain_combo_id": cid,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "supplier_id": supplier_id,
                    "inoculation_pct": inoc,
                    "benefit_tags": [x.strip() for x in tags.split(",") if x.strip()],
                    "members": members
                })
                st.success(t("refreshed"))

        st.subheader(t("delete"))
        del_id = st.selectbox(t("delete_combo"), [c.get("strain_combo_id") for c in combos] or [""], key=k("del_combo"))
        if st.button(t("delete_selected"), key=k("del_combo_btn")):
            if del_id:
                delete_strain_combo(del_id)
                st.success(t("refreshed"))

    # -------- Row2: Rheology --------
    with tab2:
        methods = data.get("rheo_methods", [])
        st.dataframe(pd.DataFrame([{
            "id": m.get("rheo_method_id"),
            "name": m.get("name_zh") if lang=="zh" else m.get("name_en"),
            "gates": json.dumps(m.get("quality_gates", {}), ensure_ascii=False)
        } for m in methods]), use_container_width=True)

        with st.form(key=k("rheo_form")):
            rid = st.text_input(t("rheo_id"), value=f"RHEO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("rheo_id"))
            name_zh = st.text_input(t("name_zh"), value="", key=k("rheo_name_zh"))
            name_en = st.text_input(t("name_en"), value="", key=k("rheo_name_en"))
            req_full = st.checkbox(t("require_full"), True, key=k("rheo_full"))
            req_torque = st.checkbox(t("require_torque"), True, key=k("rheo_torque"))
            req_rep = st.checkbox(t("require_rep"), False, key=k("rheo_rep"))
            save = st.form_submit_button(t("save_upsert"))
            if save:
                upsert_rheo_method({
                    "rheo_method_id": rid,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "quality_gates": {
                        "require_full_regime": req_full,
                        "require_torque_floor_ok": req_torque,
                        "require_repeatability_ok": req_rep
                    }
                })
                st.success(t("refreshed"))

        del_id = st.selectbox(t("delete_rheo"), [m.get("rheo_method_id") for m in methods] or [""], key=k("del_rheo"))
        if st.button(t("delete_selected"), key=k("del_rheo_btn")):
            if del_id:
                delete_rheo_method(del_id)
                st.success(t("refreshed"))

    # -------- Row3: Ingredients & Suppliers --------
    with tab3:
        c1, c2 = st.columns(2)

        with c1:
            st.subheader(t("ingredient_table"))
            ing = data.get("ingredients", [])
            st.dataframe(pd.DataFrame([{
                "id": i.get("ingredient_id"),
                "cat": i.get("category"),
                "name": i.get("name_zh") if lang=="zh" else i.get("name_en"),
                "supplier": i.get("supplier_id")
            } for i in ing]), use_container_width=True)

            with st.form(key=k("ing_form")):
                iid = st.text_input(t("ingredient_id"), value=f"ING-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("ing_id"))
                cat = st.selectbox(t("category"), ["protein","sweetener","stabilizer","fat","flavor","other"], 0, key=k("ing_cat"))
                name_zh = st.text_input(t("name_zh"), value="", key=k("ing_name_zh"))
                name_en = st.text_input(t("name_en"), value="", key=k("ing_name_en"))
                supplier_id = st.text_input(t("supplier_id"), value="TBD-SUP", key=k("ing_supplier"))
                save = st.form_submit_button(t("save_upsert"))
                if save:
                    upsert_ingredient({
                        "ingredient_id": iid,
                        "category": cat,
                        "name_zh": name_zh,
                        "name_en": name_en,
                        "supplier_id": supplier_id
                    })
                    st.success(t("refreshed"))

            del_ing = st.selectbox(t("delete_ing"), [i.get("ingredient_id") for i in ing] or [""], key=k("del_ing"))
            if st.button(t("delete_selected"), key=k("del_ing_btn")):
                if del_ing:
                    delete_ingredient(del_ing)
                    st.success(t("refreshed"))

        with c2:
            st.subheader(t("supplier_table"))
            sups = data.get("suppliers", [])
            st.dataframe(pd.DataFrame([{
                "id": s.get("supplier_id"),
                "name": s.get("name"),
                "region": s.get("region"),
                "contact": s.get("contact")
            } for s in sups]), use_container_width=True)

            with st.form(key=k("sup_form")):
                sid = st.text_input(t("sup_id"), value=f"SUP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("sup_id"))
                name = st.text_input(t("sup_name"), value="", key=k("sup_name"))
                region = st.text_input(t("region"), value="UK", key=k("sup_region"))
                contact = st.text_input(t("contact"), value="", key=k("sup_contact"))
                save = st.form_submit_button(t("save_upsert"))
                if save:
                    upsert_supplier({"supplier_id": sid, "name": name, "region": region, "contact": contact})
                    st.success(t("refreshed"))

            del_sup = st.selectbox(t("delete_sup"), [s.get("supplier_id") for s in sups] or [""], key=k("del_sup"))
            if st.button(t("delete_selected"), key=k("del_sup_btn")):
                if del_sup:
                    delete_supplier(del_sup)
                    st.success(t("refreshed"))

    # -------- Row4: Formulations & Runs --------
    with tab4:
        forms = data.get("formulations", [])
        st.subheader("Formulations" if lang=="en" else "配方列表")
        st.dataframe(pd.DataFrame([{
            "id": f.get("formulation_id"),
            "base": f.get("base_id"),
            "n_items": len((f.get("ingredients") or []))
        } for f in forms]), use_container_width=True)

        ing = data.get("ingredients", [])
        ing_labels = [f"{i.get('ingredient_id')} | {(i.get('name_zh') if lang=='zh' else i.get('name_en'))}" for i in ing]
        ing_map = {lab: lab.split(" | ")[0] for lab in ing_labels}
        base_ids = [b.get("id") for b in data.get("bases", [])]

        with st.form(key=k("form_form")):
            fid = st.text_input(t("form_id"), value=f"FORM-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("form_id"))
            base_id = st.selectbox(t("base_id"), base_ids, 0, key=k("form_base"))
            selected = st.multiselect(t("pick_ing"), ing_labels, default=ing_labels[:1] if ing_labels else [], key=k("form_ing"))
            dosages = {}
            for lab in selected:
                dosages[lab] = st.number_input(f"{lab} {t('dosage')}", 0.0, 100.0, 1.0, 0.1, key=k(f"dos_{lab}"))

            save = st.form_submit_button(t("save_form"))
            if save:
                items, total = [], 0.0
                for lab in selected:
                    kg = float(dosages[lab]); total += kg
                    items.append({"ingredient_id": ing_map[lab], "dosage_kg": kg})
                items.append({"ingredient_id": "WATER", "dosage_kg": max(0.0, 100.0-total)})
                upsert_formulation({"formulation_id": fid, "base_id": base_id, "basis": "per_100kg", "ingredients": items})
                st.success(t("refreshed"))

        del_form = st.selectbox(t("delete_form"), [f.get("formulation_id") for f in forms] or [""], key=k("del_form"))
        if st.button(t("delete_selected"), key=k("del_form_btn")):
            if del_form:
                delete_formulation(del_form)
                st.success(t("refreshed"))

        st.markdown("---")
        st.subheader(t("run_add"))
        combos = data.get("strains", [])
        combo_ids = [c.get("strain_combo_id") for c in combos]
        rm_ids = [m.get("rheo_method_id") for m in data.get("rheo_methods", [])]
        form_ids = [f.get("formulation_id") for f in forms]
        form_map = {f.get("formulation_id"): f for f in forms}

        with st.form(key=k("run_form")):
            texture = st.selectbox(t("texture"), ["soft","thick","refreshing"], 0, key=k("run_texture"))
            combo_id = st.selectbox(t("combo_id"), combo_ids or ["COMBO-TBD"], key=k("run_combo"))
            formulation_id = st.selectbox(t("form_id"), form_ids or ["(create first)"], key=k("run_formid"))
            ferm_time = st.number_input(t("ferm_time"), 0.0, 200.0, 8.0, 0.5, key=k("run_time"))
            end_ph = st.number_input(t("end_ph"), 3.5, 6.5, 4.6, 0.05, key=k("run_ph"))
            rm = st.selectbox(t("rheo_id"), rm_ids or ["NW-Lambda-v1"], key=k("run_rm"))
            torque_ok = st.checkbox(t("torque_ok"), True, key=k("run_torque"))
            repeat_ok = st.checkbox(t("rep_ok"), True, key=k("run_rep"))
            regime = st.selectbox(t("regime"), ["partial (Λ<1)","full (Λ≥1)"], 1, key=k("run_regime"))
            sy = st.number_input(t("syneresis"), 0.0, 100.0, 0.0, 0.5, key=k("run_sy"))
            overall = st.slider(t("overall"), 1, 5, 3, key=k("run_overall"))

            save = st.form_submit_button(t("save_run"))
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
                st.success(t("saved_run"))

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

    # -------- Row5: Fit --------
    with tab5:
        st.subheader(t("fit_title"))
        runs = iter_runs(limit=10000)
        gate_full = st.checkbox(t("gate_full"), True, key=k("gate_full"))
        alpha = st.number_input(t("alpha"), 0.01, 1000.0, 1.0, 0.1, key=k("alpha"))

        if st.button(t("train_btn"), key=k("train_btn")):
            model = train_surrogate(runs, alpha=float(alpha), gate_full=gate_full)
            model["model_type"] = "surrogate_v1"
            model["model_id"] = datetime.utcnow().strftime("SURR-%Y%m%d-%H%M%S")
            model["n_used"] = (model.get("schema") or {}).get("n_used", 0)
            append_model(model)
            st.success(f"{model['model_id']}  OK={model.get('ok')}  n_used={model.get('n_used')}")

        latest = get_latest_model("surrogate_v1")
        if latest:
            st.json({k2: latest.get(k2) for k2 in ["model_id","ok","n_used","rmse_syneresis","rmse_overall","alpha","gate_full"]})
        else:
            st.warning(t("no_runs"))