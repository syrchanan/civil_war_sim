/** The vignette's colours, one letter each. Fixed in both colour schemes: it is a little painting, not chrome. */
export const PALETTE: Record<string, string> = {
  k: '#2a2420', // hats, boots, belts
  f: '#e0b08a', // skin
  m: '#b8c0c8', // steel
  w: '#7a4e2a', // wood
  c: '#b08a3e', // bronze
  h: '#7a4a2a', // horse
  H: '#3e2414', // mane, tail
  y: '#ffd84a', // flash
  o: '#ff8a2a', // flash, its heart
  g: '#e4e4dc', // smoke
  G: '#b4b4ac', // smoke, shaded
  l: '#6f9a4a', // grass
  L: '#557c36', // grass, darker
  E: '#2f5a2a', // canopy behind
  e: '#3f7a34', // leaves in front
  t: '#5a3c22', // trunk
  T: '#3e2a18', // trunk, shaded
  r: '#9a958c', // rock
  R: '#6a665f', // rock, shaded
};

export const SKY = '#cfe3ef';
export const SKY_WOODS = '#b9d3c0';

/**
 * Uniforms by side, American Civil War: the first side in Union dark blue coats, sky-blue trousers and kepis; the
 * second in Confederate cadet gray with butternut trousers. S coat, U trousers, K cap.
 */
export const UNIFORMS: [Record<string, string>, Record<string, string>] = [
  { S: '#2b3a63', U: '#7f9cc4', K: '#2b3a63' },
  { S: '#8d9094', U: '#9a7f52', K: '#7d8084' },
];
