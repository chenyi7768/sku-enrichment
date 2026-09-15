"""SKU Catalog Enrichment Pipeline — rule/template based, no LLM required."""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Header aliases (messy Chinese / English / mixed)
# ---------------------------------------------------------------------------
HEADER_ALIASES: dict[str, list[str]] = {
    "sku": [
        "sku", "sku编码", "sku_id", "skuid", "商品编码", "货号", "料号",
        "产品编码", "编码", "编号", "item", "item_id", "itemid", "product_id",
        "商品编号", "物料编码", "物料号",
    ],
    "name": [
        "name", "品名", "商品名称", "产品名称", "名称", "product_name",
        "product", "title", "商品名", "产品名", "描述", "商品描述",
        "产品描述", "物料名称", "品名规格",
    ],
    "category": [
        "category", "分类", "品类", "类目", "商品分类", "产品分类",
        "类别", "cate", "cat", "一级分类", "二级分类",
    ],
    "brand": [
        "brand", "品牌", "厂家", "厂商", "制造商", "品牌名", "make",
    ],
    "specs": [
        "specs", "spec", "规格", "规格型号", "型号", "参数", "技术参数",
        "规格参数", "尺寸", "size", "model", "型号规格",
    ],
    "unit": [
        "unit", "单位", "计量单位", "销售单位", "uom",
    ],
    "material": [
        "material", "材质", "材料", "质地",
    ],
    "color": [
        "color", "颜色", "色彩", "colour",
    ],
    "price": [
        "price", "价格", "单价", "售价", "成本", "cost",
    ],
}

# Building-supply category inference keywords
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "管材管件": ["管", "弯头", "三通", "四通", "接头", "法兰", "卡箍", "管箍", "异径", "PVC管", "PPR", "PE管"],
    "阀门": ["阀", "闸阀", "球阀", "蝶阀", "截止阀", "止回阀", "减压阀", "电磁阀"],
    "紧固件": ["螺丝", "螺栓", "螺母", "垫圈", "螺钉", "膨胀螺栓", "锚栓", "铆钉", "自攻"],
    "五金工具": ["扳手", "锤子", "钳子", "螺丝刀", "电钻", "手电钻", "角磨机", "卷尺", "水平仪"],
    "电线电缆": ["电线", "电缆", "导线", "BV线", "护套线", "铜线", "铝线", "线缆"],
    "涂料防水": ["涂料", "油漆", "防水", "腻子", "乳胶漆", "底漆", "面漆", "防腐漆"],
    "板材型材": ["板", "钢板", "铝板", "木板", "型钢", "角钢", "槽钢", "方管", "工字钢"],
    "密封胶粘": ["胶", "密封胶", "硅胶", "玻璃胶", "结构胶", "胶水", "胶带", "止水带"],
    "卫浴洁具": ["马桶", "龙头", "花洒", "面盆", "浴缸", "角阀", "地漏", "水箱"],
    "照明电气": ["灯", "开关", "插座", "断路器", "空开", "配电箱", "LED", "灯管", "筒灯"],
}

BRAND_HINTS = [
    "伟星", "日丰", "联塑", "中财", "公元", "皮尔萨", "金德", "潜水艇",
    "东成", "博世", "牧田", "得伟", "史丹利", "世达", "3M", "德力西",
    "正泰", "施耐德", "ABB", "西门子", "飞利浦", "欧普", "雷士", "立邦",
    "多乐士", "三棵树", "东方雨虹", "科顺", "伟巴斯特", "美巢",
]

UNIT_MAP = {
    "个": "个", "只": "只", "件": "件", "套": "套", "米": "米", "m": "米",
    "根": "根", "卷": "卷", "箱": "箱", "包": "包", "袋": "袋", "kg": "千克",
    "千克": "千克", "吨": "吨", "升": "升", "l": "升", "盒": "盒", "把": "把",
}

