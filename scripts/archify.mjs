#!/usr/bin/env node
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const archifyBin = path.resolve(__dirname, '..', '.agents', 'skills', 'archify', 'bin', 'archify.mjs');

const child = spawn(process.execPath, [archifyBin, ...process.argv.slice(2)], {
  stdio: 'inherit'
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
