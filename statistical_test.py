import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from autorank import autorank, plot_stats, create_report, latex_table

# =============================================
# Configuration — edit paths here
# =============================================
PLOT_OUTPUT_DIR = "/results/path"


def model_name_from_path(path):
    """
    Example:
    /path/to/TextBraTS_base_BioClinicalBERT.csv
    -> TextBraTS_base_BioClinicalBERT
    """
    return Path(path).stem


def read_metric_from_csv(csv_path, metric_column, id_column):
    df = pd.read_csv(csv_path)

    if id_column not in df.columns:
        raise ValueError(f"Column '{id_column}' not found in {csv_path}")

    if metric_column not in df.columns:
        raise ValueError(f"Column '{metric_column}' not found in {csv_path}")

    # Remove AVERAGE row
    df = df[df[id_column].astype(str).str.upper() != "AVERAGE"].copy()

    # Keep only subject ID and chosen metric
    df = df[[id_column, metric_column]].copy()

    # Convert metric to numeric
    df[metric_column] = pd.to_numeric(df[metric_column], errors="coerce")

    # Drop rows where the selected metric is NaN
    df = df.dropna(subset=[metric_column])

    # Check duplicated subject IDs
    if df[id_column].duplicated().any():
        duplicated = df.loc[df[id_column].duplicated(), id_column].tolist()
        raise ValueError(
            f"Duplicated subject IDs found in {csv_path}: {duplicated[:10]}"
        )

    return df


def build_paired_dataframe(csv_files, metric_column, id_column):
    merged_df = None

    for csv_path in csv_files:
        model_name = model_name_from_path(csv_path)

        model_df = read_metric_from_csv(
            csv_path=csv_path,
            metric_column=metric_column,
            id_column=id_column,
        )

        model_df = model_df.rename(columns={metric_column: model_name})

        if merged_df is None:
            merged_df = model_df
        else:
            merged_df = pd.merge(
                merged_df,
                model_df,
                on=id_column,
                how="inner",
            )

    if merged_df is None:
        raise ValueError("No CSV files were provided.")

    if len(merged_df) == 0:
        raise ValueError("No paired cases remain after merging by subject_id.")

    # subject_id is only used for alignment, not for autorank
    paired_data = merged_df.drop(columns=[id_column])

    return merged_df, paired_data


def main():
    parser = argparse.ArgumentParser(
        description="Run autorank statistical comparison on paired model CSV files."
    )

    parser.add_argument(
        "--csv-files",
        nargs="+",
        required=True,
        help="CSV files, one per model.",
    )

    parser.add_argument(
        "--metric-column",
        required=True,
        help="Metric column to compare, e.g. DSC_aggregated_mean or DSC_mean.",
    )

    parser.add_argument(
        "--id-column",
        default="subject_id",
        help="Case ID column used to align paired cases. Default: subject_id.",
    )

    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level. Default: 0.05.",
    )

    parser.add_argument(
        "--order",
        choices=["ascending", "descending"],
        default="descending",
        help=(
            "Use descending when higher metric is better, "
            "ascending when lower metric is better. Default: descending."
        ),
    )

    parser.add_argument(
        "--output-prefix",
        default="autorank_results",
        help="Prefix for output files.",
    )

    args = parser.parse_args()

    merged_df, paired_data = build_paired_dataframe(
        csv_files=args.csv_files,
        metric_column=args.metric_column,
        id_column=args.id_column,
    )

    print("\nNumber of paired cases used:", len(paired_data))
    print("\nModels compared:")
    for col in paired_data.columns:
        print(f"  - {col}")

    print("\nMean performance per model:")
    print(paired_data.mean().sort_values(ascending=False))

    # Save the paired table used by autorank, useful for reproducibility
    paired_output = f"{args.output_prefix}_paired_data.csv"
    merged_df.to_csv(paired_output, index=False, float_format="%.4f")
    print(f"\nSaved paired data to: {paired_output}")

    # Run autorank
    result = autorank(
        paired_data,
        alpha=args.alpha,
        verbose=True,
        order=args.order,
    )

    print("\nAutorank result:")
    print(result)

    print("\nAutorank textual report:")
    create_report(result)

    print("\nLaTeX table:")
    latex_table(result)

    # Plot statistical result
    plot_stats(result)
    plt.tight_layout()

    plot_output = f"{PLOT_OUTPUT_DIR}/{args.output_prefix}_plot.png"
    plt.savefig(plot_output, dpi=300)
    print(f"\nSaved plot to: {plot_output}")


if __name__ == "__main__":
    main()