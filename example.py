import os
import sys

import imgui
import pygame
import zengl

from zengl_imgui import PygameBackend

os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'

pygame.init()
pygame.display.set_mode((1280, 720), flags=pygame.OPENGL | pygame.DOUBLEBUF, vsync=True)

impl = PygameBackend()

ctx = zengl.context()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        impl.process_event(event)
    impl.process_inputs()

    imgui.new_frame()
    imgui.show_test_window()
    imgui.end_frame()
    imgui.render()

    ctx.new_frame()
    impl.render()
    ctx.end_frame()

    pygame.display.flip()
