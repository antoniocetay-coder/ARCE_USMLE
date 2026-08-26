class ApplicationError(RuntimeError):
    """Base application error safe to present to the UI."""

class DatabaseError(ApplicationError): pass
class QuestionGenerationError(ApplicationError): pass
class FlashcardGenerationError(ApplicationError): pass
class TutorGenerationError(ApplicationError): pass
class InvalidAISettingsError(ApplicationError): pass
class InvalidQuestionError(ApplicationError): pass
class StudySessionError(ApplicationError): pass
class DuplicateBatchError(ApplicationError): pass
# Compatibility name for page-level error handling during migration.
StudyApplicationError = ApplicationError
PersistenceError = DatabaseError
