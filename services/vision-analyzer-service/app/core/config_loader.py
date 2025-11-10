"""
IP Configuration Loader for Vision Analyzer Service.

Loads IP-specific configurations from Firestore to enable dynamic,
multi-IP video analysis without hardcoded character lists.
"""

import logging
import os
import time
from dataclasses import dataclass

from google.cloud import firestore

logger = logging.getLogger(__name__)


@dataclass
class IPConfig:
    """IP-specific configuration for vision analysis."""

    id: str
    name: str
    owner: str
    characters: list[str]
    visual_keywords: list[str]
    ai_tool_patterns: list[str]
    false_positive_filters: list[str]
    common_video_titles: list[str]

    @property
    def has_valid_data(self) -> bool:
        """Check if config has minimum required data."""
        return bool(self.characters and self.name and self.owner)


class ConfigLoader:
    """Loads IP configurations from Firestore with caching."""

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self._cache: dict[str, IPConfig] = {}
        self._cache_timestamps: dict[str, float] = {}
        self.cache_ttl = int(os.getenv("CONFIG_CACHE_TTL_SECONDS", "300"))
        self.collection_name = os.getenv("IP_CONFIG_COLLECTION", "ip_configs")

    def get_config(self, ip_id: str) -> IPConfig | None:
        """
        Get configuration for a specific IP.

        Args:
            ip_id: IP configuration ID (e.g., 'justice-league')

        Returns:
            IPConfig if found, None otherwise
        """
        now = time.time()

        # Check if cached and not expired
        if ip_id in self._cache:
            cache_time = self._cache_timestamps.get(ip_id, 0)
            if now - cache_time < self.cache_ttl:
                logger.debug(f"Config cache hit for {ip_id}")
                return self._cache[ip_id]
            else:
                logger.debug(f"Config cache expired for {ip_id}")

        # Load from Firestore
        config = self._load_from_firestore(ip_id)

        if config:
            # Update cache
            self._cache[ip_id] = config
            self._cache_timestamps[ip_id] = now
            logger.info(f"Loaded config for {ip_id}: {config.name}")
        else:
            logger.error(f"Config not found for IP: {ip_id}")

        return config

    def get_all_configs(self) -> list[IPConfig]:
        """
        Get all IP configurations.

        Useful for multi-IP matching in discovery service.

        Returns:
            List of all IPConfig objects
        """
        configs = []
        try:
            docs = self.db.collection(self.collection_name).stream()
            for doc in docs:
                try:
                    config = self._doc_to_config(doc)
                    if config and config.has_valid_data:
                        configs.append(config)
                except Exception as e:
                    logger.error(f"Error parsing config {doc.id}: {e}")
                    continue

            logger.info(f"Loaded {len(configs)} IP configs")
        except Exception as e:
            logger.error(f"Error loading all configs: {e}")

        return configs

    def invalidate_cache(self, ip_id: str | None = None):
        """
        Manually invalidate cache.

        Args:
            ip_id: Specific IP to invalidate, or None to clear all
        """
        if ip_id:
            self._cache.pop(ip_id, None)
            self._cache_timestamps.pop(ip_id, None)
            logger.info(f"Invalidated cache for {ip_id}")
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Invalidated all config cache")

    def _load_from_firestore(self, ip_id: str) -> IPConfig | None:
        """Load config from Firestore."""
        try:
            doc = self.db.collection(self.collection_name).document(ip_id).get()
            if not doc.exists:
                return None

            return self._doc_to_config(doc)

        except Exception as e:
            logger.error(f"Error loading config {ip_id} from Firestore: {e}")
            return None

    def _doc_to_config(self, doc) -> IPConfig | None:
        """Convert Firestore document to IPConfig."""
        try:
            data = doc.to_dict()
            if not data:
                return None

            config = IPConfig(
                id=doc.id,
                name=data.get("name", ""),
                owner=data.get("owner", ""),
                characters=data.get("characters", []),
                visual_keywords=data.get("visual_keywords", []),
                ai_tool_patterns=data.get("ai_tool_patterns", []),
                false_positive_filters=data.get("false_positive_filters", []),
                common_video_titles=data.get("common_video_titles", []),
            )

            # Validate required fields
            if not config.has_valid_data:
                logger.warning(f"Config {doc.id} missing required fields")
                return None

            return config

        except Exception as e:
            logger.error(f"Error parsing config document {doc.id}: {e}")
            return None
