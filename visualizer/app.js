const fileInput = document.getElementById("fileInput");
const board = document.getElementById("board");
const actionView = document.getElementById("actionView");
const speedInput = document.getElementById("speedInput");

let events = [];
let states = [];
let actions = [];
let current = 0;
let timer = null;

const cols = "abcdefghi";

function parseLog(text) {
  events = text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  states = events.filter((event) => event.type === "state");
  actions = events.filter((event) => event.type === "action");
  current = 0;
  render();
}

function coordToXY(coord) {
  return { x: cols.indexOf(coord[0]) + 1, y: Number(coord[1]) };
}

function render() {
  const state = states[current];
  board.innerHTML = "";
  for (let y = 9; y >= 1; y -= 1) {
    for (let x = 1; x <= 9; x += 1) {
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.dataset.coord = `${cols[x - 1]}${y}`;
      const coord = document.createElement("span");
      coord.className = "coord";
      coord.textContent = cell.dataset.coord;
      cell.appendChild(coord);
      board.appendChild(cell);
    }
  }
  if (!state) return;
  placePawn("P1", state.pawns.P1);
  placePawn("P2", state.pawns.P2);
  state.walls.forEach(placeWall);

  const start = events.find((event) => event.type === "start");
  const end = events.find((event) => event.type === "end");
  const previousAction = actions.find((event) => event.turn_index === state.turn_index);
  setText("matchId", start?.match_id || "-");
  setText("turnIndex", state.turn_index);
  setText("turnSide", state.turn || "-");
  setText("winner", end && current === states.length - 1 ? `${end.winner} (${end.reason})` : "-");
  setText("p1Invalid", end?.p1_invalid_count ?? countInvalid("P1"));
  setText("p2Invalid", end?.p2_invalid_count ?? countInvalid("P2"));
  actionView.classList.toggle("invalid", Boolean(previousAction?.was_invalid));
  actionView.textContent = previousAction ? JSON.stringify(previousAction, null, 2) : "開始局面";
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function countInvalid(player) {
  return actions.filter((action) => action.player === player && action.was_invalid).length;
}

function placePawn(player, coord) {
  const cell = board.querySelector(`[data-coord="${coord}"]`);
  if (!cell) return;
  const pawn = document.createElement("div");
  pawn.className = `pawn ${player === "P1" ? "p1" : "p2"}`;
  pawn.textContent = player;
  cell.appendChild(pawn);
}

function placeWall(wall) {
  const { x, y } = coordToXY(wall.at);
  const element = document.createElement("div");
  element.className = `wall ${wall.orientation}`;
  const cellSize = 100 / 9;
  element.style.left = `${(x - 1) * cellSize}%`;
  if (wall.orientation === "h") {
    element.style.top = `${(9 - y) * cellSize}%`;
  } else {
    element.style.left = `${x * cellSize}%`;
    element.style.top = `${(9 - (y + 1)) * cellSize}%`;
  }
  board.appendChild(element);
}

function step(delta) {
  current = Math.max(0, Math.min(states.length - 1, current + delta));
  render();
}

function togglePlay() {
  if (timer) {
    clearInterval(timer);
    timer = null;
    document.getElementById("playBtn").textContent = "Play";
    return;
  }
  document.getElementById("playBtn").textContent = "Pause";
  timer = setInterval(() => {
    if (current >= states.length - 1) {
      togglePlay();
    } else {
      step(1);
    }
  }, Number(speedInput.value));
}

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (file) parseLog(await file.text());
});
document.getElementById("firstBtn").addEventListener("click", () => {
  current = 0;
  render();
});
document.getElementById("prevBtn").addEventListener("click", () => step(-1));
document.getElementById("nextBtn").addEventListener("click", () => step(1));
document.getElementById("lastBtn").addEventListener("click", () => {
  current = Math.max(0, states.length - 1);
  render();
});
document.getElementById("playBtn").addEventListener("click", togglePlay);
speedInput.addEventListener("input", () => {
  if (timer) {
    togglePlay();
    togglePlay();
  }
});

