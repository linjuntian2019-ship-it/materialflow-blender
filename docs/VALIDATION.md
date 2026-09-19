# Validation and limits

The published media reuses the existing 960 × 720 / 24 fps wood-water render.
The README GIF is a smaller transcode; it is not a new simulation or render.

Reference motion: 1 m³ solid, density 600 kg/m³, mass 600 kg, water density
1000 kg/m³, gravity 9.81 m/s², initial clearance 1.8 m, 288 integration steps/s.
The reference run reaches about 0.6015 submerged volume fraction at 10 s
(hydrostatic target 0.6), final speed about 0.0123 m/s. It fully immerses before
resurfacing. These describe this synthetic example only.

Automated checks cover density-dependent equilibrium, free-fall acceleration,
finite normalized motion, conservative physical-type suggestions, Blender
volume/unit conversion, mass input, open-solid rejection and open-liquid
parameter storage. The portable example is built in background Blender without
rebaking. These checks do not validate a real fluid experiment or recognition
accuracy. Recognition has been exercised on the procedural wood example; no
representative material benchmark has been completed.

Known limits: empirical damping, approximate submerged volume, single box,
no bottom collision, no sinking dense solids, no fluid feedback, no variable
viscosity dynamics, and only Windows/CUDA tested for AI. A closed manifold mesh
is required for volume, but passing that check does not prove absence of
self-intersections. Hollow and composite solids need additional modeling.
