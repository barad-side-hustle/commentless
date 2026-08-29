export { DEFAULT_KEEP_RULES, resolveKeepRules } from './core/keep.js';
export { DEFAULT_EXTENSIONS, scanSource, scriptKindFor } from './core/scan.js';
export { collapseBlankLines, stripComments } from './core/strip.js';
export { discoverFiles, type DiscoverOptions, type DiscoveryMode } from './core/files.js';
export { processFile, type ProcessOptions } from './core/process.js';
export { cacheDirectory, CleanFileCache } from './core/cache.js';
export { defaultConcurrency, run, type RunOptions } from './core/run.js';
export { report, REPORTERS, type ReportContext, type ReporterName } from './reporters/index.js';
export {
  CONFIG_FILE_NAME,
  ConfigError,
  loadConfig,
  validateConfig,
  type FileConfig,
} from './config.js';
export { defaultConfig, init, type InitOptions, type InitResult } from './init.js';
export { main } from './cli.js';
export type * from './types.js';
