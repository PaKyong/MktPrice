// 장보기 목록 저장. 화면은 이 파일의 함수만 부른다.
// 지금은 폰 안 저장 공간(localStorage)에 두고, 나중에 가족 공유로 바꿀 때 이 파일만 바꾼다.
// 그래서 함수는 처음부터 결과를 나중에 돌려주는 방식(Promise)이다.

const KEY = "mp.list.v1";
let memory = null;

// 저장 공간을 못 쓰는 브라우저(사생활 보호 모드 등)에서는 이 화면을 연 동안만 목록을 유지한다.
function load() {
  if (memory) return memory;
  try {
    memory = JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    memory = [];
  }
  return memory;
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // 저장하지 못해도 화면은 메모리의 목록으로 이어 간다.
  }
}

// 목록: [{ id, name, qty }]. name은 품종이 가격 파일에서 빠져도 이름을 보여 주려고 함께 둔다.
export async function getList() {
  return load().map((entry) => ({ ...entry }));
}

export async function addItem(id, name) {
  const list = load();
  if (!list.some((entry) => entry.id === id)) {
    list.push({ id, name, qty: 1 });
    save();
  }
}

export async function removeItem(id) {
  memory = load().filter((entry) => entry.id !== id);
  save();
}

export async function setQty(id, qty) {
  const entry = load().find((e) => e.id === id);
  if (entry) {
    entry.qty = Math.max(1, Math.round(qty));
    save();
  }
}
