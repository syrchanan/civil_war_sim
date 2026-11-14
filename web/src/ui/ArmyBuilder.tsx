/**
 * Two side-by-side tables of units, with each unit's corps, division and brigade. Each side's army can be saved as
 * a CSV file and loaded again (see armyCsv). The day, the ground and starting the battle are in the setup panel.
 */

import { useState } from 'preact/hooks';

import { ORG_KEYS } from '../engine';
import defaults from '../engine/defaults.json';
import { ArmyReview } from './ArmyReview';
import { save } from './FileBar';
import type { Store, UnitDraft, UnitType } from './store';

const SUBTYPES: Record<string, string[]> = defaults.unit_subtypes;
const TYPE_LABELS: [UnitType | '', string][] = [['inf', 'Infantry'], ['cav', 'Cavalry'], ['art', 'Artillery'],
  ['', 'Generic']];

/** Weapon code -> its name (guns are named differently). */
const weaponNames = (type: UnitType | null): [number, string][] =>
  Object.entries(type === 'art' ? defaults.names.artillery_weapons : defaults.names.weapons)
    .map(([name, code]) => [code, name] as [number, string]);

export const toNumber = (text: string): number => (text.trim() === '' ? NaN : Number(text));
/** What a number box shows: an emptied box holds NaN until something is typed. */
export const numberText = (n: number | null): string => (Number.isFinite(n) ? String(n) : '');
const ORG_LABELS = { corps: 'Corps', division: 'Division', brigade: 'Brigade' };

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
  const problem = store.unitProblem(unit);
  return (
    <tr id={`unit-${unit.id}`} class={problem === null ? undefined : 'has-problem'} title={problem ?? undefined}>
      <td data-label="Name"><input aria-label={label('name')} value={unit.name}
        onInput={(e) => set({ name: e.currentTarget.value })} /></td>
      <td data-label="Type">
        <select aria-label={label('type')} value={unit.type ?? ''}
          onChange={(e) => set({ type: (e.currentTarget.value || null) as UnitType | null })}>
          {TYPE_LABELS.map(([value, text]) => <option value={value}>{text}</option>)}
        </select>
      </td>
      <td data-label="Subtype">
        {unit.type === null ? '—' : (
          <select aria-label={label('subtype')} value={unit.subtype!}
            onChange={(e) => set({ subtype: e.currentTarget.value })}>
            {SUBTYPES[unit.type].map((s) => <option value={s}>{s}</option>)}
          </select>
        )}
      </td>
      <td data-label="Men"><input aria-label={label(unit.type === 'art' ? 'crew' : 'men')} type="number" min="1" class="num"
        value={numberText(unit.size)} onInput={(e) => set({ size: toNumber(e.currentTarget.value) })} /></td>
      <td data-label="Exp"><input aria-label={label('experience')} type="number" min="1" max="10" class="stat" value={xp}
        onInput={(e) => setStat(0, e.currentTarget.value)} /></td>
      <td data-label="Morale"><input aria-label={label('morale')} type="number" min="1" max="10" class="stat" value={morale}
        onInput={(e) => setStat(1, e.currentTarget.value)} /></td>
      <td data-label="Weapon">
        <select aria-label={label('weapon')} value={weapon} onChange={(e) => setStat(2, e.currentTarget.value)}>
          {weapons.map(([code, name]) => <option value={String(code)}>{name}</option>)}
        </select>
      </td>
      <td data-label="Melee only"><input aria-label={label('melee only')} type="checkbox" checked={meleeOnly === '1'}
        onChange={(e) => setStat(3, e.currentTarget.checked ? '1' : '0')} /></td>
      <td class="num" data-label="Guns">
        {unit.type === 'art'
          ? <input aria-label={label('guns')} type="number" min="0" class="num" value={numberText(unit.guns)}
            onInput={(e) => set({ guns: toNumber(e.currentTarget.value) })} />
          : '—'}
      </td>
      {ORG_KEYS.map((key) => (
        <td data-label={ORG_LABELS[key]}><input class="org" aria-label={label(key)} value={unit.org?.[key] ?? ''}
          onInput={(e) => {
            const org = { ...unit.org, [key]: e.currentTarget.value };
            if (org[key] === '') delete org[key];
            set({ org });
          }} /></td>
      ))}
      <td class="card-action"><button aria-label={`Remove ${unit.name}`} onClick={() => store.removeUnit(unit.id)}>×</button></td>
    </tr>
  );
}

function SideTable({ store, side }: { store: Store; side: 0 | 1 }) {
  const [problems, setProblems] = useState<string[]>([]);
  const units = store.units.value.filter((u) => u.side === side);
  const name = store.sides.value[side];
  const onLoad = async (input: HTMLInputElement) => {
    const file = input.files![0];
    input.value = '';
    if (!file) return;
    setProblems(store.loadArmy(side, await file.text(), file.name).map((p) => `${file.name}: ${p}`));
  };
  return (
    <div class={`side side-${side}`}>
      <input class="side-name" aria-label={`Side ${side + 1} name`} value={store.sides.value[side]}
        onInput={(e) => store.renameSide(side, e.currentTarget.value)} />
      <div class="table-wrap">
        <table aria-label={`${store.sides.value[side]} units`} class="stack">
          <thead>
            <tr>
              <th>Name</th><th>Type</th><th>Subtype</th><th class="num">Men</th><th>Exp</th><th>Morale</th>
              <th>Weapon</th><th>Melee only</th><th class="num">Guns</th><th>Corps</th><th>Division</th>
              <th>Brigade</th><th />
            </tr>
          </thead>
          <tbody>{units.map((u) => <UnitRow key={u.id} store={store} unit={u} />)}</tbody>
        </table>
      </div>
      <div class="controls">
        <button onClick={() => store.addUnit(side)}>Add unit to {name}</button>
        <button aria-label={`Download ${name} army (CSV)`} onClick={() => {
          const file = store.armyDownload(side);
          save(file.name, file.text, 'text/csv');
        }}>Download army (CSV)</button>
        <label class="button">
          Load army (CSV)
          <input type="file" accept=".csv,text/csv" aria-label={`Load ${name} army (CSV)`}
            onChange={(e) => onLoad(e.currentTarget)} />
        </label>
      </div>
      {problems.length > 0 && <ul role="alert" class="problems">{problems.map((p) => <li>{p}</li>)}</ul>}
      {store.mode.value === 'admin' && <ArmyReview store={store} side={side} />}
    </div>
  );
}

/** A player builds their own side's army; the other side's table is there to practise against. */
function PlayerArmy({ store }: { store: Store }) {
  const own = store.playerSide.value;
  const other = (1 - own) as 0 | 1;
  return (
    <div class="army-builder">
      <label class="you-command">
        You command{' '}
        <select aria-label="You command" value={String(own)}
          onChange={(e) => { store.playerSide.value = Number(e.currentTarget.value) as 0 | 1; }}>
          <option value="0">{store.sides.value[0]}</option>
          <option value="1">{store.sides.value[1]}</option>
        </select>
      </label>
      <SideTable store={store} side={own} />
      <details>
        <summary>{store.sides.value[other]}, to practise against</summary>
        <SideTable store={store} side={other} />
      </details>
    </div>
  );
}

export function ArmyBuilder({ store }: { store: Store }) {
  if (store.mode.value === 'player') return <PlayerArmy store={store} />;
  return (
    <div class="army-builder">
      <div class="sides">
        <SideTable store={store} side={0} />
        <SideTable store={store} side={1} />
      </div>
      <div class="controls">
        <button onClick={() => store.clearUnits()}>Clear all units</button>
      </div>
    </div>
  );
}
