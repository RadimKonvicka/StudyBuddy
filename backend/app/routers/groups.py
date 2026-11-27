"""Třídy: učitel založí třídu, žáci se připojí kódem a učitel vidí jejich témata a výsledky.

Role ("teacher" | "student") patří k členství ve třídě, ne k účtu. Kdo třídu založí, je v ní
učitel a může povýšit další členy na učitele. Učitel výsledky žáků jen čte – nic jim nemění.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import get_member, get_membership
from ..database import get_db
from ..deps import get_current_user
from ..models import Group, GroupMember, Quiz, Subject, User
from ..schemas import (
    GroupIn,
    GroupListItem,
    GroupOut,
    JoinIn,
    MemberBrief,
    QuizResultOut,
    RoleIn,
    StudentDetail,
    StudentRow,
)
from .quizzes import quiz_result
from .subjects import subject_out

router = APIRouter(prefix="/api/groups", tags=["Třídy"])

# Bez snadno zaměnitelných znaků (0/O, 1/I/L), aby se kód dal nadiktovat.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.scalar(select(Group.id).where(Group.join_code == code)):
            return code


def _normalize_code(code: str) -> str:
    """„k7p-2qx “ → „K7P2QX“ (žák může kód napsat malými písmeny, s mezerou nebo pomlčkou)."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _teachers(group: Group) -> list[GroupMember]:
    return [m for m in group.members if m.role == "teacher"]


def _list_item(group: Group, me: GroupMember) -> dict:
    return dict(
        id=group.id,
        name=group.name,
        role=me.role,
        teachers=[MemberBrief(user_id=m.user_id, display_name=m.user.display_name) for m in _teachers(group)],
        student_count=sum(m.role == "student" for m in group.members),
        join_code=group.join_code if me.role == "teacher" else None,
    )


def _subjects_of(db: Session, user_id: int) -> list[Subject]:
    return list(db.scalars(select(Subject).where(Subject.user_id == user_id).order_by(Subject.id.desc())))


def _student_row(member: GroupMember, subjects: list[Subject]) -> dict:
    user = member.user
    tested = [s.mastery for subj in subjects for s in subj.subtopics if s.mastery is not None]
    return dict(
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        joined_at=member.joined_at,
        xp=user.xp,
        streak=user.streak,
        last_active_date=user.last_active_date,
        subject_count=len(subjects),
        quizzes_done=sum(q.completed_at is not None for subj in subjects for q in subj.quizzes),
        mastery=round(sum(tested) / len(tested)) if tested else None,
    )


def _group_out(db: Session, group: Group, me: GroupMember) -> GroupOut:
    students = []
    if me.role == "teacher":
        students = [
            StudentRow(**_student_row(m, _subjects_of(db, m.user_id)))
            for m in group.members
            if m.role == "student"
        ]
    return GroupOut(**_list_item(group, me), students=students)


# --- Moje třídy, založení, připojení --------------------------------------------------------

@router.get("", response_model=list[GroupListItem])
def my_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.scalars(select(GroupMember).where(GroupMember.user_id == user.id).order_by(GroupMember.id.desc()))
    return [GroupListItem(**_list_item(m.group, m)) for m in members]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(body: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Založí třídu – zakladatel je v ní učitel."""
    group = Group(name=body.name, join_code=_new_code(db))
    me = GroupMember(user_id=user.id, role="teacher")
    group.members = [me]
    db.add(group)
    db.commit()
    return _group_out(db, group, me)


@router.post("/join", response_model=GroupOut)
def join_group(body: JoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Připojení do třídy kódem od učitele – jako žák."""
    group = db.scalar(select(Group).where(Group.join_code == _normalize_code(body.code)))
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Třída s tímto kódem neexistuje. Zkontroluj ho u učitele.")
    if any(m.user_id == user.id for m in group.members):
        raise HTTPException(status.HTTP_409_CONFLICT, "V této třídě už jsi.")
    me = GroupMember(user_id=user.id, role="student")
    group.members.append(me)
    db.commit()
    return _group_out(db, group, me)


# --- Detail a správa třídy ------------------------------------------------------------------

@router.get("/{group_id}", response_model=GroupOut)
def group_detail(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Učitel dostane i přehled žáků, žák jen základní informace o třídě."""
    me = get_membership(db, group_id, user)
    return _group_out(db, me.group, me)


@router.post("/{group_id}/code", response_model=GroupOut)
def new_code(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Nový kód pro připojení (starý přestane platit) – když kód unikl mimo třídu."""
    me = get_membership(db, group_id, user, teacher=True)
    me.group.join_code = _new_code(db)
    db.commit()
    return _group_out(db, me.group, me)


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Smaže třídu. Témata a výsledky žáků zůstanou – patří žákům, ne třídě."""
    me = get_membership(db, group_id, user, teacher=True)
    db.delete(me.group)
    db.commit()
    return Response(status_code=204)


def _keep_a_teacher(group: Group, member: GroupMember) -> None:
    if member.role == "teacher" and len(_teachers(group)) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ve třídě musí zůstat aspoň jeden učitel. Nejdřív jmenuj jiného učitele, nebo třídu smaž.",
        )


@router.patch("/{group_id}/members/{user_id}", response_model=GroupOut)
def change_role(
    group_id: int, user_id: int, body: RoleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Povýšení žáka na učitele, nebo naopak."""
    me = get_membership(db, group_id, user, teacher=True)
    member = get_member(db, me.group, user_id)
    if body.role == "student":
        _keep_a_teacher(me.group, member)
    member.role = body.role
    db.commit()
    return _group_out(db, me.group, me)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(group_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Učitel odebere člena, nebo kdokoli sám odejde (user_id = jeho vlastní ID)."""
    me = get_membership(db, group_id, user, teacher=user_id != user.id)
    member = me if user_id == user.id else get_member(db, me.group, user_id)
    _keep_a_teacher(me.group, member)
    db.delete(member)
    db.commit()
    return Response(status_code=204)


# --- Výsledky žáků (jen pro učitele) --------------------------------------------------------

@router.get("/{group_id}/students/{user_id}", response_model=StudentDetail)
def student_detail(group_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Všechna témata žáka se zvládnutím podtémat a historií testů."""
    me = get_membership(db, group_id, user, teacher=True)
    student = get_member(db, me.group, user_id, role="student")
    subjects = _subjects_of(db, user_id)
    return StudentDetail(
        **_student_row(student, subjects),
        group_id=me.group.id,
        group_name=me.group.name,
        subjects=[subject_out(s) for s in subjects],
    )


@router.get("/{group_id}/students/{user_id}/quizzes/{quiz_id}", response_model=QuizResultOut)
def student_quiz(
    group_id: int, user_id: int, quiz_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Odevzdaný test žáka i s jeho odpověďmi – učitel vidí, co přesně pokazil."""
    me = get_membership(db, group_id, user, teacher=True)
    get_member(db, me.group, user_id, role="student")
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.subject.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test neexistuje.")
    if quiz.completed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Žák tento test ještě neodevzdal.")
    return quiz_result(quiz)
