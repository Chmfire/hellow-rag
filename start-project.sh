#!/bin/bash

# =============================================================================
# 自动化启动脚本
# 用于快速启动当前项目，包括前端、后端、容器服务和 MCP Server
# =============================================================================

# 颜色定义
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
NC="\033[0m" # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_DIR="$PROJECT_ROOT/logs"
PID_DIR="$PROJECT_ROOT/.pids"
ENV_FILE="$PROJECT_ROOT/.env"

# 创建必要的目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# =============================================================================
# 帮助信息
# =============================================================================
show_help() {
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}           RAG 知识库系统 - 项目启动脚本               ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e ""
    echo -e "用法: ./start-project.sh [选项]"
    echo -e ""
    echo -e "${CYAN}启动选项:${NC}"
    echo -e "  --all            启动所有服务（默认）"
    echo -e "  --frontend       仅启动前端服务"
    echo -e "  --backend        仅启动后端服务"
    echo -e "  --mcp            仅启动 MCP Server"
    echo -e "  --containers     仅启动容器服务（PostgreSQL、Milvus等）"
    echo -e ""
    echo -e "${CYAN}管理选项:${NC}"
    echo -e "  --stop           停止所有服务"
    echo -e "  --stop-backend   仅停止后端"
    echo -e "  --stop-mcp       仅停止 MCP Server"
    echo -e "  --restart        重启所有服务"
    echo -e "  --status         查看服务状态"
    echo -e "  --logs [服务]    查看日志 (frontend|backend|mcp|containers)"
    echo -e ""
    echo -e "${CYAN}初始化选项:${NC}"
    echo -e "  --install        安装依赖（前端和后端）"
    echo -e "  --build          构建前端项目"
    echo -e "  --init-db        初始化数据库"
    echo -e "  --clean          清理构建文件和缓存"
    echo -e ""
    echo -e "${CYAN}运行模式:${NC}"
    echo -e "  --daemon         后台运行（默认前台）"
    echo -e ""
    echo -e "${CYAN}其他选项:${NC}"
    echo -e "  --help, -h       显示此帮助信息"
    echo -e ""
    echo -e "${CYAN}示例:${NC}"
    echo -e "  ./start-project.sh --all              启动所有服务"
    echo -e "  ./start-project.sh --all --daemon     后台启动所有服务"
    echo -e "  ./start-project.sh --install --all    安装依赖并启动"
    echo -e "  ./start-project.sh --stop             停止所有服务"
    echo -e "  ./start-project.sh --restart          重启所有服务"
    echo -e "  ./start-project.sh --status           查看服务状态"
    echo -e "  ./start-project.sh --logs backend     查看后端日志"
    echo -e ""
}

# =============================================================================
# 工具函数
# =============================================================================

# 打印标题
print_header() {
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  $1${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
}

# 打印成功
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 打印警告
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 打印错误
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 打印信息
print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "命令 '$1' 不存在，请先安装"
        return 1
    fi
    return 0
}

# 检查端口是否被占用
check_port() {
    local port=$1
    local service_name=$2
    if lsof -i :$port > /dev/null 2>&1; then
        print_warning "端口 $port 已被占用 ($service_name)"
        lsof -i :$port | grep LISTEN
        return 0
    fi
    return 1
}

# 释放端口（杀死占用进程）
kill_port_occupier() {
    local port=$1
    local service_name=$2
    if check_port "$port" "$service_name"; then
        echo -e "${YELLOW}是否释放端口？[y/N]${NC}"
        read -t 5 -r answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            print_info "正在释放端口 $port..."
            lsof -ti :$port | xargs kill -9 2>/dev/null
            sleep 1
            print_success "端口 $port 已释放"
        else
            print_error "跳过端口释放，启动可能会失败"
        fi
    fi
}

# =============================================================================
# 环境检查
# =============================================================================

