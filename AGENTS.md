# AI助教系统 - AI Coding Agent Guide

> **项目**: AI助教系统 (AI Tutor System)  
> **语言**: Python 3.11+  
> **文档版本**: v1.1  
> **最后更新**: 2024年

---

## 1. 项目概述

AI助教系统是一个面向中学生（13-16岁）的AI驱动作业诊断平台。系统通过多模型仲裁、变形题生成和分层诊断，识别学习问题的**根本原因**（而非仅判对错）。

### 1.1 核心设计理念

| 原则 | 说明 |
|------|------|
| **诊断先于讲解** | 先定位认知断点，再推送解决方案 |
| **少即是多** | 考点描述≤3条，诊断选项≤3个，避免认知过载 |
| **数据驱动** | 1个月冷启动积累，形成个人认知画像 |
| **90秒闭环** | 从上传作业到诊断完成的完整流程控制在90秒内 |

### 1.2 90秒闭环诊断流程

```
作业照片上传 (0s)
    ↓
多模态识图 (Vision API) (5s)
    ↓
题目理解 + 答案提取 + 学科分类 (10s)
    ↓
3模型仲裁 (并行推理) (20s)
    ↓
考点识别(≤3条) + 错因初判
    ↓
即时变形题生成 (AI实时) (5s)
    ↓
验证:粗心?/方法错误?/概念漏洞? (30s)
    ↓
分层选择诊断 (2-3步) (15s)
    ↓
定位具体认知断点 → 动态知识图谱更新 → 推荐下一步行动 (5s)
```

### 1.3 三模型仲裁机制

| 模型 | 职责 | 权重 |
|------|------|------|
| **模型A** (GPT-4 / Kimi-for-coding) | 题目解构、考点分类 | 0.4 |
| **模型B** (DeepSeek-Math) | 逻辑推演、步骤验证 | 0.4 |
| **模型C** (Llama-3-70B / Gemini) | 概念映射、归因交叉验证 | 0.2 |

**仲裁逻辑**:
- **共识≥2/3**: 采用多数结果，置信度"高"
- **全部分歧**: 触发即时变形题测试，置信度"待验证"

---

## 2. 技术栈

| 层级 | 技术选型 | 版本要求 |
|------|----------|----------|
| **后端框架** | FastAPI | >=0.109.0 |
| **ASGI服务器** | Uvicorn | >=0.27.0 |
| **数据库** | SQLite + SQLAlchemy | >=2.0.0 |
| **数据库迁移** | Alembic | >=1.13.0 |
| **数据验证** | Pydantic + Pydantic-Settings | >=2.6.0 |
| **AI模型** | OpenAI, Kimi, Gemini, Anthropic, DeepSeek, Ollama | - |
| **OCR** | 百度OCR API, Gemini Vision | - |
| **图像处理** | Pillow, OpenCV, NumPy | - |
| **异步** | asyncio, aiohttp, aiosqlite | - |
| **日志** | structlog | >=24.1.0 |

---

## 3. 项目结构

