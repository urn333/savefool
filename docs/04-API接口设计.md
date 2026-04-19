# AI助教系统 API接口设计文档

> 文档版本：v1.1.0  
> 最后更新：2026-04-19  
> API版本：v1  
> **变更**: 统计接口（API-STAT-001~002）数据来源从 mock 改为真实数据库查询

---

## 目录

1. [API概述](#1-api概述)
2. [公共规范](#2-公共规范)
3. [认证授权](#3-认证授权)
4. [API分组详解](#4-api分组详解)
   - 4.1 作业管理API
   - 4.2 题目识别API
   - 4.3 诊断API
   - 4.4 变形题API
   - 4.5 知识图谱API
   - 4.6 统计API
   - 4.7 家长描述API
5. [错误码定义](#5-错误码定义)
6. [接口依赖关系](#6-接口依赖关系)
7. [OpenAPI规范](#7-openapi规范)

---

## 1. API概述

### 1.1 版本策略

| 版本 | 状态 | 说明 |
|------|------|------|
| v1 | 当前版本 | 稳定版本，推荐使用 |
| v2 | 规划中 | 预计2024年Q4发布 |

**版本控制方式**：URL路径版本控制
```
https://api.ai-tutor.com/v1/...
```

### 1.2 API分组

| 分组 | 前缀 | 描述 | 接口数量 |
|------|------|------|----------|
| 作业管理 | `/v1/homework` | 作业上传、查询、管理 | 4 |
| 题目识别 | `/v1/recognition` | 图片识别、OCR、校正 | 3 |
| 诊断 | `/v1/diagnosis` | 错题诊断、选项管理 | 3 |
| 变形题 | `/v1/variant` | 变形题生成、验证 | 3 |
| 知识图谱 | `/v1/knowledge` | 知识图谱、薄弱点 | 3 |
| 统计 | `/v1/statistics` | 学习统计、趋势分析 | 3 |
| 家长描述 | `/v1/parent` | 家长描述解析 | 2 |

### 1.3 基础信息

```yaml
Base URL: https://api.ai-tutor.com
Protocol: HTTPS
Content-Type: application/json
Charset: UTF-8
Timeout: 30s (默认) / 90s (文件上传)
```

---

## 2. 公共规范

### 2.1 统一响应格式

所有API响应均采用以下统一格式：

```json
{
  "code": 0,           // 业务状态码，0表示成功
  "message": "success", // 状态描述
  "data": {},          // 业务数据（可选）
  "request_id": "req_xxx", // 请求追踪ID
  "timestamp": 1704067200  // 响应时间戳
}
```

### 2.2 分页规范

列表接口统一使用游标分页：

**请求参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cursor | string | 否 | 游标，首次请求不传 |
| limit | integer | 否 | 每页数量，默认20，最大100 |

**响应格式**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [],
    "pagination": {
      "has_more": true,
      "next_cursor": "xxx",
      "total": 100
    }
  }
}
```

### 2.3 请求头规范

| Header | 必填 | 说明 |
|--------|------|------|
| Authorization | 是 | Bearer Token，格式：`Bearer {token}` |
| Content-Type | 是 | `application/json` |
| X-Request-ID | 否 | 请求追踪ID，不传则服务端生成 |
| X-Client-Version | 是 | 客户端版本，如 `1.0.0` |
| X-Device-ID | 是 | 设备唯一标识 |

### 2.4 文件上传规范

| 参数 | 说明 |
|------|------|
| Content-Type | `multipart/form-data` |
| 单文件大小 | ≤10MB |
| 支持格式 | jpg, jpeg, png, webp |
| 图片分辨率 | 建议 ≥1080p |

---

## 3. 认证授权

### 3.1 认证方式

采用 **JWT Bearer Token** 认证

**Token获取**：通过登录接口获取
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 3.2 Token有效期

| Token类型 | 有效期 | 说明 |
|-----------|--------|------|
| Access Token | 2小时 | 接口访问凭证 |
| Refresh Token | 7天 | 刷新Access Token |

### 3.3 权限级别

| 级别 | 标识 | 说明 |
|------|------|------|
| 公开 | `public` | 无需认证 |
| 用户 | `user` | 需登录 |
| 家长 | `parent` | 家长身份 |
| 学生 | `student` | 学生身份 |
| 管理员 | `admin` | 管理员权限 |

---

## 4. API分组详解

### 4.1 作业管理API

#### API-HW-001: 上传作业

| 属性 | 值 |
|------|-----|
| **接口ID** | API-HW-001 |
| **路径** | `/v1/homework` |
| **方法** | POST |
| **描述** | 上传作业照片和家长描述 |
| **权限** | user |
| **限流** | 10次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| image | body | file | 是 | 作业照片，≤10MB |
| description | body | string | 否 | 家长描述，≤140字 |
| student_id | body | string | 是 | 学生ID |
| subject | body | string | 是 | 学科：math/chinese/english/... |

**请求示例**：
```http
POST /v1/homework HTTP/1.1
Content-Type: multipart/form-data
Authorization: Bearer {token}

------WebKitFormBoundary
Content-Disposition: form-data; name="image"; filename="homework.jpg"
Content-Type: image/jpeg

[二进制数据]
------WebKitFormBoundary
Content-Disposition: form-data; name="description"

孩子这道题做错了，不太理解
------WebKitFormBoundary
Content-Disposition: form-data; name="student_id"

stu_123456
------WebKitFormBoundary
Content-Disposition: form-data; name="subject"

math
------WebKitFormBoundary--
```

**响应示例（成功）**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "homework_id": "hw_abc123",
    "status": "processing",
    "created_at": 1704067200,
    "estimated_time": 30
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

**响应示例（失败）**：
```json
{
  "code": 400001,
  "message": "图片格式不支持",
  "data": null,
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-HW-002: 获取作业列表

| 属性 | 值 |
|------|-----|
| **接口ID** | API-HW-002 |
| **路径** | `/v1/homework` |
| **方法** | GET |
| **描述** | 获取学生作业列表 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | query | string | 是 | 学生ID |
| subject | query | string | 否 | 学科筛选 |
| status | query | string | 否 | 状态：pending/processing/completed |
| cursor | query | string | 否 | 分页游标 |
| limit | query | integer | 否 | 每页数量，默认20 |

**请求示例**：
```http
GET /v1/homework?student_id=stu_123456&subject=math&limit=20 HTTP/1.1
Authorization: Bearer {token}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "homework_id": "hw_abc123",
        "subject": "math",
        "status": "completed",
        "thumbnail_url": "https://cdn.example.com/thumb.jpg",
        "created_at": 1704067200,
        "completed_at": 1704067230,
        "error_count": 3,
        "total_count": 10
      }
    ],
    "pagination": {
      "has_more": true,
      "next_cursor": "eyJpZCI6MTB9",
      "total": 156
    }
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-HW-003: 获取作业详情

| 属性 | 值 |
|------|-----|
| **接口ID** | API-HW-003 |
| **路径** | `/v1/homework/{homework_id}` |
| **方法** | GET |
| **描述** | 获取作业详细信息和诊断结果 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| homework_id | path | string | 是 | 作业ID |

**请求示例**：
```http
GET /v1/homework/hw_abc123 HTTP/1.1
Authorization: Bearer {token}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "homework_id": "hw_abc123",
    "student_id": "stu_123456",
    "subject": "math",
    "status": "completed",
    "image_url": "https://cdn.example.com/hw.jpg",
    "parent_description": "孩子这道题做错了",
    "created_at": 1704067200,
    "completed_at": 1704067230,
    "questions": [
      {
        "question_id": "q_001",
        "type": "fill_blank",
        "content": "3 + 5 = ?",
        "student_answer": "7",
        "correct_answer": "8",
        "is_correct": false,
        "knowledge_point": "加法运算",
        "difficulty": "easy"
      }
    ],
    "summary": {
      "total_count": 10,
      "correct_count": 7,
      "error_count": 3,
      "accuracy_rate": 0.7
    }
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-HW-004: 删除作业

| 属性 | 值 |
|------|-----|
| **接口ID** | API-HW-004 |
| **路径** | `/v1/homework/{homework_id}` |
| **方法** | DELETE |
| **描述** | 删除指定作业 |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| homework_id | path | string | 是 | 作业ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted": true
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.2 题目识别API

#### API-REC-001: 提交图片识别

| 属性 | 值 |
|------|-----|
| **接口ID** | API-REC-001 |
| **路径** | `/v1/recognition` |
| **方法** | POST |
| **描述** | 提交作业图片进行OCR识别 |
| **权限** | user |
| **限流** | 10次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| image | body | file | 是 | 作业图片 |
| homework_id | body | string | 否 | 关联的作业ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "recognition_id": "rec_xyz789",
    "status": "processing",
    "estimated_time": 15
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-REC-002: 获取识别结果

| 属性 | 值 |
|------|-----|
| **接口ID** | API-REC-002 |
| **路径** | `/v1/recognition/{recognition_id}` |
| **方法** | GET |
| **描述** | 获取OCR识别结果 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| recognition_id | path | string | 是 | 识别任务ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "recognition_id": "rec_xyz789",
    "status": "completed",
    "questions": [
      {
        "question_id": "q_001",
        "type": "fill_blank",
        "content": "3 + 5 = ____",
        "student_answer": "7",
        "bbox": {
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50
        },
        "confidence": 0.95
      }
    ],
    "raw_text": "3 + 5 = 7",
    "confidence": 0.92
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-REC-003: 校正识别结果

| 属性 | 值 |
|------|-----|
| **接口ID** | API-REC-003 |
| **路径** | `/v1/recognition/{recognition_id}/correction` |
| **方法** | PUT |
| **描述** | 人工校正识别结果 |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| recognition_id | path | string | 是 | 识别任务ID |
| corrections | body | array | 是 | 校正内容列表 |

**请求Body**：
```json
{
  "corrections": [
    {
      "question_id": "q_001",
      "content": "3 + 5 = ____",
      "student_answer": "8"
    }
  ]
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "corrected": true,
    "updated_questions": 1
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.3 诊断API

#### API-DIA-001: 获取诊断选项

| 属性 | 值 |
|------|-----|
| **接口ID** | API-DIA-001 |
| **路径** | `/v1/diagnosis/{question_id}/options` |
| **方法** | GET |
| **描述** | 获取错题的3选项分层诊断 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| question_id | path | string | 是 | 题目ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "question_id": "q_001",
    "options": [
      {
        "level": 1,
        "label": "粗心大意",
        "description": "计算过程正确，但结果写错",
        "icon": "careless"
      },
      {
        "level": 2,
        "label": "概念模糊",
        "description": "对进位加法概念理解不透彻",
        "icon": "concept"
      },
      {
        "level": 3,
        "label": "完全不会",
        "description": "不理解加法运算的基本方法",
        "icon": "unknown"
      }
    ]
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-DIA-002: 提交诊断选择

| 属性 | 值 |
|------|-----|
| **接口ID** | API-DIA-002 |
| **路径** | `/v1/diagnosis/{question_id}` |
| **方法** | POST |
| **描述** | 提交诊断选项选择 |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| question_id | path | string | 是 | 题目ID |
| level | body | integer | 是 | 选择层级：1/2/3 |
| notes | body | string | 否 | 补充说明 |

**请求Body**：
```json
{
  "level": 2,
  "notes": "孩子好像不太理解进位"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "diagnosis_id": "dia_abc456",
    "status": "completed",
    "result": {
      "level": 2,
      "knowledge_gap": "进位加法概念",
      "recommendation": "建议复习进位加法规则"
    }
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-DIA-003: 获取诊断结果

| 属性 | 值 |
|------|-----|
| **接口ID** | API-DIA-003 |
| **路径** | `/v1/diagnosis/{diagnosis_id}` |
| **方法** | GET |
| **描述** | 获取完整诊断结果和讲解 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| diagnosis_id | path | string | 是 | 诊断ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "diagnosis_id": "dia_abc456",
    "question_id": "q_001",
    "level": 2,
    "analysis": {
      "error_type": "概念模糊",
      "root_cause": "对进位规则理解不透彻",
      "knowledge_points": ["加法运算", "进位规则"]
    },
    "explanation": {
      "text": "我们来看这道题：3 + 5 = 8。个位数相加：3 + 5 = 8，不需要进位。",
      "steps": [
        {
          "step": 1,
          "content": "先看个位数：3和5",
          "highlight": "3, 5"
        },
        {
          "step": 2,
          "content": "个位相加：3 + 5 = 8",
          "highlight": "8"
        }
      ],
      "tips": ["记住：相加满10才进位", "先算个位，再算十位"]
    },
    "variant_ready": true
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.4 变形题API

#### API-VAR-001: 生成变形题

| 属性 | 值 |
|------|-----|
| **接口ID** | API-VAR-001 |
| **路径** | `/v1/variant` |
| **方法** | POST |
| **描述** | 基于错题生成变形练习题 |
| **权限** | user |
| **限流** | 20次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| question_id | body | string | 是 | 原题ID |
| difficulty | body | string | 否 | 难度：same/easier/harder，默认same |
| count | body | integer | 否 | 生成数量，默认3，最大5 |

**请求Body**：
```json
{
  "question_id": "q_001",
  "difficulty": "same",
  "count": 3
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "variant_set_id": "var_set_789",
    "variants": [
      {
        "variant_id": "var_001",
        "content": "4 + 5 = ?",
        "type": "fill_blank",
        "difficulty": "easy",
        "knowledge_point": "加法运算"
      },
      {
        "variant_id": "var_002",
        "content": "7 + 2 = ?",
        "type": "fill_blank",
        "difficulty": "easy",
        "knowledge_point": "加法运算"
      },
      {
        "variant_id": "var_003",
        "content": "6 + 6 = ?",
        "type": "fill_blank",
        "difficulty": "medium",
        "knowledge_point": "进位加法"
      }
    ]
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-VAR-002: 提交变形题答案

| 属性 | 值 |
|------|-----|
| **接口ID** | API-VAR-002 |
| **路径** | `/v1/variant/{variant_set_id}/answers` |
| **方法** | POST |
| **描述** | 提交变形题答案 |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| variant_set_id | path | string | 是 | 变形题组ID |
| answers | body | array | 是 | 答案列表 |

**请求Body**：
```json
{
  "answers": [
    {
      "variant_id": "var_001",
      "answer": "9"
    },
    {
      "variant_id": "var_002",
      "answer": "9"
    },
    {
      "variant_id": "var_003",
      "answer": "12"
    }
  ]
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "validated": true,
    "results": [
      {
        "variant_id": "var_001",
        "correct": true,
        "answer": "9",
        "correct_answer": "9"
      },
      {
        "variant_id": "var_002",
        "correct": true,
        "answer": "9",
        "correct_answer": "9"
      },
      {
        "variant_id": "var_003",
        "correct": true,
        "answer": "12",
        "correct_answer": "12"
      }
    ],
    "score": 100,
    "passed": true
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-VAR-003: 获取验证结果

| 属性 | 值 |
|------|-----|
| **接口ID** | API-VAR-003 |
| **路径** | `/v1/variant/{variant_set_id}/result` |
| **方法** | GET |
| **描述** | 获取变形题验证结果和反馈 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| variant_set_id | path | string | 是 | 变形题组ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "variant_set_id": "var_set_789",
    "score": 100,
    "passed": true,
    "feedback": {
      "summary": "太棒了！全部答对！",
      "encouragement": "你已经掌握了这个知识点，继续保持！",
      "next_steps": ["尝试更难一点的题目", "学习下一个知识点"]
    },
    "knowledge_update": {
      "mastered": true,
      "mastery_level": 0.85
    }
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.5 知识图谱API

#### API-KG-001: 获取个人知识图谱

| 属性 | 值 |
|------|-----|
| **接口ID** | API-KG-001 |
| **路径** | `/v1/knowledge/graph` |
| **方法** | GET |
| **描述** | 获取学生个人知识图谱 |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | query | string | 是 | 学生ID |
| subject | query | string | 否 | 学科筛选 |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "stu_123456",
    "subject": "math",
    "graph": {
      "nodes": [
        {
          "id": "kp_001",
          "name": "加法运算",
          "category": "计算",
          "mastery_level": 0.85,
          "status": "mastered",
          "x": 100,
          "y": 100
        },
        {
          "id": "kp_002",
          "name": "进位加法",
          "category": "计算",
          "mastery_level": 0.6,
          "status": "learning",
          "x": 200,
          "y": 100
        }
      ],
      "edges": [
        {
          "source": "kp_001",
          "target": "kp_002",
          "relation": "prerequisite"
        }
      ]
    },
    "updated_at": 1704067200
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-KG-002: 获取薄弱点列表

| 属性 | 值 |
|------|-----|
| **接口ID** | API-KG-002 |
| **路径** | `/v1/knowledge/weaknesses` |
| **方法** | GET |
| **描述** | 获取Top5薄弱知识点 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | query | string | 是 | 学生ID |
| subject | query | string | 否 | 学科筛选 |
| limit | query | integer | 否 | 数量，默认5，最大10 |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "stu_123456",
    "weaknesses": [
      {
        "rank": 1,
        "knowledge_point_id": "kp_003",
        "name": "减法借位",
        "category": "计算",
        "mastery_level": 0.35,
        "error_count": 12,
        "last_error_at": 1703980800,
        "priority": "high"
      },
      {
        "rank": 2,
        "knowledge_point_id": "kp_004",
        "name": "乘法口诀",
        "category": "计算",
        "mastery_level": 0.45,
        "error_count": 8,
        "last_error_at": 1703894400,
        "priority": "high"
      }
    ],
    "total": 5
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-KG-003: 获取知识点详情

| 属性 | 值 |
|------|-----|
| **接口ID** | API-KG-003 |
| **路径** | `/v1/knowledge/points/{point_id}` |
| **方法** | GET |
| **描述** | 获取知识点详细信息和关联题目 |
| **权限** | user |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| point_id | path | string | 是 | 知识点ID |
| student_id | query | string | 是 | 学生ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "point_id": "kp_003",
    "name": "减法借位",
    "description": "当被减数个位小于减数个位时，需要向十位借1",
    "category": "计算",
    "difficulty": "medium",
    "prerequisites": ["kp_001", "kp_002"],
    "related_points": ["kp_005", "kp_006"],
    "student_status": {
      "mastery_level": 0.35,
      "practice_count": 25,
      "error_count": 12,
      "last_practice_at": 1703980800
    },
    "recommended_exercises": [
      {
        "exercise_id": "ex_001",
        "type": "fill_blank",
        "content": "32 - 15 = ?",
        "difficulty": "medium"
      }
    ]
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.6 统计API

#### API-STAT-001: 获取学习统计

| 属性 | 值 |
|------|-----|
| **接口ID** | API-STAT-001 |
| **路径** | `/v1/statistics/overview` |
| **方法** | GET |
| **描述** | 获取学生学习概览统计（从 homework 表真实聚合） |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | query | string | 是 | 学生ID |
| period | query | string | 否 | 周期：week/month/semester，默认month |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "stu_123456",
    "period": "month",
    "overview": {
      "total_homework": 45,
      "total_questions": 450,
      "accuracy_rate": 0.78,
      "practice_time": 1800,
      "streak_days": 7
    },
    "subject_stats": [
      {
        "subject": "math",
        "homework_count": 20,
        "accuracy_rate": 0.75,
        "weakness_count": 3
      },
      {
        "subject": "chinese",
        "homework_count": 15,
        "accuracy_rate": 0.82,
        "weakness_count": 2
      }
    ],
    "achievements": [
      {
        "id": "ach_001",
        "name": "连续7天打卡",
        "icon": "streak_7",
        "earned_at": 1704067200
      }
    ]
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-STAT-002: 获取成长趋势

| 属性 | 值 |
|------|-----|
| **接口ID** | API-STAT-002 |
| **路径** | `/v1/statistics/trend` |
| **方法** | GET |
| **描述** | 获取学习成长趋势曲线（从 homework 表按周聚合） |
| **权限** | user |
| **限流** | 30次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | query | string | 是 | 学生ID |
| metric | query | string | 是 | 指标：accuracy/mastery/practice_time |
| period | query | string | 否 | 周期：week/month/semester/year |
| subject | query | string | 否 | 学科筛选 |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "student_id": "stu_123456",
    "metric": "accuracy",
    "period": "month",
    "subject": "math",
    "trend": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "data_points": [
        {
          "date": "2024-01-01",
          "value": 0.65,
          "homework_count": 2
        },
        {
          "date": "2024-01-15",
          "value": 0.72,
          "homework_count": 3
        },
        {
          "date": "2024-01-31",
          "value": 0.78,
          "homework_count": 2
        }
      ],
      "trend_direction": "up",
      "improvement": 0.13
    }
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-STAT-003: 生成学习报告

| 属性 | 值 |
|------|-----|
| **接口ID** | API-STAT-003 |
| **路径** | `/v1/statistics/report` |
| **方法** | POST |
| **描述** | 生成学习报告 |
| **权限** | user |
| **限流** | 5次/小时 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| student_id | body | string | 是 | 学生ID |
| period | body | string | 是 | 周期：week/month/semester |
| format | body | string | 否 | 格式：pdf/html，默认pdf |

**请求Body**：
```json
{
  "student_id": "stu_123456",
  "period": "month",
  "format": "pdf"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "rep_abc789",
    "status": "generating",
    "estimated_time": 10,
    "download_url": null
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

**查询报告状态**：
```http
GET /v1/statistics/report/{report_id}
```

**响应示例（完成）**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "rep_abc789",
    "status": "completed",
    "download_url": "https://cdn.example.com/reports/rep_abc789.pdf",
    "expires_at": 1706659200
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

### 4.7 家长描述API

#### API-PAR-001: 提交家长描述

| 属性 | 值 |
|------|-----|
| **接口ID** | API-PAR-001 |
| **路径** | `/v1/parent/description` |
| **方法** | POST |
| **描述** | 提交家长对作业的观察描述 |
| **权限** | parent |
| **限流** | 20次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| homework_id | body | string | 是 | 作业ID |
| description | body | string | 是 | 家长描述，≤140字 |

**请求Body**：
```json
{
  "homework_id": "hw_abc123",
  "description": "孩子这道题做错了，不太理解进位的概念，希望多讲解一下"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "description_id": "desc_xyz456",
    "homework_id": "hw_abc123",
    "status": "processing",
    "parsed_keywords": null,
    "estimated_time": 5
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

#### API-PAR-002: 获取解析结果

| 属性 | 值 |
|------|-----|
| **接口ID** | API-PAR-002 |
| **路径** | `/v1/parent/description/{description_id}` |
| **方法** | GET |
| **描述** | 获取AI解析的家长描述结果 |
| **权限** | parent |
| **限流** | 60次/分钟 |

**请求参数**：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| description_id | path | string | 是 | 描述ID |

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "description_id": "desc_xyz456",
    "homework_id": "hw_abc123",
    "original_text": "孩子这道题做错了，不太理解进位的概念",
    "parsed_result": {
      "keywords": ["进位", "不理解"],
      "intent": "概念讲解",
      "urgency": "normal",
      "related_knowledge": ["进位加法"],
      "suggested_focus": ["进位规则", "加法运算步骤"]
    },
    "ai_suggestions": [
      "建议使用实物演示进位过程",
      "可以先从简单的个位数加法开始"
    ],
    "integrated_into_diagnosis": true
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

## 5. 错误码定义

### 5.1 错误码格式

错误码采用6位数字格式：`XXYYYY`
- `XX`：错误类别
- `YYYY`：具体错误

### 5.2 错误码列表

| 错误码 | 类别 | 说明 | HTTP状态码 |
|--------|------|------|------------|
| **系统级错误 (00)** |
| 000001 | 系统 | 系统内部错误 | 500 |
| 000002 | 系统 | 服务暂时不可用 | 503 |
| 000003 | 系统 | 请求超时 | 504 |
| **认证授权错误 (01)** |
| 010001 | 认证 | Token无效或过期 | 401 |
| 010002 | 认证 | Token格式错误 | 401 |
| 010003 | 授权 | 权限不足 | 403 |
| 010004 | 授权 | 未登录 | 401 |
| **请求参数错误 (02)** |
| 020001 | 参数 | 参数缺失 | 400 |
| 020002 | 参数 | 参数格式错误 | 400 |
| 020003 | 参数 | 参数值非法 | 400 |
| 020004 | 参数 | JSON解析失败 | 400 |
| **资源错误 (03)** |
| 030001 | 资源 | 资源不存在 | 404 |
| 030002 | 资源 | 资源已存在 | 409 |
| 030003 | 资源 | 资源被占用 | 423 |
| **业务逻辑错误 (04)** |
| 040001 | 业务 | 图片格式不支持 | 400 |
| 040002 | 业务 | 图片大小超限 | 400 |
| 040003 | 业务 | 识别失败 | 422 |
| 040004 | 业务 | 诊断未完成 | 422 |
| 040005 | 业务 | 变形题生成失败 | 422 |
| 040006 | 业务 | 描述长度超限 | 400 |
| **限流错误 (05)** |
| 050001 | 限流 | 请求过于频繁 | 429 |
| 050002 | 限流 | 配额已用完 | 429 |

### 5.3 错误响应示例

```json
{
  "code": 010001,
  "message": "Token已过期，请重新登录",
  "data": {
    "error_type": "authentication",
    "detail": "Token expired at 1704067200"
  },
  "request_id": "req_xxx",
  "timestamp": 1704067200
}
```

---

## 6. 接口依赖关系

### 6.1 90秒闭环流程

```mermaid
sequenceDiagram
    participant U as 用户/家长
    participant A as API Gateway
    participant H as 作业服务
    participant R as 识别服务
    participant D as 诊断服务
    participant V as 变形题服务
    participant K as 知识图谱服务

    %% 作业上传
    U->>A: POST /v1/homework (图片+描述)
    A->>H: 创建作业记录
    H-->>A: homework_id, status=processing
    A-->>U: 返回homework_id

    %% 异步识别
    H->>R: 提交图片识别任务
    R-->>H: recognition_id
    
    loop 轮询识别结果
        U->>A: GET /v1/recognition/{id}
        A->>R: 查询识别状态
        R-->>A: 识别结果
        A-->>U: 返回题目列表
    end

    %% 获取诊断选项
    U->>A: GET /v1/diagnosis/{qid}/options
    A->>D: 获取3选项分层诊断
    D-->>A: 诊断选项列表
    A-->>U: 返回选项

    %% 提交诊断选择
    U->>A: POST /v1/diagnosis/{qid} (level)
    A->>D: 保存诊断选择
    D->>K: 更新知识图谱
    D-->>A: diagnosis_id
    A-->>U: 返回诊断ID

    %% 获取诊断结果
    U->>A: GET /v1/diagnosis/{id}
    A->>D: 获取完整诊断
    D-->>A: 诊断结果+讲解
    A-->>U: 返回结果

    %% 生成变形题
    U->>A: POST /v1/variant (question_id)
    A->>V: 生成变形题
    V-->>A: 变形题列表
    A-->>U: 返回变形题

    %% 提交答案
    U->>A: POST /v1/variant/{id}/answers
    A->>V: 验证答案
    V->>K: 更新掌握度
    V-->>A: 验证结果
    A-->>U: 返回结果

    %% 更新知识图谱
    K->>K: 重新计算掌握度
    K->>K: 更新薄弱点列表
```

### 6.2 统计页面数据流

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as API Gateway
    participant S as 统计服务
    participant K as 知识图谱服务

    U->>A: GET /v1/knowledge/graph
    A->>K: 获取知识图谱
    K-->>A: 图谱数据
    A-->>U: 返回图谱

    U->>A: GET /v1/knowledge/weaknesses
    A->>K: 获取薄弱点Top5
    K-->>A: 薄弱点列表
    A-->>U: 返回列表

    U->>A: GET /v1/statistics/trend
    A->>S: 获取成长趋势
    S-->>A: 趋势数据
    A-->>U: 返回趋势曲线
```

---

## 7. OpenAPI规范

### 7.1 完整OpenAPI 3.0定义

```yaml
openapi: 3.0.3
info:
  title: AI助教系统 API
  description: AI助教系统RESTful API接口规范
  version: 1.0.0
  contact:
    name: AI助教技术支持
    email: support@ai-tutor.com

servers:
  - url: https://api.ai-tutor.com/v1
    description: 生产环境
  - url: https://api-staging.ai-tutor.com/v1
    description: 测试环境

security:
  - BearerAuth: []

paths:
  # ========== 作业管理 ==========
  /homework:
    get:
      summary: 获取作业列表
      operationId: listHomework
      tags:
        - 作业管理
      parameters:
        - name: student_id
          in: query
          required: true
          schema:
            type: string
        - name: subject
          in: query
          schema:
            type: string
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, processing, completed]
        - name: cursor
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HomeworkListResponse'
    post:
      summary: 上传作业
      operationId: createHomework
      tags:
        - 作业管理
      requestBody:
        content:
          multipart/form-data:
            schema:
              $ref: '#/components/schemas/HomeworkUploadRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HomeworkCreateResponse'
        '400':
          description: 参数错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /homework/{homework_id}:
    get:
      summary: 获取作业详情
      operationId: getHomework
      tags:
        - 作业管理
      parameters:
        - name: homework_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HomeworkDetailResponse'
    delete:
      summary: 删除作业
      operationId: deleteHomework
      tags:
        - 作业管理
      parameters:
        - name: homework_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeleteResponse'

  # ========== 题目识别 ==========
  /recognition:
    post:
      summary: 提交图片识别
      operationId: submitRecognition
      tags:
        - 题目识别
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                image:
                  type: string
                  format: binary
                homework_id:
                  type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RecognitionSubmitResponse'

  /recognition/{recognition_id}:
    get:
      summary: 获取识别结果
      operationId: getRecognition
      tags:
        - 题目识别
      parameters:
        - name: recognition_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RecognitionResultResponse'

  /recognition/{recognition_id}/correction:
    put:
      summary: 校正识别结果
      operationId: correctRecognition
      tags:
        - 题目识别
      parameters:
        - name: recognition_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RecognitionCorrectionRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorrectionResponse'

  # ========== 诊断 ==========
  /diagnosis/{question_id}/options:
    get:
      summary: 获取诊断选项
      operationId: getDiagnosisOptions
      tags:
        - 诊断
      parameters:
        - name: question_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DiagnosisOptionsResponse'

  /diagnosis/{question_id}:
    post:
      summary: 提交诊断选择
      operationId: submitDiagnosis
      tags:
        - 诊断
      parameters:
        - name: question_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DiagnosisSubmitRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DiagnosisSubmitResponse'

  /diagnosis/{diagnosis_id}:
    get:
      summary: 获取诊断结果
      operationId: getDiagnosisResult
      tags:
        - 诊断
      parameters:
        - name: diagnosis_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DiagnosisResultResponse'

  # ========== 变形题 ==========
  /variant:
    post:
      summary: 生成变形题
      operationId: generateVariant
      tags:
        - 变形题
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VariantGenerateRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VariantGenerateResponse'

  /variant/{variant_set_id}/answers:
    post:
      summary: 提交变形题答案
      operationId: submitVariantAnswers
      tags:
        - 变形题
      parameters:
        - name: variant_set_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VariantAnswersRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VariantValidationResponse'

  /variant/{variant_set_id}/result:
    get:
      summary: 获取验证结果
      operationId: getVariantResult
      tags:
        - 变形题
      parameters:
        - name: variant_set_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VariantResultResponse'

  # ========== 知识图谱 ==========
  /knowledge/graph:
    get:
      summary: 获取个人知识图谱
      operationId: getKnowledgeGraph
      tags:
        - 知识图谱
      parameters:
        - name: student_id
          in: query
          required: true
          schema:
            type: string
        - name: subject
          in: query
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/KnowledgeGraphResponse'

  /knowledge/weaknesses:
    get:
      summary: 获取薄弱点列表
      operationId: getWeaknesses
      tags:
        - 知识图谱
      parameters:
        - name: student_id
          in: query
          required: true
          schema:
            type: string
        - name: subject
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 5
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/WeaknessesResponse'

  /knowledge/points/{point_id}:
    get:
      summary: 获取知识点详情
      operationId: getKnowledgePoint
      tags:
        - 知识图谱
      parameters:
        - name: point_id
          in: path
          required: true
          schema:
            type: string
        - name: student_id
          in: query
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/KnowledgePointResponse'

  # ========== 统计 ==========
  /statistics/overview:
    get:
      summary: 获取学习统计
      operationId: getStatisticsOverview
      tags:
        - 统计
      parameters:
        - name: student_id
          in: query
          required: true
          schema:
            type: string
        - name: period
          in: query
          schema:
            type: string
            enum: [week, month, semester]
            default: month
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StatisticsOverviewResponse'

  /statistics/trend:
    get:
      summary: 获取成长趋势
      operationId: getStatisticsTrend
      tags:
        - 统计
      parameters:
        - name: student_id
          in: query
          required: true
          schema:
            type: string
        - name: metric
          in: query
          required: true
          schema:
            type: string
            enum: [accuracy, mastery, practice_time]
        - name: period
          in: query
          schema:
            type: string
        - name: subject
          in: query
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StatisticsTrendResponse'

  /statistics/report:
    post:
      summary: 生成学习报告
      operationId: generateReport
      tags:
        - 统计
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ReportGenerateRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ReportGenerateResponse'

  # ========== 家长描述 ==========
  /parent/description:
    post:
      summary: 提交家长描述
      operationId: submitParentDescription
      tags:
        - 家长描述
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ParentDescriptionRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ParentDescriptionResponse'

  /parent/description/{description_id}:
    get:
      summary: 获取解析结果
      operationId: getParentDescription
      tags:
        - 家长描述
      parameters:
        - name: description_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ParentDescriptionDetailResponse'

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    # ========== 基础响应 ==========
    BaseResponse:
      type: object
      required:
        - code
        - message
        - request_id
        - timestamp
      properties:
        code:
          type: integer
          description: 业务状态码
        message:
          type: string
          description: 状态描述
        data:
          type: object
          description: 业务数据
        request_id:
          type: string
          description: 请求追踪ID
        timestamp:
          type: integer
          description: 响应时间戳

    ErrorResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                error_type:
                  type: string
                detail:
                  type: string

    # ========== 分页 ==========
    Pagination:
      type: object
      properties:
        has_more:
          type: boolean
        next_cursor:
          type: string
        total:
          type: integer

    # ========== 作业管理 ==========
    HomeworkUploadRequest:
      type: object
      required:
        - image
        - student_id
        - subject
      properties:
        image:
          type: string
          format: binary
          description: 作业照片
        description:
          type: string
          maxLength: 140
          description: 家长描述
        student_id:
          type: string
        subject:
          type: string
          enum: [math, chinese, english, physics, chemistry, biology, history, geography, politics]

    HomeworkCreateResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                homework_id:
                  type: string
                status:
                  type: string
                created_at:
                  type: integer
                estimated_time:
                  type: integer

    HomeworkListResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                list:
                  type: array
                  items:
                    $ref: '#/components/schemas/HomeworkItem'
                pagination:
                  $ref: '#/components/schemas/Pagination'

    HomeworkItem:
      type: object
      properties:
        homework_id:
          type: string
        subject:
          type: string
        status:
          type: string
        thumbnail_url:
          type: string
        created_at:
          type: integer
        completed_at:
          type: integer
        error_count:
          type: integer
        total_count:
          type: integer

    HomeworkDetailResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                homework_id:
                  type: string
                student_id:
                  type: string
                subject:
                  type: string
                status:
                  type: string
                image_url:
                  type: string
                parent_description:
                  type: string
                created_at:
                  type: integer
                completed_at:
                  type: integer
                questions:
                  type: array
                  items:
                    $ref: '#/components/schemas/Question'
                summary:
                  $ref: '#/components/schemas/HomeworkSummary'

    Question:
      type: object
      properties:
        question_id:
          type: string
        type:
          type: string
        content:
          type: string
        student_answer:
          type: string
        correct_answer:
          type: string
        is_correct:
          type: boolean
        knowledge_point:
          type: string
        difficulty:
          type: string

    HomeworkSummary:
      type: object
      properties:
        total_count:
          type: integer
        correct_count:
          type: integer
        error_count:
          type: integer
        accuracy_rate:
          type: number

    DeleteResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                deleted:
                  type: boolean

    # ========== 题目识别 ==========
    RecognitionSubmitResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                recognition_id:
                  type: string
                status:
                  type: string
                estimated_time:
                  type: integer

    RecognitionResultResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                recognition_id:
                  type: string
                status:
                  type: string
                questions:
                  type: array
                  items:
                    $ref: '#/components/schemas/RecognizedQuestion'
                raw_text:
                  type: string
                confidence:
                  type: number

    RecognizedQuestion:
      type: object
      properties:
        question_id:
          type: string
        type:
          type: string
        content:
          type: string
        student_answer:
          type: string
        bbox:
          $ref: '#/components/schemas/BoundingBox'
        confidence:
          type: number

    BoundingBox:
      type: object
      properties:
        x:
          type: integer
        y:
          type: integer
        width:
          type: integer
        height:
          type: integer

    RecognitionCorrectionRequest:
      type: object
      required:
        - corrections
      properties:
        corrections:
          type: array
          items:
            type: object
            properties:
              question_id:
                type: string
              content:
                type: string
              student_answer:
                type: string

    CorrectionResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                corrected:
                  type: boolean
                updated_questions:
                  type: integer

    # ========== 诊断 ==========
    DiagnosisOptionsResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                question_id:
                  type: string
                options:
                  type: array
                  items:
                    $ref: '#/components/schemas/DiagnosisOption'

    DiagnosisOption:
      type: object
      properties:
        level:
          type: integer
        label:
          type: string
        description:
          type: string
        icon:
          type: string

    DiagnosisSubmitRequest:
      type: object
      required:
        - level
      properties:
        level:
          type: integer
          enum: [1, 2, 3]
        notes:
          type: string

    DiagnosisSubmitResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                diagnosis_id:
                  type: string
                status:
                  type: string
                result:
                  $ref: '#/components/schemas/DiagnosisResultBrief'

    DiagnosisResultBrief:
      type: object
      properties:
        level:
          type: integer
        knowledge_gap:
          type: string
        recommendation:
          type: string

    DiagnosisResultResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                diagnosis_id:
                  type: string
                question_id:
                  type: string
                level:
                  type: integer
                analysis:
                  $ref: '#/components/schemas/DiagnosisAnalysis'
                explanation:
                  $ref: '#/components/schemas/Explanation'
                variant_ready:
                  type: boolean

    DiagnosisAnalysis:
      type: object
      properties:
        error_type:
          type: string
        root_cause:
          type: string
        knowledge_points:
          type: array
          items:
            type: string

    Explanation:
      type: object
      properties:
        text:
          type: string
        steps:
          type: array
          items:
            $ref: '#/components/schemas/ExplanationStep'
        tips:
          type: array
          items:
            type: string

    ExplanationStep:
      type: object
      properties:
        step:
          type: integer
        content:
          type: string
        highlight:
          type: string

    # ========== 变形题 ==========
    VariantGenerateRequest:
      type: object
      required:
        - question_id
      properties:
        question_id:
          type: string
        difficulty:
          type: string
          enum: [same, easier, harder]
          default: same
        count:
          type: integer
          default: 3
          maximum: 5

    VariantGenerateResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                variant_set_id:
                  type: string
                variants:
                  type: array
                  items:
                    $ref: '#/components/schemas/Variant'

    Variant:
      type: object
      properties:
        variant_id:
          type: string
        content:
          type: string
        type:
          type: string
        difficulty:
          type: string
        knowledge_point:
          type: string

    VariantAnswersRequest:
      type: object
      required:
        - answers
      properties:
        answers:
          type: array
          items:
            type: object
            properties:
              variant_id:
                type: string
              answer:
                type: string

    VariantValidationResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                validated:
                  type: boolean
                results:
                  type: array
                  items:
                    $ref: '#/components/schemas/VariantResult'
                score:
                  type: integer
                passed:
                  type: boolean

    VariantResult:
      type: object
      properties:
        variant_id:
          type: string
        correct:
          type: boolean
        answer:
          type: string
        correct_answer:
          type: string

    VariantResultResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                variant_set_id:
                  type: string
                score:
                  type: integer
                passed:
                  type: boolean
                feedback:
                  $ref: '#/components/schemas/VariantFeedback'
                knowledge_update:
                  $ref: '#/components/schemas/KnowledgeUpdate'

    VariantFeedback:
      type: object
      properties:
        summary:
          type: string
        encouragement:
          type: string
        next_steps:
          type: array
          items:
            type: string

    KnowledgeUpdate:
      type: object
      properties:
        mastered:
          type: boolean
        mastery_level:
          type: number

    # ========== 知识图谱 ==========
    KnowledgeGraphResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                student_id:
                  type: string
                subject:
                  type: string
                graph:
                  $ref: '#/components/schemas/Graph'
                updated_at:
                  type: integer

    Graph:
      type: object
      properties:
        nodes:
          type: array
          items:
            $ref: '#/components/schemas/GraphNode'
        edges:
          type: array
          items:
            $ref: '#/components/schemas/GraphEdge'

    GraphNode:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        category:
          type: string
        mastery_level:
          type: number
        status:
          type: string
        x:
          type: number
        y:
          type: number

    GraphEdge:
      type: object
      properties:
        source:
          type: string
        target:
          type: string
        relation:
          type: string

    WeaknessesResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                student_id:
                  type: string
                weaknesses:
                  type: array
                  items:
                    $ref: '#/components/schemas/Weakness'
                total:
                  type: integer

    Weakness:
      type: object
      properties:
        rank:
          type: integer
        knowledge_point_id:
          type: string
        name:
          type: string
        category:
          type: string
        mastery_level:
          type: number
        error_count:
          type: integer
        last_error_at:
          type: integer
        priority:
          type: string

    KnowledgePointResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                point_id:
                  type: string
                name:
                  type: string
                description:
                  type: string
                category:
                  type: string
                difficulty:
                  type: string
                prerequisites:
                  type: array
                  items:
                    type: string
                related_points:
                  type: array
                  items:
                    type: string
                student_status:
                  $ref: '#/components/schemas/StudentKnowledgeStatus'
                recommended_exercises:
                  type: array
                  items:
                    $ref: '#/components/schemas/Exercise'

    StudentKnowledgeStatus:
      type: object
      properties:
        mastery_level:
          type: number
        practice_count:
          type: integer
        error_count:
          type: integer
        last_practice_at:
          type: integer

    Exercise:
      type: object
      properties:
        exercise_id:
          type: string
        type:
          type: string
        content:
          type: string
        difficulty:
          type: string

    # ========== 统计 ==========
    StatisticsOverviewResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                student_id:
                  type: string
                period:
                  type: string
                overview:
                  $ref: '#/components/schemas/OverviewStats'
                subject_stats:
                  type: array
                  items:
                    $ref: '#/components/schemas/SubjectStat'
                achievements:
                  type: array
                  items:
                    $ref: '#/components/schemas/Achievement'

    OverviewStats:
      type: object
      properties:
        total_homework:
          type: integer
        total_questions:
          type: integer
        accuracy_rate:
          type: number
        practice_time:
          type: integer
        streak_days:
          type: integer

    SubjectStat:
      type: object
      properties:
        subject:
          type: string
        homework_count:
          type: integer
        accuracy_rate:
          type: number
        weakness_count:
          type: integer

    Achievement:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        icon:
          type: string
        earned_at:
          type: integer

    StatisticsTrendResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                student_id:
                  type: string
                metric:
                  type: string
                period:
                  type: string
                subject:
                  type: string
                trend:
                  $ref: '#/components/schemas/TrendData'

    TrendData:
      type: object
      properties:
        start_date:
          type: string
        end_date:
          type: string
        data_points:
          type: array
          items:
            $ref: '#/components/schemas/DataPoint'
        trend_direction:
          type: string
        improvement:
          type: number

    DataPoint:
      type: object
      properties:
        date:
          type: string
        value:
          type: number
        homework_count:
          type: integer

    ReportGenerateRequest:
      type: object
      required:
        - student_id
        - period
      properties:
        student_id:
          type: string
        period:
          type: string
        format:
          type: string
          enum: [pdf, html]
          default: pdf

    ReportGenerateResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                report_id:
                  type: string
                status:
                  type: string
                estimated_time:
                  type: integer
                download_url:
                  type: string
                  nullable: true

    # ========== 家长描述 ==========
    ParentDescriptionRequest:
      type: object
      required:
        - homework_id
        - description
      properties:
        homework_id:
          type: string
        description:
          type: string
          maxLength: 140

    ParentDescriptionResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                description_id:
                  type: string
                homework_id:
                  type: string
                status:
                  type: string
                parsed_keywords:
                  type: array
                  items:
                    type: string
                  nullable: true
                estimated_time:
                  type: integer

    ParentDescriptionDetailResponse:
      allOf:
        - $ref: '#/components/schemas/BaseResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                description_id:
                  type: string
                homework_id:
                  type: string
                original_text:
                  type: string
                parsed_result:
                  $ref: '#/components/schemas/ParsedResult'
                ai_suggestions:
                  type: array
                  items:
                    type: string
                integrated_into_diagnosis:
                  type: boolean

    ParsedResult:
      type: object
      properties:
        keywords:
          type: array
          items:
            type: string
        intent:
          type: string
        urgency:
          type: string
        related_knowledge:
          type: array
          items:
            type: string
        suggested_focus:
          type: array
          items:
            type: string
```

---

## 附录

### A. 接口汇总表

| 接口ID | 路径 | 方法 | 权限 | 限流 |
|--------|------|------|------|------|
| API-HW-001 | /v1/homework | POST | user | 10/min |
| API-HW-002 | /v1/homework | GET | user | 60/min |
| API-HW-003 | /v1/homework/{id} | GET | user | 60/min |
| API-HW-004 | /v1/homework/{id} | DELETE | user | 30/min |
| API-REC-001 | /v1/recognition | POST | user | 10/min |
| API-REC-002 | /v1/recognition/{id} | GET | user | 60/min |
| API-REC-003 | /v1/recognition/{id}/correction | PUT | user | 30/min |
| API-DIA-001 | /v1/diagnosis/{qid}/options | GET | user | 60/min |
| API-DIA-002 | /v1/diagnosis/{qid} | POST | user | 30/min |
| API-DIA-003 | /v1/diagnosis/{id} | GET | user | 60/min |
| API-VAR-001 | /v1/variant | POST | user | 20/min |
| API-VAR-002 | /v1/variant/{id}/answers | POST | user | 30/min |
| API-VAR-003 | /v1/variant/{id}/result | GET | user | 60/min |
| API-KG-001 | /v1/knowledge/graph | GET | user | 30/min |
| API-KG-002 | /v1/knowledge/weaknesses | GET | user | 60/min |
| API-KG-003 | /v1/knowledge/points/{id} | GET | user | 60/min |
| API-STAT-001 | /v1/statistics/overview | GET | user | 30/min |
| API-STAT-002 | /v1/statistics/trend | GET | user | 30/min |
| API-STAT-003 | /v1/statistics/report | POST | user | 5/hour |
| API-PAR-001 | /v1/parent/description | POST | parent | 20/min |
| API-PAR-002 | /v1/parent/description/{id} | GET | parent | 60/min |

### B. 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0.0 | 2024-XX-XX | 初始版本，包含7个API分组共21个接口 |

---

*文档结束*
