# Setup / 安装配置

## Plugin only

Install the release ZIP, not GitHub's whole-repository source ZIP, in Blender
Preferences → Add-ons → Install from Disk. Enable MaterialFlow. The module is
named `material_physics` for compatibility with existing scene properties.
Disable/remove a previous copy before replacing it, then restart Blender.
Tested: Blender 5.2.2 LTS on Windows. Earlier Blender versions are unsupported.

The manual density/mass workflow and demo use Blender's bundled Python.
No separate environment or account is needed for those features.

## Optional local AI / 可选本地识别

The worker is CUDA-only. Tested with Python 3.11, PyTorch 2.5.1 + CUDA 12.4,
torchvision 0.20.1, NumPy 2.4.6 and Pillow 12.3.0. A compatible NVIDIA driver
and enough GPU memory are required; lower-end cards have not been benchmarked.

Create an environment outside the plugin folder (PowerShell example):

```powershell
py -3.11 -m venv .venv-ai
.venv-ai/Scripts/python.exe -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
.venv-ai/Scripts/python.exe -m pip install -r requirements-ai.txt
```

Obtain the **DMS46 pretrained model** and `taxonomy.json` from the
[official Apple DMS project](https://github.com/apple/ml-dms-dataset).
Follow its model download link and extract `DMS46_v1.pt`. Review the model
license separately from the dataset license. Model files are not bundled here.

In MaterialFlow preferences set:

| Field | Value |
| --- | --- |
| 独立 Python | Absolute path to `.venv-ai/Scripts/python.exe` |
| Apple DMS 模型 | Absolute path to `DMS46_v1.pt` |
| 类别文件 | Absolute path to upstream `taxonomy.json` |
| 本地结果目录 | Writable cache folder; a local default is provided |

Select a visible textured mesh and run recognition in the 材料物理 sidebar.
The plugin saves a scene snapshot, renders 12 isolated views using another
Blender process, then starts the local worker. It does not send images to an API.
Job folders contain snapshots/images/results; remove them manually when no
longer needed. Restart recognition after changing geometry or materials.

Check the proposed material and physical type. Enter a measured/appropriate
density or mass; the plugin does not fetch a density database. Open meshes may
be recognized, but cannot supply a valid solid volume. A liquid surface can
store liquid parameters without a closed volume.

## Demo

Use a closed 1 m cube with unit scale and no shape-changing modifiers.
Start with solid density 600 kg/m³ and drop clearance 1.8 m. Creating the demo
makes a separate scene; save it before baking. Baking fluid and spray can take
minutes and produce over 1 GB of cache. Render only after baking completes.
The example uses 241 frames at 24 fps (motion samples span 10 seconds).

To build the procedural example from source:

```sh
blender --background --factory-startup --python-exit-code 1 --python examples/create_demo.py -- --out generated/wood-drop
```

Open the saved scene and bake via the plugin. The generated scene contains
local cache paths; rebuild it in the destination folder when moving machines.
Rendered MP4/GIF media can be shared without those caches.
