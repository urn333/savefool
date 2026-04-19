# AI助教系统 - 开发计划

> 开发模式: 测试驱动开发(TDD) + 阶段式推进
> 质量标准: 所有测试通过才能进入下一阶段

---

## 阶段规划

### Phase 0: 项目初始化 ✅
- [x] 目录结构创建
- [x] Git初始化
- [x] 依赖配置
- [x] 基础工具类（generate_id, now_timestamp 等）
- [x] 配置管理（Pydantic-Settings, .env）

### Phase 1: 数据层
**目标**: 建立完整的数据存储基础

**开发任务**:
- 设计SQLite数据库Schema（基于docs/03-数据模型设计.md）
- 实现SQLAlchemy ORM模型
- 实现基础CRUD操作
- 实现数据库迁移(alembic)

**测试要求**:
- 所有表结构测试
- CRUD操作测试
- 外键约束测试
- 索引性能测试

---

### Phase 2: 记忆系统基础
**目标**: 实现OpenHarness风格的四层记忆系统

**开发任务**:
- Profile记忆（长期认知画像）
- Episodic记忆（作业事件流）
- Semantic记忆（结构化知识）
- Meta记忆（元认知层）

**测试要求**:
- 每层记忆的读写测试
- 记忆数据序列化/反序列化测试
- 记忆查询接口测试

---

### Phase 3: 多模型仲裁引擎
**目标**: 实现三模型并行推理和仲裁

**开发任务**:
- 模型A调度器（通用大模型）
- 模型B调度器（理科专用模型）
- 模型C调度器（开源验证模型）
- 并行任务协调器
- 仲裁决策引擎
- 结果融合算法

**测试要求**:
- 单模型调用测试（Mock）
- 并行调度测试
- 仲裁逻辑测试（各种共识场景）
- 超时处理测试

---

### Phase 4: 诊断流程引擎
**目标**: 实现90秒闭环诊断

**开发任务**:
- 错题识别与定位
- 错误归因分析
- 分层诊断选项生成（Step1/Step2）
- 诊断路径记录

**测试要求**:
- 错题识别准确率测试
- 归因分析测试
- 分层选项生成测试
- 诊断路径记录测试

---

### Phase 5: 变形题生成引擎
**目标**: 实现即时变形题生成和验证

**开发任务**:
- 数值变形生成
- 逆运算变形生成
- 变形题难度评估
- 可信度评分（1-5星人工评分机制）

**测试要求**:
- 变形正确性测试（100%答案正确）
- 等价性保持测试
- 可信度评分测试

---

### Phase 6: Web API层与记忆系统集成 ✅ (进行中)
**目标**: 提供RESTful API接口，启用数据库持久化，接入记忆系统

**已完成 (Phase 6-1)**:
- [x] FastAPI应用框架 + lifespan 数据库建表
- [x] 扩展 HomeworkStatus 枚举（PENDING/PROCESSING/COMPLETED/FAILED）
- [x] 扩展 Homework 模型（诊断结果、错误计数等字段）
- [x] 新建 HomeworkService（替代内存存储 _homework_store）
- [x] 新建 MemoryService（封装记忆系统查询/写入）
- [x] 诊断流程接入记忆读取（薄弱环节结构化查询拼入 Kimi prompt）
- [x] 诊断流程接入记忆写入（掌握度更新、认知缺口创建）

**已完成 (Phase 6-2)**:
- [x] 统计页从真实数据库数据生成（替换 random mock）
  - [x] /overview: homework 表聚合统计
  - [x] /trends: 按周聚合正确率/掌握度趋势
  - [x] /weak-points: cognitive_gap + student_knowledge_mastery 真实查询
  - [x] /knowledge-graph: student_knowledge_mastery 节点构建

**待完成**:
- [ ] Phase 6-3: 诊断时读取掌握度影响诊断选项
- [ ] Phase 6-4: 结果页展示历史薄弱点关联
- [ ] Phase 6-5: 结晶机制定时触发（pending → crystallized）

**测试要求**:
- API单元测试
- 集成测试
- 限流测试
- 当前: 482 passed, coverage 66%

---

### Phase 7: 24小时结晶机制
**目标**: 实现记忆数据自动结晶

**状态**: 核心代码已实现（crystallization/ 目录），待接入定时调度

**开发任务**:
- [ ] 定时任务调度（APScheduler 或诊断时检查）
- [x] 结晶条件判定（已实现）
- [x] 数据压缩(auto-compact)（已实现）
- [x] 状态流转(pending → crystallized/dismissed)（已实现）

**测试要求**:
- 结晶条件判定测试
- 状态流转测试
- 数据压缩测试

---

## Git提交规范

```
[Phase-X] 类型: 简短描述

详细描述...

测试: 测试通过情况
```

类型:
- `feat`: 新功能
- `fix`: 修复
- `test`: 测试相关
- `refactor`: 重构
- `docs`: 文档

---

## 质量门禁

每个Phase必须通过:
1. 单元测试覆盖率 ≥ 85%
2. 所有测试用例通过
3. 代码风格检查通过(black, isort, mypy)
4. 代码审查（子代理交叉检查）
