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
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.models import MaskRunResult
from src.masker import run as run_masker
from src.repo_finder import discover_repositories, find_enclosing_repository_root
from src.reporter import export_step, export_tree, serialise_results
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


def _default_export_dir() -> str:
    """証跡出力先のデフォルトパスを返す。

    Args:
        なし。
    Returns:
        str: `~/safe-repo-scanner-output/{YYYYMMDD_HHMMSS}` 形式のパス。
    Raises:
        ValueError: 送出しない。
    Note:
        Streamlit rerun ごとに変わらないよう session_state 初期化時のみ使う。
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path.home() / "safe-repo-scanner-output" / timestamp)


def _is_git_repository(path: str | Path) -> bool:
    """指定パスが Git リポジトリか判定する。

    Args:
        path: 判定対象ディレクトリ。
    Returns:
        bool: 自身または親ディレクトリが Git 管理下なら True。
    Raises:
        ValueError: 送出しない。
    Note:
        Git 管理下のサブディレクトリも対象にできるよう親方向へ探索する。
    """

    return find_enclosing_repository_root(path) is not None


def _select_directory_via_dialog(initial_dir: str | Path | None = None) -> str | None:
    """ローカルのフォルダ選択ダイアログを開く。

    Args:
        initial_dir: ダイアログの初期表示ディレクトリ。
    Returns:
        str | None: 選択したディレクトリ。キャンセル時は None。
    Raises:
        RuntimeError: ダイアログ初期化に失敗した場合。
    Note:
        Streamlit サーバーと同一端末で動作するローカル利用を前提とする。
    """

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("フォルダ選択ダイアログを利用できません。") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        preferred_dir = Path(initial_dir or Path.home()).expanduser()
        if preferred_dir.exists():
            dialog_dir = preferred_dir
        elif preferred_dir.parent.exists():
            dialog_dir = preferred_dir.parent
        else:
            dialog_dir = Path.home()
        selected_dir = filedialog.askdirectory(
            initialdir=str(dialog_dir),
            mustexist=True,
            title="対象リポジトリを選択",
        )
        return selected_dir or None
    finally:
        root.destroy()


def _render_directory_input_with_dialog(
    label: str,
    path_key: str,
    button_label: str,
    button_key: str,
    initial_dir: str | Path | None = None,
) -> str:
    """フォルダダイアログ付きのディレクトリ入力欄を描画する。

    Args:
        label: テキスト入力ラベル。
        path_key: 入力値を保持する session_state キー。
        button_label: ダイアログ起動ボタンの表示名。
        button_key: ダイアログ起動ボタンの widget key。
        initial_dir: ダイアログ初期ディレクトリ候補。
    Returns:
        str: 現在選択されているディレクトリパス。
    Raises:
        RuntimeError: ダイアログ起動に失敗した場合。
    Note:
        session_state の更新は text_input より前に行い、Streamlit の制約を避ける。
    """

    path_column, button_column = st.columns([5, 1])
    if button_column.button(button_label, key=button_key):
        try:
            selected_dir = _select_directory_via_dialog(st.session_state.get(path_key) or initial_dir)
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            if selected_dir:
                st.session_state[path_key] = selected_dir
    path_column.text_input(label, key=path_key)
    return st.session_state.get(path_key, "").strip()


def _render_path_tree_nodes(tree: dict[str, dict], depth: int = 0) -> list[str]:
    """パス階層辞書をツリー表示用の行へ変換する。

    Args:
        tree: パスから組み立てた階層辞書。
        depth: 現在の階層深さ。
    Returns:
        list[str]: 表示用 1 行文字列の一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        UI の expander にプレーンテキストで表示するため簡易な箇条書き形式を使う。
    """

    lines: list[str] = []
    indent = "  " * depth
    for name in sorted(tree):
        children = tree[name]
        suffix = "/" if children else ""
        lines.append(f"{indent}- {name}{suffix}")
        if children:
            lines.extend(_render_path_tree_nodes(children, depth + 1))
    return lines


def _render_path_tree(paths: list[str], root_label: str) -> str:
    """相対パス一覧をツリー文字列へ変換する。

    Args:
        paths: 相対パス一覧。
        root_label: ルート表示名。
    Returns:
        str: ツリー表示用の複数行文字列。
    Raises:
        ValueError: 送出しない。
    Note:
        対象ファイル候補の視認性を上げるため、重複パスは除去してから表示する。
    """

    if not paths:
        return f"{root_label}/\n- (no files)"

    tree: dict[str, dict] = {}
    for path in sorted(set(paths)):
        node = tree
        for part in path.split("/"):
            node = node.setdefault(part, {})
    return "\n".join([f"{root_label}/", *_render_path_tree_nodes(tree)]) + "\n"


def _filtered_masked_detections(detections: list, changed_files: list[str]) -> list:
    """実際に変更されるファイルだけの DetectionResult を返す。

    Args:
        detections: スキャン済み検出結果一覧。
        changed_files: マスク実行で変更対象になった相対パス一覧。
    Returns:
        list: 変更対象ファイルに属する DetectionResult 一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        Step 3 / Step 4 / Tree Export を変更対象に限定するために使う。
    """

    changed_file_set = set(changed_files)
    return [detection for detection in detections if detection.file_path in changed_file_set]


def _build_skipped_file_entries(skipped_files: list[str]) -> list[dict[str, str]]:
    """skipped_files を export_tree() 用の構造へ変換する。

    Args:
        skipped_files: スキップされた相対パス一覧。
    Returns:
        list[dict[str, str]]: `path` と `reason` を持つ辞書一覧。
    Raises:
        ValueError: 送出しない。
    Note:
        現行 masker は理由詳細を返さないため、UI では encoding error として扱う。
    """

    return [{"path": file_path, "reason": "encoding error"} for file_path in skipped_files]


def _run_masker_from_ui(
    repo_path: str,
    output_path: str,
    mode: str,
    detections: list,
    rules: dict,
    selected_paths: list[str] | None,
) -> MaskRunResult | None:
    """UI から masker を安全に呼び出す。

    Args:
        repo_path: 元リポジトリパス。
        output_path: UI 上の出力先パス。
        mode: `dry-run` または `apply`。
        detections: スキャン済み検出結果。
        rules: masking_rules.yaml の設定。
        selected_paths: UI で選択された対象ファイル一覧。
    Returns:
        MaskRunResult | None: 成功時は実行結果、失敗時は None。
    Raises:
        RuntimeError: 送出しない。
    Note:
        Streamlit 画面を例外スタックトレースで止めず、エラーメッセージへ変換する。
    """

    try:
        result = run_masker(
            repo_path,
            output_path=output_path,
            mode=mode,
            target_files=selected_paths,
            detections=detections,
            rules=rules,
        )
        st.session_state["mask_result"] = result
        return result
    except FileExistsError:
        st.session_state.pop("mask_result", None)
        suggested_path = _suggest_available_output_path(output_path)
        st.session_state["output_path"] = suggested_path
        st.error(f"出力先が既に存在します: {output_path}")
        st.info(f"別の出力先を使ってください。候補: {suggested_path}")
    except ValueError as exc:
        st.session_state.pop("mask_result", None)
        st.error(str(exc))
    return None


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

    if "export_dir" not in st.session_state:
        st.session_state["export_dir"] = _default_export_dir()
    if "repo_selection_mode" not in st.session_state:
        st.session_state["repo_selection_mode"] = "一覧から選択"
    if "selected_repo_path" not in st.session_state:
        st.session_state["selected_repo_path"] = ""
    if "step_exports" not in st.session_state:
        st.session_state["step_exports"] = {}

    rules = load_masking_rules()
    default_root = str(Path.home())
    repositories = st.session_state.get("repositories", [])
    selection_column, selection_button_column = st.columns([5, 1])
    selection_mode = selection_column.radio(
        "リポジトリ選択方法",
        ["一覧から選択", "フォルダダイアログで選択"],
        key="repo_selection_mode",
        horizontal=True,
    )

    selected_repo = ""
    if selection_mode == "一覧から選択":
        search_root = st.text_input("検索ルート", value=st.session_state.get("search_root", default_root))
        st.session_state["search_root"] = search_root
        if st.button("リポジトリ検索"):
            st.session_state["repositories"] = discover_repositories(search_root)
            repositories = st.session_state.get("repositories", [])
        _render_table(_serialise_rows(repositories))
        if not repositories:
            st.info("一覧から選択するには、先にリポジトリ検索を実行してください。")
            return

        options = {f"{repo.name} | {repo.branch} | {repo.path}": repo.path for repo in repositories}
        labels = list(options.keys())
        selected_path = st.session_state.get("selected_repo_path", "")
        default_index = 0
        if selected_path:
            matching_indices = [index for index, label in enumerate(labels) if options[label] == selected_path]
            if matching_indices:
                default_index = matching_indices[0]
        selected_label = st.selectbox("対象リポジトリ", labels, index=default_index)
        selected_repo = options[selected_label]
        st.session_state["selected_repo_path"] = selected_repo
    else:
        if selection_button_column.button("フォルダ選択", key="repo_folder_dialog_button"):
            try:
                selected_dir = _select_directory_via_dialog(
                    st.session_state.get("selected_repo_path") or st.session_state.get("search_root") or default_root
                )
            except RuntimeError as exc:
                st.error(str(exc))
            else:
                if selected_dir:
                    st.session_state["selected_repo_path"] = selected_dir
        st.text_input("対象リポジトリパス", key="selected_repo_path")
        selected_repo = st.session_state.get("selected_repo_path", "").strip()
        if not selected_repo:
            st.info("フォルダ選択ダイアログ、またはパス入力で対象リポジトリを指定してください。")
            return
        if not Path(selected_repo).exists():
            st.error(f"指定したフォルダが存在しません: {selected_repo}")
            return
        repository_root = find_enclosing_repository_root(selected_repo)
        if repository_root is None:
            st.error(f"指定したフォルダは Git 管理下ではありません: {selected_repo}")
            return
        if Path(selected_repo).expanduser().resolve() == repository_root.resolve():
            st.caption(f"選択中: {selected_repo}")
        else:
            st.caption(f"選択中: {selected_repo} (Git ルート: {repository_root})")

    export_dir = _render_directory_input_with_dialog(
        "証跡出力先",
        "export_dir",
        "出力先選択",
        "export_dir_dialog_button",
        st.session_state.get("export_dir") or default_root,
    )

    if st.session_state.get("selected_repo") not in {None, selected_repo}:
        st.session_state.pop("detections", None)
        st.session_state.pop("selected_paths", None)
        st.session_state.pop("mask_result", None)
        st.session_state.pop("tree_export_path", None)
        st.session_state["step_exports"] = {}

    if st.button("対象ファイル候補を生成"):
        generated_entries = generate_target_file_entries(selected_repo, rules)
        st.session_state["target_entries"] = generated_entries
        st.session_state["selected_repo"] = selected_repo
        st.session_state.pop("detections", None)
        st.session_state.pop("selected_paths", None)
        st.session_state.pop("mask_result", None)
        st.session_state.pop("tree_export_path", None)
        step_exports = dict(st.session_state.get("step_exports", {}))
        try:
            step_exports[1] = str(export_step(1, generated_entries, Path(export_dir)))
        except OSError as exc:
            st.error(f"Step 1 の出力に失敗しました: {exc}")
        st.session_state["step_exports"] = step_exports

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
        with st.expander("対象ファイルツリー", expanded=False):
            st.code(_render_path_tree(selected_paths, Path(selected_repo).name), language="text")

        if st.button("スキャン実行"):
            detections = scan_selected_files(selected_repo, target_files=selected_paths, rules=rules)
            st.session_state["detections"] = detections
            st.session_state["selected_paths"] = selected_paths
            st.session_state.pop("tree_export_path", None)
            step_exports = dict(st.session_state.get("step_exports", {}))
            try:
                step_exports[2] = str(export_step(2, detections, Path(export_dir)))
            except OSError as exc:
                st.error(f"Step 2 の出力に失敗しました: {exc}")
            st.session_state["step_exports"] = step_exports

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
            result = _run_masker_from_ui(
                selected_repo,
                output_path=output_path,
                mode="dry-run",
                selected_paths=st.session_state.get("selected_paths"),
                detections=detections,
                rules=rules,
            )
            if result:
                st.session_state.pop("tree_export_path", None)
                masked_detections = _filtered_masked_detections(result.detections, result.changed_files)
                step_exports = dict(st.session_state.get("step_exports", {}))
                try:
                    step_exports[3] = str(export_step(3, masked_detections, Path(export_dir)))
                except OSError as exc:
                    st.error(f"Step 3 の出力に失敗しました: {exc}")
                st.session_state["step_exports"] = step_exports
        if apply_column.button("apply"):
            result = _run_masker_from_ui(
                selected_repo,
                output_path=output_path,
                mode="apply",
                selected_paths=st.session_state.get("selected_paths"),
                detections=detections,
                rules=rules,
            )
            if result:
                masked_detections = _filtered_masked_detections(result.detections, result.changed_files)
                step_exports = dict(st.session_state.get("step_exports", {}))
                try:
                    step_exports[4] = str(export_step(4, masked_detections, Path(export_dir)))
                    tree_path = export_tree(
                        masked_detections,
                        _build_skipped_file_entries(result.skipped_files),
                        Path(selected_repo).name,
                        Path(export_dir),
                    )
                    st.session_state["tree_export_path"] = str(tree_path)
                except OSError as exc:
                    st.error(f"apply 後の証跡出力に失敗しました: {exc}")
                st.session_state["step_exports"] = step_exports

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
        step_exports = st.session_state.get("step_exports", {})
        tree_export_path = st.session_state.get("tree_export_path")
        if step_exports or tree_export_path:
            export_summary = {f"step_{step}": path for step, path in sorted(step_exports.items())}
            if tree_export_path:
                export_summary["masked_file_tree"] = tree_export_path
            st.write({"exports": export_summary})
        for file_path, diff_text in mask_result.diffs.items():
            st.markdown(f"**{file_path}**")
            st.code(diff_text or "(no diff)", language="diff")
        if tree_export_path:
            with st.expander("マスク済みファイルツリー", expanded=False):
                tree_text = Path(tree_export_path).read_text(encoding="utf-8")
                st.markdown(tree_text)


if __name__ == "__main__":
    main()
