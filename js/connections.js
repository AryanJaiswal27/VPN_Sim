// ==========================
// CREATE CURVE
// ==========================
export function createCurve(globe, start, end) {

    const distance = start.distanceTo(end);

    const mid = start.clone().add(end).multiplyScalar(0.5);

    const height = 1.2 + distance * 0.3;
    mid.normalize().multiplyScalar(height);

    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);

    const points = curve.getPoints(100);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);

    const material = new THREE.LineBasicMaterial({ color: 0xffffff });

    const line = new THREE.Line(geometry, material);
    globe.add(line);

    return line;
}


// ==========================
// UPDATE CONNECTIONS
// ==========================
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

function findServerByName(servers, name) {
    return servers.find(s =>
        s.userData.name?.toLowerCase() === name.toLowerCase()
    );
}


// ==========================
// UPDATE CONNECTIONS
// ==========================
export function updateConnections(globe, nodes, vpnOn, connections) {

    connections.forEach(c => globe.remove(c));
    connections.length = 0;

    const users = nodes.filter(n => n.userData.type === "user");
    const vpns = nodes.filter(n => n.userData.type === "vpn");
    const servers = nodes.filter(n => n.userData.type === "server");

    users.forEach(user => {

        const targetName = user.userData.targetServer;
        if (!targetName) return;

        const server = findServerByName(servers, targetName);
        if (!server) return;

        if (vpnOn) {

            const vpn = getNearestVPN(user, vpns);

            if (vpn) {
                connections.push(createCurve(globe, user.position, vpn.position));
                connections.push(createCurve(globe, vpn.position, server.position));
            } else {
                connections.push(createCurve(globe, user.position, server.position));
            }

        } else {
            connections.push(createCurve(globe, user.position, server.position));
        }
    });
}


// ==========================
// PACKET ANIMATION
// ==========================
export function animatePackets(globe, connections) {

    connections.forEach(line => {

        const points = line.geometry.attributes.position.array;

        let t = (performance.now() * 0.0008) % 1;
        let index = Math.floor(t * (points.length / 3));

        const x = points[index * 3];
        const y = points[index * 3 + 1];
        const z = points[index * 3 + 2];

        const packet = new THREE.Mesh(
            new THREE.SphereGeometry(0.015),
            new THREE.MeshBasicMaterial({ color: 0x00ffff })
        );

        packet.position.set(x, y, z);

        globe.add(packet);

        setTimeout(() => globe.remove(packet), 200);
    });
}