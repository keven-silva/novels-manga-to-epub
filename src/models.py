from dataclasses import dataclass, field


@dataclass
class Chapter:
    title: str
    content: str | list[bytes]
    url: str
    index: int


@dataclass
class Novel:
    title: str
    author: str
    cover_image: bytes | None = None
    cover_media_type: str = "image/jpeg"
    chapters: list[Chapter] = field(default_factory=list)
    is_manga: bool = False
