# -*- coding: utf-8 -*-
import streamlit as st
import json
from datetime import datetime
import pandas as pd
import hmac

from core.storage import (
    load_data,
    load_admin_db,
    upsert_strain_combo, delete_strain_combo,
    upsert_ingredient, delete_ingredient,
    upsert_rheo_method, delete_rheo_method,
    upsert_supplier, delete_supplier,
    upsert_formulation, delete_formulation,
    append_run, iter_runs,
    append_model, get_latest_model, append_qc_feedback, append_batch_sop_lock
    ,
    # New Admin DB CRUD
    upsert_supplier2, delete_supplier2,
    upsert_supplier_contact, delete_supplier_contact,
    upsert_material2, delete_material2,
    upsert_supplier_material, delete_supplier_material,
    upsert_strain_product, delete_strain_product,
    upsert_strain_component, delete_strain_component,
    upsert_material_lot, delete_material_lot,
    upsert_rheo_setup, delete_rheo_setup,
    upsert_formulation2, delete_formulation2,
    upsert_formulation_line, delete_formulation_line,
    upsert_process, delete_process,
    upsert_run2, delete_run2,
    upsert_run_result, delete_run_result,
    upsert_model_run, delete_model_run,
    upsert_model_prediction, delete_model_prediction
)
from core.modeling import train_surrogate
from core.engine import UserRequest, generate_candidates, resolve_structure_kpi, simplify_candidate, evaluate_qc_feedback, recalibrate_from_feedback

st.set_page_config(page_title="NutriWave", page_icon="🌱", layout="wide")

# -----------------------------
# i18n
# -----------------------------
I18N = {
    # Sidebar / Navigation
    "lang_selector": {"zh": "🌍 语言 / Language", "en": "🌍 Language"},
    "nav_title": {"zh": "导航", "en": "Navigation"},
    "nav_home": {"zh": "🏠 首页", "en": "🏠 Home"},
    "nav_engine": {"zh": "✨ 工艺与结构联合推演引擎", "en": "✨ Process & Structure Co-Engine"},
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
    "engine_title": {"zh": "✨ 工艺与结构联合推演引擎 (Process & Structure Co-Engine)", "en": "✨ Process & Structure Co-Engine"},
    "brief": {"zh": "需求简介", "en": "Brief"},
    "brief_default_zh": {"zh": "大豆酸奶，要去除豆腥味，口感浓稠（thick），需要可放大的工艺窗口。", "en": ""},
    "brief_default_en": {"zh": "", "en": "Soy yogurt; reduce beany flavor; thick texture; needs a scale-up-ready process window."},
    "base": {"zh": "基质", "en": "Base"},
    "texture": {"zh": "口感目标 → 结构 KPI", "en": "Texture target → Structure KPI"},
    "generate": {"zh": "🚀 生成", "en": "🚀 Generate"},
    "download_pack": {"zh": "📥 下载工艺窗口包", "en": "📥 Download process-window pack"},
    "generated_ok": {"zh": "✅ 已生成候选工艺窗口", "en": "✅ Process-window candidates generated"},


    # Process & structure engine display
    "structure_kpi_card_title": {"zh": "🧪 感官词 → 物理结构 KPI", "en": "🧪 Sensory word → physical structure KPI"},
    "process_window_title": {"zh": "🏭 工艺窗口（工厂可执行）", "en": "🏭 Process Window (factory-executable)"},
    "json_audit_caption": {"zh": "下面 JSON 只作为审计轨迹；真正交付物是其下方的工艺窗口与 QC 关卡。", "en": "The JSON below is only an audit trail; the real deliverable is the process window and QC gates below it."},
    "fermentation_temp_range": {"zh": "发酵温度区间", "en": "Fermentation temp range"},
    "max_shear_rpm": {"zh": "最大剪切/转速", "en": "Max shear / RPM"},
    "qc_stop_gate": {"zh": "发酵终止 QC", "en": "Stop QC gate"},
    "yield_stress_target": {"zh": "目标屈服应力", "en": "Target yield stress"},
    "viscosity_target": {"zh": "目标粘度", "en": "Target viscosity"},
    "predicted_yield_stress": {"zh": "预测 τy", "en": "Predicted τy"},
    "predicted_viscosity": {"zh": "预测 η", "en": "Predicted η"},
    "structure_release_gate": {"zh": "结构放行门槛", "en": "Structure release gate"},
    "scaleup_note": {"zh": "放大生产提示", "en": "Scale-up note"},
    "process_core_badge": {"zh": "核心交付物 = Process Window", "en": "Core deliverable = Process Window"},

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
    "need_formulation_first": {"zh": "请先在上方创建/填写一个有效的配方ID（配方头），再添加明细行。", "en": "Please create/enter a valid Formulation ID in the header first, then add line items."},

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

    # New Admin DB tabs
    "tab_suppliers": {"zh": "🏢 供应商/联系人", "en": "🏢 Suppliers/Contacts"},
    "tab_materials": {"zh": "📦 物料/供货关系", "en": "📦 Materials/Sourcing"},
    "tab_strains": {"zh": "🧫 菌粉目录/成分", "en": "🧫 Strain Products/Components"},
    "tab_lots": {"zh": "🧾 批次/版本（Lots）", "en": "🧾 Lots/Versions"},
    "tab_rheo_setups": {"zh": "🌀 流变配置（Setups）", "en": "🌀 Rheology Setups"},
    "tab_formulations": {"zh": "🧪 配方", "en": "🧪 Formulations"},
    "tab_runs": {"zh": "🧷 工艺/实验记录", "en": "🧷 Processes/Runs"},
    "tab_results": {"zh": "📈 实验结果", "en": "📈 Results"},
    "tab_models": {"zh": "🧠 模型拟合记录", "en": "🧠 Model Runs"},
    "tab_legacy_fit": {"zh": "🧩 旧版 Row5 拟合（不影响新库）", "en": "🧩 Legacy Row5 Fit (does not affect new DB)"},

    # Common upload labels
    "upload": {"zh": "上传文件自动填充（CSV/XLSX/JSON/JSONL）", "en": "Upload to auto-fill (CSV/XLSX/JSON/JSONL)"},
    "upload_done": {"zh": "上传完成：成功 {ok} 条，失败 {bad} 条", "en": "Upload done: {ok} ok, {bad} failed"},

    # Suppliers/Contacts fields
    "suppliers_title": {"zh": "供应商公司", "en": "Supplier Companies"},
    "contacts_title": {"zh": "联系人", "en": "Contacts"},
    "supplier_company_id": {"zh": "供应商公司ID", "en": "supplier_company_id"},
    "company_name": {"zh": "公司名", "en": "company_name"},
    "country": {"zh": "国家", "en": "country"},
    "website": {"zh": "网站", "en": "website"},
    "notes": {"zh": "备注", "en": "notes"},
    "delete_supplier2": {"zh": "删除供应商公司", "en": "Delete supplier company"},
    "contact_id": {"zh": "联系人ID", "en": "contact_id"},
    "contact_name": {"zh": "联系人姓名", "en": "name"},
    "role": {"zh": "职位", "en": "role"},
    "email": {"zh": "邮箱", "en": "email"},
    "phone": {"zh": "电话", "en": "phone"},
    "delete_contact": {"zh": "删除联系人", "en": "Delete contact"},
    "upload_suppliers": {"zh": "上传供应商公司表", "en": "Upload suppliers"},
    "upload_contacts": {"zh": "上传联系人表", "en": "Upload contacts"},

    # Materials
    "materials_title": {"zh": "物料目录", "en": "Materials Catalog"},
    "supplier_materials_title": {"zh": "供应商-物料关系", "en": "Supplier ↔ Material"},
    "material_id": {"zh": "物料ID", "en": "material_id"},
    "material_name": {"zh": "物料名称", "en": "material_name"},
    "spec_description": {"zh": "规格/说明", "en": "spec_description"},
    "catalog_no": {"zh": "货号/目录号", "en": "catalog_no"},
    "typical_pack_size": {"zh": "常见包装", "en": "typical_pack_size"},
    "lead_time_days": {"zh": "交期(天)", "en": "lead_time_days"},
    "delete_material": {"zh": "删除物料", "en": "Delete material"},
    "delete_supplier_material": {"zh": "删除供货关系", "en": "Delete supplier-material"},
    "upload_materials": {"zh": "上传物料目录", "en": "Upload materials"},
    "upload_supplier_materials": {"zh": "上传供货关系表", "en": "Upload supplier-materials"},

    # Strain products
    "strain_products_title": {"zh": "菌粉产品目录", "en": "Strain Products"},
    "strain_components_title": {"zh": "功效成分清单", "en": "Strain Components"},
    "strain_product_id": {"zh": "菌粉ID", "en": "strain_product_id"},
    "product_name": {"zh": "菌粉名字", "en": "product_name"},
    "description": {"zh": "功能宣称/描述", "en": "description"},
    "default_dosage_min": {"zh": "默认最小剂量", "en": "default_dosage_min"},
    "default_dosage_max": {"zh": "默认最大剂量", "en": "default_dosage_max"},
    "default_dosage_unit": {"zh": "默认剂量单位", "en": "default_dosage_unit"},
    "component_name": {"zh": "功效成分", "en": "component_name"},
    "claimed_value": {"zh": "标称含量", "en": "claimed_value"},
    "unit": {"zh": "单位", "en": "unit"},
    "test_method": {"zh": "测试方法", "en": "test_method"},
    "delete_strain_product": {"zh": "删除菌粉产品", "en": "Delete strain product"},
    "delete_strain_component": {"zh": "删除功效成分", "en": "Delete strain component"},
    "upload_strain_products": {"zh": "上传菌粉产品目录", "en": "Upload strain products"},
    "upload_strain_components": {"zh": "上传功效成分清单", "en": "Upload strain components"},

    # Lots
    "lots_title": {"zh": "物料批次/版本（Lots）", "en": "Material Lots / Versions"},
    "lot_id": {"zh": "批次ID", "en": "lot_id"},
    "material_type": {"zh": "类型(material/strain)", "en": "material_type"},
    "lot_number": {"zh": "批号", "en": "lot_number"},
    "manufacture_date": {"zh": "生产日期", "en": "manufacture_date"},
    "expiry_date": {"zh": "到期日期", "en": "expiry_date"},
    "coa_file": {"zh": "COA 文件/链接", "en": "coa_file"},
    "delete_lot": {"zh": "删除批次", "en": "Delete lot"},
    "upload_lots": {"zh": "上传批次表", "en": "Upload lots"},

    # Rheology setups
    "rheo_setups_title": {"zh": "流变配置（设备+几何+协议）", "en": "Rheology Setups"},
    "rheo_setup_id": {"zh": "配置ID", "en": "rheo_setup_id"},
    "rheometer_model": {"zh": "流变仪型号", "en": "rheometer_model"},
    "geometry_type": {"zh": "几何类型", "en": "geometry_type"},
    "geometry_id": {"zh": "几何ID", "en": "geometry_id"},
    "gap_mm": {"zh": "Gap(mm)", "en": "gap_mm"},
    "temperature_C": {"zh": "温度(°C)", "en": "temperature_C"},
    "protocol_id": {"zh": "协议ID", "en": "protocol_id"},
    "delete_rheo_setup": {"zh": "删除流变配置", "en": "Delete rheology setup"},
    "upload_rheo_setups": {"zh": "上传流变配置表", "en": "Upload rheology setups"},

    # Formulations
    "formulations_title": {"zh": "配方（Formulations）", "en": "Formulations"},
    "formulation_id": {"zh": "配方ID", "en": "formulation_id"},
    "is_optional": {"zh": "可选项", "en": "is_optional"},
    "delete_formulation2": {"zh": "删除配方头", "en": "Delete formulation"},
    "delete_formulation_line": {"zh": "删除明细行", "en": "Delete line"},
    "upload_formulations": {"zh": "上传配方头", "en": "Upload formulations"},
    "upload_formulation_lines": {"zh": "上传配方明细", "en": "Upload formulation lines"},

    # Processes / Runs
    "processes_title": {"zh": "工艺参数（Processes）", "en": "Processes"},
    "process_id": {"zh": "工艺ID", "en": "process_id"},
    "heat_treat_C": {"zh": "热处理温度(°C)", "en": "heat_treat_C"},
    "heat_treat_min": {"zh": "热处理时间(min)", "en": "heat_treat_min"},
    "fermentation_time_h": {"zh": "发酵时间(h)", "en": "fermentation_time_h"},
    "fermentation_temp_C": {"zh": "发酵温度(°C)", "en": "fermentation_temp_C"},
    "post_stir_rpm": {"zh": "发酵后搅拌速率(rpm)", "en": "post_stir_rpm"},
    "post_stir_min": {"zh": "发酵后搅拌时间(min)", "en": "post_stir_min"},
    "storage_time_h": {"zh": "储存时间(h)", "en": "storage_time_h"},
    "storage_temp_C": {"zh": "储存温度(°C)", "en": "storage_temp_C"},
    "delete_process": {"zh": "删除工艺", "en": "Delete process"},
    "upload_processes": {"zh": "上传工艺表", "en": "Upload processes"},
    "runs_title": {"zh": "实验记录（Runs）", "en": "Runs"},
    "run_id": {"zh": "实验ID", "en": "run_id"},
    "status": {"zh": "状态", "en": "status"},
    "starter_id": {"zh": "菌粉ID", "en": "starter_id"},
    "rheo_setup_id_in_run": {"zh": "流变配置ID", "en": "rheo_setup_id"},
    "made_at": {"zh": "制备时间", "en": "made_at"},
    "operator": {"zh": "操作者", "en": "operator"},
    "delete_run2": {"zh": "删除实验记录", "en": "Delete run"},
    "upload_runs": {"zh": "上传实验记录", "en": "Upload runs"},

    # Results
    "results_title": {"zh": "实验结果（Run Results）", "en": "Run Results"},
    "qc_flag": {"zh": "质控标记(qc_flag)", "en": "qc_flag"},
    "pH_end": {"zh": "终点pH", "en": "pH_end"},
    "delete_result": {"zh": "删除结果", "en": "Delete result"},
    "upload_results": {"zh": "上传结果表", "en": "Upload results"},

    # Results fields (Row5)
    "result_id": {"zh": "结果ID", "en": "result_id"},
    "firmness": {"zh": "firmness(质构硬度)", "en": "firmness"},
    "consistency": {"zh": "consistency(稠度)", "en": "consistency"},
    "cohesiveness": {"zh": "cohesiveness(内聚性)", "en": "cohesiveness"},
    "viscosity_index": {"zh": "viscosity_index(粘度指数)", "en": "viscosity_index"},
    "beany_min": {"zh": "最小感官异味(beany_min)", "en": "beany_min"},
    "sour_score": {"zh": "酸味(sour)", "en": "sour"},
    "grainy_or_smooth_score": {"zh": "颗粒-顺滑(grainy_or_smooth)", "en": "grainy_or_smooth"},
    "TA": {"zh": "酸度(TA)", "en": "TA"},
    "Gp_1Hz_Pa": {"zh": "Gp@1Hz (Pa)", "en": "Gp_1Hz_Pa"},
    "tauy_Pa": {"zh": "屈服应力 tauy (Pa)", "en": "tauy_Pa"},
    "recovery_pct": {"zh": "恢复率(%)", "en": "recovery_pct"},
    "measured_at": {"zh": "测量时间(measured_at)", "en": "measured_at"},
    "analyst": {"zh": "分析者(analyst)", "en": "analyst"},


    # Model runs / predictions
    "model_runs_title": {"zh": "模型训练记录（model_runs）", "en": "Model Runs"},
    "model_predictions_title": {"zh": "模型预测记录（model_predictions）", "en": "Model Predictions"},
    "model_run_id": {"zh": "模型训练ID", "en": "model_run_id"},
    "model_name": {"zh": "模型名", "en": "model_name"},
    "target": {"zh": "预测目标", "en": "target"},
    "feature_set_version": {"zh": "特征版本", "en": "feature_set_version"},
    "train_run_ids": {"zh": "训练集run_id列表(JSON)", "en": "train_run_ids (JSON)"},
    "metrics_json": {"zh": "指标(JSON)", "en": "metrics_json (JSON)"},
    "artifact_path": {"zh": "模型文件路径", "en": "artifact_path"},
    "trained_at": {"zh": "训练时间", "en": "trained_at"},
    "prediction_id": {"zh": "预测ID", "en": "prediction_id"},
    "y_pred": {"zh": "预测值", "en": "y_pred"},
    "y_true": {"zh": "真实值", "en": "y_true"},
    "delete_model_run": {"zh": "删除模型训练记录", "en": "Delete model run"},
    "delete_model_prediction": {"zh": "删除预测记录", "en": "Delete prediction"},
    "upload_model_runs": {"zh": "上传模型训练记录", "en": "Upload model runs"},
    "upload_model_predictions": {"zh": "上传预测记录", "en": "Upload predictions"},
}

