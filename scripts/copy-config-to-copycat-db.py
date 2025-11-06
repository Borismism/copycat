"""Copy ip_configs from default database to copycat database."""

from google.cloud import firestore

project = "irdeto-copycat-internal-dev"

# Connect to both databases
default_db = firestore.Client(project=project, database="(default)")
copycat_db = firestore.Client(project=project, database="copycat")

print("=== Copying ip_configs from default to copycat database ===\n")

# Get all configs from default
configs = list(default_db.collection("ip_configs").stream())
print(f"Found {len(configs)} configs in DEFAULT database")

if not configs:
    print("No configs to copy!")
    exit(0)

# Copy each config
for doc in configs:
    data = doc.to_dict()
    config_id = doc.id

    print(f"\nCopying config: {config_id}")
    print(f"  Name: {data.get('name')}")
    print(f"  Search keywords: {len(data.get('search_keywords', []))} keywords")

    # Write to copycat database with same document ID
    copycat_db.collection("ip_configs").document(config_id).set(data)
    print(f"  ✅ Copied to copycat database")

print(f"\n✅ Successfully copied {len(configs)} configs to copycat database")

# Verify
copycat_configs = list(copycat_db.collection("ip_configs").stream())
print(f"\nVerification: copycat database now has {len(copycat_configs)} configs")
