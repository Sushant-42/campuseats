class APIError(Exception):
    def __init__(self, status: int, title: str, detail: str, retry_after: int = None):
        self.status = status
        self.title = title
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(detail)


def problem_response(error: APIError):
    return {
        "type": "about:blank",
        "title": error.title,
        "status": error.status,
        "detail": error.detail
    }
