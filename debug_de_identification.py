## rtdicomexplorer@gmail.com 30.09.2024
from deep_de_identification import DicomDeIdentification
from datetime import datetime
import asyncio
import time
import logging
logger = logging.getLogger(__name__)
log_file_name = f"{datetime.now().strftime('%Y%m%d')}.log"

input_data_folder =  r'C:\challenge_testdata\input_data'
rules_file = './custom_rules.json'
basic_profile_file = './base_anonymization_profile.csv'

execute_text_detection = False
async def main():
 
    logging.basicConfig(filename=log_file_name, encoding='utf-8', level=logging.DEBUG, 
                    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt='%Y%m%d %H:%M:%S')
    anon = DicomDeIdentification(profile_file_name=basic_profile_file, detect_text=execute_text_detection, delete_private_tags=True, json_file_rules=rules_file)
    async for result in anon.start_process_collection(input_folder= input_data_folder):
             print(result)


if __name__ == "__main__":
    st = time.time()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main()) 
    et = time.time()
    elapsed_time = et - st
    print(f'Execution time: {elapsed_time} seconds')