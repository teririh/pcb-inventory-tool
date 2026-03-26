import streamlit as st
import pandas as pd
import os
import re
import streamlit.components.v1 as components

# ==================== 配置文件路径 ====================
INVENTORY_FILE = "pcb_inventory.xlsx"
BOM_FILE = "bom_data.xlsx"

# ==================== 辅助函数：中文数字转阿拉伯数字 ====================
def cn_num_to_arabic(cn_num):
    cn_num_map = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"两":2}
    for k,v in cn_num_map.items():
        cn_num = cn_num.replace(k, str(v))
    return re.sub(r"\D", "", cn_num)

# ==================== 数据层：表格加载与保存 ====================
def init_files():
    if not os.path.exists(INVENTORY_FILE):
        pd.DataFrame(columns=["PCB型号", "版本", "数量", "存放位置"]).to_excel(INVENTORY_FILE, index=False)
    if not os.path.exists(BOM_FILE):
        pd.DataFrame(columns=["PCB型号", "器件型号", "器件描述"]).to_excel(BOM_FILE, index=False)

def load_inventory():
    init_files()
    return pd.read_excel(INVENTORY_FILE)

def save_inventory(df):
    df.to_excel(INVENTORY_FILE, index=False)

def load_bom():
    init_files()
    return pd.read_excel(BOM_FILE)

def save_bom(df):
    df.to_excel(BOM_FILE, index=False)

