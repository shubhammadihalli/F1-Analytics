/* ============================================================================
 * f1-api.js — DATA ACCESS LAYER (real backend)
 * ----------------------------------------------------------------------------
 * Backed by the F1 Analytics FastAPI service at /api/v1 (same origin as this
 * static page). Every exported function/shape matches the original mock
 * contract exactly so the dashboard's template + chart code didn't need to
 * change - only this module's internals did.
 *
 * Two deliberate adaptations from the original mock, both driven by what the
 * real schema can honestly support:
 *  - Driver "id" is the driver_number as a string (e.g. "1"), not a 3-letter
 *    code - it's what every backend endpoint keys on. `code`/`name_acronym`
 *    is still surfaced as a separate field.
 *  - The 6-axis radar uses Wins / Podiums / Poles / Points / Avg Finish /
 *    Avg Qualifying instead of the mock's invented Pace/Racecraft/Tyre
 *    Mgmt/Wet axes - those aren't derivable from this data without making
 *    numbers up.
 * ==========================================================================*/

const BASE = (typeof window !== "undefined" && window.F1_API_BASE) || "/api/v1";
const SEASON = 2026;
const DEFAULT_COLOUR = "#8a8a8f";
const COMPOUND_COLOURS = {
  SOFT: "#E10600", MEDIUM: "#F2C200", HARD: "#E8E8E8",
  INTERMEDIATE: "#3DA336", WET: "#1E88E5", TEST_UNKNOWN: "#6B6B6F",
};

async function getJSON(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
  return r.json();
}

async function getAllPages(path, params = {}) {
  const items = [];
  let page = 1;
  for (;;) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null) qs.set(k, v); });
    qs.set("page", page);
    qs.set("page_size", 500);
    const data = await getJSON(`${path}?${qs}`);
    items.push(...data.items);
    if (page >= data.pages || data.items.length === 0) break;
    page++;
  }
  return items;
}

function normColour(hex) {
  if (!hex) return DEFAULT_COLOUR;
  return hex.startsWith("#") ? hex : `#${hex}`;
}

function fmtLapTime(seconds) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = (seconds - m * 60).toFixed(3);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

/* ============================ STATIC REFERENCE ============================
 * Top-level await: the dynamic `import('./f1-api.js')` in the dashboard
 * component doesn't resolve until this finishes, so by the time the caller
 * touches `api.DRIVERS` / `api.TEAMS` they're already plain arrays, not
 * promises - same synchronous-looking contract the mock had.
 * ========================================================================= */

const [_driversRaw, _constructorsRaw] = await Promise.all([
  getAllPages("/drivers"),
  getAllPages("/constructors"),
]);

const _driversByNum = Object.fromEntries(_driversRaw.map((d) => [d.driver_number, d]));
const _teamColour = Object.fromEntries(_constructorsRaw.map((c) => [c.team_name, normColour(c.team_colour)]));

function teamColourFor(teamName) { return _teamColour[teamName] || DEFAULT_COLOUR; }

export const TEAMS = _constructorsRaw.map((c) => ({
  id: c.team_name, name: c.team_name, short: c.team_name, color: teamColourFor(c.team_name), engine: "",
}));

export const DRIVERS = _driversRaw
  .map((d) => ({
    id: String(d.driver_number), code: d.name_acronym || String(d.driver_number),
    first: d.first_name || "", last: d.last_name || "", team: d.team_name, num: d.driver_number,
  }))
  .sort((a, b) => a.last.localeCompare(b.last));

export function driverName(id) {
  const d = _driversByNum[Number(id)];
  return d ? d.full_name : id;
}
export function teamColor(id) {
  const d = _driversByNum[Number(id)];
  return d ? teamColourFor(d.team_name) : DEFAULT_COLOUR;
}

export const META = { SEASON };

/* ============================ SEASON CACHE =================================
 * Everything below this point needs the season's calendar/results, fetched
 * once and memoized. _advanceLive() (the "Live refresh" feature) invalidates
 * it so the next accessor call re-fetches real fresh data from the backend -
 * no fake number jitter, an actual re-poll.
 * ========================================================================= */

