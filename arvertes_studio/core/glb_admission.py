"""Checks the arrays used by the local importer before starting Blender."""
import re
from math import isfinite

DATA = re.compile(r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+")
COMPONENT_BYTES = {5120:1, 5121:1, 5122:2, 5123:2, 5125:4, 5126:4}
ELEMENTS = {"SCALAR":1, "VEC2":2, "VEC3":3, "VEC4":4, "MAT2":4, "MAT3":9, "MAT4":16}


def _int(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def validate_payload(document, binary_size):
    def table(name, limit=5000):
        rows = document.get(name, [])
        if not isinstance(rows, list) or len(rows) > limit or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Coleção GLB inválida ou acima da reserva: " + name)
        return rows

    def index(value, rows):
        return _int(value, 0, len(rows)-1)

    buffers, views = table("buffers",1), table("bufferViews")
    nodes, meshes, accessors = table("nodes"), table("meshes"), table("accessors")
    skins, materials, textures, images = table("skins",128), table("materials"), table("textures"), table("images",64)
    if any("uri" in row for row in buffers):
        raise ValueError("Use um buffer BIN autocontido.")
    if binary_size:
        if len(buffers) != 1 or not _int(buffers[0].get("byteLength"), max(1,binary_size-3), binary_size):
            raise ValueError("O buffer do GLB diverge do bloco BIN.")
    elif buffers:
        raise ValueError("O buffer BIN declarado está ausente.")
    size = buffers[0]["byteLength"] if buffers else 0
    for view in views:
        offset, length = view.get("byteOffset",0), view.get("byteLength")
        if not index(view.get("buffer"), buffers) or not _int(offset,0,size) or not _int(length,1,size-offset):
            raise ValueError("A faixa de dados ultrapassa o buffer BIN.")
        if "byteStride" in view and (not _int(view["byteStride"],4,252) or view["byteStride"] % 4):
            raise ValueError("Stride de buffer view incompatível.")
    used = 0
    for accessor in accessors:
        component, typ, count = accessor.get("componentType"), accessor.get("type"), accessor.get("count")
        if (type(component) is not int or component not in COMPONENT_BYTES or not isinstance(typ,str)
                or typ not in ELEMENTS or not _int(count,1,3_000_000) or "sparse" in accessor):
            raise ValueError("Accessor fora do perfil local. Exporte um GLB materializado.")
        used += count * ELEMENTS[typ]
        if used > 12_000_000:
            raise ValueError("Dados geométricos excedem a reserva local.")
        view_id = accessor.get("bufferView")
        if not index(view_id, views):
            raise ValueError("Accessor sem faixa materializada.")
        view = views[view_id]
        component_size = COMPONENT_BYTES[component]
        unit = component_size * ELEMENTS[typ]
        if typ in ("MAT2", "MAT3"):
            side = int(typ[-1])
            unit = side*((side*component_size+3)//4)*4
        stride = view.get("byteStride",unit)
        head = accessor.get("byteOffset",0)
        if (stride < unit or not _int(head,0,view["byteLength"]) or head % component_size
                or head + (count-1)*stride + unit > view["byteLength"]):
            raise ValueError("Accessor descreve dados além de sua faixa.")
    children = []
    for row in nodes:
        for field, number in (("matrix",16), ("translation",3), ("rotation",4), ("scale",3)):
            value = row.get(field)
            if field in row and (not isinstance(value,list) or len(value) != number or any(
                    type(item) not in (int,float) or not -1e12 <= item <= 1e12 or not isfinite(item) for item in value)):
                raise ValueError("Transformação de nó inválida.")
        if any(key in row and not index(row[key], target) for key,target in (("mesh",meshes),("skin",skins))):
            raise ValueError("Nó referencia um elemento inexistente.")
        links = row.get("children",[])
        if not isinstance(links,list) or len(links) > len(nodes) or not all(index(link,nodes) for link in links):
            raise ValueError("Hierarquia de nós inválida.")
        children.append(links)
    # Kahn catches cycles, shared parenting and deep chains without Python recursion.
    parent_count = [0]*len(nodes)
    for links in children:
        for child in links:
            parent_count[child] += 1
            if parent_count[child] > 1:
                raise ValueError("Nó GLB com múltiplos pais.")
    ready = [(i,0) for i,n in enumerate(parent_count) if n == 0]
    seen = 0
    while ready:
        vertex, depth = ready.pop()
        if depth > 128:
            raise ValueError("Hierarquia excede a profundidade operacional.")
        seen += 1
        ready.extend((child,depth+1) for child in children[vertex])
    if seen != len(nodes):
        raise ValueError("A hierarquia GLB contém um ciclo.")
    total = 0
    for row in meshes:
        primitives = row.get("primitives")
        if not isinstance(primitives,list) or not primitives:
            raise ValueError("Uma malha GLB precisa de primitivas.")
        total += len(primitives)
        if total > 5000:
            raise ValueError("Primitivas acima da reserva local.")
        for primitive in primitives:
            if not isinstance(primitive,dict):
                raise ValueError("Primitiva GLB inválida.")
            attributes = primitive.get("attributes")
            if (not isinstance(attributes,dict) or "POSITION" not in attributes
                    or not all(index(item,accessors) for item in attributes.values())
                    or "indices" in primitive and not index(primitive["indices"],accessors)
                    or "material" in primitive and not index(primitive["material"],materials)):
                raise ValueError("Atributos, índices ou material de malha inválidos.")
            positions = accessors[attributes["POSITION"]]["count"]
            for value in attributes.values():
                if accessors[value]["count"] != positions:
                    raise ValueError("A contagem de atributos diverge da malha.")
    for skin in skins:
        joints = skin.get("joints")
        if (not isinstance(joints,list) or not 1 <= len(joints) <= 1024 or
                not all(index(item,nodes) for item in joints) or len(set(joints)) != len(joints)
                or "inverseBindMatrices" in skin and not index(skin["inverseBindMatrices"],accessors)):
            raise ValueError("Juntas ou matrizes de inversão incompatíveis.")
    for media in images:
        value = media.get("uri")
        if ("uri" in media and (not isinstance(value,str) or len(value)>2*1024*1024 or not DATA.fullmatch(value))
                or "uri" not in media and not index(media.get("bufferView"),views)):
            raise ValueError("Recursos externos ou formato de imagem embutida incompatíveis.")
    for texture in textures:
        if "source" in texture and not index(texture["source"], images):
            raise ValueError("Textura referencia imagem inexistente.")
    for animation in table("animations",128):
        samplers, channels = animation.get("samplers"), animation.get("channels")
        if not isinstance(samplers,list) or not samplers or not isinstance(channels,list) or not channels:
            raise ValueError("Clipe GLB incompleto.")
        for sampler in samplers:
            if not isinstance(sampler,dict) or any(not index(sampler.get(field),accessors) for field in ("input","output")):
                raise ValueError("Clipe referencia acessores inexistentes.")
        for channel in channels:
            target = channel.get("target") if isinstance(channel,dict) else None
            if (not isinstance(target,dict) or not index(channel.get("sampler"),samplers)
                    or not index(target.get("node"),nodes)):
                raise ValueError("Canal de animação fora da hierarquia.")
