export function latLngToVector3(lat, lon, radius = 1) {
    const phi = (90 - lat) * Math.PI / 180;
    const theta = (lon + 180) * Math.PI / 180;

    return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta)
    );
}

export function createNode(globe, lat, lon, type, info) {

    const colors = {
        user: 0x00ff00,
        vpn: 0x0000ff,
        server: 0xff0000
    };

    const pos = latLngToVector3(lat, lon, 1.02);

    const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.02),
        new THREE.MeshBasicMaterial({ color: colors[type] })
    );

    mesh.position.copy(pos);

    // 🔥 Attach metadata
    mesh.userData = {
        type,
        ...info
    };

    globe.add(mesh);

    return mesh;
}

export function addNodes(globe) {
    return []; // now it's a dynamic list
}