let _seasonPromise = null;
const _gridCache = {};
const _fastestLapCache = {};
const _lapsCache = {};
const _positionsCache = {};

async function ensureStartingGrid(sessionKey) {
  if (!_gridCache[sessionKey]) _gridCache[sessionKey] = await getAllPages("/starting-grid", { session_key: sessionKey });
  return _gridCache[sessionKey];
}
async function ensureFastestLapFor(sessionKey, driverNumber) {
  const key = `${sessionKey}|${driverNumber}`;
  if (!(key in _fastestLapCache)) {
    const data = await getJSON(`/laps?session_key=${sessionKey}&driver_number=${driverNumber}&sort=lap_duration&page_size=1`);
    _fastestLapCache[key] = data.items[0] || null;
  }
  return _fastestLapCache[key];
}
async function ensureLaps(sessionKey) {
  if (!_lapsCache[sessionKey]) _lapsCache[sessionKey] = await getAllPages("/laps", { session_key: sessionKey });
  return _lapsCache[sessionKey];
}
async function ensurePositions(sessionKey) {
  if (!_positionsCache[sessionKey]) _positionsCache[sessionKey] = await getAllPages("/positions", { session_key: sessionKey });
  return _positionsCache[sessionKey];
}

function ensureSeason() {
  if (_seasonPromise) return _seasonPromise;
  _seasonPromise = (async () => {
    const [raceTypeSessions, qualiTypeSessions, driverStandings, constructorStandings] = await Promise.all([
      getAllPages("/races", { year: SEASON, session_type: "Race" }),
      getAllPages("/races", { year: SEASON, session_type: "Qualifying" }),
      getJSON(`/standings?year=${SEASON}&type=driver`),
      getJSON(`/standings?year=${SEASON}&type=constructor`),
    ]);

    const mainRaces = raceTypeSessions
      .filter((r) => r.session_name === "Race" && !r.is_cancelled)
      .sort((a, b) => new Date(a.date_start) - new Date(b.date_start));
    const sprints = raceTypeSessions.filter((r) => r.session_name === "Sprint" && !r.is_cancelled);
    const qualis = qualiTypeSessions.filter((r) => r.session_name === "Qualifying" && !r.is_cancelled);

    const rounds = mainRaces.map((race, i) => ({
      round: i + 1, race,
      sprint: sprints.find((sp) => sp.meeting_key === race.meeting_key) || null,
      quali: qualis.find((q) => q.meeting_key === race.meeting_key) || null,
    }));
    const byRound = Object.fromEntries(rounds.map((r) => [r.round, r]));
    const sessionKeyToRound = {};
    rounds.forEach((r) => {
      sessionKeyToRound[r.race.session_key] = r.round;
      if (r.sprint) sessionKeyToRound[r.sprint.session_key] = r.round;
    });

    const [raceResults, qualiResults] = await Promise.all([
      getAllPages("/results", { year: SEASON, session_type: "Race" }),
      getAllPages("/results", { year: SEASON, session_type: "Qualifying" }),
    ]);

    const podiumsBy = {}, polesBy = {};
    raceResults.forEach((r) => { if (r.position != null && r.position <= 3) podiumsBy[r.driver_number] = (podiumsBy[r.driver_number] || 0) + 1; });
    qualiResults.forEach((r) => { if (r.position === 1) polesBy[r.driver_number] = (polesBy[r.driver_number] || 0) + 1; });

    const standingsRows = driverStandings.map((st) => ({
      pos: st.position, id: String(st.driver_number), points: st.points, wins: st.wins,
      podiums: podiumsBy[st.driver_number] || 0, poles: polesBy[st.driver_number] || 0, team: st.team_name,
    }));

    return { rounds, byRound, sessionKeyToRound, raceResults, qualiResults, driverStandings, constructorStandings, standingsRows };
  })();
  return _seasonPromise;
}

