"""
Pipeline nhận file: giới hạn kích thước → SHA-256 → nhận diện định dạng → quét virus →
phát hiện trùng → lưu bản gốc bất biến → giải nén ZIP (đệ quy có giới hạn) → audit.
Trích xuất dữ liệu chạy sau, trong worker (extract/), có cache theo phiên bản parser.
"""

import io

from .. import audit, db, settings, storage
from . import archive, scanner, sniff


def _result(upload_id, name, status, file_id=None, kind=None, error=None, children=None, warnings=None):
    return {
        "upload_id": upload_id, "name": name, "status": status, "file_id": file_id, "kind": kind,
        "error": error, "children": children or [], "warnings": warnings or [],
    }


def _record_upload(c, ctx, name, conversation_id, outcome, file_id=None, dup=False, error=None):
    uid = db.new_id()
    db.insert(c, "uploads", {
        "id": uid, "org_id": ctx.org_id, "file_id": file_id, "conversation_id": conversation_id,
        "original_name": name[:255], "duplicate_of_existing": 1 if dup else 0, "outcome": outcome,
        "error_json": db.dumps(error) if error else None, "uploaded_by": ctx.user, "uploaded_at": db.now(),
    })
    return uid


def ingest_stream(ctx, fp, original_name, conversation_id=None):
    ctx.require("upload")
    limit = int(settings.get()["max_file_mb"]) * 1024 * 1024
    try:
        tmp, sha, size = storage.hash_stream(fp, limit)
    except storage.StorageError as e:
        with db.tx() as c:
            err = {"code": "too_large", "message": str(e)}
            uid = _record_upload(c, ctx, original_name, conversation_id, "rejected", error=err)
            audit.log(c, ctx.org_id, ctx.user, "file.reject", "upload", uid, name=original_name, error=err)
        return _result(uid, original_name, "rejected", error=err)
    return _ingest_tmp(ctx, tmp, sha, size, original_name, conversation_id, depth=0, parent=None)


def _ingest_tmp(ctx, tmp, sha, size, name, conversation_id, depth, parent, archive_path=None):
    kind, mime, info = sniff.sniff(tmp, name)
    warnings = []
    if kind in sniff.REJECTED:
        err = {"code": f"unsupported_{kind}", "message": sniff.REJECTED[kind], "detected": kind}
        storage.discard_tmp(tmp)
        with db.tx() as c:
            uid = _record_upload(c, ctx, name, conversation_id, "rejected", error=err)
            audit.log(c, ctx.org_id, ctx.user, "file.reject", "upload", uid, name=name, sha256=sha, error=err)
        return _result(uid, name, "rejected", kind=kind, error=err)

    # Thành viên trong ZIP đã được quét cùng archive cha
    if parent is None:
        scan_status, scan_note = scanner.scan(tmp)
    else:
        scan_status, scan_note = "SCANNED_WITH_PARENT", parent["scan_status"]
    if scan_status == "INFECTED":
        storage.discard_tmp(tmp)
        err = {"code": "infected", "message": "File bị trình quét virus đánh dấu là độc hại", "scanner": scan_note}
        with db.tx() as c:
            uid = _record_upload(c, ctx, name, conversation_id, "rejected", error=err)
            audit.log(c, ctx.org_id, ctx.user, "file.infected", "upload", uid, name=name, sha256=sha)
        return _result(uid, name, "rejected", kind=kind, error=err)
    if scan_status in ("NOT_SCANNED", "ERROR"):
        warnings.append(f"Chưa quét virus: {scan_note}")
    if info.get("has_macros"):
        warnings.append("File chứa macro — macro KHÔNG được thực thi, chỉ đọc dữ liệu")

    existing = db.one("SELECT id, kind FROM files WHERE org_id=? AND sha256=?", (ctx.org_id, sha))
    if existing:
        storage.discard_tmp(tmp)
        with db.tx() as c:
            uid = _record_upload(c, ctx, name, conversation_id, "duplicate", existing["id"], dup=True)
            audit.log(c, ctx.org_id, ctx.user, "file.duplicate", "file", existing["id"], name=name, sha256=sha)
        children = []
        kids = db.all_("SELECT id, original_name, kind FROM files WHERE org_id=? AND parent_file_id=?",
                       (ctx.org_id, existing["id"]))
        if kids:
            # ZIP trùng: các file con cũng được gắn vào phiên làm việc hiện tại
            with db.tx() as c:
                for ch in kids:
                    cuid = _record_upload(c, ctx, ch["original_name"], conversation_id, "duplicate", ch["id"], dup=True)
                    children.append(_result(cuid, ch["original_name"], "duplicate", ch["id"], ch["kind"]))
        return _result(uid, name, "duplicate", existing["id"], existing["kind"], children=children,
                       warnings=warnings + ["Trùng hoàn toàn với file đã tải lên trước đó (cùng SHA-256)"])

    rel = storage.put_original(ctx.org_id, tmp, sha)
    file_id = db.new_id()
    with db.tx() as c:
        db.insert(c, "files", {
            "id": file_id, "org_id": ctx.org_id, "sha256": sha, "size": size, "original_name": name[:255],
            "kind": kind, "mime": mime, "storage_path": rel,
            "parent_file_id": parent["id"] if parent else None, "archive_path": archive_path,
            "scan_status": scan_status, "status": "stored",
            "error_json": db.dumps({"warnings": warnings, "sniff": info}),
            "uploaded_by": ctx.user, "uploaded_at": db.now(),
        })
        uid = _record_upload(c, ctx, name, conversation_id, "stored", file_id)
        audit.log(c, ctx.org_id, ctx.user, "file.store", "file", file_id, name=name, sha256=sha,
                  size=size, kind=kind, scan=scan_status, parent=parent["id"] if parent else None)

    children = []
    if kind == "zip":
        children = _expand(ctx, file_id, rel, scan_status, conversation_id, depth, warnings)
    return _result(uid, name, "stored", file_id, kind, children=children, warnings=warnings)


def _expand(ctx, file_id, rel, scan_status, conversation_id, depth, warnings):
    if depth + 1 > int(settings.get()["max_zip_depth"]):
        warnings.append("ZIP lồng quá sâu — không giải nén tiếp")
        return []
    try:
        items, skipped = archive.members(storage.abspath(rel))
    except archive.ArchiveError as e:
        warnings.append(str(e))
        with db.tx() as c:
            c.execute("UPDATE files SET status='rejected_archive', error_json=? WHERE id=? AND org_id=?",
                      (db.dumps({"code": e.code, "message": str(e)}), file_id, ctx.org_id))
            audit.log(c, ctx.org_id, ctx.user, "archive.reject", "file", file_id, code=e.code)
        return []
    for s in skipped:
        warnings.append(f"Bỏ qua '{s['name']}' trong ZIP: {s['reason']}")
    parent = {"id": file_id, "scan_status": scan_status}
    out = []
    for name, data in items:
        tmp, sha, size = storage.hash_stream(io.BytesIO(data))
        base = name.rsplit("/", 1)[-1]
        out.append(_ingest_tmp(ctx, tmp, sha, size, base, conversation_id, depth + 1, parent, archive_path=name))
    return out


def flatten(results):
    """Danh sách file_id đã lưu (kể cả trùng và thành viên ZIP), bỏ chính file ZIP chứa."""
    ids = []
    for r in results:
        if r["status"] in ("stored", "duplicate") and r["kind"] != "zip":
            ids.append(r["file_id"])
        ids.extend(flatten(r["children"]))
    return ids
