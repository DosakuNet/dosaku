from PIL.Image import Image

from dosaku import Service
from dosaku.apis import Clipdrop


class ClipdropTextToImage(Service):
    name = 'ClipdropTextToImage'

    def __init__(self):
        super().__init__()
        self.clipdrop = Clipdrop()

    def text_to_image(self, prompt: str, **_) -> Image:
        return self.clipdrop.text_to_image(prompt=prompt)

    def __call__(self, prompt: str, **_) -> Image:
        return self.text_to_image(prompt, **_)


#ClipdropTextToImage.register_task(task='TextToImage')
