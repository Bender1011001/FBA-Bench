import { defineConfig, mergeConfig } from 'vitest/config'
import baseConfig from './vite.config'

export default defineConfig(async () => {
  const resolvedBase = await baseConfig()
  return mergeConfig(resolvedBase, {
    test: {
      environment: 'jsdom',
      setupFiles: './vitest.setup.ts',
      globals: true,
      exclude: ['tests/e2e/**'],
    },
  })
})
