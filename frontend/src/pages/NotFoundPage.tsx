import { Link } from 'react-router-dom'
import { ArrowLeft, SearchX } from 'lucide-react'
import BrandWordmark from '../components/BrandWordmark'

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-10 text-text-primary">
      <section className="standard-panel max-w-xl p-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.06]">
          <SearchX className="text-accent" size={26} />
        </div>
        <div className="mt-5 flex justify-center">
          <BrandWordmark caption="404" compact />
        </div>
        <h1 className="mt-6 text-3xl font-semibold">页面不存在</h1>
        <p className="mt-3 text-sm leading-6 text-text-secondary">
          该链接可能已移动或不可用。你可以返回首页，或登录后进入工作台继续查看信号和执行记录。
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to="/" className="secondary-button px-5 py-3">
            <ArrowLeft size={16} />
            返回首页
          </Link>
          <Link to="/app/dashboard" className="primary-button px-5 py-3">进入工作台</Link>
        </div>
      </section>
    </main>
  )
}
