"""
Phân quyền theo tổ chức (tenant). Quyền quyết định ở máy chủ từ bảng org_members, không tin frontend.

Hub đã kiểm tra đăng nhập + quyền dùng công cụ "accounting" (core/auth._guard). Ở đây kiểm tra
người dùng là thành viên tổ chức và có vai trò phù hợp với thao tác.
"""

from dataclasses import dataclass, field

from . import audit, db

ROLES = ("ADMIN", "ACCOUNTANT", "REVIEWER", "APPROVER", "AUDITOR", "VIEWER")

PERMS = {
    "read": set(ROLES),
    "upload": {"ADMIN", "ACCOUNTANT"},
    "run_task": {"ADMIN", "ACCOUNTANT"},
    "edit_draft": {"ADMIN", "ACCOUNTANT"},
    "request_commit": {"ADMIN", "ACCOUNTANT"},
    "review": {"ADMIN", "REVIEWER"},
    "approve": {"APPROVER"},
    "lock_period": {"ADMIN", "APPROVER"},
    "audit": {"ADMIN", "AUDITOR"},
    "manage": {"ADMIN"},
}


class Forbidden(Exception):
    def __init__(self, msg, code="forbidden"):
        super().__init__(msg)
        self.code = code


class NotFound(Exception):
    pass


@dataclass
class Ctx:
    org_id: str
    user: str
    roles: set = field(default_factory=set)

    def can(self, perm):
        return bool(self.roles & PERMS[perm])

    def require(self, perm):
        if not self.can(perm):
            raise Forbidden(f"Vai trò của bạn không có quyền '{perm}' trong tổ chức này", "no_role")


def roles_of(org_id, user):
    with db.central():
        return {
            r["role"]
            for r in db.all_(
                "SELECT role FROM org_members WHERE org_id=? AND user_email=?", (org_id, user)
            )
        }


def context(org_id, user):
    """Ctx cho người dùng trong tổ chức; không phải thành viên → NotFound (không lộ tổ chức tồn tại)."""
    if not org_id or not user:
        raise NotFound()
    roles = roles_of(org_id, user)
    if not roles:
        raise NotFound()
    return Ctx(org_id, user, roles)


def orgs_of(user):
    with db.central():
        return _orgs_of(user)


def _orgs_of(user):
    rows = db.all_(
        """SELECT o.id, o.name, o.tax_id, o.base_currency, o.accounting_regime, group_concat(m.role) roles
           FROM orgs o JOIN org_members m ON m.org_id=o.id WHERE m.user_email=?
           GROUP BY o.id ORDER BY o.created_at""",
        (user,),
    )
    for r in rows:
        r["roles"] = sorted(set((r["roles"] or "").split(",")))
    return rows


def create_org(name, created_by, roles=("ADMIN", "ACCOUNTANT", "REVIEWER", "APPROVER"), tax_id=None,
               base_currency="VND"):
    from . import tenancy
    from .engine import coa

    org_id = db.new_id()
    row = {
        "id": org_id, "name": name.strip()[:120] or "Tổ chức", "tax_id": (tax_id or None),
        "base_currency": base_currency, "accounting_regime": coa.DEFAULT_REGIME,
        "created_by": created_by, "created_at": db.now(),
    }
    with db.central(), db.tx() as c:  # danh bạ trung tâm: tổ chức + thành viên
        db.insert(c, "orgs", row)
        for role in roles:
            db.insert(c, "org_members", {
                "org_id": org_id, "user_email": created_by, "role": role,
                "added_by": created_by, "added_at": db.now(),
            })
    tenancy.create_tenant(row)  # file database riêng của tổ chức
    with db.use_org(org_id), db.tx() as c:
        coa.seed(c, org_id)
        audit.log(c, org_id, created_by, "org.create", "org", org_id, name=name, roles=list(roles))
    return org_id


def ensure_personal_org(user, display_name):
    orgs = orgs_of(user)
    if orgs:
        return orgs[0]["id"]
    return create_org(f"Không gian kế toán của {display_name or user}", user)


def set_member(ctx, email, roles):
    ctx.require("manage")
    email = str(email or "").strip().lower()
    bad = [r for r in roles if r not in ROLES]
    if bad or not email:
        raise Forbidden(f"Vai trò không hợp lệ: {bad}", "bad_role")
    with db.central(), db.tx() as c:
        before = sorted(r[0] for r in c.execute(
            "SELECT role FROM org_members WHERE org_id=? AND user_email=?", (ctx.org_id, email)))
        if email == ctx.user and "ADMIN" in before and "ADMIN" not in roles:
            admins = c.execute(
                "SELECT count(*) FROM org_members WHERE org_id=? AND role='ADMIN'", (ctx.org_id,)
            ).fetchone()[0]
            if admins <= 1:
                raise Forbidden("Tổ chức phải còn ít nhất một ADMIN", "last_admin")
        c.execute("DELETE FROM org_members WHERE org_id=? AND user_email=?", (ctx.org_id, email))
        for role in sorted(set(roles)):
            db.insert(c, "org_members", {
                "org_id": ctx.org_id, "user_email": email, "role": role,
                "added_by": ctx.user, "added_at": db.now(),
            })
    with db.use_org(ctx.org_id):
        audit.record(ctx.org_id, ctx.user, "member.set", "member", email, before=before, after=sorted(set(roles)))


def member_count(org_id):
    with db.central():
        return db.one("SELECT count(DISTINCT user_email) n FROM org_members WHERE org_id=?", (org_id,))["n"]


def self_approval(ctx):
    """None = không được tự duyệt; "setting" = cấu hình cho phép; "single_member" = tổ chức chỉ có một người
    (không có người thứ hai để phân tách nhiệm vụ) — được tự duyệt khi xác nhận rõ, có ghi audit."""
    from . import settings

    if settings.get()["allow_self_approval"]:
        return "setting"
    return "single_member" if member_count(ctx.org_id) == 1 else None


def members(ctx):
    with db.central():
        rows = db.all_(
        "SELECT user_email, group_concat(role) roles FROM org_members WHERE org_id=? GROUP BY user_email",
            (ctx.org_id,),
        )
    return [{"email": r["user_email"], "roles": sorted(r["roles"].split(","))} for r in rows]
