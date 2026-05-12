## Automatic dataset generation
This pipeline expects the dataset to be in the classical BraTS2023 layout:
```text
<DATASET_ROOT>/
  BraTS-GLI-XXXXXX/
    BraTS-GLI-00001-t1n.nii.gz
    BraTS-GLI-00001-t1c.nii.gz
    BraTS-GLI-00001-t2f.nii.gz
    BraTS-GLI-00001-t2w.nii.gz
    BraTS-GLI-00001-seg.nii.gz
  BraTS-GLI-XXXXXX/
    ...
```
### How To Run

1. Create connected-component segmentations

```bash
python report_generation/autogen/run_cc_segmentation.py \
  --image-path /path/to/brats_dataset \
  --output-path /path/to/BraTS_CC \
  --num-workers NUM_WORKERS
```

2. Register atlas to each subject

```bash
python  report_generation/autogen/generate_atlas.py \
  --input-dir /path/to/brats_dataset \
  --output-dir /path/to/BraTS_atlas \
```

3. Fill tiny holes in atlas labels (creates `*-fill.nii.gz`)

```bash
python -m report_generation.autogen.fill_atlas \
  --input-path /path/to/BraTS_atlas
```
4. Warp eloquent masks from atlas space to each subject

```bash
python  report_generation/autogen/generate_eloquent.py \
  --input-path /path/to/BraTS_atlas \
  --output-path /path/to/BraTS_eloquent \
```

5. Generate final structured/text reports

```bash
python -m report_generation.autogen.generate_reports \
  --cc-path /path/to/BraTS_CC \
  --atlas-path /path/to/BraTS_atlas \
  --eloquent-path /path/to/BraTS_eloquent \
  --legend-path /path/to/legend_postprocessed.csv \
  --output-root /path/to/output \
  --thresholds 0.0 \
  --num-workers 8

## What It Produces

Given subject-level MRI/segmentation data, the pipeline builds:
- connected-component tumor labels (`BraTS_CC`)
- subject-space anatomical atlas labels (`BraTS_atlas`)
- subject-space eloquent masks (`BraTS_eloquent`)
- final generated outputs (`ReportX_tXX`), one folder per threshold, each subject containing:
  - `generated.json` (structured representation)
  - `generated.txt` (natural-language report)