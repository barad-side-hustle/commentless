import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { applyScripts, planScripts } from '../src/scripts.js';
import { VERSION } from '../src/version.js';
import { sandbox, type Sandbox } from './helpers.js';

describe('planScripts', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('returns null when there is no package.json', () => {
    expect(planScripts(box.dir)).toBeNull();
  });

  it('returns null when package.json is not valid JSON', () => {
    box.write('package.json', '{ nope');
    expect(planScripts(box.dir)).toBeNull();
  });

  it('pins a bunx command when commentless is not a dependency', () => {
    box.write('package.json', '{"name":"x"}');
    const plan = planScripts(box.dir);

    expect(plan?.installed).toBe(false);
    expect(plan?.missing['comments:remove']).toBe(`bunx -y commentless@${VERSION} --write`);
    expect(plan?.missing['comments:check']).toBe(
      `bunx -y commentless@${VERSION} --check --reporter github`
    );
  });

  it('calls the binary directly when commentless is a devDependency', () => {
    box.write('package.json', '{"name":"x","devDependencies":{"commentless":"^0.1.0"}}');
    const plan = planScripts(box.dir);

    expect(plan?.installed).toBe(true);
    expect(plan?.missing['comments:remove']).toBe('commentless --write');
  });

  it('reports a script that already exists instead of planning to overwrite it', () => {
    box.write('package.json', '{"name":"x","scripts":{"comments:remove":"my own thing --write"}}');
    const plan = planScripts(box.dir);

    expect(plan?.present).toEqual(['comments:remove']);
    expect(Object.keys(plan?.missing ?? {})).toEqual(['comments:check']);
  });
});

describe('applyScripts', () => {
  let box: Sandbox;

  beforeEach(() => {
    box = sandbox();
  });

  afterEach(() => box.cleanup());

  it('adds the scripts without touching the rest of the file', () => {
    box.write(
      'package.json',
      JSON.stringify({ name: 'x', version: '1.0.0', scripts: { build: 'tsc' } }, null, 2) + '\n'
    );
    const plan = planScripts(box.dir)!;
    applyScripts(plan);

    const parsed = JSON.parse(readFileSync(plan.packageFile, 'utf8'));
    expect(parsed.name).toBe('x');
    expect(parsed.version).toBe('1.0.0');
    expect(parsed.scripts.build).toBe('tsc');
    expect(parsed.scripts['comments:check']).toContain('--check');
  });

  it('never overwrites a script that is already there', () => {
    box.write('package.json', '{\n  "scripts": {\n    "comments:remove": "my own thing"\n  }\n}\n');
    const plan = planScripts(box.dir)!;
    applyScripts(plan);

    const parsed = JSON.parse(readFileSync(plan.packageFile, 'utf8'));
    expect(parsed.scripts['comments:remove']).toBe('my own thing');
    expect(parsed.scripts['comments:check']).toBeTruthy();
  });

  it('creates a scripts block when there is none', () => {
    box.write('package.json', '{\n  "name": "x"\n}\n');
    const plan = planScripts(box.dir)!;
    applyScripts(plan);

    expect(Object.keys(JSON.parse(readFileSync(plan.packageFile, 'utf8')).scripts)).toEqual([
      'comments:remove',
      'comments:check',
    ]);
  });

  it('keeps the file indentation', () => {
    box.write('package.json', '{\n    "name": "x"\n}\n');
    const plan = planScripts(box.dir)!;
    applyScripts(plan);

    expect(readFileSync(plan.packageFile, 'utf8')).toContain('\n    "scripts"');
  });

  it('keeps the trailing newline, or its absence', () => {
    box.write('package.json', '{"name":"x"}\n');
    applyScripts(planScripts(box.dir)!);
    expect(readFileSync(`${box.dir}/package.json`, 'utf8').endsWith('}\n')).toBe(true);

    box.write('package.json', '{"name":"y"}');
    applyScripts(planScripts(box.dir)!);
    expect(readFileSync(`${box.dir}/package.json`, 'utf8').endsWith('}')).toBe(true);
  });
});
