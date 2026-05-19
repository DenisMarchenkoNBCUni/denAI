"""Direct Jira REST API client using the new POST /rest/api/3/search/jql endpoint.

The mcp-atlassian 0.21.1 search_jira_issues tool is broken because Atlassian
removed the old GET /rest/api/3/search endpoint (HTTP 410). This module calls
the new endpoint directly.
"""

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

TOOL_NAME = "jira_search_jql"

TOOL_DEFINITION: dict[str, Any] = {
    "name": f"atlassian__{TOOL_NAME}",
    "description": (
        "Search Jira issues using JQL (Jira Query Language). "
        "Returns matching issues with key, summary, status, assignee, and URL. "
        "Use this instead of search_jira_issues which is broken."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "jql": {
                "type": "string",
                "description": "A JQL query string, e.g. 'assignee = \"user@email.com\" AND status != Done'",
            },
            "maxResults": {
                "type": "number",
                "description": "Maximum results to return (default 20, max 100)",
                "default": 20,
            },
            "fields": {
                "type": "string",
                "description": "Comma-separated fields to return (default: summary,status,assignee,priority,issuetype,updated)",
                "default": "summary,status,assignee,priority,issuetype,updated",
            },
        },
        "required": ["jql"],
    },
}


class JiraClient:
    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, api_token)

    async def search(self, jql: str, max_results: int = 20, fields: str = "") -> dict[str, Any]:
        field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else [
            "summary", "status", "assignee", "priority", "issuetype", "updated"
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/api/3/search/jql",
                json={
                    "jql": jql,
                    "maxResults": min(max_results, 100),
                    "fields": field_list,
                },
                auth=self._auth,
            )

        if resp.status_code != 200:
            error_body = resp.text[:500]
            logger.warning("jira search failed", status=resp.status_code, body=error_body)
            return {"error": f"Jira API returned HTTP {resp.status_code}: {error_body}"}

        return resp.json()

    def format_results(self, data: dict[str, Any]) -> str:
        if "error" in data:
            return data["error"]

        issues = data.get("issues", [])
        total = data.get("total", len(issues))

        if not issues:
            return "No issues found matching the query."

        lines = [f"Found {total} issue(s). Showing {len(issues)}:\n"]
        for issue in issues:
            key = issue["key"]
            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            status = fields.get("status", {}).get("name", "Unknown")
            assignee = fields.get("assignee", {})
            assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
            priority = fields.get("priority", {})
            priority_name = priority.get("name", "") if priority else ""
            issue_type = fields.get("issuetype", {})
            type_name = issue_type.get("name", "") if issue_type else ""
            url = f"{self._base_url}/browse/{key}"

            line = f"• *{key}* — {summary}\n  Status: {status} | Type: {type_name} | Priority: {priority_name} | Assignee: {assignee_name}\n  {url}"
            lines.append(line)

        return "\n".join(lines)
