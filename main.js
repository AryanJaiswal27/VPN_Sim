// ==========================
// IMPORTS
// ==========================

import { addNodes } from './js/nodes.js';
import { updateConnections, animatePackets } from './js/connections.js';
import { addControls, enableNodePlacement } from './js/controls.js';
import { createNode } from './js/nodes.js';

import { createGlobe, setGlobeTexture } from './js/globe.js';


let theme = "light";
document.body.classList.add("light");

// ==========================
// SCENE SETUP
// ==========================
let scene = new THREE.Scene();

let camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
);
camera.position.z = 3;

let renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);


// ==========================
// OBJECTS
// ==========================
let globe = createGlobe(scene);
let nodes = addNodes(globe); // now []
let connections = [];
let vpnOn = false;


// ==========================
// MODE SYSTEM
// ==========================
let mode = "spectator"; // default
let rotateGlobe = true;


// ==========================
// CONTROLS
// ==========================
addControls(globe, () => mode);
enableNodePlacement(camera, scene, globe, nodes, () => mode);


// ==========================
// UI BUTTONS
// ==========================
const modeBtn = document.getElementById("modeToggle");

modeBtn.onclick = () => {

    if (mode === "spectator") {

        mode = "edit";
        rotateGlobe = false;

        modeBtn.innerText = "Spectator Mode";

    } else {

        mode = "spectator";
        rotateGlobe = true;

        modeBtn.innerText = "Edit Mode";

        // 🔥 clear active node selection
        document.querySelectorAll(".node-btn")
            .forEach(b => b.classList.remove("active"));

        window.setMode(null);
    }

    refreshVisualization();
    updateUIState();
};


// VPN toggle (ONLY spectator)
document.getElementById("toggleVPN").onclick = () => {

    if (mode !== "spectator") return;

    vpnOn = !vpnOn;
    refreshVisualization();
};


// rotation toggle (ONLY spectator)
document.getElementById("toggleRotation").onclick = () => {

    if (mode !== "spectator") return;

    rotateGlobe = !rotateGlobe;
};


// ==========================
// VISUALIZATION CONTROL
// ==========================
function refreshVisualization() {

    // remove old connections
    connections.forEach(c => globe.remove(c));
    connections.length = 0;

    // only show in spectator mode
    if (mode === "spectator") {
        updateConnections(globe, nodes, vpnOn, connections);
    }
}


// ==========================
// LIGHT + BACKGROUND
// ==========================
const light = new THREE.PointLight(0xffffff, 1);
light.position.set(5, 5, 5);
scene.add(light);

const loader = new THREE.TextureLoader();
scene.background = loader.load('assets/starfield.jpg');


// ==========================
// RESIZE
// ==========================
window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});


// ==========================
// ANIMATION LOOP
// ==========================
function animate() {
    requestAnimationFrame(animate);

    if (rotateGlobe) {
        globe.rotation.y += 0.001;
    }

    // packets only in spectator mode
    if (mode === "spectator") {
        animatePackets(globe, connections);
    }

    renderer.render(scene, camera);
}
animate();


// ==========================
// INITIAL LOAD
// ==========================
refreshVisualization();



const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

const tooltip = document.createElement("div");
tooltip.style.position = "absolute";
tooltip.style.padding = "6px 10px";
tooltip.style.background = "rgba(0,0,0,0.7)";
tooltip.style.color = "#fff";
tooltip.style.fontSize = "12px";
tooltip.style.pointerEvents = "none";
tooltip.style.display = "none";
document.body.appendChild(tooltip);


function getDistance(a, b) {
    return a.position.distanceTo(b.position);
}

function getNearestVPN(user, vpns) {
    if (vpns.length === 0) return null;

    let nearest = vpns[0];
    let minDist = getDistance(user, vpns[0]);

    for (let i = 1; i < vpns.length; i++) {
        const dist = getDistance(user, vpns[i]);
        if (dist < minDist) {
            minDist = dist;
            nearest = vpns[i];
        }
    }

    return nearest;
}




// window.addEventListener("click", (event) => {

//     // ignore UI clicks
//     if (event.target.closest("#ui")) return;

//     // only in spectator mode
//     if (mode !== "spectator") return;

//     mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
//     mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

//     raycaster.setFromCamera(mouse, camera);

//     const intersects = raycaster.intersectObjects(nodes);

//     if (intersects.length > 0) {

//         const node = intersects[0].object;

//         // ✅ only allow USER nodes
//         if (node.userData.type !== "user") return;

//         const serverName = prompt("Enter server name:");

//         if (!serverName) return;

//         // 🔥 store per user
//         node.userData.targetServer = serverName;

