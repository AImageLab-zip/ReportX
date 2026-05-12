import csv
from argparse import ArgumentParser
from pathlib import Path

import report_generation.agreement.radfact
from report_generation.agreement.radfact import compute_radfact
from tqdm import tqdm


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--clinician-1-path",
        type=Path,
        required=True,
        help="Directory containing the first clinician report set, one subdirectory per case.",
    )
    parser.add_argument(
        "--clinician-2-path",
        type=Path,
        required=True,
        help="Directory containing the second clinician report set, one subdirectory per case.",
    )
    parser.add_argument(
        "--results-file",
        type=Path,
        required=True,
        help="CSV file where RadFact agreement results will be written.",
    )
    parser.add_argument(
        "--radfact-model",
        default="radfact-70b:latest",
        help="Ollama model name to use for RadFact scoring.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama server URL.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    references = []
    predictions = []

    old_files = [file for folder in sorted(args.clinician_1_path.iterdir()) for file in folder.iterdir() if "eng" in file.name]
    new_files = [file for folder in sorted(args.clinician_2_path.iterdir()) for file in folder.iterdir() if "eng" in file.name]
    assert len(old_files) == len(new_files) == 10

    for old, new in zip(old_files, new_files):
        assert old.parent.name == new.parent.name
    for old, new in zip(old_files, new_files):
        with open(old, "r") as f:
            references.append(f.read())
        with open(new, "r") as f:
            predictions.append(f.read())

    assert len(references) == len(predictions) == 10

    temperatures = [0.0, 0.0, 0.0]

    args.results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(args.results_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "temp", "precision", "recall", "F1"])

        for temperature in temperatures:
            results = compute_radfact(predictions=predictions,
                                      references=references,
                                      ollama_url=args.ollama_url,
                                      radfact_model=args.radfact_model,
                                      max_workers=10,
                                      temperature=temperature)
            writer.writerow(
                [
                    args.radfact_model,
                    temperature,
                    results["radfact-precision"],
                    results["radfact-recall"],
                    results["radfact-f1"],
                ]
            )
            print(f"num calls:{agreement.radfact.NUM_CALLS}, total tokens:{agreement.radfact.NUM_TOKENS}")


if __name__ == "__main__":
    main()
