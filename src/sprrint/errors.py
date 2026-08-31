class SprrintError(Exception):
    def __init__(self, message, status=None, code=None, extra=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra or {}


class ConfigError(SprrintError):
    pass


class AuthError(SprrintError):
    pass