export function _advanceLive() {
  _seasonPromise = null;
  Object.keys(_gridCache).forEach((k) => delete _gridCache[k]);
  Object.keys(_fastestLapCache).forEach((k) => delete _fastestLapCache[k]);
  Object.keys(_lapsCache).forEach((k) => delete _lapsCache[k]);
  Object.keys(_positionsCache).forEach((k) => delete _positionsCache[k]);
}

function radarFor(standingRow, season) {
  const maxOf = (key) => Math.max(1, ...season.standingsRows.map((r) => r[key] || 0));
  const num = Number(standingRow.id);
  const avgOf = (rows) => {
    const v = rows.filter((r) => r.driver_number === num && r.position != null).map((r) => r.position);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  };
  const posScore = (avg) => (avg == null ? 0 : Math.max(0, (20 - avg) / 19 * 100));
  return {
    indicators: [
      { name: "Wins", max: 100 }, { name: "Podiums", max: 100 }, { name: "Poles", max: 100 },
      { name: "Points", max: 100 }, { name: "Avg Finish", max: 100 }, { name: "Avg Qualifying", max: 100 },
    ],
    values: [
      Math.round((standingRow.wins || 0) / maxOf("wins") * 100),
      Math.round((standingRow.podiums || 0) / maxOf("podiums") * 100),
      Math.round((standingRow.poles || 0) / maxOf("poles") * 100),
      Math.round((standingRow.points || 0) / maxOf("points") * 100),
      Math.round(posScore(avgOf(season.raceResults))),
      Math.round(posScore(avgOf(season.qualiResults))),
    ],
  };
}

/* ============================ ACCESSORS (API) ============================ */

export async function getSeasonMeta() {
  const s = await ensureSeason();
  const now = new Date();
  const completed = s.rounds.filter((r) => new Date(r.race.date_start) <= now).length;
  return {
    season: SEASON, totalRounds: s.rounds.length,
    currentRound: Math.min(completed + 1, s.rounds.length || 1),
    completed, remaining: s.rounds.length - completed,
  };
}

export async function getKPIs() {
  const s = await ensureSeason();
  const meta = await getSeasonMeta();
  const leader = s.standingsRows[0] || { id: null, points: 0 };
  const constructorLeader = s.constructorStandings[0] || { team_name: null, points: 0 };
  const fastestLapData = await getJSON(`/laps?year=${SEASON}&session_type=Race&sort=lap_duration&page_size=1`);
  const fastestLapRow = fastestLapData.items[0] || null;
  const fastestLapRound = fastestLapRow ? s.sessionKeyToRound[fastestLapRow.session_key] : null;
  const fastestLapGp = fastestLapRound ? (s.byRound[fastestLapRound].race.circuit_short_name || "") : "";
  const byWins = [...s.standingsRows].sort((a, b) => b.wins - a.wins);
  const byPoles = [...s.standingsRows].sort((a, b) => b.poles - a.poles);
  const byPodiums = [...s.standingsRows].sort((a, b) => b.podiums - a.podiums);
  return {
    championLeader: { id: leader.id, points: leader.points },
    constructorLeader: { team: constructorLeader.team_name, points: constructorLeader.points },
    totalRaces: meta.totalRounds, completedRaces: meta.completed, remainingRaces: meta.remaining,
    fastestLap: {
      id: fastestLapRow ? String(fastestLapRow.driver_number) : null,
      time: fastestLapRow ? fmtLapTime(fastestLapRow.lap_duration) : "—",
      gp: fastestLapGp,
    },
    mostWins: { id: byWins[0]?.id, value: byWins[0]?.wins || 0 },
    mostPoles: { id: byPoles[0]?.id, value: byPoles[0]?.poles || 0 },
    mostPodiums: { id: byPodiums[0]?.id, value: byPodiums[0]?.podiums || 0 },
  };
}

export async function getDriverStandings() {
  const s = await ensureSeason();
  return s.standingsRows;
}

export async function getConstructorStandings() {
  const s = await ensureSeason();
  return s.constructorStandings.map((c, i) => ({
    pos: c.position ?? i + 1, team: c.team_name, name: c.team_name, color: teamColourFor(c.team_name), points: c.points,
  }));
}