# Critical numeric / size tokens that must be preserved in titles when present in source.
# Order matters for finding; we de-dupe later.
_RAW_SIZE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"开孔\s*\d+(?:\.\d+)?\s*mm", re.I),
    re.compile(r"(?:DN|dn)\s*\d+(?:\.\d+)?"),
    re.compile(r"[Φφф]\s*\d+(?:\.\d+)?"),
    re.compile(r"(?:PN|pn)\s*\d+(?:\.\d+)?"),
    re.compile(r"\d+(?:\.\d+)?\s*平方"),
    re.compile(r"\d{3,4}\s*K\b"),
    re.compile(r"M\d+(?:[xX×*]\d+(?:\.\d+)?)?"),
    re.compile(
        r"\d+(?:\.\d+)?\s*(?:mm|MM)\s*[xX×*]\s*\d+(?:\.\d+)?\s*(?:m|米|mm|MM)?"
    ),
    re.compile(
        r"\d+(?:\.\d+)?\s*[xX×*]\s*\d+(?:\.\d+)?(?:\s*[xX×*]\s*\d+(?:\.\d+)?)?\s*(?:mm|MM|m|米)?"
    ),
    re.compile(r"\d+(?:\.\d+)?\s*(?:mm|MM)\b"),
    re.compile(r"\d+(?:\.\d+)?\s*(?:kg|KG|千克)\b"),
    re.compile(r"\d+(?:\.\d+)?\s*米"),
    # lowercase-m length only (avoid 3M / S1M brand/model codes)
    re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*m(?![A-Za-z])"),
    re.compile(r"\d+(?:\.\d+)?\s*[Ww](?![a-zA-Z])"),
    re.compile(r"(?<![A-Za-z0-9\-])\d+\s*[Aa]\b"),  # 32A, not -100A
    re.compile(r"\d+\s*[Vv](?![a-zA-Z])"),
]

_FEATURE_KEYWORDS = ["防臭", "热熔", "柔韧型", "单芯", "内外丝", "透明", "镀锌"]


def _norm_header(h: Any) -> str:
    if h is None or (isinstance(h, float) and pd.isna(h)):
        return ""
    s = str(h).strip().lower()
    s = re.sub(r"[\s_\-./\\]+", "", s)
    return s


def detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """Map canonical fields → actual column names in the dataframe."""
    mapping: dict[str, str | None] = {k: None for k in HEADER_ALIASES}
    used: set[str] = set()

    normalized = {_norm_header(c): c for c in df.columns}

    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            key = _norm_header(alias)
            if key in normalized and normalized[key] not in used:
                mapping[field] = normalized[key]
                used.add(normalized[key])
                break
        if mapping[field] is None:
            # fuzzy: alias contained in header or vice versa
            for nh, orig in normalized.items():
                if orig in used or not nh:
                    continue
                for alias in aliases:
                    a = _norm_header(alias)
                    if a and (a in nh or nh in a):
                        mapping[field] = orig
                        used.add(orig)
                        break
                if mapping[field]:
                    break
    return mapping


