"""Streamlit UI エントリポイント。

概要:
    リポジトリ探索、対象ファイル選択、スキャン結果表示、dry-run / apply 実行を
    行う Phase 1 用の最小 UI を提供する。
入出力:
    ユーザー入力を受け取り、テーブル表示とマスク実行結果を返す。
制約:
    表示には preview のみを使い、生値は UI に表示しない。
Note:
    Streamlit 実行時は `streamlit run app.py` を使用する。
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import streamlit as st

from src.masker import run as run_masker
from src.repo_finder import discover_repositories
from src.reporter import serialise_results
from src.scanner import scan_selected_files
from src.target_file_selector import generate_target_file_entries
from src.utils import load_masking_rules


def _render_table(rows: list[dict]) -> None:
    """辞書リストを Streamlit 上へ表示する。

    Args:
        rows: 表示対象の辞書リスト。
    Returns:
        None
    Raises:
        ValueError: 送出しない。
    Note:
        pandas を追加せずに済むよう、Streamlit 標準描画を使う。
    """

    if rows:
        st.write(rows)
    else:
        st.info("表示対象はありません。")


def _serialise_rows(items: list[object]) -> list[dict]:
    """dataclass 一覧を Streamlit 表示向け辞書へ変換する。

    Args:
        items: dataclass インスタンス一覧。
    Returns:
        list[dict]: Streamlit 表示用の辞書一覧。
    Raises:
        TypeError: dataclass 以外が渡された場合。
    Note:
        slots=True の dataclass は `__dict__` を持たないため `asdict` を使う。
    """

    return [asdict(item) for item in items]


def _suggest_available_output_path(preferred_path: str | Path) -> str:
    """未使用の出力先パス候補を返す。

    Args:
        preferred_path: 第1候補の出力先パス。
    Returns:
        str: まだ存在しない出力先パス。
    Raises:
        ValueError: 送出しない。
    Note:
        既存ディレクトリを上書きしないため、末尾に連番を付けて回避する。
    """

    candidate = Path(preferred_path)
    if not candidate.exists():
        return str(candidate)

    index = 1
    while True:
        suffixed_candidate = candidate.parent / f"{candidate.name}-{index}"
        if not suffixed_candidate.exists():
            return str(suffixed_candidate)
        index += 1


def _run_masker_from_ui(
    repo_path: str,
    output_path: str,
    mode: str,
    detections: list,
    rules: dict,
    selected_paths: list[str] | None,
) -> None:
    """UI から masker を安全に呼び出す。

    Args:
        repo_path: 元リポジトリパス。
        output_path: UI 上の出力先パス。
        mode: `dry-run` または `apply`。
        detections: スキャン済み検出結果。
        rules: masking_rules.yaml の設定。
        selected_paths: UI で選択された対象ファイル一覧。
    Returns:
        None
    Raises:
        RuntimeError: 送出しない。
    Note:
        Streamlit 画面を例外スタックトレースで止めず、エラーメッセージへ変換する。
    """

    try:
        st.session_state["mask_result"] = run_masker(
            repo_path,
            output_path=output_path,
            mode=mode,
            target_files=selected_paths,
            detections=detections,
            rules=rules,
        )
    except FileExistsError:
        st.session_state.pop("mask_result", None)
        suggested_path = _suggest_available_output_path(output_path)
        st.session_state["output_path"] = suggested_path
        st.error(f"出力先が既に存在します: {output_path}")
        st.info(f"別の出力先を使ってください。候補: {suggested_path}")
    except ValueError as exc:
        st.session_state.pop("mask_result", None)
        st.error(str(exc))


def main() -> None:
    """Streamlit UI を描画する。

    Args:
        なし
    Returns:
        None
    Raises:
        RuntimeError: Streamlit 実行時の UI 例外。
    Note:
        session_state を使って検索結果とスキャン結果を保持する。
    """

    st.set_page_config(page_title="safe-repo-scanner", layout="wide")
    st.title("safe-repo-scanner")
    st.caption("ローカル Git リポジトリの機密情報を preview ベースで確認し、安全なコピーへマスク適用します。")

    rules = load_masking_rules()
    default_root = str(Path.home())
    search_root = st.text_input("検索ルート", value=st.session_state.get("search_root", default_root))
    st.session_state["search_root"] = search_root

    if st.button("リポジトリ検索"):
        st.session_state["repositories"] = discover_repositories(search_root)

    repositories = st.session_state.get("repositories", [])
    _render_table(_serialise_rows(repositories))
    if not repositories:
        return

    options = {f"{repo.name} | {repo.branch} | {repo.path}": repo.path for repo in repositories}
    selected_label = st.selectbox("対象リポジトリ", list(options.keys()))
    selected_repo = options[selected_label]

    if st.button("対象ファイル候補を生成"):
        st.session_state["target_entries"] = generate_target_file_entries(selected_repo, rules)
        st.session_state["selected_repo"] = selected_repo

    target_entries = st.session_state.get("target_entries", [])
    if st.session_state.get("selected_repo") != selected_repo:
        target_entries = []

    if target_entries:
        high_only = st.checkbox("high risk のみ表示", value=False)
        visible_entries = [entry for entry in target_entries if not high_only or entry.risk_level == "high"]
        selected_paths = st.multiselect(
            "スキャン対象ファイル",
            [entry.path for entry in visible_entries],
            default=[entry.path for entry in visible_entries if entry.selected],
        )
        _render_table(_serialise_rows(visible_entries))

        if st.button("スキャン実行"):
            st.session_state["detections"] = scan_selected_files(selected_repo, target_files=selected_paths, rules=rules)
            st.session_state["selected_paths"] = selected_paths

    detections = st.session_state.get("detections", [])
    if detections:
        st.subheader("スキャン結果")
        _render_table(serialise_results(detections))

        default_output = _suggest_available_output_path(Path(selected_repo).with_name(f"{Path(selected_repo).name}-masked"))
        if st.session_state.get("output_repo") != selected_repo:
            st.session_state["output_repo"] = selected_repo
            st.session_state["output_path"] = default_output
        elif not st.session_state.get("output_path"):
            st.session_state["output_path"] = default_output

        output_path = st.text_input("マスク済みコピー出力先", key="output_path")

        dry_run_column, apply_column = st.columns(2)
        if dry_run_column.button("dry-run"):
            _run_masker_from_ui(
                selected_repo,
                output_path=output_path,
                mode="dry-run",
                selected_paths=st.session_state.get("selected_paths"),
                detections=detections,
                rules=rules,
            )
        if apply_column.button("apply"):
            _run_masker_from_ui(
                selected_repo,
                output_path=output_path,
                mode="apply",
                selected_paths=st.session_state.get("selected_paths"),
                detections=detections,
                rules=rules,
            )

    mask_result = st.session_state.get("mask_result")
    if mask_result:
        st.subheader("実行結果")
        st.write(
            {
                "mode": mask_result.mode,
                "detections": len(mask_result.detections),
                "changed_files": len(mask_result.changed_files),
                "output_path": mask_result.output_path,
                "report_paths": mask_result.report_paths,
                "skipped_files": mask_result.skipped_files,
            }
        )
        for file_path, diff_text in mask_result.diffs.items():
            st.markdown(f"**{file_path}**")
            st.code(diff_text or "(no diff)", language="diff")


if __name__ == "__main__":
    main()