export async function getPointsProgression(topN = 6) {
  const s = await ensureSeason();
  const now = new Date();
  const completedRounds = s.rounds.filter((r) => new Date(r.race.date_start) <= now);
  const pointsByDriverRound = {};
  s.raceResults.forEach((r) => {
    const round = s.sessionKeyToRound[r.session_key];
    if (!round) return;
    const byRound = (pointsByDriverRound[r.driver_number] = pointsByDriverRound[r.driver_number] || {});
    byRound[round] = (byRound[round] || 0) + (r.points || 0);
  });
  const rounds = completedRounds.map((r) => r.round);
  const top = s.standingsRows.slice(0, topN);
  const series = top.map((d) => {
    let acc = 0;
    const data = rounds.map((rd) => { acc += (pointsByDriverRound[Number(d.id)] || {})[rd] || 0; return acc; });
    return { id: d.id, name: driverName(d.id), color: teamColor(d.id), data };
  });
  return { rounds, series };
}

export async function getCalendar() {
  const s = await ensureSeason();
  const now = new Date();
  return s.rounds.map((r) => {
    const race = r.race;
    const done = new Date(race.date_start) <= now;
    const winnerRow = done ? s.raceResults.find((x) => x.session_key === race.session_key && x.position === 1) : null;
    const name = race.circuit_short_name || `Round ${r.round}`;
    return {
      round: r.round, name, country: name, circuit: name, date: race.date_start,
      status: done ? "completed" : "upcoming",
      winner: winnerRow ? String(winnerRow.driver_number) : null,
    };
  });
}

export async function getWinDistribution() {
  const s = await ensureSeason();
  return s.standingsRows
    .filter((r) => r.wins > 0)
    .sort((a, b) => b.wins - a.wins)
    .map((r) => ({ id: r.id, name: driverName(r.id), color: teamColor(r.id), wins: r.wins }));
}

/* ---- DRIVER PAGE -------------------------------------------------------- */

export async function getDriver(id) {
  const s = await ensureSeason();
  const num = Number(id);
  const driver = _driversByNum[num] || {};
  const now = new Date();
  const completedRounds = s.rounds.filter((r) => new Date(r.race.date_start) <= now);
  const rounds = completedRounds.map((r) => r.round);
  const labels = completedRounds.map((r) => r.race.circuit_short_name || `R${r.round}`);

  const finishes = completedRounds.map((r) => {
    const res = s.raceResults.find((x) => x.session_key === r.race.session_key && x.driver_number === num);
    return res ? res.position : null;
  });

  const grids = await Promise.all(completedRounds.map(async (r) => {
    const grid = await ensureStartingGrid(r.race.session_key);
    const row = grid.find((g) => g.driver_number === num);
    return row ? row.grid_position : null;
  }));

  const qualis = completedRounds.map((r) => {
    if (!r.quali) return null;
    const res = s.qualiResults.find((x) => x.session_key === r.quali.session_key && x.driver_number === num);
    return res ? res.position : null;
  });

  const pace = await Promise.all(completedRounds.map(async (r) => {
    const lap = await ensureFastestLapFor(r.race.session_key, num);
    return lap && lap.lap_duration != null ? +lap.lap_duration.toFixed(3) : null;
  }));

  let acc = 0;
  const progression = rounds.map((rd) => {
    const pts = s.raceResults
      .filter((x) => x.driver_number === num && s.sessionKeyToRound[x.session_key] === rd)
      .reduce((sum, r) => sum + (r.points || 0), 0);
    acc += pts;
    return acc;
  });

  const standingRow = s.standingsRows.find((r) => r.id === id) || { id, points: 0, wins: 0, podiums: 0, poles: 0, pos: null };

  return {
    id, name: driverName(id), code: driver.name_acronym || id, num,
    team: driver.team_name, teamName: driver.team_name, color: teamColor(id),
    points: standingRow.points, wins: standingRow.wins, podiums: standingRow.podiums, poles: standingRow.poles,
    standing: standingRow.pos,
    rounds, labels, finishes, grids, qualis, pace, progression,
    radar: radarFor(standingRow, s),
  };
}

