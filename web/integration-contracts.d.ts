// Contratos de evolução. O navegador usa apenas ProductionRepository nesta versão.
export type ProductionType = "character" | "creature" | "environment" | "vegetation" | "prop" | "model" | "audio";
export type TaskKind = "approval" | "requirements" | "attachment" | "catalog" | "inspection" | "validation" | "external";

export interface Brief {
  name: string;
  instruction: string;
  type?: ProductionType | "";
}

export interface GlbSnapshot {
  digest: string; // SHA-256 hexadecimal dos bytes apresentados
  name: string;
  data: Record<"bytes" | "meshes" | "primitives" | "triangles" | "other" | "uv" |
    "materials" | "textures" | "skins" | "skinnedNodes" | "animations", number>;
}

export type Evidence = { at: string } & (
  | { kind: "human-approval" }
  | { kind: "requirements"; technical: string; artistic: string }
  | { kind: "imported-glb"; asset: GlbSnapshot }
  | { kind: "catalog"; digest: string; category: string }
  | { kind: "inspection"; digest: string; report: string[] }
  | { kind: "human-validation"; digest: string }
);

export interface Task {
  id: string; // identificador da etapa, único dentro da produção
  agentId: string; // identificador do cadastro Habblaud
  agent: string;
  title: string;
  description: string;
  tool: string;
  kind: TaskKind;
  needs: string[];
  evidence?: Evidence;
}

export interface LocalProduction {
  schema: 1;
  id: string;
  type: ProductionType;
  name: string;
  instruction: string;
  createdAt: string;
  approvedAt?: string;
  tasks: Task[];
  history: { at: string; type: "plan" | "checkpoint" | "note" | "error"; message: string }[];
}

export type Command =
  | { action: "approve" | "inspect-ready" | "validate" }
  | { action: "note" | "error"; message: string }
  | { action: "prepare"; technical: string; artistic: string }
  | { action: "attach"; asset: GlbSnapshot; category: string }
  | { action: "inspect" | "extend" | "execute"; id: string };

export interface ProductionRepository {
  list(): Promise<LocalProduction[]>;
  create(brief: Brief): Promise<LocalProduction>;
  dispatch(id: string, command: Command): Promise<{ production: LocalProduction; rejection?: string }>;
}

// As interfaces remotas são propostas de integração, sem adaptadores ou URLs ativos.
export interface Capability {
  toolId: string;
  status: "available" | "unavailable" | "unknown";
  observedAt: string;
  expiresAt: string;
  quota: null | { remaining: number; unit: string };
}

export interface VerifiedCheckpoint {
  executionId: string;
  taskId: string;
  artifactId: string;
  sha256: string;
  verifiedAt: string;
}

export interface FuturePorts {
  capabilities(): Promise<Capability[]>;
  getMemory(productionId: string): Promise<{ revision: string; production: LocalProduction }>;
  putMemory(production: LocalProduction, expectedRevision: string): Promise<{ revision: string }>;
  // Identificadores opacos. O adaptador autenticado decide o escopo de Drive.
  getArtifact(artifactId: string): Promise<{ digest: string; bytes: number; mediaType: string }>;
  putArtifact(file: Blob, digest: string, idempotencyKey: string): Promise<{ artifactId: string }>;
  submitExecution(request: {
    productionId: string;
    taskId: string;
    toolId: string;
    artifactIds: string[];
    approvalId: string;
    expectedRevision: string;
    idempotencyKey: string;
    maxCostCentavos: 0;
  }): Promise<{ executionId: string }>;
  getExecution(executionId: string): Promise<{
    status: "waiting" | "running" | "failed" | "verified";
    checkpoint?: VerifiedCheckpoint;
    errorCode?: string;
  }>;
}