```
savefool/
├── docs/                              # 技术文档（中文）
│   ├── AI助教系统-开发技术文档.md       # 主文档导航
│   ├── 01-系统架构设计.md              # 分层架构详细设计
│   ├── 02-功能模块设计.md              # 51个功能点（含追溯ID）
│   ├── 03-数据模型设计.md              # ER图、SQLite Schema
│   ├── 04-API接口设计.md               # OpenAPI 3.0规范（21个API）
│   ├── 05-测试策略设计.md              # 100+测试用例
│   ├── DEVELOPMENT_PLAN.md            # 开发计划（Phase规划）
│   └── *.xlsx                         # 追踪表（任务/用例/矩阵）
│
├── src/                               # 源代码
│   ├── __init__.py
│   ├── core/                          # 核心工具类
│   ├── presentation/                  # 表现层
│   │   ├── api/                       # FastAPI应用
│   │   │   ├── main.py               # 应用主入口
│   │   │   ├── schemas.py            # Pydantic模型
│   │   │   ├── exceptions.py         # 异常处理
│   │   │   ├── run.py                # 启动脚本
│   │   │   └── routes/               # API路由
│   │   │       ├── homework.py       # 作业管理
│   │   │       ├── diagnosis.py      # 诊断接口
│   │   │       ├── variant.py        # 变形题接口
│   │   │       └── statistics.py     # 统计接口
│   │   └── web/                       # Web界面（Jinja2模板）
│   │       ├── static/               # 静态资源
│   │       └── templates/            # HTML模板
│   │           ├── upload.html
│   │           ├── result.html
│   │           └── statistics.html
│   ├── application/                   # 应用层（服务编排）
│   ├── domain/                        # 领域层
│   │   ├── __init__.py
│   │   ├── engines/                   # 核心引擎
│   │   │   ├── diagnosis_engine.py    # 诊断流程引擎
│   │   │   ├── arbitration_engine.py  # 多模型仲裁引擎
│   │   │   ├── variant_generator.py   # 变形题生成引擎
│   │   │   ├── variant_validator.py   # 变形题验证
│   │   │   ├── ocr_engine.py         # OCR引擎
│   │   │   ├── image_preprocessor.py  # 图像预处理
│   │   │   ├── error_detection.py     # 错误检测
│   │   │   ├── error_attribution.py   # 错误归因
│   │   │   ├── layered_diagnosis.py   # 分层诊断
│   │   │   ├── result_fusion.py       # 结果融合
│   │   │   ├── model_schedulers.py    # 模型调度器
│   │   │   ├── parallel_coordinator.py # 并行协调器
│   │   │   ├── explanation_generator.py # 解释生成
│   │   │   ├── diagnosis_assembler.py # 诊断组装
│   │   │   └── variant_strategies/    # 变形策略
│   │   │       ├── base.py
│   │   │       ├── numeric_strategy.py
│   │   │       ├── inverse_strategy.py
│   │   │       └── context_strategy.py
│   │   ├── memory/                    # 记忆系统（OpenHarness风格）
│   │   │   ├── memory_manager.py      # 记忆管理器
│   │   │   ├── profile_memory.py      # Profile记忆（长期认知画像）
│   │   │   ├── episodic_memory.py     # Episodic记忆（作业事件流）
│   │   │   ├── semantic_memory.py     # Semantic记忆（结构化知识）
│   │   │   ├── meta_memory.py         # Meta记忆（元认知层）
│   │   │   └── crystallization/       # 结晶机制
│   │   │       ├── monitor.py
│   │   │       ├── conditions.py
│   │   │       ├── scheduler.py
│   │   │       ├── executor.py
│   │   │       ├── compaction.py
│   │   │       └── jobs.py
│   │   ├── models/                    # 领域模型
│   │   │   ├── base.py               # 基础模型类
│   │   │   ├── diagnosis.py          # 诊断相关模型
│   │   │   ├── variant.py            # 变形题模型
│   │   │   ├── memory.py             # 记忆模型
│   │   │   └── arbitration.py        # 仲裁模型
│   │   ├── services/                  # 领域服务
│   │   └── exceptions.py              # 领域异常
│   └── infrastructure/                # 基础设施层
│       ├── __init__.py
│       ├── config.py                  # 配置管理（Pydantic-Settings）
│       ├── logging.py                 # 日志配置（structlog）
│       ├── db/                        # ORM模型
│       │   ├── base.py               # SQLAlchemy基类
│       │   ├── student.py            # 学生表
│       │   ├── homework.py           # 作业表
│       │   ├── answer.py             # 答案表
│       │   ├── variant.py            # 变形题表
│       │   ├── knowledge.py          # 知识点表
│       │   ├── cognitive_gap.py      # 认知缺口表
│       │   ├── parent.py             # 家长描述表
│       │   └── enums.py              # 枚举定义
│       ├── models/                    # AI模型客户端
│       │   ├── base.py               # 模型基类
│       │   ├── openai_client.py      # OpenAI客户端
│       │   ├── gemini_client.py      # Gemini客户端
│       │   ├── kimi_client.py        # Kimi客户端
│       │   ├── anthropic_client.py   # Anthropic客户端
│       │   ├── deepseek_client.py    # DeepSeek客户端
│       │   ├── ollama_client.py      # Ollama客户端
│       │   ├── baidu_ocr_client.py   # 百度OCR客户端
│       │   ├── client_factory.py     # 客户端工厂
│       │   └── exceptions.py         # 模型异常
│       └── storage/                   # 存储适配
│           ├── database.py           # 数据库连接
│           ├── repositories.py       # 仓库模式实现
│           └── repository.py         # 仓库接口
│
├── tests/                             # 测试代码
│   ├── conftest.py                    # Pytest配置和Fixtures
│   ├── unit/                          # 单元测试（60%）
│   │   ├── test_*.py                  # 各模块单元测试
│   │   └── domain/                    # 领域层测试
│   ├── integration/                   # 集成测试（30%）
│   ├── e2e/                           # E2E测试（10%）
│   ├── test_domain/                   # 领域模型测试
│   ├── test_infrastructure/           # 基础设施测试
│   └── fixtures/                      # 测试数据
│       ├── problem_data.py
│       ├── variant_fixtures.py
│       └── memory_data.py
│
├── alembic/                           # 数据库迁移
│   ├── env.py                        # Alembic环境配置
│   ├── script.py.mako                # 迁移脚本模板
│   └── versions/                     # 迁移版本
│
├── scripts/                           # 运维脚本
│   ├── start.sh                      # 启动服务
│   ├── stop.sh                       # 停止服务
│   ├── restart.sh                    # 重启服务
│   ├── status.sh                     # 查看状态
│   └── logs.sh                       # 查看日志
│
├── data/                              # SQLite数据库文件
├── logs/                              # 日志文件
├── uploads/                           # 上传文件存储
├── htmlcov/                           # 测试覆盖率报告
├── requirements.txt                   # 生产依赖
├── requirements-dev.txt               # 开发依赖
├── pytest.ini                        # Pytest配置
├── alembic.ini                       # Alembic配置
├── .env.example                      # 环境变量示例
└── AGENTS.md                         # 本文件
```