/* ---- RACE PAGE ---------------------------------------------------------- */

export async function getRace(round) {
  const s = await ensureSeason();
  const r = s.byRound[round];
  if (!r) return null;
  const sessionKey = r.race.session_key;

  const [results, laps, positions, stints, pitStopsRaw, weatherRaw, grid] = await Promise.all([
    getAllPages("/results", { session_key: sessionKey }),
    ensureLaps(sessionKey),
    ensurePositions(sessionKey),
    getAllPages("/stints", { session_key: sessionKey }),
    getAllPages("/pit-stops", { session_key: sessionKey }),
    getAllPages("/weather", { session_key: sessionKey }),
    ensureStartingGrid(sessionKey),
  ]);

  const classified = results.filter((x) => x.position != null).sort((a, b) => a.position - b.position);
  const order = classified.slice(0, 10).map((x) => String(x.driver_number));
  const totalLaps = laps.reduce((m, l) => Math.max(m, l.lap_number), 0);

  const lapsByDriver = {};
  laps.forEach((l) => { (lapsByDriver[l.driver_number] = lapsByDriver[l.driver_number] || []).push(l); });
  Object.values(lapsByDriver).forEach((arr) => arr.sort((a, b) => a.lap_number - b.lap_number));

  const positionsByDriver = {};
  positions.forEach((p) => { (positionsByDriver[p.driver_number] = positionsByDriver[p.driver_number] || []).push(p); });
  Object.values(positionsByDriver).forEach((arr) => arr.sort((a, b) => new Date(a.date) - new Date(b.date)));

  function positionAtLapEnd(driverNum, lapNumber) {
    const driverLaps = lapsByDriver[driverNum] || [];
    const lapRow = driverLaps.find((l) => l.lap_number === lapNumber);
    const nextLapRow = driverLaps.find((l) => l.lap_number === lapNumber + 1);
    let boundary = null;
    if (nextLapRow && nextLapRow.date_start) boundary = new Date(nextLapRow.date_start);
    else if (lapRow && lapRow.date_start && lapRow.lap_duration) {
      boundary = new Date(new Date(lapRow.date_start).getTime() + lapRow.lap_duration * 1000);
    }
    if (!boundary) return null;
    const driverPositions = positionsByDriver[driverNum] || [];
    let best = null;
    for (const p of driverPositions) {
      if (new Date(p.date) <= boundary) best = p; else break;
    }
    return best ? best.position : null;
  }

  const lapChart = order.map((idStr) => {
    const num = Number(idStr);
    const data = [];
    for (let l = 1; l <= totalLaps; l++) data.push(positionAtLapEnd(num, l));
    return { id: idStr, name: driverName(idStr), color: teamColor(idStr), data };
  });

  const stintsByDriver = {};
  stints.forEach((st) => (stintsByDriver[st.driver_number] = stintsByDriver[st.driver_number] || []).push(st));
  const tyreStrategy = order.map((idStr) => {
    const num = Number(idStr);
    const driverStints = (stintsByDriver[num] || []).sort((a, b) => a.stint_number - b.stint_number);
    const stintsOut = driverStints.map((st) => ({
      compound: st.compound || "TEST_UNKNOWN",
      laps: Math.max(1, (st.lap_end ?? totalLaps) - st.lap_start + 1),
    }));
    return { id: idStr, name: driverName(idStr), color: teamColor(idStr), stints: stintsOut };
  });
  const compounds = Object.fromEntries(
    Object.entries(COMPOUND_COLOURS).map(([k, v]) => [k, [k.charAt(0) + k.slice(1).toLowerCase(), v]])
  );

  const pitByDriver = {};
  pitStopsRaw.forEach((p) => (pitByDriver[p.driver_number] = pitByDriver[p.driver_number] || []).push(p));
  const pitStops = order.map((idStr) => {
    const num = Number(idStr);
    const mine = pitByDriver[num] || [];
    const durations = mine.map((p) => p.pit_duration).filter((d) => d != null);
    return {
      id: idStr, name: driverName(idStr), color: teamColor(idStr),
      stops: mine.length, best: durations.length ? +Math.min(...durations).toFixed(2) : 0,
    };
  });

  const referenceDriverNum = classified[0] ? classified[0].driver_number : (laps[0] && laps[0].driver_number);
  const refLaps = (lapsByDriver[referenceDriverNum] || []).slice().sort((a, b) => a.lap_number - b.lap_number);
  function lapForTimestamp(ts) {
    let lapNum = 1;
    for (const l of refLaps) {
      if (l.date_start && new Date(l.date_start) <= ts) lapNum = l.lap_number; else break;
    }
    return lapNum;
  }
  const weatherSorted = weatherRaw.slice().sort((a, b) => new Date(a.date) - new Date(b.date));
  const weather = {
    laps: weatherSorted.map((w) => lapForTimestamp(new Date(w.date))),
    airTemp: weatherSorted.map((w) => w.air_temperature),
    trackTemp: weatherSorted.map((w) => w.track_temperature),
    humidity: weatherSorted.map((w) => w.humidity),
  };

  const durationsByDriver = {};
  laps.forEach((l) => {
    if (l.lap_duration != null) (durationsByDriver[l.driver_number] = durationsByDriver[l.driver_number] || []).push(l.lap_duration);
  });
  const fastestLaps = Object.entries(durationsByDriver)
    .map(([num, durations]) => ({ id: String(num), name: driverName(String(num)), color: teamColor(String(num)), time: Math.min(...durations) }))
    .sort((a, b) => a.time - b.time);

  const sectors = order.slice(0, 6).map((idStr) => {
    const num = Number(idStr);
    const mine = (lapsByDriver[num] || []).filter((l) => l.duration_sector_1 != null && l.duration_sector_2 != null && l.duration_sector_3 != null);
    return {
      id: idStr, name: driverName(idStr), color: teamColor(idStr),
      s1: mine.length ? Math.min(...mine.map((l) => l.duration_sector_1)) : null,
      s2: mine.length ? Math.min(...mine.map((l) => l.duration_sector_2)) : null,
      s3: mine.length ? Math.min(...mine.map((l) => l.duration_sector_3)) : null,
    };
  });

  const positionChanges = order.map((idStr) => {
    const num = Number(idStr);
    const gridRow = grid.find((g) => g.driver_number === num);
    const resRow = results.find((x) => x.driver_number === num);
    return {
      id: idStr, name: driverName(idStr), color: teamColor(idStr),
      start: gridRow ? gridRow.grid_position : null, finish: resRow ? resRow.position : null,
    };
  });

  const winnerRow = classified[0];
  const name = r.race.circuit_short_name || `Round ${round}`;
  return {
    round, name, country: name, circuit: name, date: r.race.date_start,
    status: new Date(r.race.date_start) <= new Date() ? "completed" : "upcoming",
    winner: winnerRow ? String(winnerRow.driver_number) : null,
    laps: totalLaps,
    lapChart, tyreStrategy, compounds, pitStops, weather, fastestLaps, sectors, positionChanges,
  };
}

