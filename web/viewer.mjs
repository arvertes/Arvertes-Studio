import {
  ACESFilmicToneMapping, Box3, Color, DirectionalLight, GridHelper,
  HemisphereLight, LoadingManager, PerspectiveCamera, Scene, Sphere,
  Spherical, Vector3, WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { readGlbDocument } from "./glb.mjs";

const embeddedData = /^data:(?:application\/(?:octet-stream|gltf-buffer)|image\/(?:png|jpeg|webp|avif));base64,[a-z\d+/=\s]+$/i;
const externalError = "A prévia exige um GLB autocontido com recursos incorporados.";
const decoderExtensions = ["KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"];

function validateResources(buffer, stats) {
  const gltf = readGlbDocument(buffer);
  const accessorSizes = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };
  let accessorBytes = 0;
  for (const accessor of gltf.accessors ?? []) {
    if (!Number.isSafeInteger(accessor.count) || accessor.count <= 0) throw Error("Accessor inválido.");
    accessorBytes += accessor.count * (accessorSizes[accessor.type] ?? 16) * 4;
  }
  if (accessorBytes > 96 * 1024 * 1024 || (gltf.nodes?.length ?? 0) > 5000 ||
      (gltf.images?.length ?? 0) > 32 || stats.triangles > 1000000 || stats.primitives > 3000) {
    throw Error("Modelo acima do limite da prévia local. Consulte os metadados ou abra o GLB no Blender.");
  }
  for (const resource of [...(gltf.buffers ?? []), ...(gltf.images ?? [])]) {
    if (resource.uri !== undefined && (typeof resource.uri !== "string" || !embeddedData.test(resource.uri))) {
      throw Error(externalError);
    }
  }
  if (decoderExtensions.some(extension => gltf.extensionsRequired?.includes(extension))) {
    throw Error("A prévia requer uma exportação GLB sem compressão obrigatória de malha ou textura.");
  }
}

function disposeScenes(scenes) {
  const resources = new Set();
  const images = new Set();
  for (const scene of scenes) scene.traverse(object => {
    if (object.geometry) resources.add(object.geometry);
    if (object.skeleton) resources.add(object.skeleton);
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (!material) continue;
      resources.add(material);
      for (const value of Object.values(material)) {
        if (!value?.isTexture) continue;
        resources.add(value);
        if (value.source?.data?.close) images.add(value.source.data);
      }
    }
  });
  for (const resource of resources) resource.dispose();
  for (const bitmap of images) bitmap.close();
}

