import os

from django.core.exceptions import ValidationError

ALLOWED_UPLOAD_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".heic",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_uploaded_file(file):
    """Block clearly unsafe uploads before they reach MEDIA_ROOT.

    Extension whitelist + size cap. This is a first line of defence; production
    deployments should also serve /media/ only through an authenticated route
    and scan attachments with antivirus tooling.
    """
    ext = os.path.splitext(file.name.lower())[1]
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed types: {allowed}."
        )
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("File is too large. Maximum allowed size is 10 MB.")