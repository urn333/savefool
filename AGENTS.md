# AI助教系统 - 开发指南

> **项目状态**: 设计完成，待开发  
> **文档版本**: v1.0  
> **最后更新**: 2024年

---

## 1. 项目概述

AI助教系统是一个面向中学生（13-16岁）的AI驱动作业诊断平台，通过多模型仲裁、变形题生成和分层诊断，识别学习问题的**根本原因**（而非仅判对错）。

### 1.1 核心设计理念

| 原则 | 说明 |
|------|------|
| **诊断先于讲解** | 先定位认知断点，再推送解决方案 |
| **少即是多** | 考点描述≤3条，诊断选项≤3个，避免认知过载 |
| **数据驱动** | 1个月冷启动积累，形成个人认知画像 |

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
| **模型A** (GPT-4 通用) | 题目解构、考点分类 | 0.4 |
| **模型B** (DeepSeek-Math) | 逻辑推演、步骤验证 | 0.4 |
| **模型C** (Llama-3-70B) | 概念映射、归因交叉验证 | 0.2 |

**仲裁逻辑**:
- **共识≥2/3**: 采用多数结果，置信度"高"
- **全部分歧**: 触发即时变形题测试，置信度"待验证"

---

## 2. 技术架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│  表现层 (Presentation Layer)                              │
│  ├── 三页面极简UI（上传页/结果页/统计页）                    │
│  ├── 拍照组件                                             │
│  ├── 可视化图表（知识星系/成长曲线）                        │
│  └── 本地缓存 SQLite                                      │
├─────────────────────────────────────────────────────────┤
│  应用层 (Application Layer)                               │
│  ├── API网关                                              │
│  ├── 会话管理                                             │
│  ├── 上传服务 / 结果服务 / 统计服务                         │
├─────────────────────────────────────────────────────────┤
│  领域层 (Domain Layer)                                    │
│  ├── 核心引擎                                             │
│  │   ├── 诊断流程引擎 (DiagnosisEngine)                   │
│  │   ├── 多模型仲裁引擎 (ArbitrationEngine)               │
│  │   └── 变形题生成引擎 (VariantGenerator)                │
│  ├── 记忆系统 (参考OpenHarness memory/)                   │
│  │   ├── Profile记忆 (长期认知画像)                        │
│  │   ├── Episodic记忆 (作业事件流)                         │
│  │   ├── Semantic记忆 (结构化知识)                         │
│  │   └── Meta记忆 (元认知层)                               │
│  └── 领域服务                                             │
│      ├── 知识图谱服务                                      │
│      ├── 概念映射服务                                      │
│      └── 薄弱点分析服务                                     │
├─────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure Layer)                        │
│  ├── 多模态识别 (GPT-4V / Claude 3)                        │
│  ├── 仲裁模型集群                                         │
│  ├── 存储层                                               │
│  │   ├── SQLite (活跃数据)                                │
│  │   ├── Markdown (归档)                                  │
│  │   └── 向量数据库 (语义检索)                              │
│  └── 外部集成 (OpenHarness / MCP Server)                  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 OpenHarness架构映射

```
AI助教系统 ←→ OpenHarness框架
├── 诊断流程引擎 ←→ engine/ Agent Loop
├── 多模型仲裁引擎 ←→ tools/ 工具集
├── 变形题生成引擎 ←→ skills/ 知识技能
├── 记忆系统 ←→ memory/ 持久化记忆
└── 知识图谱服务 ←→ coordinator/ 多Agent协调
```

### 2.3 技术栈

| 层级 | 技术选型 |
|------|----------|
| **后端** | Python (FastAPI/Flask) |
| **数据库** | SQLite (活跃数据) |
| **向量存储** | 向量数据库 (语义检索) |
| **归档** | Markdown文件 |
| **AI模型** | GPT-4, DeepSeek-Math, Llama-3-70B |
| **前端** | React/Vue (待确定) |
| **部署** | Docker容器化 |

---

## 3. 项目结构

