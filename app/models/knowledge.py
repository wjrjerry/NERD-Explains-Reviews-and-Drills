"""Database models for AI knowledge extraction results.

This file should store records generated from parsed materials, such as summary,
outline, keywords, key points, and exam points.

This model belongs to member B's AI learning flow, but it depends on member A's
material table through material_id. One material usually has zero or one latest
knowledge extraction result.
"""

# Suggested table: knowledge_results
# Suggested fields:
# - id: primary key
# - user_id: owner of this generated result
# - target_id: related course/exam target, nullable for early integration
# - material_id: source material ID
# - summary: generated material summary
# - outline: generated outline, can be JSON
# - keywords: generated keywords, can be JSON
# - key_points: generated key points, can be JSON
# - exam_points: generated likely exam points, can be JSON
# - created_at / updated_at: timestamps

# TODO: Define KnowledgeResult SQLAlchemy model.
# TODO: Add foreign key to materials.id after A's material model is stable.
# TODO: Decide whether outline/keywords/key_points/exam_points use JSON columns
#       or separate child tables. JSON is simpler for the first version.
