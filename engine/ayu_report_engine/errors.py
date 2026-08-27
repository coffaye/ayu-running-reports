class EngineError(Exception):
    """Base error for deterministic, user-actionable engine failures."""


class IdentityError(EngineError, ValueError):
    """The source activity does not have a safe stable identity."""


class DataSourceError(EngineError, ValueError):
    """A source file is missing, malformed, or lacks required fields."""


class DataMismatchError(DataSourceError):
    """Two source representations disagree on an observed metric."""


class SchemaValidationError(EngineError, ValueError):
    """A context or semantic report does not satisfy its contract."""
