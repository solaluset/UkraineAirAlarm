from io import StringIO
from traceback import print_exc
from typing import Union, Tuple

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


URL = "https://alerts.in.ua/"

options = Options()
options.headless = True
driver = Chrome(options=options)
driver.implicitly_wait(10)
driver.get(URL)

_map = None


def get_map(driver: Chrome):
    global _map
    if _map:
        return _map

    _map = driver.find_element(By.TAG_NAME, "svg")

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

    Image.open(BytesIO(get_img()[0])).show()
