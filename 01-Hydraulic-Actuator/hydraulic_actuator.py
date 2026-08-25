"""
Parametric Hydraulic Actuator Generator
========================================

Generates 3D CAD models for aircraft hydraulic flight control actuators.
Useful for understanding actuator sizing, seal dimensions, and assembly.

Input: Bore diameter, rod diameter, stroke length
Output: STEP file + PDF drawings + Bill of Materials

Author: Vinaykumar (Aerospace Engineering)
Date: 2026-08-22
Integration: Connects to turbofan cycle model for control actuation analysis
"""

import cadquery as cq
import json
from pathlib import Path


class HydraulicActuator:
    """
    Parametric hydraulic cylinder for aircraft flight control systems.

    Typical applications:
    - Elevator actuation (pitch control)
    - Aileron actuation (roll control)
    - Rudder actuation (yaw control)
    - Landing gear extension/retraction
    """

    def __init__(self, bore_diameter_mm=30, rod_diameter_mm=18, stroke_length_mm=200):
        """
        Initialize actuator with parametric dimensions.

        Args:
            bore_diameter_mm: Cylinder bore diameter (mm). Typical: 20-60 mm
            rod_diameter_mm: Piston rod diameter (mm). Typical: 0.6*bore
            stroke_length_mm: Stroke length (mm). Typical: 100-300 mm
        """
        self.bore = bore_diameter_mm
        self.rod = rod_diameter_mm
        self.stroke = stroke_length_mm

        # Derived dimensions (typical aerospace standards)
        self.wall_thickness = 3  # mm, aluminum cylinder
        self.cylinder_od = self.bore + 2 * self.wall_thickness
        self.rod_seal_groove_depth = 1.5  # mm
        self.rod_seal_groove_width = 4.0  # mm
        self.clevis_thickness = 8  # mm
        self.port_diameter = 8  # mm (hydraulic port SAE standard)

    def create_cylinder_body(self):
        """Create hollow cylinder body with internal bore."""
        cylinder = (
            cq.Workplane("XY")
            .circle(self.cylinder_od / 2)
            .extrude(self.stroke + 50)  # Extra length for end fittings
            .faces(">Z")
            .workplane()
            .circle(self.bore / 2)
            .cutBlind(-self.stroke)  # Internal bore
            .faces("<Z")
            .workplane()
            .circle(self.bore / 2)
            .cutBlind(-25)  # End cap thickness
        )
        return cylinder

    def create_piston_rod(self):
        """Create piston rod with an end pocket standing in for a seal
        groove. Not a true circumferential O-ring groove (that cuts
        radially into the rod's cylindrical surface, not axially into its
        end face) -- this is a simplified stand-in, sized to actually fit
        within the rod's own diameter rather than the original's cutter
        (rod + 2*groove_width, wider than the rod itself, which would have
        machined off the whole tip instead of leaving a groove)."""
        groove_radius = max(self.rod / 2 - self.rod_seal_groove_width, 1.0)
        rod = (
            cq.Workplane("XY")
            .circle(self.rod / 2)
            .extrude(self.stroke)
            .faces(">Z")
            .workplane()
            .circle(groove_radius)
            .cutBlind(-self.rod_seal_groove_depth)
        )
        return rod

    # Clevis proportions. The plate has to be big enough to carry the two
    # M6 mounting holes clear of the pin bore, and the old fixed
    # `rod + 10` square was not: at rod 21 the bore is already 25 across,
    # leaving 3 mm of plate either side for a hole needing 6.5. The holes
    # landed inside the bore and were swallowed by it -- on the B777
    # variant they vanished entirely, leaving a 7-face clevis where the
    # smaller variants had 10. Sizing the plate from the bore outwards
    # instead makes that impossible by construction.
    BOLT_CLEARANCE_HOLE = 6.5   # M6 clearance, ISO 273 medium series
    BORE_TO_HOLE_LIGAMENT = 4.0  # min material between pin bore and bolt hole
    HOLE_TO_EDGE_MARGIN = 4.0    # min material between bolt hole and plate edge

    @property
    def pin_bore_diameter(self):
        """Through-bore for the attachment pin. Two millimetres larger in
        radius than the rod it caps."""
        return self.rod + 4.0

    @property
    def bolt_hole_offset(self):
        """Bolt-hole centres, measured from the pin-bore axis."""
        return (self.pin_bore_diameter / 2 + self.BORE_TO_HOLE_LIGAMENT
                + self.BOLT_CLEARANCE_HOLE / 2)

    @property
    def clevis_size(self):
        """Square plate side, derived so the bolt holes always clear both
        the bore and the edge."""
        return 2 * (self.bolt_hole_offset + self.BOLT_CLEARANCE_HOLE / 2
                    + self.HOLE_TO_EDGE_MARGIN)

    def create_clevis_end(self):
        """Create clevis-end mounting for aircraft attachment: a mounting
        block (not a true forked yoke -- that's a separate modelling task)
        with a through-bore for the rod pin and two bolt holes, all drilled
        through the same thickness direction so they sit on one consistent
        workplane.

        Plate size is derived from the bore rather than fixed -- see the
        constants above for why."""
        size = self.clevis_size
        clevis = (
            cq.Workplane("XY")
            .box(size, self.clevis_thickness, size)
            .faces(">Y")
            .workplane()
            .circle(self.pin_bore_diameter / 2)
            .cutThruAll()
        )
        clevis = (
            clevis.faces(">Y")
            .workplane()
            .pushPoints([(0, self.bolt_hole_offset), (0, -self.bolt_hole_offset)])
            .hole(self.BOLT_CLEARANCE_HOLE)
        )
        return clevis

    def create_hydraulic_ports(self):
        """Create A/B hydraulic ports for pressure/return."""
        # Port A (pressure) - typically on cap end
        port_a = (
            cq.Workplane("XY")
            .circle(self.port_diameter / 2)
            .extrude(10)
        )

        # Port B (return) - typically on rod end
        port_b = (
            cq.Workplane("XY")
            .circle(self.port_diameter / 2)
            .extrude(10)
        )

        return port_a, port_b

    # Fraction of the rod left engaged in the bore when the assembly is
    # posed extended. Real rod-end actuators keep a proportion of the rod
    # captive at full extension so the piston stays supported; a third is a
    # reasonable simplified value.
    ROD_ENGAGEMENT = 0.35

    def assembly(self):
        """Create complete actuator assembly, posed extended.

        The pose matters, and the obvious one is wrong. Build every part at
        the origin and nothing is visible: the cylinder body is
        `stroke + 50` long against a `stroke`-long rod, so the rod -- and
        the clevis sitting 10 mm above its tip -- end up entirely inside
        the barrel. That is what this assembly used to export: a bare tube
        with the aircraft attachment point sealed inside it, geometry that
        no viewer could show and no reviewer could read.

        Posing the rod extended puts both where they belong. Nothing about
        the parts themselves changes -- this is placement only.
        """
        cylinder = self.create_cylinder_body()
        rod = self.create_piston_rod()
        clevis = self.create_clevis_end()

        # Rod slid out along the bore until only ROD_ENGAGEMENT of it
        # remains captive, measured from the cylinder's rod end.
        cylinder_length = self.stroke + 50
        rod_base_z = cylinder_length - self.ROD_ENGAGEMENT * self.stroke
        rod_tip_z = rod_base_z + self.stroke

        asm = cq.Assembly()
        asm.add(cylinder, name="cylinder_body", color=cq.Color("gray70"))
        asm.add(rod.translate((0, 0, rod_base_z)),
                name="piston_rod", color=cq.Color("gray50"))
        # Clevis centred 10 mm past the rod tip, the same small overlap the
        # original placement used to join the two.
        asm.add(clevis.translate((0, 0, rod_tip_z + 10)),
                name="clevis_end", color=cq.Color("gray30"))

        return asm

    def export_step(self, filename="hydraulic_actuator.step"):
        """Export assembly to STEP file for CAD software."""
        asm = self.assembly()
        asm.save(filename)
        print(f"✓ STEP file saved: {filename}")
        return filename

    def export_parts_separately(self, output_dir="./parts"):
        """Export individual parts for subassembly."""
        Path(output_dir).mkdir(exist_ok=True)

        cylinder = self.create_cylinder_body()
        rod = self.create_piston_rod()
        clevis = self.create_clevis_end()

        # Workplane has no .save() -- that's an Assembly method (used in
        # export_step above); a bare shape/Workplane exports through
        # cq.exporters.export instead.
        cq.exporters.export(cylinder, f"{output_dir}/01_cylinder_body.step")
        cq.exporters.export(rod, f"{output_dir}/02_piston_rod.step")
        cq.exporters.export(clevis, f"{output_dir}/03_clevis_end.step")

        print(f"✓ Individual parts saved to {output_dir}/")
        return output_dir

    def get_bom(self):
        """Generate Bill of Materials."""
        bom = {
            "actuator": {
                "bore_diameter_mm": self.bore,
                "rod_diameter_mm": self.rod,
                "stroke_length_mm": self.stroke,
                "cylinder_material": "Aluminum 6061-T6",
                "rod_material": "Steel 4340",
            },
            "components": [
                {
                    "part_name": "Cylinder Body",
                    "material": "Aluminum 6061-T6",
                    "mass_kg": self._calc_cylinder_mass(),
                },
                {
                    "part_name": "Piston Rod",
                    "material": "Steel 4340",
                    "mass_kg": self._calc_rod_mass(),
                },
                {
                    "part_name": "Rod Seal",
                    "material": "PTFE",
                    "quantity": 2,
                },
                {
                    "part_name": "Piston Seal",
                    "material": "PTFE",
                    "quantity": 1,
                },
                {
                    "part_name": "Clevis End",
                    "material": "Steel 4340",
                    "mass_kg": self._calc_clevis_mass(),
                },
                {
                    "part_name": "Hydraulic Port (A/B)",
                    "material": "Steel SAE",
                    "quantity": 2,
                },
            ]
        }
        return bom

    # Densities, g/cm3. Aluminium 6061-T6 for the cylinder, steel 4340 for
    # the rod and clevis -- matching the materials the BOM already declares.
    DENSITY_ALUMINIUM = 2.70
    DENSITY_STEEL = 7.85

    @staticmethod
    def _solid_mass_kg(workplane, density_g_cm3):
        """Mass from the real solid's OCC volume, not a hand-rolled formula.

        The formulas this replaced were all wrong, in three different ways.
        The cylinder's used `stroke` where the part is `stroke + 50` long
        and ignored the end-cap web entirely. The rod's ignored the seal
        pocket. The clevis's was `(bore / 10) * 0.2` -- a heuristic with no
        connection to the geometry at all, which is why every B737-class
        clevis weighed exactly 0.700 kg however the plate was sized.

        Project 02 found and fixed exactly this, and the lesson did not
        cross over. The solids already exist by the time get_bom() runs, so
        there was never a reason to approximate.
        """
        volume_mm3 = workplane.val().Volume()
        return (volume_mm3 / 1000) * density_g_cm3 / 1000

    def _calc_cylinder_mass(self):
        return self._solid_mass_kg(self.create_cylinder_body(),
                                   self.DENSITY_ALUMINIUM)

    def _calc_rod_mass(self):
        return self._solid_mass_kg(self.create_piston_rod(),
                                   self.DENSITY_STEEL)

    def _calc_clevis_mass(self):
        return self._solid_mass_kg(self.create_clevis_end(),
                                   self.DENSITY_STEEL)

    def save_bom(self, filename="BOM.json"):
        """Save BOM to JSON file."""
        bom = self.get_bom()
        with open(filename, 'w') as f:
            json.dump(bom, f, indent=2)
        print(f"✓ BOM saved: {filename}")
        return filename

    def get_specs(self):
        """Get technical specifications string."""
        specs = f"""
HYDRAULIC ACTUATOR SPECIFICATIONS
==================================

Bore Diameter:      {self.bore} mm
Rod Diameter:       {self.rod} mm
Stroke Length:      {self.stroke} mm

Cylinder OD:        {self.cylinder_od} mm
Wall Thickness:     {self.wall_thickness} mm
Clevis Thickness:   {self.clevis_thickness} mm

Hydraulic Ports:    {self.port_diameter} mm (SAE standard)
Seal Grooves:       {self.rod_seal_groove_width} mm wide × {self.rod_seal_groove_depth} mm deep

Application:        Aircraft flight control actuation
                    (elevators, ailerons, rudders, landing gear)

Typical Pressure:   3000 PSI (210 bar)
Typical Flow:       2-10 GPM (7.5-38 L/min)

Force Output:       {self._calc_force_output():.1f} kN @ 210 bar
Speed (extend):     {self._calc_speed():.1f} cm/s @ 5 GPM
"""
        return specs

    def _calc_force_output(self):
        """Calculate force output at typical pressure."""
        import math
        # Force = Pressure × Area
        # P = 210 bar = 21 MPa
        # A = π * (d/2)²
        area_mm2 = math.pi * (self.bore / 2)**2
        pressure_mpa = 21  # 210 bar
        force_n = area_mm2 * pressure_mpa
        return force_n / 1000  # Convert to kN

    def _calc_speed(self):
        """Calculate extension speed at typical flow."""
        import math
        # Speed = Flow / Area
        # Flow = 5 GPM = 0.315 L/min = 5.25 cm³/s
        flow_cm3_s = 5.25
        area_mm2 = math.pi * (self.bore / 2)**2
        area_cm2 = area_mm2 / 100
        speed_cm_s = flow_cm3_s / area_cm2
        return speed_cm_s


