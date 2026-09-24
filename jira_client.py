"""
Jira REST client.

jira_search(jql) -> {"issues": [...], "total": N, ...}   (POST /rest/api/2/search/)

Pages through results so squads with more than 1000 matching stories are
returned in full. Uses a Personal Access Token (Bearer) from config / .env.
"""

import http.client
import json
import ssl

import config


def jira_search(jql):

    print("\n---- JQL ----")
    print(jql)

    headers = {
        "Authorization": f"Bearer {config.BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Optional corporate CA bundle for Jira servers with an internal certificate
    context = (
        ssl.create_default_context(cafile=config.JIRA_CA_BUNDLE)
        if config.JIRA_CA_BUNDLE else None
    )

    all_issues = []
    start_at = 0
    data = {}

    while True:

        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": 1000,
            "fields": [
                "summary",
                "assignee",
                "status",
                "created",
                "resolutiondate",
                config.STORY_POINTS_FIELD,
                config.SPRINT_FIELD
            ]
        }

        conn = http.client.HTTPSConnection(
            config.JIRA_HOST,
            context=context,
            timeout=60
        )

        conn.request(
            "POST",
            "/rest/api/2/search/",
            json.dumps(payload),
            headers
        )

        response = conn.getresponse()
        print("Response status:", response.status)

        response_text = response.read().decode("utf-8")

        conn.close()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            raise Exception(
                f"Jira API Error (HTTP {response.status}):\n{response_text[:500]}"
            )

        if "issues" not in data:
            raise Exception(
                f"Jira API Error (HTTP {response.status}):\n{response_text}"
            )

        all_issues.extend(data["issues"])
        start_at += len(data["issues"])

        if not data["issues"] or start_at >= data.get("total", 0):
            break

    data["issues"] = all_issues
    data["total"] = len(all_issues)

    return data
