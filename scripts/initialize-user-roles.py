#!/usr/bin/env python3
"""Initialize default user role assignments in Firestore."""

import asyncio
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, "/Users/boris/copycat/services/api-service")

from google.cloud import firestore

from app.core.config import settings


async def initialize_roles():
    """Initialize default role assignments."""
    # Initialize Firestore client
    if settings.firestore_emulator_host:
        # Local development with emulator
        db = firestore.Client(
            project=settings.gcp_project_id,
            database="(default)",  # Emulator uses default database
        )
        print(f"✅ Connected to Firestore emulator at {settings.firestore_emulator_host}")
    else:
        # Production
        db = firestore.Client(
            project=settings.gcp_project_id,
            database=settings.firestore_database,
        )
        print(f"✅ Connected to Firestore: {settings.gcp_project_id}/{settings.firestore_database}")

    role_collection = db.collection("user_roles")

    # Default role assignments
    default_roles = [
        {
            "email": "boris@nextnovate.com",
            "role": "admin",
            "assigned_by": "system",
            "assigned_at": datetime.now(timezone.utc),
            "notes": "System administrator (initial setup)",
        },
        {
            "domain": "nextnovate.com",
            "role": "editor",
            "assigned_by": "system",
            "assigned_at": datetime.now(timezone.utc),
            "notes": "Default editor access for Nextnovate domain",
        },
    ]

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for assignment in default_roles:
        # Create document ID
        if "email" in assignment:
            identifier = assignment["email"]
            doc_id = identifier.replace("@", "_at_").replace(".", "_")
        else:
            identifier = assignment["domain"]
            doc_id = identifier.replace(".", "_")

        # Check if already exists
        doc_ref = role_collection.document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            existing_data = doc.to_dict()
            # Update if role changed
            if existing_data.get("role") != assignment["role"]:
                doc_ref.set(assignment)
                print(f"✏️  Updated: {identifier} → {assignment['role']}")
                updated_count += 1
            else:
                print(f"⏭️  Skipped: {identifier} (already exists with role {assignment['role']})")
                skipped_count += 1
        else:
            # Create new assignment
            doc_ref.set(assignment)
            print(f"➕ Created: {identifier} → {assignment['role']}")
            created_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Initialization complete!")
    print(f"   - Created: {created_count}")
    print(f"   - Updated: {updated_count}")
    print(f"   - Skipped: {skipped_count}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(initialize_roles())
