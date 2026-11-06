def test_index_is_served_at_root(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="board"' in response.text
    assert "/static/app.js" in response.text


def test_static_css_is_served(client) -> None:
    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".board" in response.text


def test_static_js_is_served(client) -> None:
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "/game/" in response.text


def test_unknown_static_file_returns_404(client) -> None:
    response = client.get("/static/missing.js")

    assert response.status_code == 404
