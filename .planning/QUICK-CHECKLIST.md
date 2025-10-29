# Quick Checklist - Before Marking Story as DONE

**Print this and keep it visible while coding.**

---

## ✅ Story Complete Checklist

### 1. Code Quality (5 min)
```bash
cd services/discovery-service
uv run ruff check app/
uv run ruff format app/
```
- [ ] Zero ruff warnings
- [ ] Type hints on ALL functions
- [ ] Docstrings on ALL public methods
- [ ] No code duplication found
- [ ] No commented-out code
- [ ] No debug print statements
- [ ] Proper logging levels used

### 2. Testing (15 min)
```bash
uv run pytest -v
uv run pytest --cov=app --cov-report=term-missing
```
- [ ] All tests pass
- [ ] Coverage ≥80%
- [ ] Edge cases tested
- [ ] Error conditions tested
- [ ] Integration tests pass

### 3. Local Verification (10 min)
```bash
./scripts/dev-local.sh discovery-service
curl http://localhost:8080/health
```
- [ ] Service starts without errors
- [ ] Health check returns 200
- [ ] Can process test request
- [ ] Firestore emulator shows data
- [ ] PubSub emulator receives messages

### 4. GCP Deployment (15 min)
```bash
./scripts/deploy-service.sh discovery-service dev
```
- [ ] Build succeeds
- [ ] Terraform apply succeeds
- [ ] Service deploys successfully
- [ ] Health check passes in Cloud Run
- [ ] No errors in Cloud Logging

### 5. Production Verification (10 min)
```bash
# Get service URL
gcloud run services describe discovery-service --region=us-central1 --format='value(status.url)'

# Test endpoint
curl $SERVICE_URL/health

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=discovery-service AND severity>=ERROR" --limit 20
```
- [ ] API responds correctly
- [ ] Firestore operations work
- [ ] PubSub messages published
- [ ] Zero errors in logs (10 min monitoring)

### 6. Documentation (5 min)
- [ ] Inline comments for complex logic
- [ ] API docs updated (OpenAPI)
- [ ] CLAUDE.md updated (if needed)

---

## ❌ Common Failures - Fix Immediately

### Ruff Errors
```bash
# Fix imports
uv run ruff check --select I --fix

# Format code
uv run ruff format .
```

### Test Failures
```bash
# Run single test
uv run pytest tests/test_video_processor.py::test_name -v

# Debug test
uv run pytest tests/test_video_processor.py::test_name -v -s
```

### Low Coverage
```bash
# See missing lines
uv run pytest --cov=app.core.video_processor --cov-report=term-missing

# Open HTML report
uv run pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### Deployment Fails
```bash
# Check build logs
gcloud builds list --limit=5

# View build details
gcloud builds log [BUILD_ID]

# Check service logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50
```

---

## 🚀 Story DONE Criteria (Must ALL Pass)

- [ ] Ruff: ✅ PASS
- [ ] Tests: ✅ ALL PASS
- [ ] Coverage: ✅ ≥80%
- [ ] Local: ✅ WORKS
- [ ] Deploy: ✅ SUCCESS
- [ ] Health: ✅ 200 OK
- [ ] Logs: ✅ NO ERRORS
- [ ] Docs: ✅ UPDATED

**If ANY checkbox is empty, story is NOT done.**

---

## 🎯 Daily Workflow

### Morning (Start of Day)
1. Pull latest code: `git pull origin main`
2. Sync dependencies: `uv sync`
3. Run tests: `./scripts/test-service.sh discovery-service`
4. Pick next story from epic

### During Development (Per Method)
1. Write skeleton with types/docstrings
2. Implement method
3. Write tests immediately
4. Run tests: `uv run pytest -v`
5. Commit: `git commit -m "feat: implement X"`

### Before Lunch/End of Day
1. Run full test suite
2. Check coverage
3. Run ruff
4. Push code: `git push`

### End of Story
1. Complete this checklist
2. Deploy to dev
3. Monitor for 10 minutes
4. Mark story as DONE
5. Update epic progress

---

## 💡 Quality Mantras

**"If tests are hard, code is bad."**
→ Rewrite code to be testable

**"If you can't explain it, you don't understand it."**
→ Write docstrings before implementation

**"Duplication is debt."**
→ Extract shared logic immediately

**"Works on my machine" is not done.**
→ Must work on GCP Cloud Run

**"Good enough" is not good enough.**
→ Code must be fantastic

---

## 📊 Story Velocity Tracking

Track completion time to estimate future stories:

```
Story 1.1: VideoProcessor
- Estimated: 5 points
- Actual: 6 hours
- Ratio: 1.2 hours/point

Story 1.2: QuotaManager
- Estimated: 3 points
- Actual: 4 hours
- Ratio: 1.33 hours/point

Story 2.1: ChannelTracker
- Estimated: 8 points
- Actual: ? hours
- Ratio: ? hours/point
```

Average: ~1.5 hours per story point (typical)

Sprint capacity: 40 hours = ~26 story points

---

## 🔥 Zero Tolerance Rules

These will cause IMMEDIATE story rejection:

1. **No type hints** → REJECTED
2. **No tests** → REJECTED
3. **Coverage <80%** → REJECTED
4. **Ruff warnings** → REJECTED
5. **Duplicated code** → REJECTED
6. **Doesn't deploy** → REJECTED
7. **Errors in logs** → REJECTED
8. **No docstrings** → REJECTED
9. **Magic numbers** → REJECTED
10. **Commented code** → REJECTED

**Fix these BEFORE requesting review.**

---

## 📞 When You're Stuck

### Tests Won't Pass
1. Read error message carefully
2. Add `print()` statements to debug
3. Run single test with `-v -s` flags
4. Check test fixtures are set up correctly
5. Verify mocks return expected data

### Coverage Too Low
1. Run with `--cov-report=html`
2. Open HTML report in browser
3. Find red (uncovered) lines
4. Write tests for those paths
5. Focus on error conditions

### Deploy Fails
1. Check Cloud Build logs
2. Verify Dockerfile syntax
3. Check environment variables
4. Verify service account permissions
5. Test build locally: `docker build .`

### Firestore Errors
1. Check IAM roles on service account
2. Verify collection names match
3. Check document ID format
4. Test with Firestore emulator first
5. Check quota limits in GCP Console

### Need Help
1. Read IMPLEMENTATION-STANDARDS.md
2. Look at existing working code
3. Check CLAUDE.md for architecture
4. Review similar completed stories
5. Ask for code review

---

## ✨ Before Pushing Code

Final 60-second review:

1. **Read every changed line** (2x)
2. **Run tests** one more time
3. **Check for TODOs** (resolve or create ticket)
4. **Verify no secrets** in code
5. **Write clear commit message**

```bash
# Good commit message
git commit -m "feat(discovery): add VideoProcessor for zero-duplication video handling

- Eliminates 300+ lines of duplicate code
- Single source of truth for video operations
- 92% test coverage
- All edge cases handled

Closes #123"
```

---

**Keep this checklist visible. Check EVERY box EVERY time.**

**Fantastic code is a habit, not an accident.** 🚀
