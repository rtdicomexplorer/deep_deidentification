# Introduction 
DEIDENTIFICATION of dicom studies, for participating to MIDI-B De-identification challenge

# installation 
1. Clone the repository
1. Create an enviroment python -m venv venv
2. Activate the venv venv\Scripts\activate
3. Install all pakages  pip install -r requirements.txt

## lets run:
 
 - into debug_de_identification.py insert the input parameters:
        - input_data_folder =  r'C:\challenge_testdata\input_data'
        - rules_file = './anon_custom_rules.json'
        - basic_profile_file = './basic_anonymization_profile.csv'
- python debug_de_identification


# Build and Test
https://wiki.cancerimagingarchive.net/display/Public/Submission+and+De-identification+Overview

DEMO DATA like described in  https://www.synapse.org/Synapse:syn53065760/wiki/627887


About COLLECTION-DATA:

CT  |
    |
    STRUCT  |
            |
            PLAN    |
                    |
                    DOSE


# Contribute

https://dicom.nema.org/dicom/2013/output/chtml/part15/sect_E.3.html#sect_E.3.1


