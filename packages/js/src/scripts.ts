import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { VERSION } from './version.js';

export const SCRIPT_NAMES = ['comments:remove', 'comments:check'] as const;

export interface ScriptPlan {
  packageFile: string;
  installed: boolean;
  missing: Record<string, string>;
  present: string[];
}

function detectIndent(source: string): string {
  const match = /\n(\s+)"/.exec(source);
  return match?.[1] ?? '  ';
}

export function planScripts(cwd: string): ScriptPlan | null {
  const packageFile = path.join(cwd, 'package.json');
  if (!existsSync(packageFile)) return null;

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(readFileSync(packageFile, 'utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }

  const deps = {
    ...((parsed.dependencies as Record<string, string>) ?? {}),
    ...((parsed.devDependencies as Record<string, string>) ?? {}),
  };
  const installed = Object.hasOwn(deps, 'commentless');
  const binary = installed ? 'commentless' : `bunx -y commentless@${VERSION}`;

  const wanted: Record<string, string> = {
    'comments:remove': `${binary} --write`,
    'comments:check': `${binary} --check --reporter github`,
  };

  const scripts = (parsed.scripts as Record<string, string>) ?? {};
  const missing: Record<string, string> = {};
  const present: string[] = [];

  for (const [name, command] of Object.entries(wanted)) {
    if (Object.hasOwn(scripts, name)) present.push(name);
    else missing[name] = command;
  }

  return { packageFile, installed, missing, present };
}

export function applyScripts(plan: ScriptPlan): void {
  const source = readFileSync(plan.packageFile, 'utf8');
  const parsed = JSON.parse(source) as Record<string, unknown>;
  parsed.scripts = { ...((parsed.scripts as Record<string, string>) ?? {}), ...plan.missing };

  const trailing = source.endsWith('\n') ? '\n' : '';
  writeFileSync(
    plan.packageFile,
    JSON.stringify(parsed, null, detectIndent(source)) + trailing,
    'utf8'
  );
}