---

## 4. 开发环境搭建

### 4.1 基础环境

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置API密钥

# 4. 初始化数据库
mkdir -p data logs uploads
alembic upgrade head

# 5. 运行测试
pytest --cov=src --cov-report=term-missing
```

### 4.2 启动服务

```bash
# 方式1: 使用脚本（推荐）
./scripts/start.sh

# 方式2: 直接启动
uvicorn src.presentation.api.main:app --reload --host 0.0.0.0 --port 8000

# 服务地址:
# - Web界面: http://localhost:8000/web/upload
# - API文档: http://localhost:8000/docs
# - 健康检查: http://localhost:8000/health
```

---

## 5. 测试策略

### 5.1 测试分层金字塔

```
                    ┌─────────┐
                    │ E2E测试  │  ← 关键用户旅程 (10%)
                    │  (UI)   │     自动化率: 80%
                    └────┬────┘
                         │
                   ┌─────┴─────┐
                   │  集成测试  │  ← API/数据流 (30%)
                   │(服务/组件)│     自动化率: 90%
                   └─────┬─────┘
                         │
               ┌─────────┴─────────┐
               │     单元测试       │  ← 业务逻辑 (60%)
               │ (函数/类/组件)     │     自动化率: 100%
               └───────────────────┘
```

### 5.2 测试命令

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/ -v --cov=src --cov-report=html

# 运行集成测试
pytest tests/integration/ -v

# 运行E2E测试
pytest tests/e2e/ -v

# 运行带覆盖率检查的测试（质量门禁）
pytest --cov=src --cov-report=term-missing --cov-fail-under=85

# 运行特定标记的测试
pytest -m unit        # 仅单元测试
pytest -m integration # 仅集成测试
pytest -m slow        # 慢测试
```

### 5.3 测试覆盖率目标

| 类型 | 目标 | 测量方式 |
|------|------|----------|
| 代码覆盖率 | ≥85% | pytest-cov |
| 功能覆盖率 | 核心功能100% | 功能-测试用例矩阵 |
| 场景覆盖率 | 正常100%，边界≥90% | 测试用例评审 |

---

## 6. 代码风格规范

### 6.1 基础规范

- **语言**: Python 3.11+
- **类型注解**: 强制使用 Type Hints
- **文档字符串**: 使用 Google Style Docstrings
- **代码格式化**: Black (line-length: 88)
- **导入排序**: isort
- **静态检查**: mypy + pylint

