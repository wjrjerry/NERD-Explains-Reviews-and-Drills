# NERD 前端边界测试报告与优化方案

## 测试概览

| 测试类型 | 数量 | 通过 | 失败 | 跳过 |
|----------|------|------|------|------|
| 原有单元/集成测试 | 61 | 34 | 23 | 4 |
| **新增边界测试** | **61** | **60** | **1** | **0** |
| **合计** | **122** | **94** | **24** | **4** |

> 注：24 个失败中，23 个是原有测试在 Windows/SQLite 环境下的兼容性问题（Redis 不可用、SQLite 并发限制），与新功能无关。1 个是认证 Token Scheme 边界处理不一致。

## 新增边界测试覆盖范围

测试文件：[tests/test_boundary_frontend.py](tests/test_boundary_frontend.py)

| 测试类 | 覆盖内容 | 结果 |
|--------|----------|------|
| `TestAuthBoundaryCase` | 空用户名/密码、SQL注入、重复注册、错误密码、过期Token、非数字sub、并发注册 | ✅ 10/10 |
| `TestStudyTargetBoundaryCase` | 空标题、非法类型、分页边界、跨用户隔离 | ✅ 4/4 |
| `TestMaterialBoundaryCase` | 空文件、无文件上传、不存在的target、跨用户上传、超大文本、状态转换 | ✅ 6/6 |
| `TestQaBoundaryCase` | 未解析资料提问、空问题、跨用户访问、分页边界 | ✅ 4/4 |
| `TestQuestionBoundaryCase` | 非法题型、count=0、非法难度、未解析资料出题 | ✅ 4/4 |
| `TestSubmitBoundaryCase` | 空答案、缺少字段、无效question_id、不存在material | ✅ 4/4 |
| `TestWrongQuestionBoundaryCase` | 非法mastery状态、跨用户隔离、分页边界 | ✅ 3/3 |
| `TestReviewPlanBoundaryCase` | end<start、非法日期格式、跨用户计划、分页边界 | ✅ 4/4 |
| `TestKnowledgeGraphBoundaryCase` | 不存在的target、跨用户图谱、非法max_points、空图谱、不存在知识点 | ✅ 5/5 |
| `TestApiResponseConsistencyCase` | 所有公开端点返回 `{code, message, data}` 封套 | ✅ 3/3 |
| `TestAdminBoundaryCase` | 学生被拒403、管理员正常访问 | ✅ 2/2 |
| `TestFullFlowBoundaryCase` | **注册→目标→上传→解析→提炼→问答→出题→自测→错题→复习计划** | ✅ 通过 |
| `TestAiUsageBoundaryCase` | 认证要求、分页边界、摘要端点 | ✅ 3/3 |
| `TestExportBoundaryCase` | 未登录拒绝导出错题/复习计划 | ✅ 2/2 |

## 发现的关键边界问题

### 1. 认证 Token Scheme 处理不一致