def parse_upload(content: bytes, filename: str) -> pd.DataFrame:
    """Parse .xlsx or .csv bytes into a DataFrame."""
    name = (filename or "").lower()
    bio = io.BytesIO(content)
    if name.endswith(".csv"):
        # try utf-8 then gbk
        try:
            df = pd.read_csv(bio, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            bio.seek(0)
            df = pd.read_csv(bio, dtype=str, keep_default_na=False, encoding="gbk")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(bio, dtype=str, engine="openpyxl")
        df = df.fillna("")
    else:
        # sniff
        bio.seek(0)
        try:
            df = pd.read_excel(bio, dtype=str, engine="openpyxl")
            df = df.fillna("")
        except Exception:
            bio.seek(0)
            try:
                df = pd.read_csv(bio, dtype=str, keep_default_na=False)
            except UnicodeDecodeError:
                bio.seek(0)
                df = pd.read_csv(bio, dtype=str, keep_default_na=False, encoding="gbk")
    # drop fully empty rows
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.astype(str).replace({"nan": "", "None": "", "NaT": ""})
    return df


def _clean_text(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("　", " ")
    # unify common punctuation
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("【", "[").replace("】", "]")
    return s.strip(" ,;，；|/")


def _normalize_dup_key(s: str) -> str:
    s = _clean_text(s).lower()
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def _infer_category(name: str, specs: str, existing: str) -> str:
    if existing and existing not in ("", "未知", "其他", "其它"):
        return existing
    blob = f"{name} {specs}"
    scores: dict[str, int] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw.lower() in blob.lower() or kw in blob)
        if score:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return existing or "建材五金"


def _infer_brand(name: str, specs: str, existing: str) -> str:
    if existing and existing.strip():
        return existing.strip()
    blob = f"{name} {specs}"
    for b in BRAND_HINTS:
        if b in blob:
            return b
    return ""


def _extract_raw_size_tokens(blob: str) -> list[str]:
    """Extract critical numeric/size tokens that clearly appear in source text."""
    found: list[str] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in occupied)

    for pat in _RAW_SIZE_PATTERNS:
        for m in pat.finditer(blob):
            if overlaps(m.start(), m.end()):
                continue
            tok = re.sub(r"\s+", "", m.group(0))
            # Normalize separators for display consistency but keep numbers exact
            tok = tok.replace("x", "×").replace("X", "×").replace("*", "×")
            if tok and tok not in found:
                found.append(tok)
                occupied.append((m.start(), m.end()))

    # Feature keywords (non-numeric but critical for title quality)
    for feat in _FEATURE_KEYWORDS:
        if feat in blob and feat not in found:
            found.append(feat)

    return found


