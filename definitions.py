

DEFAULT_ANONIMIZATION_VALUES = {
                "DT": "0010101010101.000000+0000" ,
                "TM": "000000.00" ,
                "DA": "00010101" ,
                "LO": "Anonymized" ,
                "LT": "Anonymized" ,
                "SH": "Anonymized" ,
                "PN": "Anonymized" ,
                "CS": "Anonymized" ,
                "ST": "Anonymized" ,
                "UT": "Anonymized" ,
                "UN": "Anonymized" ,
                "FD": "0" ,
                "FL": "0" ,
                "SS": "0" ,
                "US": "0" ,
                "SL": "0" ,
                "UL": "0" ,
                "DS": "0" ,
                "IS": "0" ,
                "SQ": "-",
                "UI": "-",
                "AE": "-",
                "AS": "-",
                "AT": "-",
                "OB": "-",
                "OW": "-",
                "OD": "-",
                "OF": "-"}

SW_VERSION = "rtdcmXplr-1.0.1"
SW_UID = '1.2.826.0.1.3680043.10.1500.1.100'
# ANNEX_E_EXTRA_ACTIONS ={
#                         'basic_profile' :1,
#                         'retain_safe_private_options' :2,
#                         'retain_save_uid_options' : 3,
#                         'retain_device_identifier_options' :4,
#                         'retain_patient_chars_options' :5,
#                         'retain_longitudinal_full_dates_options' :6,
#                         'retain_save_longitudinal_modified_dates_options' :7,
#                         'clean_desc_options' :8,
#                         'clean_struct_cont_options' : 9,
#                         'clean_graph_options':10
#                         }
#https://wiki.cancerimagingarchive.net
# BASE_ANON_PROFILE_ACTIONS =[
#                         {"action":"base","code":"113100"},
#                         {"action":"clean_pixel_data_options","code":"113101"},
#                         {"action":"clean_recognizable_visual_features_option","value":"113102"},
#                         {"action":"clean_graphics_option","value":"113103"},
#                         {"action":"clean_structured_content_option","value":"113104"},
#                         {"action":"clean_descriptors_option","value":"113105"},
#                         {"action":"retain_longitudinal_temporal_information_with_full_dates_option","value":"113106"},
#                         {"action":"retain_longitudinal_temporal_information_with_modified_dates_option","value":"113107"},
#                         {"action":"retain_patient_characteristics_option","value":"113108"},
#                         {"action":"retain_device_identity_option","value":"113109"},
#                         {"action":"retain_institution_identity_option","value":"xxxxxxx"},
#                         {"action":"retain_uid_option","value":"113110"},
#                         {"action":"retain_safe_private_option","value":"113111"}
#   ]
DICT_ANON_PROFILE_ACTIONS =  { 1:"base", 
                                2:"retain_safe_private_option",
                                3:"retain_uid_option",
                                4:"retain_device_identity_option",
                                5:"retain_institution_identity_option",
                                6:"retain_patient_characteristics_option",
                                7:"retain_longitudinal_temporal_information_with_full_dates_option",
                                8:"retain_longitudinal_temporal_information_with_modified_dates_option",
                                9:"clean_descriptors_option",
                                10:"clean_structured_content_option",
                                11:"clean_graphics_option"
                                }


PREPOSITION_TEXT = ['for:' 'on:', 'to:', 'at:', 'by:', 'call:','for', 'on', 'to', 'at', 'by', 'call']
PREFIX_NAME=['prof.','dr.']


PET_SOP_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.128"