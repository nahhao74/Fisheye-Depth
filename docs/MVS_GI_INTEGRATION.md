# MVS-GI Integration Plan

## Why MVS-GI is the first external dataset target

MVS-GI is the closest public research baseline currently identified for NADIR's spatial core because it uses three fisheye cameras facing the same direction and provides synthetic training/validation data for omnidirectional stereo depth.

Important limitation: MVS-GI is not a 225-degree dataset. Its released code uses a 195-degree raw camera model in the evaluation wrapper. Therefore it can validate the three-camera stereo pipeline, but it cannot validate NADIR's extreme 225-degree edge region.

## Official data sources

Main project:

- https://github.com/castacks/mvs_gi

Official download helper:

- https://github.com/castacks/mvs_gi_download

The MVS-GI README describes the full synthetic dataset as roughly 1.3 TB total, about 1.2 TB training data, with 50 training environments and 21 validation environments.

Do **not** download the full dataset for the first integration pass.

## First integration target: released sample validation data

The official offline-validation instructions provide a much smaller sample package:

```bash
wget -O sample_validation_data.zip \
  https://airlab-share.andrew.cmu.edu:8081/mvs_gi/code_release_202310_data.zip

unzip sample_validation_data.zip -d <DATA_ROOT>
```

Expected top-level extracted structure from the official instructions:

```text
<DATA_ROOT>/
└── code_release_202310_data/
    ├── real_world/
    └── synthetic/
```

Before writing any adapter, inspect the extracted tree:

```bash
python scripts/inspect_dataset_tree.py \
  <DATA_ROOT>/code_release_202310_data \
  --json artifacts/mvs_gi_sample_tree.json
```

The adapter is only frozen after we identify the actual meanings and file formats of:

- the three synchronized fisheye images;
- target/reference camera ordering;
- metric distance/depth ground truth;
- camera intrinsics / Double Sphere parameters;
- camera-to-rig extrinsics and transform direction;
- image and depth units;
- invalid/masked depth semantics.

## Full dataset downloader

The official `mvs_gi_download` repository uses a MinIO client. Its documented workflow is:

```bash
git clone https://github.com/castacks/mvs_gi_download.git
cd mvs_gi_download
python3 -m pip install -r requirements.txt
python3 download_lists.py
```

This retrieves training/validation object lists. A selected subset can then be downloaded with:

```bash
python3 download_dataset.py \
  --input_list list_validate.txt \
  --output_dir datasets \
  --dataset_type validate
```

NADIR should initially select a small validation subset rather than the full 1.3 TB corpus.

## NADIR acceptance sequence for MVS-GI

1. `DATA-INSPECT`: confirm file semantics from released sample data.
2. `DATA-ADAPTER`: convert one sample to `nadir.sample_manifest.v1` without guessed fields.
3. `CAL-CHECK`: verify pixel -> ray -> pixel roundtrip using dataset calibration.
4. `RIG-CHECK`: verify camera centers, baseline and transform directions.
5. `VIS-LUT`: build visibility and projection LUT from the real dataset rig.
6. `SWEEP-RGB`: run a non-neural sphere/ray sweep on one frame.
7. `GT-CHECK`: compare radial predicted depth with the dataset's metric GT semantics.
8. Only after this passes do we introduce learned image features.

## Scientific constraint

Success on MVS-GI establishes evidence for the three-camera stereo implementation at its released FoV. It does **not** establish performance in the target 225-degree peripheral region. That region requires separate 220-225-degree data and ultimately NADIR-specific 225-degree synthetic/real validation.
