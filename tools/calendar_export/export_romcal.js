/**
 * One-off export of romcal's Ordinary Form calendars into Precentor.
 *
 * romcal (https://github.com/romcal/romcal) is copyright 2018 Julian
 * Pereira, MIT licence. This script reads its General Roman, England
 * and Wales calendars and writes, into ordo/data/romcal/:
 *
 *   <calendar>.json            the occasions Precentor loads
 *                              (manage.py load_calendar)
 *   reference/<calendar>.json  romcal's resolved calendar for 2020 to
 *                              2040, which ordo's tests compare against
 *
 * Run it from this folder after `npm install`:
 *
 *   node export_romcal.js
 *
 * The general file holds every day in scope; a national file holds only
 * the days that country (or the region it belongs to, Europe for England
 * and Wales) adds or changes, matched to the general ones by key. Out of scope: ordinary weekdays and optional memorials, except a
 * national row that makes a general memorial optional, which is kept
 * so it can override the general one. See docs/calendar_plan.md.
 */

const fs = require("fs");
const path = require("path");
const { Romcal } = require("romcal");

const CALENDARS = {
  general_roman: require("@romcal/calendar.general-roman").GeneralRoman_EnGb,
  england: require("@romcal/calendar.england").England_EnGb,
  wales: require("@romcal/calendar.wales").Wales_EnGb,
};
const OUT_OF_SCOPE = new Set(["WEEKDAY_13", "OPTIONAL_MEMORIAL_12"]);
const YEARS = { first: 2020, last: 2040 };
const OUT_DIR = path.join(__dirname, "..", "..", "ordo", "data", "romcal");

const COLOURS = {
  PURPLE: "violet", WHITE: "white", GOLD: "white", RED: "red", GREEN: "green", ROSE: "rose", BLACK: "black",
};
const SEASONS = {
  ADVENT: "Advent", CHRISTMAS_TIME: "Christmas", LENT: "Lent", PASCHAL_TRIDUUM: "Easter Triduum",
  EASTER_TIME: "Easter", ORDINARY_TIME: "Ordinary Time",
};

// Corrections to romcal's English names, by key. Each fixes a typo in
// the source; none changes a title.
const NAME_CORRECTIONS = {
  commemoration_of_all_the_faithful_departed: "The Commemoration of All the Faithful Departed (All Souls’ Day)",
};

const snake = (name) => name.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
const precedenceCode = (precedence) => precedence.match(/_(\d+[A-F]?)$/)[1].toLowerCase();
const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1);

// romcal writes "Saturday of the second week of Lent"; the English
// Missal capitalises the week, as romcal already does for the Sundays.
const titleWeeks = (name) =>
  name.replace(/\b([a-z-]+) week of\b/g, (_, ordinal) => `${capitalise(ordinal)} Week of`);

function dateRule(dateDef) {
  if (dateDef.dateFn) {
    return {
      date_rule: snake(dateDef.dateFn),
      date_rule_args: dateDef.dateArgs ?? [],
      date_offset_days: (dateDef.addDay ?? 0) - (dateDef.subtractDay ?? 0),
    };
  }
  return { fixed_month: dateDef.month, fixed_day: dateDef.date };
}

function transfer(exception) {
  let result;
  if (Number.isInteger(exception.ifIsDayOfWeek)) {
    result = { if_day_of_week: exception.ifIsDayOfWeek };
  } else if (exception.ifIsBetween) {
    const { from, to, inclusive } = exception.ifIsBetween;
    result = {
      if_between: { from: { rule: snake(from.dateFn) }, to: { rule: snake(to.dateFn) }, inclusive: Boolean(inclusive) },
    };
  } else {
    throw new Error(`Unexpected transfer: ${JSON.stringify(exception)}`);
  }
  const then = exception.setDate;
  const days = (then.addDay ?? 0) - (then.subtractDay ?? 0);
  result.then = then.dateFn ? { rule: snake(then.dateFn), add_days: days } : { add_days: days };
  return result;
}

