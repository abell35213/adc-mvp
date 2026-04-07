"""Repository layer for users and orgs."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import User, Org, UserOrg
from app.security.permissions import Role, normalize_role


# ── Users ──────────────────────────────────────────────────────────


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: _uuid.UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    email: str,
    password_hash: str,
    role: str = Role.SAFETY_MANAGER.value,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        role=normalize_role(role).value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Orgs ───────────────────────────────────────────────────────────


def get_org(db: Session, org_id: _uuid.UUID) -> Org | None:
    return db.query(Org).filter(Org.id == org_id).first()


def create_org(db: Session, name: str) -> Org:
    org = Org(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


# ── User ↔ Org links ──────────────────────────────────────────────


def link_user_org(db: Session, user_id: _uuid.UUID, org_id: _uuid.UUID) -> UserOrg:
    link = UserOrg(user_id=user_id, org_id=org_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_user_org_ids(db: Session, user_id: _uuid.UUID) -> list[_uuid.UUID]:
    """Return org IDs for a user."""
    rows = db.query(UserOrg.org_id).filter(UserOrg.user_id == user_id).all()
    return [r[0] for r in rows]
