
import re
import os
import csv
import json
import keras_ocr
from collections import OrderedDict
import pydicom as dcm
from pydicom.uid import generate_uid
from pydicom.uid import UID
from pydicom.multival import MultiValue
from datetime import datetime
from dcm_collection import DcmCollection
import random
import string
import logging
from thefuzz import fuzz

from pydicom.datadict import dictionary_VR


from text_detection import *
from definitions import *

class DicomDeIdentification:
    """
        Main object  
        tha execute the de-identification
    """
    __default_deleted_string = 'deleted'
    __default_binary_object_string = "other object"

    def __generate_studyUID(self):
        rootuid = generate_uid(prefix=None)
        suffix = str(datetime.now().timestamp())
        studyuid = f"{rootuid}.{suffix.split('.')[0]}"
        return studyuid[0:50]
    
    def __generate_patient_name(self, size = 20):
        chars=string.ascii_uppercase + string.digits
        pat_name = f"{''.join(random.choice(chars) for _ in range(size))}^ANON"
        return pat_name

    def __generate_patient_id(self, size = 10):
        chars=string.ascii_uppercase + string.digits
        pat_id = f"PID{''.join(random.choice(chars) for _ in range(size))}"
        return pat_id


    def __update_history(self, elem, new_value, history):
        """Saves the old and new values with group and element and vr
        """
        
        if history is None:
            return
        try:
            tag_group = "0x%04x" % elem.tag.group
            tag_element = "0x%04x" % elem.tag.element       
            element = elem
            if isinstance(elem, dcm.dataelem.RawDataElement):
                element = dcm.dataelem.DataElement_from_raw(elem)
            vr = dictionary_VR(element.tag)
            skip = ["OB", "OW","OF", "OD"]
            if history is not None:
        
                value = ""
                if (vr  not in skip):
                    value = str(element.value)
                else:
                    value = self.__default_binary_object_string + " ("+str(vr )+")"
                keyword = element.keyword
                i=0
                while keyword in history:
                    i+=1
                    keyword = keyword+str(i)

                history[keyword] = tag_group, tag_element, vr , element.name, value, new_value
        except Exception as e:

                self.__logger.error(f"{tag_group},{tag_element}, Error: {e}")

    def __update_history_private(
    self,
    element,
    new_value,
    history,
     private_keyword):
        vr = dictionary_VR(element.tag)
        skip = ["OB", "OW"]
        if history is not None:
            tag_group = "0x%04x" % element.tag.group
            tag_element = "0x%04x" % element.tag.element
            value = ""
            if (vr  not in skip):
                value = str(element.value)
            else:
                value = self.__default_binary_object_string

            keyword = element.keyword

            if len(keyword) == 0 and private_keyword is not None:
                keyword = private_keyword

            history[keyword] = tag_group, tag_element, vr , element.name, value, new_value


    #extra fuction
    def __replace_element_with_given_value(self,dataset, tag,history = None):
        """
        Replace element with given value
        """
        element = dataset.get(tag)
        if element is not None:
            new_value = self.__extra_replacement_values[( element.tag.group, element.tag.element)]
            self.__update_history(element,new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value

    def __set_date_to_year(self,dataset, tag, history):
        """
        Remove day and month if not empty yyyymmdd to yyyy0101
        """
        element = dataset.get(tag)
        if element is not None and element.value:
            new_value = f"{element.value[:4]}0101" # YYYYMMDD format
            self.__update_history(element,new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value 

    def __shift_date_year(self,dataset,tag, history):
        """
        Shit the year with a given value
        """
        element = dataset.get(tag)
        if element is not None and element.value:
            shift_value = self.__extra_replacement_values[( element.tag.group, element.tag.element)]
            year = int(element.value[:4])+ int (shift_value)
            new_value = f"{year}{element.value[4:]}" 
            self.__update_history(element,new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value 

    def __replace_text_inside_tag(self, dataset, tag, history):
        """
        Replace text inside a tag
        """
        element = dataset.get(tag)
        if element is not None and element.value:
            value_to_add = self.__extra_replacement_values[( element.tag.group, element.tag.element)]
            new_sub_string =""
            if len(value_to_add)>1:
                new_sub_string = value_to_add[1]
                old_sub_string =value_to_add[0]
                value = str(element.value)
                new_value = value.replace(old_sub_string, new_sub_string)
                self.__update_history(element,new_value, history)
                self.__sensible_burning_data.append(str(element.value))
                element.value =  new_value

    def __keep(self,dataset,tag,history):
        """
        Keep the element with a condition
        keep (unchanged for non-sequence attributes, cleaned for sequences)
        """
        element = dataset.get(tag)
        if element.is_private:
            #do nothing
            return
        vr = dictionary_VR(element.tag)
        if element is not None and element.value:
            target = ( element.tag.group, element.tag.element)
            if target in self.__extra_replacement_values:
                condition_value = self.__extra_replacement_values[( element.tag.group, element.tag.element)]
                if condition_value is None:
                    if dataset.parent is None:
                        #keeped without condition out side sequence
                        return
                    else :
                        new_value = ""
                        self.__update_history(element,new_value, history)
                        self.__sensible_burning_data.append(str(element.value))
                        element.value = new_value 
                else :
                    value = str(element.value)
                    comp = self.__compare_dcm_values(vr ,value, condition_value)
                    if comp == False:             
                        if ( element.tag.group, element.tag.element) in self.__original_anon_actions:
                            action =  self.__original_anon_actions[( element.tag.group, element.tag.element)]
                            action(dataset, tag, history)
            else:
                if dataset.parent is None:
                #keeped without condition out side sequence
                    return
                else :                   
                    new_value = ""
                    self.__update_history(element,new_value, history)
                    self.__sensible_burning_data.append(str(element.value))
                    element.value = new_value 

    def __skip(self,dataset,tag,history):
        """Do nothing
        """       
        pass

    def __check_person_name_present(self,dataset,tag,history):
        element = dataset.get(tag)
        if element.is_private:
            #do nothing
            return
        vr = dictionary_VR(element.tag)
        if element is not None and element.value:
            if  vr in ('LO', 'LT', 'SH', 'PN', 'CS', 'ST', 'UT'):        
                new_value = str(element.value)
                new_values = new_value.split()
                values_to_check = new_value.lower().split()
                #check the person name:
                for text in self.__preson_name_to_clean:
                    if text in values_to_check:
                        pos = values_to_check.index(text) 
                        values_to_check = values_to_check[:pos]+values_to_check[pos+1:]
                        new_values = new_values[:pos]+ new_values[pos+1:]
                new_value =  " ".join(new_values)
                self.__update_history(element,new_value, history)
                element.value = new_value



    def __clean(self,dataset,tag,history):
        '''
        clean, that is replace with values of similar meaning known not to contain identifying information and consistent with the VR
        For DA DT and TM it happens a shifting
        '''     
        element = dataset.get(tag)
        if element.is_private:
            #do nothing
            return
        vr = dictionary_VR(element.tag)
        found_preposition = False
        found_indetifying = False
        if element is not None and element.value:
            new_value =""           
            if vr in ('DA', 'DT'):
                shift_value = '5'#maybe input value
                year = int(element.value[:4])+ int (shift_value)
                new_value = f"{year}{element.value[4:]}" 
                found_indetifying = True
            elif vr =='TM':# do nothing
                return
            elif  vr in ('LO', 'LT', 'SH', 'PN', 'CS', 'ST', 'UT'):              
                new_value = str(element.value)
                   #check the person name:
                for text in self.__preson_name_to_clean:
                    if text in new_value.lower():
                        self.__update_history(element,new_value, history)
                        element.value = ""
                        return
                new_value = self.__check_preposition(vr ,new_value)
                found_preposition = new_value != str(element.value)
                value_to_check = new_value.lower()       
                for text in  self.__texts_to_clean:
                    if text in value_to_check:
                        new_value = self.__texts_to_clean[0]
                        found_indetifying = True
                        break
                if found_indetifying == False:
                    values_to_check = value_to_check.split()   
                    new_values = new_value.split()
                    for single_data in self.__sensible_data_to_clean:
                        if single_data in values_to_check:
                            pos = values_to_check.index(single_data)#  value_to_check.find(single_data)      
                            new_values = new_values[:pos]+ new_values[pos+1:]
                            values_to_check = values_to_check[:pos]+values_to_check[pos+1:]
                            found_indetifying = True
                    new_value =  " ".join(new_values)
            if found_indetifying == True or found_preposition == True: 
                self.__update_history(element,new_value, history)
                self.__sensible_burning_data.append(str(element.value))
                element.value = new_value

    def __check_and_retain(self,dataset,tag,history):
        """
        To manage the case like series number where the really number should be retain
        example is series number
        """
        element = dataset.get(tag)
        if element.is_private:
            #do nothing
            return
        vr = dictionary_VR(element.tag)
        if element is not None and vr== 'IS' and  element.value:
            new_value = str(element.value)
            value_to_check = new_value.lower()       
            for text in  self.__sensible_data_to_clean:
                if text == value_to_check:
                    new_value = ""
                    self.__update_history(element,new_value, history)
                    element.value = new_value
                    return

    def __compare_dcm_values(self,vr,left,right):
        """Just for testing,  used for tags like Patient age.. 
        
        Keyword arguments:
        argument -- description
        Return: return_description
        """
        
        if vr == "AS":#compare age
            l1 = ""
            l2 =""
            for char in left: 
                if not char.isalpha():
                    l1+=char#099
                else:
                    l2+=char # Y,M,D
            r1 = ""
            r2 = ""
            for char in right:
                if not char.isalpha():
                    r1+=char#0999
                else:
                    r2+=char# Y,M,D
            
            if l2 == r2:
                return l1>r1
            else:
                return l2>r2

        return False


    def __get_uid(self, old_uid: str) -> str:
        """
        Existing UID in dictionary or create new one if none found
        """
        if old_uid not in self.__dictionary_uids:
            self.__dictionary_uids[old_uid] = generate_uid(None)
        return self.__dictionary_uids.get(old_uid)

    def __replace_element_uid(self, element, history=None):
        """
        Replace UID element's
        """
        if isinstance(element.value, MultiValue):  
            for k, v in enumerate(element.value):
                element.value[k] = self.__get_uid(v)
        else:
            new_value = self.__get_uid(element.value)
            self.__update_history(element, new_value,history)       
        element.value = new_value

    def __replace_element_date(self, element,history = None):
        """
        Replace date element's
        """
        vr = dictionary_VR(element.tag)
        new_value = self.__default_anon_values[vr]
        self.__update_history(element, new_value, history)
        self.__sensible_burning_data.append(str(element.value))
        element.value = new_value

    def __replace_element(self, element,history = None):
        """
        Replace element according with the VR, and the rules
        """

        vr = dictionary_VR(element.tag)
        new_value =  self.__default_anon_values[vr]#    self.__default_date_time_value
        if vr in ('LO', 'LT', 'SH', 'PN', 'CS', 'ST', 'UT','DS', 'IS','DT', 'DA', 'TM'):
            self.__update_history(element, new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value  # CS VR accepts only uppercase characters
        elif vr  == 'UI':
            self.__replace_element_uid(element, history)
        elif vr  in ('FD', 'FL', 'SS', 'US', 'SL', 'UL'):
            self.__update_history(element, new_value, history)
            element.value = new_value
        elif vr  == 'UN':
            new_value =new_value.encode('ascii')
            self.__update_history(element, new_value, history)
            element.value = new_value
        elif vr  == 'SQ':
            for sub_dataset in element.value:
                for sub_element in sub_dataset.elements():
                    if isinstance(sub_element, dcm.dataelem.RawDataElement):
                        raw_element = dcm.dataelem.DataElement_from_raw(sub_element)
                        self.__replace_element(raw_element, history)
                        sub_dataset.add(raw_element)
                    else:
                        self.__replace_element(sub_element, history)

    def __replace_dataset(self, dataset, tag,history = None):
        element = dataset.get(tag)
        if element is not None:
            self.__replace_element(element, history)

    def __empty_element(self, element,history = None):

        if isinstance(element, dcm.dataelem.RawDataElement):
            element = dcm.dataelem.DataElement_from_raw(element)
        
        vr = dictionary_VR(element.tag)
        new_value =  self.__default_anon_values[vr]#    self.__default_date_time_value
        

        if vr  in ('SH', 'PN', 'UI', 'LO', 'LT', 'CS', 'AS', 'ST', 'UT', 'AE'):
            new_value = ""
            self.__update_history(element, new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value
        elif vr  in ('UL', 'FL', 'FD', 'SL', 'SS', 'US','DS', 'IS','DT', 'DA', 'TM'):
            self.__update_history(element, new_value, history)
            self.__sensible_burning_data.append(str(element.value))
            element.value = new_value
        elif vr  == 'UN':
            new_value =new_value.encode('ascii')
            self.__update_history(element, new_value, history)
            element.value = new_value
        elif vr  == 'SQ':
            for sub_dataset in element.value:
                for sub_element in sub_dataset.elements():
                    self.__empty_element(sub_element, history)


    def __empty_dataset(self, dataset, tag, history = None):
        """ Empty elements according with rules and VR
        """
        element = dataset.get(tag)
        if element is not None:
            self.__empty_element(element, history)


    def __delete_element(self, dataset, element,history = None):
        """
        Delete element according with Rules and VR.
        """
        vr = dictionary_VR(element.tag)
        if vr  == 'DA':
            self.__replace_element_date(element, history)
        elif vr  == 'SQ': # and element.value is type(Sequence):
            for sub_dataset in element.value:
                for sub_element in sub_dataset.elements():
                    self.__update_history(element = sub_element, new_value = self.__default_deleted_string, history=history)
                    self.__delete_element(sub_dataset, sub_element, history)
        else:
            self.__update_history(element , self.__default_deleted_string, history=history)
            del dataset[element.tag]


    def __delete_dataset(self, dataset, tag,history = None):
        """ Delete dataset according with Rules and VR."""
        element = dataset.get(tag)
        if element is not None:
            self.__delete_element(dataset, element, history) 


    def __replace_UID(self, dataset, tag,history = None):
        element = dataset.get(tag)
        if element is not None:
            self.__replace_element_uid(element, history)

    def __empty_or_replace_dataset(self, dataset, tag,history = None):
        """Z/D - Z unless D is required to maintain IOD conformance (Type 2 versus Type 1)"""
        self.__replace_dataset(dataset, tag, history)


    def __delete_or_empty_dataset(self, dataset, tag,history = None):
        """X/Z - X unless Z is required to maintain IOD conformance (Type 3 versus Type 2)"""
        self.__empty_dataset(dataset, tag, history)


    def __delete_or_replace_dataset(self, dataset, tag,history = None):
        """X/D - X unless D is required to maintain IOD conformance (Type 3 versus Type 1)"""
        self.__replace_dataset(dataset, tag, history)


    def __delete_or_empty_or_replace_dataset(self, dataset, tag, history = None):
        """
        X/Z/D - X unless Z or D is required to maintain IOD conformance (Type 3 versus Type 2 versus
        Type 1)
        """
        self.__replace_dataset(dataset, tag, history)


    def __delete_or_empty_or_replace_UID(self, dataset, tag,history = None):
        """
        X/Z/U* - X unless Z or replacement of contained instance UIDs (U) is required to maintain IOD
        conformance (Type 3 versus Type 2 versus Type 1 sequences containing UID references)
        """
        element = dataset.get(tag)
        vr = dictionary_VR(element.tag)

        if element is not None:
            if vr  == 'UI':
                self.__replace_element_uid(element, history)
            else:
                self.__empty_element(element, history)


    def __remove_private_tags(self, dataset: dcm.Dataset):
        """Remove all private elements from the :class:`Dataset`."""
        def remove_callback(dataset, data_element) -> None:
            """Internal method to use as callback to walk() method."""
            if data_element.tag.is_private:
                self.__private_tags.append(data_element)
                del dataset[data_element.tag]
        dataset.walk(remove_callback)
    
    def __clean_private_tags(self, dataset: dcm.Dataset):
        """Clean all private elements from sensible data
            using the same rules like for not private element
        """
        
        def clean_private_callback(dataset,data_element):
               
                found_preposition = False
                found_indetifying = False
                if data_element is not None and data_element.tag.is_private and data_element.value:
                    vr =  data_element.VR 
                    if vr == 'SQ':
                        for sub_dataset in data_element.value:
                            self.__clean_private_tags(sub_dataset)
                    new_value =""

                    if vr  =="UI":
                        new_value = self.__get_uid(data_element.value)
                        found_indetifying = True           
                    if vr  in ('DA', 'DT'):
                        shift_value = '5'#maybe input value
                        year = int(data_element.value[:4])+ int (shift_value)
                        new_value = f"{year}{data_element.value[4:]}" 
                        found_indetifying = True
                    elif vr  =='TM':
                        return
                    elif  vr  in ('LO', 'LT', 'SH', 'PN', 'CS', 'ST', 'UT'):              
                        new_value = str(data_element.value) 
                                 #check the person name:
                        for text in self.__preson_name_to_clean:
                            if text in new_value.lower():
                                #self.__update_history(data_element,new_value,None)
                                data_element.value = ""
                                return
                        new_value = self.__check_preposition(vr ,new_value)
                        found_preposition = new_value != str(data_element.value)
                        value_to_check = new_value.lower()   
                        if found_indetifying == False:
                            values_to_check = value_to_check.split()   
                            new_values = new_value.split()
                            for single_data in self.__sensible_data_to_clean:
                                if single_data in values_to_check:
                                    pos = values_to_check.index(single_data)#  value_to_check.find(single_data)      
                                    new_values = new_values[:pos]+ new_values[pos+1:]
                                    values_to_check = values_to_check[:pos]+values_to_check[pos+1:]
                                    # #check for other 
                                    # value_to_check = new_value.lower() 
                                    found_indetifying = True
                            new_value =  " ".join(new_values)
                    if found_indetifying ==  True or found_preposition == True: 
                        data_element.value = new_value
        try:
                dataset.walk(clean_private_callback)
        except Exception as e:
            self.__logger.error(e)
            #needs to continue
                
    def __check_preposition(self, VR,value):
        """
        Check if the preposition are present and remove that with the next text
        """
        if VR in ('LO', 'LT', 'ST', 'UT'):  
            vals = value.split()
            index1 = -1
            index2 = -1
            for prefix in self.__prefix_text:

                for i, val in enumerate(vals):
                    if prefix ==  val.lower():
                        if len(vals)-1 == i:
                            break
                        index1 = i
                        index2 = i+2
                        if vals[i+1].lower() in PREFIX_NAME:
                            index2 +=1 #remove also the name
                        vals = vals[:index1]+vals[index2:]
                        break
            return  " ".join(vals)
        return value


    def __init__(self, profile_file_name,detect_text = True, delete_private_tags: bool = True,  json_file_rules = None):
        
        self.__detect_text = detect_text
        if self.__detect_text:
            self.__kera_pipeline = keras_ocr.pipeline.Pipeline()
        self.__logger = logging.getLogger(__name__)
        self.__texts_to_clean=[]
        self.__prefix_text =[]
        self.__preson_name_to_clean = [] #if a person name is present the tag will be completely cleaned
        self.__tags_to_check_by_keep = []
        self.__sensible_data_to_clean = []
        self.__sensible_burning_data = []
        self.__profile_anon_action_list = [] 
        self.__original_anon_actions = {}
        self.__default_anon_values = DEFAULT_ANONIMIZATION_VALUES
        self.__extra_replacement_values = {}
        self.__extra_rules = {}
        self.__delete_private_tags = delete_private_tags
        self.__history = {}
        self.__dictionary_uids = {}
        self.__private_tags = []
        self.__logger.info(f"Anonimization profile: {profile_file_name}")
        self.__dict_profile, self.__profile_list_tags =  self.__read_new_profile_file(profile_file_name) #self.__read_profile_file(profile_file_name) #
        self.__profile_action = self.__initialize_anon_actions_by_profile()
        self.__logger.info(f"Cusotm rules: {json_file_rules}")
        self.__read_extra_rules_file(json_file_rules)
        self.__profile_anon_action_list_dcm_standard = []
        for action in self.__profile_anon_action_list:
            if action in self.__dict_profile:
                self.__profile_anon_action_list_dcm_standard.append(self.__dict_profile[action])
        #retain safe private tags
        if  DICT_ANON_PROFILE_ACTIONS[2] in  self.__profile_anon_action_list:
               self.__delete_private_tags = False


    def __initialize_anon_actions_by_profile(self):

     return  {'D':self.__replace_dataset,'X':self.__delete_dataset,'Z':self.__empty_dataset,'C':self.__clean, 'K': self.__keep, 
              'U':self.__replace_UID, 'Z/D':self.__empty_or_replace_dataset,'X/Z':self.__delete_or_empty_dataset,
              'X/D':self.__delete_or_replace_dataset,'X/Z/D':self.__delete_or_empty_or_replace_dataset,
              'X/Z/U*':self.__delete_or_empty_or_replace_UID,
              'X/P': self.__keep}

    def __read_new_profile_file(self, profile_file_name):
        tcia_file =open(profile_file_name, 'r')
        list_tags = tcia_file.readlines()
        tcia_file.close()
        profiles={"base":{},"retain_safe_private_option":{},"retain_uid_option":{},
            "retain_device_identity_option":{},"retain_institution_identity_option":{},
            "retain_patient_characteristics_option":{},
            "retain_longitudinal_temporal_information_with_full_dates_option":{},
            "retain_longitudinal_temporal_information_with_modified_dates_option":{},"clean_descriptors_option":{},
            "clean_structured_content_option":{},"clean_graphics_option":{}}

       # basic_profile = {}
        for line in list_tags:
            lines = line.split('\n')[0]
            parts = lines.split(';')
            if len(lines)==0 or len(parts)==0:
                continue
            for  i in range (1,len(parts)):
                if len(parts[i])>0:
                   act_name = DICT_ANON_PROFILE_ACTIONS[i]
                   profiles[act_name].update({parts[0]:parts[i]}) 
        
        dict_keys = re.compile('|'.join( profiles[DICT_ANON_PROFILE_ACTIONS[1]]), re.IGNORECASE)

        return  profiles, dict_keys


    def __read_extra_rules_file(self,json_file_rules):
        
        if json_file_rules is  None:
            return
        if os.path.isfile(json_file_rules) == False:
            return
        try:

            # Opening JSON file
            f = open(json_file_rules)
            rules = json.load(f)
            f.close()
            if 'tag_list' in rules:
                tag_list = rules['tag_list']
                for element in tag_list:
                    if not "tag_group" in element or not "tag_element" in element or not "action" in element:
                        continue
                    tag_group = int(element["tag_group"],16)
                    tag_element = int(element["tag_element"],16)
                    action = element['action']
                    value = None
                    if 'values' in element:
                        values = element['values']
                        if len(values)>0:
                            value = values[0]['value']
                        if action =='REPLACE_PART_TEXT':
                            old_value = ""
                            if len(values)>1:
                                old_value = values[1]['value']
                            self.__extra_rules[(tag_group,tag_element)] = self.__replace_text_inside_tag
                            self.__extra_replacement_values[(tag_group,tag_element)] = [old_value,value]
                        elif action =='REPLACE_FULL_TEXT':
                            self.__extra_rules[(tag_group,tag_element)] = self.__replace_element_with_given_value 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action == "SET_DATE_YEAR":
                            self.__extra_rules[(tag_group,tag_element)] = self.__set_date_to_year  
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action =="SHIFT_DATE_YEAR":
                            self.__extra_rules[(tag_group,tag_element)] = self.__shift_date_year 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action =="EMPTY":
                            self.__extra_rules[(tag_group,tag_element)] = self.__empty_dataset 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action =="DELETE":
                            self.__extra_rules[(tag_group,tag_element)] = self.__delete_dataset 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action == "KEEP":
                              self.__extra_rules[(tag_group,tag_element)] = self.__keep 
                              self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action == "SKIP":
                            self.__extra_rules[(tag_group,tag_element)] = self.__skip 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action == "CHEKANDRETAIN":
                            self.__extra_rules[(tag_group,tag_element)] = self.__check_and_retain 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value
                        elif action == "CHEKPERSONNAME":
                            self.__extra_rules[(tag_group,tag_element)] = self.__check_person_name_present 
                            self.__extra_replacement_values[(tag_group,tag_element)] = value

            else:
                print("Custom rules does not contain a custom tag_list actions")
            if 'default_anon_values' in rules:
                anon_vr_values = rules['default_anon_values']
                for element in anon_vr_values:
                    if "vr" in element and "value" in element:
                        vr = element['vr']
                        value = element['value']
                        self.__default_anon_values[vr] = value 

            if 'custom_actions' in rules:
                custom_anon_action = rules['custom_actions']
                for element in custom_anon_action:
                    if "action" in element and "value" in element:
                        if element['value']== 'yes':
                            self.__profile_anon_action_list.append(element['action'])

            if 'tag_list_to_check_by_keep' in rules:
                tag_list = rules['tag_list_to_check_by_keep']
                for element in tag_list:
                    if not "tag_group" in element or not "tag_element" in element:
                        continue
                    tag_group = int(element["tag_group"],16)
                    tag_element = int(element["tag_element"],16)
                    self.__tags_to_check_by_keep.append({'group': tag_group, 'element':tag_element}) 
            if 'text_to_clean' in rules:
                text_list =rules['text_to_clean']['values']
                for text in text_list:
                    self.__texts_to_clean.append(text)
            
            if 'prefix_to_check' in rules:
                text_list =rules['prefix_to_check']['values']
                for text in text_list:
                    self.__prefix_text.append(text)

        except BaseException:
                self.__extra_rules = {}
                self.__extra_replacement_values = {}
                print("Cannot read the extra rules file")

    def __anonymize_dataset_inside(self, dataset: dcm.Dataset) -> None:
        """Process the recursively the DICOM tags
        """       

        for data_element in dataset:
            if data_element.is_private: # skipped at moment, in the future sould be execute at this time..😁
                continue
            try:
                vr = dictionary_VR(data_element.tag)
                tag_group = "%04x" % data_element.tag.group
                tag_element = "%04x" % data_element.tag.element
                if vr  == 'SQ':# and data_element.value is type(Sequence):
                    for sub_dataset in data_element.value:
                        self.__anonymize_dataset_inside(sub_dataset)
                else:

                    if  (data_element.tag.group,data_element.tag.element) in self.__extra_rules:
                        self.__extra_rules[(data_element.tag.group,data_element.tag.element)](dataset=dataset,tag = data_element.tag, history= self.__history)
                    else:
                        target = f"{tag_group},{tag_element}"
                        tags_found  = re.findall(self.__profile_list_tags,target)
                        if tags_found:
                            label_action = []
                            for tag in tags_found: 
                                for index in range(1,len(self.__profile_anon_action_list_dcm_standard)):
                                    found = False
                                    for k, v in self.__profile_anon_action_list_dcm_standard[index].items():
                                        if re.match(k, tag, re.IGNORECASE):
                                            label_action.append(v)
                                            found = True
                                            break
                                    if found:
                                        break
                                if found == False:
                                    for k, v in self.__profile_anon_action_list_dcm_standard[0].items():
                                        if re.match(k, tag, re.IGNORECASE):
                                            label_action.append(v)
                                            found = True
                                            break

                            #chek if the tag is present in a action list and get the action
                            if label_action[0] in self.__profile_action:
                                #just the first for base
                                self.__profile_action[label_action[0]](dataset=dataset,tag = data_element.tag, history= self.__history)    
                        else:
                             if vr == 'UI':#ui should be replaced anywhere also if not found in the list
                                 self.__replace_UID(dataset=dataset,tag = data_element.tag, history= self.__history)
            except Exception as e:
                self.__logger.error(f"{tag_group},{tag_element}, Error: {e}")



    def __anonymize_dataset(self, dataset: dcm.Dataset) -> None:
        """
        Anonymize a pydicom Dataset by using anonymization rules which links an action to a tag
        :param dataset: Dataset to be anonymize
        """
        self.__sensible_data_to_clean = PREFIX_NAME # 'prof.','dr.']
        self.__preson_name_to_clean = []
        sop_class_uid = str(dataset[0x0008,0x0016].value)
        self.__dictionary_uids[sop_class_uid] = sop_class_uid
        impl_class_uid =str(dataset.file_meta[0x0002,0x0012].value)
        self.__dictionary_uids[impl_class_uid] = SW_UID
        for tag in self.__tags_to_check_by_keep:
       
            group = tag['group']
            elem = tag['element']
            if [group,elem] in dataset:
               
                vr = dictionary_VR(dataset[group,elem].tag)
                value = str(dataset[group,elem].value)     
                if vr == 'PN':
                    cmps = value.strip().split('^')
                    for cmp in cmps:
                        cmp1 = cmp.strip()
                        cmp1s = cmp1.split(' ')          
                        for sub_elem in cmp1s:
                            if sub_elem !="" and sub_elem != " ":
                                self.__preson_name_to_clean.append(cmp.lower())
                                self.__sensible_burning_data.append(value)  
                elif vr == "DA" and len(value)==8:
                    year = value[:4]
                    month = value[4:6]
                    self.__sensible_data_to_clean.append(value)
                    self.__sensible_data_to_clean.append(year)
                    self.__sensible_data_to_clean.append(month)   
                    self.__sensible_burning_data.append(year)
                    self.__sensible_burning_data.append(month)            
                elif vr in ('LO', 'LT', 'SH', 'PN', 'CS', 'ST', 'UT'):    
                    values = value.lower().split()
                    for val in values:
                        self.__sensible_burning_data.append(val)
                        self.__sensible_data_to_clean.append(val) 

                           
        self.__anonymize_dataset_inside(dataset)
        self.__anonymize_dataset_inside(dataset.file_meta)

        if self.__delete_private_tags:
            self.__remove_private_tags(dataset)

            # # Adding back private tags if specified in dictionary
            index = 0
            for private_tag in self.__private_tags:
                index = index +1
                keyword = 'private'+str(index)
                self.__update_history_private(private_tag, self.__default_deleted_string,self.__history,keyword)
        else:
            self.__clean_private_tags(dataset)
        self.__add_deidentification_tags(dataset)


    def __add_deidentification_tags(self, dataset:dcm.Dataset):
        ''' Add the de-identification types into the header
        https://www.dicomstandard.org/News-dir/ftsup/docs/sups/sup142.pdf
        0x00120062 Patient identify removed: yes
        0x00120063 De-identification method: Per DICOM PS3.15 AnnexE. Details in 0012,0064
        0x00120064 De-identification method code sequence
        --> more item s with block 
            0x00080100
            0x00080102
            0x00080104
        '''

      
        group = 0x0012

        dataset.add_new([group,0x0062],VR='CS',value='YES')
        dataset.add_new([group,0x0063],VR='LO',value='Per DICOM PS 3.15 AnnexE. Details in 0012,0064')

        code_value_list_name ={
                            '113100': 'Basic Application Confidentiality Profile',
                            '113101': 'Clean Pixel Data Option' ,
                            '113102': 'Clean Recognizable Visual Features Option',
                            '113103': 'Clean Graphics Option',
                            '113104': 'Clean Structured Content Option',
                            '113105': 'Clean Descriptors Option',
                            '113106': 'Retain Longitudinal Temporal Information Full Dates Option', 
                            '113107': 'Retain Longitudinal Temporal Information Modified Dates Option',
                            '113108': 'Retain Patient Characteristics Option',
                            '113109': 'Retain Device Identity Option',
                            '113110': 'Retain UIDs Option',
                            '113111': 'Retain Safe Private Option',
                            "xxxxxxx": "Retain Institution Identity Option"}
        
        code_value_list_name_action={
                        "base":"113100",
                        "clean_pixel_data_option":"113101",
                        "clean_recognizable_visual_features_option":"113102",
                        "clean_graphics_option":"113103",
                        "clean_structured_content_option":"113104",
                        "clean_descriptors_option":"113105",
                        "retain_longitudinal_temporal_information_with_full_dates_option":"113106",
                        "retain_longitudinal_temporal_information_with_modified_dates_option":"113107",
                        "retain_patient_characteristics_option":"113108",
                        "retain_device_identity_option":"113109",
                        "retain_uid_option":"113110",
                        "retain_safe_private_option":"113111",
                        "retain_institution_identity_option":"xxxxxxx"}

        code_scheme_designator ='DCM'

        


        ds_sequence_list = []
        for action in   self.__profile_anon_action_list:           
            if action in code_value_list_name_action:
                code_value = code_value_list_name_action[action]
                if code_value in  code_value_list_name:
                    code_name = code_value_list_name[code_value]
                    dsSeq = dcm.Dataset()       
                    dsSeq.add_new([0x0008,0x0100],VR='SH',value=code_value)
                    dsSeq.add_new([0x0008,0x0102],VR='SH',value=code_scheme_designator)
                    dsSeq.add_new([0x0008,0x0104],VR='LO',value=code_name )
                    ds_sequence_list.append(dsSeq)


        dataset.add_new([group,0x0064],VR="SQ",value = ds_sequence_list)

        date_value = "REMOVED"
        if DICT_ANON_PROFILE_ACTIONS[7] in self.__profile_anon_action_list:
            date_value = "UNMODIFIED"
        elif DICT_ANON_PROFILE_ACTIONS[8] in self.__profile_anon_action_list:
            date_value = "MODIFIED"
        dataset.add_new([0x0028,0x0303],VR="CS",value = date_value)

        #if retain_longitudinal_temporal_information_with_full_dates_option is present, the adde
        #dataset.add_new([0x0028,0x0303],VR="",value = ds_sequence_list)
        #value = "UNMODIFIED"
        #if retain_longitudinal_temporal_information_with_modified_dates_option value = "MODIFIED"
        #else REMOVED


    async  def __start_process(self, input_folder, output_folder= None, save_changes = True):

        '''
        Old method that ddoes not process the DICOM collection, 
        just all files inside a folder
        '''
        if output_folder is None:
            output_folder = os.path.join(input_folder, 'anonymized')

        csv_folder = os.path.join(output_folder, "csv")

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        if not os.path.exists(csv_folder):
            os.makedirs(csv_folder)

        count = len(os.listdir(input_folder))
        index = 0
        for fname in os.listdir(input_folder):
            file_name = os.path.join(input_folder, fname)
            if os.path.isfile(file_name):
                index +=1
                ds = dcm.dcmread(file_name, force=True)
                self.__anonymize_dataset(ds)
                self.__save_files(ds, output_folder,csv_folder, fname, save_changes)
                self.__reset_dictionaries()
                yield str(index)+'/'+str(count)


    async  def start_process_collection(self, input_folder, output_path= None, save_history = False):
        '''
        Main function that proces a complete dicom collection
        '''       
        dictionary_patient_id = {}
        self.__dictionary_uids = {}
        self.__logger.info(f"Input folder: {input_folder}")
        if output_path is None:
            output_path = f'{input_folder}'
        csv_folder = os.path.join(input_folder, "mappings")
        if not os.path.exists(csv_folder):
            os.makedirs(csv_folder)
        total_count = 0
        collection =  DcmCollection(input_folder)
        if collection.Enable:
            ratio_score = 49
            self.__logger.info(f"Text detection started with score {ratio_score}")   
            collection.Loading()
            self.__logger.info("================Process started")
            
            ix_pat = 0
            for patient in collection.Patients:
            
                #get new patient name and ID
                ix_pat +=1
                pat_name = self.__generate_patient_name()
                pat_id = self.__generate_patient_id()
                self.__logger.info(f"========== started with new patients: old_id: {patient.PatientID}, new_id: {pat_id} ==========")
                dictionary_patient_id[patient.PatientID] = pat_id
                try:

                    #=== need to set the given value for Patient in the rule    
                    # self.__extra_rules[(0x0002,0x0012)] = self.__replace_element_with_given_value 
                    # self.__extra_replacement_values[(0x0002,0x0012)] = SW_UID
                    self.__extra_rules[(0x0002,0x0013)] = self.__replace_element_with_given_value 
                    self.__extra_replacement_values[(0x0002,0x0013)] = SW_VERSION
                    self.__extra_rules[(0x0010,0x0010)] = self.__replace_element_with_given_value 
                    self.__extra_replacement_values[(0x0010,0x0010)] = pat_name
                    self.__extra_rules[(0x0010,0x0020)] = self.__replace_element_with_given_value 
                    self.__extra_replacement_values[(0x0010,0x0020)] = pat_id   
                    
                    ix_stud = 0           
                    for study in patient.Studies:
                        ix_stud += 1
                        study.sort_serie_by_modalities()
                        study_uid = self.__generate_studyUID()
                        self.__dictionary_uids[study.StudyInstanceUID]= study_uid                           
                        ix_serie = 0
                        for serie in study.Serie:
                            ix_serie +=1
                            serie_uid = f"{study_uid}.{ix_serie}"
                            self.__dictionary_uids[serie.SerieInstanceUID]= serie_uid
                       
                            ix_inst = 0
                            for instance in serie.Instances:
                                try:
                                    
                                    total_count +=1
                                    ix_inst +=1
                                    instanceUID = f"{serie_uid}.{ix_inst}"
                                    self.__dictionary_uids[instance.SopInstanceUID]= instanceUID                                   
                                    self.__anonymize_dataset(instance.DataSet)
                                    self.__sensible_burning_data = ' '.join(self.__sensible_burning_data).replace('^',' ').lower().split()
                                    self.__sensible_burning_data = list(set(self.__sensible_burning_data))
                                    self.__sensible_burning_data.append('dob')
                                    self.__sensible_burning_data.append('[m]')  # why this string ? as birth date?
                                    self.__sensible_burning_data.append('[f]')
                                    self.__sensible_burning_data.append('[o]')
                                    self.__sensible_burning_data.append('[u]')
                                    self.__sensible_burning_data.append('[mi]')#confused by [m]
                                    if self.__detect_text == True:
                                        self.__execute_text_detection(instance.DataSet, ratio_score)                                       
                                    instance_path = os.path.join( f"{pat_id}", study_uid,serie_uid)
                                    out_file_folder = os.path.join(output_path,"data",instance_path)                          
                                    if not os.path.exists(out_file_folder):
                                        os.makedirs(out_file_folder)
                                    
                                    #inst_name= f"instance{str(ix_inst).zfill(3)}.dcm"  not used, decided to use the same name
                                    self.__save_files(instance.DataSet, out_file_folder,csv_folder, instance.FileName, save_history)                    
                                    self.__reset_dictionaries()
                                except Exception as e:
                                    self.__logger.error(f"Error has happened fo the {instanceUID} \n exception: {e}")                                                 
                        self.__logger.info(f"old:{serie.SerieInstanceUID}; new {serie_uid} serie has been anonimized")
                    self.__logger.info(f"old:{study.StudyInstanceUID}; new {study_uid} study has been anonimized")   
                
                except Exception as e:
                    self.__logger.error(f"Error has happened {e}")
                    self.__logger.error(f"old:{serie.SerieInstanceUID}; new {serie_uid} serie has been anonimized")     
                
                yield f"Patient nr. {ix_pat}; ID: {pat_id} completed"
                self.__logger.info(f"========== completed patient nr.{ix_pat}; ID: {pat_id} completed ==========")

        #now saving all uid
            uid_mapping_file = os.path.join(csv_folder,f'uid_mapping.csv')
         
            with open(uid_mapping_file, "w", newline='') as f:
                writer = csv.writer(f, delimiter =',')
                writer.writerow(["id_old","id_new"])
                for key, value in self.__dictionary_uids .items():
                    if key != value:
                        writer.writerow([key, value])

            patient_id_mapping_file = os.path.join(csv_folder,f'patient_id_mapping.csv')
            with open(patient_id_mapping_file, "w", newline='') as f:
                writer = csv.writer(f, delimiter =',')
                writer.writerow(["id_old","id_new"])
                for key, value in dictionary_patient_id .items():
                    writer.writerow([key, value])
        self.__logger.info(f"=================Process completed for total files: {total_count}")              
            
           
   
    def __save_dicom(self,dataset, file_out_dcm):
        """Save the de-identified dtaset
        """
        
        dataset.save_as(file_out_dcm)
    

    def __save_history(self,file_out_csv):
        """Save all values deidentified
            Used just if explicit request         
        """       
        with open(file_out_csv, "w") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["group", "element", "vr", "name", "value", "new value"])
            for item in self.__history:
                writer.writerow(self.__history[item])
        
    def __save_files(self, dataset,output_folder, output_csv_folder,current_filename, save_history):
        """Save the deidentified files and the csv
        """
        
        self.__history = OrderedDict(sorted(self.__history.items(), key=(lambda k: (k[1][0], k[1][1]))))
        file_out_dcm = os.path.join(output_folder, current_filename)
        self.__save_dicom(dataset, file_out_dcm)
        if save_history:
            file_out_csv = os.path.join(output_csv_folder, current_filename +'.csv')
            self.__save_history(file_out_csv)

    def __reset_dictionaries (self):
        self.__private_tags = []
        self.__history = {}
        self.__sensible_burning_data= []

    def __execute_text_detection(self, ds,  ratio_score):
        """Detects the text on the pixel data
        ratio_score: the matching score used by theFuzz
        """
        modality = ds.Modality
       
        if not [0x7FE0,0x0010] in ds:
            self.__logger.info(f'Pixel data not present. The modality is: {modality}') 
            return
        if  PET_SOP_IMAGE_STORAGE in str(ds[0x0008,0x0016].value) :
            self.__logger.info(f'SOP Pixel data not supported. The sop is: {str(ds[0x0008,0x0016].value)}') 
            return
        modalities_not_supported =['CT', 'MR']#The OCR doe not work very well with these modalities
        if modality in modalities_not_supported:
            return
        try:
            original_transferx_syntax = ds.file_meta.TransferSyntaxUID   
            if UID(original_transferx_syntax).is_compressed:
                #the pydicom is not able to recompress the file into the orginal TX
                self.__logger.warning(f"Compressed transfer syntax {original_transferx_syntax} not supported")     
                return   
        
            (frames_image_data, number_of_frames, new_mask_value) = get_preview_imagedata(ds)
            if frames_image_data is None:
                self.__logger.warning(f"Unable to decode the pixel data.")  
                return

            if number_of_frames>1:
                img = skimage.color.gray2rgb(frames_image_data[0])
                self.__logger.info(f'This instance contains {number_of_frames} frames')
            else:
                img = skimage.color.gray2rgb(frames_image_data)
            # Prediction_groups is a list of (word, box) tuples
            prediction_groups = self.__kera_pipeline.recognize([img])
            
            # predictions = [] #prediction_groups[0]
            previsioni = []
            #check prediction:
            for pred in prediction_groups[0]:
                
                val = pred[0].strip()
                if len(val) <3:
                    if  "m" in val or  "f" in val  or val == "o" or val == "u" or val =="[" or val == "]": 
                        # predictions.append(pred)
                        previsioni.append(pred)
                elif len(val)>2:
                    # predictions.append(pred)
                    previsioni.append(pred)

            count_predictions_found = len(previsioni[:])
            if count_predictions_found>0:
                valid_predictions = {}
                label_valid = []
                for sens_data in  self.__sensible_burning_data:
                    for prediction in previsioni:
                        current_score = 0
                        current_label = prediction[0]
                        if(len(sens_data.strip())==1):
                            if(len(current_label.strip())==1):
                                current_score = fuzz.token_sort_ratio(current_label, sens_data)
                            else:
                                continue
                        else:
                            current_score = fuzz.token_sort_ratio(current_label, sens_data)

                        if current_score>ratio_score:
                            valid_predictions[current_label]=prediction[1]
                            label_valid.append(current_label)
                        # break                   
                if len(label_valid)>4:  
                    self.__logger.info(f'Found {len(label_valid)} valid predictions modality [{modality}]')       
                    self.__logger.info(f'Instance [{str(ds[0x0008,0x0018].value)}]')     
                    ds = mask_dicom_file(ds,new_mask_value,valid_predictions,number_of_frames)
        except Exception as e:
            self.__logger.error(f"{e} instance: {str(ds[0x0008,0x0018].value)}")
  