/* ---- TELEMETRY ---------------------------------------------------------- */

export async function getTelemetry(driverId, round) {
  const s = await ensureSeason();
  const r = s.byRound[round];
  const num = Number(driverId);
  const empty = {
    driver: driverId, name: driverName(driverId), color: teamColor(driverId), round,
    gp: r ? r.race.circuit_short_name : "", distance: [], speed: [], throttle: [], brake: [],
    gear: [], rpm: [], drs: [], accel: [], trackLength: 0, bestLap: "—",
  };
  if (!r) return empty;

  const sessionKey = r.race.session_key;
  const fastestLap = await ensureFastestLapFor(sessionKey, num);
  if (!fastestLap || !fastestLap.date_start || fastestLap.lap_duration == null) return empty;

  const samples = await getAllPages("/telemetry", { session_key: sessionKey, driver_number: num, sort: "date" });
  const lapStart = new Date(fastestLap.date_start);
  const lapEnd = new Date(lapStart.getTime() + fastestLap.lap_duration * 1000);
  const windowed = samples
    .filter((t) => { const d = new Date(t.date); return d >= lapStart && d <= lapEnd; })
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  const distance = [], accel = [];
  let cum = 0, prevSpeed = null, prevT = null;
  windowed.forEach((t) => {
    const ts = new Date(t.date).getTime();
    const dtSec = prevT == null ? 0 : (ts - prevT) / 1000;
    const speedMps = (t.speed || 0) * (1000 / 3600);
    cum += speedMps * dtSec;
    distance.push(Math.round(cum));
    if (prevT == null || dtSec === 0) accel.push(0);
    else {
      const prevSpeedMps = (prevSpeed || 0) * (1000 / 3600);
      accel.push(+(((speedMps - prevSpeedMps) / dtSec) / 9.81).toFixed(2));
    }
    prevSpeed = t.speed; prevT = ts;
  });

  return {
    driver: driverId, name: driverName(driverId), color: teamColor(driverId), round, gp: r.race.circuit_short_name,
    distance, speed: windowed.map((t) => t.speed), throttle: windowed.map((t) => t.throttle),
    brake: windowed.map((t) => t.brake), gear: windowed.map((t) => t.n_gear), rpm: windowed.map((t) => t.rpm),
    drs: windowed.map((t) => t.drs), accel,
    trackLength: distance.length ? distance[distance.length - 1] : 0,
    bestLap: fmtLapTime(fastestLap.lap_duration),
  };
}

