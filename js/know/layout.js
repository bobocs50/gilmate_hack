// Where the dots of the knowledge graph go. Plain numbers only: no page, no drawing, no memory.
// The world is measured in px at zoom 1, the guide sits at [0, 0].

const SAMPLES = 360;        // points used to measure the ring
const MIN_ARC = 112;        // px of ring a fact needs so that its name has room
const GROUP_GAP = 0.7;      // empty room between two sources, in facts
const INNER = 0.52;         // the ring of sources, as a share of the ring of facts

/**
 * The tidy start: sources on an inner ring, each source's facts behind it on the outer ring.
 * groups: [{ id, facts: [id] }], ground: { width, height } of the visible ground in px.
 * Returns Map id -> [x, y]. Equal shares are equal distances along the ring, so names keep their room
 * on a tall phone ground as well as on a wide one.
 */
export function ringLayout(groups, ground) {
  const rooms = groups.map((group) => Math.max(group.facts.length, 1) + GROUP_GAP);
  const total = rooms.reduce((sum, room) => sum + room, 0) || 1;
  let rx = clamp(ground.width / 2 - 84, 150, 380);
  let ry = clamp(ground.height / 2 - 96, 150, 250);
  let ring = measure(rx, ry);
  const need = total * MIN_ARC;
  if (ring.length < need) {
    const grow = need / ring.length;
    rx *= grow;
    ry *= grow;
    ring = measure(rx, ry);
  }
  const spots = new Map();
  const first = rooms[0] / 2;             // the first source is centred at the top
  let before = 0;
  groups.forEach((group, index) => {
    const room = rooms[index];
    const middle = (before + room / 2 - first) / total;
    spots.set(group.id, ring.point(middle, INNER));
    const start = before + (room - group.facts.length) / 2;
    group.facts.forEach((id, slot) => spots.set(id, ring.point((start + slot + 0.5 - first) / total, 1)));
    before += room;
  });
  return spots;
}

function measure(rx, ry) {
  const steps = [];
  let length = 0;
  let last = [0, -ry];
  for (let i = 1; i <= SAMPLES; i += 1) {
    const a = (i / SAMPLES) * 2 * Math.PI;
    const p = [rx * Math.sin(a), -ry * Math.cos(a)];
    length += Math.hypot(p[0] - last[0], p[1] - last[1]);
    steps.push(length);
    last = p;
  }
  return {
    length,
    point(share, scale) {
      const target = (((share % 1) + 1) % 1) * length;
      const a = ((steps.findIndex((sum) => sum >= target) + 1) / SAMPLES) * 2 * Math.PI;
      return [rx * scale * Math.sin(a), -ry * scale * Math.cos(a)];
    },
  };
}

/** The room a dot and the name under it take, around the dot's middle at [x, y]. w, h: the size of the name. */
export function boxOf(node, x = node.x, y = node.y) {
  const half = Math.max(node.w, 28) / 2;
  return { left: x - half, right: x + half, top: y - node.r - 4, bottom: y + node.r + 5 + node.h };
}

/**
 * Pushes dots apart until no name lies on another one. nodes: [{ id, tx, ty, w, h, r, fixed }], changed in place
 * (tx, ty are where each dot should come to rest). A fixed dot (one she placed herself) does not give way.
 */
export function separate(nodes, gap = 8) {
  for (let round = 0; round < 80; round += 1) {
    let moved = false;
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        if (a.fixed && b.fixed) continue;
        const ra = boxOf(a, a.tx, a.ty);
        const rb = boxOf(b, b.tx, b.ty);
        const overX = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left) + gap;
        const overY = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top) + gap;
        if (overX <= 0 || overY <= 0) continue;
        moved = true;
        // Give way along the shorter way out; a dot exactly on another one leaves sideways.
        const alongX = overX < overY;
        const push = alongX ? overX : overY;
        const centreA = alongX ? (ra.left + ra.right) / 2 : (ra.top + ra.bottom) / 2;
        const centreB = alongX ? (rb.left + rb.right) / 2 : (rb.top + rb.bottom) / 2;
        const sign = centreA <= centreB ? -1 : 1;
        const shareA = a.fixed ? 0 : b.fixed ? 1 : 0.5;
        const key = alongX ? "tx" : "ty";
        a[key] += sign * push * shareA;
        b[key] -= sign * push * (1 - shareA);
      }
    }
    if (!moved) break;
  }
  return nodes;
}

/** True when two boxes of the list lie on each other (used by the page check through the graph's own data). */
export function overlaps(nodes) {
  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const a = boxOf(nodes[i], nodes[i].tx, nodes[i].ty);
      const b = boxOf(nodes[j], nodes[j].tx, nodes[j].ty);
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5) return true;
    }
  }
  return false;
}

/**
 * One step of the light spring that brings a released dot to rest at [tx, ty].
 * Slightly under-damped: it arrives quickly and settles without a visible bounce. Returns true while it still moves.
 */
export function springStep(node, dt, stiffness = 230, damping = 25) {
  const dx = node.x - node.tx;
  const dy = node.y - node.ty;
  if (Math.abs(dx) < 0.08 && Math.abs(dy) < 0.08 && Math.abs(node.vx) < 2 && Math.abs(node.vy) < 2) {
    node.x = node.tx;
    node.y = node.ty;
    node.vx = 0;
    node.vy = 0;
    return false;
  }
  node.vx += (-stiffness * dx - damping * node.vx) * dt;
  node.vy += (-stiffness * dy - damping * node.vy) * dt;
  node.x += node.vx * dt;
  node.y += node.vy * dt;
  return true;
}

/** The zoom and shift that show all boxes inside the ground, never larger than life. pad: [top, right, bottom, left]. */
export function fitView(nodes, ground, pad = [48, 20, 44, 20], limits = [0.55, 1]) {
  if (!nodes.length) return { k: 1, tx: ground.width / 2, ty: ground.height / 2 };
  const boxes = nodes.map((node) => boxOf(node, node.tx, node.ty));
  const left = Math.min(...boxes.map((box) => box.left));
  const right = Math.max(...boxes.map((box) => box.right));
  const top = Math.min(...boxes.map((box) => box.top));
  const bottom = Math.max(...boxes.map((box) => box.bottom));
  const roomX = Math.max(60, ground.width - pad[1] - pad[3]);
  const roomY = Math.max(60, ground.height - pad[0] - pad[2]);
  const k = clamp(Math.min(roomX / (right - left), roomY / (bottom - top)), limits[0], limits[1]);
  return {
    k,
    tx: pad[3] + roomX / 2 - ((left + right) / 2) * k,
    ty: pad[0] + roomY / 2 - ((top + bottom) / 2) * k,
  };
}

export function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
