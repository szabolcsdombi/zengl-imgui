import struct

import imgui
import zengl


class OpenGL:
    GL_TEXTURE0 = 0x84c0
    GL_TEXTURE_2D = 0xde1
    GL_ARRAY_BUFFER = 0x8892
    GL_ELEMENT_ARRAY_BUFFER = 0x8893
    GL_STREAM_DRAW = 0x88e0
    GL_TRIANGLES = 0x0004
    GL_UNSIGNED_INT = 0x1405
    GL_SCISSOR_TEST = 0x0c11

    def __init__(self, load):
        from ctypes import CFUNCTYPE, c_int, c_ssize_t, c_void_p, cast
        self.glEnable = cast(load('glEnable'), CFUNCTYPE(None, c_int))
        self.glDisable = cast(load('glDisable'), CFUNCTYPE(None, c_int))
        self.glScissor = cast(load('glScissor'), CFUNCTYPE(None, c_int, c_int, c_int, c_int))
        self.glActiveTexture = cast(load('glActiveTexture'), CFUNCTYPE(None, c_int))
        self.glBindTexture = cast(load('glBindTexture'), CFUNCTYPE(None, c_int, c_int))
        self.glBindBuffer = cast(load('glBindBuffer'), CFUNCTYPE(None, c_int, c_int))
        self.glBufferData = cast(load('glBufferData'), CFUNCTYPE(None, c_int, c_ssize_t, c_void_p, c_int))
        self.glDrawElements = cast(load('glDrawElements'), CFUNCTYPE(None, c_int, c_int, c_int, c_void_p))


class ZenGLRenderer:
    def __init__(self):
        self.io = imgui.get_io()
        self.ctx = zengl.context()

        self.vertex_buffer = self.ctx.buffer(size=1)
        self.index_buffer = self.ctx.buffer(size=1, index=True)

        width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
        self.atlas = self.ctx.image((width, height), 'rgba8unorm', pixels)

        version = '#version 330 core'
        if self.ctx.info['version'].startswith('OpenGL ES'):
            version = '#version 300 es\nprecision highp float;'

        self.pipeline = self.ctx.pipeline(
            includes={
                'version': version,
            },
            vertex_shader='''
                #include "version"
                uniform vec2 Scale;
                layout (location = 0) in vec2 in_vertex;
                layout (location = 1) in vec2 in_uv;
                layout (location = 2) in vec4 in_color;
                out vec2 v_uv;
                out vec4 v_color;
                void main() {
                    v_uv = in_uv;
                    v_color = in_color;
                    gl_Position = vec4(in_vertex.xy * Scale - 1.0, 0.0, 1.0);
                    gl_Position.y = -gl_Position.y;
                }
            ''',
            fragment_shader='''
                #version 330 core
                uniform sampler2D Texture;
                in vec2 v_uv;
                in vec4 v_color;
                layout (location = 0) out vec4 out_color;
                void main() {
                    out_color = texture(Texture, v_uv) * v_color;
                }
            ''',
            layout=[
                {'name': 'Texture', 'binding': 0},
            ],
            resources=[
                {
                    'type': 'sampler',
                    'binding': 0,
                    'image': self.atlas,
                    'min_filter': 'nearest',
                    'mag_filter': 'nearest',
                },
            ],
            blend={
                'enable': True,
                'src_color': 'src_alpha',
                'dst_color': 'one_minus_src_alpha',
            },
            uniforms={
                'Scale': [0.0, 0.0],
            },
            topology='triangles',
            framebuffer=None,
            viewport=(0, 0, 0, 0),
            vertex_buffers=zengl.bind(self.vertex_buffer, '2f 2f 4nu1', 0, 1, 2),
            index_buffer=self.index_buffer,
            instance_count=0,
        )

        self.gl = OpenGL(zengl.default_loader.load_opengl_function)
        self.vtx_buffer = zengl.inspect(self.vertex_buffer)['buffer']
        self.idx_buffer = zengl.inspect(self.index_buffer)['buffer']
        self.io.fonts.texture_id = zengl.inspect(self.atlas)['texture']
        self.io.fonts.clear_tex_data()

    def render(self, draw_data=None):
        if draw_data is None:
            draw_data = imgui.get_draw_data()

        display_width, display_height = self.io.display_size
        fb_width = int(display_width * self.io.display_fb_scale[0])
        fb_height = int(display_height * self.io.display_fb_scale[1])

        if draw_data is None or fb_width == 0 or fb_height == 0:
            return

        self.pipeline.viewport = (0, 0, fb_width, fb_height)
        self.pipeline.uniforms['Scale'][:] = struct.pack('2f', 2.0 / display_width, 2.0 / display_height)
        self.pipeline.render()

        gl = self.gl
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        for commands in draw_data.commands_lists:
            idx_buffer_offset = 0
            vtx_size = commands.vtx_buffer_size * imgui.VERTEX_SIZE
            idx_size = commands.idx_buffer_size * imgui.INDEX_SIZE
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vtx_buffer)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, vtx_size, commands.vtx_buffer_data, gl.GL_STREAM_DRAW)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.idx_buffer)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, idx_size, commands.idx_buffer_data, gl.GL_STREAM_DRAW)
            for command in commands.commands:
                x1, y1, x2, y2 = command.clip_rect
                gl.glScissor(int(x1), int(fb_height - y2), int(x2 - x1), int(y2 - y1))
                gl.glBindTexture(gl.GL_TEXTURE_2D, command.texture_id)
                gl.glDrawElements(gl.GL_TRIANGLES, command.elem_count, gl.GL_UNSIGNED_INT, idx_buffer_offset)
                idx_buffer_offset += command.elem_count * imgui.INDEX_SIZE
        gl.glDisable(gl.GL_SCISSOR_TEST)


class PygameBackend:
    def __init__(self):
        import pygame
        from imgui.integrations.pygame import PygameRenderer
        class PygameInputHandler(PygameRenderer):
            def __init__(self):
                self._gui_time = None
                self.custom_key_map = {}
                try:
                    imgui.get_io()
                except:
                    imgui.create_context()
                self.io = imgui.get_io()
                self.io.display_size = pygame.display.get_window_size()
                self._map_keys()

        self.input_handler = PygameInputHandler()
        self.renderer = ZenGLRenderer()

    def render(self):
        return self.renderer.render()

    def process_event(self, event):
        return self.input_handler.process_event(event)

    def process_inputs(self):
        return self.input_handler.process_inputs()