//         refreshVisualization();
//     }
// });


window.addEventListener("click", (event) => {

    if (event.target.closest("#ui")) return;

    if (mode !== "spectator") return;

    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(nodes);

    if (intersects.length > 0) {

        const node = intersects[0].object;

        // ==========================
        // 👤 USER CLICK
        // ==========================
        if (node.userData.type === "user") {

            const serverName = prompt("Enter server name:");

            if (!serverName) return;

            node.userData.targetServer = serverName;

            refreshVisualization();
        }

        // ==========================
        // 🖥️ SERVER CLICK
        // ==========================
        else if (node.userData.type === "server") {

            const server = node;

            const users = nodes.filter(n => n.userData.type === "user");
            const vpns = nodes.filter(n => n.userData.type === "vpn");

            let output = "Connected Clients:\n\n";

            users.forEach(user => {

                // only consider users connected to THIS server
                if (user.userData.targetServer !== server.userData.name) return;

                let visibleIP = user.userData.ip;

                if (vpnOn) {
                    const vpn = getNearestVPN(user, vpns);

                    if (vpn) {
                        visibleIP = vpn.userData.ip || "VPN IP";
                    }
                }

                output += `${user.userData.name} → ${visibleIP}\n`;
            });

            alert(output);
        }
    }
});



window.addEventListener("mousemove", (event) => {

    if (mode !== "spectator") {
        tooltip.style.display = "none";
        return;
    }

    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(nodes);

    if (intersects.length > 0) {

        const obj = intersects[0].object;
        const data = obj.userData;

        tooltip.style.display = "block";
        tooltip.style.left = event.clientX + 10 + "px";
        tooltip.style.top = event.clientY + 10 + "px";

        tooltip.innerHTML = `
            <b>${data.name || "Unknown"}</b><br>
            IP: ${data.ip || "N/A"}<br>
            Type: ${data.type}
        `;

    } else {
        tooltip.style.display = "none";
    }
});



const nodeButtons = document.querySelectorAll(".node-btn");

nodeButtons.forEach(btn => {
    btn.addEventListener("click", (e) => {

        // remove active from all
        nodeButtons.forEach(b => b.classList.remove("active"));

        // add active to clicked
        btn.classList.add("active");

        // set mode
        const type = btn.dataset.type;
        window.setMode(type);
    });
});

function updateUIState() {
    const isEdit = mode === "edit";

    document.querySelectorAll(".node-btn").forEach(btn => {
        btn.disabled = !isEdit;
    });
}



document.getElementById("exportBtn").onclick = () => {

    const data = nodes.map(node => ({
        type: node.userData.type,
        name: node.userData.name,
        ip: node.userData.ip,
        targetServer: node.userData.targetServer || null,
        position: {
            x: node.position.x,
            y: node.position.y,
            z: node.position.z
        }
    }));

    const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json"
    });

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "vpn-simulation.json";
    a.click();

    URL.revokeObjectURL(url);
};


document.getElementById("importBtn").onclick = () => {
    document.getElementById("fileInput").click();
};

document.getElementById("fileInput").addEventListener("change", (event) => {

    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();

    reader.onload = (e) => {

        const data = JSON.parse(e.target.result);

        // 🧹 clear existing nodes
        nodes.forEach(n => globe.remove(n));
        nodes.length = 0;

        // 🔄 recreate nodes
        data.forEach(item => {

            const mesh = createNode(
                globe,
                0, 0, // temporary
                item.type,
                {
                    name: item.name,
                    ip: item.ip
                }
            );

            // restore position directly
            mesh.position.set(
                item.position.x,
                item.position.y,
                item.position.z
            );

            // restore target server
            if (item.targetServer) {
                mesh.userData.targetServer = item.targetServer;
            }

            nodes.push(mesh);
        });

        refreshVisualization();
    };

    reader.readAsText(file);
});


document.getElementById("themeToggle").onclick = () => {

    if (theme === "light") {

        theme = "dark";

        document.body.classList.remove("light");
        document.body.classList.add("dark");

        setGlobeTexture("dark");

        // 🌙 darker background
        // scene.background = new THREE.Color(0x050505);
        const loader = new THREE.TextureLoader();
        scene.background = loader.load('assets/starfield.jpg');

        document.getElementById("themeToggle").innerText = "☀️ Light Mode";

    } else {

        theme = "light";

        document.body.classList.remove("dark");
        document.body.classList.add("light");

        setGlobeTexture("light");

        // 🌌 restore stars
        const loader = new THREE.TextureLoader();
        scene.background = loader.load('assets/starfield.jpg');

        document.getElementById("themeToggle").innerText = "🌙 Dark Mode";
    }
};

// CN - Project