"""
shoalhaven_da_scraper_v2.py
Collects DA records from Shoalhaven City Council (01/09/2025 - 30/09/2025)
Generates results.csv with required challenge headers.
"""

import csv
import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
from webdriver_manager.chrome import ChromeDriverManager

# ------------------- CONFIG -------------------
URL = "https://www3.shoalhaven.nsw.gov.au/masterviewUI/modules/ApplicationMaster/Default.aspx"
DATE_FROM = "01/09/2025"
DATE_TO = "30/09/2025"
OUTPUT_FILE = "results.csv"

FIELDS = [
    "DA_Number",
    "Detail_URL",
    "Description",
    "Submitted_Date",
    "Decision",
    "Categories",
    "Property_Address",
    "Applicant",
    "Progress",
    "Fees",
    "Documents",
    "Contact_Council",
]

WAIT_SHORT = 5
WAIT_MED = 12

# -----------------------------------------------

def launch_browser(headless=True):
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1600,1200")
    opts.add_argument("--disable-gpu")
    opts.add_argument("user-agent=Mozilla/5.0 Chrome/120.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.set_page_load_timeout(60)
    return driver

def click_when_ready(driver, xpath, timeout=WAIT_MED):
    try:
        elem = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        elem.click()
        return True
    except Exception:
        return False

def get_text_safe(driver, xpath, timeout=WAIT_SHORT):
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
        return el.text.strip()
    except Exception:
        return ""

def set_field_value(driver, element, value):
    try:
        driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));", element, value)
    except:
        try:
            element.clear()
            element.send_keys(value)
        except:
            pass

def extract_details(driver):
    data = {f: "" for f in FIELDS}

    # DA number
    possible_num = get_text_safe(driver, "//h1") or get_text_safe(driver, "//span[contains(@id,'lblApplication')]")
    data["DA_Number"] = possible_num
    data["Detail_URL"] = driver.current_url

    mapping = {
        "Description": ["Description", "Proposal"],
        "Submitted_Date": ["Submitted", "Lodged Date"],
        "Decision": ["Decision", "Determination"],
        "Categories": ["Category", "Type"],
        "Property_Address": ["Address", "Location"],
        "Applicant": ["Applicant", "Owner"],
        "Progress": ["Progress", "Status"],
        "Fees": ["Fees", "Fee"],
        "Documents": ["Documents", "Attachments"],
        "Contact_Council": ["Contact Council", "Contact"],
    }

    for key, words in mapping.items():
        text_found = ""
        for word in words:
            xp = f"//*[contains(text(),'{word}')]/following::*[1]"
            text_found = get_text_safe(driver, xp)
            if text_found:
                break
        data[key] = text_found.strip()

    # Clean-up as per challenge
    if data["Fees"].strip() == "No fees recorded against this application.":
        data["Fees"] = "Not required"

    if data["Contact_Council"].strip().startswith("Application Is Not on exhibition"):
        data["Contact_Council"] = "Not required"

    return data

def collect_links(driver):
    all_links = []
    anchors = driver.find_elements(By.XPATH, "//a[contains(@href,'Application')]")
    for a in anchors:
        link = a.get_attribute("href")
        if link and link.startswith("http"):
            all_links.append(link)
    return list(dict.fromkeys(all_links))  # remove duplicates

def click_next_page(driver):
    next_btns = [
        "//a[@title='Next']",
        "//a[contains(text(),'Next')]",
        "//button[contains(text(),'Next')]",
    ]
    for xp in next_btns:
        try:
            el = driver.find_element(By.XPATH, xp)
            driver.execute_script("arguments[0].click();", el)
            time.sleep(1)
            return True
        except Exception:
            continue
    return False

def run_scraper():
    browser = launch_browser()
    results = []

    try:
        print("[INFO] Opening target page...")
        browser.get(URL)
        time.sleep(2)

        # Click Agree
        click_when_ready(browser, "//button[contains(.,'Agree')]") or \
        click_when_ready(browser, "//input[@value='Agree']")

        # DA Tracking tab
        click_when_ready(browser, "//a[contains(.,'DA Tracking')]")
        time.sleep(1)

        # Advanced Search
        click_when_ready(browser, "//a[contains(.,'Advanced Search')]")
        time.sleep(1)

        # Fill dates
        inputs = browser.find_elements(By.XPATH, "//input[@type='text' or @type='date']")
        for inp in inputs:
            name = (inp.get_attribute("id") or "").lower()
            if "from" in name:
                set_field_value(browser, inp, DATE_FROM)
            if "to" in name:
                set_field_value(browser, inp, DATE_TO)

        # Search button
        click_when_ready(browser, "//button[contains(.,'Search')]") or \
        click_when_ready(browser, "//input[@value='Search']")
        time.sleep(2)

        # Show results
        click_when_ready(browser, "//button[contains(.,'Show')]")
        time.sleep(2)

        all_links = []
        while True:
            links = collect_links(browser)
            all_links.extend([l for l in links if l not in all_links])
            if not click_next_page(browser):
                break

        print(f"[INFO] Found {len(all_links)} detail pages.")

        for idx, link in enumerate(all_links, start=1):
            print(f"[{idx}/{len(all_links)}] Opening {link}")
            browser.get(link)
            time.sleep(1)
            record = extract_details(browser)
            results.append(record)

        print(f"[INFO] Writing {len(results)} records to {OUTPUT_FILE}")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        print("[SUCCESS] File saved:", OUTPUT_FILE)

    finally:
        browser.quit()

if __name__ == "__main__":
    run_scraper()