export function createViewer({ container, onError, onThumbnail }) {
  const direction = new Vector3(1.3, 0.85, 1.6).normalize();
  const camera = new PerspectiveCamera(40, 1);
  const center = new Vector3();
  let radius = 1;
  let renderer, controls, observer, intersection, model, scene;
  let visible = true;
  let closed = false;

  function render() {
    if (!closed && visible && !document.hidden) renderer?.render(scene, camera);
  }
  function resize() {
    const { clientWidth: width, clientHeight: height } = container;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    render();
  }
  function frame() {
    if (!controls) return;
    const angle = camera.fov * Math.PI / 360;
    const visibleAngle = Math.min(angle, Math.atan(Math.tan(angle) * camera.aspect));
    const distance = radius / Math.sin(visibleAngle) * 1.18;
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.near = Math.max(radius / 2000, distance / 5000);
    camera.far = distance * 20;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.minDistance = radius / 8;
    controls.maxDistance = distance * 5;
    controls.update();
    render();
  }
  function orbit(delta) {
    if (!controls) return;
    const sphere = new Spherical().setFromVector3(camera.position.clone().sub(controls.target));
    sphere.theta += delta;
    camera.position.copy(controls.target).add(new Vector3().setFromSpherical(sphere));
    controls.update();
  }
  function zoom(factor) {
    if (!controls) return;
    camera.position.sub(controls.target).multiplyScalar(factor).add(controls.target);
    controls.update();
  }
  function dispose() {
    if (closed) return;
    closed = true;
    observer?.disconnect();
    intersection?.disconnect();
    controls?.dispose();
    document.removeEventListener("visibilitychange", render);
    if (scene || model) disposeScenes([...(model?.scenes ?? []), ...(scene ? [scene] : [])]);
    if (renderer) {
      renderer.domElement.remove();
      renderer.dispose();
      renderer.forceContextLoss();
    }
  }

  async function load(file, stats) {
    try {
      const buffer = await file.arrayBuffer();
      if (closed) return;
      validateResources(buffer, stats);
      const manager = new LoadingManager();
      manager.setURLModifier(url => {
        if (embeddedData.test(url) || url.startsWith(`blob:${location.origin}/`)) return url;
        throw Error(externalError);
      });
      model = await new GLTFLoader(manager).parseAsync(buffer, "");
      if (closed) {
        disposeScenes(model.scenes);
        model = undefined;
        return;
      }
      if (!model.scene) throw Error("O arquivo não declara uma cena para visualizar.");

      const bounds = new Box3().setFromObject(model.scene);
      if (bounds.isEmpty()) throw Error("A cena não contém geometria visível.");
      const sphere = bounds.getBoundingSphere(new Sphere());
      if (!Number.isFinite(sphere.radius)) throw Error("Dimensões inválidas na cena.");
      center.copy(sphere.center);
      radius = Math.max(sphere.radius, 0.001);

      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2", { antialias: true, powerPreference: "low-power" });
      if (!gl) throw Error("WebGL 2 indisponível neste navegador.");
      renderer = new WebGLRenderer({ canvas, context: gl });
      const compactDevice = matchMedia("(max-width: 760px)").matches;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, compactDevice ? 1 : 1.5));
      renderer.toneMapping = ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.3;
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", "Visualização 3D do modelo importado");
      canvas.addEventListener("webglcontextlost", event => {
        event.preventDefault();
        if (closed) return;
        dispose();
        onError("A sessão WebGL foi encerrada. Abra a prévia novamente.");
      });

      scene = new Scene();
      scene.background = new Color("#151c26");
      scene.add(model.scene, new HemisphereLight(0xf0fbff, 0x51546a, 2));
      const key = new DirectionalLight(0xfff3db, 2.15);
      key.position.copy(center).addScaledVector(direction, radius);
      key.target.position.copy(center);
      scene.add(key, key.target);
      const grid = new GridHelper(radius * 5, 14, 0x405163, 0x283747);
      grid.position.set(center.x, bounds.min.y - radius * 0.035, center.z);
      scene.add(grid);

      container.append(canvas);
      controls = new OrbitControls(camera, canvas);
      controls.addEventListener("change", render);
      observer = new ResizeObserver(resize);
      observer.observe(container);
      intersection = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        render();
      });
      intersection.observe(container);
      document.addEventListener("visibilitychange", render);
      resize();
      frame();
      const thumbnail = document.createElement("canvas");
      thumbnail.width = 280;
      thumbnail.height = 180;
      const context = thumbnail.getContext("2d");
      if (context && canvas.width && canvas.height) {
        const scale = Math.min(thumbnail.width / canvas.width, thumbnail.height / canvas.height);
        const width = canvas.width * scale, height = canvas.height * scale;
        context.fillStyle = "#151c26";
        context.fillRect(0, 0, thumbnail.width, thumbnail.height);
        context.drawImage(canvas, (thumbnail.width - width) / 2, (thumbnail.height - height) / 2, width, height);
        onThumbnail(thumbnail.toDataURL("image/webp", 0.82));
      }
    } catch (error) {
      if (closed) return;
      dispose();
      onError(error.message || "Não foi possível abrir a cena 3D.");
    }
  }
  return { load, dispose, frame, orbit, zoom };
}
