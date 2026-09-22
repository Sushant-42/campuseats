class APIError(Exception):
    def __init__(self, status: int, title: str, detail: str):
        self.status = status
        self.title = title
        self.detail = detail
        super().__init__(detail)


def problem_response(error: APIError):
    return {
        "type": "about:blank",
        "title": error.title,
        "status": error.status,
        "detail": error.detail
    }