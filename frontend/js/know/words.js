// The Korean words of the knowledge graph and of memory.js. The page's own words.js stays the first place
// for words: a sentence that has no line here is asked there. The lines are kept here as well, so that the
// graph stays Korean whatever the rest of the page keeps. English sentences are the keys.

import { t as pageWords } from "../words.js";

let lang = "en";

/** The graph is told its language with every drawing. The page's <html lang> counts as well. */
export function setKnowLang(value) {
  lang = value === "ko" ? "ko" : "en";
}

export function t(en, values = null) {
  const korean = lang === "ko" || document.documentElement.lang === "ko";
  const text = korean && KO[en] ? KO[en] : null;
  if (text === null) return pageWords(en, values);
  if (!values) return text;
  return text.replace(/\{(\w+)\}/g, (all, key) => (key in values ? String(values[key]) : all));
}

const KO = {
  // ---- the graph itself ----
  "Knowledge graph": "지식 그래프",
  "Zoom in": "확대",
  "Zoom out": "축소",
  "Tidy up": "정돈",
  "Put every dot back in its place": "모든 점을 제자리로",
  "1 thing remembered": "기억하는 것 1가지",
  "{count} things remembered": "기억하는 것 {count}가지",
  "Nothing remembered yet": "아직 기억하는 것이 없습니다",
  "Nothing yet. What you decide appears here.": "아직 없습니다. 정하신 것이 여기에 나타납니다.",
  "Only from your own answers, picks and taps.": "직접 답하고, 고르고, 누르신 것만 기억합니다.",
  "Drag a dot to move it, press it to read it.": "점을 끌면 옮겨지고, 누르면 내용이 보입니다.",
  "answered or picked": "답하거나 고르신 것",
  "Development sample": "개발용 샘플",
  "Other": "기타",
  "Kept, but its source is not one I know.": "기억하고 있지만 어디서 온 것인지는 알 수 없습니다.",
  "Your pick": "내가 고른 곳",
  "Close this card": "카드 닫기",
  "Nothing is kept here yet.": "아직 여기에 기억하는 것이 없습니다.",
  "Not in use today": "오늘은 적용 안 됨",

  // ---- memory: the three sources, the names of the facts and their state ----
  "Your answers": "내 답변",
  "Your day": "내 하루",
  "Your picks": "내가 고른 곳",
  "What you told me when I asked my questions.": "제가 여쭤봤을 때 답해 주신 내용입니다.",
  "What I learned from your taps after a walk.": "걷고 난 뒤 눌러 주신 버튼에서 제가 배운 내용입니다.",
  "The places you chose.": "직접 고르신 장소입니다.",
  "Short walks": "짧게 걷기",
  "Medium walks": "보통 거리 걷기",
  "Long walks": "오래 걷기",
  "Avoids stairs": "계단은 피하기",
  "A few stairs are fine": "계단 조금은 괜찮음",
  "Stairs are fine": "계단 괜찮음",
  "Sits down often": "자주 앉아서 쉬기",
  "Sits down sometimes": "가끔 앉아서 쉬기",
  "Rarely sits down": "거의 쉬지 않음",
  "Likes sushi": "초밥을 좋아함",
  "Likes ramen": "라멘을 좋아함",
  "Any food": "아무 음식이나 좋음",
  "Walking": "걷기",
  "Stairs": "계단",
  "Sitting down": "쉬기",
  "Food": "음식",
  "Wish": "바람",
  "{topic}: {value}": "{topic}: {value}",
  "Wish: {wish}": "바람: {wish}",
  "No wish": "바람 없음",
  "Walks up to {distance}": "{distance}까지 걷기",
  "Walking limit unknown": "걷기 한도 알 수 없음",
  "Place unknown": "장소 알 수 없음",
  "unknown": "알 수 없음",
  "Fact": "기억",
  "Your answer · {topic}": "내 답변 · {topic}",
  "Learned from your taps · Walking limit": "누르신 버튼에서 배움 · 걷기 한도",
  "Your pick · {kind}": "내가 고른 곳 · {kind}",
  "Kept fact": "기억하는 것",
  "See": "구경",
  "Shop": "쇼핑",
  "Eat": "식사",
  "still learning": "배우는 중",
  "Still learning: this is not kept for good yet.": "배우는 중입니다. 아직 계속 기억하기로 한 것은 아닙니다.",
  "Still learning. Whether it counts today is unknown: no tap with a date is saved with it.":
    "배우는 중입니다. 오늘 적용되는지는 알 수 없습니다. 날짜가 있는 기록이 함께 저장되어 있지 않습니다.",
  "Still learning. It counts for routes made today. A second “too far” would keep it.":
    "배우는 중입니다. 오늘 만드는 경로에 적용됩니다. ‘너무 멀어요’를 한 번 더 누르시면 계속 기억합니다.",
  "still learning, not in use today": "배우는 중, 오늘은 적용 안 됨",
  "Still learning, and not in use today: it comes from one tap on {day} and counted only on that day. A second “too far” would keep it.":
    "배우는 중이며 오늘은 적용되지 않습니다. {day}에 한 번 누르신 것에서 나왔고 그날에만 적용되었습니다. ‘너무 멀어요’를 한 번 더 누르시면 계속 기억합니다.",
  "learned, kept": "배워서 기억함",
  "Learned and kept: it counts for every route until you forget it.": "배워서 기억하고 있습니다. 잊으라고 하실 때까지 모든 경로에 적용됩니다.",
  "Kept until you change or forget it.": "바꾸거나 잊으라고 하실 때까지 기억합니다.",
  "state unknown": "상태 알 수 없음",
  "State unknown.": "상태를 알 수 없습니다.",
  "None": "없음",

  // ---- what the tools answered ----
  "A rule of the agent refused this step (rule: {rule}).": "에이전트의 규칙이 이 단계를 거부했습니다 (규칙: {rule}).",
  "A rule of the agent refused this step.": "에이전트의 규칙이 이 단계를 거부했습니다.",
  "The agent refused it: {reason}.": "에이전트가 거부했습니다: {reason}.",
  "The agent refused it and gave no reason.": "에이전트가 이유를 말하지 않고 거부했습니다.",
  "It is not in my memory any more.": "이미 제 기억에 없습니다.",
  "The agent answered “{status}”.": "에이전트의 답: “{status}”.",
  "Not saved: the agent finished without recording your answer.": "저장되지 않았습니다. 에이전트가 답을 기록하지 않고 끝냈습니다.",
  "Not saved. {why}": "저장되지 않았습니다. {why}",
  "Not forgotten: the agent finished without doing it.": "잊지 못했습니다. 에이전트가 하지 않고 끝냈습니다.",
  "Not forgotten. {why}": "잊지 못했습니다. {why}",
  "Forgotten: {name}.": "잊었습니다: {name}.",
  "Forgotten: {name}. I will ask you about it again.": "잊었습니다: {name}. 다시 여쭤보겠습니다.",

  // ---- the map "What Gilmate knows about you" ----
  "Map of what Gilmate knows": "길메이트가 아는 것의 지도",
  "nothing yet": "아직 없음",
  "Development sample. This memory was written for layout work, it is not about a real person.":
    "개발용 샘플입니다. 화면 작업을 위해 만든 기억이며 실제 사람의 것이 아닙니다.",
  "Also kept, without a place on the map:": "지도에 자리는 없지만 기억하는 것:",
  "Nothing is known about what Gilmate remembers.": "길메이트가 무엇을 기억하는지 알 수 없습니다.",
  "Everything here comes from your own answers, picks and taps, never from web pages.":
    "여기 있는 것은 모두 직접 답하고, 고르고, 누르신 것에서 나왔습니다. 웹 페이지에서 온 것은 없습니다.",
  "I do not know anything about you yet. I will remember your answers, your picks and what you tell me after a walk.":
    "아직 아는 것이 없습니다. 답변, 고르신 장소, 걷고 난 뒤 알려 주시는 것을 기억하겠습니다.",
  "I know 1 thing about you.": "제가 아는 것은 1가지입니다.",
  "I know {count} things about you.": "제가 아는 것은 {count}가지입니다.",
  "Press a circle to see it and to make me forget it.": "동그라미를 누르면 내용을 보고, 잊게 하실 수 있습니다.",
  "About a circle": "동그라미 설명",
  "Press a circle": "동그라미를 눌러 보세요",
  "Each circle is one thing I keep. Press it to read what I know, where it comes from, what it changes, and to make me forget it.":
    "동그라미 하나가 제가 기억하는 것 하나입니다. 누르면 제가 아는 것, 어디서 알게 되었는지, 무엇이 달라지는지 볼 수 있고, 잊게 하실 수도 있습니다.",
  "About Gilmate": "길메이트 소개",
  "The guide": "가이드",
  "I keep 1 thing about you, so I do not have to ask you twice.": "두 번 여쭤보지 않으려고 1가지를 기억하고 있습니다.",
  "I keep {count} things about you, so I do not have to ask you twice.": "두 번 여쭤보지 않으려고 {count}가지를 기억하고 있습니다.",
  "Nothing is known about what I remember.": "제가 무엇을 기억하는지 알 수 없습니다.",
  "I only keep what you answered, what you picked and what you tapped after a walk. Nothing from web pages and nothing I made up.":
    "답하신 것, 고르신 것, 걷고 난 뒤 누르신 것만 기억합니다. 웹 페이지에서 온 것도, 제가 지어낸 것도 없습니다.",
  "Where it comes from": "어디서 알게 되었는지",
  "Nothing yet.": "아직 없습니다.",
  "kept": "기억함",
  "About this": "설명",
  "Not kept": "기억하지 않음",
  "This is no longer in my memory.": "이제 제 기억에 없습니다.",
  "Still learning · not in use today": "배우는 중 · 오늘은 적용 안 됨",
  "Still learning": "배우는 중",
  "Learned · kept": "배워서 기억함",
  "Kept": "기억함",
  "State unknown": "상태 알 수 없음",
  "About: {name}": "설명: {name}",
  "What I know": "제가 아는 것",
  "What it changes": "무엇이 달라지는지",
  "Where this comes from was not saved.": "어디서 알게 되었는지는 저장되어 있지 않습니다.",
  "Saved at {time}. The day is not saved with it.": "{time}에 저장했습니다. 날짜는 함께 저장되어 있지 않습니다.",
  "What this changes was not saved.": "무엇이 달라지는지는 저장되어 있지 않습니다.",
  "Your wish, in your words: “{wish}”": "직접 쓰신 바람: “{wish}”",
  "You have no wish.": "바람을 남기지 않으셨습니다.",
  "{name} at a time.": "한 번에 {name}.",
  "You picked {name}.": "고르신 곳: {name}.",
  "No “too far” tap is saved with it.": "‘너무 멀어요’ 기록이 함께 저장되어 있지 않습니다.",
  "Your “too far” tap: {taps}.": "‘너무 멀어요’를 누르신 기록: {taps}.",
  "Your “too far” taps: {taps}.": "‘너무 멀어요’를 누르신 기록: {taps}.",
  "{day} at {time}, after a {distance} walk": "{day} {time}, {distance}를 걸은 뒤",
  "day unknown": "날짜 알 수 없음",
  "No walk of a route is marked as changed by it.": "이 한도 때문에 판단이 달라진 구간은 없습니다.",
  "walk {id}": "구간 {id}",
  "{from} to {to} ({distance})": "{from}에서 {to}까지 ({distance})",
  "a stop": "한 곳",
  "the next stop": "다음 장소",
  "It changed how this walk was judged on the last route made with it: {walks}.": "이 한도로 만든 마지막 경로에서 이 구간의 판단이 달라졌습니다: {walks}.",
  "It changed how these walks were judged on the last route made with it: {walks}.": "이 한도로 만든 마지막 경로에서 이 구간들의 판단이 달라졌습니다: {walks}.",
  "I will ask you this question again before the next plan.": "다음 계획 전에 이 질문을 다시 여쭤보겠습니다.",
  "The limit and the “too far” taps it came from are deleted. Your answer about walking counts again.":
    "이 한도와 그 바탕이 된 ‘너무 멀어요’ 기록을 지웁니다. 걷기에 대한 답변이 다시 적용됩니다.",
  "Only this note is deleted. A route that is already made stays as it is.": "이 기록만 지웁니다. 이미 만든 경로는 그대로입니다.",
  "This one thing is deleted.": "이것 하나만 지웁니다.",
  "Forget this": "이것을 잊어 주세요",
  "Forgetting it": "잊는 중입니다",
  "Forget “{name}”? {what}": "“{name}” 을(를) 잊을까요? {what}",
  "Keep it": "그대로 두기",
  "Yes, forget": "네, 잊어 주세요",
  "What the map shows": "지도 보는 법",
  "Thin line: something you answered or picked": "가는 선: 답하거나 고르신 것",
  "Solid blue line: learned from your taps and kept": "파란 실선: 누르신 버튼에서 배워 기억하는 것",
  "Dashed blue line: still learning": "파란 점선: 배우는 중",
  "No agent is named, so nothing is known about what I remember.": "에이전트가 지정되지 않아 제가 무엇을 기억하는지 알 수 없습니다.",
  "I am still reading what I remember.": "제가 기억하는 것을 읽는 중입니다.",
  "This development sample holds no memory.": "이 개발용 샘플에는 기억이 없습니다.",
  "The saved run holds no memory, so there is nothing to show here. Memory is kept by the live agent.":
    "저장된 실행에는 기억이 없어 보여 드릴 것이 없습니다. 기억은 실시간 에이전트가 보관합니다.",
  "There is no run, so nothing is known about what I remember.": "실행 기록이 없어 제가 무엇을 기억하는지 알 수 없습니다.",
  "What I remember could not be read. {why}": "제가 기억하는 것을 읽지 못했습니다. {why}",
  "The agent could not be reached, so nothing can be forgotten right now.": "에이전트에 연결할 수 없어 지금은 잊게 하실 수 없습니다.",
  "Forgetting needs the live agent. This is a development sample, so the button is switched off.":
    "잊으려면 실시간 에이전트가 필요합니다. 지금은 개발용 샘플이라 버튼이 꺼져 있습니다.",
  "Forgetting needs the live agent. This is a saved run, so the button is switched off.":
    "잊으려면 실시간 에이전트가 필요합니다. 지금은 저장된 실행이라 버튼이 꺼져 있습니다.",
};
