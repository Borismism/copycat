# ==============================================================================
# LOCAL VALUES - Source code hashing
# ==============================================================================

locals {
  # Watch all source files in app folder (Python backend + React frontend)
  app_dir       = "${path.module}/../app"

  # Exclude: dependencies, build outputs, caches, OS files
  exclude_regex = "(\\.venv/|__pycache__/|\\.git/|\\.DS_Store|Thumbs\\.db|desktop\\.ini|\\._.*|~$|\\.pyc$|\\.pytest_cache/|\\.ruff_cache/|node_modules/|\\.vite/|dist/|build/|coverage/|\\.turbo/|\\.next/|public/)"

  all_app_files = fileset(local.app_dir, "**/*")
  app_files = toset([
    for f in local.all_app_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  # Hash of app source files - triggers Cloud Run update when source code changes
  # Includes: Python backend (main.py), React source (web/src/), config files
  # Excludes: node_modules, build outputs, caches (prevents inconsistent plans)
  app_source_hash = sha256(join("", [
    for f in sort(local.app_files) : filesha256("${local.app_dir}/${f}")
  ]))
}
