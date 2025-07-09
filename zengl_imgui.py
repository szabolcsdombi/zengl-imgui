import struct
from ctypes import c_byte

import zengl
from imgui_bundle import imgui


class OpenGL:
    GL_TEXTURE0 = 0x84c0
    GL_TEXTURE_2D = 0xde1
    GL_ARRAY_BUFFER = 0x8892
    GL_ELEMENT_ARRAY_BUFFER = 0x8893
    GL_STREAM_DRAW = 0x88e0
    GL_TRIANGLES = 0x0004
    GL_UNSIGNED_INT = 0x1405
    GL_SCISSOR_TEST = 0x0c11

    def __init__(self):
        if not zengl._extern_gl:
            from ctypes import CFUNCTYPE, c_int, c_ssize_t, c_void_p, cast
            load = zengl.context().loader.load_opengl_function
            self.glEnable = cast(load('glEnable'), CFUNCTYPE(None, c_int))
            self.glDisable = cast(load('glDisable'), CFUNCTYPE(None, c_int))
            self.glScissor = cast(load('glScissor'), CFUNCTYPE(None, c_int, c_int, c_int, c_int))
            self.glActiveTexture = cast(load('glActiveTexture'), CFUNCTYPE(None, c_int))
            self.glBindTexture = cast(load('glBindTexture'), CFUNCTYPE(None, c_int, c_int))
            self.glBindBuffer = cast(load('glBindBuffer'), CFUNCTYPE(None, c_int, c_int))
            self.glBufferData = cast(load('glBufferData'), CFUNCTYPE(None, c_int, c_ssize_t, c_void_p, c_int))
            self.glDrawElementsInstanced = cast(load('glDrawElementsInstanced'), CFUNCTYPE(None, c_int, c_int, c_int, c_void_p, c_int))
        else:
            import _zengl
            _zengl.gl_symbols
            self.glEnable = _zengl.gl_symbols.zengl_glEnable
            self.glDisable = _zengl.gl_symbols.zengl_glDisable
            self.glScissor = _zengl.gl_symbols.zengl_glScissor
            self.glActiveTexture = _zengl.gl_symbols.zengl_glActiveTexture
            self.glBindTexture = _zengl.gl_symbols.zengl_glBindTexture
            self.glBindBuffer = _zengl.gl_symbols.zengl_glBindBuffer
            self.glBufferData = _zengl.gl_symbols.zengl_glBufferData
            self.glDrawElementsInstanced = _zengl.gl_symbols.zengl_glDrawElementsInstanced


class ZenGLRenderer:
    def __init__(self):
        self.io = imgui.get_io()
        self.ctx = zengl.context()

        self.vertex_buffer = self.ctx.buffer(size=1)
        self.index_buffer = self.ctx.buffer(size=1, index=True)

        self.io.fonts.add_font_default()
        tex_data = self.io.fonts.tex_data
        width, height, pixels = tex_data.width, tex_data.height, tex_data.get_pixels_array()
        self.atlas = self.ctx.image((width, height), 'rgba8unorm', pixels)
        tex_data.set_tex_id(zengl.inspect(self.atlas)['texture'])
        tex_data.set_status(imgui.ImTextureStatus.ok)
        self.io.backend_flags |= imgui.BackendFlags_.renderer_has_textures

        version = '#version 330 core'
        if 'WebGL' in self.ctx.info['version'] or 'OpenGL ES' in self.ctx.info['version']:
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
                #include "version"
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

        self.gl = OpenGL()
        self.vtx_buffer = zengl.inspect(self.vertex_buffer)['buffer']
        self.idx_buffer = zengl.inspect(self.index_buffer)['buffer']
        self.ctx.end_frame(flush=False)

    def _update_font_texture(self):
        tex_data = self.io.fonts.tex_data
        pixels = self.io.fonts.tex_data.get_pixels_array()
        self.atlas.write(pixels)
        tex_data.set_tex_id(zengl.inspect(self.atlas)['texture'])
        tex_data.set_status(imgui.ImTextureStatus.ok)

    def render(self, draw_data: imgui.ImDrawData | None = None):
        self.ctx.new_frame(clear=False)

        if self.io.fonts.tex_data.status == imgui.ImTextureStatus.want_updates:
            # the internal imgui_bundle atlas changes dynamically
            # so we need to update it or we end up with missing glyphs
            self._update_font_texture()

        if draw_data is None:
            draw_data = imgui.get_draw_data()

        display_width, display_height = self.io.display_size
        fb_width = int(display_width * self.io.display_framebuffer_scale[0])
        fb_height = int(display_height * self.io.display_framebuffer_scale[1])

        if draw_data is None or fb_width == 0 or fb_height == 0:
            return

        self.pipeline.viewport = (0, 0, fb_width, fb_height)
        self.pipeline.uniforms['Scale'][:] = struct.pack('2f', 2.0 / display_width, 2.0 / display_height)
        self.pipeline.render()

        gl = self.gl
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        for commands in draw_data.cmd_lists:
            idx_buffer_offset = 0
            vtx_size = commands.vtx_buffer.size() * imgui.VERTEX_SIZE
            idx_size = commands.idx_buffer.size() * imgui.INDEX_SIZE
            vtx_buffer_data = (c_byte * vtx_size).from_address(commands.vtx_buffer.data_address())
            idx_buffer_data = (c_byte * idx_size).from_address(commands.idx_buffer.data_address())
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vtx_buffer)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, vtx_size, vtx_buffer_data, gl.GL_STREAM_DRAW)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.idx_buffer)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, idx_size, idx_buffer_data, gl.GL_STREAM_DRAW)
            for command in commands.cmd_buffer:
                x1, y1, x2, y2 = command.clip_rect
                gl.glScissor(int(x1), int(fb_height - y2), int(x2 - x1), int(y2 - y1))
                gl.glBindTexture(gl.GL_TEXTURE_2D, command.get_tex_id())
                gl.glDrawElementsInstanced(gl.GL_TRIANGLES, command.elem_count, gl.GL_UNSIGNED_INT, idx_buffer_offset, 1)
                idx_buffer_offset += command.elem_count * imgui.INDEX_SIZE
        gl.glDisable(gl.GL_SCISSOR_TEST)

        self.ctx.end_frame()


class PygameBackend:
    def __init__(self):
        # monkey patch fix for broken OpenGL backend import within imgui_bundle
        # we only care about the input/event handling from PygameRenderer
        # so we can safely just replace it with a noop
        import sys, types
        _fake_mod = types.ModuleType("imgui_bundle.python_backends.opengl_backend_fixed")
        class FixedPipelineRenderer:
            pass
        _fake_mod.FixedPipelineRenderer = FixedPipelineRenderer
        sys.modules["imgui_bundle.python_backends.opengl_backend_fixed"] = _fake_mod

        import pygame
        from imgui_bundle.python_backends.python_backends_disabled.pygame_backend import PygameRenderer

        class PygameInputHandler(PygameRenderer):
            def __init__(self):
                self._gui_time = None
                self.custom_key_map = {}
                if not imgui.get_current_context():
                    imgui.create_context()
                self.io = imgui.get_io()
                self.io.display_size = pygame.display.get_window_size()
                self._map_keys()

        self.input_handler = PygameInputHandler()
        self.renderer = ZenGLRenderer()

    def render(self, draw_data: imgui.ImDrawData | None = None):
        return self.renderer.render(draw_data)

    def process_event(self, event):
        return self.input_handler.process_event(event)

    def process_inputs(self):
        return self.input_handler.process_inputs()
