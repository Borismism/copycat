# Risk System Redesign - IMPLEMENTED

## Summary

Redesigned the risk scoring system with a clear two-phase model:

1. **Pre-scan (SCAN PRIORITY)**: Should we scan this video?
2. **Post-scan (INFRINGEMENT RISK)**: How bad is this confirmed infringement?

Key insight: **Clean videos get risk = 0. Period.**

---

## New Model

```
Video discovered
      │
      ▼
┌─────────────────────────────┐
│ SCAN PRIORITY (0-100)       │
│ 4 factors:                  │
│ - IP match (0-40)           │
│ - Channel history (0-30)    │
│ - AI tool detected (0-20)   │
│ - Recency (0-10)            │
└─────────────────────────────┘
      │
      ▼
   Gemini scans
      │
      ├─── NO INFRINGEMENT ───► infringement_risk = 0
      │                         risk_tier = "CLEAR"
      │                         Done.
      │
      └─── INFRINGEMENT ───────► Calculate damage score
                                 │
                                 ▼
                         ┌─────────────────────────────┐
                         │ INFRINGEMENT RISK (0-100)   │
                         │ 6 factors:                  │
                         │ - View count (0-25)         │
                         │ - View velocity (0-25)      │
                         │ - Channel reach (0-20)      │
                         │ - Content severity (0-15)   │
                         │ - Duration (0-10)           │
                         │ - Engagement (0-5)          │
                         └─────────────────────────────┘
```

---

## Channel Risk

Channel risk = infringement % + absolute count + reach (only if infringing)

**Key insight**: Reach only matters if channel has infringements.
- 1M sub channel, 0 infringements = LOW risk
- 1k sub channel, 50% infringement = MEDIUM risk
- 1M sub channel, 50% infringement = HIGH risk

### Scoring (0-100):
- Infringement rate: 0-50 pts
- Absolute volume: 0-30 pts
- Reach: 0-20 pts (only if confirmed > 0)

---

## Files Changed

### New:
- `app/core/infringement_risk_calculator.py` - Post-scan damage scoring

### Modified:
- `app/core/channel_risk_calculator.py` - Simplified to rate + volume + reach
- `app/core/scan_priority_calculator.py` - Simplified to 4 factors
- `app/core/risk_analyzer.py` - Uses new model
- `app/models.py` - New enums and field names

### Deleted:
- `app/core/risk_rescorer.py` - Redundant, confusing
- `app/core/video_risk_calculator.py` - Replaced by infringement_risk_calculator
- `tests/test_risk_rescorer.py` - Test for deleted code

---

## Video Fields

| Field | When Set | Meaning |
|-------|----------|---------|
| `scan_priority` | Discovery | 0-100, higher = scan first |
| `priority_tier` | Discovery | SCAN_NOW/SCAN_SOON/SCAN_LATER/SKIP |
| `infringement_risk` | After scan | 0 if clean, 0-100 if infringement |
| `risk_tier` | After scan | CLEAR/MINIMAL/LOW/MEDIUM/HIGH/CRITICAL |
| `channel_risk` | Discovery + updates | Channel's infringement history |

---

## Priority Tiers

### Scan Priority (pre-scan):
- 70-100: **SCAN_NOW** - Queue immediately
- 40-69: **SCAN_SOON** - Normal queue
- 20-39: **SCAN_LATER** - Low priority
- 0-19: **SKIP** - Don't waste Gemini budget

### Risk Tiers (post-scan, infringements only):
- 80-100: **CRITICAL** - Immediate takedown
- 60-79: **HIGH** - Same-day action
- 40-59: **MEDIUM** - This week
- 20-39: **LOW** - Monitor
- 1-19: **MINIMAL** - Log only
- 0: **CLEAR** - No infringement
