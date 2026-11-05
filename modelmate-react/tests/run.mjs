// Runs the JSDOM test suites through Vite's SSR loader (handles JSX imports).
// Usage: node tests/run.mjs [smoke|fidelity]
import { createServer } from 'vite';

const target = process.argv[2] === 'fidelity' ? '/tests/fidelity.mjs' : '/tests/smoke.mjs';
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' });

try {
  await server.ssrLoadModule(target);
} catch (e) {
  console.error('HARNESS ERROR:', e.message);
  process.exitCode = 1;
} finally {
  await server.close();
}
