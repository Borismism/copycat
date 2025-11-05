"""Universal configuration loader for Copycat system.

All services use this to load IP catalogs, client info, and system settings.
This ensures consistency across discovery, risk-analyzer, vision-analyzer, api, and frontend.

Usage:
    from shared.config_loader import load_config, get_all_characters, get_ip_by_id

    config = load_config()
    characters = get_all_characters()
    justice_league = get_ip_by_id("dc-justice-league")
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Path to shared config (relative to repo root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "shared_config.yaml"


class CopycatConfig:
    """Parsed configuration with helper methods."""

    def __init__(self, config_dict: dict[str, Any]):
        """Initialize with parsed YAML config."""
        self._config = config_dict

    @property
    def client_name(self) -> str:
        """Get client name (e.g., 'Warner Bros. Entertainment')."""
        return self._config.get("client", {}).get("name", "Unknown Client")

    @property
    def client_abbreviation(self) -> str:
        """Get client abbreviation (e.g., 'WB')."""
        return self._config.get("client", {}).get("abbreviation", "")

    @property
    def intellectual_properties(self) -> list[dict[str, Any]]:
        """Get all IP definitions."""
        return self._config.get("intellectual_properties", [])

    @property
    def ai_tools(self) -> list[dict[str, Any]]:
        """Get all AI tool definitions."""
        return self._config.get("ai_tools", [])

    @property
    def default_characters(self) -> list[str]:
        """Get default character list."""
        return self._config.get("system", {}).get("default_characters", [])

    def get_all_characters(self, priority: str | None = None) -> list[str]:
        """
        Get all unique character names across all IPs.

        Args:
            priority: Filter by monitoring priority (high, medium, low)

        Returns:
            List of unique character names
        """
        characters = set()

        for ip in self.intellectual_properties:
            if priority and ip.get("monitoring_priority") != priority:
                continue

            characters.update(ip.get("characters", []))

        return sorted(characters)

    def get_ip_by_id(self, ip_id: str) -> dict[str, Any] | None:
        """
        Get IP definition by ID.

        Args:
            ip_id: IP identifier (e.g., "dc-justice-league")

        Returns:
            IP dict or None if not found
        """
        for ip in self.intellectual_properties:
            if ip.get("id") == ip_id:
                return ip
        return None

    def get_ips_by_character(self, character_name: str) -> list[dict[str, Any]]:
        """
        Find all IPs that include a specific character.

        Args:
            character_name: Character name (case-insensitive)

        Returns:
            List of IP dicts containing this character
        """
        character_lower = character_name.lower()
        matching_ips = []

        for ip in self.intellectual_properties:
            characters = [c.lower() for c in ip.get("characters", [])]
            if character_lower in characters:
                matching_ips.append(ip)

        return matching_ips

    def get_characters_by_priority(self, priority: str) -> list[str]:
        """
        Get characters filtered by monitoring priority.

        Args:
            priority: 'high', 'medium', or 'low'

        Returns:
            List of character names
        """
        return self.get_all_characters(priority=priority)

    def get_ai_tool_keywords(self) -> list[str]:
        """Get all AI tool detection keywords."""
        keywords = []
        for tool in self.ai_tools:
            keywords.extend(tool.get("detection_keywords", []))
        return keywords

    def get_copyright_owner(self, character_name: str) -> str:
        """
        Get copyright owner for a character.

        Args:
            character_name: Character name

        Returns:
            Owner string (e.g., "DC Comics / Warner Bros. Entertainment")
        """
        ips = self.get_ips_by_character(character_name)
        if ips:
            return ips[0].get("owner", "Unknown")
        return "Unknown"

    def get_value_tier_multiplier(self, ip_id: str) -> float:
        """
        Get risk multiplier for an IP based on its value tier.

        Args:
            ip_id: IP identifier

        Returns:
            Multiplier (e.g., 2.0 for AAA tier)
        """
        ip = self.get_ip_by_id(ip_id)
        if not ip:
            return 1.0

        value_tier = ip.get("value_tier", "B")
        multipliers = (
            self._config.get("system", {})
            .get("risk_analyzer", {})
            .get("value_tier_multipliers", {})
        )

        return multipliers.get(value_tier, 1.0)

    def generate_search_keywords(self, ip_id: str) -> list[str]:
        """
        Generate search keywords for an IP.

        Args:
            ip_id: IP identifier

        Returns:
            List of search keywords
        """
        ip = self.get_ip_by_id(ip_id)
        if not ip:
            return []

        keywords = []
        characters = ip.get("characters", [])
        ai_tools = [tool.get("name").lower() for tool in self.ai_tools if tool.get("priority") in ["high", "medium"]]

        # Generate keywords: "[character] ai|sora|runway|kling"
        for character in characters[:5]:  # Limit to top 5 characters per IP
            keyword = f"{character.lower()} ai|{'|'.join(ai_tools[:5])}"
            keywords.append(keyword)

        return keywords

    def to_dict(self) -> dict[str, Any]:
        """Get raw config dictionary."""
        return self._config


def load_config(config_path: Path | str | None = None) -> CopycatConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file (defaults to shared_config.yaml in repo root)

    Returns:
        Parsed CopycatConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Expected location: {DEFAULT_CONFIG_PATH}"
        )

    try:
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        logger.info(f"Loaded configuration from {config_path}")
        return CopycatConfig(config_dict)

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config file: {e}")
        raise


# Convenience functions for quick access
def get_all_characters(priority: str | None = None) -> list[str]:
    """Get all character names (convenience function)."""
    config = load_config()
    return config.get_all_characters(priority)


def get_ip_by_id(ip_id: str) -> dict[str, Any] | None:
    """Get IP by ID (convenience function)."""
    config = load_config()
    return config.get_ip_by_id(ip_id)


def get_client_name() -> str:
    """Get client name (convenience function)."""
    config = load_config()
    return config.client_name
