import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MailPlus, ShieldCheck, Users } from 'lucide-react'
import { createInvitation, fetchInvitations, fetchTeamMembers, revokeInvitation, updateUserRole } from '../services/api'

export default function TeamPage() {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [stepUpCode, setStepUpCode] = useState('')
  const [message, setMessage] = useState('')
  const members = useQuery({ queryKey: ['team-members'], queryFn: fetchTeamMembers })
  const invitations = useQuery({ queryKey: ['tenant-invitations'], queryFn: fetchInvitations })

  const invite = async () => {
    setMessage('')
    try {
      const result = await createInvitation(email, role)
      setMessage(result.invitation.token && import.meta.env.DEV ? `邀请已创建，本地 token: ${result.invitation.token}` : '邀请已创建')
      setEmail('')
      await invitations.refetch()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '邀请失败')
    }
  }

  const changeRole = async (userId: number, nextRole: string) => {
    setMessage('')
    try {
      await updateUserRole(userId, nextRole, stepUpCode)
      await members.refetch()
      setMessage('角色已更新')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '角色更新失败')
    }
  }

  return (
    <div className="space-y-5">
      <section className="standard-panel p-5">
        <div className="flex items-start gap-3">
          <Users className="mt-1 text-accent" size={22} />
          <div>
            <div className="section-kicker">Team</div>
            <h2 className="section-title">团队与角色管理</h2>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              OWNER/ADMIN 可以邀请成员、管理角色。角色决定租户内操作权限，套餐决定产品能力。
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="standard-panel overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-base font-semibold">成员</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>邮箱</th><th>角色</th><th>状态</th><th>邮箱验证</th><th>操作</th></tr></thead>
              <tbody>
                {(members.data?.users || []).map((member) => (
                  <tr key={member.id}>
                    <td>{member.email}</td>
                    <td>{member.role}</td>
                    <td>{member.is_active ? '启用' : '禁用'}</td>
                    <td>{member.email_verified ? '已验证' : '未验证'}</td>
                    <td>
                      <select value={member.role} onChange={(event) => changeRole(member.id, event.target.value)}>
                        <option value="owner">owner</option>
                        <option value="admin">admin</option>
                        <option value="member">member</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <section className="standard-panel p-5">
            <div className="mb-4 flex items-center gap-2">
              <MailPlus size={18} className="text-accent" />
              <h3 className="text-base font-semibold">邀请成员</h3>
            </div>
            <label className="field-block">
              <span>邮箱</span>
              <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="member@example.com" />
            </label>
            <label className="field-block mt-3">
              <span>角色</span>
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="member">member</option>
                <option value="admin">admin</option>
              </select>
            </label>
            <button onClick={invite} disabled={!email} className="primary-button mt-4 w-full justify-center py-3 disabled:opacity-50">
              创建邀请
            </button>
          </section>

          <section className="standard-panel p-5">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck size={18} className="text-green" />
              <h3 className="text-base font-semibold">Step-up Code</h3>
            </div>
            <input className="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm" value={stepUpCode} onChange={(event) => setStepUpCode(event.target.value)} placeholder="MFA code for role changes" />
          </section>
        </div>
      </section>

      <section className="standard-panel p-5">
        <h3 className="text-base font-semibold">待处理邀请</h3>
        <div className="mt-3 grid gap-2">
          {(invitations.data?.invitations || []).map((item) => (
            <div key={item.id} className="metric-tile">
              <span>{item.email} · {item.role} · expires {item.expires_at}</span>
              <button className="secondary-button px-3 py-2 text-xs" disabled={Boolean(item.accepted_at || item.revoked_at)} onClick={() => revokeInvitation(item.id).then(() => invitations.refetch())}>
                撤销
              </button>
            </div>
          ))}
          {(invitations.data?.invitations || []).length === 0 && <div className="text-sm text-text-tertiary">暂无邀请</div>}
        </div>
      </section>

      {message && <div className="rounded-2xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{message}</div>}
    </div>
  )
}
