#!/usr/bin/env python3
"""Reset a stuck video in Firestore."""

from google.cloud import firestore
import sys

# Video ID to reset
video_id = sys.argv[1] if len(sys.argv) > 1 else 'NmS3KtHfixA'

# Connect to Firestore emulator
db = firestore.Client(project='copycat-local', database='(default)')

# Update video status
doc_ref = db.collection('videos').document(video_id)
doc_ref.update({
    'status': 'failed',
    'error': 'Stuck in processing for too long - manually reset'
})

print(f"✅ Updated video {video_id} status to 'failed'")
