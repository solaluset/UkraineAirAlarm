from time import sleep

from requests import get
from cairosvg import svg2png
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .css_var_parser import parse


URL = "https://alerts.in.ua/"

options = Options()
options.headless = True
driver = Chrome(options=options)
driver.get(URL)
_map = None
_css = ""
_last_data = ""
_last_value = None


def prepare(driver: Chrome):
    global _map, _css
    if _map:
        try:
            driver.find_element(By.LINK_TEXT, "Оновити").click()
        except NoSuchElementException:
            print("Couldn't refresh map.")
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
            css += parse(get(href).text, ["light"])
    _css = "<style>" + css + "</style>"
    return _map, _css


def get_img():
    global _last_data, _last_value
    elem, css = prepare(driver)
    data = elem.get_attribute("innerHTML")
    if data == _last_data:
        return _last_value
    _last_data = data
    data = (
        elem.get_attribute("outerHTML").replace(data, "").replace("</svg>", "")
        + "<defs>"
        + css
        + "</defs>"
        + data
        + "</svg>"
    )

    _last_value = svg2png(data)
    return _last_value


if __name__ == "__main__":
    from PIL import Image
    from io import BytesIO

    Image.open(BytesIO(get_img())).show()
