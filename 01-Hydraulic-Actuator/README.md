# Parametric Hydraulic Actuator Generator

**Programmatic CAD design for aircraft flight control actuators using Python & CadQuery**

## Overview

This project generates 3D CAD models for aircraft hydraulic flight control actuators programmatically. Instead of manual CAD clicking, you write Python to generate parametric designs.

### Key Features

✅ **Parametric Design** — Change bore/rod/stroke dimensions, entire model updates  
✅ **Automated Export** — Generate STEP files for any CAD software (SOLIDWORKS, CATIA, Fusion 360)  
✅ **Bill of Materials** — Auto-generate component list with mass calculations  
✅ **Family Scaling** — One script generates actuators for Cessna → B777 aircraft  
✅ **Aerospace Standards** — SAE hydraulic port sizing, seal groove dimensions  
✅ **Open Source** — Python + CadQuery (free, no expensive CAD licenses)

## Project Structure

```
01-Hydraulic-Actuator/
├── hydraulic_actuator.py          # Main CAD generator (Python)
├── requirements.txt                # Python dependencies (cadquery)
├── README.md                       # This file
├── BOM.json                        # Generated bill of materials
└── output/
    ├── hydraulic_actuator_b737.step
    ├── hydraulic_actuator_family/
    │   ├── small_aircraft.step
    │   ├── regional_turboprop.step
    │   ├── narrow_body.step
    │   └── wide_body.step
    └── parts/
        ├── 01_cylinder_body.step
        ├── 02_piston_rod.step
        └── 03_clevis_end.step
```

## Aerospace Applications

Hydraulic actuators are used for:

| System | Aircraft | Actuators |
|--------|----------|-----------|
| **Pitch Control** | All | Elevator actuators (2-4) |
| **Roll Control** | All | Aileron actuators (4-8) |
| **Yaw Control** | All | Rudder actuators (2-4) |
| **Landing Gear** | All | Extension/retraction (3+) |
| **Thrust Reversers** | Commercial | Reverser door actuators |
| **Flight Surfaces** | Military | Canard, flap, speed brake actuators |

**Typical Performance:**
- Pressure: 3000 PSI (210 bar)
- Flow: 2-10 GPM (7.5-38 L/min)
- Force Output: 15-50 kN
- Speed: 2-10 cm/s
- Response Time: 50-500 ms

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**What gets installed:**
- `cadquery` — Parametric CAD library for Python

### 2. Verify Installation

```bash
python -c "import cadquery; print(f'CadQuery version: {cadquery.__version__}')"
```

## Usage

### Generate B737-Class Actuator

```bash
python hydraulic_actuator.py
```

**Output:**
- `hydraulic_actuator_b737.step` — Full assembly (import into SOLIDWORKS/CATIA)
- `parts/` folder — Individual components
- `BOM.json` — Bill of materials with mass calculations

### Generate Custom Actuator

```python
from hydraulic_actuator import HydraulicActuator

# Create actuator with custom dimensions
actuator = HydraulicActuator(
    bore_diameter_mm=40,      # Larger bore = more force
    rod_diameter_mm=24,       # ~60% of bore (typical)
    stroke_length_mm=220      # Longer stroke = larger deflection
)

# Display specs
print(actuator.get_specs())

# Export as STEP file
actuator.export_step("my_custom_actuator.step")

# Generate BOM
actuator.save_bom("my_custom_BOM.json")
```

### Generate Family of Actuators

```bash
python hydraulic_actuator.py
```

Creates actuators for:
- Small Aircraft (Cessna-class) — 16 mm bore
- Regional Turboprop (Q400-class) — 25 mm bore
- Narrow-body (B737-class) — 35 mm bore
- Wide-body (B777-class) — 50 mm bore

**This is parametric design in action:**
- One Python script
- 4 aircraft sizes
- 4 STEP files automatically generated

## Design Details

### Cylinder Body

