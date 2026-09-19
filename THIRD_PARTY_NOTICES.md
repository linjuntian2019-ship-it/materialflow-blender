# Third-party components

MaterialFlow source is licensed under GPL-3.0-or-later (see LICENSE).
Blender, PyTorch and NumPy are separate dependencies under their own licenses.

The optional material recognition uses Apple DMS46, from Paul Upchurch and
Ransen Niu, *A Dense Material Segmentation Dataset for Indoor and Outdoor Scene
Parsing*, ECCV 2022. See https://github.com/apple/ml-dms-dataset and
https://arxiv.org/abs/2207.10614.

The model, taxonomy and upstream software have their own Apple license:
https://github.com/apple/ml-dms-dataset/blob/main/LICENSE.txt.
The dataset has a separate CC-BY-NC 4.0 license. Neither weights, taxonomy nor
dataset are included in this repository or install ZIP. Obtain them from the
official project and review the applicable terms. This project is independent
and is not affiliated with or endorsed by Apple or the Blender Foundation.

The demonstration media and procedural scene were made for this project.
No NeRF2Physics or BPHHullSim code is bundled.
