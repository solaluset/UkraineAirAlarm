from io import StringIO
from traceback import print_exc
from typing import Union, Tuple

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException


URL = "https://alerts.in.ua/"

options = Options()
options.headless = True
options.add_argument("--disable-dev-shm-usage")
driver = Chrome(options=options)
driver.get(URL)

_map = None


def get_map(driver: Chrome):
    global _map
    if _map:
        try:
            reload = driver.find_element(By.LINK_TEXT, "перезавантажити сторінку")
        except NoSuchElementException:
            pass
        else:
            _map = None
            reload.click()
            return get_map(driver)
        return _map

    try:
        _map = WebDriverWait(driver, 10).until(
            lambda _: driver.find_element(By.TAG_NAME, "svg")
        )
    except TimeoutException:
        driver.refresh()
        raise

    driver.execute_script(
        "document.getElementsByTagName('html')[0]"
        ".classList.remove('light', 'auto-raion')"
    )

    size = _map.get_property("viewBox")["baseVal"]
    driver.set_window_size(size["width"], size["height"])

    return _map


def get_img() -> Union[Tuple[bytes, None], Tuple[None, str]]:
    try:
        return get_map(driver).screenshot_as_png, None
    except Exception:
        f = StringIO()
        print_exc(file=f)
        return None, f.getvalue()


if __name__ == "__main__":
    from PIL import Image
    from io import BytesIO

    img, error = get_img()
    if img:
        Image.open(BytesIO(img)).show()
    else:
        print(error)
