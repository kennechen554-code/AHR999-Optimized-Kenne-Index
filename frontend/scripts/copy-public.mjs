import { cpSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const publicDir = join(process.cwd(), 'public')
const distDir = join(process.cwd(), 'build')

if (existsSync(publicDir)) {
  cpSync(publicDir, distDir, { recursive: true, force: true })
}
