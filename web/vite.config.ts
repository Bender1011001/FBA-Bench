import fs from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const distAuthClientPath = resolve(__dirname, '../frontend/dist/api')
const srcAuthClientPath = resolve(__dirname, '../frontend/src/api')
const authClientBase = fs.existsSync(distAuthClientPath) ? distAuthClientPath : srcAuthClientPath
const fsAllow = Array.from(new Set([authClientBase, distAuthClientPath, srcAuthClientPath]))

// https://vitejs.dev/config/
export default defineConfig(async () => {
  const { default: react } = await import('@vitejs/plugin-react')
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@fba-enterprise/auth-client': authClientBase,
      }
    },
    server: {
      fs: {
        allow: fsAllow,
      }
    },
    define: {
      // No env bundling; API_BASE_URL set via index.html script
    }
  }
})