- Material: Aluminum 6061-T6 (lightweight, corrosion-resistant)
- OD = bore + 2×wall thickness
- Wall thickness: 3 mm (typical)
- Internal bore: precision ground (±0.05 mm)
- End caps: 25 mm thickness (standard)

### Piston Rod

- Material: Steel 4340 (hard chrome plated)
- Typical rod/bore ratio: 0.6 (reduces weight, maintains strength)
- Seal grooves: 4 mm wide × 1.5 mm deep
- Surface finish: Polished (Ra 0.2 µm for sealing)

### Clevis End

- Material: Steel 4340 (or ductile iron for larger sizes)
- Mounting holes: M8 bolts (typical, 2 holes)
- Attachment: Bolted or pinned to control surface
- Load path: Direct from rod through clevis to aircraft structure

### Hydraulic Ports

- Ports A & B: SAE ORB (O-ring boss) fittings
- Port diameter: 8 mm (M10 SAE standard)
- Port A: Cap-end pressure (high pressure)
- Port B: Rod-end return (low pressure)
- Typical pressures:
  - System pressure: 3000 PSI (210 bar)
  - Pilot pressure: 1500 PSI (105 bar)
  - Return pressure: 150 PSI (10 bar)

## Parametric Scaling Example

How dimensions scale with aircraft size:

```python
# B737 (narrow-body, 150 passengers)
b737 = HydraulicActuator(bore=35, rod=21, stroke=200)

# B777 (wide-body, 350+ passengers)
b777 = HydraulicActuator(bore=50, rod=30, stroke=250)

# Ratio: B777/B737
bore_ratio = 50/35  # 1.43× larger (more lift = more control force needed)
rod_ratio = 30/21   # 1.43× larger
stroke_ratio = 250/200  # 1.25× longer
```

**Insight:** Larger aircraft need more powerful actuators, but scaling is non-linear.

## Technical Specifications

### Performance Calculations

The script auto-calculates:

| Calculation | Formula | Example (35mm bore, 210 bar) |
|---|---|---|
| **Piston Area** | A = π(d/2)² | 961 mm² |
| **Force Output** | F = P × A | 20.2 kN |
| **Speed (5 GPM)** | v = Q / A | 5.3 cm/s |
| **Power Output** | W = F × v | 1.07 kW |
| **Cylinder Mass** | ρ_Al = 2.7 g/cm³ × OCC solid volume | 0.307 kg |
| **Rod Mass** | ρ_Steel = 7.85 g/cm³ × OCC solid volume | 0.542 kg |
| **Clevis Mass** | ρ_Steel = 7.85 g/cm³ × OCC solid volume | 0.148 kg |

### Seal Specifications

Standard seals for aircraft actuators:

| Seal Type | Material | Location | Function |
|-----------|----------|----------|----------|
| Rod Seal | PTFE (Teflon) | Rod groove | Prevents internal leakage |
| Piston Seal | PTFE/elastomer | Piston groove | Separates A/B ports |
| Rod Wiper | Polyurethane | Rod end | Keeps out contaminants |
| Gland Seal | PTFE | Port connection | Prevents external leakage |

## Importing into CAD Software

### SOLIDWORKS

1. File → Open → select `.step` file
2. Exploded view: Edit assembly → drag components apart
3. Drawing: Insert → Drawing from Part
4. Detailed drawings typically show tolerance stack-up

### CATIA V5

1. File → Open → select `.step` file
2. Update Geometry: necessary if part origins differ
3. Assembly constraints: Define mates (concentric, coincident, etc.)

### Fusion 360

1. File → Open → select `.step` file
2. Modify design: Edit feature history if needed
3. Rendering: Make physical properties match (aluminum/steel colors)

## Extending the Project

### Add Cushioning (Snubber)

Aircraft actuators often include cushioning to slow down near end of stroke:

```python
def add_cushioning(self):
    """Add needle valve cushioning at rod end."""
    # Creates metered orifice for smooth deceleration
    cushion_port = ...
```

### Add Pilot-Operated Check Valves

Directional control with load-holding:

```python
def add_check_valves(self):
    """Add pressure-relief and pilot-operated checks."""
    # Prevents float and uncontrolled extension
```

### Dynamic Simulation

Connect to your turbofan cycle model:

```python
from turbofan_cycle_model import calculate_control_surface_forces

# Get flight condition
altitude = 35000  # ft
mach = 0.82
angle_of_attack = 5  # degrees

# Calculate needed actuator force
force_needed = calculate_control_surface_forces(altitude, mach, angle_of_attack)

# Size actuator to provide 1.5× that force (safety factor)
bore = calculate_bore_from_force(force_needed * 1.5)

actuator = HydraulicActuator(bore_diameter_mm=bore, ...)
```

## Design Validation

### Manufacturing Feasibility Checks

1. **Wall Thickness** ≥ 2.5 mm (prevent buckling)
2. **Seal Grooves** within standard dimensions (supplier parts available)
3. **Port Locations** accessible for installation
4. **Clevis Geometry** manufactureable (no undercuts unless EDM capable)

### Pressure/Stress Analysis

For detailed analysis, export to ABAQUS/ANSYS:

```python
# Export to mesh-ready format
actuator.create_cylinder_body().save("cylinder_for_fea.step")
```

Then run FEA to verify:
- Hoop stress < 0.5×yield (safety factor 2)
- Buckling analysis for rod (slenderness ratio)
- Fatigue analysis (10+ million cycles typical)

## Performance Metrics

### Typical Actuator Specifications

Masses are the sum of the three modelled solids' real OCC volumes times
their material densities — not an estimate. They exclude seals, ports,
fasteners and fluid, so they are a dry structural mass, not an installed
one.

| Class | Bore × Rod × Stroke | Force @ 210 bar | Mass |
|---|---|---|---|
| Small aircraft (Cessna 172) | 16 × 10 × 100 | 4.2 kN | 0.250 kg |
| Regional turboprop (Q400) | 25 × 15 × 150 | 10.3 kN | 0.506 kg |
| Narrow-body (B737-800) | 35 × 21 × 200 | 20.2 kN | 0.997 kg |
| Wide-body (B777-300ER) | 50 × 30 × 250 | 41.2 kN | 2.108 kg |

**No cost estimates.** An earlier version of this table carried unit costs
($200–300 up to $3,000–5,000). They had no source — no supplier quote, no
cost model, nothing but plausibility — and publishing invented numbers next
to computed ones invites a reader to trust both equally. Project 02 states
the same policy for the same reason.

## Files Generated

### STEP Files (CAD Import)

- `hydraulic_actuator_b737.step` — Full assembly (SOLIDWORKS/CATIA compatible)
- `actuator_small_aircraft.step` — Family variant 1
- `actuator_regional_turboprop.step` — Family variant 2
- `parts/01_cylinder_body.step` — Individual cylinder
- `parts/02_piston_rod.step` — Individual rod
- `parts/03_clevis_end.step` — Individual clevis

### Metadata Files

- `BOM.json` — Bill of materials (parts, materials, masses)
- `specifications.txt` — Technical specs (force, speed, pressure)

## Figures

`../render.py` builds these from this same generator — tessellated on the
OpenCASCADE kernel and rendered offscreen through VTK, so no CAD GUI,
browser or screenshot is involved:

```bash
python ../render.py actuator
```

- `figures/actuator-family.png` — all four aircraft classes in one scene
  at true relative scale.
- `figures/actuator-assembly.png` — the B737-class design on its own.
- `figures/actuator-scaling.png` — output force and force per unit mass
  against bore across the family.

Each is written in light and dark variants, in the portfolio site's own
colour tokens, and these are the versions published at
<https://vinaykumar.is-a.dev>.

## Drawing pack — GD&T, fits and a tolerance stack

```bash
python drawing.py                 # four A4 sheets into drawings/
python -m pytest -q               # 54 tests
```

