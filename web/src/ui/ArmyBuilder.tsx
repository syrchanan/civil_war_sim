/** Two side-by-side tables of units, a seed, and the button that starts the battle. */

import { useState } from 'preact/hooks';

import defaults from '../engine/defaults.json';
import type { Store, UnitDraft, UnitType } from './store';

const SUBTYPES: Record<string, string[]> = defaults.unit_subtypes;
const TYPE_LABELS: [UnitType | '', string][] = [['inf', 'Infantry'], ['cav', 'Cavalry'], ['art', 'Artillery'],
  ['', 'Generic']];

/** Weapon code -> its name (guns are named differently). */
const weaponNames = (type: UnitType | null): [number, string][] =>
  Object.entries(type === 'art' ? defaults.names.artillery_weapons : defaults.names.weapons)
    .map(([name, code]) => [code, name] as [number, string]);

const toNumber = (text: string): number => (text.trim() === '' ? NaN : Number(text));
/** What a number box shows: an emptied box holds NaN until something is typed. */
const numberText = (n: number | null): string => (Number.isFinite(n) ? String(n) : '');

function UnitRow({ store, unit }: { store: Store; unit: UnitDraft }) {
  const [xp, morale, weapon, meleeOnly] = unit.stats.split('/');
  const set = (change: Partial<UnitDraft>) => store.updateUnit(unit.id, change);
  const setStat = (index: number, value: string) => {
    const stats = unit.stats.split('/');
    stats[index] = value;
    set({ stats: stats.join('/') });
  };
  const label = (what: string) => `${unit.name} ${what}`;
  const weapons = weaponNames(unit.type);
  return (
    <tr>
      <td><input aria-label={label('name')} value={unit.name}
        onInput={(e) => set({ name: e.currentTarget.value })} /></td>
      <td>
        <select aria-label={label('type')} value={unit.type ?? ''}
          onChange={(e) => set({ type: (e.currentTarget.value || null) as UnitType | null })}>
          {TYPE_LABELS.map(([value, text]) => <option value={value}>{text}</option>)}
        </select>
      </td>
      <td>
        {unit.type === null ? '—' : (
          <select aria-label={label('subtype')} value={unit.subtype!}
            onChange={(e) => set({ subtype: e.currentTarget.value })}>
            {SUBTYPES[unit.type].map((s) => <option value={s}>{s}</option>)}
          </select>
        )}
      </td>
      <td><input aria-label={label(unit.type === 'art' ? 'crew' : 'men')} type="number" min="1" class="num"
        value={numberText(unit.size)} onInput={(e) => set({ size: toNumber(e.currentTarget.value) })} /></td>
      <td><input aria-label={label('experience')} type="number" min="1" max="10" class="stat" value={xp}
        onInput={(e) => setStat(0, e.currentTarget.value)} /></td>
      <td><input aria-label={label('morale')} type="number" min="1" max="10" class="stat" value={morale}
        onInput={(e) => setStat(1, e.currentTarget.value)} /></td>
      <td>
        <select aria-label={label('weapon')} value={weapon} onChange={(e) => setStat(2, e.currentTarget.value)}>
          {weapons.map(([code, name]) => <option value={String(code)}>{name}</option>)}
        </select>
      </td>
      <td><input aria-label={label('melee only')} type="checkbox" checked={meleeOnly === '1'}
        onChange={(e) => setStat(3, e.currentTarget.checked ? '1' : '0')} /></td>
      <td>
        {unit.type === 'art'
          ? <input aria-label={label('guns')} type="number" min="0" class="num" value={numberText(unit.guns)}
            onInput={(e) => set({ guns: toNumber(e.currentTarget.value) })} />
          : '—'}
      </td>
      <td><button aria-label={`Remove ${unit.name}`} onClick={() => store.removeUnit(unit.id)}>×</button></td>
    </tr>
  );
}

function SideTable({ store, side }: { store: Store; side: 0 | 1 }) {
  const units = store.units.value.filter((u) => u.side === side);
  return (
    <div class={`side side-${side}`}>
      <input class="side-name" aria-label={`Side ${side + 1} name`} value={store.sides.value[side]}
        onInput={(e) => store.renameSide(side, e.currentTarget.value)} />
      <div class="table-wrap">
        <table aria-label={`${store.sides.value[side]} units`}>
          <thead>
            <tr>
              <th>Name</th><th>Type</th><th>Subtype</th><th class="num">Men</th><th>Exp</th><th>Morale</th>
              <th>Weapon</th><th>Melee only</th><th class="num">Guns</th><th />
            </tr>
          </thead>
          <tbody>{units.map((u) => <UnitRow key={u.id} store={store} unit={u} />)}</tbody>
        </table>
      </div>
      <button onClick={() => store.addUnit(side)}>Add unit to {store.sides.value[side]}</button>
    </div>
  );
}

export function ArmyBuilder({ store }: { store: Store }) {
  const [problems, setProblems] = useState<string[]>([]);
  return (
    <div class="army-builder">
      <div class="sides">
        <SideTable store={store} side={0} />
        <SideTable store={store} side={1} />
      </div>
      <div class="controls">
        <label>
          Seed{' '}
          <input aria-label="Seed" type="number" min="0" class="num" value={numberText(store.seed.value)}
            onInput={(e) => { store.seed.value = toNumber(e.currentTarget.value); }} />
        </label>
        <button onClick={() => store.newSeed()}>New seed</button>
        <button onClick={() => store.clearUnits()}>Clear all units</button>
        <button class="primary" onClick={() => setProblems(store.start())}>Start battle</button>
      </div>
      {problems.length > 0 && (
        <ul role="alert" class="problems">{problems.map((p) => <li>{p}</li>)}</ul>
      )}
    </div>
  );
}
