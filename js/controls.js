import { createNode } from './nodes.js';


function isValidIP(ip) {
    const regex =
        /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;
    return regex.test(ip);
}

function isDuplicateIP(ip, nodes) {
    return nodes.some(n => n.userData.ip === ip);
}



// ==========================
// GLOBE ROTATION CONTROLS
// ==========================
export function addControls(globe, getMode) {
    let isDragging = false;
    let prevX = 0;
    let prevY = 0;

    window.addEventListener('mousedown', (e) => {
        if (getMode() !== "spectator") return;

        isDragging = true;
        prevX = e.clientX;
        prevY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        let deltaX = e.clientX - prevX;
        let deltaY = e.clientY - prevY;

        globe.rotation.y += deltaX * 0.005;
        globe.rotation.x += deltaY * 0.005;

        globe.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, globe.rotation.x));

        prevX = e.clientX;
        prevY = e.clientY;
    });
}


// ==========================
// NODE SELECTION MODE
// ==========================
let currentMode = null;

export function setMode(type) {
    currentMode = type;
}
window.setMode = setMode;


// ==========================
// NODE PLACEMENT
// ==========================
export function enableNodePlacement(camera, scene, globe, nodes, getMode) {

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const preview = new THREE.Mesh(
        new THREE.SphereGeometry(0.025),
        new THREE.MeshBasicMaterial({ color: 0xffff00 })
    );

    globe.add(preview);
    preview.visible = false;


    // mouse move → preview
    window.addEventListener('mousemove', (event) => {

        if (getMode() !== "edit") {
            preview.visible = false;
            return;
        }

        preview.visible = true;

        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);

        const intersects = raycaster.intersectObject(globe, true);

                if (intersects.length > 0) {

                    // ✅ find the closest valid (front-facing) intersection
                    let validPoint = null;

                    for (let i = 0; i < intersects.length; i++) {

                        const point = intersects[i].point.clone();

                        const normal = point.clone().normalize();
                        const cameraDir = camera.position.clone().normalize();

                        // ✅ only accept points facing camera
                        if (normal.dot(cameraDir) > 0) {
                            validPoint = point;
                            break; // first valid = closest
                        }
                    }

                    if (!validPoint) {
                        preview.visible = false;
                        return;
                    }

                    // ✅ use ONLY valid point
                    const localPoint = globe.worldToLocal(validPoint);
                    localPoint.normalize().multiplyScalar(1.02);

                    preview.position.copy(localPoint);
                    preview.visible = true;

                } else {
                    preview.visible = false;
                }
    });


    // click → place node
  window.addEventListener('click', (event) => {

    if (event.target.closest("#ui")) return;
    if (getMode() !== "edit") return;

    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // 🗑️ DELETE LOGIC (unchanged)
    const nodeIntersects = raycaster.intersectObjects(nodes);

    if (nodeIntersects.length > 0) {
        const node = nodeIntersects[0].object;

        globe.remove(node);
        const index = nodes.indexOf(node);
        if (index > -1) nodes.splice(index, 1);

        return;
    }

    if (!currentMode) {
        alert("⚠ Select User / VPN / Server first");
        return;
    }

    if (!preview.visible) return;

    // ✅ 🔥 CAPTURE POSITION BEFORE PROMPT
    const savedPosition = preview.position.clone();

    // convert to lat/lon BEFORE prompt
    const radius = savedPosition.length();

    const lat = 90 - (Math.acos(savedPosition.y / radius) * 180 / Math.PI);

    const lon = (
        Math.atan2(savedPosition.z, -savedPosition.x) * 180 / Math.PI
    ) - 180;

    // 🧠 NOW ask for info
    const name = prompt("Enter Name:");
    const ip = prompt("Enter IP Address:");

    // ✅ use saved values (not preview anymore)
    const newNode = createNode(
        globe,
        lat,
        lon,
        currentMode,
        { name, ip }
    );

    nodes.push(newNode);
});
}