# 检查项目类型
check_project_type() {
    print_info "检查项目类型..."
    
    FRONTEND_TYPE="none"
    BACKEND_TYPE="none"
    MCP_AVAILABLE="no"
    CONTAINERS_AVAILABLE="no"
    
    # 检查前端项目
    if [ -f "$FRONTEND_DIR/package.json" ]; then
        print_success "前端项目: Vue.js"
        FRONTEND_TYPE="vue"
    else
        print_warning "前端项目未找到"
    fi
    
    # 检查后端项目
    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        print_success "后端项目: Python"
        BACKEND_TYPE="python"
    else
        print_warning "后端项目未找到"
    fi
    
    # 检查 MCP Server
    if [ -f "$BACKEND_DIR/app/mcp_server.py" ]; then
        print_success "MCP Server: 已配置"
        MCP_AVAILABLE="yes"
    else
        print_warning "MCP Server 未找到"
    fi
    
    # 检查容器配置
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        print_success "容器配置: Docker Compose"
        CONTAINERS_AVAILABLE="yes"
    else
        print_warning "容器配置未找到"
    fi
}

# 检查环境变量
check_env() {
    print_info "检查环境变量..."
    
    if [ ! -f "$ENV_FILE" ]; then
        print_warning ".env 文件不存在"
        if [ -f "$ENV_FILE.example" ]; then
            echo -e "${YELLOW}是否从 .env.example 创建 .env？[y/N]${NC}"
            read -t 10 -r answer
            if [[ "$answer" =~ ^[Yy]$ ]]; then
                cp "$ENV_FILE.example" "$ENV_FILE"
                print_success ".env 文件已创建"
                print_warning "请编辑 .env 文件并填写必要的配置"
                return 1
            else
                return 1
            fi
        else
            print_error "未找到 .env.example，请手动创建 .env 文件"
            return 1
        fi
    fi
    
    # 检查必要的环境变量
    local required_vars=("DATABASE_URL" "MILVUS_HOST" "MILVUS_PORT")
    local missing=0
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
            print_warning "环境变量 $var 未配置"
            missing=$((missing + 1))
        fi
    done
    
    if [ $missing -gt 0 ]; then
        print_warning "有 $missing 个必要的环境变量未配置"
        return 1
    fi
    
    print_success "环境变量检查通过"
    return 0
}

# =============================================================================
# 安装与初始化
# =============================================================================

# 安装前端依赖
install_frontend_deps() {
    if [ "$FRONTEND_TYPE" != "none" ]; then
        print_info "安装前端依赖..."
        cd "$FRONTEND_DIR" || { print_error "无法进入前端目录"; return 1; }
        npm install
        cd "$PROJECT_ROOT" || { print_error "无法返回项目根目录"; return 1; }
        print_success "前端依赖安装完成"
    fi
}

# 安装后端依赖
install_backend_deps() {
    if [ "$BACKEND_TYPE" != "none" ]; then
        print_info "安装后端依赖..."
        cd "$BACKEND_DIR" || { print_error "无法进入后端目录"; return 1; }
        
        # 检查是否有虚拟环境
        if [ ! -d "venv" ]; then
            print_info "创建 Python 虚拟环境..."
            python3 -m venv venv
        fi
        
        source venv/bin/activate
        pip install -r requirements.txt
        deactivate
        
        cd "$PROJECT_ROOT" || { print_error "无法返回项目根目录"; return 1; }
        print_success "后端依赖安装完成"
    fi
}

# 构建前端项目
build_frontend() {
    if [ "$FRONTEND_TYPE" != "none" ]; then
        print_info "构建前端项目..."
        cd "$FRONTEND_DIR" || { print_error "无法进入前端目录"; return 1; }
        npm run build
        cd "$PROJECT_ROOT" || { print_error "无法返回项目根目录"; return 1; }
        print_success "前端项目构建完成"
    fi
}

# 初始化数据库
init_db() {
    print_info "初始化数据库..."
    
    # 检查 PostgreSQL 是否可连接
    if ! check_postgres 15; then
        print_error "PostgreSQL 未启动，无法初始化数据库"
        return 1
    fi
    
    cd "$BACKEND_DIR" || { print_error "无法进入后端目录"; return 1; }
    
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    if [ -f "app/db/init_db.py" ]; then
        python -m app.db.init_db
        if [ $? -eq 0 ]; then
            print_success "数据库初始化完成"
        else
            print_error "数据库初始化失败"
        fi
    else
        print_warning "未找到数据库初始化脚本"
    fi
    
    if [ -d "venv" ]; then
        deactivate
    fi
    
    cd "$PROJECT_ROOT"
}