def _extract_specs(name: str, specs: str) -> tuple[dict[str, str], list[str], list[str]]:
    """
    Pull structured attributes from free text.
    Returns (attrs, raw_size_tokens, uncertainty_notes).
    """
    blob = f"{name} {specs}"
    attrs: dict[str, str] = {}
    notes: list[str] = []

    raw_tokens = _extract_raw_size_tokens(blob)

    # diameter DN / Φ / φ
    m = re.search(r"(?:DN|dn)\s*(\d+(?:\.\d+)?)", blob)
    if m:
        attrs["公称直径"] = f"DN{m.group(1)}"
    else:
        m = re.search(r"[Φφф]\s*(\d+(?:\.\d+)?)", blob)
        if m:
            attrs["公称直径"] = f"DN{m.group(1)}"

    # Cross-section for wire (平方) — critical, do before generic dims
    m = re.search(r"(\d+(?:\.\d+)?)\s*平方", blob)
    if m:
        attrs["截面积"] = f"{m.group(1)}平方"

    # Weight
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|KG|千克)", blob)
    if m:
        attrs["重量"] = f"{m.group(1)}kg"

    # Cutout / 开孔
    m = re.search(r"开孔\s*(\d+(?:\.\d+)?)\s*mm", blob, re.I)
    if m:
        attrs["开孔"] = f"{m.group(1)}mm"

    # Color temperature
    m = re.search(r"(\d{3,4})\s*K\b", blob)
    if m:
        attrs["色温"] = f"{m.group(1)}K"

    # Standalone mm size (e.g. 50mm 防臭) when not already 开孔 / multi-dim with units
    has_mm_product = bool(re.search(
        r"\d+(?:\.\d+)?\s*mm\s*[xX×*]\s*\d+", blob, re.I
    ))
    if "开孔" not in attrs and not has_mm_product:
        m = re.search(r"(?<![A-Za-z\d.])(\d+(?:\.\d+)?)\s*mm\b", blob, re.I)
        if m:
            attrs.setdefault("尺寸", f"{m.group(1)}mm")

    # Multi-dimension: prefer tokens that include unit (20mm×33m) over bare numbers
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(mm|MM)?\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*(mm|MM|m|米)?",
        blob,
    )
    if m:
        a, u1, b, u2 = m.group(1), m.group(2) or "", m.group(3), m.group(4) or ""
        # Only treat as 尺寸 when at least one unit present OR looks like pipe wall (dn style already handled)
        if u1 or u2 or re.search(r"\d+\s*[xX×*]\s*\d+", blob):
            left = f"{a}{u1.lower()}" if u1 else a
            right = f"{b}{u2.lower() if u2 and u2.lower() != '米' else (u2 or '')}"
            if u2 == "米":
                right = f"{b}米"
            dims = f"{left}×{right}"
            # Don't overwrite a clearer mm-only size with bare numbers lacking units
            if "尺寸" not in attrs or ("mm" in dims.lower() or "米" in dims or "m" in dims):
                # If existing is like 50mm and new is wire/tape dim, keep both via 规格尺寸
                if "尺寸" in attrs and attrs["尺寸"] != dims and "mm" in attrs["尺寸"]:
                    attrs["规格尺寸"] = dims
                else:
                    attrs["尺寸"] = dims

    # Third dimension optional already partially covered; also catch a×b×c
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)",
        blob,
    )
    if m and "规格尺寸" not in attrs:
        dims = "×".join(m.groups())
        if "mm" in blob.lower() or "毫米" in blob:
            dims += "mm"
        attrs.setdefault("尺寸", dims)

    # pressure rating
    m = re.search(r"(?:PN|pn)\s*(\d+(?:\.\d+)?)", blob)
    if m:
        attrs["压力等级"] = f"PN{m.group(1)}"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Mm][Pp][Aa]", blob)
    if m:
        attrs["压力"] = f"{m.group(1)}MPa"

    # voltage / current / power
    m = re.search(r"(\d+)\s*[Vv](?![a-zA-Z])", blob)
    if m:
        attrs["电压"] = f"{m.group(1)}V"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Ww](?![a-zA-Z])", blob)
    if m:
        attrs["功率"] = f"{m.group(1)}W"
    # Current (32A): require separator before number; ignore model tails like -100A / FF100A
    m = re.search(r"(?<![A-Za-z0-9\-])(\d+)\s*[Aa]\b", blob)
    if m:
        attrs["电流"] = f"{m.group(1)}A"

    # Length — ONLY when clearly meters in source. Never match brand 3M or model S1M.
    # 1) Chinese 米
    m = re.search(r"(\d+(?:\.\d+)?)\s*米", blob)
    if m:
        attrs["长度"] = f"{m.group(1)}米"
    else:
        # 2) lowercase m as unit, not part of identifier (3M, S1M-FF)
        m = re.search(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*m(?![A-Za-z])", blob)
        if m:
            # Avoid treating the second part of "20mm×33m" width×length as sole length
            # when we already captured full dim token — still OK to set 长度 for the m part
            attrs["长度"] = f"{m.group(1)}米"

    # material
    materials = ["不锈钢", "碳钢", "铸铁", "铜", "黄铜", "PVC", "PPR", "PE", "ABS", "铝合金", "镀锌", "球墨铸铁"]
    for mat in materials:
        if mat.lower() in blob.lower() or mat in blob:
            attrs["材质"] = mat
            break

    # thread
    m = re.search(r"(G\s*\d+(?:/\d+)?|NPT\s*\d+(?:/\d+)?|M\d+(?:[xX×]\d+(?:\.\d+)?)?)", blob, re.I)
    if m:
        attrs["螺纹"] = m.group(1).replace(" ", "")

    # color
    colors = ["白色", "黑色", "灰色", "红色", "蓝色", "绿色", "黄色", "银色", "透明"]
    for c in colors:
        if c in blob:
            attrs["颜色"] = c
            break

    # features
    if "防臭" in blob:
        attrs["特性"] = "防臭"
    elif "柔韧型" in blob:
        attrs["特性"] = "柔韧型"
    elif "单芯" in blob:
        attrs["特性"] = "单芯"

    # grade / standard
    m = re.search(r"(GB/?T?\s*[\d.\-]+|ISO\s*[\d.\-]+|HG/?T?\s*[\d.\-]+)", blob, re.I)
    if m:
        attrs["执行标准"] = m.group(1).replace(" ", "")

    # Uncertainty: source has digits that look like specs but we extracted nothing useful
    if re.search(r"\d", blob) and not attrs:
        notes.append("含数字规格但未能完整解析")
    elif re.search(r"\d", blob) and len(attrs) < 2 and not any(
        k in attrs for k in ("截面积", "重量", "开孔", "色温", "公称直径", "尺寸", "功率")
    ):
        notes.append("关键规格解析不完整")

    return attrs, raw_tokens, notes


def _infer_unit(name: str, specs: str, existing: str) -> str:
    if existing and existing.strip():
        e = existing.strip()
        return UNIT_MAP.get(e.lower(), e)
    blob = f"{name} {specs}".lower()
    if any(k in blob for k in ["管", "线", "电缆", "胶带"]):
        if "卷" in blob:
            return "卷"
        return "米"
    if any(k in blob for k in ["阀", "弯头", "三通", "接头", "法兰"]):
        return "个"
    if any(k in blob for k in ["螺丝", "螺栓", "螺母", "垫圈"]):
        return "个"
    if any(k in blob for k in ["涂料", "油漆", "胶"]):
        return "桶" if "kg" in blob or "千克" in blob else "支"
    return "件"


def _short_product_name(name: str, brand: str) -> str:
    """Keep a concise product noun phrase; drop trailing raw spec tokens."""
    core = name
    if brand and brand in core:
        core = core.replace(brand, "", 1).strip(" -_/|")
    core = _clean_text(core)
    # Cut at first tech-spec token so title can re-attach structured attrs
    m = re.search(
        r"(?:^|\s)((?:DN|dn|PN|pn|Φ|φ|ф)\s*\d|"
        r"\d+(?:\.\d+)?\s*[xX×*]|"
        r"\d+(?:\.\d+)?\s*(?:mm|MM|米|kg|KG|W\b|V\b|平方|K\b)|"
        r"开孔|"
        r"M\d+[xX×]|内外丝)",
        core,
    )
    if m and m.start() > 0:
        core = core[: m.start()].strip()
    # Also cut model-like tokens (S1M-FF-100A) after product noun when followed by power
    m2 = re.search(r"\s+[A-Z0-9][A-Z0-9\-/.]{3,}\s+\d+\s*[Ww]\b", core)
    if m2:
        # keep model in core — useful for tools; don't strip
        pass
    core = re.sub(r"\s*(白色|黑色|灰色|红色|蓝色|绿色|黄色|银色|透明)\s*$", "", core)
    core = re.sub(r"\s{2,}", " ", core).strip(" -_/|")
    return core


def _token_in_text(token: str, text: str) -> bool:
    """Loose containment check so DN25 matches dn25 etc."""
    if not token:
        return True
    t = re.sub(r"\s+", "", token).lower().replace("×", "x").replace("*", "x")
    s = re.sub(r"\s+", "", text).lower().replace("×", "x").replace("*", "x")
    if t in s:
        return True
    # numeric core match e.g. 2.5平方 vs already present
    nums = re.findall(r"\d+(?:\.\d+)?", token)
    if nums and all(n in s for n in nums) and any(
        u in s for u in ("mm", "平方", "kg", "米", "dn", "pn", "k", "w")
        if u in t
    ):
        return True
    return False


def _generate_title(
    brand: str,
    name: str,
    category: str,
    attrs: dict[str, str],
    specs: str,
    raw_tokens: list[str],
) -> str:
    """SEO-friendly product title: 品牌 + 核心品名 + 关键规格(from source) + 品类."""
    parts: list[str] = []
    if brand:
        parts.append(brand)

    core = _short_product_name(name, brand)
    if not core:
        core = category or "建材产品"
    parts.append(core)

    source_blob = f"{name} {specs}"
    title_so_far = " ".join(parts)

    # Prefer raw size tokens that clearly appear in source (never invent)
    spec_bits: list[str] = []
    for tok in raw_tokens:
        if _token_in_text(tok, title_so_far + " " + " ".join(spec_bits)):
            continue
        # Skip pure feature words temporarily; add after numeric specs
        if tok in _FEATURE_KEYWORDS:
            continue
        spec_bits.append(tok)

    # Structured attrs that are still missing from title
    key_order = [
        "公称直径", "截面积", "开孔", "色温", "尺寸", "规格尺寸",
        "重量", "压力等级", "压力", "功率", "电压", "电流",
        "材质", "颜色", "长度", "特性", "螺纹",
    ]
    for k in key_order:
        if k not in attrs:
            continue
        v = attrs[k]
        if _token_in_text(v, title_so_far + " " + " ".join(spec_bits)):
            continue
        # Safety: never add 长度 unless the exact meter value appears in source
        if k == "长度":
            num = re.search(r"(\d+(?:\.\d+)?)", v)
            if not num:
                continue
            n = num.group(1)
            if not (
                re.search(rf"{re.escape(n)}\s*米", source_blob)
                or re.search(rf"(?<![A-Za-z]){re.escape(n)}\s*m(?![A-Za-z])", source_blob)
            ):
                continue
            # Skip redundant 33米 when title already has 20mm×33m / 33m token
            joined = title_so_far + " " + " ".join(spec_bits)
            if re.search(rf"{re.escape(n)}\s*m", joined, re.I) or re.search(
                rf"{re.escape(n)}\s*米", joined
            ):
                continue
        spec_bits.append(v)

    # Features last
    for tok in raw_tokens:
        if tok in _FEATURE_KEYWORDS and not _token_in_text(tok, title_so_far + " " + " ".join(spec_bits)):
            spec_bits.append(tok)

    if not spec_bits and specs:
        short = re.split(r"[,，;/|]", specs)[0].strip()
        if short and short not in core and len(short) < 40:
            spec_bits.append(short)

    if spec_bits:
        parts.append(" ".join(spec_bits[:6]))

    if category and category not in "".join(parts):
        parts.append(category)

    title = " ".join(p for p in parts if p)
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def _generate_seo_desc(title: str, brand: str, category: str, attrs: dict[str, str], name: str) -> str:
    brand_bit = f"{brand}品牌" if brand else "精选"
    cat = category or "建材五金"
    attr_bits = "、".join(f"{k}{v}" for k, v in list(attrs.items())[:4])
    if attr_bits:
        return (
            f"{brand_bit}{cat}产品「{name}」，规格齐全（{attr_bits}），"
            f"适用于建筑工程、装修施工及工业配套。品质可靠，规格标准，支持批量采购。"
        )
    return (
        f"{brand_bit}{cat}产品「{name}」，规格标准、品质可靠，"
        f"适用于建筑工程、装修施工及工业配套场景，欢迎询价采购。"
    )


def _generate_bullets(attrs: dict[str, str], brand: str, category: str, unit: str, name: str) -> str:
    bullets: list[str] = []
    if brand:
        bullets.append(f"品牌：{brand}")
    if category:
        bullets.append(f"品类：{category}")
    for k, v in attrs.items():
        bullets.append(f"{k}：{v}")
    if unit:
        bullets.append(f"计量单位：{unit}")
    if not bullets:
        bullets.append(f"品名：{name}")
        bullets.append("规格：详见型号参数")
    # ensure 3–6 bullets
    while len(bullets) < 3:
        extras = ["适用场景：建筑工程 / 装修施工", "包装：标准工业包装", "质保：按厂家标准质保"]
        for e in extras:
            if e not in bullets:
                bullets.append(e)
            if len(bullets) >= 3:
                break
    return " | ".join(bullets[:6])


def _row_get(row: pd.Series, col: str | None) -> str:
    if not col or col not in row.index:
        return ""
    return _clean_text(str(row.get(col, "") or ""))


def _review_flags(
    brand: str,
    attrs: dict[str, str],
    notes: list[str],
    score: int,
    name: str,
    sku_from_source: bool,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if not brand:
        reasons.append("品牌待补充")
    if not attrs:
        reasons.append("结构化属性不足")
    if notes:
        reasons.extend(notes)
    if score < 60:
        reasons.append("完整度偏低")
    if not sku_from_source:
        reasons.append("SKU编码缺失已自动生成")
    # Very short / opaque name
    if name and len(name) < 4:
        reasons.append("品名过短")
    needs = bool(reasons)
    return needs, "；".join(reasons) if reasons else ""


def enrich_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Run enrichment on a raw SKU dataframe.
    Returns (enriched_df, meta) where meta has column mapping and stats.
    """
    mapping = detect_columns(df)
    rows_out: list[dict[str, Any]] = []
    dup_keys: list[str] = []

    for idx, row in df.iterrows():
        sku_raw = _row_get(row, mapping["sku"])
        sku_from_source = bool(sku_raw)
        sku = sku_raw or f"SKU-{int(idx) + 1:04d}"
        name = _row_get(row, mapping["name"])
        category_raw = _row_get(row, mapping["category"])
        brand_raw = _row_get(row, mapping["brand"])
        specs_raw = _row_get(row, mapping["specs"])
        unit_raw = _row_get(row, mapping["unit"])
        material_raw = _row_get(row, mapping["material"])
        color_raw = _row_get(row, mapping["color"])

        # If no name column, try to invent from first non-empty text-ish columns
        if not name:
            for c in df.columns:
                v = _clean_text(str(row.get(c, "") or ""))
                if v and c != mapping.get("sku") and not re.fullmatch(r"[\d.\-]+", v):
                    name = v
                    break
            if not name:
                name = sku

        # Duplicate key: SKU if present, else normalized name
        if sku_from_source:
            dup_keys.append(_normalize_dup_key(sku_raw))
        else:
            dup_keys.append(_normalize_dup_key(name))

        # Merge material/color into specs for extraction
        extra = " ".join(x for x in [material_raw, color_raw, specs_raw] if x)
        attrs, raw_tokens, notes = _extract_specs(name, extra)
        if material_raw and "材质" not in attrs:
            attrs["材质"] = material_raw
        if color_raw and "颜色" not in attrs:
            attrs["颜色"] = color_raw

        category = _infer_category(name, extra, category_raw)
        brand = _infer_brand(name, extra, brand_raw)
        unit = _infer_unit(name, extra, unit_raw)

        title = _generate_title(brand, name, category, attrs, specs_raw, raw_tokens)
        seo = _generate_seo_desc(title, brand, category, attrs, name)
        bullets = _generate_bullets(attrs, brand, category, unit, name)

        # cleanliness score (simple)
        filled = sum(1 for x in [sku_raw, name, category, brand, unit, specs_raw or attrs] if x)
        score = min(100, 40 + filled * 10 + len(attrs) * 5)

        brand_out = brand or "（待补充）"
        attrs_out = "；".join(f"{k}={v}" for k, v in attrs.items()) if attrs else "（待补充）"

        needs_review, review_reason = _review_flags(
            brand, attrs, notes, score, name, sku_from_source
        )
        if brand_out == "（待补充）" and "品牌待补充" not in review_reason:
            needs_review = True
            review_reason = ("品牌待补充；" + review_reason).strip("；")
        if attrs_out == "（待补充）":
            needs_review = True
            if "结构化属性不足" not in review_reason:
                review_reason = (review_reason + "；结构化属性不足").strip("；")

        rows_out.append({
            "SKU编码": sku,
            "原始品名": name,
            "原始规格": specs_raw,
            "品牌": brand_out,
            "品类": category,
            "计量单位": unit,
            "结构化属性": attrs_out,
            "优化标题": title,
            "SEO短描述": seo,
            "属性卖点": bullets,
            "完整度评分": score,
            "is_duplicate": False,  # filled below
            "NEEDS_REVIEW": needs_review,
            "审核原因": review_reason,
        })

    # Mark duplicates within batch
    from collections import Counter
    counts = Counter(dup_keys)
    for i, key in enumerate(dup_keys):
        rows_out[i]["is_duplicate"] = bool(key) and counts[key] > 1

    out = pd.DataFrame(rows_out)
    meta = {
        "column_mapping": {k: v for k, v in mapping.items() if v},
        "input_rows": len(df),
        "output_rows": len(out),
        "input_columns": list(df.columns.astype(str)),
        "needs_review_count": int(out["NEEDS_REVIEW"].sum()) if len(out) else 0,
        "duplicate_count": int(out["is_duplicate"].sum()) if len(out) else 0,
    }
    return out, meta
