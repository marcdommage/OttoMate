
import glob
import os
import shutil
import re
import threading
import time


import pandas as pd

import PyPDF2
import numpy as np
import ujson
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from termcolor import colored, cprint

except ImportError as e:
    print(f'[!] Missing packages, Please install them using pip command\n{e}')

month_dict = {
    'janvier': '01',
    'février': '02',
    'mars': '03',
    'avril': '04',
    'mai': '05',
    'juin': '06',
    'juillet': '07',
    'août': '08',
    'septembre': '09',
    'octobre': '10',
    'novembre': '11',
    'décembre': '12'
}


print("[*] Getting Chrome driver ready\n")
map_fiscal_nom = {}

def check_if_idf_or_not(data):
    s = data.split("\n")[-1].split(" ")[0]
    return s[:2] in ["75", "77", "78", "91", "92", "93", "94", "95"]

def calculate_category(user_data):
    if check_if_idf_or_not(user_data['address']):
        df = pd.read_csv("social_help_idf.csv")
        # print("In IDF")
    else:
        df = pd.read_csv("social_help_hors_idf.csv")
        # print("Not in IDF")
    personneACharge = user_data['personneCharge']
    rangeRevenu = [x for x in df.values if x[0] == str(personneACharge)][0]
    array = np.array([int(value[1:]) if value.startswith('≤') else int(value[1:]) + 1 for value in rangeRevenu[1:]])
    category_index = np.searchsorted(array, user_data['numFiscaleReference'])
    if category_index == 0:
        category = "Revenu tres modeste"
    elif category_index == 1:
        category = "Revenu modeste"
    elif category_index == 2:
        category = "Revenu intermediaires"
    else:
        category = "Revenu haut"
    return category


def getPersonneACharge(user_data):
    if 'numFiscaleSecond' in user_data :
        c = 2
        if float(user_data['part']) == 2:
            return c+0
        elif float(user_data['part']) == 2.5:
            return c+1
        elif float(user_data['part']) == 3:
            return c+2
        elif float(user_data['part']) == 4:
            return c+3
        else:
            c+=3
            c+= (float(user_data['part'])-4)
            return c
    else:
        c=1
        if float(user_data['part']) == 1:
            return c+0
        elif (float(user_data['part']) == 1.5) or (float(user_data['part']) == 1.25):
            return c+1
        elif float(user_data['part']) == 2:
            return c+2
        elif float(user_data['part']) == 3:
            return c+3
        else:
            c+=3
            c+= (float(user_data['part'])-3)
            return c

