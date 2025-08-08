from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService

from io import StringIO
import glob
from datetime import datetime
import pandas as pd
import os
import datetime
import time
from tqdm import tqdm
import difflib
import re

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

download_path = os.path.join(os.getcwd(), "data")
today = datetime.datetime.now().date().strftime(format="%d/%m/%Y")

def format_datetime(datestring):
    day, month, year = map(int, re.findall(r"\d+", datestring))
    return datetime.datetime(year=year, month=month, day=day)

def crawler(driver, wait):
    '''
    Get all report pubish dates and report download clickable elements
    Params:
        driver: Web driver
        wait: A WebDriverWait() object
    Output:
        reports: List of id of reports elements
        report_dates: List of publish dates
    '''

    wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, '//a[contains(@id, "region:t1:") and contains(@id, ":cl3")]')
        )
    )

    reports = driver.find_elements(
        By.XPATH,
        '//a[contains(@id, "region:t1:") and contains(@id, ":cl3")]'
    )
    report_dates = driver.find_elements(
        By.XPATH,
        '//span[contains(@id, "region:t1:") and contains(@id, ":content") and contains(@class, "x2b")]'
    )
    return reports, report_dates

def html_crawler(driver, wait):
    '''
    Get all View report HTML clickable elements
    Params:
        driver: Web driver
        wait: A WebDriverWait() object
    Output:
        reports: List of id of reports clickable elements
    '''

    wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, '//a[contains(@id, "region:t1:") and contains(@id, ":j_id__ctru36pc9")]')
        )
    )

    reports = driver.find_elements(
        By.XPATH,
        '//a[contains(@id, "region:t1:") and contains(@id, ":j_id__ctru36pc9")]'
    )
    
    return reports

def look_up(driver, start_date="01/01/2016", end_date=today):
    '''
    Type start date and end date into the look up field, and click search. The end date defaults to today
    Params:
        start_date: should be formatted as %d/%m/%Y
    Output:
        Query the desired date range    
    '''
    action = ActionChains(driver)
    action.move_to_element(
        driver.find_element(By.XPATH, '//*[contains(@id, "region:id1::content")]')
    ).click().send_keys(start_date).perform()
    action.move_to_element(
        driver.find_element(By.XPATH, '//*[contains(@id, "region:id4::content")]')
    ).click().send_keys(end_date).perform()
    driver.find_element(By.XPATH, '//*[contains(@id, "region:cb1")]').click()

def get_date_intervals(
        end_date=datetime.datetime.now().date().strftime(format="%d/%m/%Y"), 
        start_date="01/01/2016", 
        intervals=30
    ):
    '''
    Params:
        end_date: the latest date in the range, formated as %d/%m/%Y, defaults to today
        start_date: the furthest to reach, defaults to 2016
    '''
    end_date=datetime.datetime.strptime(end_date, "%d/%m/%Y").date()
    start_date=datetime.datetime.strptime(start_date, "%d/%m/%Y").date()
    periods=[]
    periods.append(end_date)

    while periods[-1]>=start_date:
        periods.append(periods[-1]-datetime.timedelta(days=intervals))
    return [datetime.datetime.strftime(periods[i], "%d/%m/%Y") for i in range(0, len(periods))]
# Change file name to its publish date
# This will be done after all files is downloaded

def rename_files(download_path=download_path):
    for file in [
        xlsx for xlsx in os.listdir(download_path) if not xlsx.startswith("omo") and xlsx.endswith(".xlsx")
    ]:
        file_path = os.path.join(os.getcwd(), "data", file)
        excel = pd.read_excel(
                file_path,
                pd.ExcelFile(file_path).sheet_names[0],
                header = None,
                engine = "openpyxl"
            )
        file_name = str(datetime.datetime.strptime(excel.iloc[1,1], "%d/%m/%Y").date())
        
        # Rename files
        try:
            os.rename(
                file_path,
                os.path.join(os.getcwd(), "data", f"omo-data-{file_name}.xlsx")
            )
        except Exception as error:
            print(error)
            os.remove(file_path)
            pass

def is_ky_han(s):
    return bool(re.search(r"kỳ\s*hạn", s, re.IGNORECASE))

def extract_row(list:list, report_year:int, report_month:int, report_day:int, transaction_type:str):
    rows = []
    i = 0
    while i < len(list):
        text = list[i]
        if is_ky_han(text):
            rows.append({
                "thoi_gian":datetime.datetime(year=report_year, month=report_month, day=report_day),
                "hinh_giao_dich":transaction_type,
                "ky_han":list[i],
                "thamgia_vs_trung":list[i+1],
                "khoi_luong_ty_vnd":list[i+2],
                "lai_suat":list[i+3]
            })
            i+=4
        else:
            i+=1
    return rows    

def fuzzy_index(text:str, data_list:list, cutoff = 0.9):
    '''
    Fuzzy find the index of the given text within a list
    Args:
        text: The text to look up in the list
        data_list: The list to look up
        cutoff: How similar the text in the list should look like the input text (Default: 70%)
    Output:
        Index of the given text in the list
    '''
    matches = difflib.get_close_matches(text, data_list, n=1, cutoff=cutoff)
    if matches:
        return data_list.index(matches[0])
    else:
        return
    
def buy_sell_index(series : pd.Series):
    """
    Find the indices of 'Mua' and 'Bán' in a pandas Series.

    Parameters
    ----------
    series : pd.Series
        A pandas Series containing strings where the function searches for 
        the keywords 'Mua' and 'Bán'.

    Returns
    -------
    tuple of int
        A tuple (buy_index, sell_index) indicating the positions of 'Mua' and 'Bán' in the Series.
        If either 'Mua' or 'Bán' is not found, returns -1.
    """
    buy_index = None
    sell_index = None

    for index, item in enumerate(list(series)):
        if "mua" in item.lower():
            buy_index = index
        if "bán" in item.lower():
            sell_index = index
        
    if buy_index is None and sell_index is None:
        return None
    
    return buy_index, sell_index
