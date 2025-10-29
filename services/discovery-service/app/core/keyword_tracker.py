"""Smart keyword scanning with rotation and time windows."""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum

from google.cloud import firestore

logger = logging.getLogger(__name__)


class KeywordPriority(str, Enum):
    """Priority levels for keyword rotation."""

    HIGH = "high"  # Scan every 3 days
    MEDIUM = "medium"  # Scan every 14 days
    LOW = "low"  # Scan every 30 days


class KeywordTracker:
    """
    Track keyword scan state to avoid duplicate discoveries.

    Each keyword maintains:
    - Last scanned timestamp
    - Last video publish date scanned
    - Scan direction (forward or backward in time)
    """

    def __init__(self, firestore_client: firestore.Client):
        self.firestore = firestore_client
        self.collection = "keyword_scan_state"

    def get_next_scan_window(
        self, keyword: str, window_days: int = 7, prioritize_recent: bool = True
    ) -> tuple[datetime | None, datetime | None]:
        """
        Get the next time window to scan for this keyword.

        Strategy:
        - First scan: ALWAYS check last 24 hours first (new content priority!)
        - Subsequent scans: Move forward OR scan recent if hasn't been checked recently
        - Returns (published_after, published_before) for bounded search

        Args:
            keyword: Search keyword
            window_days: Size of search window in days
            prioritize_recent: If True, prioritize last 24h if not scanned recently

        Returns:
            Tuple of (published_after, published_before) as datetime objects
        """
        doc_ref = self.firestore.collection(self.collection).document(keyword)

        try:
            doc = doc_ref.get()
            now = datetime.now(timezone.utc)

            if not doc.exists:
                # First scan: ALWAYS scan last 24 hours first (catch new uploads!)
                start_date = now - timedelta(days=1)
                end_date = now

                # Initialize state
                doc_ref.set({
                    "keyword": keyword,
                    "last_scanned_at": now,
                    "last_published_date": end_date,
                    "scan_direction": "forward",
                    "total_scans": 1,
                    "videos_found": 0
                })

                logger.info(
                    f"Keyword '{keyword}': First scan from "
                    f"{start_date.date()} to {end_date.date()} (random start)"
                )

                return start_date, end_date

            # Load existing state
            data = doc.to_dict()
            last_published = data.get("last_published_date")
            scan_direction = data.get("scan_direction", "forward")

            if scan_direction == "forward":
                # Scan forward from where we left off
                start_date = last_published if last_published else now - timedelta(days=1)
                end_date = min(start_date + timedelta(days=window_days), now)

                # If we caught up to present, start scanning backward
                if (now - end_date).days < 1:
                    scan_direction = "backward"
                    # Jump back to 90 days ago
                    start_date = now - timedelta(days=90)
                    end_date = start_date + timedelta(days=window_days)
                    logger.info(
                        f"Keyword '{keyword}': Caught up! Switching to backward scan"
                    )
            else:
                # Scan backward into history
                end_date = last_published
                start_date = end_date - timedelta(days=window_days)

                # Don't go back more than 365 days
                if (now - start_date).days > 365:
                    scan_direction = "forward"
                    start_date = now - timedelta(days=7)
                    end_date = now
                    logger.info(
                        f"Keyword '{keyword}': Reached 1 year back, switching to forward"
                    )

            # Update state
            doc_ref.update({
                "last_scanned_at": now,
                "last_published_date": end_date,
                "scan_direction": scan_direction,
                "total_scans": firestore.Increment(1)
            })

            logger.info(
                f"Keyword '{keyword}': Scanning {scan_direction} from "
                f"{start_date.date()} to {end_date.date()}"
            )

            return start_date, end_date

        except Exception as e:
            logger.error(f"Error getting scan window for '{keyword}': {e}")
            # Fallback: last 7 days
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
            return start_date, end_date

    def record_results(self, keyword: str, videos_found: int) -> None:
        """
        Record scan results for a keyword.

        Args:
            keyword: Search keyword
            videos_found: Number of videos discovered
        """
        doc_ref = self.firestore.collection(self.collection).document(keyword)

        try:
            doc_ref.update({
                "videos_found": firestore.Increment(videos_found),
                "last_result_count": videos_found
            })
            logger.debug(f"Keyword '{keyword}': Recorded {videos_found} videos")
        except Exception as e:
            logger.error(f"Error recording results for '{keyword}': {e}")

    def get_keywords_for_rotation(
        self, limit: int = 5, priority: KeywordPriority | None = None
    ) -> list[str]:
        """
        Get keywords that need scanning, prioritizing by priority and staleness.

        Args:
            limit: Maximum keywords to return
            priority: Filter by specific priority level (optional)

        Returns:
            List of keyword strings to scan
        """
        try:
            query = self.firestore.collection(self.collection)

            # Filter by priority if specified
            if priority:
                query = query.where("priority", "==", priority.value)

            # Order by least recently scanned
            query = query.order_by("last_scanned_at").limit(limit)

            docs = list(query.stream())
            keywords = [doc.get("keyword") for doc in docs]

            logger.info(
                f"Got {len(keywords)} keywords for rotation"
                + (f" (priority={priority.value})" if priority else "")
            )
            return keywords

        except Exception as e:
            logger.error(f"Error getting keywords for rotation: {e}")
            return []

    def get_keywords_due_for_scan(self, limit: int = 50) -> list[tuple[str, str, str]]:
        """
        Get keywords that are due for scanning based on their priority rotation schedule.

        Rotation schedules:
        - HIGH: Every 3 days
        - MEDIUM: Every 14 days
        - LOW: Every 30 days

        Args:
            limit: Maximum keywords to return

        Returns:
            List of (keyword, priority, ip_name) tuples
        """
        try:
            now = datetime.now(timezone.utc)
            due_keywords = []

            # Define rotation intervals by priority
            rotation_intervals = {
                KeywordPriority.HIGH: timedelta(days=3),
                KeywordPriority.MEDIUM: timedelta(days=14),
                KeywordPriority.LOW: timedelta(days=30),
            }

            # Query all keywords
            docs = self.firestore.collection(self.collection).stream()

            for doc in docs:
                data = doc.to_dict()
                keyword = data.get("keyword")
                priority_str = data.get("priority", "medium")
                ip_name = data.get("ip_name", "Unknown")
                last_scanned = data.get("last_scanned_at")

                try:
                    priority = KeywordPriority(priority_str)
                except ValueError:
                    priority = KeywordPriority.MEDIUM

                # Get rotation interval for this priority
                interval = rotation_intervals.get(priority, timedelta(days=14))

                # Check if keyword is due
                if last_scanned is None:
                    # Never scanned - definitely due
                    due_keywords.append((keyword, priority.value, ip_name))
                elif (now - last_scanned) >= interval:
                    # Due for rescan
                    due_keywords.append((keyword, priority.value, ip_name))

            # Sort by priority (HIGH first), then by staleness
            priority_order = {"high": 0, "medium": 1, "low": 2}
            due_keywords.sort(key=lambda x: priority_order.get(x[1], 99))

            result = due_keywords[:limit]
            logger.info(f"Found {len(result)} keywords due for scanning")

            return result

        except Exception as e:
            logger.error(f"Error getting keywords due for scan: {e}")
            return []

    def set_keyword_priority(
        self, keyword: str, priority: KeywordPriority, ip_name: str | None = None
    ) -> None:
        """
        Set or update keyword priority.

        Args:
            keyword: Search keyword
            priority: Priority level
            ip_name: Associated IP target name (optional)
        """
        doc_ref = self.firestore.collection(self.collection).document(keyword)

        try:
            update_data = {
                "priority": priority.value,
                "updated_at": datetime.now(timezone.utc),
            }

            if ip_name:
                update_data["ip_name"] = ip_name

            # Check if document exists
            if doc_ref.get().exists:
                doc_ref.update(update_data)
            else:
                # Create new document
                update_data.update(
                    {
                        "keyword": keyword,
                        "last_scanned_at": None,
                        "total_scans": 0,
                        "videos_found": 0,
                    }
                )
                doc_ref.set(update_data)

            logger.debug(f"Set keyword '{keyword}' priority to {priority.value}")

        except Exception as e:
            logger.error(f"Error setting keyword priority: {e}")

    def sync_keywords_from_ip_targets(self, ip_manager) -> dict:
        """
        Sync keyword priorities from IP targets configuration.

        Updates Firestore with priorities from ip_targets.yaml.

        Args:
            ip_manager: IPTargetManager instance

        Returns:
            Stats dict with sync results
        """
        try:

            enabled_targets = ip_manager.get_enabled_targets()

            stats = {"synced": 0, "created": 0, "updated": 0}

            for ip_target in enabled_targets:
                # Map IP priority to keyword priority
                # HIGH IP -> HIGH keywords
                # MEDIUM IP -> MEDIUM keywords
                # LOW IP -> LOW keywords
                keyword_priority = KeywordPriority(ip_target.priority.value)

                for keyword in ip_target.keywords:
                    doc_ref = self.firestore.collection(self.collection).document(
                        keyword
                    )
                    doc = doc_ref.get()

                    if doc.exists:
                        # Update existing
                        doc_ref.update(
                            {
                                "priority": keyword_priority.value,
                                "ip_name": ip_target.name,
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
                        stats["updated"] += 1
                    else:
                        # Create new
                        doc_ref.set(
                            {
                                "keyword": keyword,
                                "priority": keyword_priority.value,
                                "ip_name": ip_target.name,
                                "last_scanned_at": None,
                                "total_scans": 0,
                                "videos_found": 0,
                                "created_at": datetime.now(timezone.utc),
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
                        stats["created"] += 1

                    stats["synced"] += 1

            logger.info(
                f"Synced {stats['synced']} keywords from IP targets "
                f"({stats['created']} created, {stats['updated']} updated)"
            )

            return stats

        except Exception as e:
            logger.error(f"Error syncing keywords from IP targets: {e}")
            return {"error": str(e)}

    def get_statistics(self) -> dict:
        """Get keyword scanning statistics."""
        try:
            docs = self.firestore.collection(self.collection).stream()

            stats = {
                "total_keywords": 0,
                "total_scans": 0,
                "total_videos_found": 0,
                "by_direction": {"forward": 0, "backward": 0}
            }

            for doc in docs:
                data = doc.to_dict()
                stats["total_keywords"] += 1
                stats["total_scans"] += data.get("total_scans", 0)
                stats["total_videos_found"] += data.get("videos_found", 0)

                direction = data.get("scan_direction", "forward")
                stats["by_direction"][direction] += 1

            return stats

        except Exception as e:
            logger.error(f"Error calculating keyword statistics: {e}")
            return {"error": str(e)}
