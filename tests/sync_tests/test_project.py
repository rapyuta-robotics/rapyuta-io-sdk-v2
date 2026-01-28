import httpx
import pytest
from pytest_mock import MockFixture

# ruff: noqa: F811, F401
from rapyuta_io_sdk_v2.models import Project, ProjectList
from tests.data import project_body, project_model_mock, projectlist_model_mock
from tests.utils.fixtures import client


# Test function for list_projects
def test_list_projects_success(client, projectlist_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up mock responses for pagination
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=projectlist_model_mock,
    )

    # Call the list_projects method
    response = client.list_projects()

    # Validate the response
    assert isinstance(response, ProjectList)
    assert response.metadata.continue_ == 1
    assert len(response.items) == 1
    project = response.items[0]
    assert project.metadata.guid == "mock_project_guid"
    assert project.metadata.name == "test-project"
    assert project.kind == "Project"


def test_list_projects_unauthorized(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Call the list_projects method
    with pytest.raises(Exception) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_list_projects_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "not found"},
    )

    # Call the list_projects method
    with pytest.raises(Exception) as exc:
        client.list_projects()

    # Validate the exception message
    assert str(exc.value) == "not found"


def test_get_project_success(client, project_model_mock, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    # Call the get_project method
    response = client.get_project(project_guid="mock_project_guid")

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_get_project_not_found(client, mocker: MockFixture):
    # Mock the httpx.Client.get method
    mock_get = mocker.patch("httpx.Client.get")

    # Set up the mock response
    mock_get.return_value = httpx.Response(
        status_code=404,
        json={"error": "project not found"},
    )

    # Call the get_project method
    with pytest.raises(Exception) as exc:
        client.get_project(project_guid="mock_project_guid")

    # Validate the exception message
    assert str(exc.value) == "project not found"


def test_create_project_success(
    client, project_body, project_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=201,
        json=project_model_mock,
    )

    # Call the create_project method
    response = client.create_project(body=project_body)

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_create_project_unauthorized(client, project_body, mocker: MockFixture):
    # Mock the httpx.Client.post method
    mock_post = mocker.patch("httpx.Client.post")

    # Set up the mock response
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"error": "unauthorized permission access"},
    )

    # Call the create_project method
    with pytest.raises(Exception) as exc:
        client.create_project(body=project_body)

    # Validate the exception message
    assert str(exc.value) == "unauthorized permission access"


def test_update_project_success(
    client, project_body, project_model_mock, mocker: MockFixture
):
    # Mock the httpx.Client.put method
    mock_put = mocker.patch("httpx.Client.put")

    # Set up the mock response
    mock_put.return_value = httpx.Response(
        status_code=200,
        json=project_model_mock,
    )

    # Call the update_project method
    response = client.update_project(project_guid="mock_project_guid", body=project_body)

    # Validate the response
    assert isinstance(response, Project)
    assert response.metadata.guid == "mock_project_guid"
    assert response.metadata.name == "test-project"


def test_delete_project_success(client, mocker: MockFixture):
    # Mock the httpx.Client.delete method
    mock_delete = mocker.patch("httpx.Client.delete")

    # Set up the mock response
    mock_delete.return_value = httpx.Response(status_code=200, json={"success": True})

    # Call the delete_project method
    response = client.delete_project(project_guid="mock_project_guid")

    # Validate the response
    assert response is None