# ==================== 逻辑层：全场景口语提取规则 ====================
def super_extract_info(text):
    clean_text = re.sub(r"\s+", " ", text.strip())
    clean_text_lower = clean_text.lower()
    
    pcb_model = ""  # 纯型号（如S876）
    version = ""    # 独立版本（如00）
    quantity = ""
    location = ""

    # --- 1. 优先提取倒装句的位置 ---
    reverse_loc_match = re.search(r"放在(.*?)的(?:板子|pcb|板卡)", clean_text_lower)
    if reverse_loc_match:
        location = reverse_loc_match.group(1).strip()

       # --- 2. 提取PCB型号（修复：支持纯型号+版本分离） ---
    model_patterns = [
        r"\d+\s*(?:块|片|个|只|pcs|张)[：\s]*([a-z]*\d+(?:-\d+)*)", 
        r"pcb[a-z]*[-_\s]*([a-z]*\d+(?:-\d+)*)",
        r"(?:板子|板卡|单板|线路板)[是：:\s]*([a-z]*\d+(?:-\d+)*)",
        r"(?:板子|pcb|板卡)[\s]*([a-z]*\d+(?:-\d+)*)$",
        r"型号[：:\s是]*([a-z]*\d+(?:-\d+)*)",
        r"([a-z]*\d+(?:-\d+)*)[\s]*pcb",
        r"^([a-z]*\d+(?:-\d+)*)[，。,\s]",
    ]
    
    prefix = ""
    for pat in model_patterns:
        m = re.search(pat, clean_text_lower)
        if m:
            prefix = m.group(1).upper()
            break

    # 版本号拼接（保持不变）
    ver_patterns = [
        r"(?:版本|版)[本号]*[：:\s]*([a-z]*\d+(?:\.\d+)*)",
        r"([a-z]*\d+(?:\.\d+)*)[：:\s]*(?:版本|版)",
        r"v(?:er)?[：:\s]*([a-z]*\d+(?:\.\d+)*)",
    ]
    
    version = ""
    for pat in ver_patterns:
        m = re.search(pat, clean_text_lower)
        if m:
            version = re.sub(r"[^\d]", "", m.group(1))
            break

    if prefix:
        pcb_model = prefix
        # 【新增】如果型号里已经包含横杠，强制拆分出版本
        if "-" in pcb_model:
            parts = pcb_model.split("-")
            # 取最后一部分作为版本（如果是数字的话）
            if parts[-1].isdigit():
                version = parts[-1]
                pcb_model = "-".join(parts[:-1])  # 前面的部分作为纯型号

    # 版本号拼接（保持不变）
    ver_patterns = [

    # --- 3. 提取数量（新增：支持简单的“数字+单位”结构） ---
    qty_patterns = [
        r"(?:有|一共|总共|还有|剩|数量)[：:\s]*([一二三四五六七八九十两\d]+)\s*(?:块|片|个|只|pcs|张)",
        r"([一二三四五六七八九十两\d]+)\s*(?:块|片|个|只|pcs|张)\s*(?:板子|pcb|板卡)",
        r"(\d+)\s*(?:块|片|个|只|pcs|张)",  # 新增：直接匹配“2块”这种简单结构
    ]
    for pat in qty_patterns:
        m = re.search(pat, clean_text_lower)
        if m:
            raw_qty = m.group(1)
            quantity = cn_num_to_arabic(raw_qty)
            # 确保只保留纯数字
            quantity = re.sub(r"\D", "", quantity)
            break

    # --- 4. 补充提取常规句的位置 ---
    if not location:
        loc_patterns = [
            r"(?:存放|放|搁|存|放置)[：:\s在]*(.*?)(?:[，。,；;\n]|$)",
            r"(?:位置|地点|地方)[：:\s是在]*(.*?)(?:[，。,；;\n]|$)",
            r"在[：:\s]*(.*?)(?:[，。,；;\n]|$)",
            r"^(.*?)\s*(?:有|放着|放了|现存)\s*\d+",
        ]
        for pat in loc_patterns:
            m = re.search(pat, clean_text)
            if m:
                loc_raw = m.group(1).strip()
                if len(loc_raw) >= 2 and not loc_raw.isdigit() and "版本" not in loc_raw and "pcb" not in loc_raw.lower():
                    location = loc_raw
                    break

    return pcb_model, version, quantity, location  # 新增版本返回值

# ==================== 界面层 ====================
st.set_page_config(page_title="PCB智能库存管理系统", layout="wide")
st.title("PCB 板我司智能库存")

# 初始化
init_files()

# 标签页布局
tab1, tab5, tab2, tab3, tab4 = st.tabs(["📝 信息录入", "🗑️ 智能删除", "🔍 库存查询", "📋 BOM管理", "📊 数据总览"])

# -------------------- 标签页 1：信息录入（新增快捷按钮） --------------------
with tab1:
    st.header("智能录入")
    
    col_in1, col_in2 = st.columns([2, 1])
    
    with col_in1:
        # 快捷按钮行
        btn_col1, btn_col2, btn_col3 = st.columns([1,1,2])
        with btn_col1:
            if st.button("粘贴剪切板"):
                # 用JS组件读取剪切板
                paste_js = """
                <script>
                async function pasteFromClipboard() {
                    try {
                        const text = await navigator.clipboard.readText();
                        window.parent.postMessage({type: 'streamlit:setComponentValue', value: text}, '*');
                    } catch (err) {
                        alert('请先在浏览器中允许访问剪切板');
                    }
                }
                pasteFromClipboard();
                </script>
                """
                components.html(paste_js, height=0)
                st.info("请先复制文字，然后刷新页面再点此按钮（浏览器安全限制）")
        
        with btn_col2:
            if st.button("🗑️ 一键清空"):
                if 'input_text' in st.session_state:
                    st.session_state['input_text'] = ""
                st.rerun()
        
        # 输入框（绑定session_state）
        if 'input_text' not in st.session_state:
            st.session_state['input_text'] = ""
        
        input_text = st.text_area(
            "粘贴文字（支持任何语序）：",
            height=180,
            value=st.session_state['input_text'],
            placeholder="示例1：有一块板子是PCB-S324，存放在8楼测试部\n示例2：有一块放在小房间的板子S876",
            key='input_text'
        )
        
        if st.button("开始智能提取", type="primary"):
            if input_text:
                m, v, q, l = super_extract_info(input_text)  # 接收4个返回值
                st.session_state['new_model'] = m
                st.session_state['new_version'] = v  # 新增版本状态
                st.session_state['new_qty'] = q
                st.session_state['new_loc'] = l
                st.success("提取完成！请在右侧确认")
            else:
                st.warning("请输入内容")

    with col_in2:
        st.subheader("确认信息")
        if 'new_model' not in st.session_state:
            st.info("请先在左侧点击提取")
        else:
            fm = st.text_input("PCB型号", value=st.session_state['new_model'])
            fv = st.text_input("版本", value=st.session_state.get('new_version', ''))  # 新增版本输入框
            fq = st.text_input("数量", value=st.session_state['new_qty'])
            fl = st.text_input("存放位置", value=st.session_state['new_loc'])
            
            if st.button("✅ 保存入库"):
                df = load_inventory()
                new_row = pd.DataFrame([[fm, fv, fq, fl]], columns=df.columns)  # 按新列顺序保存
                df = pd.concat([df, new_row], ignore_index=True)
                save_inventory(df)
                st.success(f"已保存：{fm}")
                st.balloons()
                # 清空状态
                for k in ['new_model', 'new_version', 'new_qty', 'new_loc', 'input_text']:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

# -------------------- 标签页 2：库存查询 --------------------
with tab2:
    st.header("多维度查询")
    
    search_mode = st.radio("选择查询模式：", ["1. 按PCB型号/位置查询", "2. 按器件反查PCB（BOM关联）"], horizontal=True)
    
    if search_mode == "1. 按PCB型号/位置查询":
        keyword = st.text_input("输入关键词（PCB型号 或 存放位置）：", placeholder="例如：S876 或 5F")
        if st.button("🔍 搜索") and keyword:
            df = load_inventory()
            mask = df.astype(str).apply(lambda x: x.str.contains(keyword, case=False, na=False)).any(axis=1)
            result = df[mask]
            
            if len(result) > 0:
                st.success(f"找到 {len(result)} 条记录：")
                st.dataframe(result, use_container_width=True)
            else:
                st.warning("未找到相关记录")
    
    else:
        st.info("💡 提示：先在「BOM管理」页上传BOM表，才能使用此功能")
        device_keyword = st.text_input("输入器件型号：", placeholder="例如：电容0805 或 MCU-STM32")
        if st.button("反查PCB") and device_keyword:
            bom_df = load_bom()
            inv_df = load_inventory()
            
            bom_mask = bom_df.astype(str).apply(lambda x: x.str.contains(device_keyword, case=False, na=False)).any(axis=1)
            matched_pcbs = bom_df[bom_mask]['PCB型号'].unique().tolist()
            
            if matched_pcbs:
                st.success(f"器件【{device_keyword}】用于以下PCB：")
                st.write(f"PCB型号列表：{', '.join(matched_pcbs)}")
                
                st.divider()
                st.subheader("当前库存情况：")
                inv_mask = inv_df['PCB型号'].isin(matched_pcbs)
                stock_result = inv_df[inv_mask]
                if len(stock_result) > 0:
                    st.dataframe(stock_result, use_container_width=True)
                else:
                    st.warning("这些PCB目前暂无库存记录")
            else:
                st.warning("BOM表中未找到该器件，请先上传BOM")

# -------------------- 标签页 3：BOM管理 --------------------
with tab3:
    st.header("BOM表管理")
    
    st.info("📌 BOM表Excel格式要求：必须包含列名【PCB型号】、【器件型号】，可选【器件描述】")
    
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        st.subheader("上传/更新BOM")
        uploaded_file = st.file_uploader("选择Excel文件 (.xlsx)", type=['xlsx'])
        if uploaded_file and st.button("📤 导入BOM"):
            try:
                new_bom = pd.read_excel(uploaded_file)
                if 'PCB型号' in new_bom.columns and '器件型号' in new_bom.columns:
                    save_bom(new_bom)
                    st.success(f"BOM导入成功！共 {len(new_bom)} 条记录")
                    st.dataframe(new_bom.head(), use_container_width=True)
                else:
                    st.error("Excel列名不对，请检查是否有【PCB型号】和【器件型号】")
            except Exception as e:
                st.error(f"导入失败：{e}")
    
    with col_b2:
        st.subheader("当前BOM预览")
        if st.button("📋 查看现有BOM"):
            df = load_bom()
            if len(df) > 0:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("BOM表为空，请先上传")

# -------------------- 标签页 4：数据总览 --------------------
with tab4:
    st.header("库存全景")
    
    df_inv = load_inventory()
    df_bom = load_bom()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("PCB种类数", df_inv['PCB型号'].nunique())
    c2.metric("库存记录数", len(df_inv))
    c3.metric("BOM关联数", len(df_bom))
    
    st.divider()
    st.subheader("完整库存表")
    st.dataframe(df_inv, use_container_width=True)

# -------------------- 新增标签页 5：智能删除 --------------------
with tab5:
    st.header("智能删除（支持口语化输入搜索）")
    
    # 1. 输入区域（复用智能提取）
    del_input = st.text_input(
        "输入要删除的PCB信息（支持型号/位置/口语）：",
        placeholder="例如：PCB-S876 或 5F 或 有一块S876在小房间"
    )
    
        # 2. 搜索按钮（修复：支持直接输入纯型号搜索）
    if st.button("🔍 搜索要删除的记录"):
        if del_input:
            # 复用智能提取函数
            m, q, l = super_extract_info(del_input)
            
            # 构建搜索关键词
            keywords = [k for k in [m, l] if k]
            
            # 【新增兜底】如果没识别到关键词，直接把输入内容当关键词
            if not keywords:
                keywords = [del_input.strip()]
            
            df = load_inventory()
            # 模糊搜索
            mask = df.astype(str).apply(
                lambda x: x.str.contains('|'.join(keywords), case=False, na=False)
            ).any(axis=1)
            result = df[mask].copy()
            
            if len(result) > 0:
                st.success(f"找到 {len(result)} 条匹配记录，请在下方选择删除：")
                st.session_state['del_result'] = result
                st.session_state['show_del'] = True
            else:
                st.warning("未找到匹配记录")
                st.session_state['show_del'] = False
        else:
            st.warning("请输入内容")
    
    # 3. 显示搜索结果并提供删除
    if 'show_del' in st.session_state and st.session_state['show_del']:
        st.divider()
        st.subheader("搜索结果（点击右侧按钮删除该行）")
        
        df_to_show = st.session_state['del_result']
        
        # 用循环生成每行带删除按钮的表格
        for idx, row in df_to_show.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 2, 1])
            col1.write(f"**PCB型号**: {row['PCB型号']}")
            col2.write(f"**版本**: {row.get('版本', '')}")  # 显示版本
            col3.write(f"**数量**: {row['数量']}")
            col4.write(f"**位置**: {row['存放位置']}")
            
            # 删除按钮
            if col4.button("🗑️ 删除", key=f"del_{idx}"):
                # 从完整库存表里删除这一行
                full_df = load_inventory()
                # 找到匹配的行并删除（用索引差集）
                full_df = full_df.drop(full_df[(full_df['PCB型号'] == row['PCB型号']) & 
                                                (full_df.get('版本', '') == row.get('版本', '')) &  # 加版本匹配
                                                (full_df['数量'] == row['数量']) & 
                                                (full_df['存放位置'] == row['存放位置'])].index)
                save_inventory(full_df)
                st.success(f"已删除：{row['PCB型号']} ({row['存放位置']})")
                st.balloons()
                # 更新会话状态并刷新
                st.session_state['del_result'] = full_df[full_df['PCB型号'].isin(df_to_show['PCB型号'])]
                st.rerun()
        
        st.divider()
        st.info("💡 提示：删除后数据不可恢复，请谨慎操作")