# ✅ 先选择语言并得到 lang（必须在 t()/k() 前）
languages = {"中文": "zh", "English": "en"}
ui_lang_label = st.sidebar.selectbox("🌍 语言 / Language", list(languages.keys()), index=0, key="ui_lang")
lang = languages[ui_lang_label]

def t(key: str) -> str:
    v = I18N.get(key, {})
    return v.get(lang, key) if isinstance(v, dict) else str(v)


def ui(zh: str, en: str) -> str:
    return zh if lang == "zh" else en

# -----------------------------
# Stable widget keys with lang
# -----------------------------
def k(name: str) -> str:
    return f"{name}_{lang}"


def _candidate_label(candidate):
    pwin = candidate.get("process_window", {}) or {}
    return f"{candidate.get('candidate_id', 'C?')} · {pwin.get('window_id', 'PW-v1')}"


def _process_table(candidate):
    pwin = candidate.get("process_window", {}) or {}
    physical = candidate.get("predicted_physical_kpis", {}) or {}
    display = (pwin.get("display", {}) or {}).get(lang, {}) or {}
    qc = pwin.get("qc_gates", {}) or {}
    stop = qc.get("fermentation_stop", {}) or {}
    release = qc.get("structure_release", {}) or {}
    viscosity_target = (stop.get("rheological_viscosity_Pa_s", {}) or {}).get("target", 1.5)
    yield_target = (release.get("yield_stress_Pa", {}) or {}).get("target", 25)
    sy_target = (release.get("syneresis_pct", {}) or {}).get("target", 6)
    pH_target = (stop.get("pH_end", {}) or {}).get("target", 4.6)
    rows = [
        {
            ui("模块", "Module"): ui("结构 KPI", "Structure KPI"),
            ui("参数", "Parameter"): "Yield Stress τy",
            ui("目标/窗口", "Target/Window"): f"≥ {yield_target:g} Pa",
            ui("预测值", "Predicted"): f"{physical.get('yield_stress_Pa', '—')} Pa",
            ui("操作意义", "Factory meaning"): ui("结构强度达标才允许放行", "Release only when gel strength passes"),
        },
        {
            ui("模块", "Module"): ui("结构 KPI", "Structure KPI"),
            ui("参数", "Parameter"): "Viscosity η",
            ui("目标/窗口", "Target/Window"): f"≥ {viscosity_target:g} Pa·s",
            ui("预测值", "Predicted"): f"{physical.get('rheological_viscosity_Pa_s', '—')} Pa·s",
            ui("操作意义", "Factory meaning"): ui("达到粘度门槛后才能终止发酵", "Stop only after viscosity gate is met"),
        },
        {
            ui("模块", "Module"): ui("工艺窗口", "Process window"),
            ui("参数", "Parameter"): ui("发酵温度", "Fermentation temperature"),
            ui("目标/窗口", "Target/Window"): display.get("fermentation_temperature_C", "—"),
            ui("预测值", "Predicted"): "—",
            ui("操作意义", "Factory meaning"): ui("窄窗口控制，降低放大失败", "Narrow window to reduce scale-up failure"),
        },
        {
            ui("模块", "Module"): ui("工艺窗口", "Process window"),
            ui("参数", "Parameter"): ui("后搅拌最大转速", "Max post-stir RPM"),
            ui("目标/窗口", "Target/Window"): display.get("max_shear_rpm", "—"),
            ui("预测值", "Predicted"): "—",
            ui("操作意义", "Factory meaning"): ui("避免剪切破坏 EPS/蛋白凝胶网络", "Avoid shear collapse of EPS/protein gel network"),
        },
        {
            ui("模块", "Module"): "QC",
            ui("参数", "Parameter"): ui("发酵终止条件", "Fermentation stop gate"),
            ui("目标/窗口", "Target/Window"): f"pH ≤ {pH_target:g} + η ≥ {viscosity_target:g} Pa·s",
            ui("预测值", "Predicted"): "—",
            ui("操作意义", "Factory meaning"): ui("双门槛同时满足，立即停止并降温", "When both gates pass, stop and cool immediately"),
        },
        {
            ui("模块", "Module"): ui("放行", "Release"),
            ui("参数", "Parameter"): ui("析水率", "Syneresis"),
            ui("目标/窗口", "Target/Window"): f"≤ {sy_target:g}%",
            ui("预测值", "Predicted"): f"≤ {physical.get('syneresis_pct_max', '—')}%",
            ui("操作意义", "Factory meaning"): ui("货架期稳定性风险门槛", "Shelf-life stability risk gate"),
        },
    ]
    return pd.DataFrame(rows)


def _formulation_table(candidate):
    form = candidate.get("formulation", {}) or {}
    rows = []
    for it in form.get("ingredients", []) or []:
        rows.append({
            ui("物料", "Ingredient"): it.get("ingredient_id", "TBD"),
            ui("用量 kg/100kg", "Dose kg/100kg"): it.get("dosage_kg", 0),
            ui("角色", "Role"): ui("配方审计轨迹", "Formulation audit trail"),
        })
    return pd.DataFrame(rows)


