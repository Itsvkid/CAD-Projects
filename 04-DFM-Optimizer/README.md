# Design for Manufacturability (DFM) Optimizer

**Automated design checks and optimization for aerospace manufacturing**

## Overview

Script that analyzes CAD models and suggests manufacturing improvements. Reduces production cost and lead time automatically.

### Features

✅ **Wall Thickness Check** — Flag thin walls (risk of warping/failure)  
✅ **Bend Radius Validation** — Sheet metal design rules  
✅ **Draft Angle Detection** — For casting/molding ejection  
✅ **Feature Accessibility** — Can drill/mill reach this hole?  
✅ **Cost Estimation** — Material + machining hours  
✅ **Lead Time Prediction** — Supplier availability based on geometry  

## Aerospace Application

DFM rules prevent expensive manufacturing surprises:
- Thin wall (< 2 mm) = warping in aluminum
- Insufficient bend radius = material cracking in sheet metal
- Negative draft angle = can't eject from mold (casting)
- Inaccessible hole = requires custom tooling ($ + time)
- Complex geometry = manual work vs. CNC (10× cost difference)

**Cost impact:**
- Poor DFM: $5,000 per part (custom tooling, hand-finishing)
- Good DFM: $500 per part (standard CNC, no surprises)

## Design Workflow

```
CAD Model
    ↓
DFM Optimizer (this project)
    ↓
Generate Report:
  - ✓ PASS / ✗ FAIL checks
  - Cost estimate
  - Lead time
  - Recommendations
    ↓
Revise Design
    ↓
Re-analyze (iterate until optimized)
    ↓
Production-ready design
```

## Status

**Current:** DFM rules documented and validation framework designed  
**Next:** Implement STEP file parser and rule engine

## Integration

Works with outputs from:
- [[01-Hydraulic-Actuator]] — Check cylinder wall thickness, seal groove dimensions
- [[02-Gearbox-Family]] — Optimize housing ribs, bearing pocket depth
- [[03-Thermal-Duct]] — Validate duct bend radius, insulation application

---

See: [[01-Hydraulic-Actuator]] | [[02-Gearbox-Family]] | [[03-Thermal-Duct]]
