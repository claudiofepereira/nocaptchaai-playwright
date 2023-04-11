import base64
import random
import re
import requests
from requests.models import Response
from json import dumps
from playwright.async_api import Page, Locator, FrameLocator, TimeoutError, Frame, ElementHandle
import os

# Captcha xpath selectors.
CHECKBOX_CHALLENGE: str = "(//iframe[contains(@title,'checkbox')])[1]"
HOOK_CHALLENGE: str = "(//iframe[contains(@title,'content')])[1]"
PROMPT_TEXT: str = "(//h2[@class='prompt-text'])[1]"
CAPTCHA_FINAL_BUTTON: str = "(//div[@class='button-submit button'])[1]"
CAPTCHA_REFRESH_BUTTON: str = "(//div[@class='refresh button'])[1]"
TASK_IMAGE: str = "//div[@class='task-image']"


class Solver:
    page: Page = None
    user_agent: str = None

    API_KEY: str = None
    API_URL: str = None

    solved: bool = False
    target: str = None
    captcha_type: int = None

    def __init__(self, api_key: str = None, api_url: str = None) -> None:
        """
        Initializes the solver. Sets the API key and API url.
        If the api_key and api_url are not provided, it will try to get them from the environment variables.

        Args:
            api_key (str | None): The API key for the captcha solver.
            api_url (str | None): The API url for the captcha solver.
        """
        self.API_KEY = api_key if api_key is not None else os.getenv("API_KEY")
        self.API_URL = api_url if api_url is not None else os.getenv("API_URL")

    async def identify_challenge(
        self,
    ) -> None:
        """
        Identifies the type of captcha challenge.
        There are 3 types of captcha challenges:
            - Grid - Select all images of X.
            - Bounding Box - Click in a specific area of X.
            - Multiple Choice - Select the most accurate description of X.
        """
        target: str = self.target.lower().strip()

        # Check if keywords are present in the target.
        if "please click each image containing" in target:
            self.captcha_type = 0
        if "please click the center of the" in target:
            self.captcha_type = 1
        if "select the most accurate description of the image" in target:
            self.captcha_type = 2

    async def is_challenge_image_clickable(
        self,
    ) -> bool:
        """
        Checks if the challenge image is clickable.

        Returns:
            bool: True if the challenge image is clickable, False otherwise.
        """
        try:
            await self.page.wait_for_selector(
                HOOK_CHALLENGE,
                timeout=1500,
                state="visible",
            )
            return True
        except TimeoutError:
            return False

    async def is_captcha_visible(
        self,
    ) -> bool:
        """
        Checks if the captcha is visible on the screen.
        Will either check if checkbox from captcha is shown and click it,
        or check if the images are already showing.

        Returns:
            bool: True if the captcha is visible, False otherwise.
        """
        # Check if the images are already visible (no checkbox).
        already_visible: bool = False

        if await self.is_challenge_image_clickable():
            already_visible: bool = True

        if not already_visible:
            checkbox: Locator = self.page.locator(CHECKBOX_CHALLENGE)

            # Click the captcha checkbox if it is visible.
            if await checkbox.is_visible():
                await checkbox.click()

            await self.page.wait_for_timeout(1000)

            # This could mean that simply clicking the checkbox solved the captcha.
            if not await self.is_challenge_image_clickable():
                return False

        self.checkbox_frame: FrameLocator = self.page.frame_locator(
            HOOK_CHALLENGE,
        )

        self.target = await self.checkbox_frame.locator(
            PROMPT_TEXT,
        ).inner_text()

        return True

    async def solve_hcaptcha_grid(
        self,
    ) -> None:
        """
        Solves the captcha challenge of type Grid (type = 0).
        """
        await self.page.wait_for_timeout(1000)

        if not await self.is_challenge_image_clickable():
            self.solved = True
            return

        # Getting the images for the captcha solver.
        images_div: list[Locator] = await self.checkbox_frame.locator(
            TASK_IMAGE,
        ).all()

        headers: dict[str, str] = {
            "Authority": "hcaptcha.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://newassets.hcaptcha.com/",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "User-Agent": self.user_agent,
        }

        image_data: dict[int, str] = {}

        # Populating data for the API call.
        for index, item in enumerate(images_div):

            image_style: str | None = await item.locator(
                "div.image",
            ).get_attribute("style")

            if image_style is None:
                return

            url: str = re.split(r'[(")]', image_style)[2]
            img_base64: bytes = base64.b64encode(
                requests.get(
                    url,
                    headers=headers,
                ).content
            )
            img_base64_decoded: str = img_base64.decode("utf-8")
            image_data[index] = img_base64_decoded

        # Doing final formating for api by adding mandatory fields.
        data_to_send = {
            "target": self.target,
            "method": "hcaptcha_base64",
            "sitekey": "sitekey",
            "site": "site",
            "images": image_data,
        }

        # Post the problem and get the solution.
        r: Response = requests.post(
            url=self.API_URL,
            headers={
                "Content-Type": "application/json",
                "apikey": self.API_KEY,
            },
            data=dumps(data_to_send),
        )

        if r.json()["status"] == "solved":
            solution = r.json()["solution"]
            correct_images: list[int] = list(map(int, solution))

            for index in correct_images:
                await images_div[index].click()
                await self.page.wait_for_timeout(random.uniform(200, 250))

            button: Locator = self.checkbox_frame.locator(CAPTCHA_FINAL_BUTTON)

            if not button:
                return

            label: str | None = await button.get_attribute("title")

            if not label:
                return

            # Checking if there's another step to solve.
            if label == "Submit Answers":
                await button.click()
            elif label == "Next Challenge":
                await button.click()
                await self.solve_hcaptcha_grid()

        elif r.json()["status"] in ["skip", "error"]:
            refresh_button = self.checkbox_frame.locator(CAPTCHA_REFRESH_BUTTON)

            if not refresh_button:
                return

            refresh_button.click()

            await self.page.wait_for_timeout(1000)

        return

    async def solve_hcaptcha_bbox(
        self,
    ) -> None:
        """
        Solves the captcha challenge of type Bounding Box (type = 1).
        """
        await self.page.wait_for_timeout(1000)

        if not await self.is_challenge_image_clickable():
            self.solved = True
            return

        # To get the image url, we have to draw a new canvas using the existing one
        # and then use toDataURL() to get the image url in base64.
        get_image_base64 = """
            async () => {
                const originalCanvas = document.querySelector("canvas");

                if (!originalCanvas) return null;

                const [originalWidth, originalHeight] = [
                    originalCanvas.width,
                    originalCanvas.height,
                ];

                const scaleFactor = Math.min(500 / originalWidth, 536 / originalHeight);

                const [outputWidth, outputHeight] = [
                    originalWidth * scaleFactor,
                    originalHeight * scaleFactor,
                ];

                const outputCanvas = document.createElement("canvas");

                Object.assign(outputCanvas, { width: outputWidth, height: outputHeight });

                const ctx = outputCanvas.getContext("2d");

                ctx.drawImage(
                    originalCanvas,
                    0,
                    0,
                    originalWidth,
                    originalHeight,
                    0,
                    0,
                    outputWidth,
                    outputHeight
                );

                return outputCanvas
                    .toDataURL("image/jpeg", 0.4)
                    .replace(/^data:image\\/(png|jpeg);base64,/, "");
            }
        """

        captcha_frame: ElementHandle | None = await self.page.query_selector(HOOK_CHALLENGE)

        if not captcha_frame:
            return

        frame: Frame | None = await captcha_frame.content_frame()

        if not frame:
            return

        image_base64: str = await frame.evaluate(get_image_base64)

        if not image_base64:
            return

        data_to_send = {
            "target": self.target,
            "method": "hcaptcha_base64",
            "sitekey": "sitekey",
            "site": "site",
            "type": "bbox",
            "choices": [],
            "ln": "en",
            "images": {
                0: image_base64,
            },
        }

        # Post the problem.
        post_response: Response = requests.post(
            url=self.API_URL,
            headers={
                "Content-Type": "application/json",
                "apikey": self.API_KEY,
            },
            data=dumps(data_to_send),
        )

        if post_response.json()["status"] == "error":
            await self.page.reload(wait_until="networkidle")
            return

        headers: dict[str, str] = {
            "Accept-Language": "last-requested-languages",
            "apikey": self.API_KEY,
        }

        url: str = post_response.json()["url"]

        # Wait for the solution.
        while True:
            await self.page.wait_for_timeout(200)

            solve_response: Response = requests.get(
                url=url,
                headers=headers,
            )

            if solve_response.json()["status"] in ["error", "skip"]:
                refresh_button = self.checkbox_frame.locator(CAPTCHA_REFRESH_BUTTON)

                if not refresh_button:
                    return

                refresh_button.click()

                await self.page.wait_for_timeout(1000)

                return

            if solve_response.json()["status"] == "solved":
                break

        x_pos, y_pos = solve_response.json()["answer"]

        await captcha_frame.click(position={"x": x_pos + 10, "y": y_pos + 10})

        button: Locator = self.checkbox_frame.locator(CAPTCHA_FINAL_BUTTON)

        if not button:
            return

        label: str | None = await button.get_attribute("title")

        if not label:
            return

        await self.page.wait_for_timeout(500)

        # Checking if there's another step to solve.
        if label == "Submit Answers":
            await button.click()
        elif label == "Next Challenge":
            await button.click()
            await self.solve_hcaptcha_bbox()

    # TODO - Still needs testing. Logic is all there but is untested.
    async def solve_hcaptcha_multi(
        self,
    ) -> None:
        """
        Solves the captcha challenge of type Multi Selection (type = 2).
        """
        await self.page.wait_for_timeout(1000)

        if not await self.is_challenge_image_clickable():
            self.solved = True
            return

        image: Locator = self.checkbox_frame.locator(
            TASK_IMAGE,
        )

        # Get image url.
        image_style: str | None = await image.locator(
            "div.image",
        ).get_attribute("style")

        if image_style is None:
            return

        url: str = re.split(r'[(")]', image_style)[2]

        headers: dict[str, str] = {
            "Authority": "hcaptcha.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://newassets.hcaptcha.com/",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "User-Agent": self.user_agent,
        }

        # Process base64 of image.
        img_base64: bytes = base64.b64encode(
            requests.get(
                url,
                headers=headers,
            ).content
        )

        img_base64_decoded: str = img_base64.decode("utf-8")

        image_data = {0: img_base64_decoded}

        choices_images: dict[int, str] = {}
        choices_texts: list[str] = []

        choices_elements: list[Locator] = await self.checkbox_frame.locator(
            '//div[class="challenge-answer"]',
        ).all()

        for index, choice in enumerate(choices_elements):
            # Convert image to base64.
            image_style: str | None = await choice.locator(
                "div.image",
            ).get_attribute("style")

            if image_style is None:
                return

            url: str = re.split(r'[(")]', image_style)[2]

            img_base64: bytes = base64.b64encode(
                requests.get(
                    url,
                    headers=headers,
                ).content
            )

            img_base64_decoded: str = img_base64.decode("utf-8")

            # Get answer text.
            choice_text: str | None = await choice.locator(
                "div.text-content",
            ).get_attribute("text")

            if choice_text is None:
                return

            # Save choice information.
            choices_images[index] = img_base64_decoded
            choices_texts.append(choice_text)

        # Doing final formating for api call by adding mandatory fields.
        data_to_send = {
            "target": "Select the most accurate description of the image.",
            "method": "hcaptcha_base64",
            "sitekey": "sitekey",
            "site": "site",
            "example": image_data,
            "images": choices_images,
            "type": "multi",
            "choices": choices_texts,
        }

        # Calling nocaptcha api.
        r: Response = requests.post(
            url=self.API_URL,
            headers={
                "Content-Type": "application/json",
                "apikey": self.API_KEY,
            },
            data=dumps(data_to_send),
        )

        # If the api call was successful.
        if r.json()["status"] == "solved":
            # Get the solution. Should be only 1 element in the solution list.
            solution: list[int] = r.json()["solution"]

            # Clicking on the correct answer.
            await choices_elements[solution[0]].click()

            button: Locator = self.checkbox_frame.locator(CAPTCHA_FINAL_BUTTON)

            if not button:
                return

            label: str | None = await button.get_attribute("title")

            if not label:
                return

            # Checking if there's another step to solve.
            if label == "Submit Answers":
                await button.click()
            elif label == "Next Challenge":
                await button.click()
                await self.solve_hcaptcha_multi()

        elif r.json()["status"] in ["skip", "error"]:
            refresh_button = self.checkbox_frame.locator(CAPTCHA_REFRESH_BUTTON)

            if not refresh_button:
                return

            refresh_button.click()

            await self.page.wait_for_timeout(1000)

        return

    def has_balance(
        self,
    ) -> bool:
        """
        Checks if the user has balance or if the daily limit has been hit.

        Returns:
            bool: True if the user has balance, False otherwise.
        """
        balance_url: str = (
            "https://manage.nocaptchaai.com/balance"
            if "pro" in self.API_URL
            else "https://free.nocaptchaai.com/balance"
        )

        response: Response = requests.get(
            balance_url,
            headers={"apikey": self.API_KEY},
        )

        return response.json()["Balance"] > 0.0 or response.json()["Subscription"]["remaining"] > 0

    async def solve(
        self,
        page: Page,
    ) -> bool:
        """
        Will check if there's any captcha in the page,
        identify the challenge and solve it.

        Args:
            page (Page): The page where the captcha is.

        Returns:
            bool: True if the captcha was solved, False otherwise.
        """
        # Save the page object.
        self.page = page

        self.user_agent = await self.page.evaluate("() => navigator.userAgent")

        while not self.solved:
            # First check if user has balance or daily limit hasn't been hit.
            if not self.has_balance():
                return

            await self.page.wait_for_timeout(1500)

            # If captcha is not visible it means it has been solved.
            if not await self.is_captcha_visible():
                break

            self.captcha_is_open = True

            # Identify the type of captcha.
            await self.identify_challenge()

            match self.captcha_type:
                case 0:
                    await self.solve_hcaptcha_grid()
                case 1:
                    await self.solve_hcaptcha_bbox()
                case 2:
                    await self.solve_hcaptcha_multi()

        return self.solved
