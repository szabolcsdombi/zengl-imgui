import math
import sys

import moderngl
import pygame
from imgui_bundle import imgui
from zengl_imgui import PygameBackend

pygame.init()
pygame.display.set_mode((1280, 720), flags=pygame.OPENGL | pygame.DOUBLEBUF, vsync=True)
pygame.display.set_caption("ModernGL + ImGui Example")

impl = PygameBackend()

imgui.get_io().ini_saving_rate = 0.0

ctx = moderngl.get_context()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        impl.process_event(event)
    impl.process_inputs()

    imgui.new_frame()
    imgui.show_demo_window()
    imgui.end_frame()
    imgui.render()

    now = pygame.time.get_ticks() / 1000.0
    r = math.sin(now + 0.0) * 0.5 + 0.5
    g = math.sin(now + 2.1) * 0.5 + 0.5
    b = math.sin(now + 4.2) * 0.5 + 0.5
    ctx.clear(r, g, b)

    impl.render()

    pygame.display.flip()
