from PIL import Image
import numpy as np

def gen_favicon(width, height):
    pil_map = Image.new("RGBA", (width, height), 255)
    color_1 = (0, 230, 118)
    color_2 = (223, 120, 239)
    colors = np.array([color_1, color_2])
    randints = np.random.randint(2, size=width*height)
    random_grid = [tuple(colors[randint]) for randint in randints]
    pil_map.putdata(random_grid)
    return pil_map

size = 8
favicon = gen_favicon(size, size)
favicon.save("favicon.png")
favicon.save("favicon.ico")
