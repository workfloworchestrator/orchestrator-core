from http import HTTPStatus


def test_forms_endpoint(test_client):
    user_input = []
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.NOT_EXTENDED


def test_forms_endpoint_with_non_existing_form(test_client):
    user_input = []
    response = test_client.post("/api/forms/no_form", json=user_input)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Form no_form does not exist.", "title": "Not Found", "status": 404}
