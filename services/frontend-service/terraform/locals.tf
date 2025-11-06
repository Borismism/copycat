# ==============================================================================
# LOCAL VALUES - Source code hashing and computed values
# ==============================================================================

locals {
  # Watch both app and web folders for source code changes (includes React app)
  source_dir    = "${path.module}/.."
  exclude_regex = "(\\.venv/|node_modules/|__pycache__/|\\.git/|dist/|\\.DS_Store|Thumbs\\.db|desktop\\.ini|\\._.*|~$|\\.pyc$|\\.pytest_cache/|\\.ruff_cache/)"

  all_files = fileset(local.source_dir, "**/*")
  source_files = toset([
    for f in local.all_files : f
    if length(regexall(local.exclude_regex, f)) == 0
  ])

  # Hash of source files - triggers Cloud Run update when code changes
  source_code_hash = sha256(join("", [
    for f in sort(local.source_files) : filesha256("${local.source_dir}/${f}")
  ]))
}