| Sheet | Content |
|---|---|
| `ACT-001` | Cylinder body — longitudinal half-section, end view |
| `ACT-002` | Piston rod — side view, pocket-end view |
| `ACT-003` | Clevis end — front and side views, hole pattern |
| `ACT-100` | Assembly GA — ballooned, parts list, stack-up table |

A model with nominal dimensions is not a manufacturable part. What turns
one into the other is saying, for every functional feature, how far from
nominal it may be and still work — in the language a machine shop and an
inspector both already read.

**Limits and fits** come from ISO 286, derived rather than typed: the IT
grade tables and fundamental deviations live in `tolerances.py` and are
indexed by nominal size band, so changing the bore changes its limits
without anyone re-reading a handbook. The bore is ⌀35 H8, the rod ⌀21 f7,
the pin bore ⌀25 H9. Hole-basis throughout, because holes are cut by
fixed-size tooling and shafts are turned to whatever size is wanted.

**Geometric tolerances** (ISO 1101) are on the features where form or
location decides whether the part works:

- **Cylindricity 0.02** on the bore — not roundness. A bore round at every
  station but tapered still leaks past a seal.
- **Total runout 0.05 to A** on the outside diameter — not concentricity,
  because runout controls the whole surface rather than the derived centre
  of it, and an inspector can actually measure it by rotating the part
  against an indicator.
- **Straightness 0.05** on the rod. At the B737 size it is 200 mm long on a
  ⌀21 shaft, near 10:1 — a bent rod binds in its gland and scrubs its seal
  even when every diameter measures perfectly.
- **Position ⌀0.3 (M) to A B C** on the clevis bolt holes. At maximum
  material condition, so a hole drilled larger than minimum earns
  proportional bonus tolerance — withholding that rejects parts that
  assemble perfectly well.

Datums are chosen, not defaulted. On the cylinder body datum A is the
**bore axis**, not the outside diameter: the bore is what the part exists
to do, so it is what everything else should be measured from. Taking the
OD instead would be easier to fixture and would let the bore wander
relative to the very axis the actuator works on.

**Tolerance stack-up** on `ACT-100`: extended eye-to-eye length, base face
to clevis pin-bore axis, five contributors — and rod engagement *subtracts*,
since rod buried in the bore is length the assembly does not gain.

| | |
|---|---|
| Nominal | 390.0 mm |
| Worst case | ±0.90 mm |
| RSS (3σ) | ±0.44 mm |

Both are reported because they answer different questions. Worst case adds
arithmetically and is a guarantee — right for a single build. RSS adds in
quadrature and is a statistical statement about a production run, roughly
twice as tight here. Quoting only RSS hides the parts that will not fit;
quoting only worst case buys tolerance nobody needed.

A test asserts the stack's nominal equals where `assembly()` actually puts
the clevis, so the drawing cannot drift from the model it dimensions.

**What this pack is not.** It tolerances the features the model has. A
production drawing would also carry a piston and gland (this model has
neither), a rod-end bearing, thread callouts for the port bosses, and a
surface-treatment and NDT schedule. Those are features not modelled, not
tolerances left out — inventing callouts for them would be decoration.

## A real bug this caught

`assembly()` built every component at the origin and added it there. But
the cylinder body is `stroke + 50` long against a `stroke`-long rod, so
the rod — and the clevis sitting 10 mm above its tip — ended up entirely
*inside* the barrel. Every STEP file this project exported was a bare
tube with the aircraft attachment point sealed inside it, which no viewer
could show and no reviewer could read.

Caught by rendering the assembly; a solid count and a bounding box both
looked perfectly healthy. The fix is placement only — no part's own
geometry changed — sliding the rod out along the bore until
`ROD_ENGAGEMENT` of it remains captive, and putting the clevis on the
tip where it belongs.

