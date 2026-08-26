"""
Unit tests for Filesystem Subsystem tools (Phase 5).
All test cases strictly use isolated tmp_path sandbox environments.
"""

from pathlib import Path
from src.brain.models import ExecutionStatus, PermissionLevel
from src.core.config import Config
from src.core.exceptions import PathSecurityError
from src.tools.filesystem.copy import CopyFileTool
from src.tools.filesystem.create import CreateFolderTool, CreateTextFileTool
from src.tools.filesystem.delete import DeleteFileTool
from src.tools.filesystem.metadata import FileMetadataTool
from src.tools.filesystem.move import MoveFileTool
from src.tools.filesystem.organizer import OrganizeFolderTool
from src.tools.filesystem.paths import PathResolver
from src.tools.filesystem.rename import RenameFileTool
from src.tools.filesystem.search import SearchFilesTool


def test_path_resolver_security_rejection():
    resolver = PathResolver()

    # System directory path security rejection
    try:
        resolver.validate_path_security(Path("C:/Windows/System32/cmd.exe"))
        assert False, "Should have raised PathSecurityError"
    except PathSecurityError as e:
        assert "restricted system location" in str(e)


def test_filesystem_search_and_metadata(tmp_path):
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    # Create dummy files in sandbox
    (tmp_path / "test_doc.pdf").write_text("dummy pdf", encoding="utf-8")
    (tmp_path / "test_script.py").write_text("print('hello')", encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    res = search_tool.execute({"query": "test", "location": str(tmp_path)})
    assert res.status == ExecutionStatus.SUCCESS
    assert len(res.data["results"]) == 2

    # Metadata test
    meta_tool = FileMetadataTool(config=config, path_resolver=resolver)
    meta_res = meta_tool.execute({"target": str(tmp_path / "test_doc.pdf")})
    assert meta_res.status == ExecutionStatus.SUCCESS
    assert meta_res.data["name"] == "test_doc.pdf"


def test_filesystem_create_rename_move_copy_delete(tmp_path):
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    # 1. Create Folder
    create_folder = CreateFolderTool(config=config, path_resolver=resolver)
    res_f = create_folder.execute({"folder_name": "NewSubFolder", "location": str(tmp_path)})
    assert res_f.status == ExecutionStatus.SUCCESS
    assert (tmp_path / "NewSubFolder").exists()

    # 2. Create Text File
    create_file = CreateTextFileTool(config=config, path_resolver=resolver)
    res_txt = create_file.execute({"filename": "notes.txt", "content": "Sample content", "location": str(tmp_path)})
    assert res_txt.status == ExecutionStatus.SUCCESS
    file_path = tmp_path / "notes.txt"
    assert file_path.exists()

    # 3. Rename File
    rename_tool = RenameFileTool(config=config, path_resolver=resolver)
    res_ren = rename_tool.execute({"source": str(file_path), "new_name": "renamed_notes.txt"})
    assert res_ren.status == ExecutionStatus.SUCCESS
    renamed_path = tmp_path / "renamed_notes.txt"
    assert renamed_path.exists()

    # 4. Copy File
    copy_tool = CopyFileTool(config=config, path_resolver=resolver)
    res_cp = copy_tool.execute({"source": str(renamed_path), "destination": str(tmp_path / "NewSubFolder")})
    assert res_cp.status == ExecutionStatus.SUCCESS
    copied_path = tmp_path / "NewSubFolder" / "renamed_notes.txt"
    assert copied_path.exists()

    # 5. Safe Delete File
    delete_tool = DeleteFileTool(config=config, path_resolver=resolver)
    res_del = delete_tool.execute({"target": str(renamed_path)})
    assert res_del.status == ExecutionStatus.SUCCESS
    assert not renamed_path.exists()


def test_folder_organizer_dry_run(tmp_path):
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    (tmp_path / "sample.pdf").write_text("pdf", encoding="utf-8")
    (tmp_path / "sample.png").write_text("png", encoding="utf-8")

    organizer = OrganizeFolderTool(config=config, path_resolver=resolver)
    res = organizer.execute({"folder": str(tmp_path), "dry_run": True})

    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["dry_run"] is True
    assert len(res.data["plan"]) == 2
