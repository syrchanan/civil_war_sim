/**
 * Round-based battle engine with per-regiment orders (port of python/imperial_generals/battles/battle.py).
 *
 * Each round every regiment gets one order: a target and a mode (ranged / melee / idle). Ranged fire is one-way
 * along the arrow; melee is mutual and forcing. A melee order on a unit not already in contact is a charge: the
 * charger crosses the last stretch under the target's close-range fire, then a contact test decides whether it
 * goes home, falters, or the defender breaks before contact.
 *
 * All arrows run in one continuous-time Markov chain: the next casualty arrives after Exp(sum of rates), and the
 * arrow that caused it is chosen by a uniform draw weighted by rate. The port follows the Python engine step for
 * step (same draws in the same order, same operation order in every formula), so a seed gives the same battle.
 *
 * Reports, charges and results are plain objects in the state file's shape (snake_case), see state.ts.
 */

import { RuntimeError, ValueError } from './errors';
import { breakScale, MoraleState } from './morale';
import { BattleParams, type Stats, type Unit } from './params';
import { Rng } from './rng';
import { battleFromDict, battleToDict, type StateData } from './state';
import { ArtilleryBattery, CavalryRegiment, type Position, Regiment } from './units';

const MODES = ['idle', 'ranged', 'melee'] as const;
export const ORDER_KEYS = ['target', 'mode', 'ammo', 'on_break'] as const;
/** What a unit does when its target breaks, by mode; the first is the default. */
export const ON_BREAK: Record<string, readonly string[]> = {
  ranged: ['keep', 'strongest', 'weakest'],
  melee: ['fall_back', 'pursue'],
};

// =============================================================================
// Orders
// =============================================================================

/** One regiment's order for a round, as given (missing fields take their defaults). */
export interface OrderInput {
  target?: string | null;
  mode?: string;
  ammo?: string | null;
  on_break?: string | null;
}

/**
 * A validated order. Artillery may name its `ammo`, fixed for the round. `on_break` says what the unit does
 * when its target breaks (or is wiped out) during the round: fire 'keep' (default) / 'strongest' / 'weakest'
 * (men × share of morale budget left); melee 'fall_back' (default) / 'pursue'.
 */
export interface Order {
  readonly target: string | null;
  readonly mode: string;
  readonly ammo: string | null;
  readonly on_break: string | null;
}

/** An order from a plain object or null (idle). */
export function makeOrder(value: OrderInput | null | undefined): Order {
  if (value === null || value === undefined) return { target: null, mode: 'idle', ammo: null, on_break: null };
  if (typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`An order must be an object or null, got ${JSON.stringify(value)}.`);
  }
  const target = value.target ?? null;
  const mode = value.mode ?? 'idle';
  const ammo = value.ammo ?? null;
  let onBreak = value.on_break ?? null;
  if (!(MODES as readonly string[]).includes(mode)) {
    throw new ValueError(`mode must be one of ${[...MODES].sort().join(', ')}, got ${mode}.`);
  }
  if (mode === 'idle' && target !== null) throw new ValueError('An idle order has no target.');
  if (mode !== 'idle' && target === null) throw new ValueError(`A ${mode} order needs a target.`);
  if (ammo !== null && mode !== 'ranged') throw new ValueError('Only a ranged order can choose ammo.');
  if (mode === 'idle') {
    if (onBreak !== null) throw new ValueError('An idle order has no on_break.');
  } else if (onBreak === null) {
    onBreak = ON_BREAK[mode][0];
  } else if (!ON_BREAK[mode].includes(onBreak)) {
    throw new ValueError(`on_break for a ${mode} order must be one of ${ON_BREAK[mode].join(', ')}, got ${onBreak}.`);
  }
  return Object.freeze({ target, mode, ammo, on_break: onBreak });
}

// =============================================================================
// Records (state file shape)
// =============================================================================

/** One arrow of the targeting graph with its current casualty rate (casualties per minute on the target). */
export interface Engagement {
  attacker: string;
  target: string;
  mode: string;
  rate: number;
}

/**
 * A melee order on a unit not already in contact, and how it ended: 'home', 'faltered', 'defender_broke',
 * 'meeting', 'pursuit', 'charger_broke' / 'target_broke'. The odds are those of the contact test, if rolled.
 */
export interface Charge {
  charger: string;
  target: string;
  start: number;
  resolved_at: number;
  outcome: string;
  p_defender_breaks: number | null;
  p_falter: number | null;
  p_home: number | null;
}

/** A firing unit switched target (on_break 'strongest' / 'weakest') when its target broke or was wiped out. */
export interface Retarget {
  unit: string;
  old_target: string;
  new_target: string;
  time: number;
}

export interface CasualtyEvent {
  time: number;
  attacker: string;
  target: string;
}

export interface UnitReport {
  losses: number; // men hit this round (killed or wounded; split in finish)
  inflicted: number;
  size: number;
  morale: number;
  broken: boolean;
  broke_at: number | null; // game minute it broke, if it broke this round
  captured: number; // men taken prisoner as it routed this round
  guns_lost: number; // artillery: guns captured this round
}

export type BySide = Record<string, number>; // '0' / '1' -> count

