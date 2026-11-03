// 즐겨찾기 저장. 화면은 이 파일의 함수만 부른다.
// 지금은 폰 안 저장 공간(localStorage)에 두고, 나중에 가족 공유로 바꿀 때 이 파일만 바꾼다.
// 그래서 함수는 처음부터 결과를 나중에 돌려주는 방식(Promise)이다.

const KEY = "mp.fav.v1";
// 2026-11-03 전의 장보기 목록([{ id, name, qty }]). 처음 열 때 즐겨찾기로 한 번 옮기고 지운다.
const OLD_KEY = "mp.list.v1";
let memory = null;

// 옛 목록을 담은 순서대로 즐겨찾기 모양으로 바꾼다. 개수는 버리고, 같은 품종은 한 번만 남긴다.
function migrate(old) {
  const seen = new Set();
  return old.filter((e) => !seen.has(e.id) && seen.add(e.id)).map((e) => ({ id: e.id, name: e.name }));
}

// 저장 공간을 못 쓰는 브라우저(사생활 보호 모드 등)에서는 이 화면을 연 동안만 즐겨찾기를 유지한다.
function load() {
  if (memory) return memory;
  try {
    const saved = localStorage.getItem(KEY);
    const old = localStorage.getItem(OLD_KEY);
    if (saved === null && old !== null) {
      memory = migrate(JSON.parse(old));
      localStorage.setItem(KEY, JSON.stringify(memory));
      localStorage.removeItem(OLD_KEY);
    } else {
      memory = JSON.parse(saved || "[]");
    }
  } catch {
    memory = [];
  }
  return memory;
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // 저장하지 못해도 화면은 메모리의 즐겨찾기로 이어 간다.
  }
}

// 즐겨찾기: 넣은 순서대로 [{ id, name }]. name은 품종이 가격 파일에서 빠져도 이름을 보여 주려고 함께 둔다.
export async function getFavorites() {
  return load().map((entry) => ({ ...entry }));
}

export async function addFavorite(id, name) {
  const list = load();
  if (!list.some((entry) => entry.id === id)) {
    list.push({ id, name });
    save();
  }
}

export async function removeFavorite(id) {
  memory = load().filter((entry) => entry.id !== id);
  save();
}
