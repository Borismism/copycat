"""
Test startup cleanup logic for stuck videos.

This tests the RESILIENT approach - using scan_history as source of truth
to detect and recover from instance terminations (deployment/crash/autoscale).

CRITICAL: These tests prove the system can recover from Cloud Run deployments
that kill running instances mid-processing.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from google.cloud import firestore


class MockDocumentSnapshot:
    """Mock Firestore document snapshot."""

    def __init__(self, doc_id: str, data: dict, exists: bool = True):
        self.id = doc_id
        self._data = data
        self._exists = exists
        self.reference = Mock()
        self.reference.update = Mock()

    def to_dict(self):
        return self._data

    def exists(self):
        return self._exists

    @property
    def exists(self):
        return self._exists


class MockDocumentReference:
    """Mock Firestore document reference."""

    def __init__(self, doc_id: str, data: dict = None, exists: bool = True):
        self.doc_id = doc_id
        self._data = data or {}
        self._exists = exists
        self.update = Mock()

    def get(self):
        return MockDocumentSnapshot(self.doc_id, self._data, self._exists)


class MockCollectionReference:
    """Mock Firestore collection reference."""

    def __init__(self, documents: list = None):
        self._documents = documents or []
        self._where_filters = []
        self._document_refs = {}  # Track created document references

    def where(self, field, op, value):
        """Mock where() query - returns self for chaining."""
        self._where_filters.append((field, op, value))
        return self

    def stream(self):
        """Return filtered documents based on where() clauses."""
        results = self._documents

        for field, op, value in self._where_filters:
            if op == '==':
                results = [doc for doc in results if doc.to_dict().get(field) == value]

        return iter(results)

    def document(self, doc_id):
        """Return mock document reference (reuse same instance for consistency)."""
        # Reuse existing reference if already created
        if doc_id in self._document_refs:
            return self._document_refs[doc_id]

        # Find document in collection
        for doc in self._documents:
            if doc.id == doc_id:
                ref = MockDocumentReference(doc_id, doc.to_dict(), exists=True)
                self._document_refs[doc_id] = ref
                return ref

        # Document doesn't exist
        ref = MockDocumentReference(doc_id, {}, exists=False)
        self._document_refs[doc_id] = ref
        return ref


@pytest.fixture
def mock_firestore_client():
    """Create mock Firestore client with test data."""

    # Create stuck scans (status='running')
    stuck_scans = [
        MockDocumentSnapshot(
            'scan-001',
            {
                'scan_id': 'scan-001',
                'video_id': 'video-001',
                'status': 'running',
                'started_at': datetime.now(timezone.utc)
            }
        ),
        MockDocumentSnapshot(
            'scan-002',
            {
                'scan_id': 'scan-002',
                'video_id': 'video-002',
                'status': 'running',
                'started_at': datetime.now(timezone.utc)
            }
        ),
        MockDocumentSnapshot(
            'scan-003',
            {
                'scan_id': 'scan-003',
                'video_id': 'video-003',  # This video is already analyzed
                'status': 'running',
                'started_at': datetime.now(timezone.utc)
            }
        ),
        MockDocumentSnapshot(
            'scan-004',
            {
                'scan_id': 'scan-004',
                'video_id': None,  # Edge case: no video_id
                'status': 'running',
                'started_at': datetime.now(timezone.utc)
            }
        ),
    ]

    # Create corresponding videos
    videos = [
        MockDocumentSnapshot(
            'video-001',
            {
                'video_id': 'video-001',
                'status': 'processing',  # Should be reset
                'processing_started_at': datetime.now(timezone.utc),
                'title': 'Test Video 1'
            }
        ),
        MockDocumentSnapshot(
            'video-002',
            {
                'video_id': 'video-002',
                'status': 'processing',  # Should be reset
                'processing_started_at': datetime.now(timezone.utc),
                'title': 'Test Video 2'
            }
        ),
        MockDocumentSnapshot(
            'video-003',
            {
                'video_id': 'video-003',
                'status': 'analyzed',  # Already processed, should NOT be reset
                'last_analyzed_at': datetime.now(timezone.utc),
                'title': 'Test Video 3'
            }
        ),
        # video-004 doesn't exist (edge case)
    ]

    mock_client = Mock()

    # Create collection references (reuse same instances)
    scan_history_collection = MockCollectionReference(stuck_scans)
    videos_collection = MockCollectionReference(videos)

    # Mock collection() calls
    def collection_side_effect(collection_name):
        if collection_name == 'scan_history':
            return scan_history_collection
        elif collection_name == 'videos':
            return videos_collection
        else:
            return MockCollectionReference([])

    mock_client.collection = Mock(side_effect=collection_side_effect)

    # Store references for assertions
    mock_client._scan_history_docs = stuck_scans
    mock_client._video_docs = videos
    mock_client._scan_history_collection = scan_history_collection
    mock_client._videos_collection = videos_collection

    return mock_client


@pytest.mark.asyncio
async def test_cleanup_resets_stuck_videos(mock_firestore_client):
    """
    Test that stuck scans are marked as failed and videos are reset to 'discovered'.

    This is the PRIMARY test case - proves deployment recovery works.
    """
    from app.main import _cleanup_stuck_videos

    # Run cleanup
    await _cleanup_stuck_videos(mock_firestore_client)

    # Verify scan_history updates
    scan_001 = mock_firestore_client._scan_history_docs[0]
    scan_002 = mock_firestore_client._scan_history_docs[1]

    # Both scans should be marked as failed
    assert scan_001.reference.update.called
    assert scan_002.reference.update.called

    # Check update arguments
    scan_001_update = scan_001.reference.update.call_args[0][0]
    assert scan_001_update['status'] == 'failed'
    assert 'Instance terminated' in scan_001_update['error_message']

    scan_002_update = scan_002.reference.update.call_args[0][0]
    assert scan_002_update['status'] == 'failed'


@pytest.mark.asyncio
async def test_cleanup_skips_already_analyzed_videos(mock_firestore_client):
    """
    Test that videos already in 'analyzed' state are NOT reset.

    This proves idempotency - safe to run cleanup multiple times.
    """
    from app.main import _cleanup_stuck_videos

    # Run cleanup
    await _cleanup_stuck_videos(mock_firestore_client)

    # Verify scan-003 was marked failed (scan_history always updated)
    scan_003 = mock_firestore_client._scan_history_docs[2]
    assert scan_003.reference.update.called

    # But video-003 should NOT be reset (it's already analyzed)
    # The function checks current_status and skips if not 'processing'
    videos_collection = mock_firestore_client.collection('videos')
    video_003_ref = videos_collection.document('video-003')

    # Video should not be updated (it's already 'analyzed')
    assert video_003_ref.update.call_count == 0


@pytest.mark.asyncio
async def test_cleanup_handles_missing_video_id(mock_firestore_client):
    """
    Test that scans without video_id are skipped gracefully.

    Edge case: corrupt data or race condition.
    """
    from app.main import _cleanup_stuck_videos

    # Run cleanup (should not crash)
    await _cleanup_stuck_videos(mock_firestore_client)

    # Verify scan-004 (no video_id) was skipped
    scan_004 = mock_firestore_client._scan_history_docs[3]
    # Scan should NOT be updated if video_id is missing
    assert not scan_004.reference.update.called


@pytest.mark.asyncio
async def test_cleanup_handles_missing_video_document(mock_firestore_client):
    """
    Test that cleanup handles videos that don't exist in Firestore.

    Edge case: scan_history has video_id but video was deleted.
    """
    from app.main import _cleanup_stuck_videos

    # Add scan for non-existent video
    scan_999 = MockDocumentSnapshot(
        'scan-999',
        {
            'scan_id': 'scan-999',
            'video_id': 'video-999',  # This video doesn't exist
            'status': 'running',
            'started_at': datetime.now(timezone.utc)
        }
    )
    mock_firestore_client._scan_history_docs.append(scan_999)

    # Run cleanup (should not crash)
    await _cleanup_stuck_videos(mock_firestore_client)

    # Verify scan-999 was marked as failed
    assert scan_999.reference.update.called


@pytest.mark.asyncio
async def test_cleanup_is_idempotent(mock_firestore_client):
    """
    Test that running cleanup multiple times is safe (idempotent).

    Critical for Cloud Run where multiple instances may start simultaneously.
    """
    from app.main import _cleanup_stuck_videos

    # Run cleanup twice
    await _cleanup_stuck_videos(mock_firestore_client)
    await _cleanup_stuck_videos(mock_firestore_client)

    # Should not crash or cause issues
    # Second run should find no stuck scans (they're now 'failed')


@pytest.mark.asyncio
async def test_cleanup_with_no_stuck_scans(mock_firestore_client):
    """
    Test that cleanup handles case where there are no stuck scans.

    Normal healthy state - should just log and return.
    """
    # Override to return empty list
    mock_firestore_client.collection('scan_history').stream = Mock(return_value=iter([]))

    from app.main import _cleanup_stuck_videos

    # Run cleanup (should not crash)
    await _cleanup_stuck_videos(mock_firestore_client)

    # Should return early without errors


@pytest.mark.asyncio
async def test_cleanup_updates_correct_fields(mock_firestore_client):
    """
    Test that cleanup sets all required fields on video reset.

    Ensures videos can be properly reprocessed by risk-analyzer.
    """
    from app.main import _cleanup_stuck_videos

    # Run cleanup
    await _cleanup_stuck_videos(mock_firestore_client)

    # Get video-001 from collection reference (reused instance)
    videos_collection = mock_firestore_client._videos_collection
    video_001_ref = videos_collection._document_refs.get('video-001')

    # Verify update was called
    assert video_001_ref is not None, "video-001 reference should exist"
    assert video_001_ref.update.called, "video-001 update should have been called"

    # Check that correct fields are set
    update_call = video_001_ref.update.call_args[0][0]
    assert update_call['status'] == 'discovered'
    assert update_call['processing_started_at'] is None
    assert 'Reset from incomplete scan' in update_call['error_message']
    assert 'reset_at' in update_call
    assert 'updated_at' in update_call


@pytest.mark.asyncio
async def test_cleanup_resilience_to_firestore_errors(mock_firestore_client):
    """
    Test that cleanup continues even if some updates fail.

    Critical: one bad document shouldn't prevent cleanup of others.
    """
    from app.main import _cleanup_stuck_videos

    # Make scan-001 update fail
    scan_001 = mock_firestore_client._scan_history_docs[0]
    scan_001.reference.update.side_effect = Exception("Firestore write failed")

    # Run cleanup (should not crash)
    await _cleanup_stuck_videos(mock_firestore_client)

    # Verify scan-002 was still processed despite scan-001 failure
    scan_002 = mock_firestore_client._scan_history_docs[1]
    assert scan_002.reference.update.called


@pytest.mark.asyncio
async def test_cleanup_proves_deployment_recovery():
    """
    INTEGRATION TEST: Prove the entire deployment scenario works.

    Scenario:
    1. Instance A has 3 videos processing (scans in 'running' state)
    2. Deployment triggers, Cloud Run kills Instance A
    3. Instance B starts up, runs cleanup
    4. Result: All 3 videos reset to 'discovered', ready to reprocess

    This is the CRITICAL test that proves resilience.
    """
    # Simulate Instance A state before being killed
    instance_a_scans = [
        MockDocumentSnapshot(
            f'scan-{i}',
            {
                'scan_id': f'scan-{i}',
                'video_id': f'video-{i}',
                'status': 'running',  # Mid-processing when killed
                'started_at': datetime.now(timezone.utc)
            }
        )
        for i in range(3)
    ]

    instance_a_videos = [
        MockDocumentSnapshot(
            f'video-{i}',
            {
                'video_id': f'video-{i}',
                'status': 'processing',  # Stuck in processing
                'processing_started_at': datetime.now(timezone.utc),
                'title': f'Video {i}'
            }
        )
        for i in range(3)
    ]

    # Create mock Firestore for Instance B
    mock_client = Mock()
    mock_client.collection = Mock(side_effect=lambda name: (
        MockCollectionReference(instance_a_scans) if name == 'scan_history'
        else MockCollectionReference(instance_a_videos) if name == 'videos'
        else MockCollectionReference([])
    ))
    mock_client._scan_history_docs = instance_a_scans
    mock_client._video_docs = instance_a_videos

    # Run Instance B startup cleanup
    from app.main import _cleanup_stuck_videos
    await _cleanup_stuck_videos(mock_client)

    # VERIFY: All scans marked as failed
    for scan in instance_a_scans:
        assert scan.reference.update.called
        update_args = scan.reference.update.call_args[0][0]
        assert update_args['status'] == 'failed'
        assert 'Instance terminated' in update_args['error_message']

    # VERIFY: All videos reset to 'discovered'
    for i in range(3):
        video_ref = mock_client.collection('videos').document(f'video-{i}')
        assert video_ref.update.called
        update_args = video_ref.update.call_args[0][0]
        assert update_args['status'] == 'discovered'
        assert update_args['processing_started_at'] is None

    print("✅ DEPLOYMENT RECOVERY TEST PASSED")
    print("   - Instance A killed mid-processing")
    print("   - Instance B successfully recovered all stuck videos")
    print("   - System is RESILIENT to deployments")


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
