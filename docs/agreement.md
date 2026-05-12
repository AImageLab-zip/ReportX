# Agreement Evaluation

This document describes the two agreement evaluation scripts in `report_generation/agreement/`:

- `run-auto-agreement.py`: compares structured auto-generated reports against clinician reports made imitating the machine pipeline.
- `run-radfact-agreement.py`: computes report-level factual agreement between two clinician report sets with RadFact through Ollama.

## Expected Layout
`run-auto-agreement.py` expects matching case folders in both inputs:

```text
<CLINICIAN_ROOT>/
  CASE_001/
    eng.txt
  CASE_002/
    eng.txt

<AUTOGEN_ROOT>/
  CASE_001/
    eng.json
  CASE_002/
    eng.json
```
The layout produced by `autogen` pipeline is already ready use.

`run-radfact-agreement.py` expects two report roots with matching case folders. Each case folder must contain an English report file whose name includes `eng`.

```text
<CLINICIAN_1_ROOT>/
  CASE_001/
    eng.txt
  CASE_002/
    eng.txt

<CLINICIAN_2_ROOT>/
  CASE_001/
    eng.txt
  CASE_002/
    eng.txt
```

## How To Run

1. If you want to run RadFact agreement, start Ollama

```bash
ollama serve
```

By default `run-radfact-agreement.py` connects to `http://localhost:11434`. If your server runs elsewhere, pass `--ollama-url`.

2. Create the RadFact Ollama model

From the repository root:

```bash
ollama create radfact-70b -f report_generation/agreement/radfact-70b
```

This creates the default model tag `radfact-70b:latest`.

The model file currently uses:

```text
FROM llama3:70b-instruct
```

If the base model is not available locally, pull it first:

```bash
ollama pull llama3:70b-instruct
```

3. Run the structured auto-vs-clinician agreement script

Use this script to compare auto-generated JSON reports against clinician text reports that were already normalized to the same structure and field ordering.

```bash
python report_generation/agreement/run-auto-agreement.py \
  --clinician-path /path/to/clinician_reports \
  --autogen-path /path/to/autogen_reports
```

4. Run the RadFact agreement script

Use this script to compare two report sets with the RadFact evaluator running through Ollama.

```bash
python report_generation/agreement/run-radfact-agreement.py \
  --clinician-1-path /path/to/clin_1 \
  --clinician-2-path /path/to/clin_2 \
  --results-file /path/to/results.csv
```