def check_if_castable_to_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
def check_if_castable_to_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False
def get_pdf(numFiscale, pwd, pathOutput):
    user = {}
    outputDir = f"{pathOutput}/{numFiscale}"
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs', {
        "download.default_directory": outputDir, #Change default directory for downloads
        "download.prompt_for_download": False, #To auto download the file
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True #It will not show PDF directly in chrome
    })
    if os.path.isfile("/usr/local/bin/chromedriver"):
        chromeBrowser = webdriver.Chrome(options=options)
    else:
        chromeBrowser = webdriver.Chrome(service=Service(ChromeDriverManager().install(),0,None,None), options=options)
    baseUrl = "https://cfspart.impots.gouv.fr/LoginAccess"
    chromeBrowser.get(baseUrl)
    time.sleep(2)
    numFiscaleInput = chromeBrowser.find_elements(By.NAME,"spi_tmp")
    btnContinuer = chromeBrowser.find_elements(By.ID,"btnAction")
    numFiscaleInput[0].send_keys(numFiscale)
    btnContinuer[0].click()
    time.sleep(2)
    pwdInput = chromeBrowser.find_elements(By.NAME,"pwd_tmp")
    try:
        pwdInput[0].send_keys(pwd)
    except:
        print(f"Num fiscale {numFiscale} not good..Returning")
        return
    btnContinuer[0].click()
    time.sleep(5)
    if chromeBrowser.current_url == baseUrl:
        print(f"Login did not succeed for {numFiscale}..Returning")
        return
    avisImpotFound = False
    taxeFonciere = False
    buttonFermer = chromeBrowser.find_element(By.ID,"fermer")
    try:
        if buttonFermer:
            buttonFermer.click()
    except:
        pass
    Path(outputDir).mkdir(parents=True, exist_ok=True)
    for i in range(20):
        pdfButton = chromeBrowser.find_elements(By.ID,"id_zoneclick_{}".format(str(i)))
        if pdfButton:
            if not avisImpotFound and "impôt" in pdfButton[0].get_property("title") and "2023" in pdfButton[0].get_property("title") and "revenus" in pdfButton[0].get_property("title"):
                pdfButton[0].click()
                time.sleep(1)
                while [file for file in os.listdir(f"{pathOutput}/{numFiscale}") if file.endswith('.crdownload')]:
                    a=0
                avisImpotFound = True
            if not taxeFonciere and (("Avis de taxes foncières 2023" in pdfButton[0].get_property("title")) or ("Avis de taxe d'habitation" in pdfButton[0].get_property("title")) or ("taxe" in pdfButton[0].get_property("title") and "habitation" in pdfButton[0].get_property("title")) or ("taxe" in pdfButton[0].get_property("title") and "fonci" in pdfButton[0].get_property("title"))):
                pdfButton[0].click()
                time.sleep(1)
                while [file for file in os.listdir(f"{pathOutput}/{numFiscale}") if file.endswith('.crdownload')]:
                    a=0
                taxeFonciere = True
            # break
        else:
            break
        if avisImpotFound and taxeFonciere:
            break
    if not avisImpotFound:
        print(f"Avis d'impot non trouve pour {numFiscale}")
        return
    if not taxeFonciere:
        print(f"Taxe Fonciere non trouve pour {numFiscale}")
        return
    chromeBrowser.get("https://cfspart.impots.gouv.fr/enp/ensu/chargementprofil.do")
    time.sleep(2)
    user['birth'] = chromeBrowser.find_element(By.ID,"datenaissance").text
    monthNumber = month_dict[user['birth'].split(" ")[1]]
    year = user['birth'].split(" ")[2]
    day = user['birth'].split(" ")[0]
    if int(day) < 10:
        day = "0"+day
    user['birth'] = day+monthNumber+year
    user['nom'] = chromeBrowser.find_element(By.ID,"nom").text
    user['prenom'] = chromeBrowser.find_element(By.ID,"prenom").text
    user['address'] = chromeBrowser.find_element(By.ID,"adressepostale").text
    user['numFiscale'] = numFiscale
    with open("map_fiscale_nom_prenom.json", "w") as file:
        ujson.dump(map_fiscal_nom, file, indent=4)
    revenuFiscale = None
    if avisImpotFound:
        starting_string = f"{outputDir}"
        file_path = glob.glob(starting_string+"/*.pdf")
        file_path = [x for x in file_path if "impot" in x]
        if file_path:
            with open(file_path[0], 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                try:
                    revenuFiscale = reader.pages[0].extract_text().split("impots.gouv.fr.")[-1].split('\n')[0].replace(" ","")
                    if not check_if_castable_to_int(revenuFiscale):
                        revenuFiscale = ''.join(re.findall(r'\d+',reader.pages[0].extract_text().split("\n")[-2]))
                    pattern = r'\d{2} \d{2} \d{3} \d{3} \d{3}'
                    matches = re.findall(pattern, reader.pages[0].extract_text())
                    if matches and len(matches) == 2:
                        if numFiscale == matches[1].replace(" ",""):
                            user['numFiscaleSecond'] = matches[0].replace(" ","")
                        else:
                            user['numFiscaleSecond'] = matches[1].replace(" ","")
                    nbPart = reader.pages[0].extract_text().split("impots.gouv.fr.")[-1].split('\n')[-1].replace(",",".")
                    if not check_if_castable_to_float(nbPart):
                        print(f"Error while retrieving the nombre of part from numFiscale {numFiscale}")
                    else:
                        user['part'] = str(nbPart)
                        user['personneCharge'] = getPersonneACharge(user)
                except:
                    pass
                if not revenuFiscale:
                    print(f"{numFiscale} alias {user['nom']} pas trouver revenu fiscale de ref")
            user['numFiscaleReference'] = str(revenuFiscale)
            with open(f"{outputDir}/user_data.json", "w") as file:
                ujson.dump(user, file, indent=4)
            os.rename(outputDir,f"{pathOutput}/{user['nom']}_{user['prenom']}")
            if revenuFiscale:
                shutil.move(f"{pathOutput}/{user['nom']}_{user['prenom']}", pathOutput+f"/{calculate_category(user)}")
        else:
            print(f"Path to avis d'impot not found for {user['nom']}:{user['numFiscale']}")
    else:
        with open(f"{outputDir}/user_data.json", "w") as file:
            ujson.dump(user, file, indent=4)
        os.rename(outputDir,f"{pathOutput}/{user['nom']}_{user['prenom']}")



choices = input("Enter 1 if you want to run script with only one credentials and 2 for multiple\n")
if choices == "2":
    path_to_log = input("Enter path to the file containing credentials\n")
path_to_output = input("Enter path to result\n")
Path(path_to_output+"/Revenu tres modeste").mkdir(parents=True, exist_ok=True)
Path(path_to_output+"/Revenu modeste").mkdir(parents=True, exist_ok=True)
Path(path_to_output+"/Revenu intermediaires").mkdir(parents=True, exist_ok=True)
Path(path_to_output+"/Revenu haut").mkdir(parents=True, exist_ok=True)
if choices == "2":
    db = {}
    for d in open(path_to_log, "r"):
        db[d.split(":")[0]] = d.split(":")[1].rstrip()

    batch_size = 10
    data_batches = [dict(list(db.items())[i:i+batch_size]) for i in range(0, len(db), batch_size)]

    # Create and start a thread for each entry in the db dictionary
    for i in data_batches:
        threads = []
        for k in i:
            thread = threading.Thread(target=get_pdf, args=(k, i[k], path_to_output))
            thread.start()
            threads.append(thread)

        # # # Wait for all threads to complete
        for thread in threads:
            thread.join()

else:
    numFiscale = input('Enter your number fiscale')
    pwd = input('Enter your password')
    get_pdf(numFiscale=numFiscale, pwd=pwd, pathOutput=path_to_output)

for root, dirs, files in os.walk(path_to_output, topdown=False):
    for dir in dirs:
        dir_path = os.path.join(root, dir)
        if not os.listdir(dir_path):
            os.rmdir(dir_path)