/* ---- HEAD TO HEAD --------------------------------------------------------- */

export async function getHeadToHead(aId, bId) {
  const s = await ensureSeason();
  const numA = Number(aId), numB = Number(bId);
  const data = await getJSON(`/head-to-head?driver1=${numA}&driver2=${numB}&year=${SEASON}`);

  const raceSessions = data.sessions.filter((x) => x.session_type === "Race");
  const qualiSessions = data.sessions.filter((x) => x.session_type === "Qualifying");

  const winsA = raceSessions.filter((x) => x.driver1_position === 1).length;
  const winsB = raceSessions.filter((x) => x.driver2_position === 1).length;
  const podiumsA = raceSessions.filter((x) => x.driver1_position != null && x.driver1_position <= 3).length;
  const podiumsB = raceSessions.filter((x) => x.driver2_position != null && x.driver2_position <= 3).length;
  const polesA = qualiSessions.filter((x) => x.driver1_position === 1).length;
  const polesB = qualiSessions.filter((x) => x.driver2_position === 1).length;
  const avg = (rows, key) => {
    const v = rows.map((x) => x[key]).filter((x) => x != null);
    return v.length ? +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(1) : 0;
  };
  const avgFinishA = avg(raceSessions, "driver1_position"), avgFinishB = avg(raceSessions, "driver2_position");
  const avgQualiA = avg(qualiSessions, "driver1_position"), avgQualiB = avg(qualiSessions, "driver2_position");

  let fastestA = 0, fastestB = 0;
  await Promise.all(raceSessions.map(async (sess) => {
    const [lapA, lapB] = await Promise.all([
      ensureFastestLapFor(sess.session_key, numA), ensureFastestLapFor(sess.session_key, numB),
    ]);
    if (lapA && lapB) { if (lapA.lap_duration < lapB.lap_duration) fastestA++; else if (lapB.lap_duration < lapA.lap_duration) fastestB++; }
  }));

  const scatterA = [], scatterB = [];
  raceSessions.forEach((rs) => {
    const round = s.sessionKeyToRound[rs.session_key];
    const roundInfo = s.byRound[round];
    if (!roundInfo || !roundInfo.quali) return;
    const qs = qualiSessions.find((x) => x.session_key === roundInfo.quali.session_key);
    if (!qs) return;
    if (qs.driver1_position != null) scatterA.push([qs.driver1_position, rs.driver1_position ?? 20]);
    if (qs.driver2_position != null) scatterB.push([qs.driver2_position, rs.driver2_position ?? 20]);
  });

  const maxOf = (x, y) => Math.max(x, y, 1);
  const posScore = (a) => (a <= 0 ? 0 : Math.max(0, (20 - a) / 19 * 100));
  const radarIndicators = [
    { name: "Wins", max: 100 }, { name: "Podiums", max: 100 }, { name: "Poles", max: 100 },
    { name: "Points", max: 100 }, { name: "Avg Finish", max: 100 }, { name: "Avg Qualifying", max: 100 },
  ];
  const radarA = [
    winsA / maxOf(winsA, winsB) * 100, podiumsA / maxOf(podiumsA, podiumsB) * 100, polesA / maxOf(polesA, polesB) * 100,
    data.driver1_points_total / maxOf(data.driver1_points_total, data.driver2_points_total) * 100,
    posScore(avgFinishA), posScore(avgQualiA),
  ].map(Math.round);
  const radarB = [
    winsB / maxOf(winsA, winsB) * 100, podiumsB / maxOf(podiumsA, podiumsB) * 100, polesB / maxOf(polesA, polesB) * 100,
    data.driver2_points_total / maxOf(data.driver1_points_total, data.driver2_points_total) * 100,
    posScore(avgFinishB), posScore(avgQualiB),
  ].map(Math.round);

  const a = {
    id: aId, name: driverName(aId), color: teamColor(aId), team: data.driver1.team_name, num: data.driver1.driver_number,
    wins: winsA, podiums: podiumsA, points: data.driver1_points_total, poles: polesA, fastestLaps: fastestA,
    avgFinish: avgFinishA, avgQuali: avgQualiA, radar: radarA, scatter: scatterA,
  };
  const b = {
    id: bId, name: driverName(bId), color: teamColor(bId), team: data.driver2.team_name, num: data.driver2.driver_number,
    wins: winsB, podiums: podiumsB, points: data.driver2_points_total, poles: polesB, fastestLaps: fastestB,
    avgFinish: avgFinishB, avgQuali: avgQualiB, radar: radarB, scatter: scatterB,
  };

  return {
    a, b, radarIndicators,
    metrics: ["wins", "podiums", "points", "poles", "fastestLaps", "avgFinish", "avgQuali"],
    metricLabels: {
      wins: "Wins", podiums: "Podiums", points: "Points", poles: "Poles",
      fastestLaps: "Fastest Laps", avgFinish: "Avg Finish", avgQuali: "Avg Quali",
    },
    lowerBetter: ["avgFinish", "avgQuali"],
  };
}

