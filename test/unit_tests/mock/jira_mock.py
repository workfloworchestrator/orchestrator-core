from http import HTTPStatus

from orchestrator.utils.json import json_dumps


class JiraMocks:
    def __init__(self, responses):
        self.responses = responses

    def get_ticket(self, ticket_id, show_summary=True):
        response = {"ticket_id": ticket_id}
        if show_summary:
            response["summary"] = "Jira summary for Customer X"

        self.responses.add(
            "GET",
            f"/jira/tickets/{ticket_id}",
            body=json_dumps(response),
            status=HTTPStatus.CREATED,
            content_type="application/json",
        )

    def comment_on_ticket(self, ticket_id):
        self.responses.add("POST", f"/jira/tickets/{ticket_id}/comments", body=None, status=HTTPStatus.NO_CONTENT)
