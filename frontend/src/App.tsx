import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  Brain,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Download,
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
  TableOfContents,
  Trash2,
  Upload,
  UserCircle,
  XCircle
} from "lucide-react";
import { api, clearToken, getToken } from "./api";
import type {
  Difficulty,
  HealthStatus,
  KnowledgeGraph,
  KnowledgeResult,
  Material,
  MaterialPreview,
  MaterialStructured,
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
  | "admin";

type NoticeTone = "info" | "success" | "danger";

type Notice = {
  tone: NoticeTone;
  text: string;
};

const navItems: Array<{ view: View; label: string; icon: typeof LayoutDashboard }> = [
  { view: "dashboard", label: "仪表盘", icon: LayoutDashboard },
  { view: "targets", label: "目标管理", icon: BookOpen },
  { view: "materials", label: "资料库", icon: FileText },
  { view: "detail", label: "资料详情", icon: Brain },
  { view: "graph", label: "知识图谱", icon: Network },
  { view: "qa", label: "AI 问答", icon: MessageSquare },
  { view: "practice", label: "AI 出题", icon: ClipboardCheck },
  { view: "results", label: "测试结果", icon: CheckCircle2 },
  { view: "wrong", label: "错题本", icon: AlertTriangle },
  { view: "plans", label: "复习计划", icon: CalendarDays },
  { view: "admin", label: "管理员端", icon: Shield }
];

const parseStatusText: Record<Material["parse_status"], string> = {
  uploaded: "等待解析",
  parsing: "解析中",
  parsed: "可学习",
  failed: "解析失败"
};

const questionTypeOptions: Array<{ value: QuestionType; label: string }> = [
  { value: "single_choice", label: "单选题" },
  { value: "multiple_choice", label: "多选题" },
  { value: "true_false", label: "判断题" },
  { value: "subjective", label: "主观题" }
];

function App() {
  const [view, setView] = useState<View>("dashboard");
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
  const [health, setHealth] = useState<{ api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus }>({});
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const selectedTarget = useMemo(
    () => targets.find((item) => item.id === selectedTargetId) ?? null,
    [selectedTargetId, targets]
  );
  const selectedMaterial = useMemo(
    () => materials.find((item) => item.id === selectedMaterialId) ?? null,
    [materials, selectedMaterialId]
  );

  const parsedCount = materials.filter((item) => item.parse_status === "parsed").length;
  const failedCount = materials.filter((item) => item.parse_status === "failed").length;
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
      return;
    }

    setKnowledge(null);
    setStructured(null);
    void loadMaterialContext(selectedMaterialId);
  }, [selectedMaterialId, user]);

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

  async function initializeSession() {
    setLoading(true);
    try {
      const me = await api.me();
      setUser(me.user);
      await Promise.all([loadDashboardData(), loadAdminHealth()]);
      setNotice({ tone: "success", text: "已使用本地 token 初始化会话。" });
    } catch (error) {
      clearToken();
      setUser(null);
      setNotice({ tone: "danger", text: `登录状态无效：${readMessage(error)}` });
    } finally {
      setLoading(false);
    }
  }

  async function loadDashboardData() {
    const [targetData, materialData, wrongData, planData] = await Promise.all([
      api.listTargets(),
      api.listMaterials(),
      api.listWrongQuestions().catch(() => ({ items: [], total: 0, page: 1, page_size: 10 })),
      api.listReviewPlans().catch(() => ({ items: [], total: 0, page: 1, page_size: 20 }))
    ]);

    setTargets(targetData.items);
    setMaterials(materialData.items);
    setWrongQuestions(wrongData.items);
    setReviewPlans(planData.items);

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

  async function loadAdminHealth() {
    const [apiStatus, dbStatus, redisStatus] = await Promise.allSettled([api.health(), api.healthDb(), api.healthRedis()]);
    setHealth({
      api: apiStatus.status === "fulfilled" ? apiStatus.value : { status: "error" },
      db: dbStatus.status === "fulfilled" ? dbStatus.value : { status: "error" },
      redis: redisStatus.status === "fulfilled" ? redisStatus.value : { status: "error" }
    });
  }

  async function loadMaterialContext(materialId: number) {
    try {
      const [detailData, previewData, structuredData, qaHistoryData] = await Promise.all([
        api.getMaterial(materialId),
        api.getMaterialPreview(materialId).catch(() => null),
        api.getMaterialStructured(materialId).catch(() => null),
        api.listQaHistory(1, 10, materialId).catch(() => ({ items: [], total: 0, page: 1, page_size: 10 }))
      ]);

      setMaterials((current) => current.map((item) => (item.id === materialId ? detailData.material : item)));
      if (previewData) {
        setPreview(previewData);
      }
      setStructured(structuredData);
      setQaRecords(qaHistoryData.items);
    } catch (error) {
      setPreview(null);
      setStructured(null);
      setQaRecords([]);
      setNotice({ tone: "danger", text: `资料上下文加载失败：${readMessage(error)}` });
    }
  }

  async function handleLogin(formData: FormData) {
    const username = String(formData.get("username") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    if (!username || !password) {
      setNotice({ tone: "danger", text: "请输入用户名和密码。" });
      return;
    }

    setLoading(true);
    try {
      const nextUser = await api.login(username, password);
      setUser(nextUser);
      await Promise.all([loadDashboardData(), loadAdminHealth()]);
      setNotice({ tone: "success", text: "登录成功，已同步后端数据。" });
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
      await Promise.all([loadDashboardData(), loadAdminHealth()]);
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
    const targetId = Number(formData.get("target_id"));
    if (!(file instanceof File) || !targetId) {
      setNotice({ tone: "danger", text: "请先选择目标和资料文件。" });
      return;
    }

    try {
      const data = await api.uploadMaterial(targetId, file);
      setMaterials((current) => [data.material, ...current]);
      setSelectedMaterialId(data.material.id);
      setSelectedTargetId(data.material.target_id);
      setNotice({ tone: "success", text: "资料上传成功，请先解析资料再使用 AI 学习功能。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `资料上传失败：${readMessage(error)}` });
    }
  }

  async function handleDeleteMaterial(materialId: number) {
    try {
      await api.deleteMaterial(materialId);
      const nextMaterials = materials.filter((item) => item.id !== materialId);
      setMaterials(nextMaterials);
      if (selectedMaterialId === materialId) {
        setSelectedMaterialId(nextMaterials[0]?.id ?? null);
      }
      setNotice({ tone: "info", text: "资料已删除。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `资料删除失败：${readMessage(error)}` });
    }
  }

  async function handleParseMaterial(materialId: number) {
    setMaterials((current) =>
      current.map((item) => (item.id === materialId ? { ...item, parse_status: "parsing", parse_error: null } : item))
    );

    try {
      const data = await api.parseMaterial(materialId);
      setMaterials((current) => current.map((item) => (item.id === materialId ? data.material : item)));
      if (selectedMaterialId === materialId) {
        const previewData = await api.getMaterialPreview(materialId).catch(() => null);
        setPreview(previewData);
      }
      if (data.material.parse_status === "parsed") {
        setNotice({ tone: "success", text: "资料解析完成，AI 学习功能已启用。" });
      } else if (data.material.parse_status === "failed") {
        setNotice({ tone: "danger", text: data.material.parse_error ?? "资料解析失败。" });
      } else {
        setNotice({ tone: "info", text: `资料状态已更新为 ${parseStatusText[data.material.parse_status]}。` });
      }
    } catch (error) {
      await loadDashboardData().catch(() => undefined);
      setNotice({ tone: "danger", text: `资料解析失败：${readMessage(error)}` });
    }
  }

  async function handleExtractKnowledge() {
    if (!selectedMaterial) {
      return;
    }
    try {
      const data = await api.extractKnowledge(selectedMaterial.id);
      setKnowledge(data);
      setNotice({ tone: "success", text: "知识提炼完成。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `知识提炼失败：${readMessage(error)}` });
    }
  }

  async function handleAskQuestion(formData: FormData) {
    if (!selectedMaterial) {
      return;
    }
    const question = String(formData.get("question") ?? "").trim();
    if (!question) {
      return;
    }
    try {
      const data = await api.askQuestion(selectedMaterial.id, question);
      setQaRecords((current) => [data, ...current]);
      setNotice({ tone: "success", text: "问答已生成并写入历史。" });
    } catch (error) {
      setNotice({ tone: "danger", text: `问答失败：${readMessage(error)}` });
    }
  }

  async function handleGenerateQuestions(formData: FormData) {
    if (!selectedMaterial) {
      return;
    }
    try {
      const difficulty = String(formData.get("difficulty") ?? "medium") as Difficulty;
      const count = Number(formData.get("count") ?? 5);
      const questionTypes = formData.getAll("question_types").map(String) as QuestionType[];
      if (!questionTypes.length) {
        setNotice({ tone: "danger", text: "请至少选择一种题型。" });
        return;
      }
      const data = await api.generateQuestions(selectedMaterial.id, count, difficulty, questionTypes);
      setQuestions(data.questions);
      setView("practice");
      setNotice({ tone: "success", text: "题目已生成。" });
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

  async function handleExport(action: () => Promise<void>, successText: string) {
    try {
      await action();
      setNotice({ tone: "success", text: successText });
    } catch (error) {
      setNotice({ tone: "danger", text: `导出失败：${readMessage(error)}` });
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
    setSelectedTargetId(null);
    setSelectedMaterialId(null);
    setNotice({ tone: "info", text: "已退出登录。" });
  }

  if (!user) {
    return (
      <>
        <AuthPage loading={loading} notice={notice} onLogin={handleLogin} onRegister={handleRegister} onCloseNotice={() => setNotice(null)} />
      </>
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
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.view} className={view === item.view ? "active" : ""} onClick={() => setView(item.view)}>
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
            <p className="eyebrow">已连接后端接口</p>
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
            materials={materials}
            selectedMaterialId={selectedMaterialId}
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
            structured={structured}
            knowledge={knowledge}
            onParse={() => {
              if (selectedMaterial) {
                void handleParseMaterial(selectedMaterial.id);
              }
            }}
            onExtract={handleExtractKnowledge}
            onGenerateGraph={handleGenerateKnowledgeGraph}
            onExportKnowledge={() => {
              if (selectedTargetId) {
                void handleExport(() => api.exportKnowledgeSummary(selectedTargetId), "知识总结已开始下载。");
              }
            }}
            onJumpToQa={() => setView("qa")}
            onJumpToPractice={() => setView("practice")}
          />
        ) : null}

        {view === "graph" ? (
          <KnowledgeGraphPage
            target={selectedTarget}
            graph={knowledgeGraph}
            wrongQuestions={wrongQuestions}
            onGenerate={handleGenerateKnowledgeGraph}
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

        {view === "qa" ? <QaPage material={selectedMaterial} records={qaRecords} onAsk={handleAskQuestion} /> : null}

        {view === "practice" ? (
          <PracticePage material={selectedMaterial} questions={questions} onGenerate={handleGenerateQuestions} onSubmit={handleSubmitTest} />
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

        {view === "admin" ? <AdminPage health={health} materials={materials} /> : null}
      </main>
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
          <h1>{mode === "login" ? "登录" : "注册"}</h1>
        </div>

        {notice ? <NoticeBar notice={notice} onClose={onCloseNotice} /> : null}
        {loading ? <LoadingBanner /> : null}

        <input name="username" placeholder="用户名" minLength={3} required />
        <input name="password" type="password" placeholder="密码" minLength={6} required />
        {mode === "register" ? <input name="display_name" placeholder="昵称（可选）" /> : null}

        <button className="primary-button" type="submit" disabled={loading}>
          <UserCircle size={16} />
          {mode === "login" ? "登录并同步数据" : "注册并登录"}
        </button>
        <button className="ghost-button" type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
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
  selectedMaterialId,
  onSelect,
  onUpload,
  onParse,
  onDelete
}: {
  targets: StudyTarget[];
  materials: Material[];
  selectedMaterialId: number | null;
  onSelect: (material: Material) => void;
  onUpload: (formData: FormData) => void;
  onParse: (materialId: number) => void;
  onDelete: (materialId: number) => void;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  return (
    <div className="two-column">
      <form
        className="panel form-panel"
        onSubmit={(event) => {
          submitForm(event, onUpload);
          setSelectedFile(null);
        }}
      >
        <PanelTitle icon={Upload} title="上传资料" action="POST /materials" />
        <select name="target_id" defaultValue={targets[0]?.id}>
          {targets.map((target) => <option key={target.id} value={target.id}>{target.title}</option>)}
        </select>
        <label className="drop-zone">
          <Upload size={28} />
          <span>选择 PDF / TXT / 图片资料</span>
          <small>上传后需要调用解析接口，解析成功后才能使用 AI 功能</small>
          <input
            name="file"
            type="file"
            accept=".pdf,.txt,image/*"
            required
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
        <button className="primary-button" type="submit"><Upload size={16} />上传并入库</button>
      </form>

      <section className="panel">
        <PanelTitle icon={FileText} title="资料列表" />
        <div className="list">
          {materials.map((material) => (
            <div key={material.id} className={`list-item ${selectedMaterialId === material.id ? "selected-row" : ""}`}>
              <button className="material-row material-row-inline" onClick={() => onSelect(material)}>
                <div>
                  <strong>{material.original_filename}</strong>
                  <span>{formatBytes(material.file_size)} · {material.file_type.toUpperCase()}</span>
                </div>
              </button>
              <StatusBadge status={material.parse_status} />
              <button
                className="ghost-button compact-button"
                disabled={material.parse_status === "parsing"}
                onClick={() => onParse(material.id)}
              >
                <RefreshCw size={16} />
                {material.parse_status === "parsed" ? "重解析" : "解析"}
              </button>
              <button className="icon-button" title="删除资料" onClick={() => onDelete(material.id)}>
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MaterialDetailPage({
  material,
  target,
  preview,
  structured,
  knowledge,
  onParse,
  onExtract,
  onGenerateGraph,
  onExportKnowledge,
  onJumpToQa,
  onJumpToPractice
}: {
  material: Material | null;
  target: StudyTarget | null;
  preview: MaterialPreview | null;
  structured: MaterialStructured | null;
  knowledge: KnowledgeResult | null;
  onParse: () => void;
  onExtract: () => void;
  onGenerateGraph: () => void;
  onExportKnowledge: () => void;
  onJumpToQa: () => void;
  onJumpToPractice: () => void;
}) {
  if (!material) return <EmptyPanel text="请先在资料库中选择一份资料。" />;

  const aiDisabled = material.parse_status !== "parsed";

  return (
    <div className="grid learn-grid">
      <section className="panel wide">
        <PanelTitle icon={Brain} title="资料详情与 AI 学习" />
        <div className="detail-header">
          <div>
            <h2>{material.original_filename}</h2>
            <p>所属目标：{target?.title ?? "未匹配"} · 状态：{parseStatusText[material.parse_status]}</p>
            {material.parse_error ? <p className="danger-text">{material.parse_error}</p> : null}
          </div>
          <div className="quick-actions">
            <button disabled={material.parse_status === "parsing"} onClick={onParse}><RefreshCw size={16} />解析资料</button>
            <button disabled={aiDisabled} onClick={onExtract}><Sparkles size={16} />知识提炼</button>
            <button disabled={aiDisabled} onClick={onGenerateGraph}><Network size={16} />生成图谱</button>
            <button disabled={!target} onClick={onExportKnowledge}><Download size={16} />导出总结</button>
            <button disabled={aiDisabled} onClick={onJumpToQa}><MessageSquare size={16} />AI 问答</button>
            <button disabled={aiDisabled} onClick={onJumpToPractice}><ClipboardCheck size={16} />AI 出题</button>
          </div>
        </div>
      </section>

      <section className="panel">
        <PanelTitle icon={FileText} title="资料预览" />
        <p className="preview-box">{preview?.preview_text || "当前资料暂无文本预览。"}</p>
      </section>

      <section className="panel">
        <PanelTitle icon={TableOfContents} title="结构化章节" />
        {structured?.sections.length || structured?.chunks.length ? (
          <StructuredReader structured={structured} />
        ) : (
          <p className="muted-text">暂无章节结构，解析完成后可查看 sections 与 chunks。</p>
        )}
      </section>

      <section className="panel">
        <PanelTitle icon={Bot} title="知识提炼结果" />
        {knowledge ? (
          <div className="detail-stack">
            <p>{knowledge.summary}</p>
            <InfoList title="提纲" items={knowledge.outline} />
            <InfoList title="关键词" items={knowledge.keywords} />
            <InfoList title="重点" items={knowledge.key_points} />
            <InfoList title="考点" items={knowledge.exam_points} />
          </div>
        ) : (
          <p className="muted-text">还没有知识提炼结果。</p>
        )}
      </section>
    </div>
  );
}

function StructuredReader({ structured }: { structured: MaterialStructured }) {
  const [activeSectionId, setActiveSectionId] = useState<number | null>(structured.sections[0]?.id ?? null);
  const visibleChunks = structured.chunks.filter((chunk) => !activeSectionId || chunk.section_id === activeSectionId).slice(0, 12);

  useEffect(() => {
    setActiveSectionId(structured.sections[0]?.id ?? null);
  }, [structured.material_id]);

  return (
    <div className="reader-layout">
      <div className="section-nav">
        {structured.sections.length ? structured.sections.map((section) => (
          <button
            key={section.id}
            className={activeSectionId === section.id ? "active-pill" : ""}
            style={{ paddingLeft: `${10 + section.level * 12}px` }}
            onClick={() => setActiveSectionId(section.id)}
          >
            {section.title}
          </button>
        )) : <p className="muted-text">未识别出章节。</p>}
      </div>
      <div className="chunk-list">
        {visibleChunks.length ? visibleChunks.map((chunk) => (
          <article key={chunk.id} className="chunk-card">
            <strong>{chunk.title || `文本块 ${chunk.order_index + 1}`}</strong>
            <span>{chunk.chunk_type}{chunk.source_page ? ` · 第 ${chunk.source_page} 页` : ""}</span>
            <p>{chunk.text}</p>
          </article>
        )) : <p className="muted-text">当前章节暂无文本块。</p>}
      </div>
    </div>
  );
}

function KnowledgeGraphPage({
  target,
  graph,
  wrongQuestions,
  onGenerate,
  onExport,
  onExportAnki
}: {
  target: StudyTarget | null;
  graph: KnowledgeGraph | null;
  wrongQuestions: WrongQuestion[];
  onGenerate: () => void;
  onExport: () => void;
  onExportAnki: () => void;
}) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const activeNode = graph?.nodes.find((node) => node.id === activeId) ?? graph?.nodes[0] ?? null;
  const relatedWrong = activeNode
    ? wrongQuestions.filter((item) => item.knowledge_points.some((point) => activeNode.name.includes(point) || point.includes(activeNode.name)))
    : [];

  useEffect(() => {
    setActiveId(graph?.nodes[0]?.id ?? null);
  }, [graph?.target_id, graph?.nodes.length]);

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
            <InfoList title="关联错题" items={relatedWrong.map((item) => item.stem)} />
          </div>
        ) : (
          <p className="muted-text">请选择一个知识点。</p>
        )}
      </section>
    </div>
  );
}

function QaPage({ material, records, onAsk }: { material: Material | null; records: QaRecord[]; onAsk: (formData: FormData) => void }) {
  if (!material) return <EmptyPanel text="请先选择一份资料，再进入 AI 问答页面。" />;

  return (
    <div className="two-column qa-layout">
      <form className="panel form-panel" onSubmit={(event) => submitForm(event, onAsk)}>
        <PanelTitle icon={MessageSquare} title="提问" />
        <p className="muted-text">当前资料：{material.original_filename}</p>
        <textarea name="question" placeholder="围绕当前资料提出问题" required />
        <button className="primary-button" type="submit" disabled={material.parse_status !== "parsed"}>
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
              {record.references.length ? <blockquote>{record.references[0].snippet}</blockquote> : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PracticePage({
  material,
  questions,
  onGenerate,
  onSubmit
}: {
  material: Material | null;
  questions: Question[];
  onGenerate: (formData: FormData) => void;
  onSubmit: (answers: TestSubmitAnswer[]) => void;
}) {
  const [objectiveAnswers, setObjectiveAnswers] = useState<Record<number, string[]>>({});
  const [subjectiveAnswers, setSubjectiveAnswers] = useState<Record<number, string>>({});

  useEffect(() => {
    setObjectiveAnswers({});
    setSubjectiveAnswers({});
  }, [questions]);

  if (!material) return <EmptyPanel text="请先选择资料，再进入 AI 出题页面。" />;

  const submitAnswers = questions.map((question) =>
    question.type === "subjective"
      ? { question_id: question.id, answer_text: subjectiveAnswers[question.id]?.trim() ?? "" }
      : { question_id: question.id, answer: objectiveAnswers[question.id] ?? [] }
  );

  return (
    <div className="practice-layout">
      <form className="panel practice-toolbar" onSubmit={(event) => submitForm(event, onGenerate)}>
        <PanelTitle icon={ClipboardCheck} title="生成练习题" />
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
          <input name="count" type="number" min="1" max="10" defaultValue="5" />
        </div>
        <div className="toolbar-actions">
          <button className="primary-button" type="submit" disabled={material.parse_status !== "parsed"}>
            <Sparkles size={16} />生成题目
          </button>
          <button className="ghost-button" type="button" disabled={!questions.length} onClick={() => onSubmit(submitAnswers)}>
            提交自测
          </button>
        </div>
      </form>

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
        <div className="list">
          {result.results.map((item) => {
            const question = questions.find((entry) => entry.id === item.question_id);
            return (
              <article className="list-item vertical" key={item.question_id}>
                <strong>{question?.stem ?? `题目 ${item.question_id}`}</strong>
                <span>
                  你的答案：{formatAnswer(item.user_answer)} · 正确答案：{formatAnswer(item.correct_answer)} · 单题得分：{item.score}
                </span>
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

function AdminPage({
  health,
  materials
}: {
  health: { api?: HealthStatus; db?: HealthStatus; redis?: HealthStatus };
  materials: Material[];
}) {
  return (
    <div className="grid admin-grid">
      <MetricCard icon={Shield} label="API 健康" value={health.api?.status ?? "error"} hint="GET /health" />
      <MetricCard icon={Shield} label="数据库健康" value={health.db?.status ?? "error"} hint="GET /health/db" />
      <MetricCard icon={Shield} label="Redis 健康" value={health.redis?.status ?? "error"} hint="GET /health/redis" />
      <MetricCard icon={FileText} label="资料总数" value={materials.length} hint="接口巡检" />

      <section className="panel wide">
        <PanelTitle icon={AlertTriangle} title="资料解析巡检" />
        <div className="admin-table">
          {materials.map((material) => (
            <div key={material.id}>
              <span>{material.original_filename}</span>
              <span>{material.file_type}</span>
              <StatusBadge status={material.parse_status} />
              <span>{material.parse_error || "无异常"}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function NoticeBar({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  return (
    <div className={`toast ${notice.tone}`}>
      {notice.tone === "danger" ? <XCircle size={16} /> : notice.tone === "success" ? <CheckCircle2 size={16} /> : <Sparkles size={16} />}
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
      <ul className="clean-list">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
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
    detail: "资料详情与 AI 学习",
    graph: "知识图谱与掌握度",
    qa: "AI 问答页",
    practice: "AI 出题练习页",
    results: "自测结果页",
    wrong: "错题本页",
    plans: "复习计划页",
    admin: "管理员端"
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
