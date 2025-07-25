# Introduction 
DEIDENTIFICATION of dicom studies, for participating to MIDI-B De-identification challenge (https://www.synapse.org/Synapse:syn53065760/wiki/627876)


# installation 
1. Clone the repository
1. Create an enviroment python -m venv venv
2. Activate the venv venv\Scripts\activate
3. Install all pakages  pip install -r requirements.txt
4. Install keras-ocr    pip install -q keras-ocr

## lets run:
 
 - into debug_de_identification.py insert the input parameters:
        - input_data_folder =  r'C:\challenge_testdata\input_data'
        - rules_file = './custom_rules.json'  (here already the rules used for the challenge)
        - basic_profile_file = './base_anonymization_profile.csv'
- python debug_de_identification

##  Outputs
- in the input data folder have been created the data and the mappings folder
- a log file has already created.


# Contribute

https://dicom.nema.org/dicom/2013/output/chtml/part15/sect_E.3.html#sect_E.3.1


# package used

- pydicom==2.4.4
- numpy
- matplotlib
- scikit-image
- pillow
- tensorflow==2.15
- keras-ocr
- thefuzz

## 📖 Citation

If you use this code or part of it in your research, please cite:

[Michele, Bufano], *DICOM deep deidentification*, GitHub Repository, https://github.com/rtdicomexplorer/deep_deidentification

BibTeX:

```bibtex
@misc{your_project_2025,
  author       = {Michele Bufano},
  title        = {DICOM deep deidentification},
  year         = 2024,
  publisher    = {GitHub},
  journal      = {GitHub repository},
  howpublished = {\url{https://github.com/rtdicomexplorer/deep_deidentification}},
}