/* ---- SEARCH ------------------------------------------------------------- */

export async function searchAll(q) {
  const s = await ensureSeason();
  const Q = (q || "").trim().toLowerCase();
  const res = [];
  DRIVERS.forEach((d) => {
    const l = `${d.first} ${d.last}`;
    if (!Q || l.toLowerCase().includes(Q) || d.code.toLowerCase().includes(Q)) {
      res.push({ type: "Driver", id: d.id, label: l, sub: d.team, color: teamColor(d.id) });
    }
  });
  s.rounds.forEach((r) => {
    const name = r.race.circuit_short_name || `Round ${r.round}`;
    if (!Q || name.toLowerCase().includes(Q)) res.push({ type: "Race", id: r.round, label: `${name} GP`, sub: name, color: "#e10600" });
  });
  TEAMS.forEach((t) => { if (!Q || t.name.toLowerCase().includes(Q)) res.push({ type: "Constructor", id: t.id, label: t.name, sub: "", color: t.color }); });
  s.rounds.forEach((r) => {
    const name = r.race.circuit_short_name;
    if (Q && name && name.toLowerCase().includes(Q)) res.push({ type: "Circuit", id: r.round, label: name, sub: `Round ${r.round}`, color: "#888" });
  });
  return res.slice(0, 40);
}
