# Gate A Real-Data Runbook

This runbook is the next execution step for NADIR. It does **not** authorize dense/learned architecture promotion. Its purpose is to produce the first real MVS-GI sparse geometry evidence.

## 1. Keep large data on KINGSTON

Use the external storage root:

```bash
export NADIR_DATA_ROOT=/media/nahhao74/KINGSTON/NADIR_DATA
mkdir -p "$NADIR_DATA_ROOT"
```

Do not place the released dataset, extracted samples, runtime captures or large reports under `/home`.

## 2. Pull NADIR locally

If the repository is not cloned yet:

```bash
cd /media/nahhao74/KINGSTON
git clone https://github.com/nahhao74/Fisheye-Depth.git
cd Fisheye-Depth
```

If it already exists:

```bash
cd /path/to/Fisheye-Depth
git status
git pull origin main
```

## 3. Create the Gate A Python environment

```bash
python3 -m venv .venv_gate_a
source .venv_gate_a/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,mvs-gi]'
pytest
```

The local tests only verify implementation/math invariants. A PASS here is **not** Gate A scientific evidence.

## 4. Obtain a released MVS-GI sample

Use the official public downloader repository:

```bash
cd "$NADIR_DATA_ROOT"
git clone https://github.com/castacks/mvs_gi_download.git
cd mvs_gi_download
python -m pip install -r requirements.txt
```

The official downloader documents two routes:

- `download_lists.py` + `download_dataset.py` for selected train/validation tar files;
- `download_models.py` for checkpoints, optimized models and released sample data.

The latter is documented by the upstream project as roughly **5.8 GB total**, so keep it on KINGSTON:

```bash
python download_models.py
```

Do not assume the first downloaded directory is already the NADIR dataset root. After download/extraction, locate a directory that contains the verified root files together:

```text
manifest.json
metadata.json
frame_graph.json
data_partitions.json
masks.json
```

For example:

```bash
find "$NADIR_DATA_ROOT" -name manifest.json -print
```

Set the chosen root explicitly:

```bash
export MVS_GI_ROOT=/media/nahhao74/KINGSTON/.../actual_dataset_root
```

## 5. Audit the actual payload before triangulation

From the NADIR repository:

```bash
cd /path/to/Fisheye-Depth
source .venv_gate_a/bin/activate

python scripts/inspect_mvs_gi.py "$MVS_GI_ROOT" \
  --split validate \
  --max-samples 3 \
  --decode-first-gt
```

Do not proceed by guessing if this exposes a new camera model, different frame name, missing binding, unexpected image shape or incompatible dataset layout. That discrepancy must be resolved at the adapter/source-semantics layer first.

Record at minimum:

- camera model binding for `cam0/cam1/cam2/rig`;
- image resolution;
- first sample paths;
- GT shape/dtype/range;
- any loader exception or missing source file.

## 6. Run Gate A with no optional geometry thresholds

Create a result root on KINGSTON:

```bash
export NADIR_GATE_A_ROOT=/media/nahhao74/KINGSTON/NADIR_GATE_A
mkdir -p "$NADIR_GATE_A_ROOT"
```

Then run exactly one sample first:

```bash
python scripts/run_gate_a_sparse.py "$MVS_GI_ROOT" \
  --split validate \
  --sample-index 0 \
  --json-out "$NADIR_GATE_A_ROOT/sample_000_raw.json"
```

Do **not** add `--min-triangulation-angle-deg`, `--max-closest-gap-m` or `--max-reprojection-px` on the first run. The first result is intended to expose the raw distributions rather than encode a desired answer.

## 7. What the first report must answer

For each of the three camera pairs:

- how many ORB keypoints exist;
- how many Hamming cross-check matches exist;
- how many matches yield numerically valid + forward ray intersections;
- physical pair baseline;
- closest-ray gap distribution;
- triangulation-angle distribution;
- reprojection-error distribution;
- metric radial error against the released rig-reference GT;
- depth error by source incidence angle.

The harness reports `automatic_pass_fail=false`. This is intentional.

## 8. Interpretation boundary

The first raw report can support one of three next states only:

```text
EVIDENCE_INTERPRETABLE
INSUFFICIENT_CORRESPONDENCE_EVIDENCE
SOURCE_OR_GEOMETRY_DISCREPANCY
```

It must **not** directly promote:

- dense photometric sphere sweep;
- CNN/ResNet/attention;
- learned candidate selection;
- IMU/RTK fusion;
- 225° claims;
- QCS8550 performance.

If the raw result is interpretable, explicit geometry filters/acceptance criteria can be proposed from the observed distributions and then reviewed before a filtered rerun.

## 9. Known GT comparison limitation

The released MVS-GI source uses radial distance along native unit rays. That semantic is source-verified. However, the upstream training loader uses its own `INTER_BLENDED` distance resampling path, while the current Gate A sparse harness uses NADIR bilinear sampling on the raw reference distance image at the projected sparse point.

Therefore large errors near depth discontinuities must be separated from triangulation/calibration failures before any Gate A acceptance decision.

## 10. 225° boundary

MVS-GI is a bootstrap only. Its public raw configuration is approximately 195°, so it can exercise rays beyond 90° only to roughly 97.5° incidence. It cannot validate the target annulus:

```text
97.5° < incidence <= 112.5°
```

That annulus requires later exact-225° synthetic and/or real-rig evidence even if Gate A passes on MVS-GI.
