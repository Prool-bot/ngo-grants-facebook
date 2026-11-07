// NGO Grants AI v5.7 — optional Cloudflare Worker menu clarification adapter.
//
// This is NOT a replacement for the existing deployed Worker. Import its
// functions into that Worker's current 1–4 step flow before "Confirm order".
// It makes ZERO AI calls; reserve AI tokens for catalog classification.
// The daily one-request quota must be consumed only after final confirmation.
//
// No tokens, chat IDs, phone numbers or email addresses are handled here.
const SECTORS = new Set([
  "education", "medical", "culture", "environment", "it", "social",
  "recovery", "agriculture", "media", "rights", "business", "all"
]);
const AUDIENCES = new Set([
  "nonprofit", "commercial", "individual", "all", "municipal", "institution"
]);
const GEO = new Set(["ukraine", "region", "international", "all"]);

export function normalizeDraft(raw = {}) {
  const f = {
    audience: raw.audience,
    sectors: Array.isArray(raw.sectors) ? [...new Set(raw.sectors)] : [],
    geo: raw.geo,
    region: raw.geo === "region" ? String(raw.region || "") : "",
    detail: String(raw.detail || "").trim().slice(0, 180),
    custom_sector: String(raw.custom_sector || "").trim().slice(0, 60),
  };
  if (!AUDIENCES.has(f.audience) || !GEO.has(f.geo) ||
      !f.sectors.length || f.sectors.some(s => !SECTORS.has(s))) {
    throw new Error("Incomplete catalogue menu selection");
  }
  if (f.sectors.includes("all")) {
    f.sectors = ["all"];
    f.custom_sector = "";
  }
  if (f.geo === "region" && !f.region) {
    throw new Error("Regional search requires a region");
  }
  if (raw.applicant_role !== undefined) {
    if (!["lead", "partner", "either"].includes(raw.applicant_role))
      throw new Error("Invalid applicant role");
    f.applicant_role = raw.applicant_role;
  }
  if (raw.funding_format !== undefined) {
    if (!["any", "grant_only"].includes(raw.funding_format))
      throw new Error("Invalid funding format");
    f.funding_format = raw.funding_format;
  }
  return f;
}

export function clarificationSteps(facets) {
  const f = normalizeDraft(facets);
  const d = f.detail.toLowerCase();
  const questions = [];

  if (f.audience === "nonprofit" &&
      /територіальн.{0,12}громад|для громад|муніципал/.test(d)) {
    questions.push({
      key: "audience",
      title: "Хто подаватиме заявку?",
      buttons: [
        ["ГО, яка працює для громади", "nonprofit"],
        ["Місцева рада / громада", "municipal"]
      ]
    });
  }

  if (f.audience === "individual" &&
      f.sectors.some(s => ["agriculture", "business"].includes(s))) {
    questions.push({
      key: "audience",
      title: "Ви маєте зареєстрований ФОП?",
      buttons: [
        ["Ні, фізична особа", "individual"],
        ["Так, ФОП (комерційний заявник)", "commercial"]
      ]
    });
  }

  if (/(жіноч|жін|women)/.test(d) &&
      /(бізнес|підприєм|стартап|business|entrepreneur)/.test(d)) {
    questions.push({
      key: "detail",
      title: "Потрібні саме гранти для жінок чи будь-які бізнес-гранти?",
      buttons: [
        ["Спеціально для жіночого бізнесу", f.detail],
        ["Усі бізнес-гранти", "Підприємництво та бізнес"]
      ]
    });
  }

  if (f.sectors.length >= 3 && !f.detail) {
    questions.push({
      key: "detail",
      title: "Опишіть конкретну діяльність/проєкт одним реченням",
      buttons: []
    });
  }

  return questions.slice(0, 2);
}

export const MENU_STEPS_V57 = Object.freeze([
  "1. Хто заявник? ГО/БФ, бізнес/ФОП, фізособа, муніципалітет, заклад освіти.",
  "2. Напрями: вибір одного або кількох; альтернативні напрями шукаються незалежно.",
  "3. Географія: Україна, область, міжнародні конкурси або без обмежень.",
  "4. Уточнення: що саме фінансується, для кого та в якій ролі.",
  "5. Запитання про неоднозначності (за потреби); далі підсумок та підтвердження.",
]);

export function confirmationText(facets) {
  const f = normalizeDraft(facets);
  const lines = [
    "🔎 ПЕРЕВІРТЕ ЗАПИТ ПЕРЕД ПІДТВЕРДЖЕННЯМ",
    "Заявник: " + f.audience,
    "Напрями (кожен окремо): " + f.sectors.join(", "),
    "Географія: " + f.geo + (f.region ? " / " + f.region : ""),
    "Проєкт: " + (f.detail || "не уточнено"),
    "Роль: " + (f.applicant_role || "основний заявник"),
    "Тип підтримки: " + (f.funding_format || "усі види"),
    "",
    "Після підтвердження буде використано один запит на добу."
  ];
  return lines.join("\n");
}
