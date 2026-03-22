"""
SIGAA university portal scraper.
Ported from clairemont_core — fetches student info, disciplines, and
upcoming assignments from sigaa.uffs.edu.br using headless Chrome.

Requires env vars: SIGAA_USER, SIGAA_PASS
Requires system: Google Chrome + chromedriver
"""

import os
import time
import traceback

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _parse_portal(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def text(selector, method="select_one"):
        el = getattr(soup, method)(selector)
        return el.get_text(strip=True) if el else ""

    def td_sibling(label):
        td = soup.find("td", string=label)
        if td:
            sibling = td.find_next_sibling("td")
            return sibling.get_text(strip=True) if sibling else ""
        return ""

    student_info = {
        "name": text("#info-usuario .usuario span"),
        "registration": td_sibling(" Matrícula: "),
        "course": td_sibling(" Curso: "),
        "status": td_sibling(" Status: "),
        "email": td_sibling(" E-Mail: "),
        "semester": text(".periodo-atual strong"),
        "campus": text(".unidade").split("(")[0].strip(),
    }

    disciplines = []
    for row in soup.select("#main-docente table.subFormulario + table tr:not(:first-child)"):
        if "style" in row.attrs or row.find("td", colspan="5"):
            continue
        cols = row.find_all("td")
        if len(cols) >= 3:
            disciplines.append({
                "name": cols[0].get_text(strip=True),
                "location": cols[1].get_text(strip=True),
                "schedule": cols[2].get_text(strip=True),
            })

    assignments = []
    for row in soup.select("#avaliacao-portal table tr"):
        if "background" in row.get("style", "") or not row.find_all("td"):
            continue
        cols = row.find_all("td")
        if len(cols) >= 3:
            raw = cols[2].get_text(strip=True, separator=" ")
            parts = raw.split(" ", 1)
            course = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            type_, _, desc = rest.partition(":")
            assignments.append({
                "date": cols[1].get_text(strip=True),
                "course": course,
                "type": type_.strip(),
                "description": desc.strip(),
            })

    return {
        "student_info": student_info,
        "current_disciplines": disciplines,
        "upcoming_assignments": assignments,
    }


# ---------------------------------------------------------------------------
# WebDriver factory
# ---------------------------------------------------------------------------

def _create_driver(headless: bool = True):
    import random
    import undetected_chromedriver as uc
    from selenium_stealth import stealth
    from fake_useragent import UserAgent

    _FALLBACK_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    ]

    try:
        ua_string = UserAgent(os="win", platforms="pc", fallback=random.choice(_FALLBACK_UAS)).random
    except Exception:
        ua_string = random.choice(_FALLBACK_UAS)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-agent={ua_string}")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options)

    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": ua_string,
        "acceptLanguage": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "platform": "Win32",
    })

    js_shield = """
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
            ]
        });
        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
        Object.defineProperty(screen, 'width', { get: () => 1920 });
        Object.defineProperty(screen, 'height', { get: () => 1080 });
    """
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js_shield})

    stealth(
        driver,
        languages=["pt-BR", "pt"],
        vendor="Google Inc.",
        platform="Win32",
        fix_hairline=True,
        run_on_insecure_origins=False,
    )
    return driver


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_curriculum() -> dict:
    """
    Log in to SIGAA and return student info, disciplines, and assignments.
    Returns a dict with keys: student_info, current_disciplines, upcoming_assignments.
    Raises RuntimeError on failure.
    """
    user = os.environ.get("SIGAA_USER", "").strip()
    password = os.environ.get("SIGAA_PASS", "").strip()
    if not user or not password:
        raise RuntimeError("SIGAA_USER and SIGAA_PASS must be set in environment.")

    driver = None
    try:
        driver = _create_driver(headless=True)
        driver.get("https://sigaa.uffs.edu.br")
        time.sleep(3)

        wait = WebDriverWait(driver, 10)

        def find(by, locator, msg):
            try:
                el = wait.until(EC.visibility_of_element_located((by, locator)))
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                return el
            except TimeoutException:
                raise TimeoutException(msg)

        # Dismiss cookie consent if present
        find(By.XPATH, "//button[contains(text(), 'Ciente')]", "Consent button not found").click()

        # Fill login form
        login_field = find(By.NAME, "user.login", "Login field not found")
        login_field.click()
        login_field.send_keys(user)

        pass_field = find(By.NAME, "user.senha", "Password field not found")
        pass_field.click()
        pass_field.send_keys(password)

        find(By.XPATH, "//input[@type='submit' and contains(@value, 'Entrar')]", "Submit button not found").click()
        time.sleep(3)

        data = _parse_portal(driver.page_source)
        return data

    except Exception:
        traceback.print_exc()
        raise RuntimeError("Failed to retrieve SIGAA data. See server logs for details.")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
