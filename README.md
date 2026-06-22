# ReportX: The BraTS Clinical Report Dataset

This is the repository of BraTS-ReportX, a paired resource of 257 clinical reports aligned to BraTS subjects, structured into a rich set of qualitative and quantitative attributes. 
This repository contains code for:
1. Automatic generation of quantitative report attributes from BraTS data, including anatomical localization and geometric measurements; 
2. Report encoding with biomedical language models;
3. Evaluating the semantic coverage and overall quality of the dataset, supporting analyses of how well BraTS-ReportX captures clinically relevant report information compared with existing resources; and (4) training and testing of the proposed vision-text alignment framework for 3D tumor segmentation. 
The codebase is designed to support reproducibility and further research on integrating structured clinical semantics into medical image segmentation.

<p align="center">
  <img src="report_comparison.png" width="80%">
</p>
<p align="center">
  <em>Overview of the annotation protocol. Clinician reports and automatically generated reports are produced independently and then concatenated.</em>
</p>

<p align="center">
  <img src="model_overview.png" width="80%">
</p>
<p align="center">
  <em>Our segmentation pipeline overview. Encoder features from a 3D U-Net are projected into flat visual embeddings, while clinical reports are mapped to text embeddings. A contrastive vision-text module aligns both modalities during training, while inference relies only on the image backbone.</em>
</p>

## Table of Contents
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Quick Start and Usage Examples](#quick-start-and-usage-examples)
  - [Command Line Arguments](#command-line-arguments)
  - [Implement Your Own Training](#implement-your-own-training)
- [Detailed Components](#detailed-components)
  - [Base Classes](base/README.md)
  - [Configuration](config/README.md)
  - [Datasets](datasets/README.md)
  - [Losses](losses/README.md)
  - [Metrics](metrics/README.md)
  - [Models](models/README.md)
  - [Optimizers](optimizers/README.md)
  - [Trainers](trainer/README.md)
  - [Transforms](transforms/README.md)
  - [Utils](utils/README.md)
  - [Scripts](scripts/README.md)
  - [Jobs](jobs/README.md)
- [Notes](#notes)

The project structure is available [here](/docs/structure.md).

## Installation
1. Clone the repository:
```bash
git clone https://github.com/AImageLab-zip/Report-Guided-Segmentation
cd Report-Guided-Segmentation
```

2. Create a virtual environment and install dependencies:
```bash
uv sync --no-cache
```

3. Activate the environment
```bash
source .venv/bin/activate
```
## Supported Pipelines:
1. [Segmentation Model Training](/docs/training.md)
2. [Segmentation Model Testing](/docs/testing.md)
3. [Automatic Report Generation](/docs/report_gen.md)
4. [Agreement](/docs/agreement.md)
5. [Yggrasil](/docs/yggdrasil.md)
6. [Concept Coverage Score & Template Adherence](/docs/ccs_ta.md)
7. [Statistical Comparison](/docs/statistical_test.md)

## Extending
This is a fork of a universal framework from https://github.com/kev98/Medical-Image-Segmentation. An overview on using and extending it with your own implementation can be found [here](/docs/extending_framework.md)
