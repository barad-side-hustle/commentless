import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const CACHE_VERSION = 1;

interface CacheFile {
  version: number;
  signature: string;
  clean: Record<string, string>;
}

export function signatureOf(value: unknown): string {
  return createHash('sha1').update(JSON.stringify(value)).digest('base64url');
}

export function cacheDirectory(cwd: string): string {
  const nodeModules = path.join(cwd, 'node_modules');
  return existsSync(nodeModules)
    ? path.join(nodeModules, '.cache', 'commentless')
    : path.join(cwd, '.commentless-cache');
}

function stamp(file: string): string | null {
  try {
    const stats = statSync(file);
    return `${stats.size}:${stats.mtimeMs}`;
  } catch {
    return null;
  }
}

export class CleanFileCache {
  private readonly clean: Map<string, string>;
  private dirty = false;

  private constructor(
    private readonly file: string,
    private readonly signature: string,
    entries: Iterable<[string, string]>
  ) {
    this.clean = new Map(entries);
  }

  static load(cwd: string, signature: string): CleanFileCache {
    const file = path.join(cacheDirectory(cwd), 'clean.json');
    try {
      const parsed = JSON.parse(readFileSync(file, 'utf8')) as CacheFile;
      if (parsed.version === CACHE_VERSION && parsed.signature === signature) {
        return new CleanFileCache(file, signature, Object.entries(parsed.clean));
      }
    } catch {
      void 0;
    }
    return new CleanFileCache(file, signature, []);
  }

  static disabled(): CleanFileCache {
    return new CleanFileCache('', '', []);
  }

  get enabled(): boolean {
    return this.file !== '';
  }

  isClean(file: string): boolean {
    if (!this.enabled) return false;
    const known = this.clean.get(file);
    return known !== undefined && known === stamp(file);
  }

  mark(file: string, clean: boolean): void {
    if (!this.enabled) return;
    if (!clean) {
      if (this.clean.delete(file)) this.dirty = true;
      return;
    }
    const current = stamp(file);
    if (current === null) return;
    if (this.clean.get(file) !== current) {
      this.clean.set(file, current);
      this.dirty = true;
    }
  }

  save(): void {
    if (!this.enabled || !this.dirty) return;
    const payload: CacheFile = {
      version: CACHE_VERSION,
      signature: this.signature,
      clean: Object.fromEntries(this.clean),
    };
    try {
      mkdirSync(path.dirname(this.file), { recursive: true });
      writeFileSync(this.file, JSON.stringify(payload), 'utf8');
    } catch {
      void 0;
    }
  }
}
