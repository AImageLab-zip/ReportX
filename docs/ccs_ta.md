# Concept Coverage Score (CCS) & Template Adherence (TA)

[`cc_ta.ipynb`](/cc_ta.ipynb) is a notebook-based evaluation that compares a directory of `eng.txt` reports against a `global_finding.json` dataset using two complementary metrics:

- **CCS**: links report text to RadLex concepts (via NER + the BioPortal Annotator, with a local fuzzy-match fallback) and measures coverage against a reference set of brain-tumour-relevant RadLex concepts.
- **TA**: scores each report against a structured brain-tumour MRI reporting template (RANO 2.0 + BT-RADS + RSNA RadReport) by checking which template data elements are mentioned.

## Configuration

All paths are configured in the first cell of the notebook — edit that cell before running the rest:

- `REPORT_PATH`: single report used for the NER/RadLex demo (cells 1-4)
- `REPORTS_DIR`: directory of `<case>/eng.txt` reports
- `GLOBAL_JSON`: path to `global_finding.json`
- `CCS_CACHE_DIR` / `TA_CACHE_DIR`: cache directories for CCS/TA results (delete to force recomputation)
- `BIOPORTAL_API_KEY`: API key for the BioPortal Annotator (get a free key at https://bioportal.bioontology.org/account)
