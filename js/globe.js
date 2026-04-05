let globeMesh;
let currentTexture;

export function createGlobe(scene) {

    const loader = new THREE.TextureLoader();

    currentTexture = loader.load('assets/earth.jpg');

    const geometry = new THREE.SphereGeometry(1, 64, 64);
    const material = new THREE.MeshBasicMaterial({ map: currentTexture });

    globeMesh = new THREE.Mesh(geometry, material);
    scene.add(globeMesh);

    return globeMesh;
}


// 🔥 NEW FUNCTION
export function setGlobeTexture(type) {

    const loader = new THREE.TextureLoader();

    const texture = loader.load(
        type === "dark"
            ? 'assets/night.jpg'
            : 'assets/earth.jpg'
    );

    globeMesh.material.map = texture;
    globeMesh.material.needsUpdate = true;
}