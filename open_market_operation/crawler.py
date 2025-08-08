from functions import *
import os
import tempfile
import shutil
import time
from fastapi.responses import JSONResponse
from typing import Optional

def crawl(last_crawl: Optional[str] = None):

    download_path = os.path.join(os.getcwd(), "data")
    csv_name = "omo_data.csv"
    url = os.getenv("STATEBANK_URL")

    if last_crawl != None:
        last_crawl = datetime.datetime.strptime(
            last_crawl, '%Y-%m-%d'
        ).strftime("%d/%m/%Y")
        date_list = get_date_intervals(start_date=last_crawl, end_date=today, intervals=30)
    else:
        date_list = get_date_intervals(intervals=30)

    new_omo_table = pd.DataFrame()

    # Launch driver, try again if blocked   
    for i in range(0, len(date_list)-1):
        end = date_list[i]
        start = date_list[i+1]
        while True:
            
            # Set crawler options
            options = webdriver.ChromeOptions()
            prefs = {
                "download.default_directory" : download_path,
                "download.prompt_for_download": False,
                'profile.default_content_setting_values.automatic_downloads': 1
            }

            # temp_user_data_dir = tempfile.mkdtemp()
            # options.add_argument(f"--user-data-dir={temp_user_data_dir}")

            options.add_experimental_option("prefs",prefs)
            options.add_argument("--window-size=1920,1080")
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--headless=new')
            # options.add_argument('--disable-gpu')             # Optional
            # options.add_argument('--disable-features=TranslateUI')  # Remove extra noise
            # options.add_argument('--disable-features=NetworkService')
            # options.add_argument("--disable-notifications")
            options.binary_location = os.getenv("CHROME_BIN")
            service=ChromeService(
                executable_path=os.getenv("CHROMEDRIVER_PATH")
            )

            print(f"Crawling from {start} to {end}")
            driver=None

            try:
                driver=webdriver.Chrome(service=service, options=options)
                driver.get(url)
                wait=WebDriverWait(driver, 30)
                wait.until(
                    EC.visibility_of_element_located((By.XPATH, '//*[contains(@id, "region:id1::content")]'))
                )

                look_up(driver, start_date=start, end_date=end) # NOTE remember to change this

                reports=html_crawler(driver, wait) # Crawl new report list
                # Click View on each report
                report_ids = [id.get_attribute("id") for id in reports]

                for report_id in report_ids:
                    try:    
                        view_html=wait.until(EC.element_to_be_clickable(
                            (By.ID, report_id)
                        ))
                        driver.execute_script("arguments[0].scrollIntoView(true);", view_html) # Scroll to the View button
                        view_html.click()
                        
                        time.sleep(2) # To stablize the site

                        html_io = StringIO(driver.page_source)
                        table = pd.read_html(html_io, thousands=".", decimal=",")
                        
                        # Process the table
                        omo_table = table[7].dropna(how="all").reset_index(drop=True)\
                            .iloc[3:-2].reset_index(drop=True)
                        
                        day, month , year = re.findall(r"\d+", omo_table.iloc[0,0])
                        crawling_date = datetime.datetime(year=int(year), month=int(month), day=int(day))
                        last_crawl_date = datetime.datetime.strptime(last_crawl, "%d/%m/%Y")

                        if last_crawl != None:
                            last_crawl_date = datetime.datetime.strptime(last_crawl, "%d/%m/%Y")
                            if crawling_date <= last_crawl_date:
                                break
                    
                        omo_table.columns = list(omo_table.iloc[1,:].values)
                        omo_table = omo_table.assign(
                            date = lambda df : df.iloc[0,0]
                        ).drop([0, 1]).reset_index(drop=True)

                        # Differenciate buy and sell order
                        b, s = buy_sell_index(omo_table.iloc[:,0])
                        omo_table.iloc[b+1:s, 0] = omo_table.iloc[b, 0] + " " + omo_table.iloc[b+1:s, 0]
                        if s is not None:
                            omo_table.iloc[s+1:, 0] = omo_table.iloc[s, 0] + " " + omo_table.iloc[s+1:, 0]
                        
                        omo_table.columns = ["side", "participants", "volume", "interest", "interest.1", "date"]
                        # Data standardizing
                        omo_table = omo_table.drop("interest.1", axis=1)[["date", "side", "participants", "volume", "interest"]].assign(
                            date = lambda df : df["date"].apply(format_datetime).dt.strftime("%Y-%m-%d"),
                            volume = lambda df : pd.to_numeric(df["volume"], errors='coerce'),
                            interest = lambda df : pd.to_numeric(df["interest"], errors='coerce')/100
                            # NOTE Có phiên outlier: Bán hẳn - Kỳ hạn 7,Phiên 1: 10/10; Phiên 2: 11/11,"Phiên 1: 50.000,0; Phiên 2: 9.999,7","Phiên 1: 3,98 %; Phiên 2: 5%","Phiên 1: 3,98 %; Phiên 2: 5%",Ngày 19 tháng 10 năm 2022
                        ).dropna(subset=["participants", "volume", "interest"], how="all")
                        omo_table[["participants", "complete"]] = omo_table["participants"].str.split("/", expand=True, n=1) # Split participant column
                        omo_table[["side", "maturity"]] = omo_table["side"].str.split(' - ', expand=True, n=1)
                        omo_table["maturity"] = omo_table["maturity"].apply(
                            lambda x: int(re.findall(r"\d+", str(x))[0]) if re.findall(r"\d+", str(x)) else None
                        )
                        omo_table = omo_table[["date", "side", "maturity", "participants", "complete", "volume", "interest"]]\
                            .reset_index(drop=True) # Rearrange columns, for fun

                        new_omo_table = pd.concat([new_omo_table, omo_table], axis=0)
                        # init_omo_table.to_csv(csv_name, encoding="utf-8", index=False)

                        # Go back to report list page
                        return_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//a[contains(@id, ":j_id__ctru11pc9")]')
                            )
                        )
                        return_button.click() # Return to list view

                    except Exception as error:
                        print(error)

                        return_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//a[contains(@id, ":j_id__ctru11pc9")]')
                            )
                        )
                        return_button.click() # Return to list view if errors

                break # Break if done successfully
            except Exception as error:
                print(error)
                print("Restarting Driver...")
                time.sleep(2)
                pass
            finally:
                if driver:
                    driver.quit()

    if driver:
        driver.quit()
    return(
        JSONResponse(
            content=new_omo_table.fillna("NA").to_dict(orient="records")
        )
    )