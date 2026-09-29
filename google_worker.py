"""Chrome Google Images search. Never substitutes generated text for a photo."""
import sys,json,time,urllib.parse
from pathlib import Path
import core,image_sources,connections

def main(req):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    options=webdriver.ChromeOptions();options.add_argument('--window-size=1280,900')
    profile=connections.HOME/'google_browser';profile.mkdir(parents=True,exist_ok=True);options.add_argument('--user-data-dir='+str(profile.resolve()))
    # Visible browser: consent/challenge is handled by the user, never bypassed.
    driver=webdriver.Chrome(options=options);driver.set_page_load_timeout(40);records=[];seen=set()
    try:
        driver.get('https://www.google.com/search?tbm=isch&q='+urllib.parse.quote(req['query']))
        deadline=time.monotonic()+100
        while time.monotonic()<deadline and len(records)<req['count']:
            for element in driver.find_elements(By.CSS_SELECTOR,'img')[:100]:
                try:
                    src=element.get_attribute('src') or ''
                    if src in seen:continue
                    seen.add(src)
                    if element.size.get('width',0)<60:continue
                    element.click();time.sleep(.25)
                    candidates=driver.execute_script('return Array.from(document.images).filter(i=>i.naturalWidth>=1000&&i.naturalHeight>=600).map(i=>i.currentSrc||i.src)')
                    for url in candidates:
                        if not url.startswith('http') or url in seen:continue
                        seen.add(url)
                        try:
                            raw,final=image_sources.fetch(url);rec=image_sources.store_image(req['folder'],raw,req['query'],final)
                            if rec['sha256'] not in {r['sha256'] for r in records}:records.append(rec);core.write_json(req['result'],records)
                        except Exception:continue
                        if len(records)>=req['count']:break
                except Exception:continue
                if time.monotonic()>deadline or len(records)>=req['count']:break
            if len(records)>=req['count']:break
            driver.execute_script('window.scrollBy(0,700)');time.sleep(1)
    finally:driver.quit();core.write_json(req['result'],records)
if __name__=='__main__':main(core.read_json(sys.argv[1]))
