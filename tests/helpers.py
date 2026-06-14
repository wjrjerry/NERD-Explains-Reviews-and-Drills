def assert_api_response(body: dict) -> None:
    assert "code" in body
    assert "message" in body
    assert "data" in body


def assert_page_result(data: dict) -> None:
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


def assert_success_response(body: dict) -> None:
    assert_api_response(body)
    assert body["code"] == 0
    assert body["message"] == "success"
