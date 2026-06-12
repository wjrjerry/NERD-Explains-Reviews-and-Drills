"""Database access functions for knowledge extraction results.

Repository functions should contain SQLAlchemy queries only. They should not
decide business rules such as whether a material is parsed or whether AI should
be called. Those decisions belong in knowledge_service.
"""


def create_knowledge_result():
    """Insert or update one material's knowledge extraction result.

    Typical use:
    - knowledge_service receives AI output.
    - It calls this function to persist summary/outline/keywords/key_points.
    - If the same material is extracted again, update the existing row instead
      of creating duplicate knowledge records.
    """
    # TODO: Accept db session and knowledge fields.
    # TODO: Accept user_id, target_id, material_id, summary, outline, keywords,
    #       key_points, and exam_points.
    # TODO: Insert/update the KnowledgeResult row.
    # TODO: Return the saved row.
    pass


def get_knowledge_result_by_material_id():
    """Fetch the saved knowledge extraction result for one material.

    Typical use:
    - The frontend opens the material detail page.
    - The service first checks whether extraction has already been generated.
    - If a saved result exists, return it directly instead of calling AI again.
    """
    # TODO: Accept db session, user_id, and material_id.
    # TODO: Query by material_id and user ownership.
    # TODO: Return None if no extraction result exists.
    pass
