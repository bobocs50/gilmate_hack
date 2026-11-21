// The words of the phone page and of the handoff card. English is the key; Korean is listed here.
// A sentence without a Korean line is shown in English. Names and saved texts are shown as given.

const KO = {
  "Open your route on your phone": "휴대폰에서 경로 열기",
  "Copy link": "링크 복사",
  "Copied": "복사됨",
  "Not copied: select the link instead": "복사하지 못했습니다. 링크를 직접 선택해 주세요",
  "Close": "닫기",
  "Fold": "접기",
  "Phone": "휴대폰",
  "The route is in this link.": "경로가 이 링크 안에 들어 있습니다.",
  "This link opens the saved run.": "이 링크는 저장된 실행을 엽니다.",
  "The route is too large for a QR code. Copy the link instead.": "경로가 QR 코드에 담기에는 너무 큽니다. 링크를 복사해 주세요.",
  "There is no route yet.": "아직 경로가 없습니다.",
  "This address only works on this computer. Start with scripts/demo.sh --phone.": "이 주소는 이 컴퓨터에서만 열립니다. scripts/demo.sh --phone 으로 시작해 주세요.",
  "This browser cannot put the route into a link.": "이 브라우저는 경로를 링크에 담을 수 없습니다.",
  "QR code of the link": "링크의 QR 코드",

  "Stop {n} of {count}": "{count}곳 중 {n}번째",
  "Name unknown": "이름 알 수 없음",
  "Wheelchair access listed on the map": "지도에 휠체어 출입 가능으로 표시",
  "Limited wheelchair access listed on the map": "지도에 휠체어 출입 제한으로 표시",
  "Listed on the map as not wheelchair accessible": "지도에 휠체어 출입 불가로 표시",
  "Entrance access unknown": "입구 접근성 알 수 없음",
  "Street photo taken {distance} m from here": "여기서 {distance}m 떨어진 곳에서 찍은 거리 사진",
  "Street photo taken near here": "이 근처에서 찍은 거리 사진",
  "Photo of the place": "이 장소의 사진",
  "No photo found": "사진을 찾지 못했습니다",
  "The photo could not be loaded": "사진을 불러오지 못했습니다",
  "{distance} to {name}": "{name}까지 {distance}",
  "Distance to {name} unknown": "{name}까지의 거리 알 수 없음",
  "the next stop": "다음 장소",
  "the stop before": "이전 장소",
  "No stairs mapped": "지도에 표시된 계단 없음",
  "Stairs on the way": "가는 길에 계단 있음",
  "Stairs unknown": "계단 여부 알 수 없음",
  "No bench mapped": "지도에 표시된 벤치 없음",
  "1 bench mapped": "지도에 벤치 1곳",
  "{count} benches mapped": "지도에 벤치 {count}곳",
  "Not a mapped path: a straight line": "지도에 없는 길: 직선으로 표시",
  "This is the last stop.": "마지막 장소입니다.",
  "Next": "다음",
  "Done": "완료",
  "How was the walk here from {from}?": "{from}에서 여기까지 걷기는 어땠나요?",
  "Fine": "괜찮았어요",
  "Too far": "너무 멀었어요",
  "Sending your answer": "답변을 보내는 중",
  "You said: fine.": "괜찮았다고 답하셨습니다.",
  "You said: too far.": "너무 멀었다고 답하셨습니다.",
  "Kept on this phone, not sent.": "이 휴대폰에만 저장되었고 보내지 않았습니다.",
  "Saved by your guide.": "가이드가 저장했습니다.",
  "The guide could not be reached. Kept on this phone, not sent.": "가이드에 연결하지 못했습니다. 이 휴대폰에만 저장되었고 보내지 않았습니다.",
  "The guide did not save it ({reason}). Kept on this phone.": "가이드가 저장하지 않았습니다({reason}). 이 휴대폰에만 저장되었습니다.",
  "no reason given": "이유 없음",
  "Your route note": "경로 메모",
  "No route note came with this route.": "이 경로에는 경로 메모가 없습니다.",
  "Copy": "복사",
  "Not copied: select the text instead": "복사하지 못했습니다. 글을 직접 선택해 주세요",
  "Language": "언어",
  "1 answer about a walk is kept on this phone and was not sent.": "걷기에 대한 답변 1개가 이 휴대폰에만 저장되었고 보내지 않았습니다.",
  "{count} answers about the walks are kept on this phone and were not sent.": "걷기에 대한 답변 {count}개가 이 휴대폰에만 저장되었고 보내지 않았습니다.",
  "Route from the link": "링크로 받은 경로",
  "Saved run, {time}": "저장된 실행, {time}",
  "Saved run": "저장된 실행",
  "Opening your route": "경로를 여는 중",
  "This link could not be read as a route.": "이 링크에서 경로를 읽지 못했습니다.",
  "Scan the code again on the computer, or copy the whole link.": "컴퓨터에서 코드를 다시 스캔하거나 링크 전체를 복사해 주세요.",
  "This browser is too old to open the route from the link.": "이 브라우저는 너무 오래되어 링크에서 경로를 열 수 없습니다.",
  "No saved run could be read, so there is no route to show.": "저장된 실행을 읽지 못해 보여 드릴 경로가 없습니다.",
  "Map of this walk": "이 구간의 지도",
  "The walk to {name}": "{name}까지 가는 길",
};

let lang = "en";

export function setLang(value) {
  lang = value === "ko" ? "ko" : "en";
  return lang;
}

export function getLang() {
  return lang;
}

/** t("{distance} to {name}", { distance: "345 m", name: "Loft" }) */
export function t(key, values = {}) {
  const sentence = lang === "ko" ? KO[key] ?? key : key;
  return sentence.replace(/\{(\w+)\}/g, (whole, name) => (Object.hasOwn(values, name) ? String(values[name]) : whole));
}

/** The text of an {en, ko} field in the page's language, the other language when that one is empty, or null. */
export function said(field) {
  if (!field || typeof field !== "object") return null;
  const first = lang === "ko" ? "ko" : "en";
  const other = first === "ko" ? "en" : "ko";
  if (field[first]) return { text: field[first], lang: first };
  if (field[other]) return { text: field[other], lang: other };
  return null;
}
