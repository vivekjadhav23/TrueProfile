import os
import requests
import pytest
from unittest.mock import patch, Mock
from candidate_transformer.sources import GithubSource

def make_expected_github(full_name=None, emails=None, headline=None, github_url=None, location=None, skills=None):
    res = {
        "source_name": "github",
        "full_name": full_name,
        "emails": emails if emails else [],
        "phones": [],
        "headline": headline,
        "location": location,
        "linkedin_url": None,
        "github_url": github_url,
        "years_experience": None,
        "skills": skills if skills else [],
        "experience": [],
        "education": []
    }
    if github_url:
        res["links"] = {"github": github_url}
    return res

def test_github_source_success():
    """
    Test extraction when GitHub API responds successfully for user, repos, and languages.
    """
    with patch("requests.get") as mock_get:
        # Mock user details response
        user_resp = Mock()
        user_resp.status_code = 200
        user_resp.json.return_value = {
            "name": "Jane Developer",
            "email": "jane.dev@example.com",
            "bio": "Writing Python code all day.",
            "location": "Boston, MA"
        }

        # Mock repos response
        repos_resp = Mock()
        repos_resp.status_code = 200
        repos_resp.json.return_value = [
            {
                "name": "project-one",
                "languages_url": "https://api.github.com/repos/janedev/project-one/languages"
            },
            {
                "name": "project-two",
                "languages_url": "https://api.github.com/repos/janedev/project-two/languages"
            }
        ]

        # Mock languages responses
        lang1_resp = Mock()
        lang1_resp.status_code = 200
        lang1_resp.json.return_value = {"Python": 12000, "Docker": 300}

        lang2_resp = Mock()
        lang2_resp.status_code = 200
        lang2_resp.json.return_value = {"Go": 5000, "Docker": 1000}

        mock_get.side_effect = [user_resp, repos_resp, lang1_resp, lang2_resp]

        source = GithubSource()
        res = source.extract("https://github.com/janedev")

        assert res == make_expected_github(
            "Jane Developer", ["jane.dev@example.com"], "Writing Python code all day.",
            "https://github.com/janedev", "Boston, MA", ["Docker", "Go", "Python"]
        )

        # Verify calls
        assert mock_get.call_count == 4
        mock_get.assert_any_call("https://api.github.com/users/janedev", headers={"Accept": "application/vnd.github+json"}, timeout=10)
        mock_get.assert_any_call("https://api.github.com/users/janedev/repos?sort=updated&per_page=10", headers={"Accept": "application/vnd.github+json"}, timeout=10)

def test_github_source_user_not_found():
    """
    Test extraction when the user profile does not exist (404).
    """
    with patch("requests.get") as mock_get:
        user_resp = Mock()
        user_resp.status_code = 404
        mock_get.return_value = user_resp

        source = GithubSource()
        res = source.extract("notfound_user")

        assert res == make_expected_github()
        mock_get.assert_called_once()

def test_github_source_rate_limit():
    """
    Test extraction when the API returns a rate limit error (429).
    """
    with patch("requests.get") as mock_get:
        user_resp = Mock()
        user_resp.status_code = 429
        mock_get.return_value = user_resp

        source = GithubSource()
        res = source.extract("https://github.com/ratelimited")

        assert res == make_expected_github()
        mock_get.assert_called_once()

def test_github_source_network_error():
    """
    Test extraction when a network exception is raised.
    """
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("Connection error")

        source = GithubSource()
        res = source.extract("https://github.com/networkerror")

        assert res == make_expected_github()
        mock_get.assert_called_once()

def test_github_source_auth_header():
    """
    Test that GITHUB_TOKEN environment variable sets the Authorization header.
    """
    with patch.dict(os.environ, {"GITHUB_TOKEN": "secret_token_123"}):
        with patch("requests.get") as mock_get:
            user_resp = Mock()
            user_resp.status_code = 200
            user_resp.json.return_value = {"name": "Auth User"}
            
            repos_resp = Mock()
            repos_resp.status_code = 200
            repos_resp.json.return_value = []

            mock_get.side_effect = [user_resp, repos_resp]

            source = GithubSource()
            source.extract("authuser")

            # Check that the token was added to the request headers
            expected_headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer secret_token_123"
            }
            mock_get.assert_any_call("https://api.github.com/users/authuser", headers=expected_headers, timeout=10)
