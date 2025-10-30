"""Dependency injection for FastAPI routes."""

from google.cloud import firestore, pubsub_v1

from .config import settings
from .core.risk_analyzer import RiskAnalyzer

# Singleton instances
_firestore_client = None
_pubsub_subscriber = None
_risk_analyzer = None


def get_firestore_client() -> firestore.Client:
    """Get Firestore client (singleton)."""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(
            project=settings.gcp_project_id,
            database="(default)",
        )
    return _firestore_client


def get_pubsub_subscriber() -> pubsub_v1.SubscriberClient:
    """Get PubSub subscriber client (singleton)."""
    global _pubsub_subscriber
    if _pubsub_subscriber is None:
        _pubsub_subscriber = pubsub_v1.SubscriberClient()
    return _pubsub_subscriber


def get_risk_analyzer() -> RiskAnalyzer:
    """Get RiskAnalyzer instance (singleton)."""
    global _risk_analyzer
    if _risk_analyzer is None:
        _risk_analyzer = RiskAnalyzer(
            firestore_client=get_firestore_client(),
            pubsub_subscriber=get_pubsub_subscriber(),
        )
    return _risk_analyzer