def _metric_box(label, value, hint="", status="neutral"):
    border = {"green": "#16a34a", "red": "#dc2626", "yellow": "#ca8a04", "neutral": "#64748b"}.get(status, "#64748b")
    bg = {"green": "#f0fdf4", "red": "#fef2f2", "yellow": "#fefce8", "neutral": "#f8fafc"}.get(status, "#f8fafc")
    st.markdown(
        f"""
        <div style="border:2px solid {border}; background:{bg}; border-radius:16px; padding:18px; min-height:120px;">
            <div style="font-size:0.95rem; color:#334155; font-weight:700;">{label}</div>
            <div style="font-size:2.15rem; line-height:1.12; font-weight:900; color:#0f172a; margin-top:8px;">{value}</div>
            <div style="font-size:0.9rem; color:#475569; margin-top:8px;">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _latest_candidates_key():
    return k("latest_process_candidates")


def _default_engine_request(base_id="soy", texture="thick"):
    return UserRequest(
        lang=lang,
        product_type="soy_yogurt",
        base_id=base_id,
        texture=texture,
        brief=ui(
            "大豆酸奶，要去除豆腥味，口感浓稠（thick），需要可放大的工艺窗口。",
            "Soy yogurt; reduce beany flavor; thick texture; needs a scale-up-ready process window.",
        ),
        customer_profile=None,
    )


def _get_latest_or_demo_candidates():
    key = _latest_candidates_key()
    if key not in st.session_state or not st.session_state.get(key):
        model = get_latest_model("surrogate_v1")
        st.session_state[key] = generate_candidates(data, _default_engine_request(), model=model, k=3)
    return st.session_state.get(key, [])


def _render_process_window_card(candidate, show_feedback=True, operator_mode=False):
    """Render the factory-facing process window using tables/cards, not dense JSON."""
    pwin = candidate.get("process_window", {}) or {}
    physical = candidate.get("predicted_physical_kpis", {}) or {}
    display = (pwin.get("display", {}) or {}).get(lang, {}) or {}
    qc = pwin.get("qc_gates", {}) or {}
    stop_gate = (qc.get("fermentation_stop", {}) or {})
    pH_gate = stop_gate.get("pH_end", {}) or {}
    visc_gate = stop_gate.get("rheological_viscosity_Pa_s", {}) or {}

    temp_display = display.get(
        "fermentation_temperature_C",
        (pwin.get("fermentation_temperature_C", {}) or {}).get("display", "—"),
    )
    rpm_display = display.get(
        "max_shear_rpm",
        (pwin.get("maximum_shear", {}) or {}).get("display", "—"),
    )
    stop_display = display.get("qc_stop_condition", "—")
    release_display = display.get("structure_release", "—")

    with st.container(border=True):
        st.markdown(f"##### {ui('工厂可执行卡片', 'Factory-executable card')} · `{pwin.get('window_id', 'PW-v1')}`")
        m1, m2, m3 = st.columns(3)
        with m1:
            _metric_box(ui("发酵温度", "Fermentation temp"), temp_display, ui("保持在此窗口", "Hold this range"), "green")
        with m2:
            _metric_box(ui("最大转速", "Max RPM"), rpm_display, ui("超过会破坏结构", "Do not exceed"), "yellow")
        with m3:
            _metric_box(
                ui("终止 QC", "Stop QC"),
                f"pH {pH_gate.get('operator', '<=')} {pH_gate.get('target', 4.6)} + η ≥ {visc_gate.get('target', '—')}",
                ui("双门槛同时满足才停止", "Stop only when both pass"),
                "green",
            )

        if not operator_mode:
            st.dataframe(_process_table(candidate), use_container_width=True, hide_index=True)
            st.caption(ui(f"QC：{stop_display}", f"QC: {stop_display}"))
            st.caption(f"{ui('结构放行', 'Structure release')}: {release_display}")
            st.caption(
                f"{ui('放大生产提示', 'Scale-up note')}: "
                f"{(pwin.get('maximum_shear', {}) or {}).get('rationale', '—')}"
            )
        else:
            st.success(ui(f"操作指令：{stop_display}", f"Operator instruction: {stop_display}"))

    if show_feedback:
        _render_qc_feedback(candidate, operator_mode=operator_mode)
        _render_sop_lock(candidate)


def _build_batch_sop_pdf(candidate, batch_id, qc_record=None):
    """Generate a PDF digital batch record/SOP as bytes."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    buffer = BytesIO()
    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("NWNormal", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12)
    title = ParagraphStyle("NWTitle", parent=styles["Title"], fontName=font_name, fontSize=16, leading=20)
    h2 = ParagraphStyle("NWH2", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=16, spaceBefore=8)

    simple = simplify_candidate(candidate, lang=lang)
    pwin = candidate.get("process_window", {}) or {}
    display = (pwin.get("display", {}) or {}).get(lang, {}) or {}
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def P(x):
        return Paragraph(str(x), normal)

    elements = []
    elements.append(Paragraph(ui("NutriWave 数字批次 SOP / 批次报告", "NutriWave Digital Batch SOP / Batch Record"), title))
    elements.append(P(f"Batch ID: {batch_id}"))
    elements.append(P(f"Generated / Locked UTC: {generated_at}"))
    elements.append(P(f"Candidate: {candidate.get('candidate_id')} | Window: {pwin.get('window_id', 'PW-v1')} | Strain: {candidate.get('strain_combo_id')}"))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(ui("1. 工厂工艺窗口", "1. Factory Process Window"), h2))
    process_rows = [
        [P(ui("参数", "Parameter")), P(ui("指令/目标", "Instruction/Target"))],
        [P(ui("发酵温度", "Fermentation temperature")), P(display.get("fermentation_temperature_C", "—"))],
        [P(ui("最大剪切/转速", "Maximum shear/RPM")), P(display.get("max_shear_rpm", "—"))],
        [P(ui("终止 QC", "Stop QC gate")), P(display.get("qc_stop_condition", "—"))],
        [P(ui("结构放行", "Structure release")), P(display.get("structure_release", "—"))],
    ]
    table = Table(process_rows, colWidths=[48 * mm, 130 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)

    elements.append(Paragraph(ui("2. 配方审计轨迹", "2. Formulation Audit Trail"), h2))
    f_rows = [[P(ui("物料", "Ingredient")), P(ui("kg / 100kg", "kg / 100kg"))]]
    for it in simple.get("formulation_table", []):
        f_rows.append([P(it.get("ingredient", "TBD")), P(it.get("kg_per_100kg", 0))])
    ft = Table(f_rows, colWidths=[110 * mm, 68 * mm])
    ft.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(ft)

    if qc_record:
        elements.append(Paragraph(ui("3. 本批次 QC 反馈", "3. Batch QC Feedback"), h2))
        eval_result = qc_record.get("evaluation", {}) or {}
        measured = eval_result.get("measured", {}) or {}
        q_rows = [
            [P("QC status"), P(eval_result.get("status", "—"))],
            [P("pH @ 4h"), P(measured.get("ph_4h", "—"))],
            [P("Viscosity"), P(f"{measured.get('viscosity_Pa_s', '—')} Pa·s")],
            [P("Yield stress"), P(f"{measured.get('yield_stress_Pa', '—')} Pa")],
            [P("Syneresis"), P(measured.get("syneresis_observed", "—"))],
            [P("Notes"), P(qc_record.get("notes", ""))],
        ]
        qt = Table(q_rows, colWidths=[48 * mm, 130 * mm])
        qt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(qt)

    elements.append(Spacer(1, 10))
    elements.append(P(ui("签名：生产操作员 ____________    QA ____________    R&D ____________", "Sign-off: Operator ____________    QA ____________    R&D ____________")))
    elements.append(P(ui("说明：本 PDF 为数字 SOP/批次报告原型。正式 GMP/BRCGS 环境需接入电子签名、审计追踪和版本控制。", "Note: This PDF is a prototype digital SOP/batch record. GMP/BRCGS deployment requires e-signature, audit trail, and version control.")))
    doc.build(elements)
    return buffer.getvalue()


def _render_sop_lock(candidate):
    cid = candidate.get("candidate_id", "C")
    batch_key = f"batch_id_{cid}_{lang}"
    default_batch = f"NW-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{cid}"
    batch_id = st.text_input(ui("批次 ID (Batch ID)", "Batch ID"), value=st.session_state.get(batch_key, default_batch), key=batch_key)
    pdf_key = f"sop_pdf_{cid}_{lang}"
    lock_key = f"sop_lock_{cid}_{lang}"
    feedback_key = f"qc_record_{cid}_{lang}"
    qc_record = st.session_state.get(feedback_key)

    if st.button(ui("生成/锁定批次 SOP (PDF)", "Generate / Lock Batch SOP (PDF)"), key=lock_key, use_container_width=True):
        pdf_bytes = _build_batch_sop_pdf(candidate, batch_id=batch_id, qc_record=qc_record)
        st.session_state[pdf_key] = pdf_bytes
        try:
            append_batch_sop_lock({
                "batch_id": batch_id,
                "candidate_id": cid,
                "window_id": (candidate.get("process_window", {}) or {}).get("window_id"),
                "locked_at_utc": datetime.utcnow().isoformat(),
                "simple_candidate": simplify_candidate(candidate, lang=lang),
                "qc_feedback": qc_record,
            })
        except Exception as e:
            st.warning(ui(f"SOP 锁定记录写入失败：{e}", f"Failed to write SOP lock record: {e}"))
        st.success(ui("已生成并锁定本批次 SOP。", "Batch SOP generated and locked."))

    if st.session_state.get(pdf_key):
        st.download_button(
            ui("下载已锁定 SOP PDF", "Download locked SOP PDF"),
            data=st.session_state[pdf_key],
            file_name=f"{batch_id}_NutriWave_Batch_SOP.pdf",
            mime="application/pdf",
            key=f"download_sop_{cid}_{lang}",
            use_container_width=True,
        )


def _render_qc_feedback(candidate, operator_mode=False):
    cid = candidate.get("candidate_id", "C")
    pwin = candidate.get("process_window", {}) or {}
    qc = pwin.get("qc_gates", {}) or {}
    stop = qc.get("fermentation_stop", {}) or {}
    release = qc.get("structure_release", {}) or {}
    target_visc = float((stop.get("rheological_viscosity_Pa_s", {}) or {}).get("target", 1.5))
    target_yield = float((release.get("yield_stress_Pa", {}) or {}).get("target", 25.0))
    target_sy = float((release.get("syneresis_pct", {}) or {}).get("target", 6.0))
    feedback_key = f"qc_record_{cid}_{lang}"

    with st.expander(ui("录入本批次 QC 质检结果", "Enter this batch QC result"), expanded=operator_mode):
        with st.form(key=f"qc_form_{cid}_{lang}_{operator_mode}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                ph4 = st.number_input("pH @ 4h", min_value=2.5, max_value=7.5, value=4.90, step=0.01, key=f"qc_ph4_{cid}_{lang}_{operator_mode}")
                measured_visc = st.number_input(ui("实测粘度 η (Pa·s)", "Measured viscosity η (Pa·s)"), min_value=0.0, max_value=20.0, value=float(target_visc), step=0.05, key=f"qc_visc_{cid}_{lang}_{operator_mode}")
            with c2:
                measured_yield = st.number_input(ui("实测屈服应力 τy (Pa)", "Measured yield stress τy (Pa)"), min_value=0.0, max_value=500.0, value=float(target_yield), step=0.5, key=f"qc_yield_{cid}_{lang}_{operator_mode}")
                syneresis_observed = st.checkbox(ui("出现可见析水", "Visible syneresis observed"), value=False, key=f"qc_syn_obs_{cid}_{lang}_{operator_mode}")
            with c3:
                sy_pct = st.number_input(ui("析水率 %（可选）", "Syneresis % (optional)"), min_value=0.0, max_value=100.0, value=0.0, step=0.1, key=f"qc_syn_pct_{cid}_{lang}_{operator_mode}")
                operator = st.text_input(ui("质检员/操作员", "QC/operator"), value="", key=f"qc_operator_{cid}_{lang}_{operator_mode}")
            notes = st.text_area(ui("备注", "Notes"), value="", key=f"qc_notes_{cid}_{lang}_{operator_mode}")
            submitted = st.form_submit_button(ui("提交 QC 结果", "Submit QC result"), type="primary", use_container_width=True)

        if submitted:
            feedback = {
                "candidate_id": cid,
                "window_id": pwin.get("window_id"),
                "ph_4h": float(ph4),
                "measured_viscosity_Pa_s": float(measured_visc),
                "measured_yield_stress_Pa": float(measured_yield),
                "syneresis_observed": bool(syneresis_observed),
                "syneresis_pct": float(sy_pct),
                "operator": operator,
                "notes": notes,
                "created_at_utc": datetime.utcnow().isoformat(),
            }
            evaluation = evaluate_qc_feedback(candidate, feedback)
            feedback["evaluation"] = evaluation
            feedback["simple_candidate"] = simplify_candidate(candidate, lang=lang)
            st.session_state[feedback_key] = feedback
            try:
                append_qc_feedback(feedback)
                st.success(ui("QC 反馈已写入数据飞轮。", "QC feedback saved to the data flywheel."))
            except Exception as e:
                st.warning(ui(f"QC 反馈写入失败：{e}", f"Failed to save QC feedback: {e}"))

    record = st.session_state.get(feedback_key)
    if record:
        evaluation = record.get("evaluation", {}) or {}
        status = evaluation.get("status", "WATCH")
        if status == "PASS":
            st.success(ui("绿灯 PASS：本批次 QC 达标。", "GREEN PASS: this batch meets QC."))
        elif status == "WATCH":
            st.warning(ui("黄灯 WATCH：未失败，但需要继续监控。", "YELLOW WATCH: not failed, but keep monitoring."))
            for w in evaluation.get("warnings", []):
                st.caption(f"- {w}")
        else:
            st.error(ui("红灯 FAIL：QC 未达标，需要动态纠偏。", "RED FAIL: QC failed; dynamic troubleshooting required."))
            for reason in evaluation.get("fail_reasons", []):
                st.caption(f"- {reason}")
            recalc_key = f"recalibrate_{cid}_{lang}"
            if st.button(ui("一键重新计算补救方案 (Recalibrate)", "One-click Recalibrate rescue plan"), key=recalc_key, use_container_width=True):
                st.session_state[f"recalibration_{cid}_{lang}"] = recalibrate_from_feedback(candidate, record, lang=lang)
            rescue = st.session_state.get(f"recalibration_{cid}_{lang}")
            if rescue:
                st.markdown(
                    f"""
                    <div style="border:2px solid #dc2626; background:#fef2f2; border-radius:14px; padding:16px;">
                        <div style="font-size:1.1rem; font-weight:900; color:#991b1b;">{ui('临时补救指令', 'Temporary rescue instruction')}</div>
                        <div style="font-size:1.25rem; font-weight:800; color:#111827; margin-top:8px;">{rescue.get('instruction', {}).get(lang, '')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_operator_dashboard(candidate):
    pwin = candidate.get("process_window", {}) or {}
    display = (pwin.get("display", {}) or {}).get(lang, {}) or {}
    physical = candidate.get("predicted_physical_kpis", {}) or {}
    cid = candidate.get("candidate_id", "C")
    status = physical.get("status", "predicted_pass")
    light = "green" if status == "predicted_pass" else "yellow"
    st.markdown(
        f"""
        <div style="border-radius:18px; padding:18px 20px; background:#0f172a; color:white; margin-bottom:14px;">
            <div style="font-size:1.0rem; opacity:0.8;">NutriWave Operator Dashboard</div>
            <div style="font-size:2.0rem; font-weight:900;">{ui('车间操作员视角', 'Operator View')} · {cid}</div>
            <div style="font-size:1.0rem; opacity:0.9;">{ui('隐藏算法与代码，只显示可执行工艺卡片。', 'Algorithm hidden; only executable plant instructions are shown.')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
    with c1:
        _metric_box(ui("状态", "Status"), "RUN" if light == "green" else "CHECK", ui("绿灯可执行", "Green = executable"), light)
    with c2:
        _metric_box(ui("温度", "Temp"), display.get("fermentation_temperature_C", "—"), ui("保持窗口", "Hold range"), "green")
    with c3:
        _metric_box(ui("最大转速", "Max RPM"), display.get("max_shear_rpm", "—"), ui("严禁超速", "Never exceed"), "yellow")
    with c4:
        _metric_box(ui("终止门槛", "Stop gate"), "pH 4.6 + η", ui("两个条件同时满足", "Both conditions required"), "green")

    st.markdown("### " + ui("当前批次操作指令", "Current batch instruction"))
    st.info(display.get("qc_stop_condition", "—"))
    _render_process_window_card(candidate, show_feedback=True, operator_mode=True)


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

    view = st.radio(
        ui("视角切换", "View switch"),
        [ui("研发视角（R&D View）", "R&D View"), ui("车间操作员视角（Operator Dashboard）", "Operator Dashboard")],
        horizontal=True,
        key=k("engine_view"),
    )

    if view == ui("车间操作员视角（Operator Dashboard）", "Operator Dashboard"):
        cands = _get_latest_or_demo_candidates()
        labels = [_candidate_label(c) for c in cands]
        selected_label = st.selectbox(ui("选择已锁定/待执行工艺窗口", "Select locked/executable process window"), labels, key=k("operator_candidate_select"))
        selected_candidate = cands[labels.index(selected_label)] if labels else None
        if selected_candidate:
            _render_operator_dashboard(selected_candidate)
        else:
            st.warning(ui("没有可执行工艺窗口。请先在研发视角生成。", "No executable process window. Generate one in R&D View first."))

    else:
        st.caption(ui(
            "研发视角用于输入原料/口感目标、查看代理模型推演、简化 JSON、结构 KPI 和数据闭环。",
            "R&D View is for inputs, surrogate reasoning, simplified JSON, structure KPIs, and feedback-loop capture.",
        ))
        col1, col2 = st.columns([2, 1], gap="large")

        with col1:
            default_brief = t("brief_default_zh") if lang == "zh" else t("brief_default_en")
            brief = st.text_area(t("brief"), default_brief, height=90, key=k("brief"))

            bases = data.get("bases", [])
            base_names = [b["name_zh"] if lang == "zh" else b["name_en"] for b in bases]
            base_map = {(b["name_zh"] if lang == "zh" else b["name_en"]): b["id"] for b in bases}

            base_sel = st.selectbox(t("base"), base_names, 0, key=k("base_sel"))
            texture_options = ["soft", "thick", "refreshing"]
            texture = st.selectbox(t("texture"), texture_options, 1, key=k("texture"))

            structure_kpi = resolve_structure_kpi(texture, lang=lang)
            _summary = (structure_kpi.get("summary", {}) or {}).get(lang, structure_kpi.get("summary_text", ""))
            _hint = (structure_kpi.get("measurement_hint", {}) or {}).get(lang, "")
            st.markdown(
                f"""
                <div style="border:1px solid #86efac; background:#f0fdf4; border-radius:12px; padding:12px 14px; margin:8px 0 14px 0;">
                    <div style="font-weight:700; color:#14532d; margin-bottom:4px;">{t('structure_kpi_card_title')}</div>
                    <div style="font-size:0.98rem; color:#111827;">{_summary}</div>
                    <div style="font-size:0.82rem; color:#374151; margin-top:4px;">{_hint}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
                customer_profile=customer_profile,
            )
            cands = generate_candidates(data, req, model=model, k=3)
            st.session_state[_latest_candidates_key()] = cands
            st.success(t("generated_ok"))

        cands = st.session_state.get(_latest_candidates_key(), [])
        if cands:
            st.markdown("### " + ui("候选工艺窗口交付表", "Candidate process-window deliverables"))
            summary_rows = []
            for c in cands:
                sj = simplify_candidate(c, lang=lang)
                summary_rows.append({
                    ui("候选", "Candidate"): sj.get("candidate_id"),
                    ui("状态", "Status"): sj.get("status"),
                    ui("发酵温度", "Fermentation temp"): sj.get("process_window", {}).get("fermentation_temperature_C"),
                    ui("最大转速", "Max RPM"): sj.get("process_window", {}).get("maximum_shear_rpm"),
                    ui("τy 预测", "Predicted τy"): sj.get("predicted_physical_kpis", {}).get("yield_stress_Pa"),
                    ui("η 预测", "Predicted η"): sj.get("predicted_physical_kpis", {}).get("viscosity_Pa_s"),
                    ui("终止条件", "Stop condition"): sj.get("process_window", {}).get("stop_condition"),
                })
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            for c in cands:
                with st.container(border=True):
                    st.markdown(f"#### {c['candidate_id']} | combo={c.get('strain_combo_id')} | {t('process_core_badge')}")
                    _render_process_window_card(c, show_feedback=True, operator_mode=False)

                    st.markdown("##### " + ui("配方审计表（替代复杂 JSON）", "Formulation audit table (replaces dense JSON)"))
                    st.dataframe(_formulation_table(c), use_container_width=True, hide_index=True)

                    with st.expander(ui("查看简化 JSON", "View simplified JSON"), expanded=False):
                        st.json(simplify_candidate(c, lang=lang))

                    with st.expander(ui("高级：完整算法审计 JSON", "Advanced: full algorithm audit JSON"), expanded=False):
                        st.caption(t("json_audit_caption"))
                        st.json(c)

            simple_pack = {
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "simple_process_window_pack",
                "customer_profile": customer_profile,
                "candidates": [simplify_candidate(c, lang=lang) for c in cands],
            }
            st.download_button(
                t("download_pack"),
                json.dumps(simple_pack, ensure_ascii=False, indent=2),
                file_name=f"nutriwave_process_window_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                key=k("download_pack"),
                use_container_width=True,
            )
        else:
            st.info(ui("点击生成后，这里会显示表格化工艺窗口、简化 JSON、QC 反馈和 PDF SOP。", "Click Generate to show tabular process windows, simplified JSON, QC feedback, and PDF SOP."))

# -----------------------------
# Admin Database
# -----------------------------
else:
    st.title(t("admin_title"))
    if st.button(t("refresh"), key=k("refresh")):
        st.cache_data.clear()
        data = _load()
        st.success(t("refreshed"))

    # Load redesigned admin DB (separate from legacy engine DB)
    @st.cache_data
    def _load_admin():
        return load_admin_db()

    admin = _load_admin()

    # -----------------------------
    # Upload helper
    # -----------------------------
    def _read_uploaded_to_df(uploaded):
        name = (uploaded.name or "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(uploaded)
        if name.endswith(".json"):
            obj = json.load(uploaded)
            if isinstance(obj, list):
                return pd.DataFrame(obj)
            return pd.DataFrame([obj])
        if name.endswith(".jsonl"):
            rows = []
            for line in uploaded.getvalue().decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
            return pd.DataFrame(rows)
        # default: excel
        return pd.read_excel(uploaded)

    def _bulk_upsert(df: pd.DataFrame, mapping: dict, upsert_fn, id_field: str, auto_defaults=None):
        auto_defaults = auto_defaults or {}
        n_ok, n_bad = 0, 0
        for _, row in df.iterrows():
            raw = {str(k).strip(): row[k] for k in df.columns}
            rec = {}
            # map zh/en headers
            for kcol, v in raw.items():
                if pd.isna(v):
                    continue
                canon = mapping.get(kcol)
                if canon:
                    rec[canon] = v
            for kk, vv in auto_defaults.items():
                rec.setdefault(kk, vv)
            # force str ids
            if id_field in rec and rec[id_field] is not None:
                rec[id_field] = str(rec[id_field]).strip()
            try:
                upsert_fn(rec)
                n_ok += 1
            except Exception:
                n_bad += 1
        return n_ok, n_bad


    def _safe_number_input(label, min_value, max_value, value, step, key):
        """Number input that clamps persisted session_state into [min_value, max_value]."""
        if key in st.session_state:
            try:
                v = float(st.session_state[key])
            except Exception:
                v = None
            if v is None or v < min_value or v > max_value:
                st.session_state[key] = value
        return st.number_input(label, min_value, max_value, value, step, key=key)

    tabs = st.tabs([
        t("tab_suppliers"),
        t("tab_materials"),
        t("tab_strains"),
        t("tab_lots"),
        t("tab_rheo_setups"),
        t("tab_formulations"),
        t("tab_runs"),
        t("tab_results"),
        t("tab_models"),
        t("tab_legacy_fit"),
    ])

    # -------- Suppliers & Contacts --------
    with tabs[0]:
        left, right = st.columns(2)
        suppliers2 = admin.get("suppliers2", [])
        contacts = admin.get("supplier_contacts", [])

        with left:
            st.subheader(t("suppliers_title"))
            st.dataframe(pd.DataFrame(suppliers2), use_container_width=True)

            st.markdown("**" + t("upload") + "**")
            up = st.file_uploader(t("upload_suppliers"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_sup"))
            if up is not None:
                df = _read_uploaded_to_df(up)
                mapping = {
                    "supplier_company_id": "supplier_company_id", "供应商公司ID": "supplier_company_id", "供应商ID": "supplier_company_id",
                    "company_name": "company_name", "公司名": "company_name", "供应商公司名": "company_name",
                    "country": "country", "国家": "country",
                    "website": "website", "网站": "website",
                    "notes": "notes", "备注": "notes",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_supplier2, "supplier_company_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            with st.form(key=k("sup2_form")):
                sid = st.text_input(t("supplier_company_id"), value=f"SUPCO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("sup2_id"))
                name = st.text_input(t("company_name"), value="", key=k("sup2_name"))
                country = st.text_input(t("country"), value="UK", key=k("sup2_country"))
                website = st.text_input(t("website"), value="", key=k("sup2_web"))
                notes = st.text_area(t("notes"), value="", key=k("sup2_notes"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_supplier2({
                        "supplier_company_id": sid,
                        "company_name": name,
                        "country": country,
                        "website": website,
                        "notes": notes,
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_sid = st.selectbox(t("delete_supplier2"), [s.get("supplier_company_id") for s in suppliers2] or [""], key=k("del_sup2"))
            if st.button(t("delete_selected"), key=k("del_sup2_btn")):
                if del_sid:
                    delete_supplier2(del_sid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

        with right:
            st.subheader(t("contacts_title"))
            st.dataframe(pd.DataFrame(contacts), use_container_width=True)

            st.markdown("**" + t("upload") + "**")
            upc = st.file_uploader(t("upload_contacts"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_contacts"))
            if upc is not None:
                df = _read_uploaded_to_df(upc)
                mapping = {
                    "contact_id": "contact_id", "联系人ID": "contact_id",
                    "supplier_company_id": "supplier_company_id", "供应商公司ID": "supplier_company_id", "供应商ID": "supplier_company_id",
                    "name": "name", "姓名": "name", "联系人": "name",
                    "role": "role", "职位": "role",
                    "email": "email", "邮箱": "email",
                    "phone": "phone", "电话": "phone", "联系电话": "phone",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_supplier_contact, "contact_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            supplier_ids = [s.get("supplier_company_id") for s in suppliers2]
            with st.form(key=k("contact_form")):
                cid = st.text_input(t("contact_id"), value=f"CONT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("c_id"))
                scid = st.selectbox(t("supplier_company_id"), supplier_ids or [""], key=k("c_scid"))
                cname = st.text_input(t("contact_name"), value="", key=k("c_name"))
                role = st.text_input(t("role"), value="", key=k("c_role"))
                email = st.text_input(t("email"), value="", key=k("c_email"))
                phone = st.text_input(t("phone"), value="", key=k("c_phone"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_supplier_contact({
                        "contact_id": cid,
                        "supplier_company_id": scid,
                        "name": cname,
                        "role": role,
                        "email": email,
                        "phone": phone,
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_cid = st.selectbox(t("delete_contact"), [c.get("contact_id") for c in contacts] or [""], key=k("del_contact"))
            if st.button(t("delete_selected"), key=k("del_contact_btn")):
                if del_cid:
                    delete_supplier_contact(del_cid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

    # -------- Materials & Supplier-Materials --------
    with tabs[1]:
        left, right = st.columns(2)
        mats = admin.get("materials2", [])
        supm = admin.get("supplier_materials", [])
        suppliers2 = admin.get("suppliers2", [])
        supplier_ids = [s.get("supplier_company_id") for s in suppliers2]

        with left:
            st.subheader(t("materials_title"))
            st.dataframe(pd.DataFrame(mats), use_container_width=True)
            upm = st.file_uploader(t("upload_materials"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_mats"))
            if upm is not None:
                df = _read_uploaded_to_df(upm)
                mapping = {
                    "material_id": "material_id", "物料ID": "material_id",
                    "material_name": "material_name", "物料名字": "material_name", "物料名称": "material_name",
                    "category": "category", "类别": "category",
                    "spec_description": "spec_description", "规格": "spec_description", "说明": "spec_description",
                    "allergens": "allergens", "过敏原": "allergens",
                    "clean_label_tags": "clean_label_tags", "标签": "clean_label_tags",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_material2, "material_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            with st.form(key=k("mat_form")):
                mid = st.text_input(t("material_id"), value=f"MAT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("mat_id"))
                mname = st.text_input(t("material_name"), value="", key=k("mat_name"))
                cat = st.selectbox(t("category"), ["protein", "sweetener", "stabilizer", "water", "other"], 0, key=k("mat_cat"))
                spec = st.text_area(t("spec_description"), value="", key=k("mat_spec"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_material2({"material_id": mid, "material_name": mname, "category": cat, "spec_description": spec})
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_mid = st.selectbox(t("delete_material"), [m.get("material_id") for m in mats] or [""], key=k("del_mat"))
            if st.button(t("delete_selected"), key=k("del_mat_btn")):
                if del_mid:
                    delete_material2(del_mid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

        with right:
            st.subheader(t("supplier_materials_title"))
            st.dataframe(pd.DataFrame(supm), use_container_width=True)
            upsm = st.file_uploader(t("upload_supplier_materials"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_supm"))
            if upsm is not None:
                df = _read_uploaded_to_df(upsm)
                mapping = {
                    "supplier_material_id": "supplier_material_id", "关系ID": "supplier_material_id",
                    "supplier_company_id": "supplier_company_id", "供应商公司ID": "supplier_company_id", "供应商ID": "supplier_company_id",
                    "material_id": "material_id", "物料ID": "material_id",
                    "catalog_no": "catalog_no", "货号": "catalog_no",
                    "typical_pack_size": "typical_pack_size", "包装": "typical_pack_size",
                    "lead_time_days": "lead_time_days", "交期天数": "lead_time_days",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_supplier_material, "supplier_material_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            material_ids = [m.get("material_id") for m in mats]
            with st.form(key=k("supm_form")):
                scid = st.selectbox(t("supplier_company_id"), supplier_ids or [""], key=k("supm_scid"))
                mid = st.selectbox(t("material_id"), material_ids or [""], key=k("supm_mid"))
                catno = st.text_input(t("catalog_no"), value="", key=k("supm_catno"))
                pack = st.text_input(t("typical_pack_size"), value="", key=k("supm_pack"))
                lt = st.number_input(t("lead_time_days"), 0, 365, 0, 1, key=k("supm_lt"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_supplier_material({
                        "supplier_company_id": scid,
                        "material_id": mid,
                        "catalog_no": catno,
                        "typical_pack_size": pack,
                        "lead_time_days": int(lt),
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_smid = st.selectbox(t("delete_supplier_material"), [x.get("supplier_material_id") for x in supm] or [""], key=k("del_supm"))
            if st.button(t("delete_selected"), key=k("del_supm_btn")):
                if del_smid:
                    delete_supplier_material(del_smid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

    # -------- Strain products & components --------
    with tabs[2]:
        left, right = st.columns(2)
        sp = admin.get("strain_products", [])
        sc = admin.get("strain_components", [])
        suppliers2 = admin.get("suppliers2", [])
        supplier_ids = [s.get("supplier_company_id") for s in suppliers2]

        with left:
            st.subheader(t("strain_products_title"))
            st.dataframe(pd.DataFrame(sp), use_container_width=True)
            upp = st.file_uploader(t("upload_strain_products"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_sp"))
            if upp is not None:
                df = _read_uploaded_to_df(upp)
                mapping = {
                    "strain_product_id": "strain_product_id", "菌粉ID": "strain_product_id",
                    "product_name": "product_name", "菌粉名字": "product_name", "名字": "product_name",
                    "supplier_company_id": "supplier_company_id", "供应商公司ID": "supplier_company_id",
                    "description": "description", "功能宣称": "description", "描述": "description",
                    "default_dosage_min": "default_dosage_min", "默认最小剂量": "default_dosage_min",
                    "default_dosage_max": "default_dosage_max", "默认最大剂量": "default_dosage_max",
                    "default_dosage_unit": "default_dosage_unit", "默认剂量单位": "default_dosage_unit",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_strain_product, "strain_product_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            with st.form(key=k("sp_form")):
                spid = st.text_input(t("strain_product_id"), value=f"SP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("spid"))
                pname = st.text_input(t("product_name"), value="", key=k("pname"))
                scid = st.selectbox(t("supplier_company_id"), supplier_ids or [""], key=k("sp_scid"))
                desc = st.text_area(t("description"), value="", key=k("sp_desc"))
                dmin = st.number_input(t("default_dosage_min"), 0.0, 1000.0, 0.0, 0.1, key=k("sp_dmin"))
                dmax = st.number_input(t("default_dosage_max"), 0.0, 1000.0, 0.0, 0.1, key=k("sp_dmax"))
                dunit = st.text_input(t("default_dosage_unit"), value="g/L", key=k("sp_dunit"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_strain_product({
                        "strain_product_id": spid,
                        "product_name": pname,
                        "supplier_company_id": scid,
                        "description": desc,
                        "default_dosage_min": float(dmin),
                        "default_dosage_max": float(dmax),
                        "default_dosage_unit": dunit,
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_spid = st.selectbox(t("delete_strain_product"), [x.get("strain_product_id") for x in sp] or [""], key=k("del_spid"))
            if st.button(t("delete_selected"), key=k("del_sp_btn")):
                if del_spid:
                    delete_strain_product(del_spid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

        with right:
            st.subheader(t("strain_components_title"))
            st.dataframe(pd.DataFrame(sc), use_container_width=True)
            upc = st.file_uploader(t("upload_strain_components"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_sc"))
            if upc is not None:
                df = _read_uploaded_to_df(upc)
                mapping = {
                    "strain_component_id": "strain_component_id", "成分ID": "strain_component_id",
                    "strain_product_id": "strain_product_id", "菌粉ID": "strain_product_id",
                    "component_name": "component_name", "功效成分": "component_name", "成分": "component_name",
                    "claimed_value": "claimed_value", "标称含量": "claimed_value",
                    "unit": "unit", "单位": "unit",
                    "test_method": "test_method", "方法": "test_method",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_strain_component, "strain_component_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            spids = [x.get("strain_product_id") for x in sp]
            with st.form(key=k("sc_form")):
                spid = st.selectbox(t("strain_product_id"), spids or [""], key=k("sc_spid"))
                comp = st.text_input(t("component_name"), value="EPS", key=k("sc_comp"))
                val = st.text_input(t("claimed_value"), value="", key=k("sc_val"))
                unit = st.text_input(t("unit"), value="", key=k("sc_unit"))
                method = st.text_input(t("test_method"), value="", key=k("sc_method"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_strain_component({
                        "strain_product_id": spid,
                        "component_name": comp,
                        "claimed_value": val,
                        "unit": unit,
                        "test_method": method,
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_scid = st.selectbox(t("delete_strain_component"), [x.get("strain_component_id") for x in sc] or [""], key=k("del_scid"))
            if st.button(t("delete_selected"), key=k("del_sc_btn")):
                if del_scid:
                    delete_strain_component(del_scid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

    # -------- Lots --------
    with tabs[3]:
        lots = admin.get("material_lots", [])
        suppliers2 = admin.get("suppliers2", [])
        mats = admin.get("materials2", [])
        sp = admin.get("strain_products", [])
        st.subheader(t("lots_title"))
        st.dataframe(pd.DataFrame(lots), use_container_width=True)
        upl = st.file_uploader(t("upload_lots"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_lots"))
        if upl is not None:
            df = _read_uploaded_to_df(upl)
            mapping = {
                "lot_id": "lot_id", "批次ID": "lot_id",
                "material_type": "material_type", "类型": "material_type",
                "material_id": "material_id", "物料ID": "material_id",
                "strain_product_id": "strain_product_id", "菌粉ID": "strain_product_id",
                "supplier_company_id": "supplier_company_id", "供应商公司ID": "supplier_company_id",
                "lot_number": "lot_number", "批号": "lot_number",
                "manufacture_date": "manufacture_date", "生产日期": "manufacture_date",
                "expiry_date": "expiry_date", "到期日期": "expiry_date",
                "coa_file": "coa_file", "COA": "coa_file",
                "received_date": "received_date", "收货日期": "received_date",
                "concentration_or_purity_value": "concentration_or_purity_value", "纯度": "concentration_or_purity_value",
                "concentration_or_purity_unit": "concentration_or_purity_unit", "纯度单位": "concentration_or_purity_unit",
                "measured_assay_value": "measured_assay_value", "检测值": "measured_assay_value",
                "measured_assay_unit": "measured_assay_unit", "检测单位": "measured_assay_unit",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_material_lot, "lot_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        supplier_ids = [s.get("supplier_company_id") for s in suppliers2]
        material_ids = [m.get("material_id") for m in mats]
        strain_ids = [x.get("strain_product_id") for x in sp]
        with st.form(key=k("lot_form")):
            lot_id = st.text_input(t("lot_id"), value=f"LOT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("lot_id"))
            mtype = st.selectbox(t("material_type"), ["material", "strain"], 0, key=k("lot_type"))
            scid = st.selectbox(t("supplier_company_id"), supplier_ids or [""], key=k("lot_scid"))
            mid = st.selectbox(t("material_id"), material_ids or [""], key=k("lot_mid"))
            spid = st.selectbox(t("strain_product_id"), strain_ids or [""], key=k("lot_spid"))
            lotno = st.text_input(t("lot_number"), value="", key=k("lot_no"))
            mfg = st.text_input(t("manufacture_date"), value="", key=k("lot_mfg"))
            exp = st.text_input(t("expiry_date"), value="", key=k("lot_exp"))
            coa = st.text_input(t("coa_file"), value="", key=k("lot_coa"))
            if st.form_submit_button(t("save_upsert")):
                rec = {
                    "lot_id": lot_id,
                    "material_type": mtype,
                    "supplier_company_id": scid,
                    "lot_number": lotno,
                    "manufacture_date": mfg,
                    "expiry_date": exp,
                    "coa_file": coa,
                }
                if mtype == "material":
                    rec["material_id"] = mid
                else:
                    rec["strain_product_id"] = spid
                upsert_material_lot(rec)
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_lot = st.selectbox(t("delete_lot"), [x.get("lot_id") for x in lots] or [""], key=k("del_lot"))
        if st.button(t("delete_selected"), key=k("del_lot_btn")):
            if del_lot:
                delete_material_lot(del_lot)
                st.success(t("refreshed"))
                st.cache_data.clear()

    # -------- Rheology setups --------
    with tabs[4]:
        setups = admin.get("rheo_setups", [])
        st.subheader(t("rheo_setups_title"))
        st.dataframe(pd.DataFrame(setups), use_container_width=True)
        ups = st.file_uploader(t("upload_rheo_setups"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_rheo_setups"))
        if ups is not None:
            df = _read_uploaded_to_df(ups)
            mapping = {
                "rheo_setup_id": "rheo_setup_id", "配置ID": "rheo_setup_id",
                "rheometer_model": "rheometer_model", "流变仪": "rheometer_model",
                "geometry_type": "geometry_type", "几何": "geometry_type",
                "geometry_id": "geometry_id", "几何ID": "geometry_id",
                "vane_blade_number": "vane_blade_number", "叶片数": "vane_blade_number",
                "cup_id": "cup_id", "杯ID": "cup_id",
                "gap_mm": "gap_mm", "gap": "gap_mm",
                "temperature_C": "temperature_C", "温度": "temperature_C",
                "protocol_id": "protocol_id", "协议": "protocol_id",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_rheo_setup, "rheo_setup_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        with st.form(key=k("rheo_setup_form")):
            rsid = st.text_input(t("rheo_setup_id"), value=f"RS-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("rsid"))
            model = st.text_input(t("rheometer_model"), value="Bohlin CVOR", key=k("rs_model"))
            gtype = st.selectbox(t("geometry_type"), ["vane", "cone-plate", "cup-bob", "other"], 0, key=k("rs_gtype"))
            gid = st.text_input(t("geometry_id"), value="", key=k("rs_gid"))
            gap = st.number_input(t("gap_mm"), 0.0, 100.0, 1.4, 0.1, key=k("rs_gap"))
            temp = st.number_input(t("temperature_C"), -20.0, 120.0, 25.0, 0.5, key=k("rs_temp"))
            pid = st.text_input(t("protocol_id"), value="SSweep_v1", key=k("rs_pid"))
            if st.form_submit_button(t("save_upsert")):
                upsert_rheo_setup({
                    "rheo_setup_id": rsid,
                    "rheometer_model": model,
                    "geometry_type": gtype,
                    "geometry_id": gid,
                    "gap_mm": float(gap),
                    "temperature_C": float(temp),
                    "protocol_id": pid,
                })
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_rsid = st.selectbox(t("delete_rheo_setup"), [x.get("rheo_setup_id") for x in setups] or [""], key=k("del_rsid"))
        if st.button(t("delete_selected"), key=k("del_rsid_btn")):
            if del_rsid:
                delete_rheo_setup(del_rsid)
                st.success(t("refreshed"))
                st.cache_data.clear()

    # -------- Formulations (header + lines) --------
    with tabs[5]:
        forms2 = admin.get("formulations2", [])
        lines = admin.get("formulation_lines", [])
        lots = admin.get("material_lots", [])

        st.subheader(t("formulations_title"))
        df_forms = pd.DataFrame(forms2)
        if not df_forms.empty:
            st.dataframe(df_forms, use_container_width=True)

        # Upload formulations
        upf = st.file_uploader(t("upload_formulations"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_forms2"))
        if upf is not None:
            df = _read_uploaded_to_df(upf)
            mapping = {
                "formulation_id": "formulation_id", "配方ID": "formulation_id",
                "basis": "basis", "基准": "basis",
                "notes": "notes", "备注": "notes",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_formulation2, "formulation_id", auto_defaults={"basis": "g_per_L"})
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        # Active formulation selector (prevents the "no options" issue when you already have formulations)
        # We keep f2id in session_state as the single source of truth for the builder below.
        existing_fids = [x.get("formulation_id") for x in forms2 if x.get("formulation_id")]
        if k("f2id") not in st.session_state:
            st.session_state[k("f2id")] = existing_fids[0] if existing_fids else f"F2-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        active_choice = st.selectbox(
            t("formulation_id"),
            options=(existing_fids + ["+ NEW / 新建"]) if existing_fids else ["+ NEW / 新建"],
            index=(existing_fids.index(st.session_state[k("f2id")]) if st.session_state[k("f2id")] in existing_fids else (len(existing_fids) if existing_fids else 0)),
            key=k("f2_active_select"),
        )
        if active_choice != "+ NEW / 新建":
            st.session_state[k("f2id")] = active_choice

        with st.form(key=k("form2_form")):
            # If user chooses NEW, prefill a new id; otherwise edit the selected one.
            _default_new = f"F2-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            fid = st.text_input(
                t("formulation_id"),
                value=(_default_new if active_choice == "+ NEW / 新建" else st.session_state[k("f2id")]),
                key=k("f2id"),
            )
            # Show associated line IDs under the formulation ID (read-only helper)
            _line_ids_for_fid = [x.get("line_id") for x in lines if x.get("formulation_id") == fid and not x.get("is_deleted")]
            if _line_ids_for_fid:
                st.caption(f"{t('line_id')}: {', '.join(_line_ids_for_fid[:20])}{' …' if len(_line_ids_for_fid) > 20 else ''}")
            else:
                st.caption(f"{t('line_id')}: (none)")
            basis = st.text_input(t("basis"), value="g_per_L", key=k("f2basis"))
            notes = st.text_area(t("notes"), value="", key=k("f2notes"))
            if st.form_submit_button(t("save_upsert")):
                upsert_formulation2({"formulation_id": fid, "basis": basis, "notes": notes})
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_fid = st.selectbox(t("delete_formulation2"), [x.get("formulation_id") for x in forms2] or [""], key=k("del_f2"))
        if st.button(t("delete_selected"), key=k("del_f2_btn")):
            if del_fid:
                delete_formulation2(del_fid)
                st.success(t("refreshed"))
                st.cache_data.clear()

        st.markdown("---")
        st.subheader(t("formulation_lines_title"))
        df_lines = pd.DataFrame(lines)
        if not df_lines.empty:
            st.dataframe(df_lines, use_container_width=True)

        upln = st.file_uploader(t("upload_formulation_lines"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_lines"))
        if upln is not None:
            df = _read_uploaded_to_df(upln)
            mapping = {
                "line_id": "line_id", "明细ID": "line_id",
                "formulation_id": "formulation_id", "配方ID": "formulation_id",
                "lot_id": "lot_id", "批次ID": "lot_id",
                "role": "role", "角色": "role",
                "amount_value": "amount_value", "用量": "amount_value",
                "amount_unit": "amount_unit", "单位": "amount_unit",
                "is_optional": "is_optional", "可选": "is_optional",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_formulation_line, "line_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()
        lot_ids = [x.get("lot_id") for x in lots]
        form_ids = [x.get("formulation_id") for x in forms2]
        strain_products = admin.get("strain_products", [])
        # Admin DB stores materials under key "materials2" (admin_materials.jsonl)
        materials = admin.get("materials2", [])

        st.markdown("### " + t("formulation_builder_title"))
        st.caption(t("formulation_builder_help"))

        strain_opts = [x.get("strain_product_id") for x in strain_products if x.get("strain_product_id")]
        material_opts = [x.get("material_id") for x in materials if x.get("material_id")]
        with st.form(key=k("form_builder")):
            # Row 1: Formulation ID (from header)
            fid = st.session_state.get(k("f2id"), "")
            st.text_input(t("formulation_id"), value=fid, disabled=True, key=k("fb_fid"))

            # Row 2: Lot ID (batch/version)
            lot = st.selectbox(t("lot_id"), lot_ids or [""], key=k("fb_lot"))

            # Row 3: Strain table (multi rows, g/L) — dynamic add/delete rows
            st.markdown("#### " + t("strain_lines"))
            default_strain_df = pd.DataFrame([{
                "strain_product_id": "",
                "amount_value": 0.0,
                "amount_unit": "g/L",
                "is_optional": False,
            }])
            s_df = st.data_editor(
                default_strain_df,
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "strain_product_id": st.column_config.SelectboxColumn(
                        t("strain_product_id"),
                        options=(strain_opts or [""]),
                        required=False,
                    ),
                    "amount_value": st.column_config.NumberColumn(t("amount_value"), min_value=0.0, step=0.1),
                    "amount_unit": st.column_config.TextColumn(t("amount_unit")),
                    "is_optional": st.column_config.CheckboxColumn(t("is_optional")),
                },
                key=k("fb_s_df_dyn"),
            )

            # Row 4: Material table (multi rows, g/L) — dynamic add/delete rows
            st.markdown("#### " + t("material_lines"))
            default_material_df = pd.DataFrame([{
                "material_id": "",
                "amount_value": 0.0,
                "amount_unit": "g/L",
                "is_optional": False,
            }])
            m_df = st.data_editor(
                default_material_df,
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "material_id": st.column_config.SelectboxColumn(
                        t("material_id"),
                        options=(material_opts or [""]),
                        required=False,
                    ),
                    "amount_value": st.column_config.NumberColumn(t("amount_value"), min_value=0.0, step=0.1),
                    "amount_unit": st.column_config.TextColumn(t("amount_unit")),
                    "is_optional": st.column_config.CheckboxColumn(t("is_optional")),
                },
                key=k("fb_m_df_dyn"),
            )

            if st.form_submit_button(t("save_upsert")):
                if not fid or fid not in form_ids:
                    st.error(t("need_formulation_first"))
                    st.stop()
                if not lot:
                    st.error(t("need_lot_first"))
                    st.stop()

                ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')

                # Write strain lines
                for _, row in (s_df if isinstance(s_df, pd.DataFrame) else pd.DataFrame()).iterrows():
                    sid = str(row.get('strain_product_id') or '').strip()
                    if not sid:
                        continue
                    line_id = f"L-{ts}-S-{sid}"
                    upsert_formulation_line({
                        'line_id': line_id,
                        'formulation_id': fid,
                        'lot_id': lot,
                        'role': 'strain',
                        'amount_value': float(row.get('amount_value') or 0.0),
                        'amount_unit': str(row.get('amount_unit') or 'g/L'),
                        'is_optional': bool(row.get('is_optional') or False),
                        'strain_product_id': sid,
                    })

                # Write material lines
                for _, row in (m_df if isinstance(m_df, pd.DataFrame) else pd.DataFrame()).iterrows():
                    mid = str(row.get('material_id') or '').strip()
                    if not mid:
                        continue
                    line_id = f"L-{ts}-M-{mid}"
                    upsert_formulation_line({
                        'line_id': line_id,
                        'formulation_id': fid,
                        'lot_id': lot,
                        'role': 'material',
                        'amount_value': float(row.get('amount_value') or 0.0),
                        'amount_unit': str(row.get('amount_unit') or 'g/L'),
                        'is_optional': bool(row.get('is_optional') or False),
                        'material_id': mid,
                    })

                st.success(t("refreshed"))
                st.cache_data.clear()



        del_line = st.selectbox(t("delete_formulation_line"), [x.get("line_id") for x in lines] or [""], key=k("del_line"))
        if st.button(t("delete_selected"), key=k("del_line_btn")):
            if del_line:
                delete_formulation_line(del_line)
                st.success(t("refreshed"))
                st.cache_data.clear()

    # -------- Runs (processes + runs) --------
    with tabs[6]:
        processes = admin.get("processes", [])
        runs2 = admin.get("runs2", [])
        st.subheader(t("processes_title"))
        st.dataframe(pd.DataFrame(processes), use_container_width=True)

        upp = st.file_uploader(t("upload_processes"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_proc"))
        if upp is not None:
            df = _read_uploaded_to_df(upp)
            mapping = {
                "process_id": "process_id", "工艺ID": "process_id",
                "heat_treat_C": "heat_treat_C", "热处理温度": "heat_treat_C",
                "heat_treat_min": "heat_treat_min", "热处理时间": "heat_treat_min",
                "fermentation_time_h": "fermentation_time_h", "发酵时间": "fermentation_time_h",
                "fermentation_temp_C": "fermentation_temp_C", "发酵温度": "fermentation_temp_C",
                "post_stir_rpm": "post_stir_rpm", "搅拌速率": "post_stir_rpm",
                "post_stir_min": "post_stir_min", "搅拌时间": "post_stir_min",
                "storage_time_h": "storage_time_h", "储存时间": "storage_time_h",
                "storage_temp_C": "storage_temp_C", "储存温度": "storage_temp_C",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_process, "process_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        with st.form(key=k("proc_form")):
            pid = st.text_input(t("process_id"), value=f"P-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("pid"))
            htC = st.number_input(t("heat_treat_C"), 0.0, 130.0, 0.0, 1.0, key=k("htC"))
            htm = st.number_input(t("heat_treat_min"), 0.0, 240.0, 0.0, 1.0, key=k("htm"))
            ft = st.number_input(t("fermentation_time_h"), 0.0, 240.0, 0.0, 0.5, key=k("ft"))
            fT = st.number_input(t("fermentation_temp_C"), 0.0, 60.0, 0.0, 0.5, key=k("fT"))
            rpm = st.number_input(t("post_stir_rpm"), 0.0, 3000.0, 0.0, 10.0, key=k("rpm"))
            stm = st.number_input(t("post_stir_min"), 0.0, 240.0, 0.0, 1.0, key=k("stm"))
            stH = st.number_input(t("storage_time_h"), 0.0, 10000.0, 0.0, 1.0, key=k("stH"))
            stT = st.number_input(t("storage_temp_C"), -10.0, 40.0, 0.0, 0.5, key=k("stT"))
            if st.form_submit_button(t("save_upsert")):
                upsert_process({
                    "process_id": pid,
                    "heat_treat_C": float(htC),
                    "heat_treat_min": float(htm),
                    "fermentation_time_h": float(ft),
                    "fermentation_temp_C": float(fT),
                    "post_stir_rpm": float(rpm),
                    "post_stir_min": float(stm),
                    "storage_time_h": float(stH),
                    "storage_temp_C": float(stT),
                })
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_pid = st.selectbox(t("delete_process"), [x.get("process_id") for x in processes] or [""], key=k("del_pid"))
        if st.button(t("delete_selected"), key=k("del_pid_btn")):
            if del_pid:
                delete_process(del_pid)
                st.success(t("refreshed"))
                st.cache_data.clear()

        st.markdown("---")
        st.subheader(t("runs_title"))
        st.dataframe(pd.DataFrame(runs2), use_container_width=True)

        upr = st.file_uploader(t("upload_runs"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_runs2"))
        if upr is not None:
            df = _read_uploaded_to_df(upr)
            mapping = {
                "result_id": "result_id", "结果ID": "result_id", "run_id": "run_id", "实验ID": "run_id",
                "status": "status", "状态": "status",
                "formulation_id": "formulation_id", "配方ID": "formulation_id",
                "process_id": "process_id", "工艺ID": "process_id",
                "starter_id": "starter_id", "菌粉ID": "starter_id",
                "rheo_setup_id": "rheo_setup_id", "流变配置ID": "rheo_setup_id", "配置ID": "rheo_setup_id",
                "made_at": "made_at", "制备时间": "made_at",
                "operator": "operator", "操作者": "operator",
                "notes": "notes", "备注": "notes",
                "raw_files": "raw_files", "原始文件": "raw_files",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_run2, "run_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        form_ids = [x.get("formulation_id") for x in admin.get("formulations2", [])]
        proc_ids = [x.get("process_id") for x in processes]
        starter_ids = [x.get("strain_product_id") for x in admin.get("strain_products", [])]
        rheo_setup_ids = [x.get("rheo_setup_id") for x in admin.get("rheo_setups", [])]
        with st.form(key=k("run2_form")):
            rid = st.text_input(t("run_id"), value=f"RUN2-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("run2_id"))
            status = st.selectbox(t("status"), ["planned", "done", "failed"], 0, key=k("run2_status"))
            fid = st.selectbox(t("formulation_id"), form_ids or [""], key=k("run2_fid"))
            pid = st.selectbox(t("process_id"), proc_ids or [""], key=k("run2_pid"))
            sid = st.selectbox(t("starter_id"), starter_ids or [""], key=k("run2_sid"))
            rsid = st.selectbox(t("rheo_setup_id_in_run"), rheo_setup_ids or [""], key=k("run2_rsid"))
            made_at = st.text_input(t("made_at"), value=datetime.utcnow().isoformat(), key=k("run2_made"))
            op = st.text_input(t("operator"), value="", key=k("run2_op"))
            notes = st.text_area(t("notes"), value="", key=k("run2_notes"))
            if st.form_submit_button(t("save_upsert")):
                upsert_run2({
                    "run_id": rid,
                    "status": status,
                    "formulation_id": fid,
                    "process_id": pid,
                    "starter_id": sid,
                    "rheo_setup_id": rsid,
                    "made_at": made_at,
                    "operator": op,
                    "notes": notes,
                })
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_rid = st.selectbox(t("delete_run2"), [x.get("run_id") for x in runs2] or [""], key=k("del_run2"))
        if st.button(t("delete_selected"), key=k("del_run2_btn")):
            if del_rid:
                delete_run2(del_rid)
                st.success(t("refreshed"))
                st.cache_data.clear()

    # -------- Results --------
    with tabs[7]:
        res = admin.get("run_results", [])
        st.subheader(t("results_title"))
        st.dataframe(pd.DataFrame(res), use_container_width=True)

        uprs = st.file_uploader(t("upload_results"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_results"))
        if uprs is not None:
            df = _read_uploaded_to_df(uprs)
            mapping = {
                "result_id": "result_id", "结果ID": "result_id", "run_id": "run_id", "实验ID": "run_id",
                "firmness": "firmness", "firmness": "firmness",
                "consistency": "consistency", "consistency": "consistency",
                "cohesiveness": "cohesiveness", "cohesiveness": "cohesiveness",
                "viscosity_index": "viscosity_index", "viscosity_index": "viscosity_index",
                "beany_min": "beany_min", "异味": "beany_min",
                "sour": "sour", "酸": "sour",
                "grainy_or_smooth": "grainy_or_smooth", "颗粒": "grainy_or_smooth",
                "overall": "overall", "总体": "overall",
                "syneresis_pct": "syneresis_pct", "析水率": "syneresis_pct",
                "TA": "TA", "酸度TA": "TA",
                "pH_end": "pH_end", "终点pH": "pH_end",
                "Gp_1Hz_Pa": "Gp_1Hz_Pa", "Gp": "Gp_1Hz_Pa",
                "tauy_Pa": "tauy_Pa", "tauy": "tauy_Pa",
                "recovery_pct": "recovery_pct", "恢复": "recovery_pct",
                "qc_flag": "qc_flag", "质控": "qc_flag",
                "measured_at": "measured_at", "测量时间": "measured_at",
                "analyst": "analyst", "分析者": "analyst",
            }
            ok, bad = _bulk_upsert(df, mapping, upsert_run_result, "run_id")
            st.success(t("upload_done").format(ok=ok, bad=bad))
            st.cache_data.clear()

        run_ids = [x.get("run_id") for x in admin.get("runs2", [])]
        with st.form(key=k("res_form")):
            # Result ID (optional metadata; run_id remains PK)
            result_id = st.text_input(t("result_id"), value=f"RES-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("res_result_id"))
            rid = st.selectbox(t("run_id"), run_ids or [""], key=k("res_rid"))

            colA, colB, colC = st.columns(3)
            with colA:
                firmness = _safe_number_input(t("firmness"), 0.0, 1e9, 0.0, 1.0, key=k("res_firm"))
                consistency = _safe_number_input(t("consistency"), 0.0, 1e9, 0.0, 1.0, key=k("res_cons"))
                cohesiveness = _safe_number_input(t("cohesiveness"), 0.0, 1e9, 0.0, 0.01, key=k("res_coh"))
                viscosity_index = _safe_number_input(t("viscosity_index"), 0.0, 1e9, 0.0, 1.0, key=k("res_vi"))

            with colB:
                beany_min = _safe_number_input(t("beany_min"), 0.0, 5.0, 0.0, 0.1, key=k("res_beany"))
                sour = _safe_number_input(t("sour_score"), 0.0, 5.0, 0.0, 0.1, key=k("res_sour"))
                grainy_or_smooth = _safe_number_input(t("grainy_or_smooth_score"), 0.0, 5.0, 0.0, 0.1, key=k("res_grain"))
                overall = _safe_number_input(t("overall"), 1.0, 5.0, 4.0, 0.1, key=k("res_overall"))

            with colC:
                sy = _safe_number_input(t("syneresis"), 0.0, 100.0, 0.0, 0.1, key=k("res_sy"))
                TA = _safe_number_input(t("TA"), 0.0, 200.0, 0.0, 0.1, key=k("res_ta"))
                ph = _safe_number_input(t("pH_end"), 2.0, 8.0, 4.50, 0.01, key=k("res_ph"))
                Gp = _safe_number_input(t("Gp_1Hz_Pa"), 0.0, 1e9, 0.0, 1.0, key=k("res_gp"))
                tauy = _safe_number_input(t("tauy_Pa"), 0.0, 1e9, 0.0, 1.0, key=k("res_tauy"))
                recovery = _safe_number_input(t("recovery_pct"), 0.0, 200.0, 0.0, 0.1, key=k("res_rec"))

            analyst = st.text_input(t("analyst"), value="", key=k("res_analyst"))
            qc = st.selectbox(t("qc_flag"), ["pass", "suspect", "fail"], 0, key=k("res_qc"))

            if st.form_submit_button(t("save_upsert")):
                upsert_run_result({
                    "run_id": rid,
                    "result_id": result_id,
                    "firmness": float(firmness),
                    "consistency": float(consistency),
                    "cohesiveness": float(cohesiveness),
                    "viscosity_index": float(viscosity_index),
                    "beany_min": float(beany_min),
                    "sour": float(sour),
                    "grainy_or_smooth": float(grainy_or_smooth),
                    "overall": float(overall),
                    "syneresis_pct": float(sy),
                    "TA": float(TA),
                    "pH_end": float(ph),
                    "Gp_1Hz_Pa": float(Gp),
                    "tauy_Pa": float(tauy),
                    "recovery_pct": float(recovery),
                    "analyst": analyst,
                    "qc_flag": qc,
                    "measured_at": datetime.utcnow().isoformat(),
                })
                st.success(t("refreshed"))
                st.cache_data.clear()

        del_res = st.selectbox(t("delete_result"), [x.get("run_id") for x in res] or [""], key=k("del_res"))
        if st.button(t("delete_selected"), key=k("del_res_btn")):
            if del_res:
                delete_run_result(del_res)
                st.success(t("refreshed"))
                st.cache_data.clear()

    # -------- Models (Row6) --------
    with tabs[8]:
        mr = admin.get("model_runs", [])
        mp = admin.get("model_predictions", [])
        left, right = st.columns(2)
        with left:
            st.subheader(t("model_runs_title"))
            st.dataframe(pd.DataFrame(mr), use_container_width=True)
            upmr = st.file_uploader(t("upload_model_runs"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_mr"))
            if upmr is not None:
                df = _read_uploaded_to_df(upmr)
                mapping = {
                    "model_run_id": "model_run_id", "模型训练ID": "model_run_id",
                    "model_name": "model_name", "模型名": "model_name",
                    "target": "target", "目标": "target",
                    "feature_set_version": "feature_set_version", "特征版本": "feature_set_version",
                    "train_run_ids": "train_run_ids", "训练集": "train_run_ids",
                    "metrics_json": "metrics_json", "指标": "metrics_json",
                    "artifact_path": "artifact_path", "模型文件": "artifact_path",
                    "trained_at": "trained_at", "训练时间": "trained_at",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_model_run, "model_run_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            with st.form(key=k("mr_form")):
                mid = st.text_input(t("model_run_id"), value=f"MR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("mr_id"))
                mname = st.text_input(t("model_name"), value="RF", key=k("mr_name"))
                target = st.text_input(t("target"), value="overall", key=k("mr_target"))
                fver = st.text_input(t("feature_set_version"), value="v1", key=k("mr_fver"))
                run_ids = st.text_area(t("train_run_ids"), value="[]", key=k("mr_runs"))
                metrics = st.text_area(t("metrics_json"), value="{}", key=k("mr_metrics"))
                art = st.text_input(t("artifact_path"), value="", key=k("mr_art"))
                if st.form_submit_button(t("save_upsert")):
                    try:
                        run_ids_obj = json.loads(run_ids)
                    except Exception:
                        run_ids_obj = []
                    try:
                        metrics_obj = json.loads(metrics)
                    except Exception:
                        metrics_obj = {}
                    upsert_model_run({
                        "model_run_id": mid,
                        "model_name": mname,
                        "target": target,
                        "feature_set_version": fver,
                        "train_run_ids": run_ids_obj,
                        "metrics_json": metrics_obj,
                        "artifact_path": art,
                        "trained_at": datetime.utcnow().isoformat(),
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_mrid = st.selectbox(t("delete_model_run"), [x.get("model_run_id") for x in mr] or [""], key=k("del_mrid"))
            if st.button(t("delete_selected"), key=k("del_mrid_btn")):
                if del_mrid:
                    delete_model_run(del_mrid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

        with right:
            st.subheader(t("model_predictions_title"))
            st.dataframe(pd.DataFrame(mp), use_container_width=True)
            upp = st.file_uploader(t("upload_model_predictions"), type=["csv", "xlsx", "xls", "json", "jsonl"], key=k("up_mp"))
            if upp is not None:
                df = _read_uploaded_to_df(upp)
                mapping = {
                    "prediction_id": "prediction_id", "预测ID": "prediction_id",
                    "model_run_id": "model_run_id", "模型训练ID": "model_run_id",
                    "result_id": "result_id", "结果ID": "result_id", "run_id": "run_id", "实验ID": "run_id",
                    "y_pred": "y_pred", "预测": "y_pred",
                    "y_true": "y_true", "真实": "y_true",
                    "created_at": "created_at", "创建时间": "created_at",
                }
                ok, bad = _bulk_upsert(df, mapping, upsert_model_prediction, "prediction_id")
                st.success(t("upload_done").format(ok=ok, bad=bad))
                st.cache_data.clear()

            model_run_ids = [x.get("model_run_id") for x in mr]
            run_ids = [x.get("run_id") for x in admin.get("runs2", [])]
            with st.form(key=k("mp_form")):
                pid = st.text_input(t("prediction_id"), value=f"PRED-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}", key=k("pred_id"))
                mid = st.selectbox(t("model_run_id"), model_run_ids or [""], key=k("pred_mid"))
                rid = st.selectbox(t("run_id"), run_ids or [""], key=k("pred_rid"))
                ypred = st.number_input(t("y_pred"), -1e9, 1e9, 0.0, 0.1, key=k("pred_yp"))
                ytrue = st.number_input(t("y_true"), -1e9, 1e9, 0.0, 0.1, key=k("pred_yt"))
                if st.form_submit_button(t("save_upsert")):
                    upsert_model_prediction({
                        "prediction_id": pid,
                        "model_run_id": mid,
                        "run_id": rid,
                        "y_pred": float(ypred),
                        "y_true": float(ytrue),
                        "created_at": datetime.utcnow().isoformat(),
                    })
                    st.success(t("refreshed"))
                    st.cache_data.clear()

            del_pid = st.selectbox(t("delete_model_prediction"), [x.get("prediction_id") for x in mp] or [""], key=k("del_pred"))
            if st.button(t("delete_selected"), key=k("del_pred_btn")):
                if del_pid:
                    delete_model_prediction(del_pid)
                    st.success(t("refreshed"))
                    st.cache_data.clear()

    # -------- Legacy Row5 Fit (unchanged) --------
    with tabs[9]:
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
            st.json({k2: latest.get(k2) for k2 in ["model_id", "ok", "n_used", "rmse_syneresis", "rmse_overall", "alpha", "gate_full"]})
        else:
            st.warning(t("no_runs"))
