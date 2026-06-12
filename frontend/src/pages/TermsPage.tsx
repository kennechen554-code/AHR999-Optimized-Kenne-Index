import { Link } from 'react-router-dom'
import BrandWordmark from '../components/BrandWordmark'

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-bg px-4 py-10 text-text-primary sm:px-6">
      <div className="mx-auto max-w-4xl">
        <Link to="/" className="inline-flex">
          <BrandWordmark caption="Legal" compact />
        </Link>
        <section className="standard-panel mt-8 p-8">
          <div className="section-kicker">Terms of Service</div>
          <h1 className="mt-2 text-3xl font-semibold">Kenne Index 用户服务协议</h1>
          <p className="mt-2 text-xs text-text-tertiary">发布日期：2026年5月25日 | 生效日期：2026年5月25日</p>
          
          <div className="mt-8 space-y-6 text-sm leading-7 text-text-secondary">
            <div>
              <h2 className="text-lg font-semibold text-white">第一条 总则</h2>
              <p className="mt-2">
                1.1 本《用户服务协议》是您与 Kenne Index 平台（以下简称“我们”或“平台”）之间关于使用加密货币定投服务平台所订立的协议。
              </p>
              <p>
                1.2 您通过注册账户、勾选“我已阅读并同意”或以其他方式接受本协议，即表示您已阅读、理解并同意受本协议全部条款的约束。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第二条 服务内容与套餐权益</h2>
              <p className="mt-2">
                2.1 平台提供包括投资信号计算（基于幂律回归模型的 Kenne 指数）、DCA 策略自动化执行、模拟交易、历史回测、AI 智能日报以及多成员共享组织资源等服务。
              </p>
              <p>
                2.2 平台服务分为 Free（免费）、Basic（基础，¥29/月）和 Premium（高级，¥99/月）三个服务等级。其中实盘交易功能、多交易所支持和自动化任务执行仅向 Premium 订阅用户开放。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第三条 账户安全与 API Key 授权</h2>
              <p className="mt-2">
                3.1 用户有责任妥善保管您的账户密码、MFA 密钥以及交易所 API Key 等凭证。平台强烈建议用户仅向 API Key 授予必要的“交易”权限，<strong>严禁开启“提现”权限</strong>，并建议绑定服务器 IP 白名单。
              </p>
              <p>
                3.2 <strong>平台不持有用户资产</strong>。本平台不是交易所，不托管、不持有、不转移用户的任何加密货币资产。您的资产始终存放在您自己的交易所账户中，平台仅通过您授权的 API 代为发送交易指令。
              </p>
              <p>
                3.3 您的所有 API 凭证在服务端使用 AES 算法（Fernet）进行加密存储，加密密钥与数据库独立存放，平台采取合理的商业和技术手段保障您的凭证安全。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第四条 订阅付款与退款政策</h2>
              <p className="mt-2">
                4.1 平台的付费服务采用按月订阅制，由第三方支付服务商 Stripe 进行扣款和处理。订阅在计费周期结束时会自动续费，除非您提前取消订阅。
              </p>
              <p>
                4.2 <strong>退款政策</strong>：由于数字服务的特殊性，已扣除的订阅期费用原则上不予退款。仅在平台出现重大技术故障导致服务完全不可用连续超过 72 小时，或发生系统重复扣款时，方可申请人工审核退款。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第五条 投资风险披露与免责声明</h2>
              <p className="mt-2">
                5.1 <strong>非投资建议声明</strong>：本平台提供的所有数据、信号、指标（包括但不限于 Kenne 指数、MVRV 链上指标及 AI 日报）仅作为信息参考，不构成任何形式的投资建议或财务推荐。
              </p>
              <p>
                5.2 <strong>模型局限性</strong>：Kenne 指数基于加密货币历史价格的幂律回归统计分析。任何统计模型都依赖于历史数据的延续性，历史表现不代表未来，在发生结构性市场变化或极端行情时，量化模型存在失效或失真的风险。
              </p>
              <p>
                5.3 <strong>最大损失可能</strong>：加密货币价格波动剧烈，投资存在本金完全损失的极高风险。用户应当在自身财务承受范围内进行投资，并对自主配置并执行的交易结果承担全部责任。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第六条 责任限制</h2>
              <p className="mt-2">
                6.1 在法律允许的最大范围内，平台对以下原因造成的损失不承担任何赔偿责任：包括但不限于加密货币市场剧烈波动造成的投资损失、交易所技术故障或关闭限制、网络延迟导致的交易滑点以及用户因账号密码或 API 密钥被盗用造成的损失。
              </p>
              <p>
                6.2 <strong>赔偿上限</strong>：在任何情况下，平台因本协议或服务故障对您承担的累计最高责任总额，不超过在损害事件发生前 12 个月内您实际向平台支付的订阅服务费用总额。
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white">第七条 争议解决与管辖</h2>
              <p className="mt-2">
                7.1 本协议的签订、解释、履行及争议解决均适用中华人民共和国法律。
              </p>
              <p>
                7.2 因本协议引起的或与使用平台服务相关的任何争议，双方应首先友好协商解决；协商不成的，任何一方均有权向平台运营方所在地有管辖权的人民法院提起诉讼。
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
