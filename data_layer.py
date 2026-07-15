"""SQLAlchemyDataLayer adapted for SQLite and project-tagged threads."""

import json
from typing import Optional

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import PageInfo, PaginatedResponse, Pagination, ThreadFilter

from app_logging import logger
from projects import GENERAL_PROFILE


class ProjectDataLayer(SQLAlchemyDataLayer):
    """Fixes SQLite tag persistence and adds project-aware thread naming/search.

    The stock layer binds `tags` as a Python list, which sqlite3 rejects —
    and execute_sql swallows the error, silently dropping the whole thread
    INSERT. Tags are therefore stored as a JSON string and parsed on read.
    """

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list] = None,
    ):
        if name and tags and tags[0] != GENERAL_PROFILE:
            prefix = f"[{tags[0]}] "
            if not name.startswith(prefix):
                name = prefix + name
        if tags is not None:
            tags = json.dumps(tags)
        await super().update_thread(
            thread_id=thread_id, name=name, user_id=user_id, metadata=metadata, tags=tags
        )
        logger.debug("thread updated id={} name={} tags={}", thread_id, name, tags)

    async def get_all_user_threads(self, user_id=None, thread_id=None):
        threads = await super().get_all_user_threads(user_id=user_id, thread_id=thread_id)
        for thread in threads or []:
            if isinstance(thread.get("tags"), str):
                try:
                    thread["tags"] = json.loads(thread["tags"])
                except json.JSONDecodeError:
                    thread["tags"] = []
        logger.debug(
            "get_all_user_threads user_id={} thread_id={} count={}",
            user_id, thread_id, len(threads or []),
        )
        return threads

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse:
        # Mirrors the upstream implementation, except the search keyword also
        # matches thread names so "[Project]" prefixes are searchable
        # (upstream only scans step outputs).
        if not filters.userId:
            raise ValueError("userId is required")
        all_user_threads = await self.get_all_user_threads(user_id=filters.userId) or []

        search_keyword = filters.search.lower() if filters.search else None
        feedback_value = int(filters.feedback) if filters.feedback else None

        filtered_threads = []
        for thread in all_user_threads:
            keyword_match = True
            feedback_match = True
            if search_keyword:
                name_match = search_keyword in (thread.get("name") or "").lower()
                step_match = any(
                    search_keyword in step["output"].lower()
                    for step in thread["steps"]
                    if "output" in step
                )
                keyword_match = name_match or step_match
            if feedback_value is not None:
                feedback_match = False
                for step in thread["steps"]:
                    feedback = step.get("feedback")
                    if feedback and feedback.get("value") == feedback_value:
                        feedback_match = True
                        break
            if keyword_match and feedback_match:
                filtered_threads.append(thread)

        start = 0
        if pagination.cursor:
            for i, thread in enumerate(filtered_threads):
                if thread["id"] == pagination.cursor:
                    start = i + 1
                    break
        end = start + pagination.first
        paginated_threads = filtered_threads[start:end] or []

        has_next_page = len(filtered_threads) > end
        start_cursor = paginated_threads[0]["id"] if paginated_threads else None
        end_cursor = paginated_threads[-1]["id"] if paginated_threads else None

        logger.debug(
            "list_threads user_id={} search={} count={}",
            filters.userId, filters.search, len(paginated_threads),
        )
        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=start_cursor,
                endCursor=end_cursor,
            ),
            data=paginated_threads,
        )