```
savefool/
├── docs/                              # 技术文档
│   ├── AI助教系统-开发技术文档.md       # 主文档
│   ├── 01-系统架构设计.md              # 架构设计
│   ├── 02-功能模块设计.md              # 51个功能点
│   ├── 03-数据模型设计.md              # ER图/Schema
│   ├── 04-API接口设计.md               # 21个API
│   ├── 05-测试策略设计.md              # 100+测试用例
│   └── *.xlsx                         # 追踪表（任务/用例/矩阵）
├── src/                               # 源代码 (待创建)
│   ├── presentation/                  # 表现层
│   ├── application/                   # 应用层
│   ├── domain/                        # 领域层
│   │   ├── engines/                   # 核心引擎
│   │   ├── memory/                    # 记忆系统
│   │   └── services/                  # 领域服务
│   └── infrastructure/                # 基础设施层
│       ├── storage/                   # 存储适配
│       └── models/                    # 模型客户端
├── tests/                             # 测试代码 (待创建)
│   ├── unit/                          # 单元测试
│   ├── integration/                   # 集成测试
│   └── e2e/                           # 端到端测试
├── scripts/                           # 工具脚本
└── AGENTS.md                          # 本文件
```

---

## 4. 开发规范

### 4.1 代码风格

- **语言**: Python 3.11+
- **类型注解**: 强制使用 Type Hints
- **文档字符串**: 使用 Google Style Docstrings
- **代码格式化**: Black + isort
- **静态检查**: mypy + pylint

### 4.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/包 | 小写+下划线 | `diagnosis_engine.py` |
| 类 | 大驼峰 | `ArbitrationEngine` |
| 函数/方法 | 小写+下划线 | `calculate_confidence()` |
| 常量 | 大写+下划线 | `MAX_RETRY_COUNT = 3` |
| 私有成员 | 前缀下划线 | `_internal_method()` |

### 4.3 功能追溯ID体系

所有功能、API、测试用例使用统一ID格式：

| 类型 | ID格式 | 示例 |
|------|--------|------|
| 功能 | F-{模块}-{序号} | F-UPLOAD-001 |
| API | API-{分组}-{序号} | API-HW-001 |
| 测试用例 | TC-{模块}-{序号} | TC-UPLOAD-001 |
| 开发任务 | TASK-{序号} | TASK-001 |

---

## 5. 构建和测试命令

### 5.1 环境搭建

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 5.2 测试命令

```bash
# 运行单元测试
pytest tests/unit/ -v --cov=src --cov-report=html

# 运行集成测试
pytest tests/integration/ -v

# 运行E2E测试
pytest tests/e2e/ -v

# 运行所有测试并生成报告
pytest --cov=src --cov-report=term-missing --cov-fail-under=85
```

### 5.3 代码质量检查

```bash
# 代码格式化
black src/ tests/
isort src/ tests/

# 静态类型检查
mypy src/

# 代码风格检查
pylint src/
```

### 5.4 运行服务

```bash
# 开发模式
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 6. 测试策略

### 6.1 测试分层金字塔

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

### 6.2 测试覆盖率目标

| 类型 | 目标 | 测量方式 |
|------|------|----------|
| 代码覆盖率 | ≥85% | 自动化测试工具 |
| 功能覆盖率 | 核心功能100% | 功能-测试用例矩阵 |
| 场景覆盖率 | 正常100%，边界≥90% | 测试用例评审 |

### 6.3 CI/CD质量门禁

```yaml
quality_gates:
  unit_test_pass_rate: 100%
  code_coverage: ">= 85%"
  e2e_critical_paths: 100%
  p90_response: "< 90s"
  model_consensus: ">= 80%"
