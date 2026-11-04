"""도면 PDF 저장소. 파일은 {FileId}.pdf로 저장한다."""
from collections.abc import Iterable

from .. import config


def path_of(file_id: str):
    return config.file_dir() / f"{file_id}.pdf"


def remove(file_ids: Iterable[str | None]) -> None:
    for file_id in file_ids:
        if file_id:
            path_of(file_id).unlink(missing_ok=True)
