"""IP targets loader and manager."""

import logging
from pathlib import Path
from typing import Any

import yaml

from ..models import IPTarget

logger = logging.getLogger(__name__)


class IPTargetManager:
    """
    Manager for IP targets configuration.

    Loads IP targets from YAML file and provides methods to:
    - Get all enabled IPs
    - Get keywords for discovery
    - Check if content matches any IP
    """

    def __init__(self, config_path: str | Path | None = None):
        """Initialize IP target manager."""
        if config_path is None:
            # Default to ip_targets.yaml in app directory
            config_path = Path(__file__).parent.parent / "ip_targets.yaml"

        self.config_path = Path(config_path)
        self.targets: list[IPTarget] = []
        self.load_targets()

    def load_targets(self) -> None:
        """Load IP targets from YAML configuration."""
        try:
            if not self.config_path.exists():
                logger.warning(f"IP targets config not found at {self.config_path}")
                return

            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data or "targets" not in data:
                logger.warning("No targets found in IP config")
                return

            self.targets = []
            for target_data in data["targets"]:
                try:
                    target = IPTarget(**target_data)
                    self.targets.append(target)
                except Exception as e:
                    logger.error(f"Failed to load IP target: {e}")
                    continue

            logger.info(f"Loaded {len(self.targets)} IP targets from config")

        except Exception as e:
            logger.error(f"Failed to load IP targets config: {e}")
            self.targets = []

    def get_enabled_targets(self) -> list[IPTarget]:
        """Get all enabled IP targets."""
        return [t for t in self.targets if t.enabled]

    def get_targets_by_priority(self, priority: str) -> list[IPTarget]:
        """Get enabled IP targets filtered by priority."""

        return [t for t in self.get_enabled_targets() if t.priority.value == priority]

    def get_high_priority_targets(self) -> list[IPTarget]:
        """Get high priority IP targets."""
        return self.get_targets_by_priority("high")

    def get_medium_priority_targets(self) -> list[IPTarget]:
        """Get medium priority IP targets."""
        return self.get_targets_by_priority("medium")

    def get_low_priority_targets(self) -> list[IPTarget]:
        """Get low priority IP targets."""
        return self.get_targets_by_priority("low")

    def get_all_keywords(self) -> list[str]:
        """Get all keywords from enabled IP targets."""
        keywords = []
        for target in self.get_enabled_targets():
            keywords.extend(target.keywords)
        return keywords

    def match_content(self, text: str) -> list[IPTarget]:
        """
        Check if text matches any IP targets.

        YouTube-level comprehensive matching:
        - Exact keyword matches
        - Character names (with word boundaries)
        - Handles punctuation, spacing variations
        - Strips articles (The, A, An)
        - Case insensitive
        - Partial matching throughout entire text

        Args:
            text: Text to check (title, description, tags, channel name)

        Returns:
            List of matched IP targets
        """
        text_lower = text.lower()

        # Normalize: replace punctuation with spaces for better word matching
        import re
        text_normalized = re.sub(r'[^\w\s]', ' ', text_lower)
        text_normalized = ' '.join(text_normalized.split())  # Remove extra spaces

        matched = []

        for target in self.get_enabled_targets():
            target_matched = False

            # 1. Match configured keywords (most specific)
            for keyword in target.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text_lower:
                    target_matched = True
                    break

            # 2. Match character name with word boundaries
            # Ensures "Superman" matches but "supersomething" doesn't
            character_name = target.name.lower()

            # Word boundary pattern: \b{name}\b
            name_pattern = r'\b' + re.escape(character_name) + r'\b'
            if re.search(name_pattern, text_normalized):
                target_matched = True

            # 3. Handle multi-word names with articles
            # "The Flash" → also matches "Flash"
            name_without_article = re.sub(r'\b(the|a|an)\s+', '', character_name).strip()
            if name_without_article and name_without_article != character_name:
                article_pattern = r'\b' + re.escape(name_without_article) + r'\b'
                if re.search(article_pattern, text_normalized):
                    target_matched = True

            if target_matched and target not in matched:
                matched.append(target)

        return matched

    def get_target_by_name(self, name: str) -> IPTarget | None:
        """Get IP target by name."""
        for target in self.targets:
            if target.name.lower() == name.lower():
                return target
        return None

    def get_search_queries(self) -> list[str]:
        """
        Generate search queries for discovery based on IP targets.

        Returns queries optimized for YouTube search.
        """
        queries = []
        for target in self.get_enabled_targets():
            # Use the most distinctive keyword for each IP
            if target.keywords:
                primary_keyword = target.keywords[0]
                queries.append(primary_keyword)

        return queries

    def reload(self) -> None:
        """Reload IP targets from config file."""
        logger.info("Reloading IP targets configuration")
        self.load_targets()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of IP targets."""
        enabled = self.get_enabled_targets()
        return {
            "total_targets": len(self.targets),
            "enabled_targets": len(enabled),
            "disabled_targets": len(self.targets) - len(enabled),
            "total_keywords": len(self.get_all_keywords()),
            "targets_by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count targets by type."""
        counts: dict[str, int] = {}
        for target in self.get_enabled_targets():
            type_name = target.type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
