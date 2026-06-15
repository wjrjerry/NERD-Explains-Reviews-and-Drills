import type {
  Difficulty,
  HealthStatus,
  KnowledgeGraph,
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
  uploadMaterial: (targetId: number, file: File) => {
    const form = new FormData();
    form.append("target_id", String(targetId));
    form.append("file", file);
    return request<{ material: Material }>("/materials", { method: "POST", body: form });
  },
  parseMaterial: (materialId: number) =>
    request<{ material: Material }>(`/materials/${materialId}/parse`, { method: "POST" }),
  getMaterialPreview: (materialId: number) => request<MaterialPreview>(`/materials/${materialId}/preview`),
  getMaterialFile: (materialId: number) => requestBlob(`/materials/${materialId}/file`),
  getMaterialStructured: (materialId: number) => request<MaterialStructured>(`/materials/${materialId}/structured`),
  deleteMaterial: (materialId: number) => request<Record<string, never>>(`/materials/${materialId}`, { method: "DELETE" }),

  extractKnowledge: (payload: { material_id: number } | { target_id: number; force_regenerate?: boolean }) =>
    request<KnowledgeResult>("/knowledge/extract", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getKnowledgeGraph: (targetId: number) => request<KnowledgeGraph>(`/knowledge-graphs/${targetId}`),
  generateKnowledgeGraph: (targetId: number, maxPoints = 20) =>
    request<KnowledgeGraph>("/knowledge-graphs/generate", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, force_regenerate: true, max_points: maxPoints })
    }),

  askQuestion: (materialId: number, question: string) =>
    request<QaRecord>("/qa/ask", { method: "POST", body: JSON.stringify({ material_id: materialId, question }) }),
  listQaHistory: (page = 1, pageSize = 10, materialId?: number) =>
    request<Pagination<QaRecord>>(`/qa/history?page=${page}&page_size=${pageSize}${materialId ? `&material_id=${materialId}` : ""}`),

  generateQuestions: (materialId: number, count: number, difficulty: Difficulty, questionTypes: QuestionType[]) =>
    request<{ material_id: number; questions: Question[] }>("/questions/generate", {
      method: "POST",
      body: JSON.stringify({
        material_id: materialId,
        question_types: questionTypes,
        difficulty,
        count
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

  listWrongQuestions: (page = 1, pageSize = 10, targetId?: number, materialId?: number) =>
    request<Pagination<WrongQuestion>>(
      `/wrong-questions?page=${page}&page_size=${pageSize}${targetId ? `&target_id=${targetId}` : ""}${materialId ? `&material_id=${materialId}` : ""}`
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

  exportWrongQuestions: (targetId?: number, materialId?: number) =>
    download(
      `/exports/wrong-questions.md?${targetId ? `target_id=${targetId}&` : ""}${materialId ? `material_id=${materialId}` : ""}`,
      "wrong-questions.md"
    ),
  exportReviewPlan: (planId: number) => download(`/exports/review-plan/${planId}.md`, `review-plan-${planId}.md`),
  exportKnowledgeSummary: (targetId: number) => download(`/exports/knowledge-summary/${targetId}.md`, `knowledge-summary-${targetId}.md`),
  exportAnki: (targetId: number) => download(`/exports/anki/${targetId}.csv`, `anki-${targetId}.csv`)
};