**A second, since fixed:** the clevis was sized `rod + 10` square against
a pin bore of `rod/2 + 2` radius, leaving 3 mm of plate for M6 holes
needing 6.5. The holes landed inside the bore — on the B777 variant they
vanished into it entirely, leaving a 7-face clevis where the smaller
variants had 10. The plate is now derived outwards from the bore
(`BORE_TO_HOLE_LIGAMENT`, `HOLE_TO_EDGE_MARGIN`), so the holes clear it by
construction at every size, and a test asserts both clearances across the
family. All four variants now export an identical 9-face clevis.

**And a third:** the BOM's masses were hand-rolled formulas, all wrong.
The cylinder's used `stroke` where the part is `stroke + 50` long and
ignored the end-cap web; the rod's ignored the seal pocket; the clevis's
was `(bore / 10) * 0.2`, a heuristic with no connection to the geometry
at all — which is why every B737 clevis weighed exactly 0.700 kg however
the plate was sized, and why the B777 figure was 5.3× the truth. Masses
now come from each solid's real OCC volume. Project 02 had already found
and fixed exactly this; the lesson had not crossed over.

## Learning Outcomes

After this project, you'll understand:

✅ Parametric design thinking (change input → output updates)  
✅ Aerospace component design (seals, ports, mounting)  
✅ CAD file formats (STEP is universal)  
✅ Programmatic modeling advantages (reproducible, versionable, automated)  
✅ Bill of materials generation (mass, cost, supplier parts)  
✅ How flight control actuation works (hardware side of your cycle model)

## Integration with Turbofan Cycle Model

**Bridge Analysis to Hardware:**

```
Your Cycle Model
     ↓
Calculate exhaust temperature, pressure
     ↓
Determine turbine blade loads
     ↓
Size turbine bearing actuators
     ↓
Generate actuator CAD (this project)
     ↓
Design thermal ducting around actuators
```

**Example:**
- High-pressure turbine inlet: 1200 K
- Needs cooling
- Thermal duct feeds cooling air to bearing cavity
- Actuator must fit in confined space
- This script sizes the actuator parametrically

## Future Enhancements

### Short-term (Week 2-3)

- [ ] Add pressure relief valve model
- [ ] Add servo valve (directional control)
- [ ] Parametric socket-end variant
- [ ] Fatigue analysis integration

### Medium-term (Month 2-3)

- [ ] Generative design optimization (minimize mass, fit constraints)
- [ ] Monte Carlo assembly tolerance stack-up
- [ ] Cost estimation (material + manufacturing)
- [ ] Design DFM checks (automatically flag manufacturing issues)

### Long-term (After placement)

- [ ] Integrate with CATIA scripting API (automate in real CAD)
- [ ] AI-based actuator sizing (given aircraft requirements)
- [ ] Seal groove optimization (flow simulation)
- [ ] Manufacturing process planning (machine tool selection)

## References

### Aerospace Standards

- SAE AS568 — O-ring dimensions
- SAE J2244 — ORB (O-ring boss) ports
- MIL-A-8709 — Aircraft hydraulic actuator requirements
- ASME Y14.5 — Geometric dimensioning & tolerancing

### Open Source

- CadQuery Documentation: https://cadquery.readthedocs.io/
- CadQuery Examples: https://github.com/CadQuery/cadquery/tree/master/examples

## Author & Contact

**Vinaykumar**  
Aerospace Engineering Student  
Specialization: Turbofan Propulsion & Flight Systems  
Project: Bridging analysis (cycle modeling) to design (parametric CAD)

GitHub: [See portfolio repository]

---

## License

MIT License — Use freely for educational and commercial projects.

## Contributing

This is a learning project. Feedback and improvements welcome!

**Potential contributions:**
- [ ] Pilot-operated check valve model
- [ ] Solenoid valve actuation control
- [ ] Thermal analysis (heat dissipation in rod seals)
- [ ] Integration tests with cycle model

---

**Status:** ✅ Complete — Ready for:
- CAD import (SOLIDWORKS, CATIA, Fusion 360)
- Portfolio demonstration
- Next project: Parametric thermal duct generator

**Next Project:** [[02-Gearbox-Family]] — Parametric scaling for engine accessory gearbox
