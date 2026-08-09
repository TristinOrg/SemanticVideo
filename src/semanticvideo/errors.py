"""Public exception hierarchy for SemanticVideo operations."""


class SemanticVideoError(Exception):
    """Base class for expected, user-actionable SemanticVideo failures."""


class MediaInspectionError(SemanticVideoError):
    """Base class for failures while inspecting a media asset."""


class MediaNotFoundError(MediaInspectionError):
    """The requested media path does not identify a readable file."""


class FFprobeNotFoundError(MediaInspectionError):
    """The configured ffprobe executable could not be started."""


class FFprobeExecutionError(MediaInspectionError):
    """ffprobe ran but returned an unsuccessful exit code."""

    def __init__(self, returncode: int, stderr: str) -> None:
        detail = stderr.strip() or "ffprobe returned no diagnostic output"
        super().__init__(f"ffprobe failed with exit code {returncode}: {detail}")
        self.returncode = returncode
        self.stderr = stderr


class FFprobeParseError(MediaInspectionError):
    """ffprobe output was invalid or lacked required media information."""


class VideoAnalysisError(SemanticVideoError):
    """Base class for shot detection and visual-description failures."""


class FFmpegNotFoundError(VideoAnalysisError):
    """The configured ffmpeg executable could not be started."""


class FFmpegExecutionError(VideoAnalysisError):
    """ffmpeg ran but returned an unsuccessful exit code."""

    def __init__(self, operation: str, returncode: int, stderr: str) -> None:
        detail = stderr.strip() or "ffmpeg returned no diagnostic output"
        super().__init__(
            f"ffmpeg {operation} failed with exit code {returncode}: {detail}"
        )
        self.operation = operation
        self.returncode = returncode
        self.stderr = stderr


class DescriptionProviderError(VideoAnalysisError):
    """A configured visual-description provider could not return valid content."""
