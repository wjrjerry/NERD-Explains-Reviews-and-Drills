import type {
  AiUsageLogItem,
  AiUsageSummary,
  Difficulty,
  HealthStatus,
  KnowledgeGraph,
  KnowledgePointMastery,
  KnowledgePointMaterials,
  KnowledgeResult,
  Material,
  MaterialPreview,
  MaterialStructured,
  QaRecord,
  QuestionType,
  Question,
  ReviewPlan,
  StudyTarget,
  TestRecord,
  TestSubmitAnswer,
  TestResult,
  User,
  WrongQuestion
} from "./types";

const DEFAULT_API_BASE = "/api";
const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);
const TOKEN_KEY = "ai_review_token";

type Pagination<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

type KnowledgeExtractScope =
  | { materialId: number; targetId?: never; forceRegenerate?: never }
  | { targetId: number; materialId?: never; forceRegenerate?: boolean }
  | { material_id: number; target_id?: never; force_regenerate?: never }
  | { target_id: number; material_id?: never; force_regenerate?: boolean };

type QaScope = {
  materialId?: number;
  targetId?: number;
  knowledgePointId?: number;
  question: string;
};

type QuestionGenerateScope = {
  materialId?: number;
  targetId?: number;
  knowledgePointIds?: number[];
  extraRequirement?: string;
  count: number;
  difficulty: Difficulty;
  questionTypes: QuestionType[];
};

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok || payload.code !== 0) {
    throw new Error(readErrorMessage(payload));
  }

  return payload.data as T;
}

async function download(path: string, filename: string) {
  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), { headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(readErrorMessage(payload));
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function requestBlob(path: string) {
  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), { headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(readErrorMessage(payload));
  }

  return response.blob();
}

function normalizeApiBase(value: unknown) {
  const base = typeof value === "string" ? value.trim() : "";
  if (!base) {
    return DEFAULT_API_BASE;
  }
  return base.replace(/\/+$/, "");
}

function buildUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalizedPath}`;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

function readErrorMessage(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return "请求失败";
  }

  const data = payload as { detail?: unknown; message?: unknown };
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return String(item);
      })
      .join("；");
  }
  if (typeof data.message === "string") {
    return data.message;
  }
  return "请求失败";
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  healthDb: () => request<HealthStatus>("/health/db"),
  healthRedis: () => request<HealthStatus>("/health/redis"),

  async login(username: string, password: string) {
    const data = await request<{ token: { access_token: string; token_type: string }; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    setToken(data.token.access_token);
    return data.user;
  },

  register: (username: string, password: string, displayName: string) =>
    request<{ user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, display_name: displayName })
    }),

  me: () => request<{ user: User }>("/users/me"),

  listTargets: (page = 1, pageSize = 20) =>
    request<Pagination<StudyTarget>>(`/study-targets?page=${page}&page_size=${pageSize}`),
  getTarget: (targetId: number) => request<{ target: StudyTarget }>(`/study-targets/${targetId}`),
  createTarget: (target: Omit<Partial<StudyTarget>, "id" | "created_at" | "updated_at">) =>
    request<{ target: StudyTarget }>("/study-targets", { method: "POST", body: JSON.stringify(target) }),
  updateTarget: (targetId: number, target: Partial<StudyTarget>) =>
    request<{ target: StudyTarget }>(`/study-targets/${targetId}`, { method: "PATCH", body: JSON.stringify(target) }),
  deleteTarget: (targetId: number) => request<Record<string, never>>(`/study-targets/${targetId}`, { method: "DELETE" }),

  listMaterials: (page = 1, pageSize = 20, targetId?: number) =>
    request<Pagination<Material>>(`/materials?page=${page}&page_size=${pageSize}${targetId ? `&target_id=${targetId}` : ""}`),
  getMaterial: (materialId: number) => request<{ material: Material }>(`/materials/${materialId}`),
  uploadMaterial: (targetId: number, file: File, autoParse = true) => {
    const form = new FormData();
    form.append("target_id", String(targetId));
    form.append("auto_parse", String(autoParse));
    form.append("file", file);
    return request<{ material: Material }>("/materials", { method: "POST", body: form });
  },
  parseMaterial: (materialId: number) =>
    request<{ material: Material }>(`/materials/${materialId}/parse`, { method: "POST" }),
  getMaterialPreview: (materialId: number) => request<MaterialPreview>(`/materials/${materialId}/preview`),
  getMaterialFile: (materialId: number) => requestBlob(`/materials/${materialId}/file`),
  getMaterialStructured: (materialId: number) => request<MaterialStructured>(`/materials/${materialId}/structured`),
  deleteMaterial: (materialId: number) => request<Record<string, never>>(`/materials/${materialId}`, { method: "DELETE" }),

  getTargetChunks: (targetId: number, limit = 200) =>
    request<{ target_id: number; chunks: MaterialStructured["chunks"] }>(`/study-targets/${targetId}/chunks${buildQuery({ limit })}`),

  extractKnowledge: (scope: KnowledgeExtractScope) =>
    request<KnowledgeResult>("/knowledge/extract", {
      method: "POST",
      body: JSON.stringify(
        "targetId" in scope
          ? { target_id: scope.targetId, force_regenerate: scope.forceRegenerate ?? true }
          : "materialId" in scope
            ? { material_id: scope.materialId }
            : scope
      )
    }),
  getKnowledgeGraph: (targetId: number) => request<KnowledgeGraph>(`/knowledge-graphs/${targetId}`),
  generateKnowledgeGraph: (targetId: number, maxPoints = 20) =>
    request<KnowledgeGraph>("/knowledge-graphs/generate", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, force_regenerate: true, max_points: maxPoints })
    }),
  listKnowledgePointMaterials: (knowledgePointId: number) =>
    request<KnowledgePointMaterials>(`/knowledge-points/${knowledgePointId}/materials`),
  listKnowledgePointQuestions: (knowledgePointId: number, page = 1, pageSize = 10) =>
    request<Pagination<Question>>(`/knowledge-points/${knowledgePointId}/questions${buildQuery({ page, page_size: pageSize })}`),
  listKnowledgePointWrongQuestions: (knowledgePointId: number, page = 1, pageSize = 10) =>
    request<Pagination<WrongQuestion>>(
      `/knowledge-points/${knowledgePointId}/wrong-questions${buildQuery({ page, page_size: pageSize })}`
    ),
  updateKnowledgePointMastery: (knowledgePointId: number, masteryStatus: WrongQuestion["mastery_status"]) =>
    request<KnowledgePointMastery>(`/knowledge-points/${knowledgePointId}/mastery`, {
      method: "PATCH",
      body: JSON.stringify({ mastery_status: masteryStatus })
    }),

  askQuestion: (scope: QaScope) =>
    request<QaRecord>("/qa/ask", {
      method: "POST",
      body: JSON.stringify({
        material_id: scope.materialId,
        target_id: scope.targetId,
        knowledge_point_id: scope.knowledgePointId,
        question: scope.question
      })
    }),
  listQaHistory: (page = 1, pageSize = 10, materialId?: number, targetId?: number) =>
    request<Pagination<QaRecord>>(
      `/qa/history${buildQuery({ page, page_size: pageSize, material_id: materialId, target_id: targetId })}`
    ),

  generateQuestions: (scope: QuestionGenerateScope) =>
    request<{ material_id?: number | null; target_id?: number | null; questions: Question[] }>("/questions/generate", {
      method: "POST",
      body: JSON.stringify({
        material_id: scope.materialId,
        target_id: scope.targetId,
        knowledge_point_ids: scope.knowledgePointIds ?? [],
        extra_requirement: scope.extraRequirement || undefined,
        question_types: scope.questionTypes,
        difficulty: scope.difficulty,
        count: scope.count
      })
    }),

  submitTest: (materialId: number, targetId: number | null, answers: TestSubmitAnswer[]) =>
    request<TestResult>("/tests/submit", {
      method: "POST",
      body: JSON.stringify({ material_id: materialId, target_id: targetId, answers })
    }),
  listTestRecords: (page = 1, pageSize = 10, targetId?: number, materialId?: number) =>
    request<Pagination<TestRecord>>(
      `/tests/records?page=${page}&page_size=${pageSize}${targetId ? `&target_id=${targetId}` : ""}${materialId ? `&material_id=${materialId}` : ""}`
    ),

  listWrongQuestions: (page = 1, pageSize = 10, targetId?: number, materialId?: number, knowledgePointId?: number) =>
    request<Pagination<WrongQuestion>>(
      `/wrong-questions${buildQuery({
        page,
        page_size: pageSize,
        target_id: targetId,
        material_id: materialId,
        knowledge_point_id: knowledgePointId
      })}`
    ),
  getWrongQuestion: (wrongQuestionId: number) => request<WrongQuestion>(`/wrong-questions/${wrongQuestionId}`),
  updateWrongQuestionMastery: (wrongQuestionId: number, masteryStatus: WrongQuestion["mastery_status"]) =>
    request<WrongQuestion>(`/wrong-questions/${wrongQuestionId}/mastery`, {
      method: "PATCH",
      body: JSON.stringify({ mastery_status: masteryStatus })
    }),

  generateReviewPlan: (targetId: number, startDate: string, endDate: string) =>
    request<ReviewPlan>("/review-plans/generate", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, start_date: startDate, end_date: endDate })
    }),
  listReviewPlans: (page = 1, pageSize = 20, targetId?: number) =>
    request<Pagination<ReviewPlan>>(`/review-plans?page=${page}&page_size=${pageSize}${targetId ? `&target_id=${targetId}` : ""}`),

  getAiUsageSummary: (targetId?: number, materialId?: number) =>
    request<AiUsageSummary>(`/ai-usage/summary${buildQuery({ target_id: targetId, material_id: materialId })}`),
  listAiUsageLogs: (page = 1, pageSize = 20, targetId?: number, materialId?: number) =>
    request<Pagination<AiUsageLogItem>>(
      `/ai-usage/logs${buildQuery({ page, page_size: pageSize, target_id: targetId, material_id: materialId })}`
    ),

  exportWrongQuestions: (targetId?: number, materialId?: number) =>
    download(
      `/exports/wrong-questions.md?${targetId ? `target_id=${targetId}&` : ""}${materialId ? `material_id=${materialId}` : ""}`,
      "wrong-questions.md"
    ),
  exportReviewPlan: (planId: number) => download(`/exports/review-plan/${planId}.md`, `review-plan-${planId}.md`),
  exportKnowledgeSummary: (targetId: number) => download(`/exports/knowledge-summary/${targetId}.md`, `knowledge-summary-${targetId}.md`),
  exportAnki: (targetId: number) => download(`/exports/anki/${targetId}.csv`, `anki-${targetId}.csv`)
};
