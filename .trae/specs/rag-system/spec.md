# RAG System Project Spec

## 项目概述

基于 LangGraph + Milvus + PostgreSQL 的企业级 RAG（检索增强生成）知识库平台，集成知识图谱、多模态检索、MCP 协议、SSE 流式输出等能力，支持知识库问答、多轮对话、自动化报告生成。

## 项目起源

本项目基于开源 Knowledge Table 项目二次开发。原始项目仅提供基础的表格提取和知识图谱构建功能，无完整 RAG pipeline。在此基础上从零搭建了完整的 AI 问答系统。

## 架构演进

### 第一阶段：基础 RAG Pipeline

从零搭建端到端检索增强生成链路：
- LangGraph StateGraph 多节点 workflow
- ETL 数据清洗 + 文档分块（Chunking）
- Embedding 向量化（DashScope text-embedding-v3）
- Milvus 向量检索 + BM25 关键词混合检索
- LLM 答案生成（DashScope qwen-plus）

### 第二阶段：检索精度优化

- 引入 Cross-Encoder Rerank 模型重排序
- 实现启发式意图识别（单/多文档分类）
- 多策略查询扩展（Step-Back / HyDE / Complex）
- Milvus group_by_field 分组去重（多文档场景）
- Recall@5 从 68% 提升至 92%

### 第三阶段：Agent 工作流增强

- 知识图谱融合检索（WhyHow Knowledge Table 本地部署）
- 三级分块机制（Parent-Child Chunking）
- 多模态知识库支持（图片占位符 + 预签名 URL）
- LLM 语义级幻觉检测 + 引用溯源
- 可解释置信度模型（检索相关度 40% + 内容重叠度 60%）

### 第四阶段：生产级能力

- SSE 流式输出 + 断点续传
- OpenAI 兼容接口（DashScope ↔ OpenAI 消息格式双向转换）
- Redis 混合缓存优化（P99 延迟 1.2s → 300ms）
- MCP Server 集成（Model Context Protocol）
- JWT 认证 + 知识库权限隔离
- LangGraph 状态持久化（AsyncPostgresSaver）

## 核心功能模块

### 1. Agent 工作流

- **13 节点 LangGraph workflow**：query_rewrite → query_classify → determine_retrieval_strategy → kg_query_route → graph_retrieve → {single/multi}_doc_retrieve → filter_chunks → select_top_k_chunks → generate_answer → hallucination_check → check_quality → finalize_metrics
- **条件分支路由**：单文档/多文档动态切换
- **并行执行**：知识图谱检索与向量检索并发
- **流式中断恢复**：interrupt_before 实现生成前暂停推流
- **状态持久化**：psycopg3 + AsyncPostgresSaver 支持多轮对话中断-恢复

### 2. 检索系统

- **混合检索**：BM25 关键词 + 1024 维稠密向量
- **RRF 融合**：RRFRanker 双路/三路召回融合
- **动态策略**：根据 query 长度/类型动态调整 hybrid_alpha、rrf_k、top_k
- **重排序**：Cross-Encoder Rerank + 自动降级机制
- **多文档去重**：Milvus group_by_field 分组搜索

### 3. 多模态支持

- **图片占位符**：检索时剥离避免污染向量/BM25 索引
- **图片向量检索**：qwen3-vl-embedding 生成 1024 维图片向量
- **三路 ANN + RRF**：文字 dense + BM25 + 图片 dense 融合
- **预签名 URL**：图片占位符自动转换为 MinIO/OSS 可访问链接
- **Prompt 分层**：纯文本/图片/多模态/向量+图谱四种模板

### 4. 幻觉抑制

- **LLM 语义级检测**：逐句分析声明，输出结构化 JSON（claims/supported/confidence/source_ids）
- **Jaccard 降级**：LLM 异常时关键词重叠匹配（阈值 0.15）
- **引用溯源**：自动生成来源编号 [1][2][3]
- **置信度模型**：检索相关度 40% + 内容 Jaccard 重叠度 60%

### 5. 性能优化

- **Redis 缓存**：混合检索结果缓存（TTL 5 分钟）
- **SSE 流式**：首字延迟 < 200ms，支持断点续传
- **启发式意图识别**：60%+ 场景快速路径，LLM 调用率 100% → 40%
- **流式关闭幻觉检测**：减少额外 LLM 调用
- **P99 延迟**：1.2s → 300ms（降低 75%）
- **Token 消耗**：单次问答降低 35%

### 6. 知识图谱

- **WhyHow Knowledge Table**：本地部署知识图谱服务
- **图谱检索**：节点/三元组检索 + chunk 回填
- **统一打分**：图谱相关度 65% + 时效性衰减 35%
- **图谱-向量融合**：图谱检索结果与向量检索结果合并重排

### 7. MCP Server

- **Model Context Protocol**：Anthropic 提出的 Agent 通信标准
- **工具暴露**：知识库检索、文档上传等能力
- **配置**：mcp_config.json 定义 MCP 端点

### 8. 前端

- **Vue 3**：单文件组件 + Vue Router + Pinia
- **功能模块**：知识库问答、文档管理、分块编辑、知识图谱可视化、管理面板
- **API 集成**：FastAPI RESTful API + SSE 流式响应
- **暗色主题**：自定义 CSS 主题系统

### 9. 认证与权限

- **JWT 认证**：HS256 算法，PBKDF2 密码哈希（310000 轮）
- **管理员邀请码**：ADMIN_INVITE_CODE 控制管理员注册
- **知识库隔离**：每个知识库独立 collection + owner 字段

### 10. 存储系统

- **MinIO**：对象存储（文档上传、图片存储）
- **PostgreSQL**：业务元数据（用户、知识库、文档、分块、对话历史）
- **Milvus**：向量数据库（BM25 + HNSW 索引）
- **Redis**：缓存层（检索结果、会话状态）

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | Python / FastAPI |
| AI 框架 | LangGraph / LangChain |
| 向量数据库 | Milvus（BM25 + HNSW） |
| 关系型数据库 | PostgreSQL（psycopg3） |
| 缓存 | Redis |
| 对象存储 | MinIO / 阿里云 OSS |
| LLM | DashScope（qwen-plus / qwen-turbo / qwen3-vl） |
| Embedding | text-embedding-v3 |
| Rerank | Cross-Encoder |
| 前端 | Vue 3 / TypeScript / Vite |
| 容器 | Docker / Docker Compose |
| 协议 | MCP（Model Context Protocol） |
| 认证 | JWT（HS256） |

## 项目指标

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| Recall@5 | 68% | 92% |
| P99 延迟 | 1.2s | 300ms |
| Token 消耗 | - | -35% |
| 答案可验证性 | - | 95%+ |
| 任务自主完成率 | - | 85%+ |
