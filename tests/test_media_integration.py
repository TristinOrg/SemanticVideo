"""Small end-to-end media inspection test using local FFmpeg tools."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from semanticvideo.cli.main import main
from semanticvideo.media import inspect_media


@pytest.mark.integration
def test_inspect_synthetic_video(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg tools are not installed")

    output = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000",
            "-t",
            "0.4",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ],
        check=True,
        capture_output=True,
    )

    media = inspect_media(output, executable=ffprobe)

    assert media.duration.seconds == pytest.approx(0.4, abs=0.05)
    assert [stream.kind for stream in media.streams] == ["video", "audio"]
    assert media.streams[0].kind == "video"
    assert (media.streams[0].width, media.streams[0].height) == (160, 90)

    assert main(["inspect", str(output), "--ffprobe", ffprobe, "--compact"]) == 0
    cli_result = json.loads(capsys.readouterr().out)
    assert cli_result["duration"] == {"value": 2, "rate": 5}
    assert [stream["kind"] for stream in cli_result["streams"]] == [
        "video",
        "audio",
    ]
