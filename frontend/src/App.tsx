import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  Brain,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ClipboardCheck,
  Download,
  ExternalLink,
  FileText,
  GitBranch,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Network,
  Plus,
  RefreshCw,
  Shield,
  Sparkles,
  Trash2,
  Upload,
  UserCircle,
  XCircle
} from "lucide-react";
import { api, clearToken, getToken } from "./api";
import type {
  AdminLog,
  AdminParseTask,
  AdminSummary,
  AiUsageLogItem,
  AiUsageSummary,
  Difficulty,
  HealthStatus,
  KnowledgeGraph,
  KnowledgeGraphNode,
  KnowledgeJob,
  KnowledgeMasteryStatus,
  KnowledgePointMaterialItem,
  KnowledgePointReference,
  KnowledgeResult,
  Material,
  MaterialPreview,
  MaterialStructured,
  ParseStatus,
  ParseTaskStatus,
  QaRecord,
  Question,
  QuestionSolution,
  QuestionType,
  ReviewPlan,
  ReviewPlanTask,
  StudyTarget,
  TestRecord,
  TestResultItem,
  TestSubmitAnswer,
  TestResult,
  User,
  WrongQuestion
} from "./types";

type View =
  | "dashboard"
  | "targets"
  | "materials"
  | "detail"
  | "graph"
  | "qa"
  | "practice"
  | "wrong"
  | "plans"
  | "usage";

type PracticeSubView = "questions" | "results";

type FocusableScope = "target" | "knowledge_point" | "material";

type WrongBookMode = "library" | "review";

type WrongQuestionFilters = {
  targetId: number | null;
  materialId: number | null;
  knowledgePointId: number | null;
  masteryStatus: WrongQuestion["mastery_status"] | "";
};

type AdminView = "overview" | "users" | "materials" | "tasks" | "logs" | "health";

type NoticeTone = "info" | "success" | "danger" | "warning";

type Notice = {
  tone: NoticeTone;
  text: string;
};

type LoginRole = "student" | "admin";

type AiPendingActions = {
  qa: boolean;
  questions: boolean;
  test: boolean;
  plan: boolean;
};

type MaterialSourcePreview = {
  materialId: number;
  url: string;
  contentType: string;
  fileType: Material["file_type"];
};

type QuestionBatchContext = {
  materialId: number;
  targetId: number | null;
  scope: "material" | "target" | "knowledge_point";
};

const navItems: Array<{ view: View; label: string; icon: typeof LayoutDashboard }> = [
  { view: "dashboard", label: "仪表盘", icon: LayoutDashboard },
  { view: "targets", label: "目标管理", icon: BookOpen },
  { view: "materials", label: "资料库", icon: FileText },
  { view: "graph", label: "知识图谱", icon: Network },
  { view: "qa", label: "AI 问答", icon: MessageSquare },
  { view: "practice", label: "AI 出题", icon: ClipboardCheck },
  { view: "wrong", label: "错题本", icon: AlertTriangle },
  { view: "plans", label: "复习计划", icon: CalendarDays },
  { view: "usage", label: "AI 用量", icon: Bot }
];

const adminNavItems: Array<{ view: AdminView; label: string; icon: typeof LayoutDashboard }> = [
  { view: "overview", label: "后台总览", icon: LayoutDashboard },
  { view: "users", label: "用户管理", icon: UserCircle },
  { view: "materials", label: "资料管理", icon: FileText },
  { view: "tasks", label: "解析任务", icon: AlertTriangle },
  { view: "logs", label: "操作日志", icon: CalendarDays },
  { view: "health", label: "系统健康", icon: Shield }
];

const parseStatusText: Record<Material["parse_status"], string> = {
  uploaded: "等待解析",
  parsing: "解析中",
  parsed: "可学习",
  failed: "解析失败"
};

