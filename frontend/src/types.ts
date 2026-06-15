export type Role = "student" | "admin";
export type TargetType = "course" | "exam";
export type MaterialType = "pdf" | "txt" | "image";
export type ParseStatus = "uploaded" | "parsing" | "parsed" | "failed";
export type QuestionType = "single_choice" | "multiple_choice" | "true_false" | "subjective";
export type Difficulty = "easy" | "medium" | "hard";
export type MasteryStatus = "unmastered" | "reviewing" | "mastered";

export interface User {
  id: number;
  username: string;
  display_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface StudyTarget {
  id: number;
  user_id?: number;
  title: string;
  subject?: string | null;
  target_type: TargetType;
  exam_date?: string | null;
  review_goal?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Material {
  id: number;
  user_id?: number;
  target_id: number;
  original_filename: string;
  stored_filename?: string;
  file_type: MaterialType;
  content_type: string | null;
  file_size: number;
  parse_status: ParseStatus;
  parse_error?: string | null;
  parse_warning?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialPreview {
  material: Material;
  preview_text: string | null;
  message?: string;
}

export interface KnowledgeResult {
  extraction_id?: number;
  scope?: "material" | "target";
  material_id?: number | null;
  target_id?: number | null;
  summary: string;
  outline: string[];
  keywords: string[];
  key_points: string[];
  exam_points: string[];
  knowledge_graph?: KnowledgeGraph | null;
}

export interface KnowledgePointReference {
  id: number;
  name: string;
  importance_weight: number;
}

export interface KnowledgeGraphNode {
  id: number;
  parent_id: number | null;
  name: string;
  description: string | null;
  importance_weight: number;
  level: number;
  sort_order: number;
  mastery_status: MasteryStatus;
  mastery_score: number;
  accuracy: number;
  answered_count: number;
  wrong_count: number;
  materials: Array<{
    material_id: number;
    evidence_text: string | null;
    relevance_score: number;
  }>;
}

export interface KnowledgeGraph {
  target_id: number;
  nodes: KnowledgeGraphNode[];
  generated_at: string | null;
}

export interface MaterialSection {
  id: number;
  material_id: number;
  parent_id: number | null;
  title: string;
  level: number;
  order_index: number;
  source_page: number | null;
}

export interface MaterialChunk {
  id: number;
  material_id: number;
  section_id: number | null;
  chunk_type: string;
  title: string | null;
  text: string;
  order_index: number;
  source_page: number | null;
}

export interface MaterialStructured {
  material_id: number;
  sections: MaterialSection[];
  chunks: MaterialChunk[];
  figures?: Array<{
    id: number;
    material_id: number;
    section_id: number | null;
    title: string | null;
    description: string;
    order_index: number;
    source_page: number | null;
  }>;
  tables?: Array<{
    id: number;
    material_id: number;
    section_id: number | null;
    title: string | null;
    content: string;
    order_index: number;
    source_page: number | null;
  }>;
  formulas?: Array<{
    id: number;
    material_id: number;
    section_id: number | null;
    expression: string;
    explanation: string | null;
    order_index: number;
    source_page: number | null;
  }>;
}

export interface QaReference {
  material_id: number;
  snippet: string;
}

export interface QaRecord {
  qa_record_id: number;
  material_id?: number;
  target_id?: number | null;
  question: string;
  answer: string;
  references: QaReference[];
  knowledge_points?: KnowledgePointReference[];
  ai_provider?: string;
  ai_model?: string;
  created_at: string;
}

export interface QuestionOption {
  key: string;
  text: string;
  analysis: string;
}

export interface Question {
  id: number;
  type: QuestionType;
  stem: string;
  options: QuestionOption[];
  correct_answer: string[];
  analysis: string;
  knowledge_points: string[];
  knowledge_point_ids: number[];
  difficulty: Difficulty;
}

export interface TestSubmitAnswer {
  question_id: number;
  answer?: string[];
  answer_text?: string | null;
  answer_file_ids?: number[];
  answer_file_urls?: string[];
}

export interface TestResultItem {
  question_id: number;
  knowledge_point_ids: number[];
  user_answer: string[];
  correct_answer: string[];
  is_correct: boolean;
  score: number;
  analysis: string;
  matched_points: string[];
  missing_points: string[];
  misconceptions: string[];
}

export interface TestResult {
  test_record_id: number;
  score: number;
  accuracy: number;
  total_count: number;
  correct_count: number;
  wrong_count: number;
  results: TestResultItem[];
  knowledge_point_summary?: Array<{
    knowledge_point_id: number;
    total_count: number;
    correct_count: number;
    wrong_count: number;
    accuracy: number;
    average_score: number;
  }>;
}

export interface TestRecord {
  id: number;
  user_id: number;
  material_id: number;
  target_id: number | null;
  score: number;
  accuracy: number;
  total_count: number;
  correct_count: number;
  wrong_count: number;
  created_at: string;
}

export interface WrongQuestion {
  id: number;
  question_id: number;
  target_id: number | null;
  material_id: number;
  stem: string;
  user_answer: string[];
  correct_answer: string[];
  analysis: string;
  wrong_reason: string;
  knowledge_points: string[];
  knowledge_point_ids: number[];
  mastery_status: MasteryStatus;
}

export interface ReviewPlanTask {
  id: number;
  date: string;
  title: string;
  content: string;
  material_id: number | null;
  knowledge_point_id?: number | null;
  wrong_question_id: number | null;
  completed: boolean;
}

export interface ReviewPlan {
  id: number;
  target_id: number;
  title: string;
  start_date: string;
  end_date: string;
  summary: string;
  tasks: ReviewPlanTask[];
}

export interface HealthStatus {
  status: string;
}

export interface KnowledgePointMaterialItem {
  material_id: number;
  target_id: number;
  original_filename: string;
  file_type: string;
  parse_status: string;
  evidence_text: string | null;
  relevance_score: number;
}

export interface KnowledgePointMaterials {
  knowledge_point_id: number;
  items: KnowledgePointMaterialItem[];
}

export interface KnowledgePointMastery {
  knowledge_point_id: number;
  target_id: number;
  mastery_status: MasteryStatus;
  mastery_score: number;
  accuracy: number;
  answered_count: number;
  wrong_count: number;
  last_practiced_at: string | null;
  next_review_at: string | null;
}

export interface AiUsageFeatureSummary {
  feature: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number | string;
  currency: string;
}

export interface AiUsageSummary {
  total_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number | string;
  currency: string;
  billing_policy_version: string;
  by_feature: AiUsageFeatureSummary[];
}

export interface AiUsageLogItem {
  id: number;
  target_id: number | null;
  material_id: number | null;
  feature: string;
  provider: string;
  model: string | null;
  status: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  prompt_cache_hit_tokens: number | null;
  prompt_cache_miss_tokens: number | null;
  reasoning_tokens: number | null;
  estimated_cost: number | string;
  currency: string;
  billing_policy_version: string;
  latency_ms: number;
  created_at: string;
  error_message: string | null;
}
