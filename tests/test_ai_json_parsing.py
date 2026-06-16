from app.services.ai_service import _extract_json_object


def test_extract_json_object_repairs_common_llm_missing_commas():
    payload = """
    ```json
    {
      "points": [
        {
          "name": "A",
          "description": "alpha",
          "evidence": []
        }
        {
          "name": "B",
          "description": "beta",
          "evidence": []
        }
      ]
      "merges": [],
    }
    ```
    """

    data = _extract_json_object(payload)

    assert [item["name"] for item in data["points"]] == ["A", "B"]
    assert data["merges"] == []
