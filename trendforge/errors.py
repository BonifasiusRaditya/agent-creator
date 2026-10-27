class AppError(Exception):
    def __init__(self, message, code="INVALID_REQUEST", status=422, details=None):
        self.message = message
        self.code = code
        self.status = status
        self.details = details or {}
        super().__init__(message)

