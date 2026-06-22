# Statistical Comparison (autorank)

[`statistical_test.py`](/statistical_test.py) runs a paired statistical comparison across multiple models' per-case metric CSVs using [autorank](https://github.com/sherbold/autorank). It merges the CSVs by case ID, prints mean performance per model, runs the ranking test, and saves a paired-data CSV, a textual/LaTeX report, and a result plot.

## Configuration

`PLOT_OUTPUT_DIR` at the top of the file sets the directory where the result plot (`<output-prefix>_plot.png`) is saved — edit it before running.

## How To Run

```bash
python statistical_test.py \
  --csv-files /path/to/ModelA.csv /path/to/ModelB.csv /path/to/ModelC.csv \
  --metric-column DSC_aggregated_mean \
  --id-column subject_id \
  --order descending \
  --output-prefix autorank_results
```

Each CSV is expected to have one row per case (identified by `--id-column`) plus an `AVERAGE` row, which is dropped automatically. The model name used in the comparison is derived from each CSV's filename (without extension).