### 6.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/包 | 小写+下划线 | `diagnosis_engine.py` |
| 类 | 大驼峰 | `ArbitrationEngine` |
| 函数/方法 | 小写+下划线 | `calculate_confidence()` |
| 常量 | 大写+下划线 | `MAX_RETRY_COUNT = 3` |
| 私有成员 | 前缀下划线 | `_internal_method()` |

### 6.3 代码质量检查

```bash
# 代码格式化
black src/ tests/
isort src/ tests/

# 静态类型检查
mypy src/

# 代码风格检查
pylint src/
```

---

## 7. 功能追溯ID体系

所有功能、API、测试用例使用统一ID格式：

| 类型 | ID格式 | 示例 | 说明 |
|------|--------|------|------|
| 功能 | F-{模块}-{序号} | F-UPLOAD-001 | 功能模块设计 |
| API | API-{分组}-{序号} | API-HW-001 | API接口设计 |
| 测试用例 | TC-{模块}-{序号} | TC-UPLOAD-001 | 测试策略设计 |
| 开发任务 | TASK-{序号} | TASK-001 | 开发任务追踪 |

**追溯关系示例**:
```
F-UPLOAD-001 → API-HW-001 → TC-UPLOAD-001, TC-UPLOAD-006
F-ARBIT-004 → 内部调用 → TC-ARBITER-001,002,003
F-VAR-001 → API-VAR-001 → TC-VARIANT-001,005
```

---

## 8. 配置管理

### 8.1 环境变量

项目使用 `.env` 文件管理配置，通过 `pydantic-settings` 加载：

```bash
# 核心配置
DEBUG=false
ENV=development
SECRET_KEY=your-secret-key

# 数据库
DB_URL=sqlite:///./data/app.db

# AI模型提供商（推荐kimi，国内访问快）
active_model_provider=kimi

# Kimi配置（推荐）
KIMI_API_KEY=your_kimi_api_key
KIMI_MODEL=kimi-for-coding
KIMI_ENABLE_THINKING=false

# 其他模型...
OPENAI_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
DEEPSEEK_API_KEY=sk-xxx

# OCR
BAIDU_OCR_ENABLED=false
BAIDU_OCR_API_KEY=xxx
BAIDU_OCR_SECRET_KEY=xxx

# 诊断配置
DIAG_TIMEOUT_SECONDS=90
DIAG_CONFIDENCE_THRESHOLD=0.8
```

### 8.2 配置访问

```python
from src.infrastructure.config import get_settings

settings = get_settings()

# 访问配置
api_key = settings.kimi.api_key
model = settings.kimi.model
db_url = settings.database.url
```

---

## 9. 数据库

### 9.1 数据库类型

- **活跃数据**: SQLite (本地文件，路径: `./data/app.db`)
- **归档**: Markdown文件
- **向量存储**: Chroma/Pinecone (语义检索)

### 9.2 迁移命令

```bash
# 创建新迁移
alembic revision --autogenerate -m "描述"

# 升级到最新版本
alembic upgrade head

# 降级到指定版本
alembic downgrade <revision>

# 查看当前版本
alembic current

# 查看历史
alembic history
```

---

## 10. 记忆系统

系统采用OpenHarness风格的四层记忆架构：

```
student_memory/
├── profile/                    # Profile记忆（长期认知画像）
│   ├── cognitive_model.json    # 思维风格、错误DNA
│   └── zone_of_proximity.json  # 当前ZPD边界
├── episodic/                   # Episodic记忆（作业事件流）
│   ├── traces/                 # 解题决策路径
│   └── exercises/              # 原题与变形题lineage
├── semantic/                   # Semantic记忆（结构化知识）
│   ├── misconceptions/         # 已验证的概念误解
│   └── prerequisite_chains/    # 个人化知识依赖
└── meta/                       # Meta记忆（元认知层）
    ├── pending_gaps.json       # 待验证缺口（24小时观察期）
    └── crystallized/           # 已固化认知特征（≥30天）
```

**结晶机制**:
- **pending**: 初始状态，24小时观察期
- **crystallized**: 已固化（≥30天持续验证）
- **dismissed**: 已排除

