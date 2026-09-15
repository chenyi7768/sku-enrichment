"""Generate messy building-supply sample SKU spreadsheet."""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "sample_data" / "building_supply_skus.xlsx"

# Intentionally messy headers + incomplete fields (realistic ERP export)
rows = [
    {"货号": "BF-PPR-25", "品名规格": "日丰PPR热水管 dn25*4.2 pn2.0 白色 4米", "分类": "", "品牌": "", "单位": "米", "备注": "热熔连接"},
    {"货号": "LS-PVC-110", "品名规格": "联塑PVC排水管 Φ110*3.2 灰色", "分类": "管材", "品牌": "", "单位": "", "备注": ""},
    {"货号": "WX-BALL-20", "品名规格": "伟星全铜球阀 DN20 内外丝", "分类": "", "品牌": "伟星", "单位": "个", "备注": "PN1.6"},
    {"货号": "QT-FLOOR-50", "品名规格": "潜水艇地漏 不锈钢 50mm 防臭", "分类": "", "品牌": "", "单位": "只", "备注": ""},
    {"货号": "DZ-M8-40", "品名规格": "镀锌膨胀螺栓 M8x40 碳钢", "分类": "", "品牌": "", "单位": "", "备注": "100个/盒"},
    {"货号": "ZC-BV-2.5", "品名规格": "正泰BV电线 2.5平方 单芯铜线 红色 100米", "分类": "", "品牌": "", "单位": "卷", "备注": "450/750V"},
    {"货号": "YH-JS-20", "品名规格": "东方雨虹 防水涂料 柔韧型 20kg", "分类": "涂料", "品牌": "", "单位": "桶", "备注": ""},
    {"货号": "DC-AG100", "品名规格": "东成角磨机 S1M-FF-100A 720W", "分类": "工具", "品牌": "东成", "单位": "台", "备注": "配切割片"},
    {"货号": "3M-4905", "品名规格": "3M VHB胶带 4905 透明 20mm*33m", "分类": "", "品牌": "3M", "单位": "卷", "备注": ""},
    {"货号": "SN-LED12", "品名规格": "欧普LED筒灯 12W 3000K 开孔75mm 白色", "分类": "", "品牌": "", "单位": "个", "备注": ""},
    {"货号": "GX-ELB-32", "品名规格": "正泰断路器 NBE7 C32 1P 32A", "分类": "电气", "品牌": "正泰", "单位": "个", "备注": ""},
    {"货号": "HG-FLANGE-50", "品名规格": "碳钢法兰 DN50 PN16 GB/T9119", "分类": "", "品牌": "", "单位": "片", "备注": "镀锌"},
]

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(OUT, index=False, engine="openpyxl")
print(f"Wrote {OUT} ({len(df)} rows)")