# 清理构建文件
clean() {
    print_info "清理构建文件和缓存..."
    
    # 清理前端
    if [ -d "$FRONTEND_DIR/dist" ]; then
        rm -rf "$FRONTEND_DIR/dist"
        print_success "清理前端 dist 目录"
    fi
    
    if [ -d "$FRONTEND_DIR/node_modules/.cache" ]; then
        rm -rf "$FRONTEND_DIR/node_modules/.cache"
        print_success "清理前端缓存"
    fi
    
    # 清理后端
    if [ -d "$BACKEND_DIR/__pycache__" ]; then
        rm -rf "$BACKEND_DIR/__pycache__"
        print_success "清理 Python 缓存"
    fi
    
    if [ -d "$BACKEND_DIR/.pytest_cache" ]; then
        rm -rf "$BACKEND_DIR/.pytest_cache"
        print_success "清理 pytest 缓存"
    fi
    
    # 清理日志
    if [ -d "$LOG_DIR" ]; then
        rm -rf "$LOG_DIR"/*
        print_success "清理日志"
    fi
    
    print_success "清理完成"
}

# =============================================================================
# 容器管理
# =============================================================================

# 启动容器服务
start_containers() {
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        print_info "启动容器服务..."
        cd "$PROJECT_ROOT" || { print_error "无法进入项目目录"; return 1; }
        
        # 检查 Docker 是否运行
        if ! docker info > /dev/null 2>&1; then
            print_error "Docker 未运行，请先启动 Docker"
            return 1
        fi
        
        docker-compose up -d
        
        if [ $? -eq 0 ]; then
            print_success "容器服务启动完成"
            echo -e "${YELLOW}服务地址:${NC}"
            echo -e "  - PostgreSQL: localhost:5432"
            echo -e "  - Milvus: localhost:19530"
            echo -e "  - MinIO: localhost:9005"
            echo -e "  - Attu (Milvus GUI): http://localhost:8080"
            echo -e "  - Redis: localhost:6379"
        else
            print_error "容器服务启动失败"
            return 1
        fi
    fi
}

# 停止容器服务
stop_containers() {
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        print_info "停止容器服务..."
        cd "$PROJECT_ROOT" || return 1
        docker-compose down
        print_success "容器服务已停止"
    fi
}

# 重启容器服务
restart_containers() {
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        print_info "重启容器服务..."
        cd "$PROJECT_ROOT" || return 1
        docker-compose restart
        print_success "容器服务已重启"
    fi
}

# 查看容器日志
logs_containers() {
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        cd "$PROJECT_ROOT" || return 1
        docker-compose logs -f "$@"
    fi
}

# 检查 PostgreSQL 是否可连接
check_postgres() {
    local max_retries=$1
    local retry_count=0
    
    print_info "检查 PostgreSQL 连接..."
    while [ $retry_count -lt $max_retries ]; do
        # 方法1: 使用 pg_isready
        if command -v pg_isready &> /dev/null; then
            if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
                print_success "PostgreSQL 已就绪"
                return 0
            fi
        fi
        
        # 方法2: 直接检查端口是否开放
        if (echo > /dev/tcp/localhost/5432) 2>/dev/null; then
            sleep 2
            print_success "PostgreSQL 已就绪"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        print_info "等待 PostgreSQL 启动... ($retry_count/$max_retries)"
        sleep 2
    done
    
    # 方法3: 使用 docker 检查容器状态
    if docker-compose ps | grep -q "kb-postgres.*Up"; then
        print_info "PostgreSQL 容器运行中（尝试直接连接）"
        sleep 3
        return 0
    fi
    
    return 1
}

# =============================================================================
# 服务管理
# =============================================================================

# 启动前端服务
start_frontend() {
    if [ "$FRONTEND_TYPE" != "none" ]; then
        # 检查端口
        if check_port 5173 "前端"; then
            print_warning "检测到前端服务已在运行"
            kill_port_occupier 5173 "前端"
        fi
        
        print_info "启动前端服务..."
        cd "$FRONTEND_DIR" || { print_error "无法进入前端目录"; return 1; }
        
        if [ "$DAEMON_MODE" = "true" ]; then
            nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
            echo $! > "$PID_DIR/frontend.pid"
            print_success "前端服务已后台启动 (PID: $(cat "$PID_DIR/frontend.pid"))"
            print_info "日志: $LOG_DIR/frontend.log"
        else
            npm run dev
        fi
    fi
}

# 启动后端服务
start_backend() {
    if [ "$BACKEND_TYPE" != "none" ]; then
        # 检查端口
        if check_port 8000 "后端"; then
            print_warning "检测到后端服务已在运行"
            kill_port_occupier 8000 "后端"
        fi
        
        # 检查 PostgreSQL
        if ! check_postgres 15; then
            print_error "PostgreSQL 未启动或无法连接"
            print_info "请先启动容器服务: ./start-project.sh --containers"
            return 1
        fi
        
        print_info "启动后端服务..."
        cd "$BACKEND_DIR" || { print_error "无法进入后端目录"; return 1; }
        
        # 激活虚拟环境
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        
        if [ "$DAEMON_MODE" = "true" ]; then
            nohup uvicorn main:app --reload > "$LOG_DIR/backend.log" 2>&1 &
            echo $! > "$PID_DIR/backend.pid"
            print_success "后端服务已后台启动 (PID: $(cat "$PID_DIR/backend.pid"))"
            print_info "日志: $LOG_DIR/backend.log"
        else
            uvicorn main:app --reload
        fi
    fi
}

# 启动 MCP Server
start_mcp() {
    if [ "$MCP_AVAILABLE" = "yes" ]; then
        # 检查端口
        if check_port 8001 "MCP Server"; then
            print_warning "检测到 MCP Server 已在运行"
            kill_port_occupier 8001 "MCP Server"
        fi
        
        print_info "启动 MCP Server..."
        cd "$BACKEND_DIR" || { print_error "无法进入后端目录"; return 1; }
        
        # 激活虚拟环境
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        
        if [ "$DAEMON_MODE" = "true" ]; then
            nohup python -m app.mcp_server > "$LOG_DIR/mcp.log" 2>&1 &
            echo $! > "$PID_DIR/mcp.pid"
            print_success "MCP Server 已后台启动 (PID: $(cat "$PID_DIR/mcp.pid"))"
            print_info "日志: $LOG_DIR/mcp.log"
        else
            python -m app.mcp_server
        fi
    fi
}

# 停止前端服务
stop_frontend() {
    if [ -f "$PID_DIR/frontend.pid" ]; then
        local pid=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_info "停止前端服务 (PID: $pid)..."
            kill "$pid"
            rm -f "$PID_DIR/frontend.pid"
            print_success "前端服务已停止"
        else
            print_warning "前端服务未运行"
            rm -f "$PID_DIR/frontend.pid"
        fi
    else
        print_info "前端服务 PID 文件不存在"
        # 尝试通过端口查找并停止
        if check_port 5173 "前端"; then
            print_info "通过端口 5173 停止前端服务..."
            lsof -ti :5173 | xargs kill -9 2>/dev/null
            print_success "前端服务已停止"
        fi
    fi
}

# 停止后端服务
stop_backend() {
    if [ -f "$PID_DIR/backend.pid" ]; then
        local pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_info "停止后端服务 (PID: $pid)..."
            kill "$pid"
            rm -f "$PID_DIR/backend.pid"
            print_success "后端服务已停止"
        else
            print_warning "后端服务未运行"
            rm -f "$PID_DIR/backend.pid"
        fi
    else
        print_info "后端服务 PID 文件不存在"
        # 尝试通过端口查找并停止
        if check_port 8000 "后端"; then
            print_info "通过端口 8000 停止后端服务..."
            lsof -ti :8000 | xargs kill -9 2>/dev/null
            print_success "后端服务已停止"
        fi
    fi
}

# 停止 MCP Server
stop_mcp() {
    if [ -f "$PID_DIR/mcp.pid" ]; then
        local pid=$(cat "$PID_DIR/mcp.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_info "停止 MCP Server (PID: $pid)..."
            kill "$pid"
            rm -f "$PID_DIR/mcp.pid"
            print_success "MCP Server 已停止"
        else
            print_warning "MCP Server 未运行"
            rm -f "$PID_DIR/mcp.pid"
        fi
    else
        print_info "MCP Server PID 文件不存在"
        # 尝试通过端口查找并停止
        if check_port 8001 "MCP Server"; then
            print_info "通过端口 8001 停止 MCP Server..."
            lsof -ti :8001 | xargs kill -9 2>/dev/null
            print_success "MCP Server 已停止"
        fi
    fi
}

# =============================================================================
# 状态与日志
# =============================================================================

# 查看所有服务状态
show_status() {
    print_header "服务状态"
    
    # 前端状态
    if [ -f "$PID_DIR/frontend.pid" ]; then
        local pid=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_success "前端服务运行中 (PID: $pid)"
        else
            print_error "前端服务已停止 (PID 文件存在但进程不存在)"
        fi
    else
        print_error "前端服务未运行"
    fi
    
    # 后端状态
    if [ -f "$PID_DIR/backend.pid" ]; then
        local pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_success "后端服务运行中 (PID: $pid)"
        else
            print_error "后端服务已停止 (PID 文件存在但进程不存在)"
        fi
    else
        print_error "后端服务未运行"
    fi
    
    # MCP 状态
    if [ -f "$PID_DIR/mcp.pid" ]; then
        local pid=$(cat "$PID_DIR/mcp.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_success "MCP Server 运行中 (PID: $pid)"
        else
            print_error "MCP Server 已停止 (PID 文件存在但进程不存在)"
        fi
    else
        print_error "MCP Server 未运行"
    fi
    
    # 容器状态
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        if docker-compose ps 2>/dev/null | grep -q "Up"; then
            print_success "容器服务运行中"
            docker-compose ps 2>/dev/null | grep "Up"
        else
            print_error "容器服务未运行"
        fi
    else
        print_warning "容器服务不可用"
    fi
    
    # 端口状态
    echo -e ""
    echo -e "${CYAN}端口状态:${NC}"
    echo -e "  - 前端: $(check_port 5173 "前端" && echo "已占用" || echo "未占用")"
    echo -e "  - 后端: $(check_port 8000 "后端" && echo "已占用" || echo "未占用")"
    echo -e "  - MCP:  $(check_port 8001 "MCP" && echo "已占用" || echo "未占用")"
    echo -e "  - PostgreSQL: $(check_port 5432 "PostgreSQL" && echo "已占用" || echo "未占用")"
    echo -e "  - Milvus: $(check_port 19530 "Milvus" && echo "已占用" || echo "未占用")"
    echo -e "  - Redis: $(check_port 6379 "Redis" && echo "已占用" || echo "未占用")"
}

# 查看日志
show_logs() {
    local service=$1
    
    case "$service" in
        frontend)
            if [ -f "$LOG_DIR/frontend.log" ]; then
                tail -f "$LOG_DIR/frontend.log"
            else
                print_warning "前端日志不存在"
            fi
            ;;
        backend)
            if [ -f "$LOG_DIR/backend.log" ]; then
                tail -f "$LOG_DIR/backend.log"
            else
                print_warning "后端日志不存在"
            fi
            ;;
        mcp)
            if [ -f "$LOG_DIR/mcp.log" ]; then
                tail -f "$LOG_DIR/mcp.log"
            else
                print_warning "MCP Server 日志不存在"
            fi
            ;;
        containers)
            logs_containers
            ;;
        *)
            print_error "未知的服务: $service"
            ;;
    esac
}

# =============================================================================
# 主函数
# =============================================================================

# 停止所有服务
stop_all() {
    print_header "停止所有服务"
    stop_frontend
    stop_backend
    stop_mcp
    stop_containers
    print_success "所有服务已停止"
}

# 启动所有服务
start_all() {
    print_header "启动所有服务"
    
    # 启动容器
    start_containers
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        print_info "等待容器服务启动..."
        sleep 10
    fi
    
    # 启动后端
    start_backend
    sleep 2
    
    # 启动 MCP Server（如果可用）
    if [ "$MCP_AVAILABLE" = "yes" ]; then
        start_mcp
        sleep 1
    fi
    
    # 启动前端
    start_frontend
    sleep 1
    
    print_header "启动完成"
    echo -e ""
    echo -e "${GREEN}服务地址:${NC}"
    echo -e "  - 前端: ${CYAN}http://localhost:5173${NC}"
    echo -e "  - 后端: ${CYAN}http://localhost:8000${NC}"
    echo -e "  - 后端文档: ${CYAN}http://localhost:8000/docs${NC}"
    if [ "$MCP_AVAILABLE" = "yes" ]; then
        echo -e "  - MCP Server: ${CYAN}stdio 模式${NC}"
    fi
    echo -e ""
    if [ "$DAEMON_MODE" = "true" ]; then
        print_success "所有服务已后台启动"
        print_info "使用 './start-project.sh --status' 查看状态"
        print_info "使用 './start-project.sh --stop' 停止服务"
    fi
}

# 重启所有服务
restart_all() {
    print_header "重启所有服务"
    stop_all
    sleep 2
    start_all
}

# 主函数
main() {
    # 默认选项
    START_ALL=false
    START_FRONTEND=false
    START_BACKEND=false
    START_MCP=false
    START_CONTAINERS=false
    STOP_ALL=false
    STOP_BACKEND_ONLY=false
    STOP_MCP_ONLY=false
    SHOW_STATUS=false
    INSTALL_DEPS=false
    BUILD_FRONTEND=false
    INIT_DB=false
    CLEAN=false
    RESTART_ALL=false
    DAEMON_MODE=false
    SHOW_LOGS=false
    LOG_SERVICE=""
    
    # 解析命令行参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --all)
                START_ALL=true
                ;;
            --frontend)
                START_FRONTEND=true
                ;;
            --backend)
                START_BACKEND=true
                ;;
            --mcp)
                START_MCP=true
                ;;
            --containers)
                START_CONTAINERS=true
                ;;
            --stop)
                STOP_ALL=true
                ;;
            --stop-backend)
                STOP_BACKEND_ONLY=true
                ;;
            --stop-mcp)
                STOP_MCP_ONLY=true
                ;;
            --restart)
                RESTART_ALL=true
                ;;
            --status)
                SHOW_STATUS=true
                ;;
            --logs)
                SHOW_LOGS=true
                shift
                LOG_SERVICE="${1:-backend}"
                ;;
            --install)
                INSTALL_DEPS=true
                ;;
            --build)
                BUILD_FRONTEND=true
                ;;
            --init-db)
                INIT_DB=true
                ;;
            --clean)
                CLEAN=true
                ;;
            --daemon)
                DAEMON_MODE=true
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done
    
    # 如果没有任何选项，默认启动所有
    if [ "$START_ALL" = false ] && [ "$START_FRONTEND" = false ] && \
       [ "$START_BACKEND" = false ] && [ "$START_CONTAINERS" = false ] && \
       [ "$STOP_ALL" = false ] && [ "$SHOW_STATUS" = false ] && \
       [ "$START_MCP" = false ] && [ "$RESTART_ALL" = false ] && \
       [ "$SHOW_LOGS" = false ]; then
        START_ALL=true
    fi
    
    # 检查项目类型
    check_project_type
    
    # 检查必要的命令
    if [ "$FRONTEND_TYPE" != "none" ]; then
        check_command "npm" || exit 1
    fi
    
    if [ "$BACKEND_TYPE" != "none" ]; then
        check_command "uvicorn" || { print_error "请运行 'pip install uvicorn'"; exit 1; }
    fi
    
    if [ "$CONTAINERS_AVAILABLE" = "yes" ]; then
        check_command "docker-compose" || check_command "docker" || { print_error "请安装 Docker 和 Docker Compose"; exit 1; }
    fi
    
    # 执行操作
    if [ "$SHOW_STATUS" = true ]; then
        show_status
        exit 0
    fi
    
    if [ "$SHOW_LOGS" = true ]; then
        show_logs "$LOG_SERVICE"
        exit 0
    fi
    
    if [ "$STOP_ALL" = true ]; then
        stop_all
        exit 0
    fi
    
    if [ "$STOP_BACKEND_ONLY" = true ]; then
        stop_backend
        exit 0
    fi
    
    if [ "$STOP_MCP_ONLY" = true ]; then
        stop_mcp
        exit 0
    fi
    
    if [ "$RESTART_ALL" = true ]; then
        restart_all
        exit 0
    fi
    
    if [ "$CLEAN" = true ]; then
        clean
        exit 0
    fi
    
    # 安装依赖
    if [ "$INSTALL_DEPS" = true ]; then
        install_frontend_deps
        install_backend_deps
    fi
    
    # 检查环境
    check_env
    
    # 构建前端
    if [ "$BUILD_FRONTEND" = true ]; then
        build_frontend
    fi
    
    # 初始化数据库
    if [ "$INIT_DB" = true ]; then
        init_db
    fi
    
    # 启动服务
    if [ "$START_ALL" = true ]; then
        start_all
    elif [ "$START_CONTAINERS" = true ]; then
        start_containers
    elif [ "$START_FRONTEND" = true ]; then
        start_frontend
    elif [ "$START_BACKEND" = true ]; then
        start_backend
    elif [ "$START_MCP" = true ]; then
        start_mcp
    fi
}

# 运行主函数
main "$@"