---

## 11. API设计

### 11.1 基础信息

```yaml
Base URL: http://localhost:8000/api/v1
Protocol: HTTP (开发) / HTTPS (生产)
Content-Type: application/json
Timeout: 30s (默认) / 95s (诊断相关)
```

### 11.2 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

### 11.3 核心API

| API ID | 方法 | 路径 | 功能 |
|--------|------|------|------|
| API-HW-001 | POST | /api/v1/homework | 上传作业 |
| API-HW-002 | GET | /api/v1/homework/{id} | 获取作业详情 |
| API-DIA-001 | GET | /api/v1/diagnosis/options | 获取诊断选项 |
| API-DIA-002 | POST | /api/v1/diagnosis/select | 提交诊断选择 |
| API-VAR-001 | POST | /api/v1/variant/generate | 生成变形题 |
| API-STAT-001 | GET | /api/v1/statistics/weak-points | 薄弱点清单 |

---

## 12. Git提交规范

```
[Phase-X] 类型: 简短描述

详细描述...

测试: 测试通过情况
```

**类型**:
- `feat`: 新功能
- `fix`: 修复
- `test`: 测试相关
- `refactor`: 重构
- `docs`: 文档

**示例**:
```
[Phase-2] feat: 实现Episodic记忆写入

- 添加ProblemAttempt模型
- 实现AnswerTraceRepository
- 支持时间序列查询

测试: 单元测试通过，覆盖率92%
```

---

## 13. 质量门禁

每个Phase必须通过:

1. ✅ 单元测试覆盖率 ≥ 85%
2. ✅ 所有测试用例通过
3. ✅ 代码风格检查通过 (black, isort, mypy)
4. ✅ CI/CD质量门禁:
   - unit_test_pass_rate: 100%
   - code_coverage: ">= 85%"
   - e2e_critical_paths: 100%
   - p90_response: "< 90s"
   - model_consensus: ">= 80%"

---

## 14. 安全考虑

### 14.1 数据安全

- **敏感数据**: 学生姓名等使用加密存储
- **图片存储**: 原图压缩后存储，敏感信息脱敏
- **访问控制**: JWT Token认证，分级权限

### 14.2 AI安全

- **幻觉防护**: 3模型仲裁 + 人工审核机制
- **输出过滤**: 讲解内容安全性检查
- **输入过滤**: 家长描述敏感词过滤

### 14.3 性能安全

- **限流保护**: API级别限流防刷
- **超时处理**: 90秒闭环超时降级
- **并发控制**: 模型调用并发限制

---

## 15. 术语表

| 术语 | 说明 |
|------|------|
| **ZPD** | 最近发展区（Zone of Proximal Development） |
| **MCP** | Model Context Protocol |
| **OCR** | 光学字符识别 |
| **API** | 应用程序接口 |
| **E2E** | 端到端测试 |
| **冷启动** | 系统初始阶段数据不足的状态 |
| **变形题** | 基于原题生成的变式练习题 |
| **知识结晶** | 24小时后确认的持久化认知数据 |
| **记忆层** | Profile/Episodic/Semantic/Meta四层记忆 |
| **仲裁** | 多模型结果投票决策机制 |

---

## 16. 参考资源

### 16.1 项目文档

- [AI助教系统-开发技术文档](./docs/AI助教系统-开发技术文档.md) - 完整技术文档导航
- [01-系统架构设计](./docs/01-系统架构设计.md) - 分层架构详细设计
- [02-功能模块设计](./docs/02-功能模块设计.md) - 51个功能点
- [03-数据模型设计](./docs/03-数据模型设计.md) - ER图和Schema
- [04-API接口设计](./docs/04-API接口设计.md) - OpenAPI规范
- [05-测试策略设计](./docs/05-测试策略设计.md) - 测试用例

### 16.2 外部参考

- [OpenHarness GitHub](https://github.com/HKUDS/OpenHarness)
- [Kimi Code API Docs](https://www.kimi.com/code/docs/more/third-party-agents.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

*本文档基于OpenHarness架构设计，确保功能可追溯、可测性，支持敏捷开发和持续迭代。*
