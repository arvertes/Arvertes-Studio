import assert from "node:assert/strict";
import { fmtBytes } from "./system-panels.mjs";
assert.equal(fmtBytes(0), "0 MiB");
assert.equal(fmtBytes(1048576), "1 MiB");
assert.equal(fmtBytes(-1), "Indisponível");
assert.equal(fmtBytes(Number.NaN), "Indisponível");
console.log("Painéis: formatação segura dos limites locais aprovada");
