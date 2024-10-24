from rapyuta_io_sdk_v2.client import Client


# Test case for a successful token retrieval
def test_get_token_success(mocker):
    email = "test@example.com"
    password = "password123"

    # Mocking the httpx.post response
    mock_post = mocker.patch("httpx.post")

    # Setup a mocked response with a token
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "success": True,
        "data": {"token": "mocked_token"},
    }
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Call the function under test
    test_client = Client()
    token = test_client.get_token(email, password, "pr_mock_test")
    # config_instance.hosts = {"rip_host": "http://mocked-rip-host.com"}

    # Assertions
    mock_post.assert_called_once_with(
        url="https://pr_mock_testrip.apps.okd4v2.okd4beta.rapyuta.io/user/login",
        headers={"Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=10,
    )
    assert token == "mocked_token"
    # mock_handle_server_errors.assert_called_once_with(mock_response)


# Test case for handling a server error (e.g., 400 status code)
def test_get_token_server_error(mocker):
    email = "test@example.com"
    password = "password123"

    # Mocking the Configuration class
    mock_config = mocker.patch("rapyuta_io_sdk_v2.Configuration")
    config_instance = mock_config.return_value
    config_instance.hosts = {"rip_host": "http://mocked-rip-host.com"}

    # Mocking the handle_server_errors function
    # mock_handle_server_errors = mocker.patch(
    #     "rapyuta_io_sdk_v2.utils.handle_server_errors"
    # )

    # Mocking the httpx.post response
    mock_post = mocker.patch("httpx.post")
    mock_post.return_value.status_code = 400
    mock_post.json.return_value = {"error": "mocked_error"}

    # Setup a mocked response with an error status code
    mock_response = mocker.Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "mocked_error"}
    mock_post.return_value = mock_response

    mock_post.assert_called_once_with(
        url="https://mock_testrip.apps.okd4v2.okd4beta.rapyuta.io/user/login",
        headers={"Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=10,
    )
