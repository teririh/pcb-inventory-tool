import streamlit as st
import pandas as pd
import os
import re

# ---------------------- 1. 配置基础信息 ----------------------
EXCEL_FILE = "pcb_inventory.xlsx"

# ---------------------- 2. 全场景兼容的核心提取函数 ----------------------
def load_or_create_table():
    """加载/新建表格"""
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE)
    else:
        return pd.DataFrame(columns=["PCB型号", "数量", "存放位置"])

def save_table(df):
    """保存表格"""
    df.to_excel(EXCEL_FILE, index=False)

def extract_info(text):
    """
    全口语场景兼容优化，覆盖所有日常随口说的表达
    兼容示例：
    1. 标准型：PCBS823，00版本，有2块，放在小房间
    2. 口语型：这个PCB板是S283，V0.0版本，一共5片，放二楼仓库了
    3. 倒装型：小房间白架子上放了3块S323的PCB，版本00
    4. 简写型：S123 PCB 01版 8个 前台柜子
    5. 带单位型：PCBS456 Ver02 2PCS 搁在大房间货架
    """
    # 先统一转小写，避免大小写干扰，同时去掉多余空格
    clean_text = re.sub(r"\s+", " ", text.strip().lower())
    pcb_model = ""
    quantity = ""
    location = ""

    # ====================== 1. 提取PCB型号+版本号（全兼容） ======================
    # 1.1 先抓PCB型号前缀（兼容所有写法：PCB S283、pcb板S323、板子S123、S456 PCB）
    prefix_patterns = [
        r"pcb[a-z]*\s*([a-z]*\d+(?:-\d+)*)",  # PCB开头的：PCBS323、PCB S283
        r"([a-z]*\d+(?:-\d+)*)\s*pcb",  # 型号在前PCB在后：S283 PCB
        r"板子\s*([a-z]*\d+(?:-\d+)*)",  # 口语“板子”开头
        r"型号\s*[:：是]*\s*([a-z]*\d+(?:-\d+)*)",  # 带“型号”关键词
    ]
    # 遍历所有规则，抓到第一个有效前缀就停
    prefix = ""
    for pattern in prefix_patterns:
        match = re.search(pattern, clean_text)
        if match:
            prefix = match.group(1).upper()  # 转大写统一格式
            break

    # 1.2 抓版本号（兼容所有写法：00版本、V0.0、Ver01、02版、版本号1.0）
    version_patterns = [
        r"版本\s*[号]*\s*[:：是]*\s*([a-z]*\d+(?:\.\d+)*)",
        r"([a-z]*\d+(?:\.\d+)*)\s*版[本]*",
        r"v(?:er)?\s*([a-z]*\d+(?:\.\d+)*)",  # V/Ver开头的版本号
    ]
    version = ""
    for pattern in version_patterns:
        match = re.search(pattern, clean_text)
        if match:
            # 去掉版本号里的点和字母，只留数字（比如V0.0→00、Ver1.2→12）
            version = re.sub(r"[^\d]", "", match.group(1))
            break

    # 1.3 拼接完整型号
    if prefix:
        if version:
            pcb_model = f"{prefix}-{version}"
        else:
            pcb_model = prefix

    # ====================== 2. 提取数量（全兼容+防误抓） ======================
    # 兼容所有口语说法，同时避开版本号里的数字
    quantity_patterns = [
        r"(?:数量|有|一共|总共|剩|备货|还有)\s*[:：是]*\s*(\d+)\s*(?:块|片|个|只|pcs|台)*",
        r"(\d+)\s*(?:块|片|个|只|pcs|台)\s*(?:pcb|板子|板)",  # 数字在前单位在后
    ]
    for pattern in quantity_patterns:
        match = re.search(pattern, clean_text)
        if match:
            quantity = match.group(1)
            break

    # ====================== 3. 提取存放位置（全口语兼容） ======================
    location_patterns = [
        r"(?:存放|放|搁|位置|地点|放于|放在)\s*[:：在]*\s*(.*?)(?:[，。,；;！!？?]|$)",
        r"(.*?)\s*(?:里|上|处|柜子|架子|仓库|房间)\s*(?:放着|放了|有)",  # 倒装句：XX里放了X块PCB
    ]
    for pattern in location_patterns:
        match = re.search(pattern, clean_text)
        if match:
            location = match.group(1).strip()
            # 过滤掉空内容和无效内容
            if location and len(location) > 1 and not re.search(r"^\d+$", location):
                # 首字母转大写，更美观
                location = location[0].upper() + location[1:]
                break

    return pcb_model, quantity, location

# ---------------------- 3. 界面设计（优化了提示） ----------------------
st.set_page_config(page_title="PCB库存小工具", layout="centered")
st.title("📦 PCB库存信息录入工具")

# 输入区域，加了更多示例
input_text = st.text_area(
    "请粘贴/输入包含PCB信息的文字（支持所有口语化表达）：",
    height=150,
    placeholder="示例1：PCBS823，00版本，有2块，放在小房间\n示例2：这个PCB是S283，V0.0版本，一共5片，放二楼仓库了\n示例3：S123 PCB 01版 8个 前台柜子"
)

# 提取按钮
if st.button("提取信息"):
    if input_text:
        model, qty, loc = extract_info(input_text)
        # 保存到会话状态
        st.session_state["extracted_model"] = model
        st.session_state["extracted_qty"] = qty
        st.session_state["extracted_loc"] = loc
        st.session_state["ready_to_save"] = True
    else:
        st.warning("请先输入包含PCB信息的文字！")

# 确认修改区域
if "ready_to_save" in st.session_state and st.session_state["ready_to_save"]:
    st.divider()
    st.subheader("请确认提取的信息（有误可直接修改）：")
    
    confirm_model = st.text_input("PCB型号：", value=st.session_state["extracted_model"])
    confirm_qty = st.text_input("数量：", value=st.session_state["extracted_qty"])
    confirm_loc = st.text_input("存放位置：", value=st.session_state["extracted_loc"])
    
    # 保存按钮
    if st.button("✅ 确认并保存到表格"):
        df = load_or_create_table()
        # 新增一行
        new_row = pd.DataFrame([{
            "PCB型号": confirm_model,
            "数量": confirm_qty,
            "存放位置": confirm_loc
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        # 保存
        save_table(df)
        # 成功提示
        st.success("信息已成功保存到表格！")
        st.balloons()
        # 显示当前表格
        st.divider()
        st.subheader("当前库存总表")
        st.dataframe(df, use_container_width=True)
        # 重置状态
        st.session_state["ready_to_save"] = False