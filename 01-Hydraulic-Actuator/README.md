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
| **Cylinder Mass** | ρ_Al = 2.7 g/cm³ | ~0.8 kg |
| **Rod Mass** | ρ_Steel = 7.85 g/cm³ | ~0.9 kg |

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

**Small Aircraft (Cessna 172):**
- Bore: 16 mm, Rod: 10 mm, Stroke: 100 mm
- Force: 4.2 kN, Speed: 6.5 cm/s
- Mass: 0.3 kg, Cost: $200-300

**Regional Turboprop (Q400):**
- Bore: 25 mm, Rod: 15 mm, Stroke: 150 mm
- Force: 10.3 kN, Speed: 4.2 cm/s
- Mass: 0.7 kg, Cost: $400-600

**Narrow-body (B737-800):**
- Bore: 35 mm, Rod: 21 mm, Stroke: 200 mm
- Force: 20.2 kN, Speed: 3.7 cm/s
- Mass: 1.3 kg, Cost: $1,500-2,500

**Wide-body (B777-300ER):**
- Bore: 50 mm, Rod: 30 mm, Stroke: 250 mm
- Force: 41.1 kN, Speed: 2.6 cm/s
- Mass: 2.8 kg, Cost: $3,000-5,000

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
