# 📈 Kenne Index SaaS
> **面向加密资产长期配置的专业 DCA 信号与自动化执行系统**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS_v4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Stripe](https://img.shields.io/badge/Stripe-635BFF?style=for-the-badge&logo=stripe&logoColor=white)](https://stripe.com)

Kenne Index SaaS 是一个端到端的智能加密资产定投（DCA）信号与自动化执行工作台。项目已由原本的单页量化工具升级为 **“公开官网 + SaaS 用户后台”** 的分层微服务架构，包含仪表盘、定投执行、审计历史、系统设置、Stripe 订阅、自定义回测等六大核心功能版块。

> [!WARNING]
> **风险提示**
> 本项目仅提供量化信号计算、预算管理纪律、历史回测和模拟/实盘执行工具。项目所载所有内容均不构成任何投资建议，不承诺任何形式的资产收益。加密货币资产波动剧烈，在接入实盘前，请务必进行充分的回测，并确认交易所 API 权限、最小订单额度以及个人的风险承受能力。

本轮上线化改造同步完成了 Figma 设计稿重构，前端视觉基调改为面向金融 SaaS 的低噪声深色工作台，弱化营销式装饰，强化资产状态、执行前检查、审计留痕和风险控制优先级。

* Figma 设计稿：[Kenne Index SaaS Dashboard](https://www.figma.com/design/9NhYeetb7rsbcQtrriBepw?node-id=1-2)
* Figma 上线 QA 补充画板：`Release QA / Public Resilience Update / 2026-06-20`，记录公开行情页与邀请分享页的局部错误态、无全局 toast 干扰策略和生产预览验证结果。

---

## 🏗️ 系统架构图

系统的请求流和数据流向如下所示：

```mermaid
graph TD
    User([用户/浏览器]) -->|HTTPS| Frontend[React 前端工作台 (Port 5173)]
    Frontend -->|API 代理 /api/v1| Vite[Vite Dev Server (Port 5173)]
    Vite -->|反向代理| Backend[FastAPI 后端服务 (Port 8001)]
    Backend -->|Async SQLAlchemy| DB[(PostgreSQL 主库 / 租户库)]
    Backend -->|Lifespan asyncio| Tasks[自动化定时任务调度]
    Backend -->|SMTP client| Email[邮件通知 (smtplib)]
    Backend -->|ccxt / HTTP| Exchange[加密交易所 API]
    Backend -->|HTTPS| Stripe[Stripe Checkout & Webhook]
```

---

## 📂 项目目录审计与结构说明

经过对工作目录的审计整理，项目核心结构如下：

```text
📂 E:\AHR999-Optimized-Kenne-Index-main
├── 📂 backend                  # 后端服务目录 (FastAPI + SQLAlchemy)
│   ├── 📂 alembic             # 数据库迁移脚本目录
│   ├── 📂 app                 # FastAPI 业务源码目录
│   │   ├── 📂 api             # API 路由和请求响应逻辑层
│   │   ├── 📂 core            # 核心配置、数据库连接、安全性中间件
│   │   ├── 📂 engine          # 量化策略算法引擎 (DCA 规则计算)
│   │   ├── 📂 models          # SQLAlchemy 数据模型定义
│   │   └── 📂 schemas         # Pydantic 输入输出校验模式
│   ├── 📂 data                # 本地离线行情与回测数据集 (.csv)
│   ├── 📂 static              # 静态资源文件
│   ├── 📂 tests               # 自动化单元与集成测试用例
│   ├── 📂 venv                # Python 虚拟环境 (第三方依赖隔离)
│   ├── 📄 .env.example        # 后端配置环境变量模板
│   ├── 📄 alembic.ini         # Alembic 迁移工具配置文件
│   └── 📄 requirements.txt    # 后端 Python 依赖清单
├── 📂 frontend                 # 前端工作台目录 (React + Vite + Tailwind)
│   ├── 📂 public              # 静态公开资源
│   ├── 📂 src                 # React TypeScript 源代码
│   │   ├── 📂 components      # 可复用 UI 组件 (Liquid Glass 侧边栏等)
│   │   ├── 📂 hooks           # 自定义 React Hooks (状态与数据流)
│   │   ├── 📂 pages           # 业务视图页面 (仪表盘、执行、回测等)
│   │   └── 📂 utils           # 前端通用工具类
│   ├── 📄 package.json        # Node.js 依赖及脚本定义
│   ├── 📄 tsconfig.json       # TypeScript 编译器配置文件
│   └── 📄 vite.config.ts      # Vite 构建与反向代理配置文件 (后端 API 已对齐 8001 端口)
├── 📄 docker-compose.yml       # Docker 容器化编排配置文件
├── 📄 start-dev.cmd            # Windows 双击快速开发启动脚本 (关联启动前后端)
├── 📄 start-dev.ps1            # PowerShell 自动化部署/运行主脚本 (默认 API 端口已修改为 8001)
└── 📄 README.md                # 项目指南文档 (当前文件)
```

---

## 🚀 快速启动

### Windows 环境（推荐一键启动）
可以直接在项目根目录下双击运行 `start-dev.cmd`，或者在 PowerShell 中执行以下命令：
```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
```
> [!NOTE]
> 自动化脚本会自动激活后端的 `venv` 环境（若缺失依赖会利用 UTF-8 环境兼容进行国内清华源加速安装），随后分别开启前端和后端窗口，并在启动完毕后自动打开浏览器。

**本地开发默认监听端口：**
* **Backend API**: `http://127.0.0.1:8001`
* **Frontend Web**: `http://127.0.0.1:5173`

*注：原默认 API 端口为 8000，因在部分本地开发机器上容易与系统挂载服务产生冲突，现已统一对齐调整为 8001。*

### 手动独立启动

#### 后端 Python 服务
```powershell
cd backend
# Windows 下为避免 requirements.txt 中中文注释的 GBK 报错，请先设置以下环境变量
$env:PYTHONUTF8=1
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

#### 前端 Web 服务
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

#### 生产构建
```powershell
cd frontend
npm.cmd run build
```

前端生产产物输出到 `frontend/build`，Docker 镜像会从该目录复制静态文件。
当前前端构建链使用 `@vitejs/plugin-react` 6.0.x，锁文件当前解析到 Vite 8.0.16，并已通过 Windows 本地生产构建验证。

#### GitHub Pages 前端发布
仓库包含 `.github/workflows/deploy-pages.yml`。推送到 `main` 时会执行 `npm ci` 与 `npm run build`，再将 `frontend/build` 作为 GitHub Pages artifact 发布。Vite 会在目标仓库 Actions 环境中使用 `/AHR999-Optimized-Kenne-Index/` 作为资源基路径，前端在该环境下使用 `HashRouter`，避免项目页子路径刷新时出现空白页。

当前 workflow 同时会把 `frontend/build` 同步到仓库根目录的 `index.html`、`404.html`、`.nojekyll` 和 `assets/**`，作为 Pages 仍配置为 branch/root 时的静态回退。若后续在 GitHub `Settings -> Pages` 中将 Source 切换为 `GitHub Actions`，可以移除这组根目录静态回退产物，只保留 artifact 发布链路。

本地普通预览请直接运行 `npm.cmd run build && npm.cmd run preview -- --host 127.0.0.1 --port 4173`。如需模拟 GitHub Pages 基路径，可临时设置 `$env:GITHUB_REPOSITORY='kennechen554-code/AHR999-Optimized-Kenne-Index'` 后构建；最终仍以线上 Pages URL 的资产 200 状态作为发布验证证据。

---

## ⚙️ 环境变量配置

复制仓库根目录的 `.env.example` 并重命名为 `.env`，本地开发时放在后端启动目录或通过部署平台注入环境变量：

```env
ENVIRONMENT=development
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-this-local-password
POSTGRES_DB=kenne_main
DATABASE_URL=postgresql+asyncpg://postgres:change-this-local-password@localhost:5432/kenne_main
TENANT_DB_URL_TEMPLATE=postgresql+asyncpg://postgres:change-this-local-password@localhost:5432/kenne_tenant_{tenant_id}
SECRET_KEY=your-super-secret-key-change-in-production
ENCRYPTION_KEY=your-32-byte-encryption-key-here
COOKIE_SECURE=false
CSRF_PROTECTION=true
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_BACKEND=auto

SYSTEM_SMTP_HOST=
SYSTEM_SMTP_PORT=587
SYSTEM_SMTP_USER=
SYSTEM_SMTP_PASSWORD=
SYSTEM_SMTP_FROM=

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_BASIC_PRICE_ID=
STRIPE_PREMIUM_PRICE_ID=

DATA_DIR=./data
BACKTEST_ALLOWED_DIRS=[]
```

> [!IMPORTANT]
> **配置注意事项：**
> * `COOKIE_SECURE=false` 仅限本地 `http://127.0.0.1` 调试使用，生产环境（HTTPS）请务必修改为 `true`。
> * `CSRF_PROTECTION=true` 启用后，前端写操作接口将严格校验 `X-CSRF-Token`。
> * `RATE_LIMIT_BACKEND=auto` 会优先尝试连接 Redis 进行频率控制，如果 Redis 连接不可用，会自动安全降级为内存频率控制器。
> * 绝不要提交真实的 `.env` 或任何交易所 API 密钥到公共 Git 仓库。

### 生产配置门禁

当 `ENVIRONMENT=production` 或 `ENVIRONMENT=prod` 时，后端启动阶段会校验以下安全项，不满足会直接拒绝启动：

* `DEBUG=false`
* `SECRET_KEY` 和 `ENCRYPTION_KEY` 必须替换为高强度真实密钥，且长度不少于 32 字符
* `COOKIE_SECURE=true`
* `CORS_ORIGINS` 只能配置可信 HTTPS 域名，禁止 `*`
* 生产数据库连接串不能继续使用示例中的 `postgres:password@`

---

## 🔑 认证与安全设计

* **双 Token 会话管理**：登录、注册和刷新会话均通过后端写入 `HttpOnly` + `Secure` Cookie 的 `access_token` 和 `refresh_token` 完成。
* **本地持久化优化**：前端不再将敏感的 refresh_token 持久化存储至 `localStorage`，从而彻底防范 XSS 窃取风险。
* **跨站请求伪造防护 (CSRF)**：写接口全面校验 CSRF Token，前端请求库统一配置 `credentials: include` 且自动从 `csrf_token` Cookie 注入请求头。
* **高风险操作二重锁**：执行真实交易订单除了需要拥有 Premium 账号权益，还必须经过前端二次交互确认闸门。

---

## 🛠️ SaaS 用户工作台核心版块

| 功能区 | 业务逻辑与界面设计 |
|---|---|
| **仪表盘 (Dashboard)** | 汇总 Kenne Index 综合指数、MVRV-Z 链上代理解析、定投策略模式、预算消耗进度条、高风险提示以及操作审计日志摘要。 |
| **定投执行 (Execution)** | 提供行情更新、交易所余额查询、模拟执行（Dry Run）以及 Premium 实盘执行控制阀。 |
| **审计留痕 (Audit)** | 持久化记录所有 SIM / LIVE 交易数据，支持多维度过滤、分页、CSV 数据导入与导出预览、月度交易报表和管理员系统操作日志。 |
| **设置 (Settings)** | 包含基础账户资料修改、登录设备会话强制撤销、交易所 API 加密配置、定投策略参数调整、预算纪律红线及自动化控制台。 |
| **权益订阅 (Subscription)**| 展示 Basic/Premium 价格矩阵。集成 Stripe Checkout 及 Stripe Customer Portal 方便用户自主进行订阅升级、续费或退订。 |
| **策略回测 (Backtesting)**| Premium 专属。支持通过浏览器直接上传 CSV 文件或输入服务器端允许目录白名单的绝对路径进行回测。 |

---

## 📈 量化定投策略引擎

定投算法定义于后端代码 [per_asset_strategy.py](backend/app/engine/per_asset_strategy.py)，支持在设置中动态调整：

1. **`per_asset_strict_dd` (严格最大回撤控制)**
   默认防守型策略。优先保护现金流，设立极高的现金缓冲池，只在估值区间进入低估和强安全边际（极低指数值）时释放更多预算。
2. **`per_asset_balanced_return` (平衡收益最大化)**
   进攻型策略。提高资金部署频率与单次定投仓位弹性，旨在提高牛市早期的资金利用率，但需承担更深的历史回撤风险。

---

## 🧪 自动化测试与验证

### 前端类型与构建校验
```powershell
cd frontend
npm.cmd exec tsc -- --noEmit
npm.cmd test
npm.cmd run build
```

### 后端导入与单元测试校验
```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m bandit -r app -ll -ii
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

本轮已执行并通过：

* 前端：`npm.cmd exec tsc -- --noEmit`、`npm.cmd test`（4 项通过）、`npm.cmd run build`
* 后端：`.\.venv\Scripts\python.exe -m pip check`、`.\.venv\Scripts\python.exe -m ruff check app tests`、`.\.venv\Scripts\python.exe -m bandit -r app -ll -ii`、`.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`（79 项通过）
* 浏览器：已通过 in-app Browser 对生产构建预览进行桌面端和移动端回归检查，覆盖公开首页、行情页、邀请分享页无效邀请码、公开接口失败局部降级、无全局错误 toast、无控制台错误和无横向溢出。

> [!NOTE]
> 当前环境中的 Chrome 插件通道未完成 Codex native host 注册，无法使用用户 Chrome 会话直接做 QA；已改用 in-app Browser 完成等价的生产预览回归。若需要复用个人 Chrome 登录态，请先在 Codex 插件界面重新安装或启用 Chrome Extension/native host。

### 发布分支
在具备 `.git` 写权限和 GitHub 推送凭据的环境中，可执行以下脚本完成清理、暂存、提交并推送发布分支：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\publish-release.ps1
```

脚本会在提交前清理 `frontend/build`、`frontend/dist`、`reports`、`.npm-cache`、`.npm-cache-ci`、`.pip-audit-cache`、`.codex-runtime`、`__pycache__`、`.pytest_cache`、`.mypy_cache` 等本地状态，并从 Git 索引移除 `backend/.env`、`backend/dev.db` 等禁止发布文件，避免把密钥、数据库或构建缓存发布到 GitHub。

---

## 🛡️ 安全合规边界
* **回测路径沙箱**：服务器回测路径校验经过严格的 `resolve()` 路径归一化，仅允许读取 `DATA_DIR` 和 `BACKTEST_ALLOWED_DIRS` 白名单内的 `.csv` 文件，禁止目录穿越或读取配置文件。
* **数据加密脱敏**：交易所 API 密钥和 SMTP 密码通过系统对称加密库密文存储在数据库中，前端查询配置时只返回掩码（`******`）。
* **重置令牌单次实效**：忘记密码的一次性验证 Token 采用强哈希算法（如 SHA256）存储于数据库中，有效期 30 分钟且一经使用立即销毁失效。
