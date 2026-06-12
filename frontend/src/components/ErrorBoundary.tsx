import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    window.dispatchEvent(new CustomEvent('kenne-runtime-error', {
      detail: { message: error.message, componentStack: info.componentStack },
    }))
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-text-primary">
          <div className="standard-panel max-w-lg p-6 text-center">
            <div className="section-kicker">Runtime Guard</div>
            <h1 className="mt-2 text-2xl font-semibold">页面出现异常</h1>
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              当前页面组件渲染失败，请刷新页面或返回工作台。错误摘要：{this.state.message || '未知错误'}
            </p>
            <button className="primary-button mx-auto mt-5 px-5 py-3" onClick={() => window.location.reload()}>
              刷新页面
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
