"""
Jira REST client.

jira_search(jql) -> {"issues": [...], "total": N, ...}   (POST /rest/api/2/search/)
jira_search(jql, fields=["*all"], limit=1)               (used by python -m report.diagnose)

Pages through results so squads with more than 1000 matching stories are
returned in full. Uses a Personal Access Token (Bearer) from config / .env.
"""

import http.client
import json
import logging
import ssl
import time

import config

log = logging.getLogger(__name__)


def _one_line(jql):
    """JQL on one line, for log messages."""
    return " ".join(jql.split())


DEFAULT_FIELDS = [
    "summary",
    "assignee",
    "status",
    "created",
    "resolutiondate",
]


def jira_search(jql, fields=None, limit=None):
    """
    fields  Jira field ids to return; default = what the report needs
    limit   stop after this many issues (None = all pages)
    """

    started = time.perf_counter()
    log.debug("JQL: %s", _one_line(jql))

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
    pages = 0
    data = {}

    while True:

        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": min(1000, limit) if limit else 1000,
            "fields": fields or DEFAULT_FIELDS + [config.STORY_POINTS_FIELD, config.SPRINT_FIELD]
        }

        conn = http.client.HTTPSConnection(
            config.JIRA_HOST,
            context=context,
            timeout=60
        )

        try:
            conn.request(
                "POST",
                "/rest/api/2/search/",
                json.dumps(payload),
                headers
            )
            response = conn.getresponse()
            response_text = response.read().decode("utf-8")
        except (OSError, http.client.HTTPException) as exc:
            log.error("Could not reach Jira at %s: %s", config.JIRA_HOST, exc)
            raise Exception(f"Could not reach Jira at {config.JIRA_HOST}: {exc}") from exc
        finally:
            conn.close()

        log.debug("POST /rest/api/2/search/ startAt=%d -> HTTP %d (%d bytes)",
                  start_at, response.status, len(response_text))

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            log.error("Jira returned non-JSON (HTTP %d) for JQL: %s\n%s",
                      response.status, _one_line(jql), response_text[:500])
            raise Exception(
                f"Jira API Error (HTTP {response.status}):\n{response_text[:500]}"
            )

        if "issues" not in data:
            log.error("Jira API error (HTTP %d) for JQL: %s\n%s",
                      response.status, _one_line(jql), response_text[:1000])
            raise Exception(
                f"Jira API Error (HTTP {response.status}):\n{response_text}"
            )

        all_issues.extend(data["issues"])
        start_at += len(data["issues"])
        pages += 1

        if not data["issues"] or start_at >= data.get("total", 0) or (limit and start_at >= limit):
            break

    data["issues"] = all_issues
    data["total"] = len(all_issues)

    log.info("Jira search -> %d issues, %d page(s), %.0f ms | %s",
             len(all_issues), pages, (time.perf_counter() - started) * 1000, _one_line(jql)[:160])
    return data


def jira_get(path):
    """GET a Jira REST path (e.g. "/rest/api/2/field") and return the parsed JSON."""
    context = (
        ssl.create_default_context(cafile=config.JIRA_CA_BUNDLE)
        if config.JIRA_CA_BUNDLE else None
    )
    conn = http.client.HTTPSConnection(config.JIRA_HOST, context=context, timeout=60)
    try:
        conn.request("GET", path, headers={"Authorization": f"Bearer {config.BEARER_TOKEN}"})
        response = conn.getresponse()
        text = response.read().decode("utf-8")
    except (OSError, http.client.HTTPException) as exc:
        log.error("Could not reach Jira at %s: %s", config.JIRA_HOST, exc)
        raise Exception(f"Could not reach Jira at {config.JIRA_HOST}: {exc}") from exc
    finally:
        conn.close()
    log.info("GET %s -> HTTP %d", path, response.status)
    if response.status != 200:
        log.error("Jira API error (HTTP %d) for GET %s\n%s", response.status, path, text[:500])
        raise Exception(f"Jira API Error (HTTP {response.status}) for GET {path}:\n{text[:500]}")
    return json.loads(text)
