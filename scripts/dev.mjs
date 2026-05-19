import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';

process.noDeprecation = true;

const isWindows = process.platform === 'win32';
const windowsNodeDir = 'C:\\Program Files\\nodejs';
const envWithNode = {
  ...process.env,
  PATH: isWindows && existsSync(windowsNodeDir)
    ? `${windowsNodeDir};${process.env.PATH || ''}`
    : process.env.PATH,
};

const commands = [
  {
    name: 'flask',
    command: 'python',
    args: ['run.py'],
    env: {
      ...envWithNode,
      PORT: process.env.FLASK_PORT || '8009',
      FLASK_RELOAD: process.env.FLASK_RELOAD || '1',
      TEMPLATES_AUTO_RELOAD: process.env.TEMPLATES_AUTO_RELOAD || '1',
    },
  },
  {
    name: 'next',
    command: isWindows ? 'npm.cmd' : 'npm',
    args: ['--prefix', 'next-app', 'run', 'dev'],
    env: {
      ...envWithNode,
      NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8009',
    },
  },
];

const children = commands.map(({ name, command, args, env }) => {
  const child = spawn(command, args, { stdio: 'pipe', env, shell: isWindows });

  child.stdout.on('data', chunk => process.stdout.write(`[${name}] ${chunk}`));
  child.stderr.on('data', chunk => process.stderr.write(`[${name}] ${chunk}`));
  child.on('exit', code => {
    if (code && code !== 0) {
      console.error(`[${name}] exited with code ${code}`);
    }
  });

  return child;
});

function shutdown() {
  for (const child of children) {
    if (!child.killed) child.kill();
  }
}

process.on('SIGINT', () => {
  shutdown();
  process.exit(0);
});
process.on('SIGTERM', shutdown);