export interface RoundReport {
  round: number;
  start: number;
  end: number;
  orders: Record<string, { target: string | null; mode: string; ammo: string | null; on_break: string | null }>;
  engagements: Engagement[];
  units: Record<string, UnitReport>;
  events: CasualtyEvent[];
  prisoners: BySide;
  guns_captured: BySide;
  charges: Charge[];
  retargets: Retarget[];
  /** Where placed units stood as the round began (as saved), for replays on the map. */
  positions: Record<string, Position>;
  /** The admin's modifiers for this round. */
  modifiers: Record<string, Modifier>;
}

/** An admin's modifiers for one unit and one round: fractions from -1 to 1 (-0.15 is -15%), and a note. */
export interface Modifier {
  fire: number; // scales the casualties the unit inflicts by fire (closing fire included)
  melee: number; // scales the casualties it inflicts in melee
  morale: number; // scales what it spends from its morale budget (+0.1: spends 10% less)
  note: string;
}

export type ModifierInput = Partial<Modifier>;

export const MODIFIER_KEYS = ['fire', 'melee', 'morale'] as const;

const isMapping = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

/** Check one round's admin modifiers (port of Python's validate_modifiers); returns them complete. */
export function validateModifiers(modifiers: unknown, units: Map<string, unknown>): Record<string, Modifier> {
  if (!isMapping(modifiers)) throw new ValueError('modifiers must be a mapping of unit id to modifiers.');
  const checked: Record<string, Modifier> = {};
  for (const [uid, mod] of Object.entries(modifiers)) {
    if (!units.has(uid)) throw new ValueError(`Unknown unit ${uid} in modifiers.`);
    if (!isMapping(mod)) throw new ValueError(`${uid}: modifiers must be a mapping (fire, melee, morale, note).`);
    const unknown = Object.keys(mod).filter((k) => !['fire', 'melee', 'morale', 'note'].includes(k)).sort();
    if (unknown.length) throw new ValueError(`Unknown modifier(s) [${unknown.join(', ')}] for ${uid}; use fire, melee, morale, note.`);
    const out = { fire: 0, melee: 0, morale: 0, note: '' };
    for (const key of MODIFIER_KEYS) {
      const value = mod[key] ?? 0;
      if (typeof value !== 'number') {
        throw new ValueError(`${uid}: ${key} must be a number (a fraction, -0.15 for -15%), got ${JSON.stringify(value)}.`);
      }
      if (!(value >= -1 && value <= 1)) throw new ValueError(`${uid}: ${key} must be between -1 and 1 (-100% to +100%), got ${value}.`);
      out[key] = value;
    }
    const note = mod.note ?? '';
    if (typeof note !== 'string') throw new ValueError(`${uid}: the note must be text, got ${JSON.stringify(note)}.`);
    out.note = note;
    checked[uid] = out;
  }
  return checked;
}

export interface UnitOutcome {
  hits: number;
  killed: number;
  wounded: number;
  walking_wounded: number;
  wounded_captured: number;
  wounded_returned: number;
  captured_in_rout: number;
  final_size: number;
  guns_lost: number;
}

export type FieldTest = 'exchange' | 'routs' | 'standing';

export interface BattleResult {
  field_held_by: number | null;
  units: Record<string, UnitOutcome>;
  prisoners: BySide;
  guns_captured: BySide;
  field_decided_by: string; // 'army_out', 'votes' or 'admin'
  field_votes: Partial<Record<FieldTest, number | null>>;
}

export type FieldHolder = 0 | 1 | null | 'auto';

// =============================================================================
// Units in the battle
// =============================================================================

export class BattleUnit {
  losses = 0;
  inflicted = 0;
  captured = 0;
  gunsLost = 0;

  constructor(
    readonly uid: string,
    readonly side: number,
    readonly regiment: Regiment,
    public morale: MoraleState,
    readonly initialSize: number,
    readonly index: number,
    readonly key: Unit,
    readonly meleeRating: number,
    readonly name: string,
    readonly meta: Record<string, unknown>,
    readonly initialStats: Stats,
  ) {}

  get size(): number {
    return this.regiment.size;
  }

  get front(): number {
    return Math.min(this.regiment.size, this.regiment.frontSize);
  }

  /** Can act: not broken and not wiped out. */
  get active(): boolean {
    return this.regiment.size > 0 && !this.morale.broken;
  }
}

export interface UnitSpec {
  side: number;
  regiment: Regiment;
  name?: string;
  meta?: Record<string, unknown>;
}

// Python frozenset pairs: one canonical key per pair of unit ids
const SEP = '\u0000';
const pairKey = (a: string, b: string): string => (a < b ? a + SEP + b : b + SEP + a);
const pairOf = (key: string): [string, string] => key.split(SEP) as [string, string];

interface Pending {
  charger: string;
  target: string;
  end: number;
  meeting: boolean;
}

type Slot = [attacker: string, target: string, mode: string, matchup: number, share: number, gunRate: number | null];
type Arrow = [attacker: string, target: string, mode: string, rate: number];

const bySide = (): BySide => ({ 0: 0, 1: 0 });

// =============================================================================
// Battle
// =============================================================================

