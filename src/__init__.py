"""safe-repo-scanner の公開 API。

概要:
    パッケージ利用時に参照される主要データモデルを公開する。
入出力:
    import のみを受け付け、直接の入出力は持たない。
制約:
    Phase 1 の公開面のみを扱い、外部通信を含まない。
Note:
    CLI は `python -m src.scanner` から起動する。
"""

from .models import DetectionResult, MaskRunResult, RepoEntry, TargetFileEntry

__all__ = [
    "DetectionResult",
    "MaskRunResult",
    "RepoEntry",
    "TargetFileEntry",
]
