# Project Structure

```
Brain-Segmentation/
├── base/                    # Abstract base classes
│   ├── base_dataset2d_sliced.py
│   ├── base_dataset.py
│   ├── base_model.py
│   └── base_trainer.py
├── config/                  # Configuration files for training and transforms
│   ├── config_atlas.json
│   ├── atlas_transforms.json
│   └── ...
├── datasets/                # Dataset loading and preprocessing (inherited from base_datasets)
│   ├── DatasetFactory.py
│   ├── ATLAS.py
│   └── BraTS2D.py
├── losses/                  # Loss function implementations
│   └── LossFactory.py
├── metrics/                 # Metrics computation and tracking
│   ├── MetricsFactory.py
│   └── MetricsManager.py
├── models/                  # Model architectures (inherited from base_model)
│   ├── ModelFactory.py
│   ├── UNet2D.py
│   └── UNet3D.py
├── optimizers/              # Optimizer configurations
│   └── OptimizerFactory.py
├── trainer/                 # Training logic (inherited from base_trainer)
│   ├── trainer_2Dsliced.py
│   └── trainer_3D.py
├── transforms/              # Data augmentation and preprocessing
│   └── TransformsFactory.py
├── utils/                   # Utility functions
│   ├── util.py
│   └── pad_unpad.py
├── scripts/                 # Utility scripts (e.g., text embeddings)
│   └── extract_textemb_biobert.py
│   └── preprocess_qatacov.py
├── report_generation/       # Code for report generation and evaluation
│   ├── agreement
│   │   ├── radfact.py
│   │   ├── radfact-70b
│   │   ├── run-auto-agreement.py
│   │   └── run-radfact-agreement.py
│   ├── autogen
│   │   ├── fill_atlas.py
│   │   ├── generate_atlas.py
│   │   ├── generate_eloquent.py
│   │   ├── generate_reports
│   │   └── run_cc_segmentation.py
│   ├── utils
│   │   ├── data.py
│   │   ├── geometries.py
│   │   └── jsonify.py
│   └── README.md
├── config.py                # Config file handler
├── main.py                  # Training entry point
└── requirements.txt         # Python dependencies
```