/** A battle between two sides, fought in rounds. */
export class Battle {
  rng: Rng;
  seed: number | null;
  readonly params: BattleParams;
  readonly meta: Record<string, unknown>;
  readonly units = new Map<string, BattleUnit>();
  time = 0;
  round = 0;
  history: RoundReport[] = [];
  prisoners: BySide = bySide();
  gunsCaptured: BySide = bySide();
  finished = false;
  contacts = new Set<string>(); // pairs of unit ids locked in melee, carried across rounds
  result: BattleResult | null = null;
  private brokenBeforeRound = new Set<string>();
  private modifiers: Record<string, Modifier> = {}; // this round's admin modifiers, while it is fought or previewed

  /**
   * @param units unit id -> {side, regiment, name?, meta?}; side is 0 or 1. Insertion order is the unit order
   *   used for tie-breaking and draws.
   * @param rng seeded generator (defaults to a randomly seeded one)
   * @param params per-battle constants (defaults to config)
   * @param meta free-form battle details, round-tripped untouched
   */
  constructor(units: Record<string, UnitSpec>, rng?: Rng, params?: BattleParams, meta?: Record<string, unknown>) {
    this.rng = rng ?? new Rng(Math.floor(Math.random() * 2 ** 32));
    this.seed = this.rng.seed;
    this.params = params ?? BattleParams.defaults();
    this.meta = { ...(meta ?? {}) };
    Object.entries(units).forEach(([uid, spec], index) => {
      if (spec.side !== 0 && spec.side !== 1) throw new ValueError(`side must be 0 or 1, got ${spec.side} for ${uid}.`);
      const regiment = spec.regiment;
      if (!(regiment instanceof Regiment)) throw new TypeError(`${uid} must be a Regiment.`);
      // units differ: each draws a multiplier on its break point from the seed, in unit order
      const spread = this.params.morale.break_point_spread;
      const scale = spread > 0 ? breakScale(this.rng.random(), spread) : 1.0;
      const morale = new MoraleState(regiment.size, regiment.stats[0], regiment.stats[1], this.params.morale, scale);
      const key: Unit = [regiment.unitType ?? 'inf', regiment.subtype];
      this.units.set(uid, new BattleUnit(uid, spec.side, regiment, morale, regiment.size, index, key,
        this.params.matchups.meleeRating(key), spec.name ?? uid, { ...(spec.meta ?? {}) }, regiment.stats));
    });
  }

  private unit(uid: string): BattleUnit {
    return this.units.get(uid)!;
  }

  private byIndex = (a: string, b: string): number => this.unit(a).index - this.unit(b).index;

  // ---------------------------------------------------------------------------
  // Orders and the targeting graph
  // ---------------------------------------------------------------------------

