import os
import pydicom as dcm
import logging

class DcmInstance:
    def __init__(self, img):   
        dataset = img['data']
        self.SopInstanceUID = dataset[0x0008, 0x0018].value
        self.FileName = img['name']
        self.FilePath = img['path']
        self.DataSet = dataset
    

class DcmSerie:
    def __init__(self, img):
        dataset = img['data']
        modalities = {'RTSTRUCT':2,'RTPLAN':3, 'RTDOSE':4, 'RTIMAGE':5, 'SEG':6}
        self.SerieInstanceUID =  dataset[0x0020, 0x000e].value
        self.Modality = dataset.Modality
        self.Order = 1
        if self.Modality in modalities:
            self.Order = modalities[self.Modality]
        self.Instances : list[DcmInstance] =[]
        self.Instances.append(DcmInstance(img))

    def BelongTo(self,dataset):
        return dataset[0x0020, 0x000e].value== self.SerieInstanceUID 
    
    def add_item(self,img):  
        dataset = img['data']
        for instance in self.Instances:
            if instance.SopInstanceUID == dataset[0x0008, 0x0018].value:
            #already present
                return
            
        self.Instances.append(DcmInstance(img))
                
    def instances_count(self):
        return len(self.Instances)

class DcmStudy:
    def __init__(self, img):
        dataset = img['data']
        self.StudyInstanceUID =  dataset.StudyInstanceUID 
        self.Serie : list[DcmSerie]=[]
        self.Serie.append(DcmSerie(img))

    def BelongTo(self,dataset):
        return dataset.StudyInstanceUID == self.StudyInstanceUID 
    
    def add_item(self,img):
        dataset = img['data']  
        for serie in self.Serie:
            if serie.BelongTo(dataset):
                serie.add_item(img)
                return
        self.Serie.append(DcmSerie(img))
    
    def serie_count(self):
        return len(self.Serie)
    
        
    def sort_serie_by_modalities(self, reverse_order = False):
        self.Serie = sorted(self.Serie, key=lambda s: s.Order, reverse=reverse_order)  



class DcmPatient :
    def __init__(self, img):
        dataset = img['data']       
        self.PatientName = ""
        self.PatientID = ""
        if [0x0010,0x0010] in dataset:
            self.PatientName = dataset.PatientName.alphabetic
            
        if [0x0010,0x0020] in dataset:
              self.PatientID = dataset.PatientID
              
        self.Studies : list[DcmStudy] = []
        self.Studies.append(DcmStudy(img))

    def BelongTo(self,dataset):
        
        if [0x0010,0x0010] in dataset and  [0x0010,0x0020] in dataset:
            return dataset.PatientName.alphabetic == self.PatientName and dataset.PatientID == self.PatientID 
            
        elif [0x0010,0x0010] not in dataset and  [0x0010,0x0020] in dataset:
            return dataset.PatientID == self.PatientID
        elif [0x0010,0x0010] in dataset and  [0x0010,0x0020] not in dataset:
            return dataset.PatientName.alphabetic == self.PatientName 
        elif [0x0010,0x0010] not in dataset and  [0x0010,0x0020] not in dataset:
            return False    
        else: 
            return False
    
    def add_item(self,img):  
        dataset = img['data']
        for study in self.Studies:
            if study.BelongTo(dataset):
                study.add_item(img)
                return
        
        self.Studies.append(DcmStudy(img))      
    
    def studies_count(self):
        return len(self.Studies)

class DcmCollection:

    
    def patients_count(self):
        return len(self.Patients)

    def __init__(self, dicom_path):
        self.__logger = logging.getLogger(__name__)
        self.NuberOfFilesParsed = 0
        self.NuberOfFilesFailed = 0
        self.Patients: list[DcmPatient] =[]
        self.ImageList = []
        self.Enable = False
        self.__parse_images(dicom_path)
        self.Enable = True
        self.__logger.info(f"Parsed: {self.NuberOfFilesParsed} of files for {self.patients_count()} patients")

    def __add_item(self,img):
        dataset = img['data']
        for pat in self.Patients:
            if pat.BelongTo(dataset):
                pat.add_item(img)
                return       
        self.Patients.append(DcmPatient(img))

    def __parse_images(self, dicom_path):        

        for fname in os.listdir(dicom_path):
            file_name = os.path.join(dicom_path, fname)
            if os.path.isfile(file_name):               
                try:
                    self.ImageList.append({'name': fname, 'data': dcm.dcmread(file_name), 'path':dicom_path})
                    self.NuberOfFilesParsed+=1
                except Exception as e:
                    self.__logger.error(f'Unable to parse the: {fname} exception \n  {e}')
                    self.NuberOfFilesFailed +=1
            else:
                self.__parse_images(file_name)
     

    def Loading (self):
        for img in self.ImageList:
            try :
                self.__add_item(img)
            except Exception as e:  
                self.__logger.error(f"Error happened for {img['name']} \n exception {e}")
  

