#!/usr/bin/env python3
"""
Mock video scan - directly updates Firestore without Gemini or PubSub.
Tests the frontend display of scan results.
"""

import os
import sys
from datetime import datetime
from google.cloud import firestore

# Set environment for emulator
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8200"
os.environ["GCP_PROJECT_ID"] = "copycat-local"

def mock_scan_video(video_id: str):
    """Create a mock vision analysis result for a video."""

    print(f"🧪 Mock scanning video: {video_id}")

    # Initialize Firestore client
    client = firestore.Client(project="copycat-local")

    # Get video document
    doc_ref = client.collection("videos").document(video_id)
    doc = doc_ref.get()

    if not doc.exists:
        print(f"❌ Video {video_id} not found in Firestore")
        sys.exit(1)

    video_data = doc.to_dict()
    print(f"✅ Found video: {video_data.get('title', 'Unknown')}")

    # Create mock analysis result
    mock_result = {
        "vision_analysis": {
            "analyzed_at": datetime.now(),
            "gemini_model": "gemini-2.5-flash (MOCK)",
            "contains_infringement": True,
            "confidence_score": 85,
            "infringement_type": "ai_clips",
            "characters_detected": [
                {
                    "name": "Superman",
                    "screen_time_seconds": 5,
                    "prominence": "primary",
                }
            ],
            "recommended_action": "monitor",
            "cost_usd": 0.0082,
            "processing_time_seconds": 2.5,
            "full_analysis": {
                "contains_infringement": True,
                "confidence_score": 85,
                "infringement_type": "ai_clips",
                "ai_generated": {
                    "is_ai": True,
                    "confidence": 90,
                    "tools_detected": ["Sora AI"],
                    "evidence": "MOCK: Detected AI-generated artifacts"
                },
                "characters_detected": [
                    {
                        "name": "Superman",
                        "screen_time_seconds": 5,
                        "prominence": "primary",
                        "timestamps": ["0:00-0:05"],
                        "description": "MOCK: Superman in classic costume"
                    }
                ],
                "copyright_assessment": {
                    "infringement_likelihood": 85,
                    "reasoning": "MOCK ANALYSIS - This is test data for frontend display",
                    "fair_use_applies": False,
                    "fair_use_factors": {
                        "purpose": "commercial",
                        "nature": "creative_work",
                        "amount_used": "substantial",
                        "market_effect": "medium"
                    }
                },
                "video_characteristics": {
                    "duration_category": "short",
                    "content_type": "clips",
                    "monetization_detected": False,
                    "professional_quality": False
                },
                "recommended_action": "monitor",
                "legal_notes": "MOCK TEST DATA - Not a real Gemini analysis"
            }
        },
        "scan_status": "analyzed",
        "last_analyzed_at": datetime.now(),
        "analysis_cost_usd": 0.0082,
    }

    # Update Firestore
    print(f"💾 Updating Firestore...")
    doc_ref.update(mock_result)

    print(f"""
✅ Mock scan complete!

Video: {video_id}
Status: analyzed
Infringement: True
Confidence: 85%
Characters: Superman (5s)
Cost: $0.0082

Frontend should now show:
- Green "Analyzed" button (disabled)
- Checkmark icon
- Video status: analyzed
    """)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mock-scan-test.py VIDEO_ID")
        print("\nExample:")
        print("  python mock-scan-test.py QfPpbhsDnWg")
        sys.exit(1)

    video_id = sys.argv[1]
    mock_scan_video(video_id)
