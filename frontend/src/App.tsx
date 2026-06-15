import { useEffect, useMemo, useRef, useState } from "react";
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
  QuestionType,
  ReviewPlan,
  StudyTarget,
  TestRecord,
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
  | "results"
  | "wrong"
  | "plans"
  | "usage";

type AdminView = "overview" | "users" | "materials" | "tasks" | "logs" | "health";

type NoticeTone = "info" | "success" | "danger" | "warning";

type Notice = {
  tone: NoticeTone;
  text: string;
};

type LoginRole = "student" | "admin";

type MaterialSourcePreview = {
  materialId: number;
  url: string;
  contentType: string;
  fileType: Material["file_type"];
};

const navItems: Array<{ view: View; label: string; icon: typeof LayoutDashboard }> = [
  { view: "dashboard", label: "仪表盘", icon: LayoutDashboard },
  { view: "targets", label: "目标管理", icon: BookOpen },
  { view: "materials", label: "资料库", icon: FileText },
  { view: "graph", label: "知识图谱", icon: Network },
  { view: "qa", label: "AI 问答", icon: MessageSquare },
  { view: "practice", label: "AI 出题", icon: ClipboardCheck },
  { view: "results", label: "测试结果", icon: CheckCircle2 },
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
  const [questions, setQuestions] = useState<Question[]>([]);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestion[]>([]);
  const [reviewPlans, setReviewPlans] = useState<ReviewPlan[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeResult | null>(null);
  const [knowledgeGraph, setKnowledgeGraph] = useState<KnowledgeGraph | null>(null);
  const [structured, setStructured] = useState<MaterialStructured | null>(null);
  const [testRecords, setTestRecords] = useState<TestRecord[]>([]);
  const [preview, setPreview] = useState<MaterialPreview | null>(null);
  const [aiUsageSummary, setAiUsageSummary] = useState<AiUsageSummary | null>(null);
  const [aiUsageLogs, setAiUsageLogs] = useState<AiUsageLogItem[]>([]);
  const [sourcePreview, setSourcePreview] = useState<MaterialSourcePreview | null>(null);
  const [health, setHealth] = useState<{ api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus }>({});
  const [adminSummary, setAdminSummary] = useState<AdminSummary | null>(null);
  const [adminUsers, setAdminUsers] = useState<User[]>([]);
  const [adminMaterials, setAdminMaterials] = useState<Material[]>([]);
  const [adminTasks, setAdminTasks] = useState<AdminParseTask[]>([]);
  const [adminLogs, setAdminLogs] = useState<AdminLog[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [focusedKnowledgePointIds, setFocusedKnowledgePointIds] = useState<number[]>([]);
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
  const focusedKnowledgePoints = useMemo(
    () => knowledgeGraph?.nodes.filter((node) => focusedKnowledgePointIds.includes(node.id)) ?? [],
    [focusedKnowledgePointIds, knowledgeGraph]
  );
  const visibleMaterials = useMemo(
    () => (selectedTargetId ? materials.filter((item) => item.target_id === selectedTargetId) : []),
    [materials, selectedTargetId]
  );

  const parsedCount = materials.filter((item) => item.parse_status === "parsed").length;
  const failedCount = materials.filter((item) => item.parse_status === "failed").length;
  const isAdmin = user?.role === "admin";
  const visibleNavItems = navItems;
  const daysLeft = selectedTarget?.exam_date
    ? Math.max(0, Math.ceil((new Date(selectedTarget.exam_date).getTime() - Date.now()) / 86400000))
    : 0;

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

  useEffect(() => {
    if (!selectedTargetId || !user) {
      setKnowledgeGraph(null);
      return;
    }

    void Promise.all([
      api.getKnowledgeGraph(selectedTargetId).catch(() => null),
      api.listTestRecords(1, 10, selectedTargetId).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 }))
    ]).then(([graphData, recordData]) => {
      setKnowledgeGraph(graphData);
      setTestRecords(recordData.items);
    });
  }, [selectedTargetId, user]);

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

    const nextTargetId = targetData.items[0]?.id ?? null;
    const nextMaterialId = materialData.items[0]?.id ?? null;
    setSelectedTargetId((current) => current ?? nextTargetId);
    setSelectedMaterialId((current) => current ?? nextMaterialId);
  }

  async function loadAiUsage(targetId?: number, materialId?: number) {
    const [summary, logs] = await Promise.all([
      api.getAiUsageSummary(targetId, materialId).catch(() => null),
      api.listAiUsageLogs(1, 20, targetId, materialId).catch(() => ({ items: [], total: 0, page: 1, page_size: 20 }))
    ]);
    setAiUsageSummary(summary);
    setAiUsageLogs(logs.items);
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
      const [detailData, previewData, sourceFileBlob, structuredData, qaHistoryData] = await Promise.all([
        api.getMaterial(materialId),
        api.getMaterialPreview(materialId).catch(() => null),
        api.getMaterialFile(materialId).catch(() => null),
        api.getMaterialStructured(materialId).catch(() => null),
        api.listQaHistory(1, 10, materialId).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 }))
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
      setQaRecords(qaHistoryData.items);
    } catch (error) {
      setPreview(null);
      setSourcePreview(null);
      setStructured(null);
      setQaRecords([]);
      setNotice({ tone: "danger", text: `资料上下文加载失败：${readMessage(error)}` });
    }
  }

  async function refreshMaterialLearningContext(material: Material) {
    if (selectedMaterialId === material.id) {
      const [previewData, structuredData, qaHistoryData] = await Promise.all([
        api.getMaterialPreview(material.id).catch(() => null),
        api.getMaterialStructured(material.id).catch(() => null),
        api.listQaHistory(1, 10, material.id).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 }))
      ]);
      setPreview(previewData);
      setStructured(structuredData);
      setQaRecords(qaHistoryData.items);
    }

    const [graphData, extractionData] = await Promise.all([
      api.getKnowledgeGraph(material.target_id).catch(() => null),
      api.extractKnowledge({ target_id: material.target_id, force_regenerate: false }).catch(() => null)
    ]);

    if (selectedTargetId === material.target_id || selectedMaterialId === material.id) {
      setKnowledgeGraph(extractionData?.knowledge_graph ?? graphData);
      if (extractionData) {
        setKnowledge(extractionData);
      }
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
            ? "资料解析完成，但解析质量可能影响 AI 回答和出题。"
            : "资料解析完成，结构化内容和知识图谱已刷新。"
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
      exam_date: emptyToUndefined(formData.get("exam_date")),
      review_goal: emptyToUndefined(formData.get("review_goal")),
      description: emptyToUndefined(formData.get("description"))
    };

    try {
      const data = await api.createTarget(payload);
      setTargets((current) => [data.target, ...current]);
      setSelectedTargetId(data.target.id);
      setNotice({ tone: "success", text: "目标创建成功。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `目标创建失败：${readMessage(error)}` });
    }
  }

  async function handleUpdateTarget(targetId: number, reviewGoal: string) {
    try {
      const data = await api.updateTarget(targetId, { review_goal: reviewGoal });
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
            ? "资料解析完成，但解析质量可能影响 AI 回答和出题。"
            : "资料解析完成，结构化内容和知识图谱已刷新。"
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

  async function handleExtractKnowledge(scope: "material" | "target" = "material") {
    if (scope === "target") {
      if (!selectedTargetId) {
        setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
        return;
      }

      try {
        const data = await api.extractKnowledge({ targetId: selectedTargetId, forceRegenerate: true });
        setKnowledge(data);
        const graph = await api.getKnowledgeGraph(selectedTargetId).catch(() => null);
        setKnowledgeGraph(graph);
        setNotice({ tone: "success", text: "目标级知识提炼已刷新。" });
      } catch (error) {
        setNotice({ tone: "danger", text: `目标级知识提炼失败：${readMessage(error)}` });
      }
      return;
    }

    if (!selectedMaterial) {
      return;
    }
    try {
      const data = await api.extractKnowledge({ materialId: selectedMaterial.id });
      setKnowledge(data);
      setNotice({ tone: "success", text: "知识提炼完成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `知识提炼失败：${readMessage(error)}` });
    }
  }

  async function handleAskQuestion(formData: FormData) {
    const scope = String(formData.get("qa_scope") ?? "target");
    const knowledgePointId = Number(formData.get("knowledge_point_id")) || undefined;
    const question = String(formData.get("question") ?? "").trim();
    if (!question) {
      return;
    }

    if (scope === "material" && selectedMaterial?.parse_status !== "parsed") {
      setNotice({ tone: "danger", text: "当前资料尚未解析完成，不能按资料提问。" });
      return;
    }
    if (scope !== "material" && !selectedTargetId) {
      setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
      return;
    }

    try {
      const data = await api.askQuestion(
        scope === "material"
          ? { materialId: selectedMaterial?.id, question }
          : { targetId: selectedTargetId ?? undefined, knowledgePointId, question }
      );
      setQaRecords((current) => [data, ...current]);
      setNotice({ tone: "success", text: "问答已生成并写入历史。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `问答失败：${readMessage(error)}` });
    }
  }

  async function handleGenerateQuestions(formData: FormData) {
    const scope = String(formData.get("question_scope") ?? "target");
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
      if (scope === "material" && selectedMaterial?.parse_status !== "parsed") {
        setNotice({ tone: "danger", text: "当前资料尚未解析完成，不能按资料出题。" });
        return;
      }
      if (scope !== "material" && !selectedTargetId) {
        setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
        return;
      }

      const data = await api.generateQuestions({
        materialId: scope === "material" ? selectedMaterial?.id : undefined,
        targetId: scope === "material" ? undefined : selectedTargetId ?? undefined,
        knowledgePointIds,
        extraRequirement,
        count,
        difficulty,
        questionTypes
      });
      setQuestions(data.questions);
      setView("practice");
      setNotice({ tone: "success", text: scope === "material" ? "题目已按资料生成。" : "题目已按目标/知识点生成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `题目生成失败：${readMessage(error)}` });
    }
  }

  async function handleSubmitTest(answers: TestSubmitAnswer[]) {
    if (!selectedMaterial) {
      return;
    }
    try {
      const data = await api.submitTest(selectedMaterial.id, selectedMaterial.target_id, answers);
      setTestResult(data);
      setView("results");
      setNotice({ tone: "success", text: "自测已提交。" });
      const wrongData = await api.listWrongQuestions(1, 10, selectedMaterial.target_id, selectedMaterial.id).catch(() => null);
      if (wrongData) {
        setWrongQuestions(wrongData.items);
      }
      const graph = await api.getKnowledgeGraph(selectedMaterial.target_id).catch(() => null);
      setKnowledgeGraph(graph);
    } catch (error) {
      setNotice({ tone: "danger", text: `自测提交失败：${readMessage(error)}` });
    }
  }

  async function handleUpdateMastery(id: number, masteryStatus: WrongQuestion["mastery_status"]) {
    try {
      const updated = await api.updateWrongQuestionMastery(id, masteryStatus);
      setWrongQuestions((current) => current.map((item) => (item.id === id ? updated : item)));
      setNotice({ tone: "info", text: "错题掌握状态已更新。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `错题状态更新失败：${readMessage(error)}` });
    }
  }

  async function handleGenerateReviewPlan(formData: FormData) {
    const targetId = Number(formData.get("target_id"));
    const startDate = String(formData.get("start_date") ?? "");
    const endDate = String(formData.get("end_date") ?? "");
    try {
      const plan = await api.generateReviewPlan(targetId, startDate, endDate);
      setReviewPlans((current) => [plan, ...current.filter((item) => item.id !== plan.id)]);
      setView("plans");
      setNotice({ tone: "success", text: "复习计划已生成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `复习计划生成失败：${readMessage(error)}` });
    }
  }

  async function handleGenerateKnowledgeGraph() {
    if (!selectedTargetId) {
      setNotice({ tone: "danger", text: "请先选择一个学习目标。" });
      return;
    }

    try {
      const graph = await api.generateKnowledgeGraph(selectedTargetId);
      setKnowledgeGraph(graph);
      setView("graph");
      setNotice({ tone: "success", text: "知识图谱已生成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `知识图谱生成失败：${readMessage(error)}` });
    }
  }

  async function handleUpdateKnowledgePointMastery(id: number, masteryStatus: WrongQuestion["mastery_status"]) {
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
    setQuestions([]);
    setTestResult(null);
    setWrongQuestions([]);
    setReviewPlans([]);
    setKnowledge(null);
    setKnowledgeGraph(null);
    setStructured(null);
    setTestRecords([]);
    setPreview(null);
    setAiUsageSummary(null);
    setAiUsageLogs([]);
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
    setFocusedKnowledgePointIds([]);
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
            parsedCount={parsedCount}
            failedCount={failedCount}
            daysLeft={daysLeft}
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
            onSelect={setSelectedTargetId}
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
            onSelectTarget={(targetId) => {
              setSelectedTargetId(targetId);
              setSelectedMaterialId(null);
            }}
            onSelect={(material) => {
              setSelectedMaterialId(material.id);
              setSelectedTargetId(material.target_id);
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
            onParse={() => {
              if (selectedMaterial) {
                void handleParseMaterial(selectedMaterial.id);
              }
            }}
            onExtractMaterial={() => void handleExtractKnowledge("material")}
            onExtractTarget={() => void handleExtractKnowledge("target")}
            onGenerateGraph={handleGenerateKnowledgeGraph}
            onExportKnowledge={() => {
              if (selectedTargetId) {
                void handleExport(() => api.exportKnowledgeSummary(selectedTargetId), "知识总结已开始下载。");
              }
            }}
            onJumpToQa={() => setView("qa")}
            onJumpToPractice={() => setView("practice")}
            onBack={() => setView("materials")}
          />
        ) : null}

        {view === "graph" ? (
          <KnowledgeGraphPage
            target={selectedTarget}
            graph={knowledgeGraph}
            onGenerate={handleGenerateKnowledgeGraph}
            onUpdatePointMastery={(id, status) => void handleUpdateKnowledgePointMastery(id, status)}
            onFocusQa={(point) => {
              setFocusedKnowledgePointIds([point.id]);
              setView("qa");
            }}
            onFocusPractice={(point) => {
              setFocusedKnowledgePointIds([point.id]);
              setView("practice");
            }}
            onExport={() => {
              if (selectedTargetId) {
                void handleExport(() => api.exportKnowledgeSummary(selectedTargetId), "知识总结已开始下载。");
              }
            }}
            onExportAnki={() => {
              if (selectedTargetId) {
                void handleExport(() => api.exportAnki(selectedTargetId), "Anki CSV 已开始下载。");
              }
            }}
          />
        ) : null}

        {view === "qa" ? (
          <QaPage
            target={selectedTarget}
            material={selectedMaterial}
            focusedKnowledgePoints={focusedKnowledgePoints}
            records={qaRecords}
            onAsk={handleAskQuestion}
            onClearFocus={() => setFocusedKnowledgePointIds([])}
          />
        ) : null}

        {view === "practice" ? (
          <PracticePage
            target={selectedTarget}
            material={selectedMaterial}
            focusedKnowledgePoints={focusedKnowledgePoints}
            questions={questions}
            onGenerate={handleGenerateQuestions}
            onSubmit={handleSubmitTest}
            onClearFocus={() => setFocusedKnowledgePointIds([])}
          />
        ) : null}

        {view === "results" ? (
          <ResultsPage result={testResult} questions={questions} onOpenWrong={() => setView("wrong")} onOpenPlans={() => setView("plans")} />
        ) : null}

        {view === "wrong" ? (
          <WrongQuestionsPage
            items={wrongQuestions}
            onUpdateMastery={handleUpdateMastery}
            onExport={() =>
              void handleExport(
                () => api.exportWrongQuestions(selectedTargetId ?? undefined, selectedMaterialId ?? undefined),
                "错题本已开始下载。"
              )
            }
          />
        ) : null}

        {view === "plans" ? (
          <ReviewPlansPage
            targets={targets}
            plans={reviewPlans}
            onGenerate={handleGenerateReviewPlan}
            onExport={(planId) => void handleExport(() => api.exportReviewPlan(planId), "复习计划已开始下载。")}
          />
        ) : null}

        {view === "usage" ? (
          <AiUsagePage
            summary={aiUsageSummary}
            logs={aiUsageLogs}
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
      <MetricCard icon={UserCircle} label="学生 / 管理员" value={`${summary?.student_users ?? 0} / ${summary?.admin_users ?? 0}`} hint="role 分布" />
      <MetricCard icon={Shield} label="启用 / 禁用" value={`${summary?.active_users ?? 0} / ${summary?.inactive_users ?? 0}`} hint="账号状态" />
      <MetricCard icon={FileText} label="资料总数" value={summary?.total_materials ?? 0} hint="全站资料" />
      <MetricCard icon={AlertTriangle} label="失败资料" value={failedMaterials} hint="parse_status = failed" />
      <MetricCard icon={AlertTriangle} label="失败任务" value={summary?.failed_tasks ?? 0} hint="task_status = failed" />
      <MetricCard icon={Shield} label="数据库健康" value={health.db?.status ?? "error"} hint="GET /health/db" />
      <MetricCard icon={Shield} label="Redis 健康" value={health.redis?.status ?? "error"} hint="GET /health/redis" />

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
            <span>{new Date(log.created_at).toLocaleString()}</span>
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
      <MetricCard icon={Shield} label="API 健康" value={health.api?.status ?? "error"} hint="GET /health" />
      <MetricCard icon={Shield} label="数据库健康" value={health.db?.status ?? "error"} hint="GET /health/db" />
      <MetricCard icon={Shield} label="Redis 健康" value={health.redis?.status ?? "error"} hint="GET /health/redis" />
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

  return (
    <div className="auth-screen">
      <section className="auth-copy">
        <div className="brand large">
          <div className="brand-mark">
            <Sparkles size={28} />
          </div>
          <div>
            <strong>AI 智能备考复习平台</strong>
            <span>注册、登录后进入资料解析、AI 问答、出题、自测、错题和复习计划闭环。</span>
          </div>
        </div>
        <div className="hero-phone">
          <div className="phone-island" />
          <div className="mini-card blue">上传 TXT 资料</div>
          <div className="mini-card green">解析后启用 AI 学习</div>
          <div className="mini-card">沉淀错题并生成复习计划</div>
        </div>
      </section>

      <form className="auth-panel" onSubmit={(event) => submitForm(event, mode === "login" ? onLogin : onRegister)}>
        <div>
          <p className="eyebrow">{mode === "login" ? "POST /auth/login" : "POST /auth/register"}</p>
          <h1>{mode === "login" ? (loginRole === "admin" ? "管理员登录" : "学生登录") : "学生注册"}</h1>
        </div>

        {notice ? <NoticeBar notice={notice} onClose={onCloseNotice} /> : null}
        {loading ? <LoadingBanner /> : null}

        {mode === "login" ? (
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
        {mode === "login" ? <input type="hidden" name="login_role" value={loginRole} /> : null}
        <input name="username" placeholder="用户名" minLength={3} required />
        <input name="password" type="password" placeholder="密码" minLength={6} required />
        {mode === "register" ? <input name="display_name" placeholder="昵称（可选）" /> : null}

        <button className="primary-button" type="submit" disabled={loading}>
          <UserCircle size={16} />
          {mode === "login" ? "登录并同步数据" : "注册并登录"}
        </button>
        <button
          className="ghost-button"
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setLoginRole("student");
          }}
        >
          {mode === "login" ? "没有账号？创建新账号" : "已有账号？返回登录"}
        </button>
      </form>
    </div>
  );
}

function Dashboard({
  targets,
  materials,
  parsedCount,
  failedCount,
  daysLeft,
  wrongQuestions,
  reviewPlans,
  testRecords,
  knowledgeGraph,
  aiUsageSummary,
  onQuickView
}: {
  targets: StudyTarget[];
  materials: Material[];
  parsedCount: number;
  failedCount: number;
  daysLeft: number;
  wrongQuestions: WrongQuestion[];
  reviewPlans: ReviewPlan[];
  testRecords: TestRecord[];
  knowledgeGraph: KnowledgeGraph | null;
  aiUsageSummary: AiUsageSummary | null;
  onQuickView: (view: View) => void;
}) {
  const parseStats = [
    { label: "可学习", value: parsedCount, tone: "green" },
    { label: "解析中", value: materials.filter((item) => item.parse_status === "parsing").length, tone: "blue" },
    { label: "失败", value: failedCount, tone: "red" },
    { label: "待解析", value: materials.filter((item) => item.parse_status === "uploaded").length, tone: "" }
  ];
  const upcomingTasks = reviewPlans.flatMap((plan) => plan.tasks.filter((task) => !task.completed)).slice(0, 4);
  const averageAccuracy = testRecords.length
    ? Math.round((testRecords.reduce((sum, item) => sum + item.accuracy, 0) / testRecords.length) * 100)
    : 0;

  return (
    <div className="grid dashboard-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">当前主目标</p>
          <h2>{targets[0]?.title ?? "还没有学习目标"}</h2>
          <p>{targets[0]?.review_goal ?? "先创建一个课程/考试目标，再开始上传资料和 AI 学习。"}</p>
          <div className="quick-actions">
            <button onClick={() => onQuickView("targets")}><Plus size={16} />新建目标</button>
            <button onClick={() => onQuickView("materials")}><Upload size={16} />上传资料</button>
            <button onClick={() => onQuickView("graph")}><Network size={16} />查看图谱</button>
          </div>
        </div>
        <div className="progress-ring">
          <strong>{daysLeft}</strong>
          <span>距离考试天数</span>
        </div>
      </section>

      <MetricCard icon={BookOpen} label="学习目标" value={targets.length} hint="对应 /study-targets" />
      <MetricCard icon={FileText} label="资料总数" value={materials.length} hint="对应 /materials" />
      <MetricCard icon={Brain} label="可学习资料" value={parsedCount} hint="parse_status = parsed" />
      <MetricCard icon={AlertTriangle} label="失败资料" value={failedCount} hint="需关注 parse_error" />

      <section className="panel">
        <PanelTitle icon={FileText} title="资料解析状态" />
        <div className="stat-bars">
          {parseStats.map((item) => (
            <div className="stat-bar" key={item.label}>
              <span>{item.label}</span>
              <div><i className={item.tone} style={{ width: `${materials.length ? Math.max(8, (item.value / materials.length) * 100) : 0}%` }} /></div>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
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
      </section>

      <MetricCard icon={ClipboardCheck} label="近期自测均分" value={`${averageAccuracy}%`} hint="GET /tests/records" />
      <MetricCard icon={AlertTriangle} label="错题总数" value={wrongQuestions.length} hint="高频薄弱点入口" />
      <MetricCard icon={Bot} label="AI 调用" value={aiUsageSummary?.total_calls ?? 0} hint="GET /ai-usage/summary" />
      <MetricCard icon={Sparkles} label="Token 总量" value={formatCompactNumber(aiUsageSummary?.total_tokens ?? 0)} hint="本地计量估算" />

      <section className="panel wide">
        <PanelTitle icon={CalendarDays} title="即将复习任务" />
        <div className="task-list">
          {upcomingTasks.length ? upcomingTasks.map((task) => (
            <div className="task-row" key={task.id}>
              <CheckCircle2 size={18} />
              <div>
                <strong>{task.title}</strong>
                <span>{task.date} · 待完成</span>
              </div>
            </div>
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
  onUpdate: (id: number, reviewGoal: string) => void;
  onDelete: (id: number) => void;
}) {
  const selected = targets.find((item) => item.id === selectedTargetId) ?? targets[0] ?? null;

  return (
    <div className="two-column">
      <form className="panel form-panel" onSubmit={(event) => submitForm(event, onCreate)}>
        <PanelTitle icon={Plus} title="创建目标" action="POST /study-targets" />
        <input name="title" placeholder="目标标题" required />
        <input name="subject" placeholder="学科名称" required />
        <select name="target_type" defaultValue="exam">
          <option value="exam">exam</option>
          <option value="course">course</option>
        </select>
        <input name="exam_date" type="date" />
        <textarea name="review_goal" placeholder="复习目标" required />
        <textarea name="description" placeholder="补充说明（可选）" />
        <button className="primary-button" type="submit"><Plus size={16} />创建目标</button>
      </form>

      <section className="panel">
        <PanelTitle icon={BookOpen} title="目标列表" />
        <div className="list">
          {targets.map((target) => (
            <button key={target.id} className={`material-row ${target.id === selected?.id ? "selected" : ""}`} onClick={() => onSelect(target.id)}>
              <div>
                <strong>{target.title}</strong>
                <span>{target.subject ?? "未设置科目"} · {target.target_type} · {target.exam_date || "无考试日期"}</span>
              </div>
            </button>
          ))}
        </div>

        {selected ? (
          <div className="detail-stack">
            <label className="field-block">
              <span>当前复习目标</span>
              <textarea
                defaultValue={selected.review_goal ?? ""}
                onBlur={(event) => {
                  const nextValue = event.currentTarget.value.trim();
                  if (nextValue && nextValue !== selected.review_goal) {
                    onUpdate(selected.id, nextValue);
                  }
                }}
              />
            </label>
            <button className="danger-button" onClick={() => onDelete(selected.id)}><Trash2 size={16} />删除当前目标</button>
          </div>
        ) : null}
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
          <PanelTitle icon={FileText} title="资料库" action={selectedTarget?.title ?? "请选择目标"} />
          <p className="muted-text">当前页面只展示所选学习目标下的资料，上传的新资料也会自动加入该目标。</p>
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
          <PanelTitle icon={Upload} title="上传资料" action="POST /materials" />
          <p className="form-hint">
            {selectedTarget ? `上传后会加入当前目标：${selectedTarget.title}` : "请先在上方选择学习目标。"}
          </p>
          <label className="drop-zone">
            <Upload size={28} />
            <span>选择 PDF / TXT / 图片资料</span>
            <small>上传后后端会自动解析；TXT 最稳定，PDF/图片会尝试 OCR</small>
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
  onParse,
  onExtractMaterial,
  onExtractTarget,
  onGenerateGraph,
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
  onParse: () => void;
  onExtractMaterial: () => void;
  onExtractTarget: () => void;
  onGenerateGraph: () => void;
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
            <button disabled={material.parse_status === "parsing"} onClick={onParse}><RefreshCw size={16} />解析资料</button>
            <button disabled={aiDisabled} onClick={onExtractMaterial}><Sparkles size={16} />资料提炼</button>
            <button disabled={!target} onClick={onExtractTarget}><Sparkles size={16} />目标提炼</button>
            <button disabled={aiDisabled} onClick={onGenerateGraph}><Network size={16} />生成图谱</button>
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
            <div className="detail-stack">
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

function KnowledgeGraphPage({
  target,
  graph,
  onGenerate,
  onUpdatePointMastery,
  onFocusQa,
  onFocusPractice,
  onExport,
  onExportAnki
}: {
  target: StudyTarget | null;
  graph: KnowledgeGraph | null;
  onGenerate: () => void;
  onUpdatePointMastery: (id: number, masteryStatus: WrongQuestion["mastery_status"]) => void;
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
  const activeNode = graph?.nodes.find((node) => node.id === activeId) ?? graph?.nodes[0] ?? null;

  useEffect(() => {
    setActiveId(graph?.nodes[0]?.id ?? null);
  }, [graph?.target_id, graph?.nodes.length]);

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
    <div className="two-column graph-layout">
      <section className="panel wide">
        <PanelTitle icon={Network} title="知识点图谱" action={target?.title} />
        <div className="quick-actions">
          <button onClick={onGenerate}><RefreshCw size={16} />生成/刷新图谱</button>
          <button disabled={!target} onClick={onExport}><Download size={16} />导出知识总结</button>
          <button disabled={!target} onClick={onExportAnki}><Download size={16} />导出 Anki CSV</button>
        </div>
        {graph?.nodes.length ? (
          <div className="graph-canvas">
            {graph.nodes.map((node) => (
              <button
                key={node.id}
                className={`graph-node ${node.mastery_status} ${activeNode?.id === node.id ? "selected" : ""}`}
                style={{
                  width: `${56 + node.importance_weight * 42}px`,
                  minHeight: `${44 + node.importance_weight * 30}px`
                }}
                onClick={() => setActiveId(node.id)}
                title={`${node.name} · 正确率 ${Math.round(node.accuracy * 100)}%`}
              >
                <strong>{node.name}</strong>
                <span>{Math.round(node.mastery_score * 100)}%</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyPanel text="当前目标还没有知识图谱，先生成图谱或完成资料解析。" />
        )}
      </section>

      <section className="panel">
        <PanelTitle icon={Brain} title="知识点详情" />
        {activeNode ? (
          <div className="detail-stack">
            <h3>{activeNode.name}</h3>
            <p>{activeNode.description ?? "暂无描述。"}</p>
            <div className="mini-metrics">
              <span>掌握度 {Math.round(activeNode.mastery_score * 100)}%</span>
              <span>正确率 {Math.round(activeNode.accuracy * 100)}%</span>
              <span>错题 {activeNode.wrong_count}</span>
              <span>作答 {activeNode.answered_count}</span>
            </div>
            <InfoList title="关联资料片段" items={activeNode.materials.map((item) => item.evidence_text || `资料 ${item.material_id}`)} />
            <div className="quick-actions">
              <button onClick={() => onFocusQa(activeNode)}><MessageSquare size={16} />围绕此点提问</button>
              <button onClick={() => onFocusPractice(activeNode)}><ClipboardCheck size={16} />按此点出题</button>
            </div>
            <div className="quick-actions">
              {(["unmastered", "reviewing", "mastered"] as const).map((status) => (
                <button key={status} className={activeNode.mastery_status === status ? "active-pill" : ""} onClick={() => onUpdatePointMastery(activeNode.id, status)}>
                  {status}
                </button>
              ))}
            </div>
            {detail.loading ? <p className="muted-text">正在加载知识点详情...</p> : null}
            {detail.error ? <p className="danger-text">{detail.error}</p> : null}
            <InfoList title="精确关联资料" items={detail.materials.map((item) => `${item.original_filename}${item.evidence_text ? `：${item.evidence_text}` : ""}`)} />
            <InfoList title="关联题目" items={detail.questions.map((item) => item.stem)} />
            <InfoList title="关联错题" items={detail.wrongQuestions.map((item) => item.stem)} />
          </div>
        ) : (
          <p className="muted-text">请选择一个知识点。</p>
        )}
      </section>
    </div>
  );
}

function QaPage({
  target,
  material,
  focusedKnowledgePoints,
  records,
  onAsk,
  onClearFocus
}: {
  target: StudyTarget | null;
  material: Material | null;
  focusedKnowledgePoints: KnowledgePointReference[];
  records: QaRecord[];
  onAsk: (formData: FormData) => void;
  onClearFocus: () => void;
}) {
  if (!target && !material) return <EmptyPanel text="请先选择目标或资料，再进入 AI 问答页面。" />;

  const defaultScope = focusedKnowledgePoints.length && target ? "knowledge_point" : target ? "target" : "material";

  return (
    <div className="two-column qa-layout">
      <form className="panel form-panel" onSubmit={(event) => submitForm(event, onAsk)}>
        <PanelTitle icon={MessageSquare} title="提问" />
        <p className="muted-text">
          当前目标：{target?.title ?? "未选择"}；当前资料：{material?.original_filename ?? "未选择"}
        </p>
        {focusedKnowledgePoints.length ? (
          <div className="tag-cloud">
            {focusedKnowledgePoints.map((point) => <span key={point.id}>{point.name}</span>)}
            <button className="ghost-button" type="button" onClick={onClearFocus}>清除聚焦</button>
          </div>
        ) : null}
        <select name="qa_scope" defaultValue={defaultScope}>
          <option value="target" disabled={!target}>目标范围</option>
          <option value="knowledge_point" disabled={!target || !focusedKnowledgePoints.length}>聚焦知识点</option>
          <option value="material" disabled={!material}>当前资料</option>
        </select>
        {focusedKnowledgePoints[0] ? <input type="hidden" name="knowledge_point_id" value={focusedKnowledgePoints[0].id} /> : null}
        <textarea name="question" placeholder="提出你的问题，可围绕目标、资料或选中的知识点" required />
        <button className="primary-button" type="submit">
          <MessageSquare size={16} />提交问题
        </button>
      </form>

      <section className="panel">
        <PanelTitle icon={Bot} title="问答历史" />
        <div className="chat-list">
          {records.map((record) => (
            <article className="chat-card" key={record.qa_record_id}>
              <strong>{record.question}</strong>
              <p>{record.answer}</p>
              {record.knowledge_points?.length ? (
                <div className="tag-cloud">
                  {record.knowledge_points.map((point) => <span key={point.id}>{point.name}</span>)}
                </div>
              ) : null}
              {record.references.length ? <blockquote>{record.references[0].snippet}</blockquote> : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PracticePage({
  target,
  material,
  focusedKnowledgePoints,
  questions,
  onGenerate,
  onSubmit,
  onClearFocus
}: {
  target: StudyTarget | null;
  material: Material | null;
  focusedKnowledgePoints: KnowledgePointReference[];
  questions: Question[];
  onGenerate: (formData: FormData) => void;
  onSubmit: (answers: TestSubmitAnswer[]) => void;
  onClearFocus: () => void;
}) {
  const [objectiveAnswers, setObjectiveAnswers] = useState<Record<number, string[]>>({});
  const [subjectiveAnswers, setSubjectiveAnswers] = useState<Record<number, string>>({});

  useEffect(() => {
    setObjectiveAnswers({});
    setSubjectiveAnswers({});
  }, [questions]);

  if (!target && !material) return <EmptyPanel text="请先选择目标或资料，再进入 AI 出题页面。" />;

  const submitAnswers = questions.map((question) =>
    question.type === "subjective"
      ? { question_id: question.id, answer_text: subjectiveAnswers[question.id]?.trim() ?? "" }
      : { question_id: question.id, answer: objectiveAnswers[question.id] ?? [] }
  );
  const defaultScope = focusedKnowledgePoints.length && target ? "target" : target ? "target" : "material";

  return (
    <div className="practice-layout">
      <form className="panel practice-toolbar" onSubmit={(event) => submitForm(event, onGenerate)}>
        <PanelTitle icon={ClipboardCheck} title="生成练习题" />
        <div className="toolbar-fields practice-scope">
          <select name="question_scope" defaultValue={defaultScope}>
            <option value="target" disabled={!target}>目标/知识点</option>
            <option value="material" disabled={!material}>当前资料</option>
          </select>
          <input name="count" type="number" min="1" max="10" defaultValue="5" />
        </div>
        <div className="checkbox-list">
          {questionTypeOptions.map((item) => (
            <label key={item.value} className="checkbox-row">
              <input name="question_types" type="checkbox" value={item.value} defaultChecked={item.value !== "subjective"} />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
        <div className="toolbar-fields">
          <select name="difficulty" defaultValue="medium">
            <option value="easy">easy</option>
            <option value="medium">medium</option>
            <option value="hard">hard</option>
          </select>
          <input name="extra_requirement" placeholder="自定义要求：如偏期末风格" />
        </div>
        {focusedKnowledgePoints.length ? (
          <div className="focused-points">
            {focusedKnowledgePoints.map((point) => (
              <label key={point.id} className="checkbox-row">
                <input name="knowledge_point_ids" type="checkbox" value={point.id} defaultChecked />
                <span>{point.name}</span>
              </label>
            ))}
            <button className="ghost-button" type="button" onClick={onClearFocus}>清除聚焦</button>
          </div>
        ) : null}
        <div className="toolbar-actions">
          <button className="primary-button" type="submit">
            <Sparkles size={16} />生成题目
          </button>
          <button className="ghost-button" type="button" disabled={!questions.length || !material} onClick={() => onSubmit(submitAnswers)}>
            提交自测
          </button>
        </div>
      </form>
      {!material ? <p className="muted-text">当前后端自测提交仍要求 material_id，请选择目标下任一资料后再提交自测。</p> : null}

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
                    setSubjectiveAnswers((current) => ({ ...current, [question.id]: event.currentTarget.value }));
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
                          {option.analysis ? <small>{option.analysis}</small> : null}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
              <p className="analysis">
                知识点：{question.knowledge_points.length ? question.knowledge_points.join("、") : "未标注"} · 难度：{question.difficulty}
              </p>
            </article>
          ))
        ) : (
          <EmptyPanel text="还没有题目，先使用上方表单生成一组练习题。" />
        )}
      </div>
    </div>
  );
}

function ResultsPage({
  result,
  questions,
  onOpenWrong,
  onOpenPlans
}: {
  result: TestResult | null;
  questions: Question[];
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
            return (
              <article className="list-item vertical" key={item.question_id}>
                <strong>{question?.stem ?? `题目 ${item.question_id}`}</strong>
                <span>
                  你的答案：{formatAnswer(item.user_answer)} · 正确答案：{formatAnswer(item.correct_answer)} · 单题得分：{item.score}
                </span>
                {item.knowledge_point_ids.length ? <span>关联知识点 ID：{item.knowledge_point_ids.join("、")}</span> : null}
                <p>{item.analysis}</p>
                {item.matched_points.length ? <InfoList title="已覆盖要点" items={item.matched_points} /> : null}
                {item.missing_points.length ? <InfoList title="缺失要点" items={item.missing_points} /> : null}
                {item.misconceptions.length ? <InfoList title="误区" items={item.misconceptions} /> : null}
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

function WrongQuestionsPage({
  items,
  onUpdateMastery,
  onExport
}: {
  items: WrongQuestion[];
  onUpdateMastery: (id: number, masteryStatus: WrongQuestion["mastery_status"]) => void;
  onExport: () => void;
}) {
  return (
    <section className="panel">
      <PanelTitle icon={AlertTriangle} title="错题本" />
      <div className="quick-actions">
        <button onClick={onExport}><Download size={16} />导出错题 Markdown</button>
      </div>
      <div className="list">
        {items.map((item) => (
          <article className="list-item vertical" key={item.id}>
            <strong>{item.stem}</strong>
            <span>知识点：{item.knowledge_points.length ? item.knowledge_points.join("、") : "未标注"}</span>
            <span>你的答案：{formatAnswer(item.user_answer)} · 正确答案：{formatAnswer(item.correct_answer)}</span>
            {item.wrong_reason ? <p>{item.wrong_reason}</p> : null}
            {item.analysis ? <p>{item.analysis}</p> : null}
            <div className="quick-actions">
              {(["unmastered", "reviewing", "mastered"] as const).map((status) => (
                <button key={status} className={item.mastery_status === status ? "active-pill" : ""} onClick={() => onUpdateMastery(item.id, status)}>
                  {status}
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ReviewPlansPage({
  targets,
  plans,
  onGenerate,
  onExport
}: {
  targets: StudyTarget[];
  plans: ReviewPlan[];
  onGenerate: (formData: FormData) => void;
  onExport: (planId: number) => void;
}) {
  return (
    <div className="two-column">
      <form className="panel form-panel" onSubmit={(event) => submitForm(event, onGenerate)}>
        <PanelTitle icon={CalendarDays} title="生成复习计划" />
        <select name="target_id" defaultValue={targets[0]?.id}>
          {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
        </select>
        <input name="start_date" type="date" required />
        <input name="end_date" type="date" required />
        <button className="primary-button" type="submit"><CalendarDays size={16} />生成计划</button>
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
                  <span>{plan.start_date} 至 {plan.end_date}</span>
                </div>
              </div>
              <p>{plan.summary}</p>
              <div className="quick-actions">
                <button onClick={() => onExport(plan.id)}><Download size={16} />导出 Markdown</button>
              </div>
              <div className="task-list">
                {plan.tasks.map((task) => (
                  <div className="task-row" key={task.id}>
                    <CheckCircle2 size={18} />
                    <div>
                      <strong>{task.title}</strong>
                      <span>{task.date} · {task.completed ? "已完成" : "待完成"}</span>
                      {task.knowledge_point_id || task.material_id || task.wrong_question_id ? (
                        <span>
                          {task.knowledge_point_id ? `知识点 ${task.knowledge_point_id}` : ""}
                          {task.material_id ? ` · 资料 ${task.material_id}` : ""}
                          {task.wrong_question_id ? ` · 错题 ${task.wrong_question_id}` : ""}
                        </span>
                      ) : null}
                      <p className="task-content">{task.content}</p>
                    </div>
                  </div>
                ))}
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
  onRefresh
}: {
  summary: AiUsageSummary | null;
  logs: AiUsageLogItem[];
  onRefresh: () => void;
}) {
  return (
    <div className="grid dashboard-grid">
      <MetricCard icon={Bot} label="总调用次数" value={summary?.total_calls ?? 0} hint="total_calls" />
      <MetricCard icon={Sparkles} label="Prompt Tokens" value={formatCompactNumber(summary?.prompt_tokens ?? 0)} hint="prompt_tokens" />
      <MetricCard icon={MessageSquare} label="Completion Tokens" value={formatCompactNumber(summary?.completion_tokens ?? 0)} hint="completion_tokens" />
      <MetricCard icon={Download} label="估算费用" value={formatMoney(summary?.estimated_cost, summary?.currency)} hint={summary?.billing_policy_version ?? "billing policy"} />

      <section className="panel wide">
        <PanelTitle icon={Bot} title="按功能统计" />
        <div className="quick-actions">
          <button onClick={onRefresh}><RefreshCw size={16} />刷新用量</button>
        </div>
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

function LoadingBanner() {
  return (
    <div className="toast">
      <LoaderCircle className="spin" size={16} />
      <span>正在同步接口数据...</span>
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

function MetricCard({ icon: Icon, label, value, hint }: { icon: typeof Sparkles; label: string; value: number | string; hint: string }) {
  return (
    <section className="metric-card">
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </section>
  );
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

function pageTitle(view: View) {
  const titles: Record<View, string> = {
    dashboard: "学生首页 / 仪表盘",
    targets: "课程/考试目标管理",
    materials: "资料库管理",
    detail: "资料详情",
    graph: "知识图谱与掌握度",
    qa: "AI 问答页",
    practice: "AI 出题练习页",
    results: "自测结果页",
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

function formatMoney(value: number | string | null | undefined, currency = "USD") {
  const numeric = Number(value) || 0;
  return `${numeric.toFixed(4)} ${currency}`;
}

function formatAnswer(values: string[]) {
  return values.length ? values.join(", ") : "未作答";
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