  private validateOrders(orders: Record<string, OrderInput | null>): Map<string, Order> {
    if (typeof orders !== 'object' || orders === null || Array.isArray(orders)) {
      throw new TypeError('orders must be an object of unit id -> order.');
    }
    const valid = new Map<string, Order>();
    for (const [uid, value] of Object.entries(orders)) {
      if (!this.units.has(uid)) throw new ValueError(`Unknown unit ${uid} in orders.`);
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        const unknown = Object.keys(value).filter((k) => !(ORDER_KEYS as readonly string[]).includes(k)).sort();
        if (unknown.length) {
          throw new ValueError(`Unknown order key(s) [${unknown.join(', ')}] for ${uid}; use target, mode, ammo, on_break.`);
        }
      }
      const order = makeOrder(value);
      if (order.mode === 'idle') continue;
      const unit = this.unit(uid);
      if (!unit.active) throw new ValueError(`${uid} is broken or wiped out and can't act.`);
      if (!this.units.has(order.target!)) throw new ValueError(`${uid} targets unknown unit ${order.target}.`);
      const target = this.unit(order.target!);
      if (target.side === unit.side) throw new ValueError(`${uid} can't target ${order.target}: same side.`);
      if (target.size === 0) throw new ValueError(`${uid} targets ${order.target}, which is wiped out.`);
      if (order.ammo !== null) {
        if (!(unit.regiment instanceof ArtilleryBattery)) throw new ValueError(`${uid} isn't artillery and can't choose ammo.`);
        if (!(order.ammo in this.params.combat.artillery_ammo)) {
          throw new ValueError(`${uid}: unknown ammo ${order.ammo}; one of ${Object.keys(this.params.combat.artillery_ammo)
            .sort().join(', ')}.`);
        }
      }
      valid.set(uid, order);
    }
    return valid;
  }

  /** Has firearms (the stats melee-only flag decides, not the subtype). */
  private canFire(unit: BattleUnit): boolean {
    return this.params.combat.unitCoef(unit.regiment.stats, 'ranged') > 0;
  }

  /** Contacts carried into this round: pairs still joined by a melee order, either way round. */
  private roundContacts(orders: Map<string, Order>): Set<string> {
    const melee = new Set<string>();
    for (const [uid, o] of orders) if (o.mode === 'melee') melee.add(pairKey(uid, o.target!));
    return new Set([...this.contacts].filter((pair) => melee.has(pair)));
  }

  /**
   * Charges made by melee orders on units not already in contact: [pending, immediate]. Pending approaches end
   * with a contact test (or a meeting); charging a broken unit is pursuit: contact at once.
   */
  private newCharges(orders: Map<string, Order>, contacts: Set<string>, start: number, duration: number): [Pending[], Charge[]] {
    const approach = this.params.charge.approach_minutes;
    const pending: Pending[] = [];
    const immediate: Charge[] = [];
    const seen = new Set<string>();
    for (const uid of [...orders.keys()].sort(this.byIndex)) {
      const order = orders.get(uid)!;
      const pair = pairKey(uid, order.target!);
      if (order.mode !== 'melee' || contacts.has(pair) || seen.has(pair)) continue;
      seen.add(pair);
      const target = this.unit(order.target!);
      if (!target.active) {
        contacts.add(pair);
        immediate.push(charge(uid, order.target!, start, start, 'pursuit'));
        continue;
      }
      const reply = orders.get(order.target!);
      const meeting = reply !== undefined && reply.mode === 'melee' && reply.target === uid;
      let minutes = approach[this.unit(uid).key[0]];
      if (meeting) minutes = Math.min(minutes, approach[target.key[0]]);
      pending.push({ charger: uid, target: order.target!, end: start + Math.min(minutes, duration), meeting });
    }
    return [pending, immediate];
  }

  /**
   * The arrow structure for this moment of the round: [slots, partners]. Slots are sorted by (target, attacker)
   * in unit order; partners maps each unit in melee contact to its contacts.
   */
  private plan(orders: Map<string, Order>, cancelled: Set<string>, contacts: Set<string>, pending: Pending[],
    withdrawn: Set<string> = new Set()): [Slot[], Map<string, string[]>] {
    const combat = this.params.combat;
    const matchups = this.params.matchups;

    const partners = new Map<string, string[]>();
    for (const key of contacts) {
      const [a, b] = pairOf(key).sort(this.byIndex);
      if (!partners.has(a)) partners.set(a, []);
      partners.get(a)!.push(b);
      if (!partners.has(b)) partners.set(b, []);
      partners.get(b)!.push(a);
    }
    for (const p of partners.values()) p.sort(this.byIndex);

    const slots: Slot[] = [];
    for (const [uid, ps] of partners) {
      const unit = this.unit(uid);
      if (unit.active && unit.meleeRating > 0) {
        for (const p of ps) slots.push([uid, p, 'melee', matchups.multiplier(unit.key, this.unit(p).key, 'melee'), 1.0, null]);
      }
    }

    const charging = new Set(pending.map((c) => c.charger));
    const closingOn = new Map<string, string[]>();
    for (const c of pending) {
      if (!c.meeting) {
        if (!closingOn.has(c.target)) closingOn.set(c.target, []);
        closingOn.get(c.target)!.push(c.charger);
      }
    }
    for (const [targetId, chargers] of closingOn) {
      const target = this.unit(targetId);
      if (target.active && !partners.has(targetId) && !charging.has(targetId) && this.canFire(target)) {
        const gunRate = target.regiment instanceof ArtilleryBattery
          ? combat.artillery_ammo[this.params.charge.battery_closing_ammo] : null;
        for (const charger of chargers) {
          slots.push([targetId, charger, 'closing', matchups.multiplier(target.key, this.unit(charger).key, 'ranged'),
            1.0 / chargers.length, gunRate]);
        }
      }
    }

    for (const [uid, order] of orders) {
      const unit = this.unit(uid);
      const outOfReach = withdrawn.has(order.target!) && !(unit.regiment instanceof ArtilleryBattery);
      if (order.mode === 'ranged' && !cancelled.has(uid) && unit.active && this.unit(order.target!).size > 0
        && !partners.has(uid) && !charging.has(uid) && !closingOn.has(uid) && !outOfReach && this.canFire(unit)) {
        // artillery: per-gun rate of the ordered ammo, fixed for the round
        const gunRate = unit.regiment instanceof ArtilleryBattery
          ? combat.artillery_ammo[order.ammo ?? combat.artillery_default_ammo] : null;
        slots.push([uid, order.target!, 'ranged', matchups.multiplier(unit.key, this.unit(order.target!).key, 'ranged'),
          1.0, gunRate]);
      }
    }

    slots.sort((s, t) => this.byIndex(s[1], t[1]) || this.byIndex(s[0], t[0]));
    return [slots, partners];
  }

  /** Current [attacker, target, mode, rate] for each slot with a positive rate. */
  private rates(slots: Slot[], partners: Map<string, string[]>): Arrow[] {
    const combat = this.params.combat;
    const closing = this.params.charge.closing_fire_multiplier;
    const totalFronts = new Map<string, number>();
    for (const [uid, ps] of partners) {
      let total = 0;
      for (const p of ps) total += this.unit(p).front;
      totalFronts.set(uid, total);
    }
    const arrows: Arrow[] = [];
    for (const [attacker, target, mode, matchup, share, gunRate] of slots) {
      const unit = this.unit(attacker);
      const stats = unit.regiment.stats;
      let rate: number;
      if (mode === 'melee') {
        const totalFront = totalFronts.get(attacker)!;
        if (totalFront <= 0) continue;
        // melee strength from the subtype's rating, not the firearm
        const c = combat.meleeEfficiency(stats[0], stats[1], unit.meleeRating);
        const frontT = this.unit(target).front;
        // fighters split in proportion to contact fronts; casualties scale with the width in contact
        const fighters = unit.front * (frontT / totalFront);
        rate = combat.melee_kill_rate * c * Math.min(fighters, frontT) * matchup;
      } else if (gunRate !== null) {
        // artillery fires per manned gun, at the rate of its ammo
        const c = combat.unitCoef(stats, 'ranged');
        rate = c * (unit.regiment as ArtilleryBattery).effectiveGuns * gunRate * matchup;
      } else {
        const c = combat.unitCoef(stats, 'ranged');
        rate = c * unit.size * combat.ranged_kill_rate * matchup;
      }
      const mod = this.modifiers[attacker];
      if (mod !== undefined) rate = rate * (1 + (mode === 'melee' ? mod.melee : mod.fire));
      if (mode === 'closing') rate = rate * closing * share;
      if (this.unit(target).morale.broken) {
        // a broken unit scatters: harder to hit by fire, and by pursuit
        rate = rate * (mode === 'melee' ? combat.broken_melee_multiplier : combat.broken_fire_multiplier);
      }
      if (rate > 0) arrows.push([attacker, target, mode, rate]);
    }
    return arrows;
  }

  /**
   * Preview the arrows and their current casualty rates for these orders (and admin modifiers) at the start of a
   * round (no dice rolled): melee along existing contacts, closing fire on new charges, ranged fire.
   */
  engagements(orders: Record<string, OrderInput | null>, modifiers: Record<string, ModifierInput> = {}): Engagement[] {
    const valid = this.validateOrders(orders);
    this.modifiers = validateModifiers(modifiers, this.units);
    try {
      const contacts = this.roundContacts(valid);
      const [pending] = this.newCharges(valid, contacts, this.time, Infinity);
      return this.rates(...this.plan(valid, new Set(), contacts, pending)).map(engagement);
    } finally {
      this.modifiers = {};
    }
  }

  // ---------------------------------------------------------------------------
  // Rounds
  // ---------------------------------------------------------------------------

  private advance(minutes: number, engaged: Set<string>): void {
    for (const [uid, unit] of this.units) unit.morale.advance(minutes, engaged.has(uid));
  }

  private sync(uids: Iterable<string>): void {
    for (const uid of uids) {
      const unit = this.unit(uid);
      unit.regiment.updateRawMorale(unit.morale.morale);
    }
  }

  /** Units among `candidates` that broke since last checked; records when in `brokeAt`. */
  private newlyBroken(candidates: Iterable<string>, brokeAt: Map<string, number>, t: number): Set<string> {
    const gone = new Set<string>();
    for (const uid of candidates) {
      if (!brokeAt.has(uid) && !this.brokenBeforeRound.has(uid) && this.unit(uid).morale.broken) {
        brokeAt.set(uid, t);
        gone.add(uid);
      }
    }
    return gone;
  }

  /** Semi-random whole-number share of `n` men: mean × (1 ± share_spread) from one draw, clamped, rounded half up. */
  private drawCount(meanShare: number, n: number): number {
    const spread = this.params.aftermath.share_spread;
    let share = meanShare * (1 + spread * (2 * this.rng.random() - 1));
    share = Math.min(1.0, Math.max(0.0, share));
    return Math.trunc(share * n + 0.5);
  }

  /** A battery keeps `keep` guns; the rest are captured by the other side. */
  private loseGuns(unit: BattleUnit, keep: number, guns: BySide): void {
    const battery = unit.regiment as ArtilleryBattery;
    const lost = battery.guns - keep;
    if (lost > 0) {
      battery.updateGuns(keep);
      unit.gunsLost += lost;
      guns[1 - unit.side] += lost;
      this.gunsCaptured[1 - unit.side] += lost;
    }
  }

  /**
   * Take prisoners from units that just broke (more if enemy cavalry is attacking them, or broke them with a
   * charge). A breaking battery escapes with only the guns its remaining crew can man; the rest are captured.
   */
  private rout(gone: Set<string>, arrows: Arrow[], prisoners: BySide, guns: BySide,
    cavalryCharged: Set<string> = new Set()): void {
    const after = this.params.aftermath;
    for (const uid of [...gone].sort(this.byIndex)) {
      const unit = this.unit(uid);
      if (!unit.morale.broken || unit.size === 0) continue;
      const cavalry = cavalryCharged.has(uid)
        || arrows.some((a) => a[1] === uid && this.unit(a[0]).regiment instanceof CavalryRegiment);
      const mean = Math.min(1.0, after.rout_capture_share * (cavalry ? after.cavalry_capture_multiplier : 1.0));
      const taken = this.drawCount(mean, unit.size);
      unit.regiment.updateSize(unit.size - taken);
      unit.captured += taken;
      prisoners[1 - unit.side] += taken;
      this.prisoners[1 - unit.side] += taken;
      if (unit.regiment instanceof ArtilleryBattery) this.loseGuns(unit, unit.regiment.effectiveGuns, guns);
    }
  }

  /** Roll the contact test for a charge at the end of its approach: [outcome, odds]. */
  private contactTest(c: Pending): [string, [number, number, number]] {
    const ch = this.params.charge;
    const a = this.unit(c.charger);
    const x = this.unit(c.target);
    const sA = ch.steadiness(a.morale.resolve, a.regiment.stats[0], a.morale.shock);
    const sX = ch.steadiness(x.morale.resolve, x.regiment.stats[0], x.morale.shock);
    const odds = ch.odds(ch.pressure(a.size, x.size, sA, sX, ch.bonus(a.key, x.key)));
    const u = this.rng.random();
    if (u < odds[0]) return ['defender_broke', odds];
    if (u < odds[0] + odds[1]) return ['faltered', odds];
    return ['home', odds];
  }

  /**
   * Fight one round of `duration` game minutes under `orders` and return its report. Units left out of `orders`
   * are idle. See the Python engine for the rules; this follows it step for step. `modifiers` are the admin's
   * for this round only, recorded in the report.
   */
  resolveRound(duration: number, orders: Record<string, OrderInput | null>, recordEvents = false,
    modifiers: Record<string, ModifierInput> = {}): RoundReport {
    if (this.finished) throw new RuntimeError('This battle is finished.');
    if (!(duration > 0)) throw new ValueError(`duration must be > 0, got ${duration}.`);
    const valid = this.validateOrders(orders);
    const checked = validateModifiers(modifiers, this.units);
    this.modifiers = checked;
    for (const [uid, mod] of Object.entries(checked)) this.unit(uid).morale.spendFactor = 1 - mod.morale;
    try {
      return this.fightRound(duration, valid, recordEvents, checked);
    } finally {
      this.modifiers = {};
      for (const uid of Object.keys(checked)) this.unit(uid).morale.spendFactor = 1;
    }
  }

  private fightRound(duration: number, valid: Map<string, Order>, recordEvents: boolean,
    checked: Record<string, Modifier>): RoundReport {
    const live = new Map(valid); // orders as they stand: a retarget changes the target here, not in valid

    this.round += 1;
    const start = this.time;
    const end = start + duration;
    const before = new Map([...this.units].map(([uid, u]) => [uid, [u.losses, u.inflicted, u.captured, u.gunsLost]]));
    const placed: Record<string, Position> = {};
    for (const [uid, u] of this.units) {
      if (u.regiment.position !== null) placed[uid] = { ...u.regiment.position, facing: u.regiment.position.facing ?? null };
    }
    const prisoners = bySide();
    const guns = bySide();
    this.brokenBeforeRound = new Set([...this.units].filter(([, u]) => u.morale.broken).map(([uid]) => uid));
    const brokeAt = new Map<string, number>();
    const cancelled = new Set<string>();
    const withdrawn = new Set<string>(); // faltered chargers, fallen back beyond musket range for the round
    const events: CasualtyEvent[] = [];
    const contacts = this.roundContacts(valid);
    const [pending, immediate] = this.newCharges(valid, contacts, start, duration);
    const charges: Charge[] = [...immediate];
    const retargets: Retarget[] = [];
    let [slots, partners] = this.plan(live, cancelled, contacts, pending, withdrawn);
    const opening = this.rates(slots, partners).map(engagement);

    /**
     * Units that broke or were wiped out: contacts and approaches end; melee attackers fall back, and fire on a
     * wiped-out unit stands down. Fire on a broken unit keeps going (on_break 'keep'), switches target
     * ('strongest' / 'weakest'), and a melee unit in contact with it stays in contact if its order says 'pursue'.
     */
    const standDown = (gone: Set<string>, t: number): void => {
      for (const uid of [...live.keys()].sort(this.byIndex)) {
        const order = live.get(uid)!;
        const unit = this.unit(uid);
        if (gone.has(order.target!) && (order.on_break === 'strongest' || order.on_break === 'weakest')
          && unit.active && !cancelled.has(uid)) {
          // strength: men × share of morale budget left; ties go to the first unit
          const candidates = [...this.units.values()].filter((u) => u.side !== unit.side && u.active);
          if (candidates.length) {
            const strength = (u: BattleUnit) => u.size * u.morale.resolve;
            let pick = candidates[0];
            for (const u of candidates.slice(1)) {
              if (order.on_break === 'strongest' ? strength(u) > strength(pick) : strength(u) < strength(pick)) pick = u;
            }
            live.set(uid, Object.freeze({ ...order, target: pick.uid }));
            retargets.push({ unit: uid, old_target: order.target!, new_target: pick.uid, time: t });
          }
        }
      }
      const pursuit = new Set<string>();
      for (const [uid, order] of live) {
        const pair = pairKey(uid, order.target!);
        if (gone.has(order.target!) && order.on_break === 'pursue' && this.unit(uid).active
          && this.unit(order.target!).size > 0 && contacts.has(pair)) pursuit.add(pair);
      }
      for (const [uid, order] of live) {
        if (gone.has(order.target!) && !pursuit.has(pairKey(uid, order.target!))
          && (order.mode === 'melee' || this.unit(order.target!).size === 0)) cancelled.add(uid);
      }
      for (const pair of [...contacts]) {
        if (pairOf(pair).some((u) => gone.has(u)) && !pursuit.has(pair)) contacts.delete(pair);
      }
      for (const c of pending.filter((p) => gone.has(p.charger) || gone.has(p.target))) {
        pending.splice(pending.indexOf(c), 1);
        charges.push(charge(c.charger, c.target, start, t, gone.has(c.charger) ? 'charger_broke' : 'target_broke'));
      }
    };

    let t = start;
    while (t < end) {
      const arrows = this.rates(slots, partners);
      let totalRate = 0.0;
      const engaged = new Set<string>();
      const attackers = new Set<string>();
      for (const [attackerId, targetId, , rate] of arrows) {
        totalRate += rate;
        attackers.add(attackerId);
        engaged.add(attackerId);
        engaged.add(targetId);
      }

      // the next scheduled moment: the round's end, or the end of an approach
      const horizon = Math.min(end, ...pending.map((c) => c.end));
      const dt = totalRate > 0 ? this.rng.exponential(totalRate) : null;
      if (dt === null || t + dt >= horizon) {
        this.advance(horizon - t, engaged);
        if (dt !== null) this.sync(engaged);
        t = horizon;
        let gone = this.newlyBroken(engaged, brokeAt, t);
        this.rout(gone, arrows, prisoners, guns);
        if (gone.size) standDown(gone, t);
        const due = pending.filter((c) => c.end <= t);
        for (const c of due) {
          pending.splice(pending.indexOf(c), 1);
          const pair = pairKey(c.charger, c.target);
          if (c.meeting) {
            contacts.add(pair);
            charges.push(charge(c.charger, c.target, start, t, 'meeting'));
            continue;
          }
          const [outcome, odds] = this.contactTest(c);
          charges.push(charge(c.charger, c.target, start, t, outcome, odds));
          const charger = this.unit(c.charger);
          const target = this.unit(c.target);
          const cavalryCharged = new Set<string>();
          if (outcome === 'home') {
            contacts.add(pair);
          } else if (outcome === 'faltered') {
            cancelled.add(charger.uid);
            withdrawn.add(charger.uid);
            charger.morale.shake(this.params.charge.falter_cost);
          } else {
            target.morale.forceBreak();
            if (charger.regiment instanceof CavalryRegiment) cavalryCharged.add(target.uid);
          }
          this.sync([charger.uid, target.uid]);
          gone = this.newlyBroken([charger.uid, target.uid], brokeAt, t);
          this.rout(gone, arrows, prisoners, guns, cavalryCharged);
          if (outcome === 'defender_broke' && target.regiment instanceof ArtilleryBattery) {
            this.loseGuns(target, 0, guns); // overrun where it stands: no time to limber up
          }
          if (gone.size) standDown(gone, t);
        }
        if (gone.size || due.length) [slots, partners] = this.plan(live, cancelled, contacts, pending, withdrawn);
        continue;
      }

      // weighted pick of the arrow that caused this casualty
      const pick = this.rng.random() * totalRate;
      let cumulative = 0.0;
      let chosen = arrows[arrows.length - 1];
      for (const arrow of arrows) {
        cumulative += arrow[3];
        if (pick < cumulative) {
          chosen = arrow;
          break;
        }
      }

      t += dt;
      this.advance(dt, engaged);

      const victim = this.unit(chosen[1]);
      const attacker = this.unit(chosen[0]);
      victim.regiment.updateSize(victim.size - 1);
      victim.losses += 1;
      attacker.inflicted += 1;
      victim.morale.takeLoss(attackers.has(victim.uid));
      attacker.morale.inflictLoss(victim.initialSize);
      this.sync(engaged);

      if (recordEvents) events.push({ time: t, attacker: attacker.uid, target: victim.uid });

      // a unit can break from its losses or from the in-combat drain; either way (or if wiped out)
      // its attackers stand down and the arrow structure is rebuilt
      const gone = this.newlyBroken(engaged, brokeAt, t);
      this.rout(gone, arrows, prisoners, guns);
      if (victim.size === 0) {
        gone.add(victim.uid);
        if (victim.regiment instanceof ArtilleryBattery) this.loseGuns(victim, 0, guns); // overrun: every gun taken
      }
      if (gone.size) {
        standDown(gone, t);
        [slots, partners] = this.plan(live, cancelled, contacts, pending, withdrawn);
      }
    }

    // contacts carry over only between units that are both still standing
    this.contacts = new Set([...contacts].filter((pair) => pairOf(pair).every((u) => this.unit(u).active)));
    this.time = end;
    const units: Record<string, UnitReport> = {};
    for (const [uid, u] of this.units) {
      const [losses, inflicted, captured, gunsLost] = before.get(uid)!;
      units[uid] = {
        losses: u.losses - losses,
        inflicted: u.inflicted - inflicted,
        size: u.size,
        morale: u.morale.morale,
        broken: u.morale.broken,
        broke_at: brokeAt.get(uid) ?? null,
        captured: u.captured - captured,
        guns_lost: u.gunsLost - gunsLost,
      };
    }
    const orderRecords: RoundReport['orders'] = {};
    for (const [uid, o] of valid) orderRecords[uid] = { target: o.target, mode: o.mode, ammo: o.ammo, on_break: o.on_break };
    const report: RoundReport = {
      round: this.round,
      start,
      end,
      orders: orderRecords,
      engagements: opening,
      units,
      events,
      prisoners,
      guns_captured: guns,
      charges,
      retargets,
      positions: placed,
      modifiers: checked,
    };
    this.history.push(report);
    return report;
  }

  // ---------------------------------------------------------------------------
  // Saving and loading (the battle state file)
  // ---------------------------------------------------------------------------

  /** The full battle state as a JSON-safe object; see state.ts. */
  toDict(): StateData {
    return battleToDict(this);
  }

  toJson(indent?: number): string {
    return JSON.stringify(this.toDict(), null, indent);
  }

  /** Rebuild a battle saved with toDict; resolving on from it gives exactly the same results. */
  static fromDict(data: StateData): Battle {
    return battleFromDict(data);
  }

  static fromJson(text: string): Battle {
    return Battle.fromDict(JSON.parse(text));
  }

  // ---------------------------------------------------------------------------
  // After the battle
  // ---------------------------------------------------------------------------

  private side(side: number): BattleUnit[] {
    return [...this.units.values()].filter((u) => u.side === side);
  }

  /** The side still standing when every unit of the other side is broken or wiped out; else null. */
  private armyOutHolder(): number | null {
    const out = [0, 1].map((side) => this.side(side).every((u) => !u.active));
    if (out[1] && !out[0]) return 0;
    if (out[0] && !out[1]) return 1;
    return null;
  }

  /** Each field test's vote for the side that is decisively ahead, or null (see the Python engine). */
  private fieldVotes(): Record<FieldTest, number | null> {
    const after = this.params.aftermath;
    const sum = (us: BattleUnit[], f: (u: BattleUnit) => number) => us.reduce((s, u) => s + f(u), 0);
    const sides = [0, 1].map((s) => this.side(s));
    const taken = sides.map((us) => sum(us, (u) => u.losses));
    const inflicted = sides.map((us) => sum(us, (u) => u.inflicted));
    const routed = sides.map((us) => sum(us, (u) => (u.active ? 0 : u.initialSize)) / sum(us, (u) => u.initialSize));
    const standing = sides.map((us) => sum(us, (u) => (u.active ? u.size : 0)));
    const vote = (ahead: (s: number, o: number) => boolean): number | null =>
      [0, 1].find((s) => ahead(s, 1 - s)) ?? null;
    return {
      exchange: vote((s) => inflicted[s] > 0 && inflicted[s] >= after.field_exchange_ratio * taken[s]),
      routs: vote((s, o) => routed[o] - routed[s] >= after.field_rout_gap),
      standing: vote((s, o) => standing[s] > 0 && standing[s] >= after.field_standing_ratio * standing[o]),
    };
  }

  /** The side with at least field_votes_needed votes and none against; else null (a draw). */
  private votedHolder(votes: Record<FieldTest, number | null>): number | null {
    const count = [0, 1].map((side) => Object.values(votes).filter((v) => v === side).length);
    for (const side of [0, 1]) {
      if (count[side] >= this.params.aftermath.field_votes_needed && count[1 - side] === 0) return side;
    }
    return null;
  }

  /**
   * End the battle and settle its casualties: men hit split into killed and wounded; on the side that lost the
   * field some wounded leave with their unit and a share of the rest are captured; a share of the wounded who
   * weren't captured recover and rejoin. `fieldHeldBy`: 0, 1, null or 'auto' (a whole army out, else the votes).
   */
  finish(fieldHeldBy: FieldHolder = 'auto'): BattleResult {
    if (this.finished) throw new RuntimeError('This battle is already finished.');
    const votes = this.fieldVotes();
    let holder: number | null;
    let decidedBy: string;
    if (fieldHeldBy === 'auto') {
      holder = this.armyOutHolder();
      decidedBy = holder === null ? 'votes' : 'army_out';
      if (holder === null) holder = this.votedHolder(votes);
    } else if (fieldHeldBy === null || fieldHeldBy === 0 || fieldHeldBy === 1) {
      holder = fieldHeldBy;
      decidedBy = 'admin';
    } else {
      throw new ValueError(`field_held_by must be 0, 1, null or 'auto', got ${JSON.stringify(fieldHeldBy)}.`);
    }

    const after = this.params.aftermath;
    const outcomes: Record<string, UnitOutcome> = {};
    for (const [uid, unit] of this.units) {
      const hits = unit.losses;
      const killed = this.drawCount(after.killed_share, hits);
      const wounded = hits - killed;
      let walking = 0;
      let captured = 0;
      if (holder !== null && unit.side !== holder) {
        walking = this.drawCount(after.walking_wounded_share, wounded);
        captured = this.drawCount(after.wounded_captured_share, wounded - walking);
        this.prisoners[holder] += captured;
      }
      const returned = this.drawCount(after.wounded_return_share, wounded - captured);
      unit.regiment.updateSize(unit.size + returned);
      outcomes[uid] = {
        hits, killed, wounded, walking_wounded: walking, wounded_captured: captured, wounded_returned: returned,
        captured_in_rout: unit.captured, final_size: unit.size, guns_lost: unit.gunsLost,
      };
    }

    this.finished = true;
    this.result = {
      field_held_by: holder, units: outcomes, prisoners: { ...this.prisoners }, guns_captured: { ...this.gunsCaptured },
      field_decided_by: decidedBy, field_votes: votes,
    };
    return this.result;
  }
}

function charge(charger: string, target: string, start: number, resolvedAt: number, outcome: string,
  odds: [number, number, number] | null = null): Charge {
  return {
    charger, target, start, resolved_at: resolvedAt, outcome,
    p_defender_breaks: odds ? odds[0] : null, p_falter: odds ? odds[1] : null, p_home: odds ? odds[2] : null,
  };
}

const engagement = ([attacker, target, mode, rate]: Arrow): Engagement => ({ attacker, target, mode, rate });
