/**
 * What the map shows. Every layer is one entry here (key, label, group, default): the layers panel and the map both
 * read this list, so a new layer is one more entry and its drawing. Choices are remembered per viewer in the
 * browser (a convenience: the map works the same when storage is blocked).
 */

export interface Layer {
  key: LayerKey;
  label: string;
  group: string;
  default: boolean;
}

export type LayerKey = 'symbols' | 'labels' | 'allArcs' | 'arrows' | 'grid' | 'scale';
export type Layers = Record<LayerKey, boolean>;

export const LAYERS: readonly Layer[] = [
  { key: 'symbols', label: 'NATO symbols', group: 'Units', default: true },
  { key: 'labels', label: 'Names and men', group: 'Units', default: true },
  { key: 'allArcs', label: 'Front arcs of all units', group: 'Facing', default: false },
  { key: 'arrows', label: 'Order arrows', group: 'Orders', default: true },
  { key: 'grid', label: 'Grid', group: 'Field', default: true },
  { key: 'scale', label: 'Scale bar', group: 'Field', default: true },
];

const STORAGE_KEY = 'map-layers';

export const defaultLayers = (): Layers =>
  Object.fromEntries(LAYERS.map((l) => [l.key, l.default])) as Layers;

/** The viewer's saved layers over the defaults; anything unreadable is ignored. */
export function loadLayers(): Layers {
  const layers = defaultLayers();
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}');
    for (const l of LAYERS) if (typeof saved?.[l.key] === 'boolean') layers[l.key] = saved[l.key];
  } catch {
    // blocked storage or a broken value: the defaults
  }
  return layers;
}

export function saveLayers(layers: Layers): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layers));
  } catch {
    // blocked storage: the choice lasts for this page only
  }
}

/**
 * A unit's NATO symbol (simplified APP-6): the arm drawn inside the frame (infantry: crossed diagonals; cavalry: one
 * diagonal; artillery: a dot) and the echelon above it, as bars (I battery, III regiment).
 */
export function natoSymbol(type: string | null): { arm: 'infantry' | 'cavalry' | 'artillery'; echelon: number } {
  if (type === 'art') return { arm: 'artillery', echelon: 1 };
  return { arm: type === 'cav' ? 'cavalry' : 'infantry', echelon: 3 };
}
