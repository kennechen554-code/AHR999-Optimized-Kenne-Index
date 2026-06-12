# Stripe 计费集成与 SaaS 生产上线配置指南

本指南面向需要将本定投信号系统投入生产环境、正式上线对用户收费的开发者，详细说明了如何配置真实的 Stripe 支付通道及进行生产测试。

---

## 一、Stripe 后端密钥配置

1. **注册并登录 Stripe 账户**：
   - 访问 [Stripe 官网](https://stripe.com) 注册开发者账号。
2. **获取 API 密钥**：
   - 在 Stripe 仪表盘进入 `Developers` -> `API keys`。
   - 获取 **Publishable key**（公钥）与 **Secret key**（私钥）。
   - **安全警告**：生产密钥（形如 `sk_live_...`）必须妥善保存，切勿提交至 Git 仓库。
3. **配置环境变量**：
   - 打开您的生产 `.env` 文件或在云托管服务商（如 AWS, Google Cloud 等）的安全密钥管理中，写入私钥：
     ```bash
     STRIPE_SECRET_KEY=sk_live_your_actual_live_secret_key
     ```

---

## 二、创建产品 (Products) 与价格 ID (Price IDs)

本系统的计费基于 **Stripe Subscription (订阅) 模式**，包含两个付费套餐：“基础版”与“专业版”。

1. **在 Stripe 中创建产品**：
   - 进入 Stripe 仪表盘 -> `Product catalog` -> 点击 `Add product`。
   - 创建第一个产品：
     - **名称**：`DCA 基础版` (Basic)
     - **计费模式**：`Recurring` (周期性)
     - **金额**：根据您的定价设定（例如 `¥29 / Month` 或 `$4.99 / Month`）
   - 创建第二个产品：
     - **名称**：`DCA 专业版` (Premium)
     - **计费模式**：`Recurring` (周期性)
     - **金额**：根据您的定价设定（例如 `¥99 / Month` 或 `$14.99 / Month`）
2. **获取 Price ID**：
   - 创建价格后，在每个产品的 Pricing 列表中，会得到一个形如 `price_1Pxxx...` 的 **API ID**。这就是 **Price ID**。
3. **绑定 Price ID 至环境变量**：
   - 将这二者写入生产 `.env` 配置文件：
     ```bash
     STRIPE_BASIC_PRICE_ID=price_your_basic_price_id
     STRIPE_PREMIUM_PRICE_ID=price_your_premium_price_id
     ```

---

## 三、Stripe Webhook 签名配置与本地测试

Webhook 用于监听用户的付款状态，并在用户支付成功后由 Stripe 主动回调后端系统，自动将用户的租户套餐升级为 Basic 或 Premium。

### 1. 本地联调 Webhook（Stripe CLI 转发）
由于本地开发环境没有公网域名，需要借助 Stripe CLI 工具进行本地转发调试：

1. **下载并安装 Stripe CLI**：
   - 参考 [Stripe 官方 CLI 安装教程](https://docs.stripe.com/stripe-cli)。
2. **登录 Stripe 账号**：
   - 在命令行执行：
     ```bash
     stripe login
     ```
3. **启动本地监听转发**：
   - 执行以下命令，将 Stripe 事件实时转发到本地 FastAPI 后端：
     ```bash
     stripe listen --forward-to localhost:8000/api/v1/stripe/webhook
     ```
   - 命令行会输出一串 Webhook 密钥，形如：`whsec_xxx`。这就是您的 **Webhook 签名秘钥**。
4. **配置本地 .env 调试密钥**：
   - 将上述密钥填入本地 `.env`：
     ```bash
     STRIPE_WEBHOOK_SECRET=whsec_your_local_webhook_signing_secret
     ```
   - 此时，在前端页面发起模拟付款，Stripe 本地测试沙箱会直接将事件转发至您的后端，模拟租户的自动激活。

### 2. 生产环境 Webhook 配置
1. **添加 Endpoint**：
   - 在 Stripe 仪表盘进入 `Developers` -> `Webhooks` -> 点击 `Add endpoint`。
   - **Endpoint URL** 填入您的生产公网地址，路径为：`https://yourdomain.com/api/v1/stripe/webhook`。
   - **Select events** 选择以下四种核心事件：
     - `checkout.session.completed`（结算成功，创建订阅）
     - `customer.subscription.updated`（订阅状态更新，例如续费、升级）
     - `customer.subscription.deleted`（退订，套餐重置为 Free）
     - `invoice.payment_failed`（扣款失败，套餐标记为过去欠费状态）
2. **配置生产 Webhook 秘钥**：
   - 在已创建的 Webhook 端点页面获取 **Signing secret** (`whsec_...`)。
   - 填入生产服务器的环境变量：
     ```bash
     STRIPE_WEBHOOK_SECRET=whsec_your_production_webhook_signing_secret
     ```

---

## 四、安全测试卡与上线发布

Stripe 沙箱环境提供了一组测试信用卡，可用于在测试模式下进行完整的计费闭环验证：

| 模拟卡号 | 有效期 | CVC | 模拟行为 |
| :--- | :--- | :--- | :--- |
| `4242 4242 4242 4242` | 任意未来日期 | 任意 3 位数字 | **支付成功**（用于测试订阅解锁） |
| `4000 0027 6000 3184` | 任意未来日期 | 任意 3 位数字 | **银行卡被拒**（用于测试支付失败流程） |

1. **测试闭环**：
   - 启动测试，在前端点击“订阅专业版”，跳转至 Stripe 收银台。
   - 使用上述 `4242` 卡号完成订阅。
   - 付款成功后系统跳转回 `app/billing?payment=success`。
   - Webhook 收到回调并自动升级数据库中的套餐，前台页面功能锁瞬间解除。
2. **生产切换**：
   - 确认测试闭环无误后，将 Stripe 后台从 `Test Mode` 切换为 `Live Mode`（真实环境）。
   - 更换 `.env` 中所有 Stripe 环境变量为真实生产密钥和生产 Price ID。
   - 重启后端服务，系统便已正式具备了在线收费变现的生产能力！