def generate_family_of_actuators():
    """
    Generate a family of actuators for different engine sizes.
    Useful for parametric scaling across aircraft variants.
    """

    print("\n" + "="*60)
    print("GENERATING ACTUATOR FAMILY FOR DIFFERENT AIRCRAFT")
    print("="*60)

    # Define actuator sizes for different aircraft classes
    actuator_sizes = {
        "Small Aircraft (Cessna-class)": {
            "bore": 16,
            "rod": 10,
            "stroke": 100,
        },
        "Regional Turboprop (Q400-class)": {
            "bore": 25,
            "rod": 15,
            "stroke": 150,
        },
        "Narrow-body (B737-class)": {
            "bore": 35,
            "rod": 21,
            "stroke": 200,
        },
        "Wide-body (B777-class)": {
            "bore": 50,
            "rod": 30,
            "stroke": 250,
        },
    }

    for aircraft_type, dims in actuator_sizes.items():
        print(f"\n{aircraft_type}")
        print("-" * 60)

        actuator = HydraulicActuator(
            bore_diameter_mm=dims["bore"],
            rod_diameter_mm=dims["rod"],
            stroke_length_mm=dims["stroke"]
        )

        # Print specs
        print(actuator.get_specs())

        # Export STEP file
        filename = f"actuator_{aircraft_type.split('(')[0].strip().replace(' ', '_').lower()}.step"
        actuator.export_step(filename)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("HYDRAULIC ACTUATOR CAD GENERATOR")
    print("="*60)

    # Example: Create a B737-size actuator
    print("\nCreating B737-class actuator...")
    actuator = HydraulicActuator(
        bore_diameter_mm=35,
        rod_diameter_mm=21,
        stroke_length_mm=200
    )

    # Display specifications
    print(actuator.get_specs())

    # Export STEP file
    actuator.export_step("hydraulic_actuator_b737.step")

    # Export individual parts
    actuator.export_parts_separately()

    # Generate BOM
    actuator.save_bom()

    # Generate family of actuators
    generate_family_of_actuators()

    print("\n" + "="*60)
    print("✓ Actuator generation complete!")
    print("="*60)
