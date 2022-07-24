from time import sleep

import os
import sys
from requests import get
from cairosvg import svg2png
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

sys.path.append(os.path.dirname(__file__))
from css_var_parser import parse


URL = "https://alerts.in.ua/"

options = Options()
options.headless = True
driver = Chrome(options=options)
driver.get(URL)
_map = None
_css = None
_last_data = ""
_last_value = None


def prepare(driver: Chrome):
    global _map, _css
    if _map:
        try:
            driver.find_element(By.LINK_TEXT, "Оновити зараз").click()
            sleep(1)
        except NoSuchElementException:
            print("Refreshing map forcefully...")
            _map = None
            driver.refresh()
            return prepare(driver)
        return _map, _css

    while True:
        try:
            _map = driver.find_element(By.TAG_NAME, "svg")
        except NoSuchElementException:
            sleep(5)
        else:
            break

    driver.execute_script(
        "document.getElementsByTagName('html')[0].removeAttribute('class')"
    )

    css = ""
    for file in driver.find_elements(By.TAG_NAME, "link"):
        href = file.get_attribute("href")
        if file.get_attribute("rel") == "stylesheet" and href.startswith(URL):
            css += parse(get(href).text, ["light", "contrast"])
    _css = "<style>" + css + "</style>"
    return _map, _css


def get_img():
    global _last_data, _last_value
    elem, css = prepare(driver)
    data = elem.get_attribute("outerHTML")
    if data == _last_data:
        return "", _last_value
    _last_data = data

    css_soup = BeautifulSoup("<defs>" + css + "</defs>", "html.parser")
    soup = BeautifulSoup(data, "html.parser")
    svg = soup.find("svg")
    if svg.defs:
        svg.defs.replace_with(css_soup)
    else:
        svg.append(css_soup)
    width, height = svg["viewbox"].split()[2:]
    svg["width"] = width
    svg["height"] = height

    for img in soup.find_all("image"):
        if not img["href"].startswith("http"):
            img["href"] = URL + img["href"]

    soup = str(soup)
    try:
        _last_value = svg2png(soup)
    except Exception as e:
        print(e)
        _last_value = None
    return soup, _last_value


if __name__ == "__main__":
    from PIL import Image
    from io import BytesIO

    Image.open(BytesIO(get_img()[1])).show()