```

---

## 7. 开发计划

### 7.1 Sprint规划

| Sprint | 周期 | 功能 | 工时 | 产出 |
|--------|------|------|------|------|
| Sprint 1 | Week 1-2 | 基础架构 | 12人天 | 数据层+上传 |
| Sprint 2 | Week 3-4 | 核心诊断 | 13人天 | 三模型仲裁 |
| Sprint 3 | Week 5-6 | 变形题+分层 | 12人天 | 诊断闭环 |
| Sprint 4 | Week 7-8 | 记忆+统计 | 11人天 | 知识图谱 |
| Sprint 5 | Week 9-10 | 冷启动+优化 | 12人天 | MVP完成 |

### 7.2 MVP功能清单（P0 - 44人天）

- [ ] 作业上传（拍照+描述）
- [ ] 图片预处理（压缩/去噪）
- [ ] 三模型并行推理
- [ ] 仲裁聚合算法
- [ ] 错题识别
- [ ] 数值变形生成
- [ ] 变形题答题验证
- [ ] 分层选择Step1/Step2

---

## 8. 数据模型

### 8.1 核心实体

```
STUDENT ||--o{ HOMEWORK : creates
STUDENT ||--|| COGNITIVE_PROFILE : has
HOMEWORK ||--o{ QUESTION : contains
QUESTION ||--o{ STUDENT_ANSWER : answered_by
STUDENT_ANSWER ||--o{ ERROR_DIAGNOSIS : triggers
ERROR_DIAGNOSIS ||--o{ VARIANT_QUESTION : validates
QUESTION ||--o{ QUESTION_KNOWLEDGE_TAG : tagged_with
KNOWLEDGE_POINT ||--o{ QUESTION_KNOWLEDGE_TAG : tags
STUDENT ||--o{ STUDENT_KNOWLEDGE_MASTERY : masters
STUDENT ||--o{ COGNITIVE_GAP : has
```

### 8.2 记忆系统存储结构

```
student_memory/
├── profile/                    # 长期认知画像
│   ├── cognitive_model.json     # 思维风格、错误DNA
│   └── zone_of_proximity.json   # 当前ZPD边界
├── episodic/                   # 作业事件流
│   ├── traces/                 # 解题决策路径
│   └── exercises/              # 原题与变形题lineage
├── semantic/                   # 结构化知识
│   ├── misconceptions/         # 已验证的概念误解
│   └── prerequisite_chains/    # 个人化知识依赖
└── meta/                       # 元认知层
    ├── pending_gaps.json       # 待验证缺口（24小时观察期）
    └── crystallized/           # 已固化认知特征（≥30天）
```

---

## 9. API设计规范

### 9.1 基础信息

```yaml
Base URL: https://api.ai-tutor.com/v1
Protocol: HTTPS
Content-Type: application/json
Timeout: 30s (默认) / 90s (文件上传)
```

### 9.2 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

### 9.3 核心API

| API ID | 方法 | 路径 | 功能 | 限流 |
|--------|------|------|------|------|
| API-HW-001 | POST | /v1/homework | 上传作业 | 10/min |
| API-REC-002 | GET | /v1/recognition/{id} | 获取识别结果 | 60/min |
| API-DIA-001 | GET | /v1/diagnosis/options | 获取诊断选项 | 30/min |
| API-DIA-002 | POST | /v1/diagnosis/select | 提交诊断选择 | 30/min |
| API-VAR-001 | POST | /v1/variant/generate | 生成变形题 | 20/min |
| API-KG-001 | GET | /v1/knowledge/graph | 获取知识图谱 | 30/min |
| API-STAT-001 | GET | /v1/statistics/weak-points | 薄弱点清单 | 30/min |

---

## 10. 安全考虑

### 10.1 数据安全

- **敏感数据**: 学生姓名等使用加密存储
- **图片存储**: 原图压缩后存储，敏感信息脱敏
- **访问控制**: JWT Token认证，分级权限

### 10.2 AI安全

- **幻觉防护**: 3模型仲裁 + 人工审核机制
- **输出过滤**: 讲解内容安全性检查
- **输入过滤**: 家长描述敏感词过滤

### 10.3 性能安全

- **限流保护**: API级别限流防刷
- **超时处理**: 90秒闭环超时降级
- **并发控制**: 模型调用并发限制

---

## 11. 参考资源

### 11.1 技术文档

- [AI助教系统-开发技术文档](./docs/AI助教系统-开发技术文档.md) - 完整技术文档
- [01-系统架构设计](./docs/01-系统架构设计.md) - 分层架构详细设计
- [02-功能模块设计](./docs/02-功能模块设计.md) - 51个功能点
- [03-数据模型设计](./docs/03-数据模型设计.md) - ER图和Schema
- [04-API接口设计](./docs/04-API接口设计.md) - OpenAPI规范
- [05-测试策略设计](./docs/05-测试策略设计.md) - 测试用例

### 11.2 外部参考

- [OpenHarness GitHub](https://github.com/HKUDS/OpenHarness)
- [OpenHarness Architecture](https://github.com/HKUDS/OpenHarness#-harness-architecture)
- [Anthropic Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps)

---

## 12. 术语表

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

---

*本文档基于OpenHarness架构设计，确保功能可追溯、可测性，支持敏捷开发和持续迭代。*
