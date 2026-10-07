class CnrtError(RuntimeError):
    pass


class LoginError(CnrtError):
    pass


class SessionExpiredError(CnrtError):
    pass


class AvailabilityChangedError(CnrtError):
    pass


class StructureChangedError(CnrtError):
    pass
