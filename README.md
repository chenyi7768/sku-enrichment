# SKU目录智能富化（MVP）

本地Web Demo：上传杂乱的建材/五金SKU表格（`.xlsx`/`.csv`），自动识别表头、清洗文本、推断缺失属性，并生成优化标题、SEO短描述与属性卖点，支持预览与下载富化CSV。

**✅ Product-QA 通过**：保留P0功能（>500行→HTTP 400、is_duplicate、NEEDS_REVIEW+审核原因、保留原始数字规格、不臆造米数）。

## 功能特性

- 🌐 **中文落地页**：价值主张、前后对比、定价展示
- 📤 **文件上传**：支持`.xlsx` / `.csv`，或一键「试用样例」
- 🔄 **真实富化流水线**：pandas + openpyxl，规则/模板驱动，无需LLM Key
- 📊 **预览与下载**：预览前50行，下载完整`enriched_skus.csv`
- 📦 **内置建材样例**：`sample_data/building_supply_skus.xlsx`（12行真实数据）

## P0保障

- ✅ **>500行 → HTTP 400**：单次最多支持500行，超出返回错误（不会静默截断）
- ✅ **is_duplicate**：自动检测批次内重复SKU
- ✅ **NEEDS_REVIEW + 审核原因**：标记需要人工审核的行及具体原因
- ✅ **数字规格保留**：优化标题保留源文本中的关键数字规格（平方/mm/kg/开孔/色温/DN等）
- ✅ **不臆造米数**：长度值仅在源文本明确出现"米"或"m"时提取，绝不凭空生成

## 快速开始

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/chenyi7768/sku-enrichment.git
cd sku-enrichment

# 2. 创建虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 生成样例数据（如果需要）
python generate_sample.py

# 4. 启动服务
uvicorn app:app --host 0.0.0.0 --port 8000
```

浏览器打开：<http://127.0.0.1:8000>

### 使用Docker本地运行

```bash
# 构建镜像
docker build -t sku-enrichment .

# 运行容器
docker run -p 8000:8000 sku-enrichment
```

浏览器打开：<http://127.0.0.1:8000>

## Railway部署

### 方式一：从GitHub仓库部署（推荐）

1. 登录 [Railway](https://railway.app/)
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择仓库：`chenyi7768/sku-enrichment`
4. Railway会自动检测`Dockerfile`并部署
5. 部署完成后，Railway会提供一个公开URL

### 方式二：使用Railway CLI

```bash
# 安装Railway CLI
npm i -g @railway/cli

# 登录
railway login

# 初始化项目（在仓库目录下）
railway init

# 部署
railway up
```

### 环境变量（可选）

Railway会自动设置`PORT`环境变量，应用会自动适配。无需其他环境变量配置。

## 项目结构

```
sku-enrichment/
├── app.py                     # FastAPI应用入口
├── enrichment/
│   ├── __init__.py
│   └── pipeline.py            # 核心富化逻辑（表头识别/属性提取/标题生成）
├── templates/
│   └── index.html             # 中文UI界面
├── static/
│   ├── app.js                 # 前端交互逻辑
│   └── style.css              # 样式表
├── sample_data/
│   └── building_supply_skus.xlsx  # 内置样例数据
├── generate_sample.py         # 样例数据生成脚本
├── requirements.txt           # Python依赖
├── Dockerfile                 # Docker镜像配置
├── railway.json              # Railway部署配置
├── .dockerignore
├── .gitignore
└── README.md
```

## API端点

- `GET /`：落地页
- `POST /api/enrich`：上传文件并富化（multipart/form-data）
- `POST /api/enrich-sample`：使用内置样例富化
- `GET /api/download/{token}`：下载富化后的CSV
- `GET /api/sample-file`：下载样例Excel文件
- `GET /health`：健康检查

## 使用说明

1. **打开页面**：访问应用首页
2. **选择方式**：
   - 点击「选择文件」上传自己的`.xlsx`或`.csv`表格
   - 或点击「试用样例」使用内置建材SKU数据
3. **查看结果**：
   - 查看识别字段映射
   - 预览前50行富化结果
4. **下载CSV**：点击「下载富化CSV」获取完整结果

## 输出字段说明

| 字段 | 说明 |
|------|------|
| SKU编码 | 原始SKU或自动生成 |
| 原始品名 | 源表格品名 |
| 原始规格 | 源表格规格 |
| 品牌 | 自动识别或推断的品牌 |
| 品类 | 推断的商品分类 |
| 计量单位 | 推断的单位（米/个/件/卷等） |
| 结构化属性 | 提取的关键规格（直径/压力/材质/尺寸等） |
| 优化标题 | SEO友好的商品标题 |
| SEO短描述 | 适合电商展示的描述文案 |
| 属性卖点 | 结构化卖点列表 |
| 完整度评分 | 数据完整度评分（0-100） |
| is_duplicate | 是否为重复SKU |
| NEEDS_REVIEW | 是否需要人工审核 |
| 审核原因 | 需要审核的具体原因 |

## 技术栈

- **后端**：FastAPI + Uvicorn
- **数据处理**：Pandas + OpenPyXL
- **前端**：原生JavaScript + 现代CSS
- **部署**：Docker + Railway

## 限制说明

- 单次上传最多**500行**（超出返回HTTP 400，不会静默截断）
- 结果暂存在内存（demo环境），重启服务后需重新上传
- 当前为规则/模板富化，输出已明显优于原始杂乱行
- 可扩展：接入LLM API可进一步提升文案质量与多语言支持

## 开发

```bash
# 开发模式（自动重载）
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 运行样例生成
python generate_sample.py

# 测试API
curl http://localhost:8000/health
```

## License

MIT

## 作者

Yi Chen

---

**下一步Railway部署操作**：

1. 登录Railway: <https://railway.app/>
2. New Project → Deploy from GitHub repo
3. 选择仓库：`chenyi7768/sku-enrichment`
4. 等待部署完成（Railway会自动分配公开URL）

**注意**：Railway会在首次部署时自动运行`generate_sample.py`生成样例数据，无需手动操作。
