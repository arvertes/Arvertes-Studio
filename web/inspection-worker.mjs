import { inspectTask } from "./coordination.mjs";

self.onmessage = ({ data: { id, data, requirements } }) => {
  self.postMessage({ id, report: inspectTask(id, data, requirements) });
};
