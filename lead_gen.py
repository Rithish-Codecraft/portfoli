import subprocess
import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException

# ==================== CONFIGURATION ====================
SEARCH_QUERY = "Real Estate in Tamil Nadu, India"
MAX_LEADS_TO_CHECK = 500  # Adjust based on your needs
OUTPUT_FILE = r"C:\Users\RITHISH\OneDrive\Desktop\lead_gen_data\Real_Estate_TN.csv"
# =======================================================

def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--lang=en")
    # options.add_argument("--headless") # Uncomment to run invisibly
    driver = webdriver.Chrome(options=options)
    return driver

def dismiss_consent(driver):
    """Attempt to dismiss any cookie/consent dialogs Google may show."""
    consent_selectors = [
        "button[aria-label='Accept all']",
        "button[aria-label='Agree']",
        "form[action*='consent'] button",
        "#L2AGLb",  # Google's 'I agree' button ID
    ]
    for sel in consent_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            btn.click()
            time.sleep(1.5)
            print("[INFO] Dismissed consent/cookie dialog.")
            return
        except:
            pass

def scrape_google_maps():
    driver = init_driver()
    wait = WebDriverWait(driver, 20)  # Increased timeout
    driver.get("https://www.google.com/maps")
    time.sleep(3)  # Allow page to settle before interacting
    
    # Dismiss any consent/cookie popups
    dismiss_consent(driver)
    
    # Try multiple selectors for the search box
    search_box = None
    search_selectors = [
        (By.ID, "searchboxinput"),
        (By.CSS_SELECTOR, "input#searchboxinput"),
        (By.CSS_SELECTOR, "input[name='q']"),
        (By.XPATH, "//input[@id='searchboxinput']"),
    ]
    for by, selector in search_selectors:
        try:
            search_box = wait.until(EC.element_to_be_clickable((by, selector)))
            print(f"[INFO] Found search box using selector: {selector}")
            break
        except TimeoutException:
            continue
    
    if not search_box:
        print("Failed to find search box after trying all selectors.")
        driver.save_screenshot("debug_screenshot.png")
        print("[DEBUG] Screenshot saved as debug_screenshot.png")
        driver.quit()
        return []

    search_box.clear()
    search_box.send_keys(SEARCH_QUERY)
    search_box.send_keys(Keys.ENTER)

    time.sleep(5) # Allow initial results to load
    
    scraped_leads = []
    seen_identifiers = set()
    i = 0
    
    print(f"Starting extraction for: {SEARCH_QUERY}")
    
    while len(scraped_leads) < MAX_LEADS_TO_CHECK:
        try:
            sidebar = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]')))
        except TimeoutException:
            print("Could not find the results sidebar.")
            break

        # Extract all clickable cards loaded so far
        cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        
        # If we have reached the end of the loaded list, scroll down
        if i >= len(cards):
            driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", sidebar)
            time.sleep(3)
            cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            # If still no new cards after scroll, we're likely at the end
            if i >= len(cards):
                if "You've reached the end of the list." in driver.page_source:
                    print("Reached end of Google Maps results.")
                else:
                    print("No more items loaded after scroll. Ending.")
                break
        
        card = cards[i]
        i += 1
        
        try:
            name = card.get_attribute('aria-label')
            maps_url = card.get_attribute('href')
        except StaleElementReferenceException:
            i -= 1 # retry this index after a short wait
            time.sleep(1)
            continue
            
        if not name:
            continue
            
        # Click the card to open detail view
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(0.5)
            card.click()
        except:
            continue
            
        time.sleep(2.5) # Wait for detail panel to fully slide in
        
        # 1. FILTER: Check for website in detail panel
        website_elements = driver.find_elements(By.CSS_SELECTOR, "a[data-item-id='authority']")
        if website_elements:
            # Website found! Discard lead and click 'Back'
            try:
                back_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Back') or contains(@class, 'hYBOP')]")
                back_btn.click()
                time.sleep(1.5)
            except:
                pass
            continue
            
        # 2. Extract Details (Since no website was found)
        try:
            category = driver.find_element(By.CSS_SELECTOR, "button.DkE7Zb").text
        except:
            category = "N/A"
            
        try:
            phone_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id^='phone:tel:']")
            phone = phone_el.get_attribute("data-item-id").replace("phone:tel:", "")
        except:
            phone = "N/A"
            
        try:
            address_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
            address = address_el.text
        except:
            address = "N/A"
            
        try:
            rating = driver.find_element(By.CSS_SELECTOR, "div.F7nice span[aria-hidden='true']").text
            reviews = driver.find_element(By.CSS_SELECTOR, "div.F7nice span[aria-label*='reviews']").text.replace('(', '').replace(')', '').replace(',', '')
        except:
            rating = "N/A"
            reviews = "0"
            
        # De-duplication Rule
        unique_key = f"{name.lower().strip()}_{phone.strip()}"
        if unique_key not in seen_identifiers:
            seen_identifiers.add(unique_key)
            scraped_leads.append({
                "Business_Name": name,
                "Primary_Category": category,
                "Phone_Number": phone,
                "Full_Address": address,
                "Business_Rating": rating,
                "Total_Reviews": reviews,
                "Google_Maps_URL": maps_url,
                "Place_ID": "N/A" # Place ID extraction requires more complex URL parsing, kept as N/A placeholder
            })
            print(f"[QUALIFIED LEAD FOUND]: {name} - {phone}")
            
        # Click 'Back' to return to search results list
        try:
            back_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Back') or contains(@class, 'hYBOP')]")
            back_btn.click()
            time.sleep(1.5)
        except:
            pass
            
    driver.quit()
    return scraped_leads

def save_to_csv(data):
    if not data:
        print("No leads matching the criteria were found.")
        return
        
    fields = ["Business_Name", "Primary_Category", "Phone_Number", "Full_Address", "Business_Rating", "Total_Reviews", "Google_Maps_URL", "Place_ID"]
    
    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    print(f"\nSuccessfully saved {len(data)} clean leads to {OUTPUT_FILE}")

if __name__ == "__main__":
    leads = scrape_google_maps()
    save_to_csv(leads)