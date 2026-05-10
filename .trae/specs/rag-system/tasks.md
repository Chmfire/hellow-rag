# RAG System Implementation Tasks

## 任务分解

### T1: 项目初始化与环境搭建
- [x] 初始化 Git 仓库
- [x] 配置 .gitignore（排除 .env、*.backup、.kiro/、.trae/ 等）
- [x] 编写 .env.example 模板
- [x] 编写 start-project.sh 自动化启动脚本
- [x] 配置 Docker Compose（Redis、Milvus、PostgreSQL、MinIO、Attu）

### T2: 数据库设计
- [x] PostgreSQL 表结构（users、kb、documents、chunks、conversations、messages、jobs）
- [x] pg_client 连接封装（psycopg3 连接池）
- [x] Repository 层封装（base_repository + 各业务 repository）
- [x] init_db 数据库初始化脚本

### T3: Milvus 向量数据库
- [x] Milvus Schema 设计（chunk_id、file_name、chunk_index、chunk_level、content、dense、sparse_bm25）
- [x] 中文分词器配置（enable_analyzer）
- [x] BM25 内置函数配置
- [x] HNSW 索引 + IP 距离度量
- [x] 向量检索 / 关键词检索 / 混合检索 API
- [x] group_by_field 分组搜索支持
- [x] image_dense 图片向量字段
- [x] parent_chunk_id 父子切片关联

### T4: Embedding 服务
- [x] DashScope text-embedding-v3 集成
- [x] 批量发送（batch_size=20，DashScope 单次最多 25 条）
- [x] L2 归一化 + IP 距离
- [x] 多模态 embedding（qwen3-vl-embedding）

### T5: 文档解析与分块
- [x] PDF 解析（PyPDF）
- [x] Markdown 解析
- [x] Word 解析
- [x] 表格解析（doc_image_parser + table_parser）
- [x] 分块策略（chunk_size=500, overlap=50）
- [x] 三级分块（Parent-Child Chunking）
- [x] 图片占位符生成（<<IMAGE:hex_id>>）

### T6: LLM 接入
- [x] DashScope Generation API（文本生成）
- [x] DashScope MultiModalConversation API（图文混合）
- [x] OpenAI 兼容接口封装
- [x] 消息格式双向转换（DashScope ↔ OpenAI）
- [x] LLM 模型配置（qwen-plus / qwen-turbo）

### T7: LangGraph 工作流
- [x] StateGraph 定义（KnowledgeState）
- [x] query_rewrite 节点（指代消解 + 规范化）
- [x] query_classify 节点（启发式 + LLM 双层分类）
- [x] determine_retrieval_strategy 节点（动态参数决策）
- [x] kg_query_route 节点（图谱深度决策）
- [x] graph_retrieve 节点（图谱检索 + 2s 超时）
- [x] single_doc_retrieve 节点（单文档检索）
- [x] multi_doc_retrieve 节点（多文档检索 + group_by）
- [x] multimodal_retrieve 节点（图片向量检索）
- [x] filter_chunks 节点（score 阈值过滤）
- [x] select_top_k_chunks 节点（Rerank 重排）
- [x] generate_answer 节点（LLM 生成 + 置信度计算）
- [x] hallucination_check 节点（LLM + Jaccard 双层检测）
- [x] check_quality 节点（置信度门禁）
- [x] finalize_metrics 节点（指标汇总）
- [x] 条件分支路由（single/multi doc）
- [x] 并行执行（图谱 + 向量）
- [x] 中断恢复（interrupt_before generate_answer）

### T8: Rerank 服务
- [x] Cross-Encoder Rerank API 封装
- [x] 自动降级机制（API 失败回退至原始排序）
- [x] 超时控制（15s）
- [x] Rerank 配置（模型、地址、API Key）

### T9: 幻觉检测
- [x] LLM 语义级检测（逐句声明分析）
- [x] 结构化 JSON 输出（claims/supported/confidence/source_ids）
- [x] 引用溯源（自动生成 [1][2][3] 编号）
- [x] Jaccard 降级方案
- [x] 温度参数 0.1（一致性控制）

### T10: SSE 流式输出
- [x] SSE 事件流（data: / event:）
- [x] 断点续传（stream_resume_service）
- [x] 流式中断恢复（precomputed_answer 机制）
- [x] 首字延迟优化（< 200ms）
- [x] 流式模式关闭幻觉检测

### T11: MCP Server
- [x] mcp_server.py 实现
- [x] mcp_config.json 配置
- [x] 工具暴露（知识库检索、文档上传）

### T12: 认证与权限
- [x] JWT 认证（HS256）
- [x] PBKDF2 密码哈希（310000 轮）
- [x] 管理员邀请码（ADMIN_INVITE_CODE）
- [x] 知识库 owner 字段 + collection 隔离

### T13: 缓存系统
- [x] Redis 客户端封装
- [x] 混合检索结果缓存
- [x] TTL 5 分钟
- [x] 按 collection 批量失效（delete_pattern）

### T14: 存储系统
- [x] MinIO 存储（base_storage → minio_storage）
- [x] 本地存储（local_storage）
- [x] 阿里云 OSS（oss_storage）
- [x] 预签名 URL 生成

### T15: API 开发
- [x] FastAPI 应用搭建
- [x] v1/knowledge.py（知识库问答）
- [x] v1/documents.py（文档管理）
- [x] v1/chunks.py（分块管理）
- [x] v1/conversations.py（对话管理）
- [x] v1/jobs.py（任务管理）
- [x] v1/auth.py（认证）
- [x] v1/admin/（管理接口）
- [x] v1/system.py（系统配置）
- [x] v1/knowledge_graph.py（知识图谱）
- [x] v1/storage.py（存储管理）
- [x] OpenAPI 文档（/docs）

### T16: 前端开发
- [x] Vue 3 + Vite 初始化
- [x] Vue Router + Pinia
- [x] 知识库问答组件（SimpleChat）
- [x] 文档管理组件（DocList、DocUpload、DocSearch）
- [x] 分块编辑组件（ChunkEditorPanel）
- [x] 知识图谱可视化（KnowledgeGraphPanel）
- [x] 管理面板（AdminPanel）
- [x] 登录/注册页面
- [x] API 服务封装（api.js、docApi.js）
- [x] 暗色主题

### T17: 测试
- [x] pytest 配置（pytest.ini）
- [x] 单元测试（test_auth_service、test_cache、test_chunk_splitter）
- [x] 集成测试（test_api_auth）
- [x] 测试工具（test_table_parser）
- [x] conftest.py fixtures

### T18: 文档
- [x] .env.example 完整配置模板
- [x] start-project.sh 启动脚本
- [x] STORAGE_GUIDE.md 存储指南
- [x] STREAMING_PORTING_GUIDE.md 流式移植指南
- [x] HOW_TO_ADD_NEW_NODE.md 节点添加指南
- [x] 面试准备文档（深度问答、项目经历优化）