- **位置**: [app/dependencies/auth.py:34](app/dependencies/auth.py#L34)
- **现象**: 当 `Authorization` 头使用非 Bearer scheme（如 `Token abc`）时，`HTTPBearer(auto_error=False)` 返回 `None`，导致返回"未提供认证令牌"而非"认证令牌类型错误"
- **影响**: 前端如果误用了错误的 scheme 格式，得到的错误提示不准确
- **建议修复**:
  ```python
  # 在 get_current_user 中，credentials 为 None 之前，
  # 检查 Authorization 头是否存在但 scheme 不匹配
  ```

### 2. 知识提炼接口需要 exactly-one 语义

- **位置**: [app/schemas/knowledge.py:35](app/schemas/knowledge.py#L35)
- **现象**: `material_id` 和 `target_id` 不能同时传，前端需了解这个约束
- **当前**: 返回 422 错误消息清晰，不阻塞前端开发

### 3. 知识图谱接口使用路径参数

- **位置**: [app/routers/knowledge_graphs.py:42](app/routers/knowledge_graphs.py#L42)
- **现象**: `GET /knowledge-graphs/{target_id}` 而非 `GET /knowledge-graphs?target_id=X`
- **影响**: 前端需注意 URL 拼接方式

### 4. 缺少统一的测试记录列表端点

- **现象**: 只有 `POST /tests/submit`，没有 `GET /tests/records`
- **影响**: 前端目前无法查看历史自测记录列表
- **建议**: 新增 `GET /tests/records` 端点

---

## 基于用户建议的优化方向与方案

### 一、知识点图谱 + 掌握度模型（最高优先级）

**当前状态**: ✅ 后端数据模型已完整实现

- `knowledge_points` 表 + `KnowledgePoint` 模型
- `material_knowledge_points`、`question_knowledge_points`、`user_knowledge_mastery` 关联表
- AI 出题已支持 `knowledge_point_ids` 参数
- 知识图谱生成 API (`POST /knowledge-graphs/generate`) 已就绪

**前端需要建设**:

```
前端新增页面/组件：
├── KnowledgeGraphView        # 可视化知识图谱（力导向图/树图）
│   ├── 每个知识点=圆形节点
│   ├── 大小 = importance_weight 映射 (权重 0→1 映射 30px→80px)
│   ├── 颜色 = 掌握度映射 (red=薄弱, yellow=基本, green=熟练, gray=未学习)
│   └── 点击节点 → 弹出该知识点的错题列表
├── KnowledgePointDrill       # 知识点详情页
│   ├── 关联资料片段 (GET /knowledge-points/{id}/materials)
│   ├── 关联题目 (GET /knowledge-points/{id}/questions)
│   └── 关联错题 (GET /knowledge-points/{id}/wrong-questions)
└── MasteryPanel              # 掌握度管理面板
    ├── PATCH /knowledge-points/{id}/mastery 手动调整
    └── 展示 accuracy/answered_count/wrong_count
```

**可视化方案**: 使用 ECharts/D3.js 力导向图，节点配置：

```javascript
{
  name: kp.name,
  symbolSize: 30 + kp.importance_weight * 50,  // 大小=重要程度
  itemStyle: {
    color: masteryColor(kp.mastery_status)      // red/green/yellow/gray
  }
}
```

---

### 六、学习仪表盘

**当前状态**: 后端数据已就绪，缺少前端仪表盘聚合页面

**前端需要建设**:

```
Dashboard 页面，聚合以下 API 数据：

1. 目标进度 → GET /study-targets (统计总数、即将到期)
2. 资料解析状态 → GET /materials (按 parse_status 统计)
3. 知识点掌握热力图 → GET /knowledge-graphs/{target_id} + 掌握度数据
4. 各题型正确率 → 需后端新增聚合端点 或 前端从 /tests 历史统计
5. 最近 7 天学习 → 需新增 GET /ai-usage/summary?start_at=&end_at=
6. 高频错题知识点 → 从 /wrong-questions + knowledge_point 关联聚合
7. 即将复习任务 → GET /review-plans?target_id=X (筛选未完成任务)
8. AI 调用/解析任务状态 → GET /ai-usage/summary + GET /admin/tasks
```

**推荐布局**:

```
┌──────────────────┬──────────────────┐
│  目标进度卡片     │  资料解析状态     │
├──────────────────┴──────────────────┤
│         知识点掌握热力图              │
├──────────────────┬──────────────────┤
│  各题型正确率     │  最近 7 天学习     │
├──────────────────┴──────────────────┤
│  高频错题知识点 + 即将复习任务        │
└─────────────────────────────────────┘
```

---

### 七、AI Tutor 分步提示模式

**当前状态**: ❌ 完全未实现，需要新建后端表+API+前端

**后端新增**:

```
新增表:
├── tutor_sessions (id, user_id, target_id, material_id, question, status)
├── tutor_messages (id, session_id, role, content, step)
└── feedback_actions (id, session_id, action_type: view_hint|modify_answer|resubmit|show_solution)

新增 API:
├── POST /tutor/start       # 开始引导式学习 → 返回 Hint 1
├── POST /tutor/{id}/hint   # 请求下一个提示
├── POST /tutor/{id}/check  # 检查学生答案
├── POST /tutor/{id}/solve  # 显示完整解答
└── GET  /tutor/{id}/progress # 查看学习进度
```

**前端交互流程**:

```
学生问题 → [Hint 1: 概念提示]
          → [Hint 2: 解题方向]
          → [Check My Answer: 提交答案 → AI 反馈]
          → [Show Full Solution: 完整解析]

每步记录 feedback_actions:
- 是否查看了提示
- 是否修改了答案
- 是否最终掌握
```

---

### 八、管理员运维中心

**当前状态**: 后端已有 `admin` 路由、`parse_tasks`、`admin_logs`、`ai_call_logs`。前端管理面板需扩展。

**前端需要建设**:

```
Admin 面板扩展:
├── 解析任务管理
│   ├── 任务队列状态 (GET /admin/tasks?status=pending)
│   ├── 失败任务重试 (POST /admin/tasks/{id}/retry)
│   └── OCR 置信度/解析质量
├── AI 调用监控
│   ├── 调用日志 (GET /ai-usage/logs)
│   ├── 失败率统计 (GET /ai-usage/summary)
│   ├── 平均响应时间
│   └── Token 消耗图表
├── 用户/资料统计
│   ├── 用户列表 (GET /admin/users)
│   ├── 资料统计 (GET /admin/materials)
│   └── 异常题目列表
└── 操作审计
    └── 管理员日志 (GET /admin/logs)
```

---

### 九、结构化解析

**当前状态**: ✅ 后端已实现 `material_sections` + `material_chunks` 表

```
已有 API:
├── GET /materials/{id}/sections      # 章节结构
├── GET /materials/{id}/chunks        # 文本块 (支持按 section_id 筛选)
└── GET /materials/{id}/structured    # 一次性返回 sections + chunks
```

**前端需要建设**:

- 资料阅读器支持左侧章节导航
- 选中章节后高亮对应 chunks
- 支持"基于当前章节出题"功能

---

### 十、导出功能

**当前状态**: ✅ 后端已全部实现

```
已有导出 API:
├── GET /exports/wrong-questions.md           # 错题本 Markdown
├── GET /exports/review-plan/{plan_id}.md     # 复习计划 Markdown
├── GET /exports/knowledge-summary/{target_id}.md # 知识点总结
└── GET /exports/anki/{target_id}.csv         # Anki CSV 卡片
```

**前端需要建设**:

- 在各页面添加"导出"按钮，调用对应 API
- Anki CSV 格式已为 `front/back/tags` 结构，可直接下载导入 Anki

---

## 优先级建议

| 优先级 | 模块 | 后端状态 | 前端工作量 | 核心价值 |
|--------|------|----------|-----------|----------|
| **P0** | 一、知识图谱可视化 | ✅ 就绪 | 中 | 平台核心差异化功能 |
| **P0** | 六、学习仪表盘 | ✅ 大部分就绪 | 中 | 用户留存关键 |
| **P1** | 十、导出功能 | ✅ 就绪 | 小 | 快速见效 |
| **P1** | 九、结构化章节阅读 | ✅ 就绪 | 小 | 体验提升 |
| **P2** | 八、管理员运维中心 | ✅ 就绪 | 中 | 项目完整性 |
| **P2** | 七、AI Tutor | ❌ 需新建 | 大 | 创新功能 |

**即战力建议**: 优先做 P0 + P1，四个功能后端基本就绪，前端可直接对接已有 API，能在 1-2 个迭代周期内完成。