const parsePollMaxAttempts = 30;
const parsePollIntervalMs = 2500;
const knowledgeJobPollMaxAttempts = 45;
const knowledgeJobPollIntervalMs = 2000;
const initialAiPendingActions: AiPendingActions = {
  qa: false,
  questions: false,
  test: false,
  plan: false
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getParseActionText(status: Material["parse_status"]) {
  if (status === "parsing") return "解析中";
  if (status === "parsed") return "重解析";
  if (status === "failed") return "重试解析";
  return "解析";
}

function getMaterialStateHint(material: Material) {
  if (material.parse_status === "parsing") return "资料正在解析，完成后会自动刷新。";
  if (material.parse_status === "uploaded") return "等待后台解析或手动触发解析。";
  if (material.parse_status === "failed") return material.parse_error ?? "解析失败，可重试解析。";
  if (material.parse_warning) return "资料已解析，但解析质量可能影响 AI 回答和出题。";
  return "资料已解析，结构化内容和知识图谱会自动刷新。";
}

const questionTypeOptions: Array<{ value: QuestionType; label: string }> = [
  { value: "single_choice", label: "单选题" },
  { value: "multiple_choice", label: "多选题" },
  { value: "true_false", label: "判断题" },
  { value: "subjective", label: "主观题" }
];

function normalizeHealthStatus(value: HealthStatus | null | undefined, key?: "db" | "redis"): HealthStatus {
  const status = value?.status ?? (key ? value?.[key] : undefined) ?? "error";
  return { ...value, status };
}

function App() {
  const [view, setView] = useState<View>("dashboard");
  const [adminView, setAdminView] = useState<AdminView>("overview");
  const [user, setUser] = useState<User | null>(null);
  const [targets, setTargets] = useState<StudyTarget[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [qaRecords, setQaRecords] = useState<QaRecord[]>([]);
  const [qaHistoryLoading, setQaHistoryLoading] = useState(false);
  const [qaHistoryError, setQaHistoryError] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestion[]>([]);
  const [wrongQuestionFilters, setWrongQuestionFilters] = useState<WrongQuestionFilters>({
    targetId: null,
    materialId: null,
    knowledgePointId: null,
    masteryStatus: ""
  });
  const [wrongQuestionsLoading, setWrongQuestionsLoading] = useState(false);
  const [wrongBookMode, setWrongBookMode] = useState<WrongBookMode>("library");
  const [wrongReviewQueue, setWrongReviewQueue] = useState<WrongQuestion[]>([]);
  const [wrongReviewIndex, setWrongReviewIndex] = useState(0);
  const [wrongReviewLoading, setWrongReviewLoading] = useState(false);
  const [wrongRedoSubmitting, setWrongRedoSubmitting] = useState(false);
  const [wrongRedoResult, setWrongRedoResult] = useState<TestResultItem | null>(null);
  const [reviewPlans, setReviewPlans] = useState<ReviewPlan[]>([]);
  const [updatingReviewPlanTaskIds, setUpdatingReviewPlanTaskIds] = useState<Set<number>>(() => new Set());
  const [questionExplainAnswers, setQuestionExplainAnswers] = useState<Record<number, string>>({});
  const [questionExplainLoading, setQuestionExplainLoading] = useState<Record<number, boolean>>({});
  const [knowledge, setKnowledge] = useState<KnowledgeResult | null>(null);
  const [targetKnowledge, setTargetKnowledge] = useState<KnowledgeResult | null>(null);
  const [knowledgeGraph, setKnowledgeGraph] = useState<KnowledgeGraph | null>(null);
  const [graphKnowledgeGraph, setGraphKnowledgeGraph] = useState<KnowledgeGraph | null>(null);
  const [graphTargetKnowledge, setGraphTargetKnowledge] = useState<KnowledgeResult | null>(null);
  const [graphMaterialKnowledge, setGraphMaterialKnowledge] = useState<KnowledgeResult | null>(null);
  const [qaKnowledgeGraph, setQaKnowledgeGraph] = useState<KnowledgeGraph | null>(null);
  const [practiceKnowledgeGraph, setPracticeKnowledgeGraph] = useState<KnowledgeGraph | null>(null);
  const [activeKnowledgeJob, setActiveKnowledgeJob] = useState<KnowledgeJob | null>(null);
  const [graphMaterialKnowledgeLoading, setGraphMaterialKnowledgeLoading] = useState(false);
  const [graphMaterialKnowledgeError, setGraphMaterialKnowledgeError] = useState<string | null>(null);
  const [structured, setStructured] = useState<MaterialStructured | null>(null);
  const [testRecords, setTestRecords] = useState<TestRecord[]>([]);
  const [preview, setPreview] = useState<MaterialPreview | null>(null);
  const [aiUsageSummary, setAiUsageSummary] = useState<AiUsageSummary | null>(null);
  const [aiUsageLogs, setAiUsageLogs] = useState<AiUsageLogItem[]>([]);
  const [aiUsageLoading, setAiUsageLoading] = useState(false);
  const [aiUsageError, setAiUsageError] = useState<string | null>(null);
  const [sourcePreview, setSourcePreview] = useState<MaterialSourcePreview | null>(null);
  const [health, setHealth] = useState<{ api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus }>({});
  const [adminSummary, setAdminSummary] = useState<AdminSummary | null>(null);
  const [adminUsers, setAdminUsers] = useState<User[]>([]);
  const [adminMaterials, setAdminMaterials] = useState<Material[]>([]);
  const [adminTasks, setAdminTasks] = useState<AdminParseTask[]>([]);
  const [adminLogs, setAdminLogs] = useState<AdminLog[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [graphContextTargetId, setGraphContextTargetId] = useState<number | null>(null);
  const [graphContextMaterialId, setGraphContextMaterialId] = useState<number | null>(null);
  const [qaContextTargetId, setQaContextTargetId] = useState<number | null>(null);
  const [qaContextMaterialId, setQaContextMaterialId] = useState<number | null>(null);
  const [practiceContextTargetId, setPracticeContextTargetId] = useState<number | null>(null);
  const [practiceContextMaterialId, setPracticeContextMaterialId] = useState<number | null>(null);
  const [qaScope, setQaScope] = useState<FocusableScope>("target");
  const [practiceScope, setPracticeScope] = useState<FocusableScope>("target");
  const [qaFocusedKnowledgePointIds, setQaFocusedKnowledgePointIds] = useState<number[]>([]);
  const [practiceFocusedKnowledgePointIds, setPracticeFocusedKnowledgePointIds] = useState<number[]>([]);
  const [practiceSubView, setPracticeSubView] = useState<PracticeSubView>("questions");
  const [questionBatchContext, setQuestionBatchContext] = useState<QuestionBatchContext | null>(null);
  const [knowledgeRefreshing, setKnowledgeRefreshing] = useState(false);
  const [aiPendingActions, setAiPendingActions] = useState<AiPendingActions>(initialAiPendingActions);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const parsePollAttemptsRef = useRef<Map<number, number>>(new Map());
  const parsePollInFlightRef = useRef<Set<number>>(new Set());

  const selectedTarget = useMemo(
    () => targets.find((item) => item.id === selectedTargetId) ?? null,
    [selectedTargetId, targets]
  );
  const selectedMaterial = useMemo(
    () => materials.find((item) => item.id === selectedMaterialId) ?? null,
    [materials, selectedMaterialId]
  );
  const graphContextTargetIdEffective = graphContextTargetId;
  const graphContextMaterialIdEffective = graphContextMaterialId;
  const qaContextTargetIdEffective = qaContextTargetId;
  const qaContextMaterialIdEffective = qaContextMaterialId;
  const practiceContextTargetIdEffective = practiceContextTargetId;
  const practiceContextMaterialIdEffective = practiceContextMaterialId;
  const graphContextTarget = useMemo(
    () => targets.find((item) => item.id === graphContextTargetIdEffective) ?? null,
    [graphContextTargetIdEffective, targets]
  );
  const graphContextMaterial = useMemo(
    () => materials.find((item) => item.id === graphContextMaterialIdEffective) ?? null,
    [materials, graphContextMaterialIdEffective]
  );
  const qaContextTarget = useMemo(
    () => targets.find((item) => item.id === qaContextTargetIdEffective) ?? null,
    [qaContextTargetIdEffective, targets]
  );
  const qaContextMaterial = useMemo(
    () => materials.find((item) => item.id === qaContextMaterialIdEffective) ?? null,
    [materials, qaContextMaterialIdEffective]
  );
  const practiceContextTarget = useMemo(
    () => targets.find((item) => item.id === practiceContextTargetIdEffective) ?? null,
    [practiceContextTargetIdEffective, targets]
  );
  const practiceContextMaterial = useMemo(
    () => materials.find((item) => item.id === practiceContextMaterialIdEffective) ?? null,
    [materials, practiceContextMaterialIdEffective]
  );
  const qaKnowledgePointCandidates = useMemo(
    () => getKnowledgePointCandidates(qaKnowledgeGraph, qaContextMaterialIdEffective),
    [qaKnowledgeGraph, qaContextMaterialIdEffective]
  );
  const practiceKnowledgePointCandidates = useMemo(
    () => getKnowledgePointCandidates(practiceKnowledgeGraph, practiceContextMaterialIdEffective),
    [practiceKnowledgeGraph, practiceContextMaterialIdEffective]
  );
  const qaKnowledgePointCandidateIds = useMemo(
    () => new Set(qaKnowledgePointCandidates.map((point) => point.id)),
    [qaKnowledgePointCandidates]
  );
  const practiceKnowledgePointCandidateIds = useMemo(
    () => new Set(practiceKnowledgePointCandidates.map((point) => point.id)),
    [practiceKnowledgePointCandidates]
  );
  const qaFocusedKnowledgePoints = useMemo(
    () => qaKnowledgePointCandidates.filter((node) => qaFocusedKnowledgePointIds.includes(node.id)),
    [qaKnowledgePointCandidates, qaFocusedKnowledgePointIds]
  );
  const practiceFocusedKnowledgePoints = useMemo(
    () => practiceKnowledgePointCandidates.filter((node) => practiceFocusedKnowledgePointIds.includes(node.id)),
    [practiceKnowledgePointCandidates, practiceFocusedKnowledgePointIds]
  );
  const visibleMaterials = useMemo(
    () => (selectedTargetId ? materials.filter((item) => item.target_id === selectedTargetId) : []),
    [materials, selectedTargetId]
  );

  const isAdmin = user?.role === "admin";
  const visibleNavItems = navItems;

  useEffect(() => {
    const token = getToken();
    if (!token) {
      return;
    }

    void initializeSession();
  }, []);

  useEffect(() => {
    if (!selectedMaterialId || !user) {
      setSourcePreview(null);
      return;
    }

    setKnowledge(null);
    setStructured(null);
    setSourcePreview(null);
    void loadMaterialContext(selectedMaterialId);
  }, [selectedMaterialId, user]);

  useEffect(() => {
    if (!selectedTargetId || !selectedMaterialId) {
      return;
    }
    const selectedStillInTarget = materials.some(
      (material) => material.id === selectedMaterialId && material.target_id === selectedTargetId
    );
    if (!selectedStillInTarget) {
      setSelectedMaterialId(null);
      setKnowledge(null);
      setStructured(null);
      setPreview(null);
      setSourcePreview(null);
      if (view === "detail") {
        setView("materials");
      }
    }
  }, [materials, selectedMaterialId, selectedTargetId, view]);

  useEffect(() => {
    return () => {
      if (sourcePreview?.url) {
        URL.revokeObjectURL(sourcePreview.url);
      }
    };
  }, [sourcePreview?.url]);

  function handleSelectLearningTarget(targetId: number) {
    setSelectedTargetId(targetId);
    setTargetKnowledge(null);

    const currentMaterialStillInTarget = materials.some(
      (material) => material.id === selectedMaterialId && material.target_id === targetId
    );
    if (!currentMaterialStillInTarget) {
      setSelectedMaterialId(null);
      setKnowledge(null);
      setStructured(null);
      setPreview(null);
      setSourcePreview(null);
    }
  }

  function handleSelectLearningMaterial(materialId: number | null) {
    setSelectedMaterialId(materialId);
    if (materialId === null) {
      setKnowledge(null);
      setStructured(null);
      setPreview(null);
      setSourcePreview(null);
      return;
    }

    const material = materials.find((item) => item.id === materialId);
    if (material) {
      setSelectedTargetId(material.target_id);
    }
  }

  function handleSelectGraphTarget(targetId: number) {
    setGraphContextTargetId(targetId);
    setGraphContextMaterialId((current) => {
      const materialStillInTarget = materials.some((material) => material.id === current && material.target_id === targetId);
      return materialStillInTarget ? current : null;
    });
  }

  function handleSelectGraphMaterial(materialId: number | null) {
    setGraphContextMaterialId(materialId);
    const material = materials.find((item) => item.id === materialId);
    if (material) {
      setGraphContextTargetId(material.target_id);
    }
  }

  function handleSelectQaTarget(targetId: number) {
    setQaContextTargetId(targetId);
    setQaContextMaterialId((current) => {
      const materialStillInTarget = materials.some((material) => material.id === current && material.target_id === targetId);
      return materialStillInTarget ? current : null;
    });
  }

  function handleSelectQaMaterial(materialId: number | null) {
    setQaContextMaterialId(materialId);
    const material = materials.find((item) => item.id === materialId);
    if (material) {
      setQaContextTargetId(material.target_id);
    }
  }

  function handleSelectPracticeTarget(targetId: number) {
    setPracticeContextTargetId(targetId);
    setPracticeContextMaterialId((current) => {
      const materialStillInTarget = materials.some((material) => material.id === current && material.target_id === targetId);
      return materialStillInTarget ? current : null;
    });
    setPracticeSubView("questions");
    setQuestionBatchContext(null);
    setQuestions([]);
    setTestResult(null);
  }

  function handleSelectPracticeMaterial(materialId: number | null) {
    setPracticeContextMaterialId(materialId);
    const material = materials.find((item) => item.id === materialId);
    if (material) {
      setPracticeContextTargetId(material.target_id);
    }
    setPracticeSubView("questions");
    setQuestionBatchContext(null);
    setQuestions([]);
    setTestResult(null);
  }

  useEffect(() => {
    if (!selectedTargetId || !user) {
      setKnowledgeGraph(null);
      setTargetKnowledge(null);
      return;
    }

    void Promise.all([
      api.getKnowledgeGraph(selectedTargetId).catch(() => null),
      api.listTestRecords(1, 10, selectedTargetId).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 })),
      api.getLatestKnowledge({ targetId: selectedTargetId }).catch(() => null)
    ]).then(([graphData, recordData, extractionData]) => {
      setKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
      setTestRecords(recordData.items);
      setTargetKnowledge(extractionData);
    });
  }, [selectedTargetId, user]);

  useEffect(() => {
    if (!graphContextTargetIdEffective || !user) {
      setGraphKnowledgeGraph(null);
      setGraphTargetKnowledge(null);
      return;
    }

    void Promise.all([
      api.getKnowledgeGraph(graphContextTargetIdEffective).catch(() => null),
      api.getLatestKnowledge({ targetId: graphContextTargetIdEffective }).catch(() => null)
    ]).then(([graphData, extractionData]) => {
      setGraphKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
      setGraphTargetKnowledge(extractionData);
    });
  }, [graphContextTargetIdEffective, user]);

  useEffect(() => {
    if (!qaContextTargetIdEffective || !user) {
      setQaKnowledgeGraph(null);
      return;
    }
    void api.getKnowledgeGraph(qaContextTargetIdEffective).then(setQaKnowledgeGraph).catch(() => setQaKnowledgeGraph(null));
  }, [qaContextTargetIdEffective, user]);

  useEffect(() => {
    if (!practiceContextTargetIdEffective || !user) {
      setPracticeKnowledgeGraph(null);
      return;
    }
    void api.getKnowledgeGraph(practiceContextTargetIdEffective).then(setPracticeKnowledgeGraph).catch(() => setPracticeKnowledgeGraph(null));
  }, [practiceContextTargetIdEffective, user]);

  useEffect(() => {
    if (view !== "qa" || !user) {
      return;
    }
    void loadQaHistoryForCurrentContext();
  }, [view, qaContextMaterialIdEffective, qaContextTargetIdEffective, user]);

  useEffect(() => {
    if (view !== "wrong" || !user) {
      return;
    }
    void loadWrongQuestions();
  }, [view, wrongQuestionFilters, user]);

  useEffect(() => {
    setQaFocusedKnowledgePointIds((current) =>
      current.filter((id) => qaKnowledgePointCandidateIds.has(id))
    );
  }, [qaKnowledgePointCandidateIds]);

  useEffect(() => {
    setPracticeFocusedKnowledgePointIds((current) =>
      current.filter((id) => practiceKnowledgePointCandidateIds.has(id))
    );
  }, [practiceKnowledgePointCandidateIds]);

  useEffect(() => {
    if (view !== "graph" || !graphContextMaterialIdEffective || !user) {
      setGraphMaterialKnowledgeLoading(false);
      setGraphMaterialKnowledgeError(null);
      setGraphMaterialKnowledge(null);
      return;
    }

    const material = graphContextMaterial;
    if (!material || material.parse_status !== "parsed") {
      setGraphMaterialKnowledgeLoading(false);
      setGraphMaterialKnowledgeError(null);
      setGraphMaterialKnowledge(null);
      return;
    }

    let ignore = false;
    setGraphMaterialKnowledgeLoading(true);
    setGraphMaterialKnowledgeError(null);
    void api
      .getLatestKnowledge({ materialId: material.id })
      .catch(() => null)
      .then((existing) => existing ?? api.extractKnowledge({ materialId: material.id }))
      .then((extractionData) => {
        if (ignore) return;
        setGraphMaterialKnowledge(extractionData);
        setGraphMaterialKnowledgeLoading(false);
      })
      .catch((error) => {
        if (ignore) return;
        setGraphMaterialKnowledgeLoading(false);
        setGraphMaterialKnowledgeError(readMessage(error));
      });

    return () => {
      ignore = true;
    };
  }, [graphContextMaterial?.id, graphContextMaterial?.parse_status, graphContextMaterialIdEffective, user, view]);

  useEffect(() => {
    if (!user) {
      parsePollAttemptsRef.current.clear();
      return;
    }

    const parsingIds = materials.filter((material) => material.parse_status === "parsing").map((material) => material.id);
    if (!parsingIds.length) {
      parsePollAttemptsRef.current.clear();
      return;
    }

    for (const [materialId] of parsePollAttemptsRef.current) {
      if (!parsingIds.includes(materialId)) {
        parsePollAttemptsRef.current.delete(materialId);
      }
    }

    const newParsingIds = parsingIds.filter((materialId) => !parsePollAttemptsRef.current.has(materialId));
    newParsingIds.forEach((materialId) => {
      void pollMaterialParseStatus(materialId);
    });

    const intervalId = window.setInterval(() => {
      parsingIds.forEach((materialId) => {
        void pollMaterialParseStatus(materialId);
      });
    }, parsePollIntervalMs);

    return () => window.clearInterval(intervalId);
  }, [materials, user]);

  async function initializeSession() {
    setLoading(true);
    try {
      const me = await api.me();
      setUser(me.user);
      await loadDataForUser(me.user);
      setNotice({ tone: "success", text: "已使用本地 token 初始化会话。" });
    } catch (error) {
      clearToken();
      setUser(null);
      setNotice({ tone: "danger", text: `登录状态无效：${readMessage(error)}` });
    } finally {
      setLoading(false);
    }
  }

  async function loadDataForUser(nextUser: User) {
    if (nextUser.role === "admin") {
      setAdminView("overview");
      await loadAdminData();
      return;
    }

    setHealth({});
    setView("dashboard");
    await loadDashboardData();
  }

  async function loadAdminData() {
    const [summary, users, materialsData, tasks, logs] = await Promise.all([
      api.getAdminSummary(),
      api.listAdminUsers(1, 50),
      api.listAdminMaterials(1, 50),
      api.listAdminTasks(1, 50),
      api.listAdminLogs(1, 50)
    ]);
    setAdminSummary(summary);
    setAdminUsers(users.items);
    setAdminMaterials(materialsData.items);
    setAdminTasks(tasks.items);
    setAdminLogs(logs.items);
    await loadAdminHealth();
  }

  async function loadDashboardData() {
    const [targetData, materialData, wrongData, planData, usageSummary, usageLogs] = await Promise.all([
      api.listTargets(),
      api.listMaterials(),
      api.listWrongQuestions().catch(() => ({ items: [], total: 0, page: 1, page_size: 10 })),
      api.listReviewPlans().catch(() => ({ items: [], total: 0, page: 1, page_size: 20 })),
      api.getAiUsageSummary().catch(() => null),
      api.listAiUsageLogs(1, 20).catch(() => ({ items: [], total: 0, page: 1, page_size: 20 }))
    ]);

    setTargets(targetData.items);
    setMaterials(materialData.items);
    setWrongQuestions(wrongData.items);
    setReviewPlans(planData.items);
    setAiUsageSummary(usageSummary);
    setAiUsageLogs(usageLogs.items);

    const firstTargetId = targetData.items[0]?.id;
    const [recordData, graphData] = await Promise.all([
      api.listTestRecords(1, 10, firstTargetId).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 })),
      firstTargetId ? api.getKnowledgeGraph(firstTargetId).catch(() => null) : Promise.resolve(null)
    ]);
    setTestRecords(recordData.items);
    setKnowledgeGraph(graphData);
    setGraphKnowledgeGraph((current) => current ?? graphData);
    setQaKnowledgeGraph((current) => current ?? graphData);
    setPracticeKnowledgeGraph((current) => current ?? graphData);

    const nextTargetId = targetData.items[0]?.id ?? null;
    const nextMaterialId = materialData.items.find((item) => item.target_id === nextTargetId)?.id ?? null;
    setSelectedTargetId((current) => current ?? nextTargetId);
    setSelectedMaterialId((current) => current ?? nextMaterialId);
    setGraphContextTargetId((current) => current ?? nextTargetId);
    setGraphContextMaterialId((current) => current ?? nextMaterialId);
    setQaContextTargetId((current) => current ?? nextTargetId);
    setQaContextMaterialId((current) => current ?? nextMaterialId);
    setPracticeContextTargetId((current) => current ?? nextTargetId);
    setPracticeContextMaterialId((current) => current ?? nextMaterialId);
  }

  async function loadAiUsage(targetId?: number, materialId?: number) {
    setAiUsageLoading(true);
    setAiUsageError(null);
    try {
      const [summary, logs] = await Promise.all([
        api.getAiUsageSummary(targetId, materialId),
        api.listAiUsageLogs(1, 20, targetId, materialId)
      ]);
      setAiUsageSummary(summary);
      setAiUsageLogs(logs.items);
    } catch (error) {
      setAiUsageError(readMessage(error));
    } finally {
      setAiUsageLoading(false);
    }
  }

  async function loadWrongQuestions(filters = wrongQuestionFilters) {
    setWrongQuestionsLoading(true);
    try {
      const data = await api.listWrongQuestions(
        1,
        100,
        filters.targetId ?? undefined,
        filters.materialId ?? undefined,
        filters.knowledgePointId ?? undefined,
        filters.masteryStatus || undefined
      );
      setWrongQuestions(data.items);
    } catch (error) {
      setNotice({ tone: "danger", text: `错题加载失败：${readMessage(error)}` });
    } finally {
      setWrongQuestionsLoading(false);
    }
  }

  async function loadQaHistoryForCurrentContext(context?: { materialId?: number | null; targetId?: number | null }) {
    const materialId = context?.materialId !== undefined ? context.materialId : qaContextMaterialIdEffective;
    const targetId = context?.targetId !== undefined ? context.targetId : qaContextTargetIdEffective;

    if (!materialId && !targetId) {
      setQaRecords([]);
      setQaHistoryError(null);
      setQaHistoryLoading(false);
      return;
    }

    setQaHistoryLoading(true);
    setQaHistoryError(null);
    try {
      const data = materialId
        ? await api.listQaHistory(1, 10, materialId)
        : await api.listQaHistory(1, 10, undefined, targetId ?? undefined);
      setQaRecords(data.items);
    } catch (error) {
      setQaRecords([]);
      setQaHistoryError(readMessage(error));
    } finally {
      setQaHistoryLoading(false);
    }
  }

  async function loadAdminHealth() {
    const [apiStatus, dbStatus, redisStatus] = await Promise.allSettled([api.health(), api.healthDb(), api.healthRedis()]);
    setHealth({
      api: apiStatus.status === "fulfilled" ? normalizeHealthStatus(apiStatus.value) : { status: "error" },
      db: dbStatus.status === "fulfilled" ? normalizeHealthStatus(dbStatus.value, "db") : { status: "error" },
      redis: redisStatus.status === "fulfilled" ? normalizeHealthStatus(redisStatus.value, "redis") : { status: "error" }
    });
  }

  async function loadMaterialContext(materialId: number) {
    try {
      const [detailData, previewData, sourceFileBlob, structuredData, extractionData] = await Promise.all([
        api.getMaterial(materialId),
        api.getMaterialPreview(materialId).catch(() => null),
        api.getMaterialFile(materialId).catch(() => null),
        api.getMaterialStructured(materialId).catch(() => null),
        api.getLatestKnowledge({ materialId }).catch(() => null)
      ]);

      setMaterials((current) => current.map((item) => (item.id === materialId ? detailData.material : item)));
      if (previewData) {
        setPreview(previewData);
      }
      if (sourceFileBlob) {
        setSourcePreview({
          materialId,
          url: URL.createObjectURL(sourceFileBlob),
          contentType: sourceFileBlob.type,
          fileType: detailData.material.file_type
        });
      } else {
        setSourcePreview(null);
      }
      setStructured(structuredData);
      setKnowledge(extractionData);
    } catch (error) {
      setPreview(null);
      setSourcePreview(null);
      setStructured(null);
      setNotice({ tone: "danger", text: `资料上下文加载失败：${readMessage(error)}` });
    }
  }

  async function refreshMaterialLearningContext(material: Material) {
    if (selectedMaterialId === material.id) {
      const [previewData, structuredData, materialExtraction] = await Promise.all([
        api.getMaterialPreview(material.id).catch(() => null),
        api.getMaterialStructured(material.id).catch(() => null),
        api.getLatestKnowledge({ materialId: material.id }).catch(() => null)
      ]);
      setPreview(previewData);
      setStructured(structuredData);
      setKnowledge(materialExtraction);
    }

    const [graphData, extractionData] = await Promise.all([
      api.getKnowledgeGraph(material.target_id).catch(() => null),
      api.getLatestKnowledge({ targetId: material.target_id }).catch(() => null)
    ]);

    if (selectedTargetId === material.target_id || selectedMaterialId === material.id) {
      setKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
      if (extractionData) {
        setTargetKnowledge(extractionData);
      }
    }
    if (graphContextTargetIdEffective === material.target_id) {
      setGraphKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
      setGraphTargetKnowledge(extractionData);
    }
    if (qaContextTargetIdEffective === material.target_id) {
      setQaKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
    }
    if (practiceContextTargetIdEffective === material.target_id) {
      setPracticeKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
    }
    if (selectedMaterialId === material.id) {
      const refreshedMaterialExtraction = await api.getLatestKnowledge({ materialId: material.id }).catch(() => null);
      if (refreshedMaterialExtraction) {
        setKnowledge(refreshedMaterialExtraction);
        if (graphContextMaterialIdEffective === material.id) {
          setGraphMaterialKnowledge(refreshedMaterialExtraction);
        }
      }
    }

    let job = await api
      .getLatestKnowledgeJob({
        targetId: material.target_id,
        materialId: material.id,
        jobType: "target_refresh_pipeline"
      })
      .catch(() => null);
    if (!job) {
      job = await api
        .getLatestKnowledgeJob({
          targetId: material.target_id,
          jobType: "target_refresh_pipeline"
        })
        .catch(() => null);
    }
    if (job && (job.status === "pending" || job.status === "running")) {
      void waitForKnowledgeJob(job, {
        targetId: material.target_id,
        materialId: material.id,
        successMessage: "知识提炼和图谱刷新已完成。"
      });
    }
  }

  async function refreshKnowledgeViews(targetId: number, materialId?: number | null) {
    const [graphData, targetExtraction, materialExtraction] = await Promise.all([
      api.getKnowledgeGraph(targetId).catch(() => null),
      api.getLatestKnowledge({ targetId }).catch(() => null),
      materialId ? api.getLatestKnowledge({ materialId }).catch(() => null) : Promise.resolve(null)
    ]);
    setKnowledgeGraph(targetExtraction?.knowledge_graph ?? graphData);
    if (targetExtraction) {
      setTargetKnowledge(targetExtraction);
    }
    if (graphContextTargetIdEffective === targetId) {
      setGraphKnowledgeGraph(targetExtraction?.knowledge_graph ?? graphData);
      setGraphTargetKnowledge(targetExtraction);
    }
    if (qaContextTargetIdEffective === targetId) {
      setQaKnowledgeGraph(targetExtraction?.knowledge_graph ?? graphData);
    }
    if (practiceContextTargetIdEffective === targetId) {
      setPracticeKnowledgeGraph(targetExtraction?.knowledge_graph ?? graphData);
    }
    if (materialExtraction) {
      setKnowledge(materialExtraction);
      if (graphContextMaterialIdEffective === materialId) {
        setGraphMaterialKnowledge(materialExtraction);
      }
    }
  }

  async function waitForKnowledgeJob(
    initialJob: KnowledgeJob,
    options: { targetId: number; materialId?: number | null; successMessage?: string }
  ) {
    setActiveKnowledgeJob(initialJob);
    setKnowledgeRefreshing(true);
    let currentJob = initialJob;
    try {
      for (let attempt = 0; attempt < knowledgeJobPollMaxAttempts; attempt += 1) {
        currentJob = await api.getKnowledgeJob(initialJob.id);
        setActiveKnowledgeJob(currentJob);
        if (currentJob.status === "succeeded") {
          await refreshKnowledgeViews(options.targetId, options.materialId);
          setNotice({ tone: "success", text: options.successMessage ?? "知识任务已完成，图谱已刷新。" });
          return currentJob;
        }
        if (currentJob.status === "failed") {
          throw new Error(currentJob.error_message ?? "知识任务执行失败");
        }
        await sleep(knowledgeJobPollIntervalMs);
      }
      setNotice({ tone: "warning", text: "知识任务仍在后台执行，可稍后刷新查看结果。" });
      return currentJob;
    } finally {
      setKnowledgeRefreshing(false);
    }
  }

  async function pollMaterialParseStatus(materialId: number) {
    if (parsePollInFlightRef.current.has(materialId)) {
      return;
    }

    const attempts = (parsePollAttemptsRef.current.get(materialId) ?? 0) + 1;
    if (attempts > parsePollMaxAttempts) {
      parsePollAttemptsRef.current.delete(materialId);
      setNotice({ tone: "warning", text: "资料仍在解析中，可稍后刷新或进入资料详情查看最新状态。" });
      return;
    }
    parsePollAttemptsRef.current.set(materialId, attempts);
    parsePollInFlightRef.current.add(materialId);

    try {
      const data = await api.getMaterial(materialId);
      setMaterials((current) => current.map((item) => (item.id === materialId ? data.material : item)));

      if (data.material.parse_status === "parsed") {
        parsePollAttemptsRef.current.delete(materialId);
        await refreshMaterialLearningContext(data.material);
        setNotice({
          tone: data.material.parse_warning ? "warning" : "success",
          text: data.material.parse_warning
            ? "资料解析完成，已提交知识刷新任务；解析质量可能影响 AI 回答和出题。"
            : "资料解析完成，已提交知识提炼和图谱刷新任务。"
        });
      } else if (data.material.parse_status === "failed") {
        parsePollAttemptsRef.current.delete(materialId);
        if (selectedMaterialId === materialId) {
          setPreview(null);
          setSourcePreview(null);
          setStructured(null);
        }
        setNotice({ tone: "danger", text: data.material.parse_error ?? "资料解析失败，可检查文件后重试。" });
      }
    } catch {
      if (attempts >= parsePollMaxAttempts) {
        setNotice({ tone: "warning", text: "资料解析状态暂时无法同步，请稍后刷新页面重试。" });
      }
    } finally {
      parsePollInFlightRef.current.delete(materialId);
    }
  }

  async function handleLogin(formData: FormData) {
    const username = String(formData.get("username") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const loginRole = String(formData.get("login_role") ?? "student") as LoginRole;
    if (!username || !password) {
      setNotice({ tone: "danger", text: "请输入用户名和密码。" });
      return;
    }

    setLoading(true);
    try {
      const nextUser = await api.login(username, password);
      if (loginRole === "admin" && nextUser.role !== "admin") {
        clearToken();
        setUser(null);
        setHealth({});
        setNotice({ tone: "danger", text: "该账号不是管理员，请使用管理员账号登录。" });
        return;
      }
      setUser(nextUser);
      await loadDataForUser(nextUser);
      setNotice({ tone: "success", text: nextUser.role === "admin" ? "管理员登录成功。" : "登录成功，已同步后端数据。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `登录失败：${readMessage(error)}` });
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(formData: FormData) {
    const username = String(formData.get("username") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const displayName = String(formData.get("display_name") ?? "").trim();
    if (!username || !password) {
      setNotice({ tone: "danger", text: "请输入用户名和密码。" });
      return;
    }

    setLoading(true);
    try {
      await api.register(username, password, displayName || username);
      const nextUser = await api.login(username, password);
      setUser(nextUser);
      await loadDataForUser(nextUser);
      setNotice({ tone: "success", text: "注册成功，已自动登录。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `注册失败：${readMessage(error)}` });
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTarget(formData: FormData) {
    const payload = {
      title: String(formData.get("title") ?? "").trim(),
      subject: emptyToUndefined(formData.get("subject")),
      target_type: String(formData.get("target_type") ?? "exam") as StudyTarget["target_type"],
      exam_date: normalizeDateInput(formData.get("exam_date")),
      review_goal: emptyToUndefined(formData.get("review_goal")),
      description: emptyToUndefined(formData.get("description"))
    };

    try {
      const data = await api.createTarget(payload);
      setTargets((current) => [data.target, ...current]);
      setSelectedTargetId(data.target.id);
      setGraphContextTargetId((current) => current ?? data.target.id);
      setQaContextTargetId((current) => current ?? data.target.id);
      setPracticeContextTargetId((current) => current ?? data.target.id);
      setNotice({ tone: "success", text: "目标创建成功。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `目标创建失败：${readMessage(error)}` });
    }
  }

  async function handleUpdateTarget(targetId: number, payload: Partial<StudyTarget>) {
    try {
      const data = await api.updateTarget(targetId, payload);
      setTargets((current) => current.map((item) => (item.id === targetId ? data.target : item)));
      setNotice({ tone: "success", text: "目标已更新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `目标更新失败：${readMessage(error)}` });
    }
  }

  async function handleDeleteTarget(targetId: number) {
    try {
      await api.deleteTarget(targetId);
      const nextTargets = targets.filter((item) => item.id !== targetId);
      setTargets(nextTargets);
      if (selectedTargetId === targetId) {
        setSelectedTargetId(nextTargets[0]?.id ?? null);
      }
      if (graphContextTargetId === targetId) {
        setGraphContextTargetId(nextTargets[0]?.id ?? null);
        setGraphContextMaterialId(null);
      }
      if (qaContextTargetId === targetId) {
        setQaContextTargetId(nextTargets[0]?.id ?? null);
        setQaContextMaterialId(null);
      }
      if (practiceContextTargetId === targetId) {
        setPracticeContextTargetId(nextTargets[0]?.id ?? null);
        setPracticeContextMaterialId(null);
      }
      setNotice({ tone: "info", text: "目标已删除。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `目标删除失败：${readMessage(error)}` });
    }
  }

  async function handleUploadMaterial(formData: FormData) {
    const file = formData.get("file");
    const targetId = selectedTargetId;
    if (!(file instanceof File) || !targetId) {
      setNotice({ tone: "danger", text: "请先选择目标和资料文件。" });
      return;
    }

    try {
      const data = await api.uploadMaterial(targetId, file);
      setMaterials((current) => [data.material, ...current]);
      setSelectedMaterialId(data.material.id);
      setSelectedTargetId(data.material.target_id);
      setNotice({ tone: "success", text: "资料上传成功，已开始后台解析；页面会自动刷新解析状态。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `资料上传失败：${readMessage(error)}` });
    }
  }

  async function handleDeleteMaterial(materialId: number) {
    try {
      await api.deleteMaterial(materialId);
      const deletedMaterial = materials.find((item) => item.id === materialId);
      const nextMaterials = materials.filter((item) => item.id !== materialId);
      setMaterials(nextMaterials);
      if (selectedMaterialId === materialId) {
        const nextMaterialInTarget = nextMaterials.find((item) => item.target_id === deletedMaterial?.target_id) ?? null;
        setSelectedMaterialId(nextMaterialInTarget?.id ?? null);
        if (view === "detail") {
          setView("materials");
        }
      }
      if (graphContextMaterialId === materialId) {
        setGraphContextMaterialId(null);
      }
      if (qaContextMaterialId === materialId) {
        setQaContextMaterialId(null);
      }
      if (practiceContextMaterialId === materialId) {
        setPracticeContextMaterialId(null);
      }
      setNotice({ tone: "info", text: "资料已删除。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `资料删除失败：${readMessage(error)}` });
    }
  }

  async function handleParseMaterial(materialId: number) {
    setMaterials((current) =>
      current.map((item) =>
        item.id === materialId ? { ...item, parse_status: "parsing", parse_error: null, parse_warning: null } : item
      )
    );
    parsePollAttemptsRef.current.set(materialId, 0);

    try {
      const data = await api.parseMaterial(materialId);
      setMaterials((current) => current.map((item) => (item.id === materialId ? data.material : item)));
      if (data.material.parse_status === "parsed") {
        await refreshMaterialLearningContext(data.material);
        setNotice({
          tone: data.material.parse_warning ? "warning" : "success",
          text: data.material.parse_warning
            ? "资料解析完成，已提交知识刷新任务；解析质量可能影响 AI 回答和出题。"
            : "资料解析完成，已提交知识提炼和图谱刷新任务。"
        });
      } else if (data.material.parse_status === "failed") {
        setNotice({ tone: "danger", text: data.material.parse_error ?? "资料解析失败。" });
      } else if (data.material.parse_status === "parsing") {
        setNotice({ tone: "info", text: "资料正在后台解析，完成后会自动刷新。" });
      } else {
        setNotice({ tone: "info", text: "已提交后台解析任务，页面会自动刷新解析状态。" });
      }
    } catch (error) {
      await loadDashboardData().catch(() => undefined);
      setNotice({ tone: "danger", text: `资料解析失败：${readMessage(error)}` });
    }
  }

  async function handleRefreshSelectedMaterialKnowledge() {
    if (!selectedMaterial) {
      return;
    }
    if (selectedMaterial.parse_status === "parsing") {
      setNotice({ tone: "info", text: "资料仍在解析中，请等待完成后再重新提炼。" });
      return;
    }
    if (selectedMaterial.parse_status !== "parsed") {
      await handleParseMaterial(selectedMaterial.id);
      return;
    }

    setKnowledgeRefreshing(true);
    setNotice({ tone: "info", text: "已提交资料知识提炼和图谱刷新任务..." });
    try {
      const materialJob = await api.createMaterialExtractJob(selectedMaterial.id);
      await waitForKnowledgeJob(materialJob, {
        targetId: selectedMaterial.target_id,
        materialId: selectedMaterial.id,
        successMessage: "资料级知识提炼已完成。"
      });
      const graphJob = await api.createGraphRefreshJob(
        selectedMaterial.target_id,
        selectedMaterial.id,
        true,
        30
      );
      await waitForKnowledgeJob(graphJob, {
        targetId: selectedMaterial.target_id,
        materialId: selectedMaterial.id,
        successMessage: "资料知识提炼和图谱增量刷新已完成。"
      });
    } catch (error) {
      setNotice({ tone: "danger", text: `知识提炼失败：${readMessage(error)}` });
    } finally {
      setKnowledgeRefreshing(false);
    }
  }

  async function handleAskQuestion(formData: FormData) {
    const scope = String(formData.get("qa_scope") ?? "target");
    const knowledgePointIds =
      scope === "knowledge_point"
        ? formData.getAll("knowledge_point_ids").map(Number).filter(Boolean)
        : [];
    const question = String(formData.get("question") ?? "").trim();
    if (!question) {
      return;
    }
    if (aiPendingActions.qa) {
      return;
    }

    if (scope === "material" && qaContextMaterial?.parse_status !== "parsed") {
      setNotice({ tone: "danger", text: "当前资料尚未解析完成，不能按资料提问。" });
      return;
    }
    if (scope !== "material" && !qaContextTargetIdEffective) {
      setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
      return;
    }
    if (scope === "knowledge_point" && !knowledgePointIds.length) {
      setNotice({ tone: "danger", text: "请选择至少一个知识点。" });
      return;
    }

    setAiPendingActions((current) => ({ ...current, qa: true }));
    try {
      const data = await api.askQuestion(
        scope === "material"
          ? { materialId: qaContextMaterial?.id, question }
          : { targetId: qaContextTargetIdEffective ?? undefined, knowledgePointIds, question }
      );
      await loadQaHistoryForCurrentContext({
        materialId: qaContextMaterialIdEffective,
        targetId: qaContextTargetIdEffective
      });
      setQaRecords((current) =>
        current.some((record) => record.qa_record_id === data.qa_record_id)
          ? current
          : [data, ...current]
      );
      setNotice({ tone: "success", text: "问答已生成并写入历史。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `问答失败：${readMessage(error)}` });
    } finally {
      setAiPendingActions((current) => ({ ...current, qa: false }));
    }
  }

  async function handleGenerateQuestions(formData: FormData) {
    const scope = String(formData.get("question_scope") ?? "target");
    if (aiPendingActions.questions || aiPendingActions.test) {
      return;
    }
    try {
      const difficulty = String(formData.get("difficulty") ?? "medium") as Difficulty;
      const count = Number(formData.get("count") ?? 5);
      const questionTypes = formData.getAll("question_types").map(String) as QuestionType[];
      const knowledgePointIds = formData.getAll("knowledge_point_ids").map(Number).filter(Boolean);
      const extraRequirement = String(formData.get("extra_requirement") ?? "").trim();
      if (!questionTypes.length) {
        setNotice({ tone: "danger", text: "请至少选择一种题型。" });
        return;
      }
      if (scope === "material" && practiceContextMaterial?.parse_status !== "parsed") {
        setNotice({ tone: "danger", text: "当前资料尚未解析完成，不能按资料出题。" });
        return;
      }
      if (scope !== "material" && !practiceContextTargetIdEffective) {
        setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
        return;
      }
      if (scope === "knowledge_point" && !knowledgePointIds.length) {
        setNotice({ tone: "danger", text: "请选择至少一个知识点。" });
        return;
      }

      setAiPendingActions((current) => ({ ...current, questions: true }));
      setTestResult(null);
      setPracticeSubView("questions");
      setQuestionBatchContext(null);
      const data = await api.generateQuestions({
        materialId: scope === "material" ? practiceContextMaterial?.id : undefined,
        targetId: scope === "material" ? undefined : practiceContextTargetIdEffective ?? undefined,
        knowledgePointIds: scope === "knowledge_point" ? knowledgePointIds : [],
        extraRequirement,
        count,
        difficulty,
        questionTypes
      });
      if (!data.material_id) {
        setNotice({ tone: "danger", text: "题目生成成功但缺少资料归属，无法提交自测。" });
        setQuestions(data.questions);
        setView("practice");
        return;
      }
      const batchTargetId = data.target_id ?? practiceContextMaterial?.target_id ?? practiceContextTargetIdEffective ?? null;
      setQuestionBatchContext({
        materialId: data.material_id,
        targetId: batchTargetId,
        scope: scope === "material" ? "material" : scope === "knowledge_point" ? "knowledge_point" : "target"
      });
      setQuestions(data.questions);
      setView("practice");
      setNotice({ tone: "success", text: scope === "material" ? "题目已按资料生成。" : "题目已按目标/知识点生成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `题目生成失败：${readMessage(error)}` });
    } finally {
      setAiPendingActions((current) => ({ ...current, questions: false }));
    }
  }

  async function handleSubmitTest(answers: TestSubmitAnswer[]) {
    if (!questionBatchContext) {
      setNotice({ tone: "danger", text: "请先生成题目，再提交自测。" });
      return;
    }
    if (aiPendingActions.questions || aiPendingActions.test) {
      return;
    }
    setAiPendingActions((current) => ({ ...current, test: true }));
    try {
      const data = await api.submitTest(questionBatchContext.materialId, questionBatchContext.targetId, answers);
      setTestResult(data);
      setPracticeSubView("results");
      setView("practice");
      setNotice({ tone: "success", text: "自测已提交。" });
      const wrongData = await api
        .listWrongQuestions(1, 10, questionBatchContext.targetId ?? undefined, questionBatchContext.materialId)
        .catch(() => null);
      if (wrongData) {
        setWrongQuestions(wrongData.items);
      }
      if (questionBatchContext.targetId) {
        const graph = await api.getKnowledgeGraph(questionBatchContext.targetId).catch(() => null);
        setKnowledgeGraph(graph);
        if (graphContextTargetIdEffective === questionBatchContext.targetId) {
          setGraphKnowledgeGraph(graph);
        }
        if (qaContextTargetIdEffective === questionBatchContext.targetId) {
          setQaKnowledgeGraph(graph);
        }
        if (practiceContextTargetIdEffective === questionBatchContext.targetId) {
          setPracticeKnowledgeGraph(graph);
        }
      }
    } catch (error) {
      setNotice({ tone: "danger", text: `自测提交失败：${readMessage(error)}` });
    } finally {
      setAiPendingActions((current) => ({ ...current, test: false }));
    }
  }

  async function handleUpdateMastery(id: number, masteryStatus: WrongQuestion["mastery_status"]) {
    try {
      const updated = await api.updateWrongQuestionMastery(id, masteryStatus);
      setWrongQuestions((current) => current.map((item) => (item.id === id ? updated : item)));
      setWrongReviewQueue((current) => current.map((item) => (item.id === id ? updated : item)));
      setNotice({ tone: "info", text: "错题掌握状态已更新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `错题状态更新失败：${readMessage(error)}` });
    }
  }

  function handleWrongQuestionFiltersChange(nextFilters: WrongQuestionFilters) {
    setWrongQuestionFilters(nextFilters);
    setWrongRedoResult(null);
  }

  async function handleStartWrongReview() {
    setWrongReviewLoading(true);
    setWrongRedoResult(null);
    try {
      const queue = await api.listWrongQuestionReviewQueue(
        wrongQuestionFilters.targetId ?? undefined,
        wrongQuestionFilters.knowledgePointId ?? undefined,
        10
      );
      setWrongReviewQueue(queue);
      setWrongReviewIndex(0);
      setWrongBookMode("review");
      setNotice({
        tone: queue.length ? "success" : "warning",
        text: queue.length ? "已生成错题复习队列。" : "当前筛选条件下暂无可复习错题。"
      });
    } catch (error) {
      setNotice({ tone: "danger", text: `错题复习队列生成失败：${readMessage(error)}` });
    } finally {
      setWrongReviewLoading(false);
    }
  }

  async function handleRedoWrongQuestion(id: number, answer: TestSubmitAnswer) {
    setWrongRedoSubmitting(true);
    setWrongRedoResult(null);
    try {
      const data = await api.redoWrongQuestion(id, answer);
      setWrongRedoResult(data.result);
      setQuestionExplainAnswers((current) => {
        const next = { ...current };
        delete next[data.result.question_id];
        return next;
      });
      setWrongQuestions((current) =>
        current.map((item) => (item.id === id ? data.wrong_question : item))
      );
      setWrongReviewQueue((current) =>
        current.map((item) => (item.id === id ? data.wrong_question : item))
      );
      setNotice({ tone: "success", text: "错题重做已评分，掌握状态已更新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `错题重做失败：${readMessage(error)}` });
    } finally {
      setWrongRedoSubmitting(false);
    }
  }

  async function handleExplainQuestion(questionId: number, question: string) {
    const trimmed = question.trim();
    if (!trimmed || questionExplainLoading[questionId]) {
      return;
    }
    setQuestionExplainLoading((current) => ({ ...current, [questionId]: true }));
    try {
      const data = await api.explainQuestion(questionId, trimmed);
      setQuestionExplainAnswers((current) => ({ ...current, [questionId]: data.answer }));
    } catch (error) {
      setQuestionExplainAnswers((current) => ({
        ...current,
        [questionId]: `AI 追问失败：${readMessage(error)}`
      }));
    } finally {
      setQuestionExplainLoading((current) => ({ ...current, [questionId]: false }));
    }
  }

  async function handleGenerateReviewPlan(formData: FormData) {
    const targetId = Number(formData.get("target_id"));
    const startDate = normalizeDateInput(formData.get("start_date")) ?? "";
    const endDate = normalizeDateInput(formData.get("end_date")) ?? "";
    if (aiPendingActions.plan) {
      return;
    }
    setAiPendingActions((current) => ({ ...current, plan: true }));
    try {
      const plan = await api.generateReviewPlan(targetId, startDate, endDate);
      setReviewPlans((current) => [plan, ...current.filter((item) => item.id !== plan.id)]);
      setView("plans");
      setNotice({ tone: "success", text: "复习计划已生成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `复习计划生成失败：${readMessage(error)}` });
    } finally {
      setAiPendingActions((current) => ({ ...current, plan: false }));
    }
  }

  async function handleToggleReviewPlanTask(taskId: number, completed: boolean) {
    if (updatingReviewPlanTaskIds.has(taskId)) {
      return;
    }
    setUpdatingReviewPlanTaskIds((current) => new Set(current).add(taskId));
    try {
      const updated = await api.updateReviewPlanTask(taskId, completed);
      setReviewPlans((current) =>
        current.map((plan) => ({
          ...plan,
          tasks: sortReviewPlanTasks(
            plan.tasks.map((task) => (task.id === updated.id ? updated : task))
          )
        }))
      );
      setNotice({ tone: "success", text: completed ? "复习任务已标为完成。" : "复习任务已取消完成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `复习任务状态更新失败：${readMessage(error)}` });
    } finally {
      setUpdatingReviewPlanTaskIds((current) => {
        const next = new Set(current);
        next.delete(taskId);
        return next;
      });
    }
  }

  async function handleGenerateKnowledgeGraph() {
    if (!graphContextTargetIdEffective) {
      setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
      return;
    }

    setKnowledgeRefreshing(true);
    setNotice({ tone: "info", text: "已提交知识图谱刷新任务..." });
    try {
      const focusMaterialId =
        graphContextMaterial?.target_id === graphContextTargetIdEffective && graphContextMaterial.parse_status === "parsed"
          ? graphContextMaterial.id
          : undefined;
      const graphJob = await api.createGraphRefreshJob(
        graphContextTargetIdEffective,
        focusMaterialId,
        true,
        focusMaterialId ? 30 : 12
      );
      await waitForKnowledgeJob(graphJob, {
        targetId: graphContextTargetIdEffective,
        materialId: focusMaterialId,
        successMessage: focusMaterialId ? "知识图谱已增量刷新。" : "知识图谱已全量刷新。"
      });
      setView("graph");
    } catch (error) {
      setNotice({ tone: "danger", text: `知识图谱生成失败：${readMessage(error)}` });
    } finally {
      setKnowledgeRefreshing(false);
    }
  }

  async function handleUpdateKnowledgePointMastery(id: number, masteryStatus: KnowledgeMasteryStatus) {
    try {
      const updated = await api.updateKnowledgePointMastery(id, masteryStatus);
      setKnowledgeGraph((current) =>
        current
          ? {
              ...current,
              nodes: current.nodes.map((node) =>
                node.id === id
                  ? {
                      ...node,
                      mastery_status: updated.mastery_status,
                      mastery_score: updated.mastery_score,
                      accuracy: updated.accuracy,
                      answered_count: updated.answered_count,
                      wrong_count: updated.wrong_count
                    }
                  : node
              )
            }
          : current
      );
      setGraphKnowledgeGraph((current) =>
        current
          ? {
              ...current,
              nodes: current.nodes.map((node) =>
                node.id === id
                  ? {
                      ...node,
                      mastery_status: updated.mastery_status,
                      mastery_score: updated.mastery_score,
                      accuracy: updated.accuracy,
                      answered_count: updated.answered_count,
                      wrong_count: updated.wrong_count
                    }
                  : node
              )
            }
          : current
      );
      setNotice({ tone: "success", text: "知识点掌握状态已更新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `知识点掌握状态更新失败：${readMessage(error)}` });
    }
  }

  async function handleExport(action: () => Promise<void>, successText: string) {
    try {
      await action();
      setNotice({ tone: "success", text: successText });
    } catch (error) {
      setNotice({ tone: "danger", text: `导出失败：${readMessage(error)}` });
    }
  }

  async function handleRefreshAdminData() {
    try {
      await loadAdminData();
      setNotice({ tone: "success", text: "管理员后台数据已刷新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `管理员后台数据加载失败：${readMessage(error)}` });
    }
  }

  async function handleUpdateAdminUserStatus(userId: number, isActive: boolean) {
    try {
      const updated = await api.updateAdminUserStatus(userId, isActive);
      setAdminUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      await loadAdminData();
      setNotice({ tone: "success", text: `用户已${updated.is_active ? "启用" : "禁用"}。` });
    } catch (error) {
      setNotice({ tone: "danger", text: `用户状态更新失败：${readMessage(error)}` });
    }
  }

  async function handleRetryAdminTask(taskId: number) {
    try {
      await api.retryAdminTask(taskId);
      await loadAdminData();
      setNotice({ tone: "success", text: "失败任务已重新入队。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `任务重试失败：${readMessage(error)}` });
    }
  }

  function handleLogout() {
    clearToken();
    setUser(null);
    setTargets([]);
    setMaterials([]);
    setQaRecords([]);
    setQaHistoryLoading(false);
    setQaHistoryError(null);
    setQuestions([]);
    setTestResult(null);
    setWrongQuestions([]);
    setWrongQuestionFilters({ targetId: null, materialId: null, knowledgePointId: null, masteryStatus: "" });
    setWrongQuestionsLoading(false);
    setWrongBookMode("library");
    setWrongReviewQueue([]);
    setWrongReviewIndex(0);
    setWrongReviewLoading(false);
    setWrongRedoSubmitting(false);
    setWrongRedoResult(null);
    setReviewPlans([]);
    setUpdatingReviewPlanTaskIds(new Set());
    setQuestionExplainAnswers({});
    setQuestionExplainLoading({});
    setKnowledge(null);
    setTargetKnowledge(null);
    setKnowledgeGraph(null);
    setGraphKnowledgeGraph(null);
    setGraphTargetKnowledge(null);
    setGraphMaterialKnowledge(null);
    setQaKnowledgeGraph(null);
    setPracticeKnowledgeGraph(null);
    setStructured(null);
    setTestRecords([]);
    setPreview(null);
    setAiUsageSummary(null);
    setAiUsageLogs([]);
    setAiUsageLoading(false);
    setAiUsageError(null);
    setAiPendingActions(initialAiPendingActions);
    setSourcePreview(null);
    setHealth({});
    setAdminSummary(null);
    setAdminUsers([]);
    setAdminMaterials([]);
    setAdminTasks([]);
    setAdminLogs([]);
    setAdminView("overview");
    setView("dashboard");
    setSelectedTargetId(null);
    setSelectedMaterialId(null);
    setGraphContextTargetId(null);
    setGraphContextMaterialId(null);
    setQaContextTargetId(null);
    setQaContextMaterialId(null);
    setPracticeContextTargetId(null);
    setPracticeContextMaterialId(null);
    setQaScope("target");
    setPracticeScope("target");
    setQaFocusedKnowledgePointIds([]);
    setPracticeFocusedKnowledgePointIds([]);
    setPracticeSubView("questions");
    setQuestionBatchContext(null);
    setNotice({ tone: "info", text: "已退出登录。" });
  }

  if (!user) {
    return (
      <>
        <AuthPage loading={loading} notice={notice} onLogin={handleLogin} onRegister={handleRegister} onCloseNotice={() => setNotice(null)} />
      </>
    );
  }

  if (isAdmin) {
    return (
      <AdminShell
        user={user}
        view={adminView}
        onViewChange={setAdminView}
        notice={notice}
        loading={loading}
        onCloseNotice={() => setNotice(null)}
        onLogout={handleLogout}
        onRefresh={() => void handleRefreshAdminData()}
        health={health}
        summary={adminSummary}
        users={adminUsers}
        materials={adminMaterials}
        tasks={adminTasks}
        logs={adminLogs}
        onUpdateUserStatus={(userId, isActive) => void handleUpdateAdminUserStatus(userId, isActive)}
        onRetryTask={(taskId) => void handleRetryAdminTask(taskId)}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={20} />
          </div>
          <div>
            <strong>AI 备考复习平台</strong>
            <span>学生端学习闭环</span>
          </div>
        </div>

        <nav>
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = view === item.view || (view === "detail" && item.view === "materials");
            return (
              <button key={item.view} className={isActive ? "active" : ""} onClick={() => setView(item.view)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="profile-card">
          <UserCircle size={30} />
          <div>
            <strong>{user.display_name ?? user.username}</strong>
            <span>{user.role}</span>
          </div>
          <button className="icon-button" onClick={handleLogout} title="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{pageTitle(view)}</h1>
          </div>
          <button className="ghost-button" onClick={() => void initializeSession()}>
            <RefreshCw size={16} />
            刷新接口数据
          </button>
        </header>

        {notice ? <NoticeBar notice={notice} onClose={() => setNotice(null)} /> : null}
        {loading ? <LoadingBanner /> : null}

        {view === "dashboard" ? (
          <Dashboard
            targets={targets}
            materials={materials}
            selectedTarget={selectedTarget}
            wrongQuestions={wrongQuestions}
            reviewPlans={reviewPlans}
            testRecords={testRecords}
            knowledgeGraph={knowledgeGraph}
            aiUsageSummary={aiUsageSummary}
            onQuickView={(nextView) => setView(nextView)}
          />
        ) : null}

        {view === "targets" ? (
          <TargetsPage
            targets={targets}
            selectedTargetId={selectedTargetId}
            onSelect={handleSelectLearningTarget}
            onCreate={handleCreateTarget}
            onUpdate={handleUpdateTarget}
            onDelete={handleDeleteTarget}
          />
        ) : null}

        {view === "materials" ? (
          <MaterialsPage
            targets={targets}
            materials={visibleMaterials}
            selectedTarget={selectedTarget}
            selectedTargetId={selectedTargetId}
            selectedMaterialId={selectedMaterialId}
            onSelectTarget={handleSelectLearningTarget}
            onSelect={(material) => {
              handleSelectLearningMaterial(material.id);
              setView("detail");
            }}
            onUpload={handleUploadMaterial}
            onParse={handleParseMaterial}
            onDelete={handleDeleteMaterial}
          />
        ) : null}

        {view === "detail" ? (
          <MaterialDetailPage
            material={selectedMaterial}
            target={selectedTarget}
            preview={preview}
            sourcePreview={sourcePreview}
            knowledge={knowledge}
            knowledgeRefreshing={knowledgeRefreshing}
            onRefreshKnowledge={() => void handleRefreshSelectedMaterialKnowledge()}
            onExportKnowledge={() => {
              if (selectedTargetId) {
                void handleExport(() => api.exportKnowledgeSummary(selectedTargetId), "知识总结已开始下载。");
              }
            }}
            onJumpToQa={() => {
              if (selectedTargetId) {
                setQaContextTargetId(selectedTargetId);
              }
              if (selectedMaterialId) {
                setQaContextMaterialId(selectedMaterialId);
              }
              setView("qa");
            }}
            onJumpToPractice={() => {
              if (selectedTargetId) {
                setPracticeContextTargetId(selectedTargetId);
              }
              if (selectedMaterialId) {
                setPracticeContextMaterialId(selectedMaterialId);
              }
              setPracticeSubView("questions");
              setView("practice");
            }}
            onBack={() => setView("materials")}
          />
        ) : null}

        {view === "graph" ? (
          <KnowledgeGraphPage
            targets={targets}
            materials={materials}
            selectedTargetId={graphContextTargetIdEffective}
            selectedMaterialId={graphContextMaterialIdEffective}
            target={graphContextTarget}
            graph={graphKnowledgeGraph}
            targetKnowledge={graphTargetKnowledge}
            materialKnowledge={graphMaterialKnowledge}
            materialKnowledgeLoading={graphMaterialKnowledgeLoading}
            materialKnowledgeError={graphMaterialKnowledgeError}
            knowledgeRefreshing={knowledgeRefreshing}
            activeKnowledgeJob={activeKnowledgeJob}
            onSelectTarget={handleSelectGraphTarget}
            onSelectMaterial={handleSelectGraphMaterial}
            onGenerate={handleGenerateKnowledgeGraph}
            onUpdatePointMastery={(id, status) => void handleUpdateKnowledgePointMastery(id, status)}
            onFocusQa={(point) => {
              setQaContextTargetId(graphContextTargetIdEffective);
              setQaContextMaterialId(graphContextMaterialIdEffective);
              setQaFocusedKnowledgePointIds([point.id]);
              setQaScope("knowledge_point");
              setView("qa");
            }}
            onFocusPractice={(point) => {
              setPracticeContextTargetId(graphContextTargetIdEffective);
              setPracticeContextMaterialId(graphContextMaterialIdEffective);
              setPracticeFocusedKnowledgePointIds([point.id]);
              setPracticeScope("knowledge_point");
              setPracticeSubView("questions");
              setView("practice");
            }}
            onExport={() => {
              if (graphContextTargetIdEffective) {
                void handleExport(() => api.exportKnowledgeSummary(graphContextTargetIdEffective), "知识总结已开始下载。");
              }
            }}
            onExportAnki={() => {
              if (graphContextTargetIdEffective) {
                void handleExport(() => api.exportAnki(graphContextTargetIdEffective), "Anki CSV 已开始下载。");
              }
            }}
          />
        ) : null}

        {view === "qa" ? (
          <QaPage
            targets={targets}
            materials={materials}
            selectedTargetId={qaContextTargetIdEffective}
            selectedMaterialId={qaContextMaterialIdEffective}
            target={qaContextTarget}
            material={qaContextMaterial}
            knowledgePoints={qaKnowledgePointCandidates}
            focusedKnowledgePoints={qaFocusedKnowledgePoints}
            scope={qaScope}
            records={qaRecords}
            loading={qaHistoryLoading}
            error={qaHistoryError}
            isAsking={aiPendingActions.qa}
            onSelectTarget={handleSelectQaTarget}
            onSelectMaterial={handleSelectQaMaterial}
            onScopeChange={setQaScope}
            onSelectFocusPoint={(pointId) =>
              setQaFocusedKnowledgePointIds((current) =>
                current.includes(pointId)
                  ? current.filter((id) => id !== pointId)
                  : [...current, pointId]
              )
            }
            onAsk={handleAskQuestion}
            onClearFocus={() => setQaFocusedKnowledgePointIds([])}
          />
        ) : null}

        {view === "practice" ? (
          <PracticePage
            targets={targets}
            materials={materials}
            selectedTargetId={practiceContextTargetIdEffective}
            selectedMaterialId={practiceContextMaterialIdEffective}
            target={practiceContextTarget}
            material={practiceContextMaterial}
            knowledgePoints={practiceKnowledgePointCandidates}
            focusedKnowledgePoints={practiceFocusedKnowledgePoints}
            scope={practiceScope}
            questions={questions}
            testResult={testResult}
            subView={practiceSubView}
            questionBatchContext={questionBatchContext}
            isGenerating={aiPendingActions.questions}
            isSubmitting={aiPendingActions.test}
            explainAnswers={questionExplainAnswers}
            explainLoading={questionExplainLoading}
            onSelectTarget={handleSelectPracticeTarget}
            onSelectMaterial={handleSelectPracticeMaterial}
            onScopeChange={setPracticeScope}
            onSelectFocusPoint={(pointId) =>
              setPracticeFocusedKnowledgePointIds((current) =>
                current.includes(pointId)
                  ? current.filter((id) => id !== pointId)
                  : [...current, pointId]
              )
            }
            onSubViewChange={setPracticeSubView}
            onGenerate={handleGenerateQuestions}
            onSubmit={handleSubmitTest}
            onExplainQuestion={(questionId, question) => void handleExplainQuestion(questionId, question)}
            onOpenWrong={() => setView("wrong")}
            onOpenPlans={() => setView("plans")}
            onClearFocus={() => setPracticeFocusedKnowledgePointIds([])}
          />
        ) : null}

        {view === "wrong" ? (
          <WrongQuestionsPage
            items={wrongQuestions}
            targets={targets}
            materials={materials}
            knowledgePoints={knowledgeGraph?.nodes ?? []}
            filters={wrongQuestionFilters}
            mode={wrongBookMode}
            loading={wrongQuestionsLoading}
            reviewQueue={wrongReviewQueue}
            reviewIndex={wrongReviewIndex}
            reviewLoading={wrongReviewLoading}
            redoSubmitting={wrongRedoSubmitting}
            redoResult={wrongRedoResult}
            explainAnswers={questionExplainAnswers}
            explainLoading={questionExplainLoading}
            onFiltersChange={handleWrongQuestionFiltersChange}
            onModeChange={(mode) => {
              setWrongBookMode(mode);
              setWrongRedoResult(null);
            }}
            onUpdateMastery={handleUpdateMastery}
            onStartReview={() => void handleStartWrongReview()}
            onRedo={(id, answer) => void handleRedoWrongQuestion(id, answer)}
            onExplainQuestion={(questionId, question) => void handleExplainQuestion(questionId, question)}
            onNextReview={() => {
              setWrongRedoResult(null);
              setWrongReviewIndex((current) => Math.min(current + 1, Math.max(wrongReviewQueue.length - 1, 0)));
            }}
            onExport={() =>
              void handleExport(
                () => api.exportWrongQuestions(wrongQuestionFilters.targetId ?? undefined, wrongQuestionFilters.materialId ?? undefined),
                "错题本已开始下载。"
              )
            }
          />
        ) : null}

        {view === "plans" ? (
          <ReviewPlansPage
            targets={targets}
            plans={reviewPlans}
            isGenerating={aiPendingActions.plan}
            updatingTaskIds={updatingReviewPlanTaskIds}
            onGenerate={handleGenerateReviewPlan}
            onToggleTaskCompleted={(taskId, completed) => void handleToggleReviewPlanTask(taskId, completed)}
            onExport={(planId) => void handleExport(() => api.exportReviewPlan(planId), "复习计划已开始下载。")}
          />
        ) : null}

        {view === "usage" ? (
          <AiUsagePage
            summary={aiUsageSummary}
            logs={aiUsageLogs}
            loading={aiUsageLoading}
            error={aiUsageError}
            onRefresh={() => void loadAiUsage()}
          />
        ) : null}
      </main>
    </div>
  );
}

function AdminShell({
  user,
  view,
  onViewChange,
  notice,
  loading,
  onCloseNotice,
  onLogout,
  onRefresh,
  health,
  summary,
  users,
  materials,
  tasks,
  logs,
  onUpdateUserStatus,
  onRetryTask
}: {
  user: User;
  view: AdminView;
  onViewChange: (view: AdminView) => void;
  notice: Notice | null;
  loading: boolean;
  onCloseNotice: () => void;
  onLogout: () => void;
  onRefresh: () => void;
  health: { api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus };
  summary: AdminSummary | null;
  users: User[];
  materials: Material[];
  tasks: AdminParseTask[];
  logs: AdminLog[];
  onUpdateUserStatus: (userId: number, isActive: boolean) => void;
  onRetryTask: (taskId: number) => void;
}) {
  return (
    <div className="app-shell admin-shell">
      <aside className="sidebar admin-sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Shield size={20} />
          </div>
          <div>
            <strong>管理员后台</strong>
            <span>系统数据与运维中心</span>
          </div>
        </div>

        <nav>
          {adminNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.view} className={view === item.view ? "active" : ""} onClick={() => onViewChange(item.view)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="profile-card">
          <UserCircle size={30} />
          <div>
            <strong>{user.display_name ?? user.username}</strong>
            <span>admin</span>
          </div>
          <button className="icon-button" onClick={onLogout} title="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{adminPageTitle(view)}</h1>
          </div>
          <button className="ghost-button" onClick={onRefresh}>
            <RefreshCw size={16} />
            刷新后台数据
          </button>
        </header>

        {notice ? <NoticeBar notice={notice} onClose={onCloseNotice} /> : null}
        {loading ? <LoadingBanner /> : null}

        {view === "overview" ? <AdminOverview summary={summary} health={health} /> : null}
        {view === "users" ? <AdminUsersPage users={users} currentUserId={user.id} onUpdateUserStatus={onUpdateUserStatus} /> : null}
        {view === "materials" ? <AdminMaterialsPage materials={materials} /> : null}
        {view === "tasks" ? <AdminTasksPage tasks={tasks} onRetryTask={onRetryTask} /> : null}
        {view === "logs" ? <AdminLogsPage logs={logs} /> : null}
        {view === "health" ? <AdminHealthPage health={health} /> : null}
      </main>
    </div>
  );
}

function AdminOverview({
  summary,
  health
}: {
  summary: AdminSummary | null;
  health: { api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus };
}) {
  const failedMaterials = summary?.material_parse_status.failed ?? 0;

  return (
    <div className="grid admin-grid">
      <MetricCard icon={UserCircle} label="注册人数" value={summary?.total_users ?? 0} hint="未删除用户" />
      <MetricCard icon={UserCircle} label="学生 / 管理员" value={`${summary?.student_users ?? 0} / ${summary?.admin_users ?? 0}`} hint="用户角色分布" />
      <MetricCard icon={Shield} label="启用 / 禁用" value={`${summary?.active_users ?? 0} / ${summary?.inactive_users ?? 0}`} hint="账号状态" />
      <MetricCard icon={FileText} label="资料总数" value={summary?.total_materials ?? 0} hint="全站资料" />
      <MetricCard icon={AlertTriangle} label="失败资料" value={failedMaterials} hint="解析失败资料" />
      <MetricCard icon={AlertTriangle} label="失败任务" value={summary?.failed_tasks ?? 0} hint="解析任务失败" />
      <MetricCard icon={Shield} label="数据库健康" value={health.db?.status ?? "error"} hint="数据存储连接" />
      <MetricCard icon={Shield} label="Redis 健康" value={health.redis?.status ?? "error"} hint="缓存与任务队列" />

      <section className="panel wide">
        <PanelTitle icon={AlertTriangle} title="解析状态分布" />
        <div className="usage-grid">
          {(["uploaded", "parsing", "parsed", "failed"] as ParseStatus[]).map((status) => (
            <article className="usage-card" key={status}>
              <strong>{parseStatusText[status]}</strong>
              <span>{summary?.material_parse_status[status] ?? 0} 份资料</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function AdminUsersPage({
  users,
  currentUserId,
  onUpdateUserStatus
}: {
  users: User[];
  currentUserId: number;
  onUpdateUserStatus: (userId: number, isActive: boolean) => void;
}) {
  return (
    <section className="panel wide">
      <PanelTitle icon={UserCircle} title="用户管理" action={`${users.length} 条`} />
      <div className="admin-table admin-users-table">
        {users.map((item) => (
          <div key={item.id}>
            <span>{item.username}</span>
            <span>{item.display_name ?? "未设置"}</span>
            <span>{item.role}</span>
            <span>{item.is_active ? "启用" : "禁用"}</span>
            <button
              disabled={item.id === currentUserId}
              onClick={() => onUpdateUserStatus(item.id, !item.is_active)}
            >
              {item.is_active ? "禁用" : "启用"}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdminMaterialsPage({ materials }: { materials: Material[] }) {
  return (
    <section className="panel wide">
      <PanelTitle icon={FileText} title="资料管理" action={`${materials.length} 条`} />
      <div className="admin-table admin-materials-table">
        {materials.map((material) => (
          <div key={material.id}>
            <span>{material.original_filename}</span>
            <span>用户 {material.user_id ?? "-"}</span>
            <span>目标 {material.target_id}</span>
            <StatusBadge status={material.parse_status} />
            <span>{material.parse_error || material.parse_warning || "无异常"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdminTasksPage({
  tasks,
  onRetryTask
}: {
  tasks: AdminParseTask[];
  onRetryTask: (taskId: number) => void;
}) {
  return (
    <section className="panel wide">
      <PanelTitle icon={AlertTriangle} title="解析任务" action={`${tasks.length} 条`} />
      <div className="admin-table admin-tasks-table">
        {tasks.map((task) => (
          <div key={task.id}>
            <span>任务 {task.id}</span>
            <span>资料 {task.material_id}</span>
            <span>用户 {task.user_id}</span>
            <span>{task.task_status}</span>
            <span>{task.failure_reason || "无异常"}</span>
            <button disabled={task.task_status !== "failed"} onClick={() => onRetryTask(task.id)}>重试</button>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdminLogsPage({ logs }: { logs: AdminLog[] }) {
  return (
    <section className="panel wide">
      <PanelTitle icon={CalendarDays} title="操作日志" action={`${logs.length} 条`} />
      <div className="admin-table admin-logs-table">
        {logs.map((log) => (
          <div key={log.id}>
            <span>{log.operation_type}</span>
            <span>{log.target_type}{log.target_id ? ` #${log.target_id}` : ""}</span>
            <span>{log.operation_result}</span>
            <span>{log.remark ?? "无备注"}</span>
            <span>{formatDateTimeZh(log.created_at, "无时间")}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdminHealthPage({
  health
}: {
  health: { api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus };
}) {
  return (
    <div className="grid admin-grid">
      <MetricCard icon={Shield} label="API 健康" value={health.api?.status ?? "error"} hint="后端服务状态" />
      <MetricCard icon={Shield} label="数据库健康" value={health.db?.status ?? "error"} hint="数据存储连接" />
      <MetricCard icon={Shield} label="Redis 健康" value={health.redis?.status ?? "error"} hint="缓存与任务队列" />
    </div>
  );
}

function AuthPage({
  loading,
  notice,
  onLogin,
  onRegister,
  onCloseNotice
}: {
  loading: boolean;
  notice: Notice | null;
  onLogin: (formData: FormData) => void;
  onRegister: (formData: FormData) => void;
  onCloseNotice: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginRole, setLoginRole] = useState<LoginRole>("student");
  const isLogin = mode === "login";

  return (
    <div className="auth-screen">
      <div className="auth-tech-lines" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="auth-background-panels" aria-hidden="true">
        <section className="auth-bg-panel auth-bg-panel-queue">
          <div>
            <strong>AI 解析队列</strong>
            <span>Secure Sync</span>
          </div>
          <p>Chapter13.pdf · OCR</p>
          <p>编译原理笔记 · Chunking</p>
          <p>图片讲义 · Vision Parse</p>
        </section>
        <section className="auth-bg-panel auth-bg-panel-mastery">
          <div>
            <strong>知识图谱</strong>
            <span>42 nodes</span>
          </div>
          <div className="auth-bg-progress"><i style={{ width: "72%" }} /></div>
          <div className="auth-bg-progress"><i style={{ width: "48%" }} /></div>
          <div className="auth-bg-progress"><i style={{ width: "86%" }} /></div>
        </section>
        <section className="auth-bg-panel auth-bg-panel-review">
          <div>
            <strong>今日复习</strong>
            <span>4 项待完成</span>
          </div>
          <p>错题重做</p>
          <p>知识图谱回顾</p>
          <p>生成自测题</p>
        </section>
      </div>
      <div className="auth-page-content">
        <section className="auth-copy">
          <div className="brand large">
            <div className="brand-mark">
              <Sparkles size={28} />
            </div>
            <div>
              <strong>AI 智能备考复习平台</strong>
              <span>上传资料后自动解析与提炼知识点，围绕目标完成问答、出题、自测、错题复习和计划追踪。</span>
            </div>
          </div>
          <div className="hero-phone auth-workflow-stage">
            <div className="phone-island" />
            <div className="workflow-rail" aria-hidden="true" />
            <div className="mini-card blue workflow-card">
              <span className="workflow-step"><Upload size={15} />上传资料</span>
              <strong>资料自动入库</strong>
              <span>支持 TXT、PDF 和图片资料，上传后自动解析并进入学习流程。</span>
            </div>
            <div className="mini-card green workflow-card">
              <span className="workflow-step"><Bot size={15} />AI 解析</span>
              <strong>知识驱动学习</strong>
              <span>基于资料生成知识提炼、知识图谱、AI 问答和针对性出题。</span>
            </div>
            <div className="mini-card workflow-card">
              <span className="workflow-step"><ClipboardCheck size={15} />错题复习计划</span>
              <strong>复习闭环追踪</strong>
              <span>自测后沉淀错题，按掌握状态复习，并生成可勾选的复习计划。</span>
            </div>
            <div className="auth-flow-line" aria-label="学习流程">
              <span>上传资料</span>
              <span>AI 解析</span>
              <span>知识图谱</span>
              <span>自动出题</span>
              <span>错题复习</span>
              <span>计划完成</span>
            </div>
            <div className="floating-data-card card-parse"><FileText size={16} /><span>PDF 解析完成</span><strong>98%</strong></div>
            <div className="floating-data-card card-graph"><Network size={16} /><span>知识点识别</span><strong>42 个</strong></div>
            <div className="floating-data-card card-quiz"><ClipboardCheck size={16} /><span>已生成练习题</span><strong>15 道</strong></div>
            <div className="floating-data-card card-plan"><CalendarDays size={16} /><span>今日复习计划</span><strong>3 项</strong></div>
          </div>
        </section>

        <form className="auth-panel" onSubmit={(event) => submitForm(event, isLogin ? onLogin : onRegister)}>
          <div className="auth-status-strip"><Shield size={14} />AI Study Cloud · Secure Sync</div>
          <div className="auth-heading">
            <p className="eyebrow">Welcome back</p>
            <h1>{isLogin ? (loginRole === "admin" ? "管理员登录" : "学生登录") : "学生注册"}</h1>
            <span>{isLogin ? "登录后同步课程目标、资料库、错题本与复习计划" : "创建账号后即可同步资料解析、知识图谱与复习闭环"}</span>
          </div>

          {notice ? <NoticeBar notice={notice} onClose={onCloseNotice} /> : null}
          {loading ? <LoadingBanner /> : null}

          {isLogin ? (
            <div className="auth-role-switch" role="tablist" aria-label="登录身份">
              <button
                type="button"
                className={loginRole === "student" ? "active" : ""}
                onClick={() => setLoginRole("student")}
              >
                学生登录
              </button>
              <button
                type="button"
                className={loginRole === "admin" ? "active" : ""}
                onClick={() => setLoginRole("admin")}
              >
                管理员登录
              </button>
            </div>
          ) : null}
          {isLogin ? <input type="hidden" name="login_role" value={loginRole} /> : null}
          <label className="auth-input-field">
            <UserCircle size={18} />
            <input name="username" placeholder="用户名" minLength={3} required />
          </label>
          <label className="auth-input-field">
            <Shield size={18} />
            <input name="password" type="password" placeholder="密码" minLength={6} required />
          </label>
          {mode === "register" ? (
            <label className="auth-input-field">
              <Sparkles size={18} />
              <input name="display_name" placeholder="昵称（可选）" />
            </label>
          ) : null}

          <button className="primary-button auth-submit-button" type="submit" disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={16} /> : <UserCircle size={16} />}
            {isLogin ? (loading ? "正在同步数据..." : "登录并同步数据") : loading ? "正在创建账号..." : "注册并登录"}
          </button>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setLoginRole("student");
            }}
          >
            {isLogin ? "没有账号？创建新账号" : "已有账号？返回登录"}
          </button>
        </form>
      </div>
    </div>
  );
}

const examProgressWindowDays = 30;

function getDashboardTarget(selectedTarget: StudyTarget | null, targets: StudyTarget[]) {
  return selectedTarget ?? targets[0] ?? null;
}

function parseDateOnly(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const normalized = normalizeDateInput(value);
  const match = normalized?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

function startOfToday() {
  const today = new Date();
  return new Date(today.getFullYear(), today.getMonth(), today.getDate());
}

function daysUntil(value: string | null | undefined) {
  const date = parseDateOnly(value);
  if (!date) {
    return null;
  }
  return Math.ceil((date.getTime() - startOfToday().getTime()) / 86400000);
}

function getExamCountdown(target: StudyTarget | null) {
  const rawDaysLeft = daysUntil(target?.exam_date);
  if (rawDaysLeft === null) {
    return {
      displayValue: "--",
      progressPercent: 0,
      statusText: "未设置考试日期"
    };
  }

  const daysLeft = Math.max(0, rawDaysLeft);
  const progressPercent = rawDaysLeft < 0
    ? 100
    : Math.round(Math.max(0, Math.min(1, (examProgressWindowDays - daysLeft) / examProgressWindowDays)) * 100);
  return {
    displayValue: String(daysLeft),
    progressPercent,
    statusText: rawDaysLeft <= 0 ? "考试日期已到/已过" : ""
  };
}

function getUpcomingReviewTasks(reviewPlans: ReviewPlan[], limit: number) {
  return reviewPlans
    .flatMap((plan) => plan.tasks)
    .filter((task) => !task.completed)
    .sort((left, right) => {
      const leftDate = parseDateOnly(left.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      const rightDate = parseDateOnly(right.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      return leftDate - rightDate || left.id - right.id;
    })
    .slice(0, limit);
}

function sortReviewPlanTasks(tasks: ReviewPlanTask[]) {
  return [...tasks].sort((left, right) => {
    if (left.completed !== right.completed) {
      return left.completed ? 1 : -1;
    }
    const leftDate = parseDateOnly(left.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    const rightDate = parseDateOnly(right.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    return leftDate - rightDate || left.id - right.id;
  });
}

function reviewTaskTimingLabel(date: string) {
  const diff = daysUntil(date);
  if (diff === null) {
    return "待完成";
  }
  if (diff < 0) {
    return "已逾期";
  }
  if (diff === 0) {
    return "今日待完成";
  }
  if (diff === 1) {
    return "明日待完成";
  }
  return "待完成";
}

function getGraphDisplayLevel(level: number, minLevel: number) {
  return Math.max(1, level - minLevel + 1);
}

function getGraphNodeCaption(
  node: KnowledgeGraphNode,
  parent: KnowledgeGraphNode | null,
  displayLevel: number,
  isDirectlyLinked: boolean
) {
  if (parent) {
    return `属于 ${parent.name}`;
  }
  if (!isDirectlyLinked) {
    return "上级节点";
  }
  if (node.parent_id) {
    return "当前范围知识点";
  }
  return displayLevel === 1 ? "顶层知识点" : "当前范围知识点";
}

function getKnowledgePointCandidates(graph: KnowledgeGraph | null, materialId: number | null) {
  const nodes = graph?.nodes ?? [];
  if (!materialId) {
    return nodes;
  }
  return nodes.filter((node) =>
    node.materials?.some((link) => link.material_id === materialId)
  );
}

function handleKeyboardClick(event: KeyboardEvent, callback: () => void) {
  if (
    event.target instanceof HTMLElement
    && event.target.closest("button, a, input, select, textarea")
  ) {
    return;
  }
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  event.preventDefault();
  callback();
}

function Dashboard({
  targets,
  materials,
  selectedTarget,
  wrongQuestions,
  reviewPlans,
  testRecords,
  knowledgeGraph,
  aiUsageSummary,
  onQuickView
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTarget: StudyTarget | null;
  wrongQuestions: WrongQuestion[];
  reviewPlans: ReviewPlan[];
  testRecords: TestRecord[];
  knowledgeGraph: KnowledgeGraph | null;
  aiUsageSummary: AiUsageSummary | null;
  onQuickView: (view: View) => void;
}) {
  const primaryTarget = getDashboardTarget(selectedTarget, targets);
  const examCountdown = getExamCountdown(primaryTarget);
  const upcomingTasks = getUpcomingReviewTasks(reviewPlans, 4);
  const currentMaterialCount = primaryTarget
    ? materials.filter((item) => item.target_id === primaryTarget.id).length
    : materials.length;
  const averageAccuracy = testRecords.length
    ? Math.round((testRecords.reduce((sum, item) => sum + item.accuracy, 0) / testRecords.length) * 100)
    : 0;
  const primaryTargetCopy = primaryTarget
    ? primaryTarget.review_goal
      ? `复习目标：${primaryTarget.review_goal}`
      : "可在学习目标中补充复习目标。"
    : "先创建课程或考试目标，再上传资料开始学习。";
  const materialCountHint = primaryTarget ? "当前目标下的资料" : "全部目标资料";

  return (
    <div className="grid dashboard-grid">
      <section
        className="hero-panel clickable-panel"
        onClick={() => onQuickView("targets")}
      >
        <div
          className="hero-panel-copy"
          role="button"
          tabIndex={0}
          onKeyDown={(event) => handleKeyboardClick(event, () => onQuickView("targets"))}
        >
          <p className="eyebrow">主学习目标</p>
          <h2>{primaryTarget?.title ?? "还没有学习目标"}</h2>
          <p>{primaryTargetCopy}</p>
          <div className="quick-actions">
            <button onClick={(event) => { event.stopPropagation(); onQuickView("targets"); }}><Plus size={16} />新建目标</button>
            <button onClick={(event) => { event.stopPropagation(); onQuickView("materials"); }}><Upload size={16} />上传资料</button>
            <button onClick={(event) => { event.stopPropagation(); onQuickView("graph"); }}><Network size={16} />查看图谱</button>
          </div>
        </div>
        <button
          className="progress-ring"
          type="button"
          style={{ "--progress-ring-percent": `${examCountdown.progressPercent}%` } as CSSProperties & Record<"--progress-ring-percent", string>}
          onClick={(event) => {
            event.stopPropagation();
            onQuickView("targets");
          }}
        >
          <strong>{examCountdown.displayValue}</strong>
          <span>距离考试天数</span>
          {examCountdown.statusText ? <small>{examCountdown.statusText}</small> : null}
        </button>
      </section>

      <MetricCard icon={BookOpen} label="学习目标" value={targets.length} hint="管理课程与考试目标" onClick={() => onQuickView("targets")} />
      <MetricCard icon={FileText} label="当前资料总数" value={currentMaterialCount} hint={materialCountHint} onClick={() => onQuickView("materials")} />

      <button className="panel clickable-panel dashboard-panel-button" type="button" onClick={() => onQuickView("graph")}>
        <PanelTitle icon={GitBranch} title="知识点掌握" />
        {knowledgeGraph?.nodes.length ? (
          <div className="mastery-strip">
            {knowledgeGraph.nodes.slice(0, 18).map((node) => (
              <span key={node.id} className={`mastery-dot ${node.mastery_status}`} title={`${node.name} ${Math.round(node.mastery_score * 100)}%`} />
            ))}
          </div>
        ) : (
          <p className="muted-text">还没有生成知识图谱。</p>
        )}
      </button>

      <MetricCard icon={ClipboardCheck} label="近期自测均分" value={`${averageAccuracy}%`} hint="来自最近自测记录" onClick={() => onQuickView("practice")} />
      <MetricCard icon={AlertTriangle} label="错题总数" value={wrongQuestions.length} hint="高频薄弱点入口" onClick={() => onQuickView("wrong")} />
      <MetricCard icon={Sparkles} label="Token 总量" value={formatCompactNumber(aiUsageSummary?.total_tokens ?? 0)} hint="查看 AI 用量统计" onClick={() => onQuickView("usage")} />

      <section
        className="panel wide clickable-panel"
        role="button"
        tabIndex={0}
        onClick={() => onQuickView("plans")}
        onKeyDown={(event) => handleKeyboardClick(event, () => onQuickView("plans"))}
      >
        <PanelTitle icon={CalendarDays} title="即将复习任务" />
        <div className="task-list">
          {upcomingTasks.length ? upcomingTasks.map((task) => (
            <button
              className="task-row task-row-button"
              type="button"
              key={task.id}
              onClick={(event) => {
                event.stopPropagation();
                onQuickView("plans");
              }}
            >
              <CheckCircle2 size={18} />
              <div>
                <strong>{task.title}</strong>
                <span>{formatDateZh(task.date)} · {reviewTaskTimingLabel(task.date)}</span>
              </div>
            </button>
          )) : <p className="muted-text">暂无待完成复习任务。</p>}
        </div>
      </section>
    </div>
  );
}

function TargetsPage({
  targets,
  selectedTargetId,
  onSelect,
  onCreate,
  onUpdate,
  onDelete
}: {
  targets: StudyTarget[];
  selectedTargetId: number | null;
  onSelect: (id: number) => void;
  onCreate: (formData: FormData) => void;
  onUpdate: (id: number, payload: Partial<StudyTarget>) => void;
  onDelete: (id: number) => void;
}) {
  const selected = targets.find((item) => item.id === selectedTargetId) ?? targets[0] ?? null;
  const [editingTargetId, setEditingTargetId] = useState<number | null>(null);
  const [createFormVersion, setCreateFormVersion] = useState(0);
  const editingTarget = targets.find((item) => item.id === editingTargetId) ?? null;
  const isEditing = Boolean(editingTarget);

  useEffect(() => {
    if (editingTargetId && !targets.some((item) => item.id === editingTargetId)) {
      setEditingTargetId(null);
    }
  }, [editingTargetId, targets]);

  function handleTargetFormSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    if (editingTarget) {
      onUpdate(editingTarget.id, {
        title: String(formData.get("title") ?? "").trim(),
        subject: emptyToUndefined(formData.get("subject")),
        target_type: String(formData.get("target_type") ?? "exam") as StudyTarget["target_type"],
        exam_date: normalizeDateInput(formData.get("exam_date")),
        review_goal: emptyToUndefined(formData.get("review_goal")),
        description: emptyToUndefined(formData.get("description"))
      });
      return;
    }
    onCreate(formData);
    form.reset();
    setCreateFormVersion((value) => value + 1);
  }

  function handleSelectForEdit(target: StudyTarget) {
    onSelect(target.id);
    setEditingTargetId(target.id);
  }

  return (
    <div className="two-column targets-layout">
      <form
        key={editingTarget ? `edit-target-${editingTarget.id}-${editingTarget.updated_at}` : `create-target-${createFormVersion}`}
        className="panel form-panel target-editor-panel"
        onSubmit={handleTargetFormSubmit}
      >
        <PanelTitle icon={isEditing ? BookOpen : Plus} title={isEditing ? "编辑目标" : "创建目标"} />
        <input name="title" placeholder="目标标题" defaultValue={editingTarget?.title ?? ""} required />
        <input name="subject" placeholder="学科名称" defaultValue={editingTarget?.subject ?? ""} required />
        <select name="target_type" defaultValue={editingTarget?.target_type ?? "exam"}>
          <option value="exam">exam</option>
          <option value="course">course</option>
        </select>
        <DatePickerField
          name="exam_date"
          label="考试日期"
          placeholder="选择考试日期"
          initialValue={editingTarget?.exam_date ?? ""}
        />
        <textarea name="review_goal" placeholder="复习目标" defaultValue={editingTarget?.review_goal ?? ""} required />
        <textarea name="description" placeholder="补充说明（可选）" defaultValue={editingTarget?.description ?? ""} />
        <button className="primary-button" type="submit">
          {isEditing ? <CheckCircle2 size={16} /> : <Plus size={16} />}
          {isEditing ? "保存修改" : "创建目标"}
        </button>
        {isEditing ? (
          <button className="ghost-button" type="button" onClick={() => setEditingTargetId(null)}>
            取消编辑 / 新建目标
          </button>
        ) : null}
      </form>

      <section className="panel">
        <PanelTitle icon={BookOpen} title="目标列表" />
        <div className="list">
          {targets.map((target) => (
            <div key={target.id} className={`target-list-item ${target.id === selected?.id ? "selected" : ""}`}>
              <button className="material-row" onClick={() => handleSelectForEdit(target)}>
                <div>
                  <strong>{target.title}</strong>
                  <span>{target.subject ?? "未设置科目"} · {target.target_type} · {formatDateZh(target.exam_date, "无考试日期")}</span>
                </div>
              </button>
              <button
                className="target-delete-button"
                title="删除目标"
                aria-label={`删除目标：${target.title}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onDelete(target.id);
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MaterialsPage({
  targets,
  materials,
  selectedTarget,
  selectedTargetId,
  selectedMaterialId,
  onSelectTarget,
  onSelect,
  onUpload,
  onParse,
  onDelete
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTarget: StudyTarget | null;
  selectedTargetId: number | null;
  selectedMaterialId: number | null;
  onSelectTarget: (targetId: number) => void;
  onSelect: (material: Material) => void;
  onUpload: (formData: FormData) => void;
  onParse: (materialId: number) => void;
  onDelete: (materialId: number) => void;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const parsingCount = materials.filter((material) => material.parse_status === "parsing").length;
  const failedCount = materials.filter((material) => material.parse_status === "failed").length;
  const parsedCount = materials.filter((material) => material.parse_status === "parsed").length;

  return (
    <div className="material-library-page">
      <section className="panel material-library-toolbar">
        <div className="toolbar-copy">
          <PanelTitle icon={FileText} title="资料库" />
          <p className="muted-text">选择学习目标后查看、上传和管理该目标下的资料。</p>
        </div>
        <label className="field-block target-switcher">
          <span>当前学习目标</span>
          <select
            value={selectedTargetId ?? ""}
            onChange={(event) => onSelectTarget(Number(event.currentTarget.value))}
          >
            <option value="" disabled>请选择学习目标</option>
            {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
          </select>
        </label>
        <div className="library-stats">
          <span><strong>{materials.length}</strong> 份资料</span>
          <span><strong>{parsedCount}</strong> 可学习</span>
          <span><strong>{parsingCount}</strong> 解析中</span>
          <span><strong>{failedCount}</strong> 失败</span>
        </div>
      </section>

      <div className="two-column">
        <form
          className="panel form-panel"
          onSubmit={(event) => {
            submitForm(event, onUpload);
            setSelectedFile(null);
          }}
        >
          <PanelTitle icon={Upload} title="上传资料" />
          <p className="form-hint">
            {selectedTarget ? `上传后会自动解析并加入当前目标：${selectedTarget.title}` : "请先在上方选择学习目标。"}
          </p>
          <label className="drop-zone">
            <Upload size={28} />
            <span>选择 PDF / TXT / 图片资料</span>
            <small>TXT 最稳定；PDF 和图片会尝试 OCR，内容较长时解析可能需要更久。</small>
            <input
              name="file"
              type="file"
              accept=".pdf,.txt,image/*"
              required
              disabled={!selectedTargetId}
              onChange={(event) => setSelectedFile(event.currentTarget.files?.[0] ?? null)}
            />
          </label>
          {selectedFile ? (
            <div className="selected-file">
              <FileText size={16} />
              <div>
                <strong>{selectedFile.name}</strong>
                <span>{formatBytes(selectedFile.size)} · {selectedFile.type || "未知类型"}</span>
              </div>
            </div>
          ) : (
            <p className="form-hint">还没有选择文件。</p>
          )}
          <button className="primary-button" type="submit" disabled={!selectedTargetId}><Upload size={16} />上传并入库</button>
        </form>

        <section className="panel">
          <PanelTitle icon={FileText} title="资料列表" action={`${materials.length} 份`} />
          <div className="list">
            {materials.length ? materials.map((material) => (
              <div key={material.id} className={`list-item material-list-item ${selectedMaterialId === material.id ? "selected-row" : ""}`}>
                <button className="material-row material-row-inline" onClick={() => onSelect(material)}>
                  <div>
                    <strong>{material.original_filename}</strong>
                    <span>{formatBytes(material.file_size)} · {material.file_type.toUpperCase()}</span>
                    {material.parse_warning ? <small className="warning-text">解析质量提示：{material.parse_warning}</small> : null}
                  </div>
                </button>
                <StatusBadge status={material.parse_status} />
                <button
                  className="ghost-button compact-button"
                  disabled={material.parse_status === "parsing"}
                  onClick={() => onParse(material.id)}
                >
                  <RefreshCw size={16} />
                  {getParseActionText(material.parse_status)}
                </button>
                <button className="icon-button" title="删除资料" onClick={() => onDelete(material.id)}>
                  <Trash2 size={16} />
                </button>
              </div>
            )) : (
              <div className="source-empty">
                <p className="muted-text">
                  {selectedTarget ? "当前目标还没有资料，可以上传 PDF/TXT/图片。" : "请先选择学习目标。"}
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function MaterialDetailPage({
  material,
  target,
  preview,
  sourcePreview,
  knowledge,
  knowledgeRefreshing,
  onRefreshKnowledge,
  onExportKnowledge,
  onJumpToQa,
  onJumpToPractice,
  onBack
}: {
  material: Material | null;
  target: StudyTarget | null;
  preview: MaterialPreview | null;
  sourcePreview: MaterialSourcePreview | null;
  knowledge: KnowledgeResult | null;
  knowledgeRefreshing: boolean;
  onRefreshKnowledge: () => void;
  onExportKnowledge: () => void;
  onJumpToQa: () => void;
  onJumpToPractice: () => void;
  onBack: () => void;
}) {
  if (!material) return <EmptyPanel text="请先在资料库中选择一份资料。" />;

  const aiDisabled = material.parse_status !== "parsed";

  return (
    <div className="grid learn-grid">
      <section className="panel full-width">
        <div className="subpage-header">
          <div>
            <span className="breadcrumb-line">
              <button type="button" onClick={onBack}>资料库</button>
              <i>/</i>
              <em>资料详情</em>
            </span>
            <strong>{material.original_filename}</strong>
            <small>所属目标：{target?.title ?? "未匹配"} · {formatBytes(material.file_size)} · {material.file_type.toUpperCase()}</small>
          </div>
          <StatusBadge status={material.parse_status} />
        </div>
        <div className="detail-header">
          <div>
            <p>状态：{parseStatusText[material.parse_status]}</p>
            {material.parse_error ? <p className="danger-text">{material.parse_error}</p> : null}
            {material.parse_warning ? <p className="warning-text">{material.parse_warning}</p> : null}
            <p className={`flow-status ${material.parse_status}`}>
              {getMaterialStateHint(material)}
            </p>
          </div>
          <div className="quick-actions">
            <button disabled={material.parse_status === "parsing" || knowledgeRefreshing} onClick={onRefreshKnowledge}>
              {knowledgeRefreshing || material.parse_status === "parsing" ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
              {knowledgeRefreshing || material.parse_status === "parsing" ? "处理中" : "重新提炼"}
            </button>
            <button disabled={!target} onClick={onExportKnowledge}><Download size={16} />导出总结</button>
            <button disabled={aiDisabled} onClick={onJumpToQa}><MessageSquare size={16} />AI 问答</button>
            <button disabled={aiDisabled} onClick={onJumpToPractice}><ClipboardCheck size={16} />AI 出题</button>
          </div>
        </div>
      </section>

      <div className={`detail-panel-grid ${knowledge ? "has-knowledge" : ""}`}>
        <section className="panel parsed-preview-panel">
          <PanelTitle icon={FileText} title="资料预览" />
          <ParsedTextPreview material={material} preview={preview} />
        </section>

        {knowledge ? (
          <section className="panel knowledge-result-panel">
            <PanelTitle icon={Bot} title="知识提炼结果" />
            <div className="detail-stack knowledge-result-scroll">
              {knowledge.scope ? <span className="subtle-pill">{knowledge.scope === "target" ? "目标级知识提炼" : "资料级知识提炼"}</span> : null}
              <p>{knowledge.summary}</p>
              <InfoList title="提纲" items={knowledge.outline} />
              <InfoList title="关键词" items={knowledge.keywords} />
              <InfoList title="重点" items={knowledge.key_points} />
              <InfoList title="考点" items={knowledge.exam_points} />
            </div>
          </section>
        ) : null}

        <section className="panel source-panel">
          <PanelTitle icon={ExternalLink} title="源文件预览" />
          <SourceFilePreview material={material} sourcePreview={sourcePreview} />
        </section>
      </div>
    </div>
  );
}

const parsedPreviewPageSize = 2000;

function ParsedTextPreview({
  material,
  preview
}: {
  material: Material;
  preview: MaterialPreview | null;
}) {
  const [page, setPage] = useState(0);
  const parsedText = preview?.parsed_text?.trim() || preview?.preview_text?.trim() || "";
  const pages = useMemo(() => {
    if (!parsedText) {
      return [];
    }
    const nextPages: string[] = [];
    for (let index = 0; index < parsedText.length; index += parsedPreviewPageSize) {
      nextPages.push(parsedText.slice(index, index + parsedPreviewPageSize));
    }
    return nextPages;
  }, [parsedText]);
  const pageCount = pages.length;
  const currentPage = Math.min(page, Math.max(pageCount - 1, 0));

  useEffect(() => {
    setPage(0);
  }, [material.id, parsedText]);

  if (!parsedText) {
    return (
      <div className="parsed-preview-empty">
        <p className="muted-text">
          {material.parse_status === "parsing"
            ? "资料正在解析，完成后会自动刷新解析文本。"
            : material.parse_status === "uploaded"
              ? "等待后台解析或手动触发解析。"
              : material.parse_status === "failed"
                ? "资料解析失败，暂无解析文本。"
                : "当前资料暂无解析文本。"}
        </p>
      </div>
    );
  }

  return (
    <div className="parsed-preview-reader">
      <div className="parsed-preview-toolbar">
        <span>{material.file_type.toUpperCase()} · 解析文本 · 第 {currentPage + 1} / {pageCount} 页</span>
        <div className="preview-pager">
          <button
            type="button"
            disabled={currentPage === 0}
            onClick={() => setPage((value) => Math.max(value - 1, 0))}
          >
            <ChevronLeft size={16} />
            上一页
          </button>
          <button
            type="button"
            disabled={currentPage >= pageCount - 1}
            onClick={() => setPage((value) => Math.min(value + 1, pageCount - 1))}
          >
            下一页
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      <article className="parsed-preview-page">
        {pages[currentPage]}
      </article>
    </div>
  );
}

function SourceFilePreview({
  material,
  sourcePreview
}: {
  material: Material;
  sourcePreview: MaterialSourcePreview | null;
}) {
  const isCurrentSource = sourcePreview?.materialId === material.id;

  if (!isCurrentSource || !sourcePreview) {
    return (
      <div className="source-empty">
        <p className="muted-text">源文件正在加载，或当前资料文件暂不可预览。</p>
      </div>
    );
  }

  const contentType = sourcePreview.contentType.toLowerCase();
  const isPdf = sourcePreview.fileType === "pdf" || contentType.includes("pdf");
  const isImage = sourcePreview.fileType === "image" || contentType.startsWith("image/");
  const isText = sourcePreview.fileType === "txt" || contentType.startsWith("text/");

  return (
    <div className="source-preview">
      <div className="source-actions">
        <span>{material.file_type.toUpperCase()} · {material.content_type || "未知 MIME"}</span>
        <a href={sourcePreview.url} target="_blank" rel="noreferrer">
          <ExternalLink size={15} />
          新窗口打开
        </a>
      </div>

      {isImage ? (
        <img src={sourcePreview.url} alt={material.original_filename} />
      ) : isPdf || isText ? (
        <iframe src={sourcePreview.url} title={material.original_filename} />
      ) : (
        <div className="source-empty">
          <p className="muted-text">浏览器无法直接预览该文件类型，请使用新窗口打开。</p>
        </div>
      )}
    </div>
  );
}

function LearningContextSelector({
  targets,
  materials,
  selectedTargetId,
  selectedMaterialId,
  title = "学习上下文",
  onSelectTarget,
  onSelectMaterial
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTargetId: number | null;
  selectedMaterialId: number | null;
  title?: string;
  onSelectTarget: (targetId: number) => void;
  onSelectMaterial: (materialId: number | null) => void;
}) {
  const targetMaterials = selectedTargetId
    ? materials.filter((material) => material.target_id === selectedTargetId)
    : [];
  const parsedMaterials = targetMaterials.filter((material) => material.parse_status === "parsed");

  return (
    <section className="panel context-panel">
      <PanelTitle icon={GitBranch} title={title} />
      <div className="toolbar-fields context-fields">
        <label className="field-block">
          <span>当前目标</span>
          <select
            value={selectedTargetId ?? ""}
            onChange={(event) => onSelectTarget(Number(event.currentTarget.value))}
          >
            <option value="" disabled>请选择学习目标</option>
            {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
          </select>
        </label>
        <label className="field-block">
          <span>当前资料</span>
          <select
            value={selectedMaterialId ?? ""}
            onChange={(event) => onSelectMaterial(event.currentTarget.value ? Number(event.currentTarget.value) : null)}
            disabled={!selectedTargetId}
          >
            <option value="">不限定资料</option>
            {targetMaterials.map((material) => (
              <option key={material.id} value={material.id} disabled={material.parse_status !== "parsed"}>
                {material.original_filename} · {parseStatusText[material.parse_status]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="form-hint">
        {selectedTargetId
          ? `当前目标下有 ${targetMaterials.length} 份资料，其中 ${parsedMaterials.length} 份可用于 AI 学习。`
          : "请先选择目标，再进行图谱、问答或出题。"}
      </p>
    </section>
  );
}

function KnowledgeGraphPage({
  targets,
  materials,
  selectedTargetId,
  selectedMaterialId,
  target,
  graph,
  targetKnowledge,
  materialKnowledge,
  materialKnowledgeLoading,
  materialKnowledgeError,
  knowledgeRefreshing,
  activeKnowledgeJob,
  onSelectTarget,
  onSelectMaterial,
  onGenerate,
  onUpdatePointMastery,
  onFocusQa,
  onFocusPractice,
  onExport,
  onExportAnki
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTargetId: number | null;
  selectedMaterialId: number | null;
  target: StudyTarget | null;
  graph: KnowledgeGraph | null;
  targetKnowledge: KnowledgeResult | null;
  materialKnowledge: KnowledgeResult | null;
  materialKnowledgeLoading: boolean;
  materialKnowledgeError: string | null;
  knowledgeRefreshing: boolean;
  activeKnowledgeJob: KnowledgeJob | null;
  onSelectTarget: (targetId: number) => void;
  onSelectMaterial: (materialId: number | null) => void;
  onGenerate: () => void;
  onUpdatePointMastery: (id: number, masteryStatus: KnowledgeMasteryStatus) => void;
  onFocusQa: (point: KnowledgePointReference) => void;
  onFocusPractice: (point: KnowledgePointReference) => void;
  onExport: () => void;
  onExportAnki: () => void;
}) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<{
    loading: boolean;
    materials: KnowledgePointMaterialItem[];
    questions: Question[];
    wrongQuestions: WrongQuestion[];
    error: string | null;
  }>({ loading: false, materials: [], questions: [], wrongQuestions: [], error: null });
  const graphNodes = useMemo(() => {
    const allNodes = graph?.nodes ?? [];
    if (!selectedMaterialId) {
      return allNodes;
    }

    const nodeMap = new Map(allNodes.map((node) => [node.id, node]));
    const visibleIds = new Set<number>();

    allNodes
      .filter((node) => node.materials.some((item) => item.material_id === selectedMaterialId))
      .forEach((node) => {
        visibleIds.add(node.id);
        let parentId = node.parent_id;
        while (parentId) {
          visibleIds.add(parentId);
          parentId = nodeMap.get(parentId)?.parent_id ?? null;
        }
      });

    return allNodes.filter((node) => visibleIds.has(node.id));
  }, [graph?.nodes, selectedMaterialId]);
  const selectedGraphMaterial = selectedMaterialId
    ? materials.find((material) => material.id === selectedMaterialId) ?? null
    : null;
  const validMaterialKnowledge =
    selectedGraphMaterial &&
    materialKnowledge?.scope === "material" &&
    materialKnowledge.material_id === selectedGraphMaterial.id
      ? materialKnowledge
      : null;
  const displayedKnowledge = selectedGraphMaterial ? validMaterialKnowledge : targetKnowledge;
  const knowledgePanelTitle = selectedGraphMaterial ? "资料级知识提炼" : "目标级知识提炼";
  const knowledgePanelAction = selectedGraphMaterial?.original_filename ?? target?.title;
  const directlyLinkedNodeIds = useMemo(
    () =>
      new Set(
        selectedMaterialId
          ? (graph?.nodes ?? [])
              .filter((node) => node.materials.some((item) => item.material_id === selectedMaterialId))
              .map((node) => node.id)
          : (graph?.nodes ?? []).map((node) => node.id)
      ),
    [graph?.nodes, selectedMaterialId]
  );
  const activeNode = graphNodes.find((node) => node.id === activeId) ?? graphNodes[0] ?? null;
  const graphLevels = Array.from(
    new Set(graphNodes.map((node) => node.level))
  ).sort((left, right) => left - right);
  const graphMinLevel = graphLevels[0] ?? 1;
  const filteredDetailMaterials = selectedMaterialId
    ? detail.materials.filter((item) => item.material_id === selectedMaterialId)
    : detail.materials;

  useEffect(() => {
    setActiveId(graphNodes[0]?.id ?? null);
  }, [graph?.target_id, graphNodes]);

  useEffect(() => {
    if (!activeNode) {
      setDetail({ loading: false, materials: [], questions: [], wrongQuestions: [], error: null });
      return;
    }

    let ignore = false;
    setDetail((current) => ({ ...current, loading: true, error: null }));
    void Promise.all([
      api.listKnowledgePointMaterials(activeNode.id),
      api.listKnowledgePointQuestions(activeNode.id).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 })),
      api.listKnowledgePointWrongQuestions(activeNode.id).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 }))
    ])
      .then(([materialsData, questionsData, wrongData]) => {
        if (ignore) return;
        setDetail({
          loading: false,
          materials: materialsData.items,
          questions: questionsData.items,
          wrongQuestions: wrongData.items,
          error: null
        });
      })
      .catch((error) => {
        if (ignore) return;
        setDetail({ loading: false, materials: [], questions: [], wrongQuestions: [], error: readMessage(error) });
      });

    return () => {
      ignore = true;
    };
  }, [activeNode?.id]);

  return (
    <div className="graph-layout">
      <LearningContextSelector
        targets={targets}
        materials={materials}
        selectedTargetId={selectedTargetId}
        selectedMaterialId={selectedMaterialId}
        title="图谱目标"
        onSelectTarget={onSelectTarget}
        onSelectMaterial={onSelectMaterial}
      />
      <section className="panel target-knowledge-panel">
        <PanelTitle icon={Sparkles} title={knowledgePanelTitle} action={knowledgePanelAction} />
        {materialKnowledgeLoading ? (
          <p className="muted-text">正在提炼当前资料内容...</p>
        ) : materialKnowledgeError ? (
          <p className="danger-text">资料级知识提炼失败：{materialKnowledgeError}</p>
        ) : displayedKnowledge ? (
          <div className="detail-stack">
            {displayedKnowledge.scope ? <span className="subtle-pill">{displayedKnowledge.scope === "target" ? "目标级知识提炼" : "资料级知识提炼"}</span> : null}
            <p>{displayedKnowledge.summary}</p>
            <div className="knowledge-summary-columns">
              <InfoList title="提纲" items={displayedKnowledge.outline} />
              <InfoList title="关键词" items={displayedKnowledge.keywords} />
              <InfoList title="重点" items={displayedKnowledge.key_points} />
              <InfoList title="考点" items={displayedKnowledge.exam_points} />
            </div>
          </div>
        ) : (
          <p className="muted-text">
            {selectedGraphMaterial
              ? "当前资料还没有知识提炼结果，切换到已解析资料后会自动提炼。"
              : "当前目标还没有知识提炼结果。完成资料解析或刷新图谱后会自动显示。"}
          </p>
        )}
      </section>
      <div className="graph-content-grid">
      <section className="panel">
        <PanelTitle icon={Network} title="知识点图谱" action={target?.title} />
        <div className="quick-actions">
          <button disabled={knowledgeRefreshing} onClick={onGenerate}>
            {knowledgeRefreshing ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
            {knowledgeRefreshing ? "任务执行中" : selectedMaterialId ? "增量刷新图谱" : "全量刷新图谱"}
          </button>
          <button disabled={!target} onClick={onExport}><Download size={16} />导出知识总结</button>
          <button disabled={!target} onClick={onExportAnki}><Download size={16} />导出 Anki CSV</button>
        </div>
        {activeKnowledgeJob ? (
          <p className={activeKnowledgeJob.status === "failed" ? "danger-text" : "muted-text"}>
            知识任务：{activeKnowledgeJob.job_type} / {activeKnowledgeJob.status}
            {activeKnowledgeJob.error_message ? ` - ${activeKnowledgeJob.error_message}` : ""}
          </p>
        ) : null}
        {selectedGraphMaterial ? (
          <p className="form-hint">
            当前按资料筛选：{selectedGraphMaterial.original_filename}。只显示该资料关联知识点及其上级节点。
          </p>
        ) : null}
        {graphNodes.length ? (
          <div className="graph-canvas">
            {graphLevels.map((level) => {
              const displayLevel = getGraphDisplayLevel(level, graphMinLevel);
              const isCoreLevel = displayLevel === 1;
              const levelNodes = graphNodes
                .filter((node) => node.level === level)
                .sort((left, right) => left.sort_order - right.sort_order);
              return (
                <section className={`graph-level ${isCoreLevel ? "core-level" : ""}`} key={level}>
                  <div className="graph-level-heading">
                    <strong>{isCoreLevel ? "核心知识" : `第 ${displayLevel} 层知识`}</strong>
                    <span>{levelNodes.length} 个知识点</span>
                  </div>
                  <div className="graph-level-nodes">
                    {levelNodes.map((node) => {
                      const parent = node.parent_id
                        ? graphNodes.find((item) => item.id === node.parent_id)
                        : null;
                      const baseSize = 88 + Math.min(Math.max(node.importance_weight, 0), 1) * 52;
                      const size = Math.round(baseSize + (isCoreLevel ? 24 : 0));
                      return (
                        <button
                          key={node.id}
                          className={`graph-node ${node.mastery_status} ${activeNode?.id === node.id ? "selected" : ""} ${directlyLinkedNodeIds.has(node.id) ? "" : "context-node"}`}
                          style={{
                            width: `${size}px`,
                            minHeight: `${Math.round(size * 0.72)}px`
                          }}
                          onClick={() => setActiveId(node.id)}
                          title={`${node.name} · 重要度 ${Math.round(node.importance_weight * 100)}% · 正确率 ${Math.round(node.accuracy * 100)}%`}
                        >
                          <strong>{node.name}</strong>
                          <span>重要度 {Math.round(node.importance_weight * 100)}%</span>
                          <small>{getGraphNodeCaption(node, parent ?? null, displayLevel, directlyLinkedNodeIds.has(node.id))}</small>
                        </button>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        ) : (
          <EmptyPanel text={selectedGraphMaterial ? "当前资料还没有关联到知识图谱节点，可重新提炼并刷新图谱。" : "当前目标还没有知识图谱，先生成图谱或完成资料解析。"} />
        )}
      </section>

      <section className="panel knowledge-detail-panel">
        <PanelTitle icon={Brain} title="知识点详情" />
        {activeNode ? (
          <div className="detail-stack">
            <h3>{activeNode.name}</h3>
            <p>{activeNode.description ?? "暂无描述。"}</p>
            <div className="mini-metrics">
              <span>正确率 {Math.round(activeNode.accuracy * 100)}%</span>
              <span>错题 {activeNode.wrong_count}</span>
              <span>作答 {activeNode.answered_count}</span>
            </div>
            <InfoList
              title="关联资料片段"
              items={activeNode.materials
                .filter((item) => !selectedMaterialId || item.material_id === selectedMaterialId)
                .map((item) => item.evidence_text || `资料 ${item.material_id}`)}
            />
            <div className="quick-actions">
              <button onClick={() => onFocusQa(activeNode)}><MessageSquare size={16} />围绕此点提问</button>
              <button onClick={() => onFocusPractice(activeNode)}><ClipboardCheck size={16} />按此点出题</button>
            </div>
            <div className="quick-actions">
              {([
                ["unlearned", "未学习"],
                ["weak", "薄弱"],
                ["basic", "基本掌握"],
                ["proficient", "熟练"]
              ] as const).map(([status, label]) => (
                <button key={status} className={activeNode.mastery_status === status ? "active-pill" : ""} onClick={() => onUpdatePointMastery(activeNode.id, status)}>
                  {label}
                </button>
              ))}
            </div>
            {detail.loading ? <p className="muted-text">正在加载知识点详情...</p> : null}
            {detail.error ? <p className="danger-text">{detail.error}</p> : null}
            <div className="knowledge-detail-scroll">
              <InfoList title="精确关联资料" items={filteredDetailMaterials.map((item) => `${item.original_filename}${item.evidence_text ? `：${item.evidence_text}` : ""}`)} />
              <InfoList title="关联题目" items={detail.questions.map((item) => item.stem)} />
              <InfoList title="关联错题" items={detail.wrongQuestions.map((item) => item.stem)} />
            </div>
          </div>
        ) : (
          <p className="muted-text">请选择一个知识点。</p>
        )}
      </section>
      </div>
    </div>
  );
}

function QaPage({
  targets,
  materials,
  selectedTargetId,
  selectedMaterialId,
  target,
  material,
  knowledgePoints,
  focusedKnowledgePoints,
  scope,
  records,
  loading,
  error,
  isAsking,
  onSelectTarget,
  onSelectMaterial,
  onScopeChange,
  onSelectFocusPoint,
  onAsk,
  onClearFocus
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTargetId: number | null;
  selectedMaterialId: number | null;
  target: StudyTarget | null;
  material: Material | null;
  knowledgePoints: KnowledgePointReference[];
  focusedKnowledgePoints: KnowledgePointReference[];
  scope: FocusableScope;
  records: QaRecord[];
  loading: boolean;
  error: string | null;
  isAsking: boolean;
  onSelectTarget: (targetId: number) => void;
  onSelectMaterial: (materialId: number | null) => void;
  onScopeChange: (scope: FocusableScope) => void;
  onSelectFocusPoint: (pointId: number) => void;
  onAsk: (formData: FormData) => void;
  onClearFocus: () => void;
}) {
  const selectedFocusIds = new Set(focusedKnowledgePoints.map((point) => point.id));
  const knowledgePointPickerLabel = material ? "当前资料关联知识点" : "当前目标全部知识点";
  const knowledgePointEmptyText = material
    ? "当前资料还没有关联知识点，请先刷新图谱或重新提炼。"
    : "当前目标还没有知识图谱节点，请先生成或刷新目标图谱。";

  if (!target && !material) return <EmptyPanel text="请先选择目标或资料，再进入 AI 问答页面。" />;

  return (
    <div className="qa-layout">
      <LearningContextSelector
        targets={targets}
        materials={materials}
        selectedTargetId={selectedTargetId}
        selectedMaterialId={selectedMaterialId}
        title="问答上下文"
        onSelectTarget={onSelectTarget}
        onSelectMaterial={onSelectMaterial}
      />
      <div className="qa-content-grid">
      <form className="panel form-panel qa-compose-panel" onSubmit={(event) => submitForm(event, onAsk)}>
        <PanelTitle icon={MessageSquare} title="提问" />
        <p className="muted-text">
          当前目标：{target?.title ?? "未选择"}；当前资料：{material?.original_filename ?? "未选择"}
        </p>
        <select
          name="qa_scope"
          value={scope}
          onChange={(event) => onScopeChange(event.currentTarget.value as FocusableScope)}
        >
          <option value="target" disabled={!target}>目标范围</option>
          <option value="knowledge_point" disabled={!target}>聚焦知识点</option>
          <option value="material" disabled={material?.parse_status !== "parsed"}>当前资料</option>
        </select>
        {target && scope === "knowledge_point" ? (
          <div className="knowledge-point-picker">
            <div className="field-label-row">
              <span>{knowledgePointPickerLabel}</span>
              {focusedKnowledgePoints.length ? <button className="ghost-button" type="button" onClick={onClearFocus}>清除聚焦</button> : null}
            </div>
            {knowledgePoints.length ? (
              <div className="tag-cloud selectable-tags">
                {knowledgePoints.map((point) => (
                  <button
                    key={point.id}
                    type="button"
                    className={selectedFocusIds.has(point.id) ? "selected" : ""}
                    onClick={() => onSelectFocusPoint(point.id)}
                    title={`添加或移除「${point.name}」`}
                  >
                    {point.name}
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted-text">{knowledgePointEmptyText}</p>
            )}
          </div>
        ) : null}
        {scope === "knowledge_point"
          ? focusedKnowledgePoints.map((point) => (
              <input key={point.id} type="hidden" name="knowledge_point_ids" value={point.id} />
            ))
          : null}
        <textarea name="question" placeholder="提出你的问题，可围绕目标、资料或选中的知识点" required />
        <button className="primary-button" type="submit" disabled={isAsking}>
          {isAsking ? <LoaderCircle className="spin-icon" size={16} /> : <MessageSquare size={16} />}
          {isAsking ? "思考中" : "提交问题"}
        </button>
        {isAsking ? <InlineThinking text="正在根据上下文组织回答..." /> : null}
      </form>

      <section className="panel">
        <PanelTitle icon={Bot} title="问答历史" />
        <div className="chat-list">
          {loading ? <p className="muted-text">正在加载问答历史...</p> : null}
          {error ? <p className="danger-text">问答历史加载失败：{error}</p> : null}
          {!loading && !error && records.length === 0 ? (
            <p className="muted-text">当前上下文还没有问答历史。</p>
          ) : null}
          {!loading && !error
            ? records.map((record) => (
                <article className="chat-card" key={record.qa_record_id}>
                  <strong>{record.question}</strong>
                  <div className="chat-answer-markdown">
                    <MarkdownAnswer>{record.answer}</MarkdownAnswer>
                  </div>
                  {record.knowledge_points?.length ? (
                    <div className="tag-cloud">
                      {record.knowledge_points.map((point) => <span key={point.id}>{point.name}</span>)}
                    </div>
                  ) : null}
                </article>
              ))
            : null}
        </div>
      </section>
      </div>
    </div>
  );
}

function PracticePage({
  targets,
  materials,
  selectedTargetId,
  selectedMaterialId,
  target,
  material,
  knowledgePoints,
  focusedKnowledgePoints,
  scope,
  questions,
  testResult,
  subView,
  questionBatchContext,
  isGenerating,
  isSubmitting,
  explainAnswers,
  explainLoading,
  onSelectTarget,
  onSelectMaterial,
  onScopeChange,
  onSelectFocusPoint,
  onSubViewChange,
  onGenerate,
  onSubmit,
  onExplainQuestion,
  onOpenWrong,
  onOpenPlans,
  onClearFocus
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedTargetId: number | null;
  selectedMaterialId: number | null;
  target: StudyTarget | null;
  material: Material | null;
  knowledgePoints: KnowledgePointReference[];
  focusedKnowledgePoints: KnowledgePointReference[];
  scope: FocusableScope;
  questions: Question[];
  testResult: TestResult | null;
  subView: PracticeSubView;
  questionBatchContext: QuestionBatchContext | null;
  isGenerating: boolean;
  isSubmitting: boolean;
  explainAnswers: Record<number, string>;
  explainLoading: Record<number, boolean>;
  onSelectTarget: (targetId: number) => void;
  onSelectMaterial: (materialId: number | null) => void;
  onScopeChange: (scope: FocusableScope) => void;
  onSelectFocusPoint: (pointId: number) => void;
  onSubViewChange: (view: PracticeSubView) => void;
  onGenerate: (formData: FormData) => void;
  onSubmit: (answers: TestSubmitAnswer[]) => void;
  onExplainQuestion: (questionId: number, question: string) => void;
  onOpenWrong: () => void;
  onOpenPlans: () => void;
  onClearFocus: () => void;
}) {
  const [objectiveAnswers, setObjectiveAnswers] = useState<Record<number, string[]>>({});
  const [subjectiveAnswers, setSubjectiveAnswers] = useState<Record<number, string>>({});
  const [questionHints, setQuestionHints] = useState<Record<number, Record<string, string>>>({});
  const [hintLoading, setHintLoading] = useState<Record<string, boolean>>({});
  const [questionSolutions, setQuestionSolutions] = useState<Record<number, QuestionSolution>>({});
  const selectedFocusIds = new Set(focusedKnowledgePoints.map((point) => point.id));
  const knowledgePointPickerLabel = material ? "当前资料关联知识点" : "当前目标全部知识点";
  const knowledgePointEmptyText = material
    ? "当前资料还没有关联知识点，请先刷新图谱或重新提炼。"
    : "当前目标还没有知识图谱节点，请先生成或刷新目标图谱。";

  useEffect(() => {
    setObjectiveAnswers({});
    setSubjectiveAnswers({});
    setQuestionHints({});
    setHintLoading({});
    setQuestionSolutions({});
  }, [questions]);

  if (!target && !material) return <EmptyPanel text="请先选择目标或资料，再进入 AI 出题页面。" />;

  const submitAnswers = questions.map((question) =>
    question.type === "subjective"
      ? { question_id: question.id, answer_text: subjectiveAnswers[question.id]?.trim() ?? "" }
      : { question_id: question.id, answer: objectiveAnswers[question.id] ?? [] }
  );
  const batchMaterial = questionBatchContext
    ? materials.find((item) => item.id === questionBatchContext.materialId)
    : null;
  const batchTarget = questionBatchContext?.targetId
    ? targets.find((item) => item.id === questionBatchContext.targetId)
    : null;

  async function handleRevealHint(questionId: number, level: number) {
    if (questionHints[questionId]?.[level]) {
      return;
    }

    const key = `${questionId}-${level}`;
    setHintLoading((current) => ({ ...current, [key]: true }));
    try {
      const data = await api.getQuestionHint(questionId, level);
      setQuestionHints((current) => ({
        ...current,
        [questionId]: {
          ...(current[questionId] ?? {}),
          [level]: data.hint
        }
      }));
    } catch (error) {
      setQuestionHints((current) => ({
        ...current,
        [questionId]: {
          ...(current[questionId] ?? {}),
          [level]: `提示加载失败：${readMessage(error)}`
        }
      }));
    } finally {
      setHintLoading((current) => ({ ...current, [key]: false }));
    }
  }

  async function handleProgressiveHelp(question: Question) {
    const revealedCount = Object.keys(questionHints[question.id] ?? {}).filter((key) => key !== "solution").length;
    const nextLevel = revealedCount + 1;

    if (nextLevel <= question.hint_count) {
      await handleRevealHint(question.id, nextLevel);
      return;
    }

    if (questionSolutions[question.id]) {
      return;
    }

    const key = `${question.id}-solution`;
    setHintLoading((current) => ({ ...current, [key]: true }));
    try {
      const solution = await api.getQuestionSolution(question.id);
      setQuestionSolutions((current) => ({
        ...current,
        [question.id]: solution
      }));
    } catch (error) {
      setQuestionHints((current) => ({
        ...current,
        [question.id]: {
          ...(current[question.id] ?? {}),
          solution: `答案加载失败：${readMessage(error)}`
        }
      }));
    } finally {
      setHintLoading((current) => ({ ...current, [key]: false }));
    }
  }

  function helpButtonText(question: Question) {
    if (questionSolutions[question.id]) {
      return "答案已显示";
    }
    const revealedCount = Object.keys(questionHints[question.id] ?? {}).filter((key) => key !== "solution").length;
    if (revealedCount >= question.hint_count) {
      return "查看答案";
    }
    return revealedCount === 0 ? "查看提示" : "继续提示";
  }

  function isHelpLoading(questionId: number) {
    return Object.entries(hintLoading).some(
      ([key, loading]) => key.startsWith(`${questionId}-`) && loading
    );
  }

  return (
    <div className="practice-layout">
      <LearningContextSelector
        targets={targets}
        materials={materials}
        selectedTargetId={selectedTargetId}
        selectedMaterialId={selectedMaterialId}
        title="出题上下文"
        onSelectTarget={onSelectTarget}
        onSelectMaterial={onSelectMaterial}
      />
      <form className="panel practice-toolbar" onSubmit={(event) => submitForm(event, onGenerate)}>
        <PanelTitle icon={ClipboardCheck} title="生成练习题" />
        <div className="practice-form-grid">
          <label className="field-block">
            <span>出题范围</span>
            <select
              name="question_scope"
              value={scope}
              onChange={(event) => onScopeChange(event.currentTarget.value as FocusableScope)}
            >
              <option value="target" disabled={!target}>目标范围</option>
              <option value="knowledge_point" disabled={!target}>聚焦知识点</option>
              <option value="material" disabled={material?.parse_status !== "parsed"}>当前资料</option>
            </select>
          </label>
          <label className="field-block">
            <span>题目数量</span>
            <input name="count" type="number" min="1" max="10" defaultValue="5" />
          </label>
          <label className="field-block">
            <span>难度</span>
            <select name="difficulty" defaultValue="medium">
              <option value="easy">easy</option>
              <option value="medium">medium</option>
              <option value="hard">hard</option>
            </select>
          </label>
          <div className="field-block question-type-field">
            <span>题型</span>
            <div className="checkbox-list">
              {questionTypeOptions.map((item) => (
                <label key={item.value} className="checkbox-row">
                  <input name="question_types" type="checkbox" value={item.value} defaultChecked={item.value !== "subjective"} />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="field-block extra-requirement-field">
            <span>自定义要求</span>
            <textarea name="extra_requirement" placeholder="例如：偏期末考试风格，优先考概念辨析；选择题干扰项要更接近真实易错点。" />
          </label>
        </div>
        {scope === "knowledge_point" ? (
          <div className="knowledge-point-picker practice-knowledge-picker">
            <div className="field-label-row">
              <span>{knowledgePointPickerLabel}</span>
              {focusedKnowledgePoints.length ? <button className="ghost-button" type="button" onClick={onClearFocus}>清除聚焦</button> : null}
            </div>
            {knowledgePoints.length ? (
              <div className="tag-cloud selectable-tags">
                {knowledgePoints.map((point) => (
                  <button
                    key={point.id}
                    type="button"
                    className={selectedFocusIds.has(point.id) ? "selected" : ""}
                    onClick={() => onSelectFocusPoint(point.id)}
                    title={`添加或移除「${point.name}」`}
                  >
                    {point.name}
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted-text">{knowledgePointEmptyText}</p>
            )}
          </div>
        ) : null}
        {scope === "knowledge_point"
          ? focusedKnowledgePoints.map((point) => (
              <input key={point.id} type="hidden" name="knowledge_point_ids" value={point.id} />
            ))
          : null}
        <div className="toolbar-actions">
          <button className="primary-button" type="submit" disabled={isGenerating || isSubmitting}>
            {isGenerating ? <LoaderCircle className="spin-icon" size={16} /> : <Sparkles size={16} />}
            {isGenerating ? "生成中" : "生成题目"}
          </button>
          <button className="ghost-button" type="button" disabled={!questions.length || !questionBatchContext || isGenerating || isSubmitting} onClick={() => onSubmit(submitAnswers)}>
            {isSubmitting ? "评分中" : "提交自测"}
          </button>
        </div>
        {isGenerating ? <InlineThinking text="正在生成题目和提示..." /> : null}
        {isSubmitting ? <InlineThinking text="正在提交答案并分析错题..." /> : null}
      </form>
      {questionBatchContext ? (
        <p className="muted-text">
          本批题目来源：{batchTarget?.title ?? `目标 ${questionBatchContext.targetId ?? "未限定"}`} ·
          {batchMaterial?.original_filename ?? `资料 ${questionBatchContext.materialId}`} ·
          {questionBatchContext.scope === "material" ? "按资料生成" : questionBatchContext.scope === "knowledge_point" ? "按聚焦知识点生成" : "按目标生成"}
        </p>
      ) : (
        <p className="muted-text">请先生成题目，系统会自动记录本批题目的真实资料归属后再允许提交自测。</p>
      )}

      <div className="practice-subnav">
        <button
          type="button"
          className={subView === "questions" ? "active-pill" : ""}
          onClick={() => onSubViewChange("questions")}
        >
          练习题
        </button>
        <button
          type="button"
          className={subView === "results" ? "active-pill" : ""}
          disabled={!testResult}
          onClick={() => onSubViewChange("results")}
        >
          测试结果
        </button>
      </div>

      {subView === "results" ? (
        <ResultsPage
          result={testResult}
          questions={questions}
          explainAnswers={explainAnswers}
          explainLoading={explainLoading}
          onExplainQuestion={onExplainQuestion}
          onOpenWrong={onOpenWrong}
          onOpenPlans={onOpenPlans}
        />
      ) : (
      <div className="question-list">
        {questions.length ? (
          questions.map((question, index) => (
            <article className="panel question-card" key={question.id}>
              <div className="question-head">
                <span>第 {index + 1} 题</span>
                <span>{question.type}</span>
              </div>
              <h3>{question.stem}</h3>
              {question.type === "subjective" ? (
                <textarea
                  className="subjective-answer"
                  placeholder="输入主观题答案，提交后由后端 AI 评分"
                  value={subjectiveAnswers[question.id] ?? ""}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setSubjectiveAnswers((current) => ({ ...current, [question.id]: value }));
                  }}
                />
              ) : (
                <div className="option-grid">
                  {question.options.map((option) => {
                    const selected = objectiveAnswers[question.id]?.includes(option.key) ?? false;
                    return (
                      <button
                        key={option.key}
                        className={`option ${selected ? "selected" : ""}`}
                        onClick={() => {
                          setObjectiveAnswers((current) => ({
                            ...current,
                            [question.id]:
                              question.type === "multiple_choice"
                                ? toggleSelection(current[question.id] ?? [], option.key)
                                : [option.key]
                          }));
                        }}
                      >
                        <span>{option.key}</span>
                        <div>
                          <strong>{option.text}</strong>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
              {question.hint_count ? (
                <div className="hint-box">
                  <div className="hint-actions">
                    <button
                      className="ghost-button"
                      type="button"
                      disabled={isHelpLoading(question.id) || questionSolutions[question.id] !== undefined}
                      onClick={() => void handleProgressiveHelp(question)}
                    >
                      {isHelpLoading(question.id) ? "加载中" : helpButtonText(question)}
                    </button>
                  </div>
                  {Object.entries(questionHints[question.id] ?? {}).length ? (
                    <div className="hint-list">
                      {Object.entries(questionHints[question.id] ?? {})
                        .filter(([level]) => level !== "solution")
                        .sort(([left], [right]) => Number(left) - Number(right))
                        .map(([level, hint]) => (
                          <p key={level}><strong>提示 {level}：</strong>{hint}</p>
                        ))}
                      {questionHints[question.id]?.solution ? (
                        <p><strong>答案：</strong>{questionHints[question.id].solution}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="form-hint">需要时逐步查看提示，第三层之后可显示答案。</p>
                  )}
                  {questionSolutions[question.id] ? (
                    <div className="solution-box">
                      <strong>参考答案：{formatAnswer(questionSolutions[question.id].correct_answer)}</strong>
                      <p>{questionSolutions[question.id].analysis}</p>
                      {questionSolutions[question.id].options.length ? (
                        <div className="solution-options">
                          {questionSolutions[question.id].options.map((option) => (
                            <p key={option.key}>
                              <strong>{option.key}. {option.text}</strong>
                              {option.analysis ? `：${option.analysis}` : ""}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <p className="analysis">
                知识点：{question.knowledge_points.length ? question.knowledge_points.join("、") : "未标注"} · 难度：{question.difficulty}
              </p>
            </article>
          ))
        ) : (
          <EmptyPanel text="还没有题目，先使用上方表单生成一组练习题。" />
        )}
      </div>
      )}
    </div>
  );
}

function ResultsPage({
  result,
  questions,
  explainAnswers,
  explainLoading,
  onExplainQuestion,
  onOpenWrong,
  onOpenPlans
}: {
  result: TestResult | null;
  questions: Question[];
  explainAnswers: Record<number, string>;
  explainLoading: Record<number, boolean>;
  onExplainQuestion: (questionId: number, question: string) => void;
  onOpenWrong: () => void;
  onOpenPlans: () => void;
}) {
  if (!result) return <EmptyPanel text="还没有测试结果。" />;

  return (
    <div className="grid dashboard-grid">
      <MetricCard icon={CheckCircle2} label="得分" value={result.score} hint="score" />
      <MetricCard icon={ClipboardCheck} label="正确率" value={`${Math.round(result.accuracy * 100)}%`} hint="accuracy" />
      <MetricCard icon={AlertTriangle} label="错题数" value={result.wrong_count} hint="wrong_count" />
      <MetricCard icon={BookOpen} label="总题数" value={result.total_count} hint="total_count" />

      <section className="panel wide">
        <PanelTitle icon={Brain} title="题目结果明细" />
        {result.knowledge_point_summary?.length ? (
          <div className="knowledge-summary-grid">
            {result.knowledge_point_summary.map((item) => (
              <div className="summary-chip" key={item.knowledge_point_id}>
                <strong>知识点 {item.knowledge_point_id}</strong>
                <span>正确率 {Math.round(item.accuracy * 100)}% · 错 {item.wrong_count}/{item.total_count}</span>
              </div>
            ))}
          </div>
        ) : null}
        <div className="list">
          {result.results.map((item) => {
            const question = questions.find((entry) => entry.id === item.question_id);
            const tone = getResultTone(item);
            return (
              <article className={`list-item vertical result-item ${tone}`} key={item.question_id}>
                <div className="result-item-head">
                  <strong>{question?.stem ?? `题目 ${item.question_id}`}</strong>
                  <span className={`result-status ${tone}`}>{resultToneLabel(tone)}</span>
                </div>
                <span>
                  你的答案：{formatAnswer(item.user_answer)} · 正确答案：{formatAnswer(item.correct_answer)} · 单题得分：{item.score}
                </span>
                {item.knowledge_point_ids.length ? <span>关联知识点 ID：{item.knowledge_point_ids.join("、")}</span> : null}
                <p>{item.analysis}</p>
                {item.matched_points.length ? <InfoList title="已覆盖要点" items={item.matched_points} /> : null}
                {item.missing_points.length ? <InfoList title="缺失要点" items={item.missing_points} /> : null}
                {item.misconceptions.length ? <InfoList title="误区" items={item.misconceptions} /> : null}
                <QuestionExplainBox
                  questionId={item.question_id}
                  answer={explainAnswers[item.question_id]}
                  loading={Boolean(explainLoading[item.question_id])}
                  onAsk={onExplainQuestion}
                />
              </article>
            );
          })}
        </div>
        <div className="quick-actions">
          <button onClick={onOpenWrong}><AlertTriangle size={16} />查看错题本</button>
          <button onClick={onOpenPlans}><CalendarDays size={16} />打开复习计划</button>
        </div>
      </section>
    </div>
  );
}

function QuestionExplainBox({
  questionId,
  answer,
  loading,
  onAsk
}: {
  questionId: number;
  answer?: string;
  loading: boolean;
  onAsk: (questionId: number, question: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");

  return (
    <div className="question-explain-box">
      <button className="ghost-button" type="button" onClick={() => setOpen((current) => !current)}>
        <MessageSquare size={16} />
        AI 追问
      </button>
      {open ? (
        <div className="question-explain-panel">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.currentTarget.value)}
            placeholder="例如：为什么选这个答案？我哪里理解错了？再举一个例子。"
          />
          <button
            className="primary-button"
            type="button"
            disabled={loading || !question.trim()}
            onClick={() => onAsk(questionId, question)}
          >
            {loading ? <LoaderCircle className="spin-icon" size={16} /> : <Bot size={16} />}
            {loading ? "思考中" : "提交追问"}
          </button>
          {answer ? (
            <div className="chat-answer-markdown">
              <MarkdownAnswer>{answer}</MarkdownAnswer>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function WrongQuestionsPage({
  items,
  targets,
  materials,
  knowledgePoints,
  filters,
  mode,
  loading,
  reviewQueue,
  reviewIndex,
  reviewLoading,
  redoSubmitting,
  redoResult,
  explainAnswers,
  explainLoading,
  onFiltersChange,
  onModeChange,
  onUpdateMastery,
  onStartReview,
  onRedo,
  onExplainQuestion,
  onNextReview,
  onExport
}: {
  items: WrongQuestion[];
  targets: StudyTarget[];
  materials: Material[];
  knowledgePoints: KnowledgePointReference[];
  filters: WrongQuestionFilters;
  mode: WrongBookMode;
  loading: boolean;
  reviewQueue: WrongQuestion[];
  reviewIndex: number;
  reviewLoading: boolean;
  redoSubmitting: boolean;
  redoResult: TestResultItem | null;
  explainAnswers: Record<number, string>;
  explainLoading: Record<number, boolean>;
  onFiltersChange: (filters: WrongQuestionFilters) => void;
  onModeChange: (mode: WrongBookMode) => void;
  onUpdateMastery: (id: number, masteryStatus: WrongQuestion["mastery_status"]) => void;
  onStartReview: () => void;
  onRedo: (id: number, answer: TestSubmitAnswer) => void;
  onExplainQuestion: (questionId: number, question: string) => void;
  onNextReview: () => void;
  onExport: () => void;
}) {
  const [objectiveAnswers, setObjectiveAnswers] = useState<Record<number, string[]>>({});
  const [subjectiveAnswers, setSubjectiveAnswers] = useState<Record<number, string>>({});
  const visibleMaterials = filters.targetId
    ? materials.filter((material) => material.target_id === filters.targetId)
    : materials;
  const groupedByStatus = (["unmastered", "reviewing", "mastered"] as const).map((status) => ({
    status,
    items: items.filter((item) => item.mastery_status === status)
  }));
  const masteryFilterOptions: Array<{
    value: WrongQuestionFilters["masteryStatus"];
    label: string;
    count: number;
  }> = [
    { value: "", label: "全部", count: items.length },
    ...(["unmastered", "reviewing", "mastered"] as const).map((status) => ({
      value: status,
      label: masteryLabel(status),
      count: items.filter((item) => item.mastery_status === status).length
    }))
  ];
  const currentReview = reviewQueue[reviewIndex] ?? null;
  const selectedAnswers = currentReview ? objectiveAnswers[currentReview.id] ?? [] : [];

  function patchFilters(partial: Partial<WrongQuestionFilters>) {
    onFiltersChange({
      ...filters,
      ...partial
    });
  }

  function submitRedo(item: WrongQuestion) {
    if (item.question_type === "subjective") {
      onRedo(item.id, {
        question_id: item.question_id,
        answer_text: subjectiveAnswers[item.id]?.trim() ?? ""
      });
      return;
    }
    onRedo(item.id, {
      question_id: item.question_id,
      answer: objectiveAnswers[item.id] ?? []
    });
  }

  function renderMasteryButtons(item: WrongQuestion) {
    return (
      <div className="quick-actions">
        {(["unmastered", "reviewing", "mastered"] as const).map((status) => (
          <button
            key={status}
            className={item.mastery_status === status ? "active-pill" : ""}
            onClick={() => onUpdateMastery(item.id, status)}
          >
            {masteryLabel(status)}
          </button>
        ))}
      </div>
    );
  }

  function renderWrongCard(item: WrongQuestion) {
    const target = targets.find((entry) => entry.id === item.target_id);
    const material = materials.find((entry) => entry.id === item.material_id);
    return (
      <article className="list-item vertical" key={item.id}>
        <div className="wrong-card-head">
          <strong>{item.stem}</strong>
          <span className={`status-badge ${item.mastery_status}`}>{masteryLabel(item.mastery_status)}</span>
        </div>
        <span>{target?.title ?? `目标 ${item.target_id ?? "未限定"}`} · {material?.original_filename ?? `资料 ${item.material_id}`}</span>
        <span>
          复习 {item.review_count} 次 · 最近复习：{formatDateTimeZh(item.last_reviewed_at)} · 下次：{formatDateTimeZh(item.next_review_at)}
        </span>
        <div className="tag-cloud">
          {item.knowledge_points.length ? item.knowledge_points.map((point) => <span key={point}>{point}</span>) : <span>未标注知识点</span>}
        </div>
        <span>你的答案：{formatAnswer(item.user_answer)} · 正确答案：{formatAnswer(item.correct_answer)}</span>
        {item.wrong_reason ? <p>{item.wrong_reason}</p> : null}
        {item.analysis ? <p>{item.analysis}</p> : null}
        {renderMasteryButtons(item)}
      </article>
    );
  }

  return (
    <section className="panel wrong-book-panel">
      <PanelTitle icon={AlertTriangle} title="错题本" />
      <div className="quick-actions">
        <button className={mode === "library" ? "active-pill" : ""} onClick={() => onModeChange("library")}>错题库</button>
        <button className={mode === "review" ? "active-pill" : ""} onClick={() => onModeChange("review")}>复习模式</button>
        <button onClick={onExport}><Download size={16} />导出错题 Markdown</button>
      </div>

      {mode === "library" ? (
        <>
          <div className="wrong-filter-grid">
            <label className="field-block">
              <span>目标</span>
              <select
                value={filters.targetId ?? ""}
                onChange={(event) => patchFilters({
                  targetId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
                  materialId: null,
                  knowledgePointId: null
                })}
              >
                <option value="">全部目标</option>
                {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
              </select>
            </label>
            <label className="field-block">
              <span>资料</span>
              <select
                value={filters.materialId ?? ""}
                onChange={(event) => patchFilters({ materialId: event.currentTarget.value ? Number(event.currentTarget.value) : null })}
              >
                <option value="">全部资料</option>
                {visibleMaterials.map((material) => <option key={material.id} value={material.id}>{material.original_filename}</option>)}
              </select>
            </label>
            <label className="field-block">
              <span>知识点</span>
              <select
                value={filters.knowledgePointId ?? ""}
                onChange={(event) => patchFilters({ knowledgePointId: event.currentTarget.value ? Number(event.currentTarget.value) : null })}
              >
                <option value="">全部知识点</option>
                {knowledgePoints.map((point) => <option key={point.id} value={point.id}>{point.name}</option>)}
              </select>
            </label>
          </div>
          {loading ? <p className="muted-text">正在加载错题...</p> : null}
          <div className="wrong-summary-grid">
            {masteryFilterOptions.map((option) => (
              <button
                className={`summary-chip mastery-filter-chip ${option.value || "all"} ${filters.masteryStatus === option.value ? "selected" : ""}`}
                key={option.value || "all"}
                type="button"
                onClick={() => patchFilters({ masteryStatus: option.value })}
              >
                <strong>{option.label}</strong>
                <span>{option.count} 题</span>
              </button>
            ))}
          </div>
          <div className="list">
            {groupedByStatus.map((group) => group.items.length ? (
              <section className="wrong-group" key={group.status}>
                <h3>{masteryLabel(group.status)}</h3>
                {group.items.map(renderWrongCard)}
              </section>
            ) : null)}
            {!loading && !items.length ? <EmptyPanel text="当前筛选条件下暂无错题。" /> : null}
          </div>
        </>
      ) : (
        <div className="wrong-review">
          <div className="quick-actions">
            <button className="primary-button" onClick={onStartReview} disabled={reviewLoading}>
              {reviewLoading ? <LoaderCircle className="spin-icon" size={16} /> : <Sparkles size={16} />}
              {reviewLoading ? "生成中" : "生成复习队列"}
            </button>
          </div>
          {currentReview ? (
            <article className="list-item vertical">
              <div className="wrong-card-head">
                <strong>第 {reviewIndex + 1} / {reviewQueue.length} 题</strong>
                <span className={`status-badge ${currentReview.mastery_status}`}>{masteryLabel(currentReview.mastery_status)}</span>
              </div>
              <h3>{currentReview.stem}</h3>
              {currentReview.question_type === "subjective" ? (
                <textarea
                  className="subjective-answer"
                  placeholder="重新作答后提交"
                  value={subjectiveAnswers[currentReview.id] ?? ""}
                  onChange={(event) => setSubjectiveAnswers((current) => ({ ...current, [currentReview.id]: event.currentTarget.value }))}
                />
              ) : (
                <div className="option-grid">
                  {currentReview.options.map((option) => {
                    const selected = selectedAnswers.includes(option.key);
                    return (
                      <button
                        key={option.key}
                        type="button"
                        className={`option ${selected ? "selected" : ""}`}
                        onClick={() =>
                          setObjectiveAnswers((current) => ({
                            ...current,
                            [currentReview.id]:
                              currentReview.question_type === "multiple_choice"
                                ? toggleSelection(current[currentReview.id] ?? [], option.key)
                                : [option.key]
                          }))
                        }
                      >
                        <span>{option.key}</span>
                        <div><strong>{option.text}</strong></div>
                      </button>
                    );
                  })}
                </div>
              )}
              <div className="toolbar-actions">
                <button className="primary-button" type="button" disabled={redoSubmitting} onClick={() => submitRedo(currentReview)}>
                  {redoSubmitting ? <LoaderCircle className="spin-icon" size={16} /> : <ClipboardCheck size={16} />}
                  {redoSubmitting ? "评分中" : "提交重做"}
                </button>
                <button type="button" disabled={reviewIndex >= reviewQueue.length - 1} onClick={onNextReview}>下一题</button>
              </div>
              {redoResult ? (
                <div className={`solution-box ${getResultTone(redoResult)}`}>
                  <div className="result-item-head">
                    <strong>本次得分：{Math.round(redoResult.score * 100)}%</strong>
                    <span className={`result-status ${getResultTone(redoResult)}`}>
                      {resultToneLabel(getResultTone(redoResult))}
                    </span>
                  </div>
                  <p>你的答案：{formatAnswer(redoResult.user_answer)} · 正确答案：{formatAnswer(redoResult.correct_answer)}</p>
                  <p>{redoResult.analysis}</p>
                  {redoResult.missing_points.length ? <InfoList title="缺失要点" items={redoResult.missing_points} /> : null}
                  {redoResult.misconceptions.length ? <InfoList title="误区" items={redoResult.misconceptions} /> : null}
                  <QuestionExplainBox
                    questionId={redoResult.question_id}
                    answer={explainAnswers[redoResult.question_id]}
                    loading={Boolean(explainLoading[redoResult.question_id])}
                    onAsk={onExplainQuestion}
                  />
                </div>
              ) : (
                <p className="muted-text">提交前不会展示答案和解析；需要时也可以直接手动标记掌握状态。</p>
              )}
              {renderMasteryButtons(currentReview)}
            </article>
          ) : (
            <EmptyPanel text="还没有复习队列，点击“生成复习队列”生成一组错题。" />
          )}
        </div>
      )}
    </section>
  );
}

function ReviewPlansPage({
  targets,
  plans,
  isGenerating,
  updatingTaskIds,
  onGenerate,
  onToggleTaskCompleted,
  onExport
}: {
  targets: StudyTarget[];
  plans: ReviewPlan[];
  isGenerating: boolean;
  updatingTaskIds: Set<number>;
  onGenerate: (formData: FormData) => void;
  onToggleTaskCompleted: (taskId: ReviewPlanTask["id"], completed: ReviewPlanTask["completed"]) => void;
  onExport: (planId: number) => void;
}) {
  return (
    <div className="two-column">
      <form className="panel form-panel" onSubmit={(event) => submitForm(event, onGenerate)}>
        <PanelTitle icon={CalendarDays} title="生成复习计划" />
        <select name="target_id" defaultValue={targets[0]?.id}>
          {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
        </select>
        <DatePickerField name="start_date" label="开始日期" placeholder="选择开始日期" required />
        <DatePickerField name="end_date" label="结束日期" placeholder="选择结束日期" required />
        <button className="primary-button" type="submit" disabled={isGenerating}>
          {isGenerating ? <LoaderCircle className="spin-icon" size={16} /> : <CalendarDays size={16} />}
          {isGenerating ? "规划中" : "生成计划"}
        </button>
        {isGenerating ? <InlineThinking text="正在根据错题和薄弱点生成复习计划..." /> : null}
      </form>

      <section className="panel">
        <PanelTitle icon={BookOpen} title="复习计划列表" />
        <div className="task-list">
          {plans.map((plan) => (
            <article className="plan-card" key={plan.id}>
              <div className="plan-head">
                <CalendarDays size={18} />
                <div>
                  <strong>{plan.title}</strong>
                  <span>{formatDateZh(plan.start_date)} 至 {formatDateZh(plan.end_date)}</span>
                </div>
              </div>
              <p>{plan.summary}</p>
              <div className="quick-actions">
                <button onClick={() => onExport(plan.id)}><Download size={16} />导出 Markdown</button>
              </div>
              <div className="task-list">
                {sortReviewPlanTasks(plan.tasks).map((task) => {
                  const isUpdating = updatingTaskIds.has(task.id);
                  return (
                    <div className={`task-row ${task.completed ? "completed" : ""}`} key={task.id}>
                      <CheckCircle2 size={18} />
                      <div>
                        <strong>{task.title}</strong>
                        <span>{formatDateZh(task.date)} · {task.completed ? "已完成" : "待完成"}</span>
                        {task.knowledge_point_id || task.material_id || task.wrong_question_id ? (
                          <span>
                            {task.knowledge_point_id ? `知识点 ${task.knowledge_point_id}` : ""}
                            {task.material_id ? ` · 资料 ${task.material_id}` : ""}
                            {task.wrong_question_id ? ` · 错题 ${task.wrong_question_id}` : ""}
                          </span>
                        ) : null}
                        <p className="task-content">{task.content}</p>
                      </div>
                      <button
                        className="ghost-button compact-button"
                        type="button"
                        disabled={isUpdating}
                        onClick={() => onToggleTaskCompleted(task.id, !task.completed)}
                      >
                        {isUpdating ? <LoaderCircle className="spin-icon" size={16} /> : <CheckCircle2 size={16} />}
                        {isUpdating ? "更新中" : task.completed ? "取消完成" : "标为已完成"}
                      </button>
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function AiUsagePage({
  summary,
  logs,
  loading,
  error,
  onRefresh
}: {
  summary: AiUsageSummary | null;
  logs: AiUsageLogItem[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const showZeroCostHint = summary
    ? summary.total_calls > 0 && Number(summary.estimated_cost) === 0
    : logs.length > 0 && logs.every((log) => Number(log.estimated_cost ?? 0) === 0);

  return (
    <div className="grid dashboard-grid">
      <MetricCard icon={Bot} label="总调用次数" value={summary?.total_calls ?? 0} hint="total_calls" />
      <MetricCard icon={Sparkles} label="Prompt Tokens" value={formatCompactNumber(summary?.prompt_tokens ?? 0)} hint="prompt_tokens" />
      <MetricCard icon={MessageSquare} label="Completion Tokens" value={formatCompactNumber(summary?.completion_tokens ?? 0)} hint="completion_tokens" />
      <MetricCard icon={Download} label="估算费用" value={formatMoney(summary?.estimated_cost, summary?.currency)} hint={summary?.billing_policy_version ?? "billing policy"} />

      <section className="panel wide">
        <PanelTitle icon={Bot} title="按功能统计" />
        <div className="quick-actions">
          <button type="button" onClick={onRefresh} disabled={loading}>
            {loading ? <LoaderCircle className="spin-icon" size={16} /> : <RefreshCw size={16} />}
            {loading ? "刷新中" : "刷新用量"}
          </button>
        </div>
        {error ? <p className="warning-text">用量刷新失败：{error}</p> : null}
        {showZeroCostHint ? (
          <p className="muted-text">已有调用记录的费用可能按旧价格记录为 0；新 AI 调用会按当前人民币价格计费。</p>
        ) : null}
        <div className="usage-grid">
          {summary?.by_feature.length ? summary.by_feature.map((item) => (
            <article className="usage-card" key={item.feature}>
              <strong>{item.feature}</strong>
              <span>{item.calls} 次调用 · {formatCompactNumber(item.total_tokens)} tokens</span>
              <small>{formatMoney(item.estimated_cost, item.currency)}</small>
            </article>
          )) : <p className="muted-text">暂无 AI 调用统计。</p>}
        </div>
      </section>

      <section className="panel wide">
        <PanelTitle icon={FileText} title="最近调用日志" />
        <div className="admin-table usage-table">
          {logs.length ? logs.map((log) => (
            <div key={log.id}>
              <span>{log.feature}</span>
              <span>{log.status}</span>
              <span>{formatCompactNumber(log.total_tokens ?? 0)} tokens</span>
              <span>{formatMoney(log.estimated_cost, log.currency)} · {log.model ?? log.provider}</span>
            </div>
          )) : <p className="muted-text">暂无调用日志。</p>}
        </div>
      </section>
    </div>
  );
}

function NoticeBar({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  return (
    <div className={`toast ${notice.tone}`}>
      {notice.tone === "danger" ? (
        <XCircle size={16} />
      ) : notice.tone === "success" ? (
        <CheckCircle2 size={16} />
      ) : notice.tone === "warning" ? (
        <AlertTriangle size={16} />
      ) : (
        <Sparkles size={16} />
      )}
      <span>{notice.text}</span>
      <button onClick={onClose}>关闭</button>
    </div>
  );
}

function MarkdownAnswer({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
    >
      {children}
    </ReactMarkdown>
  );
}

function LoadingBanner() {
  return (
    <div className="toast">
      <LoaderCircle className="spin" size={16} />
      <span>正在同步接口数据...</span>
    </div>
  );
}

function DatePickerField({
  name,
  label,
  required = false,
  placeholder = "选择日期",
  initialValue = ""
}: {
  name: string;
  label: string;
  required?: boolean;
  placeholder?: string;
  initialValue?: string;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  function openPicker() {
    const input = inputRef.current;
    if (!input) return;
    input.focus();
    try {
      if (typeof input.showPicker === "function") {
        input.showPicker();
      } else {
        input.click();
      }
    } catch {
      input.click();
    }
  }

  return (
    <div className="date-picker-field">
      <input
        ref={inputRef}
        className="date-picker-native"
        name={name}
        type="date"
        required={required}
        value={value}
        onChange={(event) => setValue(event.currentTarget.value)}
        aria-label={label}
      />
      <button className={`date-picker-display ${value ? "has-value" : ""}`} type="button" onClick={openPicker}>
        <span>{value ? formatDateZh(value) : placeholder}</span>
        <CalendarDays size={18} />
      </button>
    </div>
  );
}

function PanelTitle({ icon: Icon, title, action }: { icon: typeof Sparkles; title: string; action?: string }) {
  return (
    <div className="panel-title">
      <div>
        <Icon size={18} />
        <strong>{title}</strong>
      </div>
      {action ? <span>{action}</span> : null}
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
  onClick
}: {
  icon: typeof Sparkles;
  label: string;
  value: number | string;
  hint: string;
  onClick?: () => void;
}) {
  const content = (
    <>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </>
  );

  if (onClick) {
    return (
      <button className="metric-card clickable-panel" type="button" onClick={onClick}>
        {content}
      </button>
    );
  }

  return <section className="metric-card">{content}</section>;
}

function StatusBadge({ status }: { status: Material["parse_status"] }) {
  const tone = status === "parsed" ? "green" : status === "parsing" ? "blue" : status === "failed" ? "red" : "";
  return <span className={`badge ${tone}`}>{parseStatusText[status]}</span>;
}

function InfoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <strong>{title}</strong>
      {items.length ? (
        <ul className="clean-list">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p className="muted-text">暂无数据。</p>
      )}
    </div>
  );
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <section className="panel">
      <p className="muted-text">{text}</p>
    </section>
  );
}

function InlineThinking({ text }: { text: string }) {
  return (
    <p className="inline-thinking">
      <LoaderCircle className="spin-icon" size={16} />
      <span>{text}</span>
    </p>
  );
}

function pageTitle(view: View) {
  const titles: Record<View, string> = {
    dashboard: "学生首页 / 仪表盘",
    targets: "课程/考试目标管理",
    materials: "资料库管理",
    detail: "资料详情",
    graph: "知识图谱与掌握度",
    qa: "AI 问答页",
    practice: "AI 出题练习页",
    wrong: "错题本页",
    plans: "复习计划页",
    usage: "AI 用量与计费"
  };
  return titles[view];
}

function adminPageTitle(view: AdminView) {
  const titles: Record<AdminView, string> = {
    overview: "管理员后台 / 总览",
    users: "用户管理",
    materials: "资料管理",
    tasks: "解析任务",
    logs: "操作日志",
    health: "系统健康"
  };
  return titles[view];
}

function submitForm(event: React.FormEvent<HTMLFormElement>, handler: (formData: FormData) => void) {
  event.preventDefault();
  handler(new FormData(event.currentTarget));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatCompactNumber(value: number | string) {
  const numeric = Number(value) || 0;
  if (numeric >= 1000000) return `${(numeric / 1000000).toFixed(1)}M`;
  if (numeric >= 1000) return `${(numeric / 1000).toFixed(1)}K`;
  return String(numeric);
}

function formatMoney(value: number | string | null | undefined, currency = "CNY") {
  const numeric = Number(value) || 0;
  return `${numeric.toFixed(4)} ${currency}`;
}

function normalizeDateInput(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  if (!text) return undefined;

  const normalized = text
    .replace(/[年月/.]/g, "-")
    .replace(/日/g, "")
    .replace(/\s+/g, "");
  const match = normalized.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!match) return text;

  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function formatDateZh(value: string | null | undefined, fallback = "未设置日期") {
  if (!value) return fallback;

  const normalized = normalizeDateInput(value);
  const match = normalized?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : formatDateObjectZh(parsed);
  }

  const [, year, month, day] = match;
  return `${year}年${Number(month)}月${Number(day)}日`;
}

function formatDateObjectZh(date: Date) {
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function formatTimeObjectZh(date: Date) {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function formatAnswer(values: string[]) {
  return values.length ? values.join(", ") : "未作答";
}

type ResultTone = "success" | "partial" | "danger";

function getResultTone(result: Pick<TestResultItem, "is_correct" | "score">): ResultTone {
  if (result.is_correct || result.score >= 0.6) {
    return "success";
  }
  if (result.score > 0) {
    return "partial";
  }
  return "danger";
}

function resultToneLabel(tone: ResultTone) {
  const labels: Record<ResultTone, string> = {
    success: "已正确",
    partial: "部分正确",
    danger: "需复习"
  };
  return labels[tone];
}

function formatDateTimeZh(value: string | null | undefined, fallback = "未复习") {
  if (!value) return fallback;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${formatDateObjectZh(parsed)} ${formatTimeObjectZh(parsed)}`;
}

function masteryLabel(status: WrongQuestion["mastery_status"]) {
  const labels: Record<WrongQuestion["mastery_status"], string> = {
    unmastered: "未掌握",
    reviewing: "复习中",
    mastered: "已掌握"
  };
  return labels[status];
}

function emptyToUndefined(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function readMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求失败";
}

function toggleSelection(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export default App;
