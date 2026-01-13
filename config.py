import os


class Config:
    """Application configuration settings"""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY") 

    # File upload settings
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "uploads"
    )
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

    # Session settings
    SESSION_TYPE = "filesystem"
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Matching algorithm settings
    EXACT_MATCH_THRESHOLD = 1.0
    FUZZY_MATCH_THRESHOLD = 0.80  # 80% similarity
    HIGH_CONFIDENCE_THRESHOLD = 0.90  # Auto-confirm matches above this
    KEYWORD_MIN_LENGTH = 3  # Minimum keyword length for matching

    # Balance calculation settings
    BALANCE_TOLERANCE = 0.01  # Tolerance for floating point comparison

    # Export settings
    DEFAULT_STATUS_TEXT = "RECONCILED"
    DEFAULT_HIGHLIGHT_COLOR = "FFFF00"  # Yellow

    # Common stopwords for entity extraction
    STOPWORDS = [
        "to",
        "from",
        "for",
        "the",
        "and",
        "or",
        "in",
        "at",
        "by",
        "invoice",
        "payment",
        "receipt",
        "transaction",
        "bill",
        "ref",
    ]

    # Transaction type keywords
    EXPENSE_KEYWORDS = ["expense", "payment", "paid", "invoice", "bill", "debit"]
    REVENUE_KEYWORDS = ["revenue", "income", "received", "credit", "deposit"]

    @staticmethod
    def init_app(app):
        """Initialize application with config"""
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
