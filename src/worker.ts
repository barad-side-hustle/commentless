import { parentPort, workerData } from 'node:worker_threads';
import { deserializeKeepRules } from './core/keep.js';
import { processFile } from './core/process.js';
import type { FileResult, SerializedKeepRule } from './types.js';

interface WorkerInit {
  keep: SerializedKeepRule[];
  collapseBlankLines: boolean;
  write: boolean;
}

const port = parentPort;
if (!port) throw new Error('commentless worker must be started from a parent thread');

const init = workerData as WorkerInit;
const options = {
  keep: deserializeKeepRules(init.keep),
  collapseBlankLines: init.collapseBlankLines,
  write: init.write,
};

port.on('message', (files: string[] | null) => {
  if (files === null) {
    port.close();
    return;
  }
  const results: FileResult[] = files.map(file => processFile(file, options));
  port.postMessage(results);
});