async function firstOccurrence(romcal, id) {
  for (let year = YEARS.first; year <= YEARS.last; year++) {
    const day = await romcal.getOneLiturgicalDay(id, { year });
    if (day) return day;
  }
  throw new Error(`${id} never occurs between ${YEARS.first} and ${YEARS.last}`);
}

async function occasion(romcal, def) {
  const day = await firstOccurrence(romcal, def.id);
  const properOfTime = def.fromCalendarId === "ProperOfTime";
  return {
    key: def.id,
    name: NAME_CORRECTIONS[def.id] ?? titleWeeks(capitalise(day.name)),
    rank: def.rank.toLowerCase(),
    precedence: precedenceCode(def.precedence),
    is_proper_of_time: properOfTime,
    shares_with_memorials: Boolean(def.allowSimilarRankItems),
    ...dateRule(def.dateDef),
    transfers: def.dateExceptions.map(transfer),
    colour: COLOURS[day.colors[0]] ?? "",
    // A saint's day falls in different seasons in different years, so
    // only the Proper of Time is given one.
    season: properOfTime ? SEASONS[day.seasons[0]] ?? null : null,
  };
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 1)}\n`);
}

// One line per day, so the reference files stay small and diff cleanly.
function writeReference(file, header, days) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const head = Object.entries(header).map(([k, v]) => ` ${JSON.stringify(k)}: ${JSON.stringify(v)},`);
  const lines = Object.entries(days).map(([date, ids]) => `  ${JSON.stringify(date)}: ${JSON.stringify(ids)}`);
  fs.writeFileSync(file, `{\n${head.join("\n")}\n "days": {\n${lines.join(",\n")}\n }\n}\n`);
}

(async () => {
  const general = await new Romcal({ localizedCalendar: CALENDARS.general_roman }).getAllDefinitions();
  const generalInScope = new Set(Object.values(general).filter((d) => !OUT_OF_SCOPE.has(d.precedence)).map((d) => d.id));

  for (const [calendar, localized] of Object.entries(CALENDARS)) {
    const romcal = new Romcal({ localizedCalendar: localized });
    const defs = Object.values(await romcal.getAllDefinitions());
    const isNational = calendar !== "general_roman";
    const wanted = defs.filter((def) => {
      if (!isNational) return !OUT_OF_SCOPE.has(def.precedence);
      // A national calendar extends a regional one (England and Wales
      // both extend Europe, whose patrons are feasts), so take every row
      // that doesn't come from the general calendar.
      if (["general_roman", "ProperOfTime"].includes(def.fromCalendarId)) return false;
      return !OUT_OF_SCOPE.has(def.precedence) || generalInScope.has(def.id);
    });

    const occasions = [];
    for (const def of wanted.sort((a, b) => a.id.localeCompare(b.id))) occasions.push(await occasion(romcal, def));
    writeJson(path.join(OUT_DIR, `${calendar}.json`), {
      source: "romcal 3.0.0-dev.140 (https://github.com/romcal/romcal), copyright 2018 Julian Pereira, MIT licence",
      calendar,
      occasions,
    });

    const inScope = new Set(defs.filter((d) => !OUT_OF_SCOPE.has(d.precedence)).map((d) => d.id));
    const days = {};
    for (let year = YEARS.first; year <= YEARS.last; year++) {
      const resolved = await romcal.generateCalendar(year);
      for (const [date, items] of Object.entries(resolved)) {
        const ids = items.filter((d) => inScope.has(d.id) && !OUT_OF_SCOPE.has(d.precedence)).map((d) => d.id);
        if (ids.length) days[date] = ids;
      }
    }
    writeReference(path.join(OUT_DIR, "reference", `${calendar}.json`), {
      source: "romcal 3.0.0-dev.140, resolved calendars; ordinary weekdays and optional memorials removed",
      calendar,
      years: [YEARS.first, YEARS.last],
    }, days);
    console.log(`${calendar}: ${occasions.length} occasions, ${Object.keys(days).length} reference days`);
  }
})();
