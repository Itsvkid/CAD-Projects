# Parametric Thermal Duct Generator

**Integration of turbofan cycle model with parametric CAD design**

## Overview

Auto-generate thermal ducting from turbofan cycle model outputs. Bridges analysis (your cycle simulator) to hardware design.

### Features

✅ **Cycle Model Integration** — Input: T, P, flow from cycle simulator  
✅ **Duct Diameter Calculation** — Based on flow rate and velocity  
✅ **3D Path Generation** — Centerline curves for complex routing  
✅ **Insulation Thickness** — Parametric heat loss optimization  
✅ **Mounting Brackets** — Auto-positioned for aircraft geometry  

## Aerospace Application

Thermal ducts route:
- Cooling air to bearing cavities (turbine)
- Bypass air around core engine
- Bleed air to environmental control system
- Engine drain air back to atmosphere

**Typical design:**
- Temperature: 300-600 K
- Pressure ratio: 1.0-2.5
- Diameter: 50-300 mm
- Length: 500-2000 mm
- Material: Inconel (hot sections), Aluminum (cold sections)

## Design Philosophy

**Integrate with your existing work:**

```
Turbofan Cycle Model
    ↓ (outlet T, P, flow)
Thermal Duct Generator (this project)
    ↓ (generates 3D geometry)
CAD Model (STEP file)
    ↓
Thermal FEA (validate heat transfer)
```

## Status

**Current:** Design requirements and integration approach documented  
**Next:** Implement duct generation from Bezier curve centerlines

---

See: [[01-Hydraulic-Actuator]] | [[02-Gearbox-Family]] | [[04-DFM-Optimizer]]
