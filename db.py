import logging
from datetime import date, datetime, timezone

from supabase import Client, create_client

from config import SUPABASE_KEY, SUPABASE_URL
from parsers.base import Internship

log = logging.getLogger(__name__)

_TABLE = "seen_internships"
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in the environment"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def init_db() -> None:
    # Table + index are provisioned in Supabase directly. Schema:
    #   uid text primary key
    #   company text not null
    #   role text not null
    #   apply_url text not null
    #   date_posted date not null
    #   source text not null
    #   posted_to_discord boolean default false
    #   first_seen_at timestamptz not null default now()
    #   discord_posted_at timestamptz
    #   create index idx_apply_url on seen_internships(apply_url)
    _get_client()


def is_seen(uid: str) -> bool:
    res = (
        _get_client()
        .table(_TABLE)
        .select("uid")
        .eq("uid", uid)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def apply_url_exists(apply_url: str) -> bool:
    res = (
        _get_client()
        .table(_TABLE)
        .select("uid")
        .eq("apply_url", apply_url)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def mark_seen(internship: Internship) -> None:
    _get_client().table(_TABLE).upsert(
        {
            "uid": internship.uid,
            "company": internship.company,
            "role": internship.role,
            "apply_url": internship.apply_url,
            "date_posted": internship.date_posted.isoformat(),
            "source": internship.source,
            "posted_to_discord": False,
            "first_seen_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="uid",
        ignore_duplicates=True,
    ).execute()


def mark_posted(uid: str) -> None:
    _get_client().table(_TABLE).update(
        {
            "posted_to_discord": True,
            "discord_posted_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("uid", uid).execute()


def get_unsent(today: date) -> list[Internship]:
    res = (
        _get_client()
        .table(_TABLE)
        .select("uid,company,role,apply_url,date_posted,source")
        .eq("posted_to_discord", False)
        .gte("date_posted", today.isoformat())
        .execute()
    )
    return [
        Internship(
            uid=r["uid"],
            company=r["company"],
            role=r["role"],
            location="",
            apply_url=r["apply_url"],
            date_posted=date.fromisoformat(r["date_posted"]),
            source=r["source"],
            is_closed=False,
        )
        for r in (res.data or [])
    ]
