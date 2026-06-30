import os
import re
import logging
import requests
from .base import BaseSource

logger = logging.getLogger(__name__)

class GitHubSource(BaseSource):
    """
    Source reader for candidate GitHub profiles via the GitHub REST API.
    """

    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract candidate details from a GitHub username or profile URL.

        Calls the GitHub REST API to get user profile details, top repos,
        and languages used in those repos to populate skills.
        """
        def empty_result():
            return {
                "source_name": "github",
                "full_name": None,
                "emails": [],
                "phones": [],
                "headline": None,
                "location": None,
                "linkedin_url": None,
                "github_url": None,
                "years_experience": None,
                "skills": [],
                "experience": [],
                "education": []
            }

        if not input_path_or_url:
            logger.warning("Empty input URL or username provided to GitHubSource.")
            return empty_result()

        # 1. Extract username from URL using regex
        username = input_path_or_url.strip().rstrip('/')
        match = re.search(r'(?:https?://)?(?:www\.)?github\.com/([^/]+)', username)
        if match:
            username = match.group(1)

        token = os.environ.get("GITHUB_TOKEN")
        headers = {
            "Accept": "application/vnd.github+json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # 2. Call GitHub REST API: GET https://api.github.com/users/{username}
        user_url = f"https://api.github.com/users/{username}"
        try:
            user_resp = requests.get(user_url, headers=headers, timeout=10)
            if user_resp.status_code == 404:
                logger.warning(f"GitHub user {username} not found (404)")
                return empty_result()
            elif user_resp.status_code == 429:
                logger.warning(f"Rate limit exceeded (429) for GitHub user {username}")
                return empty_result()
            user_resp.raise_for_status()
            user_data = user_resp.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch GitHub user {username}: {e}")
            logger.error(f"Network or HTTP error fetching user {username}: {e}", exc_info=True)
            return empty_result()

        # 3. Call GET https://api.github.com/users/{username}/repos?sort=updated&per_page=10
        repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10"
        languages_set = set()
        try:
            repos_resp = requests.get(repos_url, headers=headers, timeout=10)
            if repos_resp.status_code == 429:
                logger.warning(f"Rate limit exceeded (429) fetching repos for GitHub user {username}")
                return empty_result()
            elif repos_resp.status_code == 404:
                repos_data = []
            else:
                repos_resp.raise_for_status()
                repos_data = repos_resp.json()
                if not isinstance(repos_data, list):
                    repos_data = []
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch GitHub repos for user {username}: {e}")
            logger.error(f"Network or HTTP error fetching repos for GitHub user {username}: {e}", exc_info=True)
            repos_data = []

        # 4. Fetch languages for top repos
        for repo in repos_data:
            languages_url = repo.get("languages_url")
            if not languages_url:
                continue
            try:
                lang_resp = requests.get(languages_url, headers=headers, timeout=10)
                if lang_resp.status_code == 429:
                    logger.warning(f"Rate limit exceeded (429) fetching languages from {languages_url}")
                    return empty_result()
                elif lang_resp.status_code == 404:
                    continue
                lang_resp.raise_for_status()
                lang_data = lang_resp.json()
                if isinstance(lang_data, dict):
                    languages_set.update(lang_data.keys())
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch GitHub languages from {languages_url}: {e}")
                logger.error(f"Network or HTTP error fetching languages from {languages_url}: {e}", exc_info=True)
                continue

        name = user_data.get("name")
        email = user_data.get("email")
        bio = user_data.get("bio")
        location = user_data.get("location")

        result = empty_result()
        result["full_name"] = name if name else None
        result["emails"] = [email] if email else []
        result["headline"] = bio if bio else None
        result["github_url"] = f"https://github.com/{username}"
        result["location"] = location if location else None
        result["skills"] = sorted(list(languages_set))
        result["links"] = {"github": f"https://github.com/{username}"}

        # DEBUG: raw extracted values before normalization
        logger.debug(f"Raw GitHub extraction: {result}")

        # WARNING: when a source fails or field is null
        for k, v in result.items():
            if v is None or v == [] or v == {}:
                logger.warning(f"GitHub source field '{k}' is null or empty.")

        # INFO: which sources were processed
        logger.info(f"Processed GitHub source: {input_path_or_url}")

        return result

# Alias to support GithubSource naming
GithubSource = GitHubSource
