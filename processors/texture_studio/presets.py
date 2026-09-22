from .model import TexturePreset
BUILTIN_PRESETS=[TexturePreset('Perlin Default','perlin',{'scale':48,'octaves':4,'persistence':.5,'lacunarity':2,'seed':42,'contrast':1,'brightness':0,'warp':0}),TexturePreset('Simplex Soft','simplex',{'scale':56,'octaves':4,'persistence':.55,'lacunarity':2,'seed':7,'contrast':1,'brightness':0,'warp':0}),TexturePreset('Value Clouds','value',{'scale':64,'octaves':5,'persistence':.5,'lacunarity':2,'seed':3,'contrast':1,'brightness':0,'warp':0}),TexturePreset('Worley Cells','worley',{'scale':32,'octaves':1,'persistence':.5,'lacunarity':2,'seed':11,'contrast':1,'brightness':0,'warp':0}),TexturePreset('Cellular','cellular',{'scale':32,'octaves':1,'persistence':.5,'lacunarity':2,'seed':19,'contrast':1,'brightness':0,'warp':0})]
for k in ['stripes','rings','checker','dots','grid']: BUILTIN_PRESETS.append(TexturePreset(k.title(),f'pattern:{k}',{'size':32,'spacing':8,'angle':0,'color_a':(35,35,45),'color_b':(210,210,220),'background':(20,20,25),'anti_alias':True}))

GMIC_DEFAULTS={'intensity':25,'grain_size':3,'blend_mode':'multiply','color_tint':(220,205,180,255),'seed':42,'contrast':1,'brightness':0}
for n in ['paper','canvas','grunge','noise_blend']:
    BUILTIN_PRESETS.append(TexturePreset(n.replace('_',' ').title(),f'gmic:{n}',GMIC_DEFAULTS.copy(),['GMIC']))

RAYMARCH_DEFAULTS={'steps':96,'max_distance':6.0,'surface_threshold':0.0025,'light_direction':(0.55,0.7,0.45),'ambient':0.22,'diffuse':0.72,'specular':0.28,'color_a':(75,105,210),'color_b':(225,105,155),'fresnel':0.35,'background':(10,12,22),'gradient':0.32,'seed':42}
BUILTIN_PRESETS.append(TexturePreset('Raymarch Orb','raymarch:orb',RAYMARCH_DEFAULTS.copy(),['Raymarch','SDF']))
