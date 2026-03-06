"""Integration tests for root redirect and health-check endpoints."""


def test_healthcheck_returns_ok(app_client):
    """GET /healthcheck should return 200 with a body of 'OK'."""
    response = app_client.get("/healthcheck")
    assert response.status_code == 200
    assert response.text == "OK"


def test_root_redirects_to_docs(app_client):
    """GET / should redirect to /docs."""
    response = app_client.get("/", follow_redirects=False)
    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["location"] == "/docs"


# def test_should_fail():
#     """This test should fail to confirm that the test suite is running correctly."""
#     assert False
