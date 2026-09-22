import json
import tempfile
import unittest
from pathlib import Path
from processors.shader_studio import ShaderLibrary, ShaderPreset, UniformSpec, parse_uniforms, validate_glsl

class ShaderStudioTests(unittest.TestCase):
    def test_uniform_parser(self):
        src='// @min 0\n// @max 1\n// @step 0.1\nuniform float amount;\nuniform vec3 color;'
        u=parse_uniforms(src); self.assertEqual([x.name for x in u],['amount','color']); self.assertEqual(u[0].minimum,0.0); self.assertEqual(u[0].maximum,1.0)
    def test_builtin_glsl_validation(self):
        self.assertTrue(validate_glsl('vec4 c=texture(u_image,v_uv); fragColor=vec4(1.0-c.rgb,c.a);')[0])
        self.assertFalse(validate_glsl('this is not GLSL;')[0])
    def test_library_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            lib=ShaderLibrary(Path(d)); p=ShaderPreset('My Shader','fragColor=vec4(1.0);',[ ],[ ]) if False else ShaderPreset('My Shader','fragColor=vec4(1.0);',uniforms=[UniformSpec('amount','float',0.5)])
            lib.save(p); q=[x for x in lib.list() if x.name=='My Shader'][0]; self.assertEqual(q.uniforms[0].name,'amount'); lib.delete('My Shader'); self.assertFalse(any(x.name=='My Shader' for x in lib.list()))

if __name__=='__main__': unittest.main()
